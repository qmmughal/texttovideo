import math
import os
import re
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, features

from .store import ROOT, asset_path, uid

FFMPEG = os.environ.get("FFMPEG_PATH") or imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
AUTO_MOTIONS = ("zoom_in", "pan_right", "zoom_out", "pan_left")
MAX_CROSSFADE_SCENES = 150


def probe(path):
    result = subprocess.run(
        [FFMPEG, "-hide_banner", "-protocol_whitelist", "file,pipe", "-i", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    text = result.stderr
    duration = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", text)
    size = re.search(r"Video:.*? (\d{2,5})x(\d{2,5})", text)
    return {
        "duration": sum(float(v) * m for v, m in zip(duration.groups(), (3600, 60, 1))) if duration else 0,
        "width": int(size[1]) if size else 0,
        "height": int(size[2]) if size else 0,
        "audio": "Audio:" in text,
        "video": "Video:" in text,
    }


def run(args, cancelled):
    log = ROOT / (uid() + ".log")
    with log.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], stdout=f, stderr=f)
        try:
            while proc.poll() is None:
                if cancelled():
                    proc.kill()
                    proc.wait()
                    raise RuntimeError("Cancelled")
                time.sleep(0.15)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    error = log.read_text(encoding="utf-8", errors="replace")
    log.unlink(missing_ok=True)
    if proc.returncode:
        raise RuntimeError("FFmpeg: " + error[-2500:])


# --- Captions ---------------------------------------------------------------


def caption_chunks(text, limit):
    """Split long scene text into readable cues, preferring sentence boundaries."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return [text] if text else []
    # Aim for evenly sized cues so none flashes by too quickly to read.
    target = len(text) / math.ceil(len(text) / limit)
    chunks, line = [], ""
    for word in text.split():
        proposed = f"{line} {word}".strip()
        if line and (len(proposed) > limit or len(line) >= target):
            chunks.append(line)
            line = word
        else:
            line = proposed
        if len(line) >= target * 0.6 and line[-1] in ".!?۔؟":
            chunks.append(line)
            line = ""
    if line:
        chunks.append(line)
    return chunks


def cue_times(chunks, duration):
    """Give each cue screen time proportional to its length."""
    total = sum(len(c) for c in chunks) or 1
    times, start = [], 0.0
    for chunk in chunks:
        end = start + duration * len(chunk) / total
        times.append((start, end))
        start = end
    return times


def caption_png(text, language, options, font_path):
    if not Path(font_path).is_file():
        raise ValueError("Caption font missing. Set a local Arabic/Urdu-capable font in Settings.")
    image = Image.new("RGBA", (options.width, options.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, options.font_size)
    raqm = features.check_feature("raqm")
    layout = {"direction": "rtl" if language == "ur" else "ltr"} if raqm else {}

    def shaped(line):
        if language != "ur" or raqm:
            return line
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(line))

    max_width = options.width * (1 - 2 * options.safe_area) - 24
    lines, line = [], ""
    for word in text.split():
        proposed = (line + " " + word).strip()
        if draw.textlength(shaped(proposed), font=font, **layout) > max_width and line:
            lines.append(line)
            line = word
        else:
            line = proposed
    if line:
        lines.append(line)
    line_height = int(options.font_size * 1.8)
    y = min(options.height * options.caption_y, options.height * (1 - options.safe_area) - len(lines) * line_height)
    if y < 0:
        raise ValueError("Caption is too long. Split the scene or reduce font size.")
    for line in lines:
        draw.text((options.width / 2, y), shaped(line), font=font, fill=options.color, anchor="mt",
                  stroke_width=2, stroke_fill="black", **layout)
        y += line_height
    name = uid() + ".png"
    image.save(asset_path(name))
    return name


def timestamp(seconds):
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# --- Video filters ----------------------------------------------------------


def fit_filter(fit, w, h):
    if fit == "crop":
        return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if fit == "contain":
        return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
    return (
        f"split[b][f];[b]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20[bg];"
        f"[f]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )


def motion_filter(motion, index, w, h, duration):
    """Ken Burns zoom/pan for still images over the clip's full length."""
    if motion == "auto":
        motion = AUTO_MOTIONS[index % len(AUTO_MOTIONS)]
    frames = max(1, math.ceil(duration * FPS))
    p = f"min(on/{frames},1)"
    center_x, center_y = "iw/2-iw/zoom/2", "ih/2-ih/zoom/2"
    zoom, x, y = {
        "zoom_in": (f"1+0.1*{p}", center_x, center_y),
        "zoom_out": (f"1.1-0.1*{p}", center_x, center_y),
        "pan_left": ("1.1", f"(iw-iw/zoom)*(1-{p})", center_y),
        "pan_right": ("1.1", f"(iw-iw/zoom)*{p}", center_y),
        "pan_up": ("1.1", center_x, f"(ih-ih/zoom)*(1-{p})"),
        "pan_down": ("1.1", center_x, f"(ih-ih/zoom)*{p}"),
        "none": ("1", "0", "0"),
    }[motion]
    # Working at twice the output size gives zoompan sub-pixel precision, which removes visible stutter.
    scale = 2 if w * h <= 1920 * 1080 else 1
    return f",scale={w * scale}:{h * scale},zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={FPS}"


