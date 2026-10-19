import base64
import copy
import io
import json
import math
import os
import secrets
import subprocess
import time
from pathlib import Path

import httpx
from PIL import Image

from . import safety, voices
from .models import Scene
from .store import asset_path, uid

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def request(base, method, route, **kwargs):
    with httpx.Client(timeout=600, trust_env=False) as client:
        result = client.request(method, base + route, **kwargs)
        result.raise_for_status()
        return result.json()


# --- Ollama -----------------------------------------------------------------


def capabilities(settings, model):
    """Capabilities Ollama reports for a model, e.g. completion, vision, thinking."""
    try:
        return request(settings.ollama, "POST", "/api/show", json={"model": model}).get("capabilities", [])
    except httpx.HTTPError:
        return []


def ollama_json(settings, model, prompt, schema, images=None):
    body = {"model": model, "stream": False, "format": schema, "prompt": prompt}
    if images:
        body["images"] = images
    if "thinking" in capabilities(settings, model):
        # Reasoning output is not needed for structured answers and slows small machines down.
        body["think"] = False
    reply = request(settings.ollama, "POST", "/api/generate", json=body)
    # Some Ollama versions route a thinking model's structured answer into "thinking" instead of "response".
    for text in (reply.get("response", ""), reply.get("thinking", "")):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"{model} did not return valid JSON. Retry, or choose a different model in Settings.")


def storyboard(project, settings):
    if not settings.model:
        raise ValueError("Select an installed Ollama model in Settings. Install one with ollama pull qwen3:8b.")
    safety.review([project.prompt, project.style], settings)
    count = math.ceil(project.duration / settings.clip_seconds)
    scene_schema = {
        "type": "object",
        "properties": {"text": {"type": "string", "minLength": 1}, "prompt": {"type": "string", "minLength": 1}},
        "required": ["text", "prompt"],
    }
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "scenes": {"type": "array", "minItems": count, "maxItems": count, "items": scene_schema},
        },
        "required": ["title", "description", "scenes"],
    }
    prompt = (
        f"Create exactly {count} scenes for a {project.duration} second film. Language: {project.language}. "
        f"Style: {project.style}. Return title, description, scenes with text (short spoken caption) and prompt "
        f"(English visual description). Keep each spoken line within {settings.clip_seconds} seconds. "
        f"Respect supplied scripts. {safety.GENERATION_RULES} Input: {project.prompt}"
    )
    result = ollama_json(settings, settings.model, prompt, schema)
    if len(result["scenes"]) != count:
        raise ValueError(f'Model returned {len(result["scenes"])} scenes; expected {count}. Retry or change model.')
    empty = sum(1 for s in result["scenes"] if not s["text"].strip() or not s["prompt"].strip())
    if empty:
        raise ValueError(
            f"{settings.model} left {empty} scene(s) without a caption or visual prompt. Retry, or install the "
            "larger model recommended in Setup check."
        )
    written = [result["title"], result["description"]]
    safety.review(written + [t for s in result["scenes"] for t in (s["text"], s["prompt"])], settings)
    project.title = result["title"]
    project.description = result["description"]
    project.scenes = [
        Scene(id=uid(), text=s["text"], prompt=s["prompt"], duration=project.duration / count)
        for s in result["scenes"]
    ]
    return project


def encode_photo(name, longest=1024):
    """Downscale a photo before sending it to a vision model; smaller images are much faster."""
    with Image.open(asset_path(name)) as image:
        image = image.convert("RGB")
        image.thumbnail((longest, longest))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=88)
    return base64.b64encode(buffer.getvalue()).decode()


