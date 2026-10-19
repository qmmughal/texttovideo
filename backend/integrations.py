import copy, json, time, subprocess
from pathlib import Path
import httpx
import secrets
from .models import Scene
from .store import asset_path, uid

def request(base, method, route, **kwargs):
    with httpx.Client(timeout=600,trust_env=False) as client:
        result=client.request(method,base+route,**kwargs)
        result.raise_for_status()
        return result.json()

def storyboard(project, settings):
    if not settings.model: raise ValueError('Select an installed Ollama model in Settings. Install one with ollama pull qwen3:8b.')
    schema={'type':'object','properties':{'title':{'type':'string'},'description':{'type':'string'},'scenes':{'type':'array','minItems':1,'items':{'type':'object','properties':{'text':{'type':'string'},'prompt':{'type':'string'}},'required':['text','prompt']}}},'required':['title','description','scenes']}
    import math
    count=math.ceil(project.duration/settings.clip_seconds)
    schema['properties']['scenes']['minItems']=count
    schema['properties']['scenes']['maxItems']=count
    response=request(settings.ollama,'POST','/api/generate',json={'model':settings.model,'stream':False,'format':schema,'prompt':f'Create exactly {count} scenes for a {project.duration} second film. Language: {project.language}. Style: {project.style}. Return title, description, scenes with text (short spoken caption) and prompt (English visual description). Keep each spoken line within {settings.clip_seconds} seconds. Respect supplied scripts. Input: {project.prompt}'})
    result=json.loads(response['response'])
    if len(result['scenes'])!=count: raise ValueError(f'Model returned {len(result["scenes"])} scenes; expected {count}. Retry or change model.')
    project.title=result['title'];project.description=result['description']
    project.scenes=[Scene(id=uid(),text=s['text'],prompt=s['prompt'],duration=project.duration/count) for s in result['scenes']]
    return project

def replace_tokens(value, prompt):
    if isinstance(value,dict): return {k:replace_tokens(v,prompt) for k,v in value.items()}
    if isinstance(value,list): return [replace_tokens(v,prompt) for v in value]
    if isinstance(value,str): return value.replace('{{prompt}}',prompt)
    return value

def generate_visual(scene, mode, settings, cancelled, progress):
    workflow=settings.video_workflow if mode=='video' else settings.image_workflow
    if not workflow: raise ValueError(f'No {mode} workflow. Export a tested ComfyUI workflow in API format; paste it in Settings and replace positive prompt text with {{{{prompt}}}}.')
    if '{{prompt}}' not in json.dumps(workflow): raise ValueError('Workflow must include {{prompt}} in its positive text input.')
    if mode=='video' and scene.duration>settings.clip_seconds: raise ValueError('Scene exceeds configured model clip length. Split or shorten it first.')
    nodes=request(settings.comfy,'GET','/object_info')
    for node in workflow.values():
        if not isinstance(node,dict) or node.get('class_type') not in nodes: raise ValueError(f'Workflow node is missing in ComfyUI: {node.get("class_type") if isinstance(node,dict) else node}')
    prepared=replace_tokens(copy.deepcopy(workflow),scene.prompt)
    for node in prepared.values():
        for key in ('seed','noise_seed'):
            if isinstance(node.get('inputs',{}).get(key),int): node['inputs'][key]=secrets.randbelow(2**48)
    submitted=request(settings.comfy,'POST','/prompt',json={'prompt':prepared,'client_id':uid()})
    if 'prompt_id' not in submitted: raise ValueError('ComfyUI rejected workflow: '+str(submitted)[:1500])
    prompt_id=submitted['prompt_id'];deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        if cancelled():
            # Delete only our queued item. Never interrupt other users' active workflows.
            request(settings.comfy,'POST','/queue',json={'delete':[prompt_id]})
            raise RuntimeError('Cancelled. An already-running ComfyUI job may finish in ComfyUI; its output will not be applied.')
        history=request(settings.comfy,'GET','/history/'+prompt_id).get(prompt_id)
        if history:
            if history.get('status',{}).get('status_str')=='error': raise RuntimeError('ComfyUI execution failed: '+str(history.get('status'))[-1800:])
            for output in history.get('outputs',{}).values():
                for key in ('images','gifs','videos'):
                    for file in output.get(key,[]):
                        suffix=Path(file.get('filename','')).suffix.lower()
                        allowed=('.mp4','.webm','.mov') if mode=='video' else ('.png','.jpg','.jpeg','.webp')
                        if suffix not in allowed: continue
                        name=uid()+suffix
                        with httpx.Client(timeout=120,trust_env=False) as client:
                            response=client.get(settings.comfy+'/view',params={k:file[k] for k in ('filename','subfolder','type') if k in file});response.raise_for_status()
                            asset_path(name).write_bytes(response.content)
                        return name
            raise ValueError('Workflow finished without a supported saved output. Use SaveImage for images or a video-saving node returning an MP4/WebM output.')
        progress('ComfyUI queued / executing',None);time.sleep(1)
    raise TimeoutError('ComfyUI timed out after one hour. Check its queue and logs.')

def voice_info(settings):
    if not settings.voice: return {'available':False,'language':'','message':'Configure Piper executable and an ONNX voice, or upload narration.'}
    config=Path(settings.voice+'.json')
    if not config.is_file(): return {'available':False,'language':'','message':'Voice metadata .onnx.json is missing.'}
    language=json.loads(config.read_text(encoding='utf-8')).get('language',{}).get('code','')
    return {'available':Path(settings.voice).is_file() and Path(settings.piper).is_file(),'language':language,'message':'Urdu requires an Urdu voice; upload narration if your installed voice does not support Urdu.'}

def narrate(scene, language, settings, cancelled):
    info=voice_info(settings)
    if not info['available'] or not info['language'].startswith(language): raise ValueError('Installed Piper voice does not support this language. Configure a matching local voice or upload narration.')
    name=uid()+'.wav'
    with subprocess.Popen([settings.piper,'--model',settings.voice,'--output_file',str(asset_path(name))],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE) as proc:
        proc.stdin.write(scene.text.encode('utf-8'));proc.stdin.close();proc.stdin=None
        while True:
            try:
                _,error=proc.communicate(timeout=.5);break
            except subprocess.TimeoutExpired:
                if cancelled(): proc.kill();proc.communicate();raise RuntimeError('Cancelled')
        if proc.returncode: raise RuntimeError('Piper: '+error.decode(errors='replace')[-1500:])
    return name
