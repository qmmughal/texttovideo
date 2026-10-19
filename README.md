# Frame — local AI video studio

[![CI](https://github.com/qmmughal/texttovideo/actions/workflows/ci.yml/badge.svg)](https://github.com/qmmughal/texttovideo/actions/workflows/ci.yml)

A working Next.js/TypeScript editor with a FastAPI background worker, SQLite project/job storage, Ollama storyboards, ComfyUI visual generation, Windows or Piper narration, and FFmpeg MP4 assembly. Core processing uses local services. No cloud keys are required.

## Highlights

- **Works without a graphics card:** a setup check sizes models to your computer, and AI images can be drawn on the CPU.
- **Idea → film:** a local Ollama model writes a scene-by-scene storyboard in English or Urdu.
- **Photos → film:** upload your photos and a local vision model (e.g. `qwen3-vl:8b`) writes narration for each one.
- **Natural English and Urdu narration offline** with built-in neural voices on every OS, or Windows system voices with no download.
- **Translate a project** between English and Urdu with your local language model, keeping the visuals.
- **Brand presets** save your caption style, colours, transitions, logo and music as a reusable look.
- **Render every social format in one go:** 9:16, 16:9, 1:1 and 4:5 from a single job.
- **Runs on Windows, Linux, macOS, or Docker**, with a Windows installer.
- **Motion and transitions:** per-scene zoom/pan (Ken Burns), crossfade, fade-through-black, or hard cuts.
- **Word-synced captions:** short phrases appear as they are spoken, with the current word highlighted (exact timing with Windows voices; Whisper timing for uploaded or Piper narration). Sentence captions are also available. Full Urdu RTL shaping.
- **Exports** for Shorts/Reels, YouTube, square, and portrait, with music ducking and logo placement.
- **Project management:** duplicate and delete projects; shared media is only removed when no project uses it.

## Which models generate video?

Ollama runs language and vision models only. It has **no text-to-video models**, and its experimental image generation (Z-Image Turbo, FLUX.2 Klein) only ran on macOS/Linux and was removed in Ollama v0.32.6. Frame therefore uses Ollama for writing (storyboards, photo narration), a built-in OpenVINO engine or ComfyUI for pictures, and ComfyUI for video:

| Purpose | Runs in | Good local choices |
| --- | --- | --- |
| Storyboard / script | Ollama | `qwen3:8b`, `qwen3:4b` (8–16 GB RAM), `qwen3:1.7b` (under 8 GB) |
| Photo narration | Ollama | `qwen3-vl:8b`, `qwen3-vl:4b`, `qwen3-vl:2b` (vision-capable models) |
| Still images, no GPU | Built-in (OpenVINO) | LCM Dreamshaper v7 int8, downloaded from Setup check |
| Still images, NVIDIA GPU | ComfyUI | Stable Diffusion 1.5 / SDXL checkpoints, FLUX |
| Video clips | ComfyUI | Wan 2.2 (5B runs on ~8 GB VRAM), LTX-Video / LTX-2, HunyuanVideo |

Video models need a capable NVIDIA GPU. Without one, use the animated slideshow mode: images, motion, transitions, narration and captions all run on the CPU.

## Running on a computer without a graphics card

Everything except AI video clips runs on an ordinary CPU. Rough timings on a typical laptop:

| Step | CPU-only speed |
| --- | --- |
| Rendering a 30 s 1080×1920 Short (6 scenes, motion, crossfades, captions) | about 20 s on a recent laptop, a minute or two on older ones |
| Storyboard with a 4B model | about 30–60 s |
| One AI image (512×768, LCM, 4 steps) | about 15 s on a recent laptop CPU (measured), up to about a minute on older ones; the first image also loads the model |
| Narration with Windows voices | a second or two per scene |
| Word timing with the Whisper base model | a few seconds per scene |
| AI video (Wan, LTX) | not practical: minutes to hours per clip |

## Setup check

Open **Setup check** in the sidebar on first run. It reads the computer's memory, CPU, free disk space, and graphics card, then recommends a tier:

- **Light** (under 8 GB memory): `qwen3:1.7b` and `qwen3-vl:2b`; use your own photos for visuals.
- **Standard (CPU)** (8–16 GB): `qwen3:4b`, `qwen3-vl:4b`, and the built-in image engine.
- **Strong (CPU)** (16 GB or more): `qwen3:8b`, `qwen3-vl:8b`, and the built-in image engine.
- **GPU** (NVIDIA with 8 GB or more): the 8B models plus ComfyUI for images and video.

Each step has a button that downloads the model through Ollama or from Hugging Face, shows progress, can be cancelled, and resumes after an interruption. Finished downloads are selected in settings automatically. The dashboard shows a reminder until the essentials are ready.

## AI images without a graphics card

The built-in engine uses [OpenVINO GenAI](https://openvinotoolkit.github.io/openvino.genai/) with `OpenVINO/LCM_Dreamshaper_v7-int8-ov` (about 1 GB download, MIT licence), a pre-converted latent consistency model that needs only 4 steps per image. Download it from Setup check; it is stored in `data/models`. In **Models & settings**, choose **Built-in · runs on CPU** as the image engine and optionally run it on Intel graphics or an Intel NPU instead of the CPU.

Images are drawn at 512×768, 768×512, or 512×512 to match the export shape, then scaled to the export size, so they are not high resolution. The scene's visual prompt and the project's style are combined into the image prompt. Video mode always uses the ComfyUI video workflow.

## License

The application source code is available under the [MIT License](LICENSE).
The bundled Noto Naskh Arabic font is licensed separately under the
[SIL Open Font License 1.1](frontend/public/fonts/OFL.txt).
Third-party dependencies and separately downloaded models retain their own
licenses; the MIT license does not relicense them.

## Install

Frame runs as one local server at **http://127.0.0.1:8000** (API documentation at `/docs`). It binds to this computer only. After installing, open **Setup check** in the sidebar to download models that suit your hardware.

### Windows installer

Download `Frame-Setup-<version>.exe` from the [Releases page](https://github.com/qmmughal/texttovideo/releases) and run it. It installs for the current user without administrator rights, installs Python 3.12 with winget if no Python 3.11+ is found, sets up the Python packages (a few minutes, once), and adds **Frame** to the Start menu. The shortcut starts the server and opens your browser; close its window to stop Frame. Uninstalling removes the program and its Python environment but keeps your projects in the install folder's `data` directory.

### Windows from source

Install Python 3.11+ and Node.js 22+. From PowerShell in this folder:

```powershell
.\setup.ps1
.\start.ps1
```

`start.ps1` opens the browser when the server is ready; press Ctrl+C to stop. `.\start.ps1 -Dev` runs the hot-reloading interface on port 3000 for development. If PowerShell policy prevents running scripts, run `powershell -ExecutionPolicy Bypass -File .\setup.ps1` rather than changing machine policy.

### Linux and macOS

Install Python 3.11+ (with `venv`) and Node.js 22+, then:

```sh
./setup.sh
./start.sh
```

Windows system voices are not available here; use the built-in neural voices from Setup check. Everything else works the same.

### Docker

```sh
docker compose up -d
```

This builds Frame, starts it with an Ollama container, and publishes it on `127.0.0.1:8000` only. Projects and models are kept in Docker volumes. Install models from Setup check as usual; they download into the Ollama container. AI images and narration run on the CPU inside the container. To reach services by name, Frame accepts only the hosts listed in `FRAME_SERVICE_HOSTS` besides localhost.

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

Upload narration per scene, or generate it locally.

**Built-in neural voices** work on every operating system. Download them from Setup check (about 80 MB each). They are [Piper](https://github.com/OHF-Voice/piper1-gpl) voices run in-process by [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx), and only voices whose training data allows commercial use are offered:

| Voice | Language | Licence |
| --- | --- | --- |
| Joe | US English, male | CC0 |
| Cori | UK English, female | public domain |
| Alba | Scottish English, female | CC BY 4.0 |
| Fasih | Urdu, male | MIT |

Choose the English and Urdu voice under **Models & settings**. When a speech model for word timing is installed, narration from these voices is word-timed automatically.

**Windows system voices** need no download. In **Models & settings**, set **Narration engine** to Windows, then choose a voice (or leave it automatic to match the project language) and a speaking rate. Narration uses the System.Speech API through PowerShell; text is passed through a temporary UTF-8 file, never a command line. Windows ships English voices by default. Urdu projects automatically use the built-in Urdu voice when it is downloaded and Windows has none.

**Piper command line** remains available for advanced users who want other Piper voices. Configure the [Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md) and a local voice:

```powershell
# Use a Python environment supported by piper-tts (a separate Python 3.11/3.12 environment may be needed).
python -m pip install piper-tts
python -m piper.download_voices en_US-lessac-medium
```

Set the full path to that environment's `Scripts\piper.exe` and the downloaded `.onnx` file. Keep the matching `.onnx.json` alongside it. Language capability is read from the voice metadata, and mismatched language generation is rejected. An English voice is not treated as Urdu-capable. If no compatible Urdu voice exists locally, upload your Urdu narration.

English and Urdu captions support size, color, vertical position, safe margins, burned-in output, and UTF-8 SRT. Noto Naskh Arabic and its SIL Open Font License are bundled in `frontend/public/fonts`. No web-font request is required. Pillow uses RAQM where available; otherwise Arabic reshaping and Unicode bidirectional ordering provide joined RTL captions on Windows. The UI uses browser text shaping. This is Naskh, not Nastaliq; advanced Nastaliq typography is best used with a RAQM-capable renderer and compatible font.

Choose **Caption style** in export settings:

- **Word-synced:** short phrases of up to five words appear as they are spoken, with the current word in the highlight colour. Windows voices report exact word timings while speaking. For uploaded or Piper narration, download the Whisper speech model in Setup check and use **Time captions to voice**; a scene with narration but no script gets its caption filled in from what was said. Without timings, words are spread evenly over the narration. Urdu phrases are shown whole without per-word colouring, to keep letters joined.
- **Sentences:** each scene has one narration asset. Long scene text is split into several caption cues (set **Characters per caption** in export settings), preferring sentence boundaries. Each cue's screen time is proportional to its length, and the SRT file uses the same cues. Cues are not word-aligned to the narration. Uploaded clip audio is intentionally replaced by the narration/music mix; upload any dialogue you want to preserve as narration.

## Translate a project

On a project card, choose **اردو copy** (or **English copy** for an Urdu project). Frame makes a copy, and your storyboard model translates every caption, the title, and the description. Visuals and visual prompts are kept; narration is cleared because it belongs to the old language, so generate voices for the copy. Urdu translations must come back in Urdu script; a reply in Roman Urdu is retried once and otherwise reported, so choose a larger model if that happens.

## Brand presets

In export settings, **Save look** stores the caption style and colours, highlight colour, transition, safe area, music volume, logo, and music under a name. **Brand preset** applies a saved look to any project. Saving under an existing name updates that preset. Media used by a preset is never removed when a project is deleted.

## Rendering and editing

- **Also render** in export settings adds other social formats to the same job: one click produces the current format plus any of 9:16, 16:9, 1:1, and 4:5. Caption size is scaled to each frame.

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

GitHub Actions runs the backend tests on Ubuntu, Windows, and macOS; the frontend typecheck and build; the Linux setup script; a Docker build and smoke test; and the Windows installer build (downloadable from the run). Pushing a tag such as `v1.2.0` publishes the installer on a GitHub release. The Windows voice test runs only where a system voice is installed.

`verify_live` requires installed `llama3.2:1b`, runs a real Ollama storyboard, renders the sample images with crossfades, and saves an `ollama-verified` project. It selects that model in settings and resets the hand-drawn sample. Test data lives under `data/test-runs`, separate from normal projects.

Verified on the development machine: **14 passing tests** and Next.js production build; local Ollama `llama3.2:1b` storyboard; two-scene 360×640 MP4 with a measured duration of 10.02 seconds; full decode with H.264/AAC/yuv420p; all four full-resolution social export dimensions; crop/contain/blur; music/ducking/logo filter composition; image-scene narration extension; shaped Urdu caption inspection; upload/path/origin validation; no silent slideshow fallback; cancellation; persisted restart interruption. The browser played the full sample to 10.021 seconds with no media error.

Not verified with real model inference here: ComfyUI image/video generation (server absent), Piper voice synthesis (no voice configured), and demanding GPU/long-duration workloads. These adapters are implemented against the documented APIs/CLI; no mock assets are presented as generated output.

## Source map

`frontend/app/page.tsx`: app state and actions. `frontend/components/`: dashboard, wizard, editor, scene cards, export panel, setup check, settings, jobs. `frontend/lib/api.ts`: API client and types. `backend/main.py`: API, setup and background jobs. `backend/models.py`: validation. `backend/store.py`: SQLite and safe asset paths. `backend/integrations.py`: Ollama storyboards, photo narration, translation, ComfyUI, narration engines. `backend/media.py`: captions, motion, transitions, FFmpeg rendering, audio mixing, SRT. `backend/words.py`: word timing and Whisper alignment. `backend/cpu_images.py`: OpenVINO image generation. `backend/voices.py`: built-in neural voices. `backend/hub.py`: resumable model downloads. `backend/system.py`: hardware detection and recommendations. `installer/`: Windows installer. `tests/test_studio.py`: real-media and failure checks.