def render(project, options, settings, progress, cancelled):
    if not project.scenes:
        raise ValueError("Add scenes before rendering.")
    crossfade = options.transition == "crossfade" and len(project.scenes) > 1 and options.fade >= 0.05
    if crossfade and len(project.scenes) > MAX_CROSSFADE_SCENES:
        raise ValueError(f"Crossfade supports up to {MAX_CROSSFADE_SCENES} scenes. Use fade through black instead.")
    clips, durations, subtitles, sources, temporary = [], [], [], [], []
    elapsed, cue = 0.0, 1
    w, h = options.width, options.height
    try:
        plans = []
        for index, scene in enumerate(project.scenes):
            source = asset_path(scene.asset)
            if not source.is_file():
                raise ValueError(f"Scene {index + 1} needs a visual.")
            is_image = source.suffix.lower() in IMAGE_SUFFIXES
            if project.mode == "video" and is_image:
                raise ValueError("AI-generated video mode requires video clips in every scene.")
            info = probe(source)
            duration = scene.duration
            if scene.narration:
                voice = probe(asset_path(scene.narration))
                if not voice["audio"]:
                    raise ValueError("Narration must contain audio.")
                duration = max(duration, voice["duration"] + 0.2)
            if not is_image and info["duration"] + 0.05 < duration:
                raise ValueError(
                    f'Scene {index + 1}: clip is too short ({info["duration"]:.1f}s for {duration:.1f}s). '
                    "Shorten scene or generate a longer clip; narration is never cut."
                )
            plans.append((scene, source, is_image, info, duration))
        # A crossfade overlaps neighbouring clips, so each clip except the last runs `blend` seconds longer.
        blend = min(options.fade, min(p[4] for p in plans) / 2) if crossfade else 0
        last = len(plans) - 1
        for index, (scene, source, is_image, info, duration) in enumerate(plans):
            progress(f"Rendering scene {index + 1}/{len(plans)}", index / len(plans) * 85)
            sources.append({"width": info["width"], "height": info["height"]})
            length = duration + (blend if index < last else 0)
            args = ["-framerate", str(FPS), "-loop", "1", "-i", str(source)] if is_image else ["-i", str(source)]
            if scene.narration:
                args += ["-i", str(asset_path(scene.narration))]
            else:
                args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            vf = "[0:v]" + fit_filter(options.fit, w, h) + ",setsar=1"
            if is_image:
                vf += motion_filter(scene.motion, index, w, h, length)
            else:
                vf += f",fps={FPS}"
                if length > duration:
                    # Only the outgoing half of a crossfade can show this held frame.
                    vf += f",tpad=stop_mode=clone:stop_duration={length - duration:.3f}"
            fade = min(options.fade, duration / 4)
            fade_in = options.transition == "fade" or (crossfade and index == 0)
            fade_out = options.transition == "fade" or (crossfade and index == last)
            if fade_in and fade > 0:
                vf += f",fade=t=in:st=0:d={fade}"
            if fade_out and fade > 0:
                vf += f",fade=t=out:st={length - fade}:d={fade}"
            vf += "[base]"
            current, input_index = "base", 2
            if options.captions and scene.text:
                chunks = caption_chunks(scene.text, options.caption_chars)
                for chunk, (start, end) in zip(chunks, cue_times(chunks, duration)):
                    caption = caption_png(chunk, project.language, options, settings.font)
                    temporary.append(caption)
                    args += ["-loop", "1", "-i", str(asset_path(caption))]
                    # Captions switch cleanly at scene time rather than overlapping the next scene's during a crossfade.
                    timed = len(chunks) > 1 or length > duration
                    enable = f":enable='between(t,{start:.3f},{end:.3f})'" if timed else ""
                    vf += f";[{current}][{input_index}:v]overlay=0:0{enable}[c{input_index}]"
                    current = f"c{input_index}"
                    input_index += 1
            if project.logo:
                args += ["-loop", "1", "-i", str(asset_path(project.logo))]
                margin_x, margin_y = round(w * options.safe_area), round(h * options.safe_area)
                vf += f";[{input_index}:v]scale={round(w * 0.15)}:-1[logo];[{current}][logo]overlay={margin_x}:{margin_y}[branded]"
                current = "branded"
            clip = uid() + ".mp4"
            temporary.append(clip)
            args += [
                "-filter_complex", vf, "-map", f"[{current}]", "-map", "1:a",
                "-af", f"apad,afade=t=in:d=0.05,afade=t=out:st={max(0, duration - 0.1)}:d=0.1",
                "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-threads", str(settings.threads),
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(asset_path(clip)),
            ]
            run(args, cancelled)
            clips.append(clip)
            durations.append(duration)
            chunks = caption_chunks(scene.text, options.caption_chars)
            for chunk, (start, end) in zip(chunks, cue_times(chunks, duration)):
                subtitles.append(f"{cue}\n{timestamp(elapsed + start)} --> {timestamp(elapsed + end)}\n{chunk}\n")
                cue += 1
            elapsed += duration

        progress("Assembling MP4 and mixing audio", 90)
        output = uid() + ".mp4"
        if crossfade:
            args, video, audio = [], "", ""
            for clip in clips:
                args += ["-i", str(asset_path(clip))]
            graph, previous, offset = [], "0:v", 0.0
            for index in range(1, len(clips)):
                offset += durations[index - 1]
                label = f"v{index}"
                graph.append(f"[{previous}][{index}:v]xfade=transition=fade:duration={blend:.3f}:offset={offset:.3f}[{label}]")
                previous = label
            video = previous
            # Audio is not blended: each clip contributes exactly its scene time, so narration is never faded early.
            for index, length in enumerate(durations):
                graph.append(f"[{index}:a]atrim=0:{length:.3f},asetpts=PTS-STARTPTS[a{index}]")
            graph.append("".join(f"[a{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=0:a=1[voice]")
            audio, music_input = "voice", len(clips)
            encode = ["-c:v", "libx264", "-preset", "veryfast", "-threads", str(settings.threads), "-pix_fmt", "yuv420p"]
        else:
            manifest = uid() + ".txt"
            temporary.append(manifest)
            asset_path(manifest).write_text("".join(f"file '{name}'\n" for name in clips), encoding="utf-8")
            args = ["-f", "concat", "-safe", "1", "-i", str(asset_path(manifest))]
            graph, video, audio, music_input = [], "0:v", "0:a", 1
            encode = ["-c:v", "copy"]
        if project.music:
            args += ["-stream_loop", "-1", "-i", str(asset_path(project.music))]
            graph.append(
                f"[{audio}]asplit[speech][control];[{music_input}:a]volume={options.music_volume}[music];"
                "[music][control]sidechaincompress=threshold=0.025:ratio=8[duck];"
                "[speech][duck]amix=inputs=2:duration=first:normalize=0,"
                f"afade=t=in:d=0.5,afade=t=out:st={max(0, elapsed - 0.5)}:d=0.5[mixed]"
            )
            audio = "mixed"
        if graph:
            def ref(label):
                return label if ":" in label else f"[{label}]"
            args += ["-filter_complex", ";".join(graph), "-map", ref(video), "-map", ref(audio), *encode, "-c:a", "aac"]
        else:
            args += ["-c", "copy"]
        args += ["-t", f"{elapsed:.3f}", "-movflags", "+faststart", str(asset_path(output))]
        run(args, cancelled)
        srt = uid() + ".srt"
        asset_path(srt).write_text("\n".join(subtitles), encoding="utf-8")
        return {
            "asset": output,
            "srt": srt,
            "duration": elapsed,
            "width": w,
            "height": h,
            "transition": options.transition,
            "sources": sources,
            "upscaled": any(s["width"] < w or s["height"] < h for s in sources),
        }
    finally:
        for name in temporary:
            asset_path(name).unlink(missing_ok=True)
