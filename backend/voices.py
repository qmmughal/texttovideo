"""Built-in neural narration: Piper voices run in-process by sherpa-onnx on any operating system."""

import threading
import wave

from . import hub

# Only voices whose training data allows commercial use are listed.
CATALOG = {
    "en_US-joe-medium": {
        "repo": "csukuangfj/vits-piper-en_US-joe-medium",
        "name": "Joe · US English · male",
        "language": "en",
        "license": "CC0",
        "size_mb": 80,
    },
    "en_GB-cori-medium": {
        "repo": "csukuangfj/vits-piper-en_GB-cori-medium",
        "name": "Cori · UK English · female",
        "language": "en",
        "license": "public domain",
        "size_mb": 80,
    },
    "en_GB-alba-medium": {
        "repo": "csukuangfj/vits-piper-en_GB-alba-medium",
        "name": "Alba · Scottish English · female",
        "language": "en",
        "license": "CC BY 4.0",
        "size_mb": 80,
    },
    "ur_PK-fasih-medium": {
        "repo": "csukuangfj2/vits-piper-ur_PK-fasih-medium",
        "name": "Fasih · Urdu · male",
        "language": "ur",
        "license": "MIT",
        "size_mb": 82,
    },
}
DEFAULTS = {"en": "en_US-joe-medium", "ur": "ur_PK-fasih-medium"}

_engines = {}
_lock = threading.Lock()


def available():
    import importlib.util

    return importlib.util.find_spec("sherpa_onnx") is not None


def is_downloaded(key):
    return key in CATALOG and hub.is_downloaded(CATALOG[key]["repo"])


def status():
    return [{"key": key, **info, "downloaded": is_downloaded(key)} for key, info in CATALOG.items()]


def download(key, cancelled, progress, client=None):
    if key not in CATALOG:
        raise ValueError(f"Unknown voice: {key}")
    info = CATALOG[key]
    hub.download(info["repo"], f"{info['name']} voice", cancelled, progress, ("README", "vits-piper"), client)


def pick(language, preferred):
    """The preferred voice if it is downloaded and speaks the language, else any downloaded voice that does."""
    if preferred in CATALOG and CATALOG[preferred]["language"] == language and is_downloaded(preferred):
        return preferred
    return next((k for k, v in CATALOG.items() if v["language"] == language and is_downloaded(k)), None)


def engine(key, threads):
    import sherpa_onnx

    with _lock:
        if key not in _engines:
            folder = hub.folder_for(CATALOG[key]["repo"])
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(folder / f"{key}.onnx"),
                tokens=str(folder / "tokens.txt"),
                data_dir=str(folder / "espeak-ng-data"),
            )
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(vits=vits, num_threads=threads, provider="cpu"),
                max_num_sentences=1,
            )
            if not config.validate():
                raise ValueError(f"Voice files for {CATALOG[key]['name']} are incomplete. Download the voice again.")
            _engines[key] = sherpa_onnx.OfflineTts(config)
        return _engines[key]


def synthesize(text, key, path, rate=0, threads=2):
    """Write 16-bit mono WAV. `rate` uses the same -10…10 scale as Windows voices."""
    speed = 1.0 + rate * 0.05
    audio = engine(key, threads).generate(text, sid=0, speed=speed)
    if not len(audio.samples):
        raise RuntimeError("The voice produced no audio for this text.")
    import numpy

    samples = numpy.clip(numpy.asarray(audio.samples, dtype=numpy.float32), -1, 1)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(audio.sample_rate)
        out.writeframes((samples * 32767).astype("<i2").tobytes())