def describe_photos(project, settings, cancelled, progress, only_scene=None):
    """Write captions and visual prompts for photo scenes with a local vision model."""
    model = settings.vision_model
    if not model:
        raise ValueError("Choose a vision model in Settings. Install one with ollama pull qwen3-vl:8b.")
    if "vision" not in capabilities(settings, model):
        raise ValueError(f"{model} cannot read images. Choose a vision model such as qwen3-vl:8b or gemma3.")
    photos = [s for s in project.scenes if Path(s.asset).suffix.lower() in IMAGE_SUFFIXES]
    if only_scene:
        photos = [s for s in photos if s.id == only_scene]
    if not photos:
        raise ValueError("Add photos to scenes first. Only image scenes can be described.")
    safety.review([project.prompt], settings)
    language = "Urdu" if project.language == "ur" else "English"
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string", "minLength": 1}, "prompt": {"type": "string", "minLength": 1}},
        "required": ["text", "prompt"],
    }
    for index, scene in enumerate(photos):
        if cancelled():
            raise RuntimeError("Cancelled")
        if scene.text and not only_scene:
            continue
        progress(f"Describing photo {index + 1}/{len(photos)}", index / len(photos) * 90)
        position = project.scenes.index(scene) + 1
        story = [s.text for s in project.scenes[: position - 1] if s.text]
        words = max(4, round(scene.duration * 2.3))
        prompt = (
            f"You are narrating scene {position} of {len(project.scenes)} in a short {project.style.lower()} film "
            f"built from personal photos. Creator's theme: {project.prompt.strip() or 'none given'}. "
            f"Narration so far: {' / '.join(story[-3:]) or 'this is the opening scene'}. "
            f'Look at the photo. Return "text": narration in {language} for this photo that continues the story, '
            f'at most {words} words, natural to read aloud, no hashtags or emoji; and "prompt": a concise English '
            f"description of what the photo shows. {safety.GENERATION_RULES}"
        )
        result = ollama_json(settings, model, prompt, schema, images=[encode_photo(scene.asset)])
        scene.text = result["text"].strip()[:3000]
        scene.prompt = result["prompt"].strip()[:5000]
    story = [s.text for s in project.scenes if s.text]
    if story and project.title.strip() in ("", "Untitled film"):
        progress("Naming the film", 95)
        summary = ollama_json(
            settings,
            model,
            f"Give a short title (max 6 words) and one-sentence description in {language} for a film with this "
            f"narration: {' '.join(story)}",
            {
                "type": "object",
                "properties": {"title": {"type": "string"}, "description": {"type": "string"}},
                "required": ["title", "description"],
            },
        )
        project.title = summary["title"].strip()[:200] or project.title
        project.description = summary["description"].strip()
    # Photos can carry content the theme did not; check what was written before it is saved.
    safety.review([project.title, project.description] + [t for s in photos for t in (s.text, s.prompt)], settings)
    return project


LANGUAGES = {"en": "English", "ur": "Urdu"}
SCRIPT_RULES = {
    "ur": "Write Urdu in Urdu script (Nastaliq/Arabic letters), never in Roman Urdu or Latin letters.",
    "en": "Write in English.",
}


def in_script(text, language):
    """Urdu output must be mostly Arabic-script letters; models often slip into Roman Urdu."""
    if language != "ur":
        return True
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum("؀" <= c <= "ۿ" for c in letters) / len(letters) > 0.6


