import os
import platform
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import cpu_images, integrations, media, safety, store, system, voices, words
from .models import Export, Preset, Project, Settings

FRONTEND_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
TRUSTED_ORIGINS = (*FRONTEND_ORIGINS, "http://localhost:8000", "http://127.0.0.1:8000")
MEDIA_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm", ".wav", ".mp3", ".m4a", ".ogg")
JOB_KINDS = ("storyboard", "describe", "visuals", "narration", "align", "render", "translate")
SETUP_KINDS = ("ollama_model", "image_model", "whisper_model", "voice")
SYSTEM = "__system__"

pool = ThreadPoolExecutor(max_workers=1)
lock = threading.RLock()


def settings():
    try:
        return Settings(**store.get("settings", "local"))
    except KeyError:
        return Settings()


def active_job(project_id):
    return any(j["project"] == project_id and j["status"] in ("queued", "running") for j in store.all_docs("job"))


@asynccontextmanager
async def lifespan(app):
    for job in store.all_docs("job"):
        if job["status"] in ("running", "queued"):
            job.update(status="interrupted", stage="Server restarted. Completed assets are safe; retry this job.")
            store.put("job", job["id"], job)
    yield


app = FastAPI(title="Frame Local Studio", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(FRONTEND_ORIGINS),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in TRUSTED_ORIGINS:
        return JSONResponse({"detail": "Untrusted origin"}, 403)
    if request.url.hostname not in ("localhost", "127.0.0.1", "::1", "testserver"):
        return JSONResponse({"detail": "Localhost only"}, 403)
    return await call_next(request)


@app.exception_handler(KeyError)
async def not_found(request, exc):
    return JSONResponse({"detail": "Not found"}, 404)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail": str(exc)}, 400)


# --- Settings & status ------------------------------------------------------


@app.get("/api/settings")
def read_settings():
    return settings()


@app.put("/api/settings")
def save_settings(value: Settings):
    store.put("settings", "local", value.model_dump())
    return value


@app.get("/api/status")
def status():
    s = settings()
    result = {
        "cpu": platform.processor(),
        "threads": os.cpu_count(),
        "ffmpeg": media.FFMPEG,
        "windows": os.name == "nt",
        "voice": integrations.voice_info(s),
    }
    for name, base, route in [("ollama", s.ollama, "/api/tags"), ("comfy", s.comfy, "/system_stats")]:
        try:
            with httpx.Client(timeout=3, trust_env=False) as client:
                response = client.get(base + route)
                response.raise_for_status()
                result[name] = {"online": True, "data": response.json()}
        except Exception as exc:
            result[name] = {"online": False, "error": str(exc)}
    if result["ollama"]["online"]:
        for model in result["ollama"]["data"].get("models", []):
            model["capabilities"] = integrations.capabilities(s, model["name"])
    return result


@app.get("/api/setup")
def setup():
    s = settings()
    current = status()
    hw = system.hardware()
    plan = system.recommend(hw)
    models = [m["name"] for m in current["ollama"].get("data", {}).get("models", [])] if current["ollama"]["online"] else []
    return {
        "hardware": hw,
        "plan": plan,
        "ollama": {"state": system.ollama_state(current["ollama"]), "models": models},
        "voice": current["voice"],
        "voices": {"engine": voices.available(), "catalog": voices.status()},
        "images": {
            "engine": s.image_engine,
            "openvino": cpu_images.available(),
            "models": cpu_images.model_status(),
            "comfy": current["comfy"]["online"],
        },
        "words": {
            "whisper": words.whisper_available(),
            "size": s.whisper_size,
            "downloaded": words.whisper_downloaded(s.whisper_size),
        },
        "settings": {"model": s.model, "vision_model": s.vision_model, "tts": s.tts},
        "safety": safety_status(s, current["ollama"]["online"]),
    }


def safety_status(s, online):
    model = safety.reviewer(s) if online else (s.safety_model or s.model or s.vision_model)
    size = safety.model_sizes(s).get(model) if online and model else None
    return {"model": model, "size_b": size, "small": size is not None and size < safety.SMALL_MODEL}


@app.post("/api/setup/jobs/{kind}")
def start_setup_job(kind: str, options: dict):
    if kind not in SETUP_KINDS:
        raise HTTPException(400, "Unknown setup task")
    if kind == "ollama_model" and not str(options.get("model", "")).strip():
        raise ValueError("Choose a model to install")
    if kind == "image_model" and options.get("key") not in cpu_images.CATALOG:
        raise ValueError("Unknown image model")
    if kind == "voice" and options.get("key") not in voices.CATALOG:
        raise ValueError("Unknown voice")
    with lock:
        if any(j["project"] == SYSTEM and j["status"] in ("queued", "running") for j in store.all_docs("job")):
            raise HTTPException(409, "Another download is running. Wait for it to finish.")
        job = {
            "id": store.uid(), "project": SYSTEM, "kind": kind, "options": options, "scene": None,
            "status": "queued", "stage": "Waiting for local worker", "progress": 0, "cancel": False,
        }
        store.put("job", job["id"], job)
        pool.submit(execute, job["id"])
    return job


def run_setup_job(job, s, cancelled, progress):
    options = job["options"]
    if job["kind"] == "ollama_model":
        model = options["model"].strip()
        system.pull(s, model, cancelled, progress)
        field = "vision_model" if options.get("role") == "vision" else "model"
        latest = settings()
        setattr(latest, field, model)
        store.put("settings", "local", latest.model_dump())
    elif job["kind"] == "image_model":
        cpu_images.download(options["key"], cancelled, progress)
        latest = settings()
        latest.image_engine, latest.cpu_image_model = "cpu", options["key"]
        store.put("settings", "local", latest.model_dump())
    elif job["kind"] == "voice":
        voices.download(options["key"], cancelled, progress)
        latest = settings()
        if latest.tts == "piper" and not integrations.voice_info(latest)["available"]:
            latest.tts = "builtin"
        field = "builtin_voice_ur" if voices.CATALOG[options["key"]]["language"] == "ur" else "builtin_voice_en"
        setattr(latest, field, options["key"])
        store.put("settings", "local", latest.model_dump())
    elif job["kind"] == "whisper_model":
        if not words.whisper_available():
            raise ValueError("faster-whisper is not installed. Run setup again.")
        progress(f"Downloading the {s.whisper_size} speech model", None)
        words.whisper_model(s.whisper_size)


# --- Projects ---------------------------------------------------------------


@app.get("/api/projects")
def projects():
    return store.all_docs("project")


@app.post("/api/projects")
def create_project(value: Project):
    value.id = store.uid()
    value.exports = []
    store.put("project", value.id, value.model_dump())
    return value


@app.get("/api/projects/{key}")
def read_project(key: str):
    return store.get("project", key)


@app.put("/api/projects/{key}")
def save_project(key: str, value: Project):
    with lock:
        old = store.get("project", key)
        if active_job(key):
            raise HTTPException(409, "Wait for or cancel the active job before editing.")
        value.id = key
        value.exports = old.get("exports", [])
        store.put("project", key, value.model_dump())
    return value


@app.post("/api/projects/{key}/duplicate")
def duplicate_project(key: str):
    copy = Project(**store.get("project", key))
    copy.id = store.uid()
    copy.title = (copy.title + " (copy)")[:200]
    copy.exports = []
    for scene in copy.scenes:
        scene.id = store.uid()
    # Asset files are shared, not copied; deletion only removes files no other project uses.
    store.put("project", copy.id, copy.model_dump())
    return copy


@app.post("/api/projects/{key}/translate")
def translate_project(key: str, body: dict):
    language = body.get("language")
    source = Project(**store.get("project", key))
    if language not in integrations.LANGUAGES or language == source.language:
        raise ValueError("Choose a different language to translate into")
    copy = source.model_copy(deep=True)
    copy.id = store.uid()
    copy.language = language
    copy.exports = []
    for scene in copy.scenes:
        scene.id = store.uid()
        # Narration and its word timings belong to the old language.
        scene.narration, scene.words, scene.words_for = "", [], ""
    store.put("project", copy.id, copy.model_dump())
    job = start_job(copy.id, "translate", {"source": source.language})
    return {"project": copy, "job": job}


@app.get("/api/presets")
def presets():
    return store.all_docs("preset")


@app.post("/api/presets")
def save_preset(value: Preset):
    # Size and format list are per export, not part of a brand look.
    value.options = {k: v for k, v in Export(**value.options).model_dump().items() if k not in ("width", "height", "formats")}
    existing = next((p for p in store.all_docs("preset") if p["name"].lower() == value.name.lower()), None)
    value.id = existing["id"] if existing else store.uid()
    store.put("preset", value.id, value.model_dump())
    return value


@app.delete("/api/presets/{key}")
def delete_preset(key: str):
    store.get("preset", key)
    store.delete("preset", key)
    return {"deleted": key}


@app.delete("/api/projects/{key}")
def delete_project(key: str):
    with lock:
        project = store.get("project", key)
        if active_job(key):
            raise HTTPException(409, "Cancel the active job before deleting this project.")
        store.delete("project", key)
        in_use = set()
        for other in store.all_docs("project"):
            in_use |= store.project_assets(other)
        for preset in store.all_docs("preset"):
            in_use |= {preset.get("logo", ""), preset.get("music", "")}
        removed = 0
        for name in store.project_assets(project) - in_use:
            try:
                path = store.asset_path(name)
            except ValueError:
                continue
            if path.is_file():
                path.unlink()
                removed += 1
        for job in store.all_docs("job"):
            if job["project"] == key:
                store.delete("job", job["id"])
    return {"deleted": key, "files_removed": removed}


# --- Assets -----------------------------------------------------------------


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in MEDIA_SUFFIXES:
        raise HTTPException(400, "Unsupported media format")
    name = store.uid() + suffix
    path = store.asset_path(name)
    total = 0
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise ValueError("Upload exceeds 512 MB")
                out.write(chunk)
        if suffix in integrations.IMAGE_SUFFIXES:
            with Image.open(path) as image:
                image.verify()
        else:
            info = media.probe(path)
            if not info["audio"] and not info["video"]:
                raise ValueError("File is not valid audio/video")
        return {"asset": name, "info": media.probe(path)}
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "Invalid upload: " + str(exc)[:300]) from exc


