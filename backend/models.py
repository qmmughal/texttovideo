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


class Settings(BaseModel):
    ollama: str = "http://127.0.0.1:11434"
    comfy: str = "http://127.0.0.1:8188"
    model: str = ""
    vision_model: str = ""
    image_engine: Literal["comfy", "cpu"] = "comfy"
    cpu_image_model: str = "lcm-dreamshaper"
    cpu_image_device: str = Field("CPU", pattern=r"^(CPU|GPU(\.\d+)?|NPU)$")
    whisper_size: Literal["tiny", "base", "small"] = "base"
    image_workflow: dict = Field(default_factory=dict)
    video_workflow: dict = Field(default_factory=dict)
    clip_seconds: float = Field(5, ge=1, le=30)
    threads: int = Field(2, ge=1, le=16)
    font: str = str(Path(__file__).resolve().parents[1] / "frontend/public/fonts/NotoNaskhArabic.ttf")
    tts: Literal["piper", "windows"] = "piper"
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
            or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Use a localhost HTTP backend URL")
        return value.rstrip("/")


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

    @field_validator("color", "highlight")
    @classmethod
    def valid_color(cls, value):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Use #rrggbb")
        return value
