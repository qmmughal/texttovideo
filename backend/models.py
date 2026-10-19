from typing import Literal
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse
from pathlib import Path

class Scene(BaseModel):
    id: str
    text: str = Field('', max_length=3000)
    prompt: str = Field('', max_length=5000)
    duration: float = Field(5, ge=0.5, le=120)
    asset: str = ''
    narration: str = ''

class Project(BaseModel):
    id: str = ''
    title: str = Field('Untitled film', max_length=200)
    description: str = ''
    prompt: str = Field('', max_length=30000)
    language: Literal['en','ur'] = 'en'
    duration: float = Field(20, ge=1, le=3600)
    style: str = 'Cinematic'
    mode: Literal['slideshow','video'] = 'slideshow'
    scenes: list[Scene] = Field(default_factory=list, max_length=3600)
    music: str = ''
    logo: str = ''
    exports: list[dict] = Field(default_factory=list)

class Settings(BaseModel):
    ollama: str = 'http://127.0.0.1:11434'
    comfy: str = 'http://127.0.0.1:8188'
    model: str = ''
    image_workflow: dict = Field(default_factory=dict)
    video_workflow: dict = Field(default_factory=dict)
    clip_seconds: float = Field(5, ge=1, le=30)
    threads: int = Field(2, ge=1, le=16)
    font: str = str(Path(__file__).resolve().parents[1] / 'frontend/public/fonts/NotoNaskhArabic.ttf')
    piper: str = ''
    voice: str = ''
    @field_validator('ollama','comfy')
    @classmethod
    def local_url(cls, value):
        p = urlparse(value)
        if p.scheme != 'http' or p.hostname not in ('127.0.0.1','localhost','::1') or p.username or p.password:
            raise ValueError('Use a localhost HTTP backend URL')
        return value.rstrip('/')

class Export(BaseModel):
    width: int = Field(720, ge=128, le=3840, multiple_of=2)
    height: int = Field(1280, ge=128, le=3840, multiple_of=2)
    fit: Literal['crop','contain','blur'] = 'crop'
    captions: bool = True
    font_size: int = Field(42, ge=12, le=160)
    caption_y: float = Field(.80, ge=.1, le=.9)
    safe_area: float = Field(.08, ge=0, le=.3)
    color: str = '#ffffff'
    music_volume: float = Field(.15, ge=0, le=1)
    fade: float = Field(.25, ge=0, le=1)
    @field_validator('color')
    @classmethod
    def valid_color(cls, value):
        import re
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',value): raise ValueError('Use #rrggbb')
        return value