@app.get("/api/assets/{name}")
def asset(name: str, download: bool = False):
    path = store.asset_path(name)
    if path.suffix not in (*MEDIA_SUFFIXES, ".srt") or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=name if download or path.suffix == ".srt" else None)


# --- Jobs -------------------------------------------------------------------


def execute(key):
    job = store.get("job", key)

    def cancelled():
        return store.get("job", key).get("cancel", False)

    def progress(stage, percent):
        with lock:
            current = store.get("job", key)
            current.update(stage=stage, status="running")
            if percent is not None:
                current["progress"] = percent
            store.put("job", key, current)

    try:
        if cancelled():
            raise RuntimeError("Cancelled")
        s = settings()
        if job["project"] == SYSTEM:
            run_setup_job(job, s, cancelled, progress)
            with lock:
                current = store.get("job", key)
                current.update(status="completed", stage="Complete", progress=100)
                store.put("job", key, current)
            return
        project = Project(**store.get("project", job["project"]))
        progress("Starting " + job["kind"], 0)
        if job["kind"] == "storyboard":
            project = integrations.storyboard(project, s)
        elif job["kind"] == "describe":
            project = integrations.describe_photos(project, s, cancelled, progress, job.get("scene"))
        elif job["kind"] == "align":
            align_scenes(project, s, job.get("scene"), cancelled, progress)
        elif job["kind"] in ("visuals", "narration"):
            scenes = [v for v in project.scenes if not job.get("scene") or v.id == job["scene"]]
            if not scenes:
                raise ValueError("No scenes selected. Generate or add a storyboard first.")
            # Text the user wrote is checked too; without a reachable local model this check is skipped.
            sources = [v.text for v in scenes] if job["kind"] == "narration" else [v.prompt for v in scenes]
            safety.review(sources, s, required=False)
            for index, scene in enumerate(scenes):
                if cancelled():
                    raise RuntimeError("Cancelled")
                progress(f"Generating scene {index + 1}/{len(scenes)}", index / len(scenes) * 100)
                if job["kind"] == "visuals":
                    if scene.asset and not job.get("scene"):
                        continue
                    if s.image_engine == "cpu" and project.mode == "slideshow":
                        aspect = float(job["options"].get("aspect") or 1)
                        scene.asset = cpu_images.generate(scene.prompt, project.style, s, cancelled, progress, aspect)
                    else:
                        scene.asset = integrations.generate_visual(scene, project.mode, s, cancelled, progress)
                else:
                    if (scene.narration or not scene.text.strip()) and not job.get("scene"):
                        continue
                    scene.narration, scene.words = integrations.narrate(scene, project.language, s, cancelled)
                    if not scene.words and words.whisper_available() and words.whisper_downloaded(s.whisper_size):
                        # Engines without word events get their timings from the speech model straight away.
                        progress(f"Timing words in scene {index + 1}/{len(scenes)}", None)
                        recognized = words.transcribe(store.asset_path(scene.narration), project.language, s.whisper_size)
                        scene.words = words.align(scene.text, recognized)
                    scene.words_for = scene.narration if scene.words else ""
                if cancelled():
                    raise RuntimeError("Cancelled")
                store.put("project", project.id, project.model_dump())
        elif job["kind"] == "translate":
            project = integrations.translate(project, s, job["options"]["source"], cancelled, progress)
        elif job["kind"] == "render":
            safety.review([project.title] + [v.text for v in project.scenes], s, required=False)
            base = Export(**job["options"])
            targets = [[base.width, base.height]] + [f for f in base.formats if f != [base.width, base.height]]
            for n, (width, height) in enumerate(targets):
                # Keep captions the same size relative to the frame in every format.
                scale = min(width, height) / min(base.width, base.height)
                options = base.model_copy(update={
                    "width": width, "height": height, "formats": [],
                    "font_size": max(12, min(160, round(base.font_size * scale))),
                })

                def format_progress(stage, percent, n=n):
                    label = f"{width}×{height} ({n + 1} of {len(targets)}) · {stage}" if len(targets) > 1 else stage
                    progress(label, None if percent is None else (n * 100 + percent) / len(targets))

                project.exports.append(media.render(project, options, s, format_progress, cancelled))
                store.put("project", project.id, project.model_dump())
        if cancelled():
            raise RuntimeError("Cancelled")
        store.put("project", project.id, project.model_dump())
        with lock:
            current = store.get("job", key)
            current.update(status="completed", stage="Complete", progress=100)
            store.put("job", key, current)
    except Exception as exc:
        with lock:
            current = store.get("job", key)
            # A refusal is final: retrying the same request would be refused again.
            status = "cancelled" if cancelled() else "refused" if isinstance(exc, safety.Refusal) else "failed"
            current.update(status=status, stage=str(exc))
            store.put("job", key, current)


