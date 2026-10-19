"""Built-in AI image generation on the CPU (or an Intel GPU) with OpenVINO GenAI.

Models are pre-converted OpenVINO repositories on Hugging Face, downloaded once into data/models.
"""

import secrets
import threading

from PIL import Image

from . import hub
from .store import asset_path, uid

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
_pipelines = {}
_load_lock = threading.Lock()


def available():
    import importlib.util

    return importlib.util.find_spec("openvino_genai") is not None


def model_dir(key):
    if key not in CATALOG:
        raise ValueError(f"Unknown image model: {key}")
    return hub.folder_for(CATALOG[key]["repo"])


def is_downloaded(key):
    return key in CATALOG and hub.is_downloaded(CATALOG[key]["repo"])


def model_status():
    return [{"key": key, **info, "downloaded": is_downloaded(key)} for key, info in CATALOG.items()]


def download(key, cancelled, progress, client=None):
    info = CATALOG[key]
    hub.download(info["repo"], info["name"], cancelled, progress, info.get("skip", ()), client)


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