def translate(project, settings, source, cancelled, progress, batch=12):
    """Translate captions, title and description; visual prompts stay in English for image models."""
    if not settings.model:
        raise ValueError("Select an installed Ollama model in Settings to translate.")
    src, dst = LANGUAGES[source], LANGUAGES[project.language]
    spoken = [s for s in project.scenes if s.text.strip()]
    safety.review([project.title, project.description] + [s.text for s in spoken], settings)
    for start in range(0, len(spoken), batch):
        if cancelled():
            raise RuntimeError("Cancelled")
        chunk = spoken[start : start + batch]
        progress(f"Translating scenes {start + 1}-{start + len(chunk)} of {len(spoken)}", start / max(len(spoken), 1) * 90)
        schema = {
            "type": "object",
            "properties": {"lines": {"type": "array", "minItems": len(chunk), "maxItems": len(chunk),
                                     "items": {"type": "string", "minLength": 1}}},
            "required": ["lines"],
        }
        numbered = "\n".join(f"{i + 1}. {s.text}" for i, s in enumerate(chunk))
        prompt = (
            f"Translate these {len(chunk)} narration lines of a short film from {src} to {dst}. Keep the meaning, "
            f"tone and roughly the same length, natural to read aloud. {SCRIPT_RULES[project.language]} "
            f"{safety.GENERATION_RULES} "
            f"Return exactly {len(chunk)} lines in order, without numbers.\n{numbered}"
        )
        for attempt in range(2):
            lines = ollama_json(settings, settings.model, prompt, schema)["lines"]
            complete = len(lines) == len(chunk) and all(line.strip() for line in lines)
            if complete and all(in_script(line, project.language) for line in lines):
                break
        else:
            raise ValueError(
                f"{settings.model} did not return a complete {dst} translation in {dst} script. "
                "Retry or choose a larger model."
            )
        for scene, line in zip(chunk, lines):
            scene.text = line.strip()[:3000]
    progress("Translating title", 95)
    meta = ollama_json(
        settings, settings.model,
        f"Translate this film title and description from {src} to {dst}. {SCRIPT_RULES[project.language]}\n"
        f"Title: {project.title}\n"
        f"Description: {project.description or '-'}",
        {"type": "object", "properties": {"title": {"type": "string", "minLength": 1}, "description": {"type": "string"}},
         "required": ["title", "description"]},
    )
    project.title = meta["title"].strip()[:200] or project.title
    project.description = meta["description"].strip()
    return project


# --- ComfyUI ----------------------------------------------------------------


def replace_tokens(value, prompt):
    if isinstance(value, dict):
        return {k: replace_tokens(v, prompt) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_tokens(v, prompt) for v in value]
    if isinstance(value, str):
        return value.replace("{{prompt}}", prompt)
    return value


def generate_visual(scene, mode, settings, cancelled, progress):
    workflow = settings.video_workflow if mode == "video" else settings.image_workflow
    if not workflow:
        raise ValueError(
            f"No {mode} workflow. Export a tested ComfyUI workflow in API format; paste it in Settings and "
            "replace positive prompt text with {{prompt}}."
        )
    if "{{prompt}}" not in json.dumps(workflow):
        raise ValueError("Workflow must include {{prompt}} in its positive text input.")
    if mode == "video" and scene.duration > settings.clip_seconds:
        raise ValueError("Scene exceeds configured model clip length. Split or shorten it first.")
    nodes = request(settings.comfy, "GET", "/object_info")
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") not in nodes:
            missing = node.get("class_type") if isinstance(node, dict) else node
            raise ValueError(f"Workflow node is missing in ComfyUI: {missing}")
    prepared = replace_tokens(copy.deepcopy(workflow), scene.prompt)
    for node in prepared.values():
        for key in ("seed", "noise_seed"):
            if isinstance(node.get("inputs", {}).get(key), int):
                node["inputs"][key] = secrets.randbelow(2**48)
    submitted = request(settings.comfy, "POST", "/prompt", json={"prompt": prepared, "client_id": uid()})
    if "prompt_id" not in submitted:
        raise ValueError("ComfyUI rejected workflow: " + str(submitted)[:1500])
    prompt_id = submitted["prompt_id"]
    deadline = time.monotonic() + 3600
    allowed = (".mp4", ".webm", ".mov") if mode == "video" else IMAGE_SUFFIXES
    while time.monotonic() < deadline:
        if cancelled():
            # Delete only our queued item. Never interrupt other users' active workflows.
            request(settings.comfy, "POST", "/queue", json={"delete": [prompt_id]})
            raise RuntimeError("Cancelled. An already-running ComfyUI job may finish in ComfyUI; its output will not be applied.")
        history = request(settings.comfy, "GET", "/history/" + prompt_id).get(prompt_id)
        if history:
            if history.get("status", {}).get("status_str") == "error":
                raise RuntimeError("ComfyUI execution failed: " + str(history.get("status"))[-1800:])
            for output in history.get("outputs", {}).values():
                for key in ("images", "gifs", "videos"):
                    for file in output.get(key, []):
                        suffix = Path(file.get("filename", "")).suffix.lower()
                        if suffix not in allowed:
                            continue
                        name = uid() + suffix
                        params = {k: file[k] for k in ("filename", "subfolder", "type") if k in file}
                        with httpx.Client(timeout=120, trust_env=False) as client:
                            response = client.get(settings.comfy + "/view", params=params)
                            response.raise_for_status()
                            asset_path(name).write_bytes(response.content)
                        return name
            raise ValueError(
                "Workflow finished without a supported saved output. Use SaveImage for images or a video-saving "
                "node returning an MP4/WebM output."
            )
        progress("ComfyUI queued / executing", None)
        time.sleep(1)
    raise TimeoutError("ComfyUI timed out after one hour. Check its queue and logs.")


