import json, os, platform, subprocess, threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from . import store, media, integrations
from .models import Project, Settings, Export

pool=ThreadPoolExecutor(max_workers=1)
lock=threading.RLock()

def settings():
    try: return Settings(**store.get('settings','local'))
    except KeyError: return Settings()

@asynccontextmanager
async def lifespan(app):
    for job in store.all_docs('job'):
        if job['status'] in ('running','queued'):
            job.update(status='interrupted',stage='Server restarted. Completed assets are safe; retry this job.');store.put('job',job['id'],job)
    yield

app=FastAPI(title='Frame Local Studio',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000','http://127.0.0.1:3000'],allow_methods=['GET','POST','PUT'],allow_headers=['Content-Type'])

@app.middleware('http')
async def local_only(request:Request,call_next):
    from fastapi.responses import JSONResponse
    origin=request.headers.get('origin')
    if origin and origin not in ('http://localhost:3000','http://127.0.0.1:3000','http://localhost:8000','http://127.0.0.1:8000'):
        return JSONResponse({'detail':'Untrusted origin'},403)
    if request.url.hostname not in ('localhost','127.0.0.1','::1','testserver'):
        return JSONResponse({'detail':'Localhost only'},403)
    return await call_next(request)

@app.exception_handler(KeyError)
async def not_found(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail':'Not found'},404)

@app.exception_handler(ValueError)
async def invalid(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail':str(exc)},400)

@app.get('/api/settings')
def read_settings(): return settings()

@app.put('/api/settings')
def save_settings(value:Settings):
    store.put('settings','local',value.model_dump());return value

@app.get('/api/status')
def status():
    s=settings();result={'cpu':platform.processor(),'threads':os.cpu_count(),'ffmpeg':media.FFMPEG,'voice':integrations.voice_info(s)}
    import httpx
    for name,base,route in [('ollama',s.ollama,'/api/tags'),('comfy',s.comfy,'/system_stats')]:
        try:
            with httpx.Client(timeout=3,trust_env=False) as client:
                response=client.get(base+route);response.raise_for_status();result[name]={'online':True,'data':response.json()}
        except Exception as exc: result[name]={'online':False,'error':str(exc)}
    return result

@app.get('/api/projects')
def projects(): return store.all_docs('project')

@app.post('/api/projects')
def create_project(value:Project):
    value.id=store.uid();value.exports=[];store.put('project',value.id,value.model_dump());return value

@app.put('/api/projects/{key}')
def save_project(key:str,value:Project):
    with lock:
        old=store.get('project',key)
        if any(j['project']==key and j['status'] in ('queued','running') for j in store.all_docs('job')): raise HTTPException(409,'Wait for or cancel the active job before editing.')
        value.id=key;value.exports=old.get('exports',[])
        store.put('project',key,value.model_dump())
    return value

@app.get('/api/projects/{key}')
def read_project(key:str): return store.get('project',key)

@app.post('/api/upload')
async def upload(file:UploadFile=File(...)):
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ('.png','.jpg','.jpeg','.webp','.mp4','.mov','.webm','.wav','.mp3','.m4a','.ogg'): raise HTTPException(400,'Unsupported media format')
    name=store.uid()+suffix;path=store.asset_path(name);total=0
    try:
        with path.open('wb') as out:
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total>512*1024*1024: raise ValueError('Upload exceeds 512 MB')
                out.write(chunk)
        if suffix in ('.png','.jpg','.jpeg','.webp'):
            with Image.open(path) as im: im.verify()
        else:
            info=media.probe(path)
            if not info['audio'] and not info['video']: raise ValueError('File is not valid audio/video')
        return {'asset':name,'info':media.probe(path)}
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400,'Invalid upload: '+str(exc)[:300]) from exc

@app.get('/api/assets/{name}')
def asset(name:str,download:bool=False):
    path=store.asset_path(name)
    if path.suffix not in ('.png','.jpg','.jpeg','.webp','.mp4','.mov','.webm','.wav','.mp3','.m4a','.ogg','.srt') or not path.is_file(): raise HTTPException(404)
    return FileResponse(path,filename=name if download or path.suffix=='.srt' else None)

def execute(key):
    job=store.get('job',key)
    def cancelled(): return store.get('job',key).get('cancel',False)
    def progress(stage,percent):
        with lock:
            current=store.get('job',key);current.update(stage=stage,status='running')
            if percent is not None: current['progress']=percent
            store.put('job',key,current)
    try:
        if cancelled(): raise RuntimeError('Cancelled')
        project=Project(**store.get('project',job['project']));s=settings();progress('Starting '+job['kind'],0)
        if job['kind']=='storyboard':
            project=integrations.storyboard(project,s)
        elif job['kind'] in ('visuals','narration'):
            scenes=[v for v in project.scenes if not job.get('scene') or v.id==job['scene']]
            if not scenes: raise ValueError('No scenes selected. Generate or add a storyboard first.')
            for index,scene in enumerate(scenes):
                if cancelled(): raise RuntimeError('Cancelled')
                progress(f'Generating scene {index+1}/{len(scenes)}',index/len(scenes)*100)
                if job['kind']=='visuals':
                    if scene.asset and not job.get('scene'): continue
                    scene.asset=integrations.generate_visual(scene,project.mode,s,cancelled,progress)
                else:
                    if scene.narration and not job.get('scene'): continue
                    scene.narration=integrations.narrate(scene,project.language,s,cancelled)
                if cancelled(): raise RuntimeError('Cancelled')
                store.put('project',project.id,project.model_dump())
        elif job['kind']=='render':
            output=media.render(project,Export(**job['options']),s,progress,cancelled)
            project.exports.append(output)
        if cancelled(): raise RuntimeError('Cancelled')
        store.put('project',project.id,project.model_dump())
        with lock:
            current=store.get('job',key);current.update(status='completed',stage='Complete',progress=100);store.put('job',key,current)
    except Exception as exc:
        with lock:
            current=store.get('job',key);current.update(status='cancelled' if cancelled() else 'failed',stage=str(exc));store.put('job',key,current)

@app.post('/api/projects/{key}/jobs/{kind}')
def start_job(key:str,kind:str,options:dict):
    if kind not in ('storyboard','visuals','narration','render'): raise HTTPException(400,'Unknown operation')
    with lock:
        store.get('project',key)
        if any(j['project']==key and j['status'] in ('queued','running') for j in store.all_docs('job')): raise HTTPException(409,'A job is already active for this project')
        if kind=='render': Export(**options)
        job={'id':store.uid(),'project':key,'kind':kind,'options':options,'scene':options.get('scene'),'status':'queued','stage':'Waiting for local worker','progress':0,'cancel':False}
        store.put('job',job['id'],job);pool.submit(execute,job['id'])
    return job

@app.get('/api/jobs')
def jobs(): return store.all_docs('job')

@app.post('/api/jobs/{key}/cancel')
def cancel(key:str):
    with lock:
        job=store.get('job',key);job['cancel']=True;store.put('job',key,job)
    return job

@app.post('/api/jobs/{key}/retry')
def retry(key:str):
    job=store.get('job',key)
    if job['status'] in ('running','queued'): raise HTTPException(409,'Job is active')
    return start_job(job['project'],job['kind'],job['options'])
