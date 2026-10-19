"""Hardware detection and model recommendations for the first-run setup check."""

import ctypes
import json
import os
import platform
import shutil
import subprocess

from .store import ROOT

GB = 1024**3


def memory_gb():
    try:
        if os.name == "nt":

            class Status(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong),
                    ("page_total", ctypes.c_ulonglong), ("page_available", ctypes.c_ulonglong),
                    ("virtual_total", ctypes.c_ulonglong), ("virtual_available", ctypes.c_ulonglong),
                    ("extended", ctypes.c_ulonglong),
                ]

            status = Status()
            status.length = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return round(status.total / GB, 1)
        if platform.system() == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return round(int(out.stdout) / GB, 1)
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) * 1024 / GB, 1)
    except Exception:
        pass
    return 0.0


def nvidia_gpus():
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        gpus = []
        for line in out.stdout.strip().splitlines():
            name, memory = [part.strip() for part in line.rsplit(",", 1)]
            gpus.append({"name": name, "vram_gb": round(int(memory) / 1024, 1)})
        return gpus
    except Exception:
        return []


def openvino_devices():
    try:
        import openvino

        return list(openvino.Core().available_devices)
    except Exception:
        return []


def installed(module):
    import importlib.util

    return importlib.util.find_spec(module) is not None


def hardware():
    disk = shutil.disk_usage(ROOT)
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or platform.machine(),
        "threads": os.cpu_count() or 1,
        "ram_gb": memory_gb(),
        "disk_free_gb": round(disk.free / GB, 1),
        "nvidia": nvidia_gpus(),
        "openvino_devices": openvino_devices(),
    }


def recommend(hw):
    """Pick models that fit this machine. Sizes are Ollama's download sizes."""
    ram = hw["ram_gb"]
    vram = max((g["vram_gb"] for g in hw["nvidia"]), default=0)
    if ram and ram < 8:
        tier = {
            "name": "Light",
            "summary": "Under 8 GB of memory: small models only. Use your own photos for visuals.",
            "text_model": ("qwen3:1.7b", 1.4),
            "vision_model": ("qwen3-vl:2b", 1.9),
            "images": "photos",
        }
    elif ram < 16 and vram < 8:
        tier = {
            "name": "Standard (CPU)",
            "summary": "8–16 GB of memory without a large graphics card. Everything runs on the CPU, "
                       "AI images take roughly 10–40 seconds each.",
            "text_model": ("qwen3:4b", 2.5),
            "vision_model": ("qwen3-vl:4b", 3.3),
            "images": "cpu",
        }
    elif vram < 8:
        tier = {
            "name": "Strong (CPU)",
            "summary": "16 GB or more of memory. Larger models fit; AI images run on the CPU.",
            "text_model": ("qwen3:8b", 5.2),
            "vision_model": ("qwen3-vl:8b", 6.1),
            "images": "cpu",
        }
    else:
        tier = {
            "name": "GPU",
            "summary": f"NVIDIA graphics card with {vram:g} GB. ComfyUI can generate images and short video clips.",
            "text_model": ("qwen3:8b", 5.2),
            "vision_model": ("qwen3-vl:8b", 6.1),
            "images": "comfy",
        }
    tier["video"] = vram >= 8
    return tier


def ollama_state(status):
    if status.get("online"):
        return "running"
    return "installed" if shutil.which("ollama") else "missing"


def pull(settings, model, cancelled, progress):
    """Download an Ollama model, reporting byte progress."""
    import httpx

    with httpx.Client(timeout=None, trust_env=False) as client:
        with client.stream("POST", settings.ollama + "/api/pull", json={"model": model, "stream": True}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if cancelled():
                    raise RuntimeError("Cancelled. Ollama keeps the partial download and resumes next time.")
                if not line:
                    continue
                event = json.loads(line)
                if event.get("error"):
                    raise RuntimeError(f"Ollama: {event['error']}")
                total, done = event.get("total"), event.get("completed")
                percent = done / total * 100 if total and done else None
                label = event.get("status", "")
                if total and done:
                    label = f"{label} · {done / GB:.2f} of {total / GB:.2f} GB"
                progress(f"{model}: {label}", percent)
