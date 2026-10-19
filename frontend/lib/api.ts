export type Motion = 'auto' | 'zoom_in' | 'zoom_out' | 'pan_left' | 'pan_right' | 'pan_up' | 'pan_down' | 'none';

export type Scene = {
  id: string;
  text: string;
  prompt: string;
  duration: number;
  asset: string;
  narration: string;
  motion: Motion;
};

export type Output = {
  asset: string;
  srt: string;
  width: number;
  height: number;
  duration: number;
  upscaled: boolean;
  transition?: string;
};

export type Project = {
  id: string;
  title: string;
  description: string;
  prompt: string;
  language: string;
  duration: number;
  style: string;
  mode: string;
  scenes: Scene[];
  music: string;
  logo: string;
  exports: Output[];
};

export type Settings = {
  ollama: string;
  comfy: string;
  model: string;
  vision_model: string;
  image_workflow: object;
  video_workflow: object;
  clip_seconds: number;
  threads: number;
  font: string;
  tts: 'piper' | 'windows';
  piper: string;
  voice: string;
  windows_voice: string;
  voice_rate: number;
};

export type Job = {
  id: string;
  project: string;
  kind: string;
  status: string;
  stage: string;
  progress: number;
};

export type ExportOptions = {
  width: number;
  height: number;
  fit: string;
  captions: boolean;
  font_size: number;
  caption_y: number;
  safe_area: number;
  color: string;
  music_volume: number;
  transition: string;
  fade: number;
  caption_chars: number;
};

export type OllamaModel = { name: string; capabilities?: string[] };

export type Voice = { name: string; language: string };

export type Status = {
  cpu: string;
  threads: number;
  windows: boolean;
  voice: { engine: string; available: boolean; language: string; voices: Voice[]; message: string };
  ollama: { online: boolean; data?: { models: OllamaModel[] } };
  comfy: { online: boolean; data?: { devices?: { name: string; vram_total: number }[] } };
};

const API = 'http://127.0.0.1:8000/api';

export const assetUrl = (name: string) => `${API}/assets/${name}`;

export const isImage = (name: string) => /\.(png|jpg|jpeg|webp)$/i.test(name);

export async function call<T = any>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch(API + path, {
    method,
    headers: form ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  const value = await response.json();
  if (!response.ok) {
    throw new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail));
  }
  return value;
}

export async function uploadFile(file: File): Promise<string> {
  const data = new FormData();
  data.append('file', file);
  return (await call<{ asset: string }>('/upload', 'POST', data)).asset;
}

export const newScene = (value: Partial<Scene> = {}): Scene => ({
  id: crypto.randomUUID(),
  text: '',
  prompt: '',
  duration: 5,
  asset: '',
  narration: '',
  motion: 'auto',
  ...value,
});

export const freshProject = (): Project => ({
  id: '',
  title: 'Untitled film',
  description: '',
  prompt: '',
  language: 'en',
  duration: 20,
  style: 'Cinematic',
  mode: 'slideshow',
  scenes: [],
  music: '',
  logo: '',
  exports: [],
});

export const defaultExport: ExportOptions = {
  width: 360,
  height: 640,
  fit: 'crop',
  captions: true,
  font_size: 26,
  caption_y: 0.8,
  safe_area: 0.08,
  color: '#ffffff',
  music_volume: 0.15,
  transition: 'fade',
  fade: 0.25,
  caption_chars: 84,
};

export const formats = [
  ['9:16 · Shorts / Reels', 1080, 1920],
  ['16:9 · YouTube', 1920, 1080],
  ['1:1 · Square', 1080, 1080],
  ['4:5 · Portrait', 1080, 1350],
  ['Preview · 360 × 640', 360, 640],
] as const;

export const motions: [Motion, string][] = [
  ['auto', 'Auto (varies by scene)'],
  ['zoom_in', 'Slow zoom in'],
  ['zoom_out', 'Slow zoom out'],
  ['pan_left', 'Pan left'],
  ['pan_right', 'Pan right'],
  ['pan_up', 'Pan up'],
  ['pan_down', 'Pan down'],
  ['none', 'Still'],
];
