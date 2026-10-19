import os, tempfile
os.makedirs('data/test-runs',exist_ok=True)
os.environ['LOCAL_VIDEO_DATA']=tempfile.mkdtemp(prefix='frame-tests-',dir='data/test-runs')
import subprocess, time, wave
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend import media, store
from backend.main import app
from backend.models import Project, Scene, Settings, Export

@pytest.fixture
def project():
    Image.new('RGB',(320,240),'#679782').save(store.asset_path('test.png'))
    return Project(id='test',scenes=[Scene(id='one',text='A local story',duration=1,asset='test.png'),Scene(id='two',text='Another frame',duration=1,asset='test.png')])

@pytest.mark.parametrize('fit',['crop','contain','blur'])
def test_real_render(project,fit):
    result=media.render(project,Export(width=240,height=320,fit=fit,font_size=22),Settings(),lambda *a:None,lambda:False)
    info=media.probe(store.asset_path(result['asset']))
    assert info['width']==240 and info['height']==320
    assert abs(info['duration']-2)<.1 and info['audio']
    decoded=subprocess.run([media.FFMPEG,'-v','error','-i',str(store.asset_path(result['asset'])),'-f','null','-'],capture_output=True)
    assert decoded.returncode==0,decoded.stderr
    metadata=subprocess.run([media.FFMPEG,'-i',str(store.asset_path(result['asset']))],capture_output=True).stderr.decode(errors='replace')
    assert 'h264' in metadata and 'yuv420p' in metadata and 'aac' in metadata
    assert '00:00:02,000' in store.asset_path(result['srt']).read_text()

def test_narration_extends_image(project):
    with wave.open(str(store.asset_path('voice.wav')),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(b'\0\0'*32000)
    project.scenes=project.scenes[:1];project.scenes[0].narration='voice.wav'
    result=media.render(project,Export(width=240,height=320,captions=False),Settings(),lambda *a:None,lambda:False)
    assert result['duration']==2.2

def test_urdu_shaping():
    result=media.caption_png('یہ ایک خوبصورت نئی کہانی ہے', 'ur',Export(width=540,height=960,font_size=42),Settings().font)
    assert Image.open(store.asset_path(result)).getbbox() is not None

def test_no_silent_slideshow(project):
    project.mode='video'
    with pytest.raises(ValueError,match='requires video clips'):media.render(project,Export(),Settings(),lambda *a:None,lambda:False)

def test_api_validation_and_recovery():
    store.put('job','interrupted',{'id':'interrupted','project':'none','status':'running'})
    with TestClient(app) as client:
        assert store.get('job','interrupted')['status']=='interrupted'
        assert client.put('/api/settings',json={'ollama':'https://external.example'}).status_code==422
        assert client.post('/api/projects',json={'duration':-1}).status_code==422
        assert client.post('/api/upload',files={'file':('evil.mp4',b'not media','video/mp4')}).status_code==400
        assert client.post('/api/projects',json={},headers={'Origin':'https://evil.example'}).status_code==403
        assert client.get('/api/projects/missing').status_code==404
        p=client.post('/api/projects',json={}).json()
        j=client.post(f'/api/projects/{p["id"]}/jobs/render',json={}).json()
        for _ in range(50):
            current=store.get('job',j['id'])
            if current['status']=='failed':break
            time.sleep(.05)
        assert current['status']=='failed' and 'Add scenes' in current['stage']

def test_path_traversal():
    for name in ('../secret','..\\secret','C:\\Windows\\system.ini'):
        with pytest.raises(ValueError):store.asset_path(name)

def test_cancel(project):
    with pytest.raises(RuntimeError,match='Cancelled'):
        media.render(project,Export(width=240,height=320),Settings(),lambda *a:None,lambda:True)

@pytest.mark.parametrize('size',[(1080,1920),(1920,1080),(1080,1080),(1080,1350)])
def test_social_sizes(project,size):
    project.scenes=project.scenes[:1];project.scenes[0].duration=.5
    result=media.render(project,Export(width=size[0],height=size[1],captions=False),Settings(),lambda *a:None,lambda:False)
    info=media.probe(store.asset_path(result['asset']))
    assert (info['width'],info['height'])==size
    assert result['upscaled']

def test_music_logo_and_short_clip(project):
    with wave.open(str(store.asset_path('music.wav')),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(b'\0\0'*16000)
    project.music='music.wav';project.logo='test.png';project.scenes=project.scenes[:1]
    result=media.render(project,Export(width=240,height=320),Settings(),lambda *a:None,lambda:False)
    assert media.probe(store.asset_path(result['asset']))['audio']
    project.scenes[0].asset=result['asset'];project.scenes[0].duration=4;project.mode='video'
    with pytest.raises(ValueError,match='too short'):
        media.render(project,Export(width=240,height=320),Settings(),lambda *a:None,lambda:False)
