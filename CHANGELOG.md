# Changelog

All notable changes to Frame. Versions follow [semantic versioning](https://semver.org/).

## 1.3.0 — 2026-10-20

### Safety

- Acceptable-use policy ([ACCEPTABLE_USE.md](ACCEPTABLE_USE.md)): Frame refuses hateful, abusive, discriminatory, or harmful content, including content that demeans people for their religion or belief, and content promoting violence, harassment, or dehumanization. A local model reviews requests and generated text and answers a violation with a brief refusal and a safe alternative. Respectful religious content is welcome.
- The larger of the story and vision models reviews by default; a safety reviewer can be chosen in settings, and Setup check warns when the reviewer is too small to be reliable.
- Refused jobs show as "refused" without a retry button.

### Documentation

- New README with screenshots and rendered frames, plus CONTRIBUTING, SECURITY, and this changelog.

### Fixes

- Project cards mixed English and Urdu text in the wrong order.
- The export preview showed a black box until played; it now opens on a frame after the fade-in.

## 1.2.0 — 2026-10-20

The first tagged release, with a [Windows installer](https://github.com/qmmughal/texttovideo/releases/tag/v1.2.0).

### Runs anywhere

- One local server: the web interface is a static export served by the backend on port 8000, so Node.js is needed only to build it.
- Windows installer (per user, no administrator rights) that installs Python with winget if needed.
- `setup.sh` and `start.sh` for Linux and macOS; Dockerfile and compose file with an Ollama container.
- Setup check: detects memory, CPU, disk, and graphics card, recommends models that fit, and downloads them with progress, cancel, and resume.

### AI without a graphics card

- Built-in image generation on the CPU (or Intel graphics/NPU) with OpenVINO GenAI and LCM Dreamshaper v7, about 15 s per image on a laptop CPU.
- Built-in neural narration on every OS with sherpa-onnx: English voices Joe, Cori, and Alba, and the Urdu voice Fasih. Only commercially usable voices are offered.

### Making videos

- Photos to story: a local vision model writes narration for your photos.
- Word-synced captions with the spoken word highlighted; timings from Windows speech or Whisper.
- Translate a project between English and Urdu, with Urdu script enforced.
- Per-scene zoom and pan motion; crossfade, fade-through-black, and hard-cut transitions.
- Render several social formats in one job; brand presets for caption style, colours, transition, logo, and music.
- Duplicate and delete projects; Windows system voices for narration.

### Fixes

- Storyboards with empty captions are rejected instead of saved.
- Whisper audio is decoded with the bundled FFmpeg (PyAV 19 is incompatible with faster-whisper 1.2.1).
- Model downloads retry dropped connections and resume partial files.
- PowerShell scripts are ASCII so Windows PowerShell 5.1 can parse them, and Python is detected correctly there.

## 1.0.0 — 2026-10-19

Initial open-source release (untagged): Next.js editor, FastAPI worker, SQLite storage, Ollama storyboards, ComfyUI image and video workflows, Piper narration, Urdu captions, and FFmpeg MP4 export under the MIT licence.