# --- Narration --------------------------------------------------------------

LIST_VOICES = (
    "Add-Type -AssemblyName System.Speech;"
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "try{ConvertTo-Json -Compress -InputObject @($s.GetInstalledVoices()|Where-Object Enabled|"
    "ForEach-Object{@{name=$_.VoiceInfo.Name;language=$_.VoiceInfo.Culture.Name}})}finally{$s.Dispose()}"
)

SPEAK = (
    "$ErrorActionPreference='Stop';Add-Type -AssemblyName System.Speech;"
    "$text=[IO.File]::ReadAllText($env:FRAME_TEXT,[Text.Encoding]::UTF8);"
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$words=New-Object Collections.ArrayList;"
    "$s.add_SpeakProgress({param($sender,$e)[void]$words.Add(@{start=$e.AudioPosition.TotalSeconds;"
    "at=$e.CharacterPosition;length=$e.CharacterCount})});"
    "try{$s.SelectVoice($env:FRAME_VOICE);$s.Rate=[int]$env:FRAME_RATE;"
    "$s.SetOutputToWaveFile($env:FRAME_OUT);$s.Speak($text)}finally{$s.Dispose()};"
    "[IO.File]::WriteAllText($env:FRAME_WORDS,(ConvertTo-Json -Compress -InputObject @($words)),[Text.Encoding]::UTF8)"
)


def powershell(script, env=None, timeout=30):
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )


def windows_voices():
    """Installed Windows (SAPI) voices as [{name, language}]; empty off Windows."""
    if os.name != "nt":
        return []
    try:
        result = powershell(LIST_VOICES)
        return json.loads(result.stdout or "[]") if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def pick_windows_voice(settings, language, voices):
    for voice in voices:
        if voice["name"] == settings.windows_voice and voice["language"].startswith(language):
            return voice
    return next((v for v in voices if v["language"].startswith(language)), None)


def voice_info(settings):
    if settings.tts == "builtin":
        ready = [v for v in voices.status() if v["downloaded"]]
        if not voices.available():
            return {"engine": "builtin", "available": False, "language": "", "voices": [],
                    "message": "The built-in voice engine (sherpa-onnx) is not installed. Run setup again."}
        if not ready:
            return {"engine": "builtin", "available": False, "language": "", "voices": [],
                    "message": "Download an English or Urdu voice in Setup check."}
        languages = sorted({v["language"] for v in ready})
        return {"engine": "builtin", "available": True, "language": ", ".join(languages),
                "voices": [{"name": v["key"], "language": v["language"]} for v in ready],
                "message": f"Downloaded voices: {', '.join(v['name'] for v in ready)}."}
    if settings.tts == "windows":
        system_voices = windows_voices()
        if not system_voices:
            return {"engine": "windows", "available": False, "language": "", "voices": [],
                    "message": "No Windows voices found. Add one in Settings > Time & language > Speech."}
        chosen = next((v for v in system_voices if v["name"] == settings.windows_voice), system_voices[0])
        languages = sorted({v["language"] for v in system_voices})
        return {"engine": "windows", "available": True, "language": chosen["language"], "voices": system_voices,
                "message": f"Installed voice languages: {', '.join(languages)}. Install an Urdu voice in Windows "
                           "speech settings for Urdu narration, or upload narration."}
    if not settings.voice:
        return {"engine": "piper", "available": False, "language": "", "voices": [],
                "message": "Configure Piper executable and an ONNX voice, choose Windows voices, or upload narration."}
    config = Path(settings.voice + ".json")
    if not config.is_file():
        return {"engine": "piper", "available": False, "language": "", "voices": [],
                "message": "Voice metadata .onnx.json is missing."}
    language = json.loads(config.read_text(encoding="utf-8")).get("language", {}).get("code", "")
    return {"engine": "piper", "available": Path(settings.voice).is_file() and Path(settings.piper).is_file(),
            "language": language, "voices": [],
            "message": "Urdu requires an Urdu voice; upload narration if your installed voice does not support Urdu."}


