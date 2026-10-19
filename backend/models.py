import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

Motion = Literal["auto", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "none"]


class Scene(BaseModel):
    id: str
    text: str = Field("", max_length=3000)
    prompt: str = Field("", max_length=5000)
    duration: float = Field(5, ge=0.5, le=120)
    asset: str = ""
    narration: str = ""
    motion: Motion = "auto"
    # Word timings relative to the narration start, valid only for the narration file named in words_for.
    words: list[dict] = Field(default_factory=list, max_length=2000)
    words_for: str = ""


class Project(BaseModel):
    id: str = ""
    title: str = Field("Untitled film", max_length=200)
    description: str = ""
    prompt: str = Field("", max_length=30000)
    language: Literal["en", "ur"] = "en"
    duration: float = Field(20, ge=1, le=3600)
    style: str = "Cinematic"
    mode: Literal["slideshow", "video"] = "slideshow"
    scenes: list[Scene] = Field(default_factory=list, max_length=3600)
    music: str = ""
    logo: str = ""
    exports: list[dict] = Field(default_factory=list)


# Docker and similar setups reach Ollama/ComfyUI by service name; only names listed here are accepted.
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
SERVICE_HOSTS = tuple(h.strip() for h in os.environ.get("FRAME_SERVICE_HOSTS", "").split(",") if h.strip())


class Settings(BaseModel):
    ollama: str = os.environ.get("FRAME_OLLAMA_URL", "http://127.0.0.1:11434")
    comfy: str = os.environ.get("FRAME_COMFY_URL", "http://127.0.0.1:8188")
    model: str = ""
    vision_model: str = ""
    # Model that reviews requests against the acceptable-use policy; empty picks the largest configured model.
    safety_model: str = ""
    image_engine: Literal["comfy", "cpu"] = "comfy"
    cpu_image_model: str = "lcm-dreamshaper"
    cpu_image_device: str = Field("CPU", pattern=r"^(CPU|GPU(\.\d+)?|NPU)$")
    whisper_size: Literal["tiny", "base", "small"] = "base"
    image_workflow: dict = Field(default_factory=dict)
    video_workflow: dict = Field(default_factory=dict)
    clip_seconds: float = Field(5, ge=1, le=30)
    threads: int = Field(2, ge=1, le=16)
    font: str = str(Path(__file__).resolve().parents[1] / "frontend/public/fonts/NotoNaskhArabic.ttf")
    # Windows has system voices; elsewhere the built-in neural voices work without extra software.
    tts: Literal["builtin", "windows", "piper"] = "windows" if os.name == "nt" else "builtin"
    builtin_voice_en: str = "en_US-joe-medium"
    builtin_voice_ur: str = "ur_PK-fasih-medium"
    piper: str = ""
    voice: str = ""
    windows_voice: str = Field("", max_length=200)
    voice_rate: int = Field(0, ge=-10, le=10)

    @field_validator("ollama", "comfy")
    @classmethod
    def local_url(cls, value):
        parsed = urlparse(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in LOCAL_HOSTS + SERVICE_HOSTS
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Use a localhost HTTP backend URL")
        return value.rstrip("/")


class Preset(BaseModel):
    id: str = ""
    name: str = Field(..., min_length=1, max_length=80)
    options: dict = Field(default_factory=dict)
    logo: str = ""
    music: str = ""


class Export(BaseModel):
    width: int = Field(720, ge=128, le=3840, multiple_of=2)
    height: int = Field(1280, ge=128, le=3840, multiple_of=2)
    fit: Literal["crop", "contain", "blur"] = "crop"
    captions: bool = True
    font_size: int = Field(42, ge=12, le=160)
    caption_y: float = Field(0.80, ge=0.1, le=0.9)
    safe_area: float = Field(0.08, ge=0, le=0.3)
    color: str = "#ffffff"
    music_volume: float = Field(0.15, ge=0, le=1)
    transition: Literal["fade", "crossfade", "none"] = "fade"
    fade: float = Field(0.25, ge=0, le=1.5)
    caption_chars: int = Field(84, ge=20, le=400)
    caption_style: Literal["blocks", "words"] = "blocks"
    highlight: str = "#ffd23f"
    # Extra [width, height] sizes rendered in the same job; empty renders only width x height.
    formats: list[list[int]] = Field(default_factory=list, max_length=8)

    @field_validator("formats")
    @classmethod
    def valid_formats(cls, value):
        for size in value:
            if len(size) != 2 or any(not 128 <= n <= 3840 or n % 2 for n in size):
                raise ValueError("Each format needs an even width and height between 128 and 3840")
        return value

    @field_validator("color", "highlight")
    @classmethod
    def valid_color(cls, value):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Use #rrggbb")
        return value