def align_scenes(project, s, only_scene, cancelled, progress):
    """Time every word of the narration with Whisper; fills empty captions from what was said."""
    targets = [v for v in project.scenes if v.narration and (not only_scene or v.id == only_scene)]
    if not targets:
        raise ValueError("Add or generate narration first; word timing follows the narration audio.")
    for index, scene in enumerate(targets):
        if cancelled():
            raise RuntimeError("Cancelled")
        if scene.words and scene.words_for == scene.narration and not only_scene:
            continue
        progress(f"Listening to scene {index + 1}/{len(targets)}", index / len(targets) * 100)
        recognized = words.transcribe(store.asset_path(scene.narration), project.language, s.whisper_size)
        if not scene.text.strip():
            scene.text = " ".join(w["text"] for w in recognized)[:3000]
        scene.words = words.align(scene.text, recognized)
        scene.words_for = scene.narration
        store.put("project", project.id, project.model_dump())


@app.post("/api/projects/{key}/jobs/{kind}")
def start_job(key: str, kind: str, options: dict):
    if kind not in JOB_KINDS:
        raise HTTPException(400, "Unknown operation")
    with lock:
        store.get("project", key)
        if active_job(key):
            raise HTTPException(409, "A job is already active for this project")
        if kind == "render":
            Export(**options)
        job = {
            "id": store.uid(), "project": key, "kind": kind, "options": options, "scene": options.get("scene"),
            "status": "queued", "stage": "Waiting for local worker", "progress": 0, "cancel": False,
        }
        store.put("job", job["id"], job)
        pool.submit(execute, job["id"])
    return job


@app.get("/api/jobs")
def jobs():
    return store.all_docs("job")


@app.post("/api/jobs/{key}/cancel")
def cancel(key: str):
    with lock:
        job = store.get("job", key)
        job["cancel"] = True
        store.put("job", key, job)
    return job


@app.post("/api/jobs/{key}/retry")
def retry(key: str):
    job = store.get("job", key)
    if job["status"] in ("running", "queued"):
        raise HTTPException(409, "Job is active")
    return start_job(job["project"], job["kind"], job["options"])


# The exported web UI (frontend/out) is served from the same origin, so one process runs the whole studio.
UI_DIR = Path(__file__).resolve().parents[1] / "frontend" / "out"
if UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
