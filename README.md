# Frame — local AI video studio

[![CI](https://github.com/qmmughal/texttovideo/actions/workflows/ci.yml/badge.svg)](https://github.com/qmmughal/texttovideo/actions/workflows/ci.yml)

A working Next.js/TypeScript editor with a FastAPI background worker, SQLite project/job storage, Ollama storyboards, ComfyUI visual generation, Windows or Piper narration, and FFmpeg MP4 assembly. Core processing uses local services. No cloud keys are required.

## Highlights

- **Idea → film:** a local Ollama model writes a scene-by-scene storyboard in English or Urdu.
- **Photos → film:** upload your photos and a local vision model (e.g. `qwen3-vl:8b`) writes narration for each one.
- **Narration out of the box on Windows** using built-in system voices — no extra install. Piper neural voices are optional.
- **Motion and transitions:** per-scene zoom/pan (Ken Burns), crossfade, fade-through-black, or hard cuts.
- **Readable captions:** long scene text is split into timed cues, both burned in and in the SRT file. Full Urdu RTL shaping.
- **Exports** for Shorts/Reels, YouTube, square, and portrait, with music ducking and logo placement.
- **Project management:** duplicate and delete projects; shared media is only removed when no project uses it.

## Which models generate video?

Ollama runs language and vision models only. It has **no text-to-video models**, and its experimental image generation (Z-Image Turbo, FLUX.2 Klein) only ran on macOS/Linux and was removed in Ollama v0.32.6. Frame therefore uses Ollama for writing (storyboards, photo narration) and ComfyUI for pictures and video:

| Purpose | Runs in | Good local choices |
| --- | --- | --- |
| Storyboard / script | Ollama | `qwen3:8b`, `llama3.2:3b` (small machines), `gemma3` |
| Photo narration | Ollama | `qwen3-vl:8b`, `gemma3` (vision-capable models) |
| Still images | ComfyUI | Stable Diffusion 1.5 / SDXL checkpoints, FLUX |
| Video clips | ComfyUI | Wan 2.2 (5B runs on ~8 GB VRAM), LTX-Video / LTX-2, HunyuanVideo |

Video models need a capable NVIDIA GPU. Without one, use the animated slideshow mode: motion, transitions, narration and captions all run on the CPU.

## License

The application source code is available under the [MIT License](LICENSE).
The bundled Noto Naskh Arabic font is licensed separately under the
[SIL Open Font License 1.1](frontend/public/fonts/OFL.txt).
Third-party dependencies and separately downloaded models retain their own
licenses; the MIT license does not relicense them.

## Windows quick start

Install Python 3.11+ and Node.js 22+. From PowerShell in this folder:

```powershell
.\setup.ps1
.\start.ps1
```

Open **http://127.0.0.1:3000**. The backend runs at **http://127.0.0.1:8000** and API documentation at `/docs`. Both bind to loopback. Stop with Ctrl+C in the startup terminal. If PowerShell policy prevents running scripts, run the commands below individually rather than changing machine policy.

```powershell
python -m venv .venv
python -m pip --python .venv\Scripts\python.exe install -r backend\requirements.txt
cd frontend
npm ci
cd ..
.\.venv\Scripts\python -m scripts.sample
# Terminal 1:
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
# Terminal 2, in frontend:
npm run dev
```

If `venv` reports an `ensurepip` error but creates its Python executable, the `python -m pip --python ...` command above can install dependencies into that environment using the main Python's pip. This was necessary on the development machine.

FFmpeg comes from the `imageio-ffmpeg` wheel, avoiding incompatible executables on PATH. To use another FFmpeg build, set `$env:FFMPEG_PATH='C:\tools\ffmpeg\bin\ffmpeg.exe'` before starting. H.264/AAC encoding must be available. No separate ffprobe installation is needed.

The sample project contains two explicitly hand-drawn landscape illustrations. Open it and select **Render MP4** to verify the app without installing AI models. Re-running `scripts.sample` resets this sample only; other projects are preserved.

## Connect language models

1. Install [Ollama for Windows](https://ollama.com/download/windows), start it, and install a text-capable model, for example `ollama pull qwen3:8b`. Choose a smaller model if RAM/VRAM is limited.
2. In **Models & settings**, keep `http://127.0.0.1:11434`, refresh connections, choose an installed model, and save.
3. Create a video, choose English or Urdu, duration, style, canvas, and generation mode. Generate the storyboard. Each scene's script and English visual prompt can be edited before generating media.

Model discovery uses [GET /api/tags](https://docs.ollama.com/api/tags), and each model's capabilities (such as `vision`) come from `/api/show`. Storyboards use [POST /api/generate](https://docs.ollama.com/api/generate) with a JSON schema and constrained scene count. Reasoning is switched off for thinking models to keep structured answers fast. Model quality varies, especially for Urdu. Ollama generates text, not video.

### Photos to story

1. Install a vision model, for example `ollama pull qwen3-vl:8b`, and choose it as the **Vision model** in **Models & settings**.
2. Choose **Create a video → From my photos**, add an optional theme, pick photos in order, and continue.
3. Each photo becomes a scene. The vision model writes narration for it in English or Urdu, continuing from the previous scenes, plus an English description of the photo. It also titles the film.
4. Edit any caption, use **Describe photo** to rewrite a single scene, then voice and render as usual.

Photos are downscaled to 1024 px before being sent to the local model. They never leave your computer.

## Connect local visuals

Install and start [ComfyUI](https://docs.comfy.org/installation/system_requirements) on localhost port 8188. First verify your chosen workflow works directly in ComfyUI with its models installed. ComfyUI workflows can include third-party/custom/cloud nodes; use only trusted **local inference** nodes for this app's local-only workflow.

### Animated slideshow

Use an image-generation workflow ending in `SaveImage`. `examples/comfy-image-api.json` is a starter for a conventional Stable Diffusion checkpoint with built-in nodes; replace the checkpoint filename with an installed, compatible SD checkpoint. It is not a universal workflow for FLUX or video models. The initial 512×512 output is intentionally modest; export upscaling is labeled separately.

### AI-generated video

Start with a supported native video workflow, such as the [official ComfyUI Wan 2.2 tutorial](https://docs.comfy.org/tutorials/video/wan/wan2_2). Follow that tutorial's specific model downloads, model directories, node versions, and GPU requirements. Run a short clip successfully in ComfyUI before connecting it. Use a text-to-video workflow; image-to-video conditioning upload is not automated in this first version.

### Import a workflow

1. Export the tested workflow in **API format**, not the canvas/UI format.
2. Replace the positive text prompt with the literal `{{prompt}}`.
3. Paste JSON into the image or video workflow setting.
4. Set **Model clip length** to the actual duration produced by the workflow (frames ÷ fps). This determines storyboard scene splitting. Keep output frame count and FPS fixed in the workflow. Longer films are assembled from many short scenes.
5. Save. Generate missing visuals, or regenerate one scene. Integer `seed` and `noise_seed` inputs are randomized on each generation.

The adapter checks node types with `/object_info`, submits `/prompt`, polls `/history/{prompt_id}`, and fetches saved output through `/view`, following the [ComfyUI server API](https://docs.comfy.org/development/comfyui-server/comms_routes). ComfyUI validates model filenames and input compatibility during submission. Supported output records are `images`, `gifs`, or `videos` with a saved PNG/JPEG/WebP image or MP4/WebM/MOV clip. Custom nodes with another output contract require an adapter change. No video mode falls back to a still image.

## Narration and captions

Upload narration per scene, or generate it locally with one of two engines.

**Windows built-in voices** need no install. In **Models & settings**, set **Narration engine** to Windows, then choose a voice (or leave it automatic to match the project language) and a speaking rate. Narration uses the System.Speech API through PowerShell; text is passed through a temporary UTF-8 file, never a command line. Windows ships English voices by default. For Urdu, add an Urdu voice under Windows **Settings → Time & language → Speech**, if one is available for your Windows edition, or upload narration.

**Piper** is optional and gives more natural neural voices. Configure the [Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md) and a local voice:

```powershell
# Use a Python environment supported by piper-tts (a separate Python 3.11/3.12 environment may be needed).
python -m pip install piper-tts
python -m piper.download_voices en_US-lessac-medium
```

Set the full path to that environment's `Scripts\piper.exe` and the downloaded `.onnx` file. Keep the matching `.onnx.json` alongside it. Language capability is read from the voice metadata, and mismatched language generation is rejected. An English voice is not treated as Urdu-capable. If no compatible Urdu voice exists locally, upload your Urdu narration.

English and Urdu captions support size, color, vertical position, safe margins, burned-in output, and UTF-8 SRT. Noto Naskh Arabic and its SIL Open Font License are bundled in `frontend/public/fonts`. No web-font request is required. Pillow uses RAQM where available; otherwise Arabic reshaping and Unicode bidirectional ordering provide joined RTL captions on Windows. The UI uses browser text shaping. This is Naskh, not Nastaliq; advanced Nastaliq typography is best used with a RAQM-capable renderer and compatible font.

Each scene has one narration asset. Long scene text is split into several caption cues (set **Characters per caption** in export settings), preferring sentence boundaries. Each cue's screen time is proportional to its length, and the SRT file uses the same cues. Cues are not word-aligned to the narration. Uploaded clip audio is intentionally replaced by the narration/music mix; upload any dialogue you want to preserve as narration.

## Rendering and editing

- Reorder, add, delete, edit, upload, and individually regenerate or re-voice scenes. Save before leaving the editor. Generation also saves current edits first.
- Duplicate a project to try a variation; delete removes the project, its jobs, and any media no other project uses.
- Generate missing assets reuses every completed scene. Editing a visual prompt retains its existing asset until you explicitly regenerate it.
- Each image scene has a **Motion**: slow zoom in or out, pan in any direction, still, or automatic (varies from scene to scene). Motion is rendered at twice the output resolution for smooth movement.
- **Transitions:** fade through black, crossfade, or hard cut. Crossfades blend pictures only; audio switches exactly at the scene boundary, so narration is never faded out early, and total length is unchanged. With crossfades, a video clip's last frame is held for the outgoing half of the blend. Crossfade supports up to 150 scenes.
- Image scenes extend to narration length plus 0.2 seconds. Video clips shorter than the requested scene/narration duration are rejected with an actionable error. Clips are never silently looped or frozen to conceal a short source.
- Export 1080×1920, 1920×1080, 1080×1080, 1080×1350, a small preview, or custom even dimensions up to 3840 per axis. Render each desired format; all exports remain attached to the same project.
- Crop, contain, and blurred backgrounds are supported. Caption position and logo margins adapt to output dimensions and the safe-area setting. Logo placement is currently top-left with proportional size.
- Export is 30 fps H.264/AAC, yuv420p, fast-start MP4. Source dimensions and whether resizing up occurred are stored with each output. Upscaling is conventional resizing, not AI super-resolution.
- Music loops to match the video, with adjustable gain, narration sidechain ducking, and audio fades. Use the browser player and MP4/SRT download links after rendering.

## Reliability and local operation

`data/studio.db` stores projects, settings, job state, and output metadata. Assets are UUID-named files under `data/`. Back up the entire directory. Change location with `LOCAL_VIDEO_DATA`. A single background worker runs jobs sequentially to limit resource use. Editing a project with an active job is blocked to prevent overwritten changes.

After a restart, unfinished jobs become **interrupted**, not falsely completed. Retry from Processing activity. Completed scene assets survive and missing-scene generation skips them. Partial renders restart from the beginning. Failed intermediate files are not served as completed exports.

Cancellation kills an active FFmpeg/Piper process and checks between scene operations. Ollama cancellation currently discards the result when its request returns (up to the request timeout); it does not forcibly unload a shared model. ComfyUI cancellation deletes this app's queued prompt, but leaves an already-running shared-server prompt alone. Its eventual output is not applied after cancellation. The single worker can remain occupied until that external request returns. This behavior avoids interrupting unrelated ComfyUI work.

Uploads allow only supported media types, validate content, cap files at 512 MB, and ignore user-supplied filenames. Asset paths are constrained to the data directory. Commands use argument arrays, not shell interpolation. Media probing disallows network protocols. Backend URLs must be loopback HTTP; CORS and Origin/Host checks restrict browser access. This is a single-user localhost app, not a publicly deployable multi-user service. Custom ComfyUI nodes remain software you install and trust independently.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q
cd frontend
npm run build
cd ..
.\.venv\Scripts\python -m scripts.verify_live
```

GitHub Actions runs the backend tests on Ubuntu and Windows plus the frontend typecheck and build on every push. The Windows voice test runs only where a system voice is installed.

`verify_live` requires installed `llama3.2:1b`, runs a real Ollama storyboard, renders the sample images with crossfades, and saves an `ollama-verified` project. It selects that model in settings and resets the hand-drawn sample. Test data lives under `data/test-runs`, separate from normal projects.

Verified on the development machine: **14 passing tests** and Next.js production build; local Ollama `llama3.2:1b` storyboard; two-scene 360×640 MP4 with a measured duration of 10.02 seconds; full decode with H.264/AAC/yuv420p; all four full-resolution social export dimensions; crop/contain/blur; music/ducking/logo filter composition; image-scene narration extension; shaped Urdu caption inspection; upload/path/origin validation; no silent slideshow fallback; cancellation; persisted restart interruption. The browser played the full sample to 10.021 seconds with no media error.

Not verified with real model inference here: ComfyUI image/video generation (server absent), Piper voice synthesis (no voice configured), and demanding GPU/long-duration workloads. These adapters are implemented against the documented APIs/CLI; no mock assets are presented as generated output.

## Source map

`frontend/app/page.tsx`: dashboard, wizard, storyboard, settings, jobs, exports. `frontend/app/style.css`: responsive UI. `backend/main.py`: API and background jobs. `backend/models.py`: validation. `backend/store.py`: SQLite and safe asset paths. `backend/integrations.py`: Ollama, ComfyUI, Piper. `backend/media.py`: caption shaping, FFmpeg rendering, audio mixing, SRT. `tests/test_studio.py`: focused real-media and failure checks.
