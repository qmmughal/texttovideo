import os, re, subprocess, time, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features
import imageio_ffmpeg
from .store import ROOT, asset_path, uid

FFMPEG = os.environ.get('FFMPEG_PATH') or imageio_ffmpeg.get_ffmpeg_exe()

def probe(path):
    result = subprocess.run([FFMPEG,'-hide_banner','-protocol_whitelist','file,pipe','-i',str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    text = result.stderr
    duration = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',text)
    size = re.search(r'Video:.*? (\d{2,5})x(\d{2,5})',text)
    return {'duration': sum(float(v)*m for v,m in zip(duration.groups(),(3600,60,1))) if duration else 0,
            'width': int(size[1]) if size else 0, 'height': int(size[2]) if size else 0,
            'audio': 'Audio:' in text, 'video': 'Video:' in text}

def run(args, cancelled):
    log = ROOT / (uid()+'.log')
    with log.open('w',encoding='utf-8') as f:
        proc = subprocess.Popen([FFMPEG,'-hide_banner','-loglevel','error','-y',*args],stdout=f,stderr=f)
        try:
            while proc.poll() is None:
                if cancelled():
                    proc.kill(); proc.wait(); raise RuntimeError('Cancelled')
                time.sleep(.15)
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()
    error = log.read_text(encoding='utf-8',errors='replace'); log.unlink(missing_ok=True)
    if proc.returncode: raise RuntimeError('FFmpeg: '+error[-2500:])

def caption_png(text, language, options, font_path):
    if not Path(font_path).is_file(): raise ValueError('Caption font missing. Set a local Arabic/Urdu-capable font in Settings.')
    im = Image.new('RGBA',(options.width,options.height)); draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(font_path,options.font_size)
    raqm=features.check_feature('raqm')
    layout={'direction':'rtl' if language=='ur' else 'ltr'} if raqm else {}
    def shaped(line):
        if language!='ur' or raqm: return line
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(line))
    max_width = options.width*(1-2*options.safe_area)-24
    lines, line = [], ''
    for word in text.split():
        proposed = (line+' '+word).strip()
        if draw.textlength(shaped(proposed),font=font,**layout)>max_width and line:
            lines.append(line); line=word
        else: line=proposed
    if line: lines.append(line)
    line_height = int(options.font_size*1.8)
    y = min(options.height*options.caption_y,options.height*(1-options.safe_area)-len(lines)*line_height)
    if y < 0: raise ValueError('Caption is too long. Split the scene or reduce font size.')
    for line in lines:
        draw.text((options.width/2,y),shaped(line),font=font,fill=options.color,anchor='mt',stroke_width=2,stroke_fill='black',**layout)
        y += line_height
    name=uid()+'.png'; im.save(asset_path(name)); return name

def timestamp(seconds):
    ms=round(seconds*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def render(project, options, settings, progress, cancelled):
    if not project.scenes: raise ValueError('Add scenes before rendering.')
    clips=[]; subtitles=[]; elapsed=0; sources=[]; temporary=[]
    try:
        for index, scene in enumerate(project.scenes):
            progress(f'Rendering scene {index+1}/{len(project.scenes)}',index/len(project.scenes)*85)
            source=asset_path(scene.asset)
            if not source.is_file(): raise ValueError(f'Scene {index+1} needs a visual.')
            is_image=source.suffix.lower() in ('.png','.jpg','.jpeg','.webp')
            if project.mode=='video' and is_image: raise ValueError('AI-generated video mode requires video clips in every scene.')
            info=probe(source); sources.append({'width':info['width'],'height':info['height']})
            duration=scene.duration
            if scene.narration:
                voice=probe(asset_path(scene.narration))
                if not voice['audio']: raise ValueError('Narration must contain audio.')
                duration=max(duration,voice['duration']+.2)
            if not is_image and info['duration']+.05<duration:
                raise ValueError(f'Scene {index+1}: clip is too short ({info["duration"]:.1f}s for {duration:.1f}s). Shorten scene or generate a longer clip; narration is never cut.')
            args=['-loop','1','-i',str(source)] if is_image else ['-i',str(source)]
            args+=['-i',str(asset_path(scene.narration))] if scene.narration else ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
            w,h=options.width,options.height
            if options.fit=='crop': vf=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
            elif options.fit=='contain': vf=f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black'
            else: vf=f'split[b][f];[b]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20[bg];[f]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2'
            vf='[0:v]'+vf+',setsar=1'
            if is_image:
                vf+=f",zoompan=z='min(zoom+0.00035,1.04)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps=30"
            else: vf+=',fps=30'
            fade=min(options.fade,duration/4)
            vf+=f',fade=t=in:st=0:d={max(fade,.001)},fade=t=out:st={duration-fade}:d={max(fade,.001)}[base]'
            current='base'; input_index=2
            if options.captions and scene.text:
                caption=caption_png(scene.text,project.language,options,settings.font); temporary.append(caption)
                args+=['-loop','1','-i',str(asset_path(caption))]
                vf+=f';[{current}][{input_index}:v]overlay=0:0[captioned]';current='captioned';input_index+=1
            if project.logo:
                args+=['-loop','1','-i',str(asset_path(project.logo))]
                vf+=f';[{input_index}:v]scale={round(w*.15)}:-1[logo];[{current}][logo]overlay={round(w*options.safe_area)}:{round(h*options.safe_area)}[branded]';current='branded'
            clip=uid()+'.mp4'; temporary.append(clip)
            args+=['-filter_complex',vf,'-map',f'[{current}]','-map','1:a','-af',f'apad,afade=t=in:d=0.05,afade=t=out:st={duration-.1}:d=0.1','-t',str(duration),'-c:v','libx264','-preset','veryfast','-threads',str(settings.threads),'-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2',str(asset_path(clip))]
            run(args,cancelled);clips.append(clip)
            subtitles.append(f'{index+1}\n{timestamp(elapsed)} --> {timestamp(elapsed+duration)}\n{scene.text}\n'); elapsed+=duration
        progress('Assembling MP4 and mixing audio',90)
        manifest=uid()+'.txt'; temporary.append(manifest)
        asset_path(manifest).write_text(''.join(f"file '{name}'\n" for name in clips),encoding='utf-8')
        output=uid()+'.mp4'; args=['-f','concat','-safe','1','-i',str(asset_path(manifest))]
        if project.music:
            args+=['-stream_loop','-1','-i',str(asset_path(project.music)),'-filter_complex',f'[0:a]asplit[voice][control];[1:a]volume={options.music_volume}[music];[music][control]sidechaincompress=threshold=0.025:ratio=8[duck];[voice][duck]amix=inputs=2:duration=first:normalize=0,afade=t=in:d=0.5,afade=t=out:st={max(0,elapsed-.5)}:d=0.5[a]','-map','0:v','-map','[a]','-c:v','copy','-c:a','aac']
        else: args+=['-c','copy']
        args+=['-t',str(elapsed),'-movflags','+faststart',str(asset_path(output))];run(args,cancelled)
        srt=uid()+'.srt';asset_path(srt).write_text('\n'.join(subtitles),encoding='utf-8')
        return {'asset':output,'srt':srt,'duration':elapsed,'width':options.width,'height':options.height,'sources':sources,'upscaled':any(s['width']<options.width or s['height']<options.height for s in sources)}
    finally:
        for name in temporary: asset_path(name).unlink(missing_ok=True)