def wait(proc, cancelled, name):
    while True:
        try:
            _, error = proc.communicate(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if cancelled():
                proc.kill()
                proc.communicate()
                raise RuntimeError("Cancelled")
    if proc.returncode:
        raise RuntimeError(f"{name}: " + (error or b"").decode(errors="replace")[-1500:])


def speech_words(text, events, duration):
    """Turn Windows SpeakProgress events (start time + character span) into timed words."""
    words = []
    for index, event in enumerate(events):
        end = events[index + 1]["start"] if index + 1 < len(events) else duration
        word = text[event["at"] : event["at"] + event["length"]]
        if word.strip():
            words.append({"text": word, "start": round(event["start"], 3), "end": round(max(end, event["start"]), 3)})
    return words


def narrate(scene, language, settings, cancelled):
    """Synthesize narration; returns (asset name, word timings or [] when the engine gives none)."""
    if not scene.text.strip():
        raise ValueError("Scene has no script to narrate.")
    name = uid() + ".wav"
    engine = settings.tts
    if engine == "windows" and not pick_windows_voice(settings, language, windows_voices()) and voices.pick(
        language, settings.builtin_voice_ur if language == "ur" else settings.builtin_voice_en
    ):
        # Windows rarely ships an Urdu voice; a downloaded built-in voice covers that language instead.
        engine = "builtin"
    if engine == "builtin":
        if not voices.available():
            raise ValueError("The built-in voice engine is not installed. Run setup again.")
        preferred = settings.builtin_voice_ur if language == "ur" else settings.builtin_voice_en
        key = voices.pick(language, preferred)
        if not key:
            raise ValueError(
                f"No {'Urdu' if language == 'ur' else 'English'} voice is downloaded. Download one in Setup check."
            )
        if cancelled():
            raise RuntimeError("Cancelled")
        voices.synthesize(scene.text, key, asset_path(name), settings.voice_rate, settings.threads)
        return name, []
    if engine == "windows":
        voice = pick_windows_voice(settings, language, windows_voices())
        if not voice:
            raise ValueError(
                f"No installed Windows voice speaks {'Urdu' if language == 'ur' else 'English'}. "
                "Add one in Windows speech settings or upload narration."
            )
        text_file = asset_path(uid() + ".txt")
        words_file = asset_path(uid() + ".txt")
        text_file.write_text(scene.text, encoding="utf-8")
        env = {"FRAME_TEXT": str(text_file), "FRAME_VOICE": voice["name"], "FRAME_WORDS": str(words_file),
               "FRAME_RATE": str(settings.voice_rate), "FRAME_OUT": str(asset_path(name))}
        try:
            with subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", SPEAK],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env={**os.environ, **env},
            ) as proc:
                wait(proc, cancelled, "Windows speech")
            events = json.loads(words_file.read_text(encoding="utf-8-sig") or "[]")
        finally:
            text_file.unlink(missing_ok=True)
            words_file.unlink(missing_ok=True)
        from .media import probe

        return name, speech_words(scene.text, events, probe(asset_path(name))["duration"])
    info = voice_info(settings)
    if not info["available"] or not info["language"].startswith(language):
        raise ValueError(
            "Installed Piper voice does not support this language. Configure a matching local voice or upload narration."
        )
    with subprocess.Popen(
        [settings.piper, "--model", settings.voice, "--output_file", str(asset_path(name))],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    ) as proc:
        proc.stdin.write(scene.text.encode("utf-8"))
        proc.stdin.close()
        proc.stdin = None
        wait(proc, cancelled, "Piper")
    return name, []
