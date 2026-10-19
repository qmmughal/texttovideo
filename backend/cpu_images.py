"""Built-in AI image generation on the CPU (or an Intel GPU) with OpenVINO GenAI.

Models are pre-converted OpenVINO repositories on Hugging Face, downloaded once into data/models.
"""

import re
import secrets
import threading

import httpx
from PIL import Image

from .store import ROOT, asset_path, uid

MODELS_DIR = ROOT / "models"
CATALOG = {
    "lcm-dreamshaper": {
        "repo": "OpenVINO/LCM_Dreamshaper_v7-int8-ov",
        "name": "LCM Dreamshaper v7 · fast, general purpose",
        "size_gb": 1.0,
        # OpenVINO GenAI never loads the safety checker; skipping it saves 1.2 GB.
        "skip": ("safety_checker/", "feature_extractor/"),
        "steps": 4,
        "guidance": 8.0,
        "license": "MIT",
    },
}
HF = "https://huggingface.co"

_pipelines = {}
_load_lock = threading.Lock()


def available():
    import importlib.util

    return importlib.util.find_spec("openvino_genai") is not None


def model_dir(key):
    if key not in CATALOG:
        raise ValueError(f"Unknown image model: {key}")
    return MODELS_DIR / re.sub(r"[^A-Za-z0-9_.-]", "_", CATALOG[key]["repo"])


def is_downloaded(key):
    folder = model_dir(key)
    return (folder / ".complete").is_file()


def model_status():
    return [
        {"key": key, **info, "downloaded": is_downloaded(key)}
        for key, info in CATALOG.items()
    ]


def download(key, cancelled, progress, client=None):
    """Fetch every file of a model repository with resumable, cancellable progress."""
    repo = CATALOG.get(key, {}).get("repo") or ""
    folder = model_dir(key)
    folder.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(60, read=300), trust_env=True, follow_redirects=True)
    try:
        listing = client.get(f"{HF}/api/models/{repo}/tree/main", params={"recursive": "true"})
        listing.raise_for_status()
        skip = (".", *CATALOG[key].get("skip", ()))
        files = [f for f in listing.json() if f["type"] == "file" and not f["path"].startswith(skip)]
        total = sum(f.get("size", 0) for f in files) or 1
        done = 0
        for file in files:
            target = (folder / file["path"]).resolve()
            if folder.resolve() not in target.parents:
                raise ValueError("Unsafe file path in model repository")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file() and target.stat().st_size == file.get("size"):
                done += file.get("size", 0)
                continue
            partial = target.with_name(target.name + ".part")
            with client.stream("GET", f"{HF}/{repo}/resolve/main/{file['path']}") as response:
                response.raise_for_status()
                with partial.open("wb") as out:
                    for chunk in response.iter_bytes(1024 * 1024):
                        if cancelled():
                            raise RuntimeError("Cancelled. Downloaded files are kept and the next attempt resumes.")
                        out.write(chunk)
                        done += len(chunk)
                        progress(f"Downloading {CATALOG[key]['name']} · {done / 1024**3:.2f} of {total / 1024**3:.2f} GB",
                                 min(done / total * 100, 99.9))
            partial.replace(target)
        (folder / ".complete").write_text(repo, encoding="utf-8")
    finally:
        if own_client:
            client.close()


def pipeline(key, device):
    import openvino_genai

    with _load_lock:
        cache_key = (key, device)
        if cache_key not in _pipelines:
            _pipelines.clear()  # keep only one model in memory
            try:
                _pipelines[cache_key] = openvino_genai.Text2ImagePipeline(str(model_dir(key)), device)
            except RuntimeError as exc:
                if device != "CPU":
                    raise ValueError(f"{device} could not run the image model. Choose CPU in Models & settings.") from exc
                raise
        return _pipelines[cache_key]


def size_for(aspect):
    """SD 1.5-class models work best near 512 px; pick a frame that crops well to the export."""
    if aspect < 0.8:
        return 512, 768
    if aspect > 1.25:
        return 768, 512
    return 512, 512


def generate(prompt, style, settings, cancelled, progress, aspect=1.0):
    if not available():
        raise ValueError("Built-in image generation needs OpenVINO GenAI. Run setup again or: pip install openvino-genai")
    key = settings.cpu_image_model
    if not is_downloaded(key):
        raise ValueError("The built-in image model is not downloaded yet. Open Setup check and download it.")
    if not prompt.strip():
        raise ValueError("Scene needs a visual prompt.")
    progress("Loading image model (first time takes a moment)", None)
    pipe = pipeline(key, settings.cpu_image_device)
    info = CATALOG[key]
    width, height = size_for(aspect)
    steps = info["steps"]

    def on_step(step, num_steps, latent):
        progress(f"Painting on {settings.cpu_image_device} · step {step + 1} of {num_steps}", None)
        return cancelled()  # returning True stops generation

    result = pipe.generate(
        f"{prompt}, {style.lower()} style, highly detailed",
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=info["guidance"],
        rng_seed=secrets.randbelow(2**31),
        callback=on_step,
    )
    if cancelled():
        raise RuntimeError("Cancelled")
    name = uid() + ".png"
    Image.fromarray(result.data[0]).save(asset_path(name))
    return name

