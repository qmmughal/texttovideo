# Contributing to Frame

Thanks for helping. Frame is a local-first app: everything it does should work offline on the user's own computer, and nothing should be presented as AI output unless a model produced it.

## Getting set up

You need Python 3.11+ and Node.js 22+.

```sh
./setup.sh            # Linux/macOS  (Windows: .\setup.ps1)
./start.sh --dev      # backend on :8000, hot-reloading UI on :3000  (Windows: .\start.ps1 -Dev)
```

Set `LOCAL_VIDEO_DATA` to a scratch folder while developing so your own projects are untouched. Running `python -m scripts.sample` recreates the hand-drawn sample project, which renders without any AI models.

## Project layout

| Path | What lives there |
| --- | --- |
| `backend/main.py` | HTTP API, setup endpoints, and the background job worker |
| `backend/models.py` | Pydantic models and validation for projects, settings, exports, presets |
| `backend/media.py` | Captions, motion, transitions, FFmpeg rendering, audio mixing, SRT |
| `backend/integrations.py` | Ollama (storyboards, photo narration, translation), ComfyUI, narration engines |
| `backend/words.py` | Word timings and Whisper alignment |
| `backend/cpu_images.py` | OpenVINO image generation |
| `backend/voices.py` | Built-in neural voices (sherpa-onnx) |
| `backend/hub.py` | Resumable Hugging Face downloads |
| `backend/system.py` | Hardware detection and model recommendations |
| `backend/store.py` | SQLite documents and safe asset paths |
| `frontend/app/page.tsx` | App state and actions |
| `frontend/components/` | Dashboard, wizard, editor, scene card, export panel, setup check, settings, jobs |
| `frontend/lib/api.ts` | API client and shared types |
| `installer/` | Windows installer (Inno Setup) and first-run script |
| `tests/test_studio.py` | Backend tests, including real FFmpeg renders |

## Tests

```sh
python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

Tests render real video with FFmpeg rather than mocking it. External model servers (Ollama, ComfyUI) are mocked at the HTTP boundary. Tests that need something only some machines have, such as a Windows system voice, skip themselves elsewhere. Add a test for every behaviour you change; a bug fix should come with a test that fails without it.

`python -m scripts.verify_live` runs a real Ollama storyboard and render if `llama3.2:1b` is installed.

## Conventions

- Match the surrounding style: readable Python (PEP 8, 120-column lines) and TypeScript components with typed props.
- Keep user-facing errors actionable: say what to do next ("Download an Urdu voice in Setup check"), not just what failed.
- Never send user data off the machine. New network access must go to localhost, a listed service host, or a model download the user starts.
- Only add models and voices whose licences allow commercial use, and show the licence in the app.
- PowerShell scripts must stay ASCII: Windows PowerShell 5.1 reads BOM-less files in the system code page.

## Pull requests

1. Branch from `main` and keep each pull request to one topic.
2. Run the tests and the frontend build locally.
3. Describe what changed, how you tested it, and anything you could not test.
4. CI must pass: backend tests on Ubuntu, Windows, and macOS; frontend build; Linux setup script; Docker image; Windows installer.

## Releasing

Update [CHANGELOG.md](CHANGELOG.md), merge to `main`, then push a version tag:

```sh
git tag -a v1.3.0 -m "Frame 1.3.0"
git push origin v1.3.0
```

The release workflow builds `Frame-Setup-<version>.exe` and attaches it to a GitHub release.
