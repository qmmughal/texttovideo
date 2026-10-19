import os
import tempfile

os.makedirs("data/test-runs", exist_ok=True)
os.environ["LOCAL_VIDEO_DATA"] = tempfile.mkdtemp(prefix="frame-tests-", dir="data/test-runs")

import json
import subprocess
import time
import wave

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import integrations, media, store
from backend.main import app
from backend.models import Export, Project, Scene, Settings


def no_progress(*args):
    pass


def not_cancelled():
    return False


def write_silence(name, seconds):
    with wave.open(str(store.asset_path(name)), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\0\0" * int(16000 * seconds))


@pytest.fixture
def project():
    Image.new("RGB", (320, 240), "#679782").save(store.asset_path("test.png"))
    return Project(
        id="test",
        scenes=[
            Scene(id="one", text="A local story", duration=1, asset="test.png"),
            Scene(id="two", text="Another frame", duration=1, asset="test.png"),
        ],
    )


def decodes_cleanly(name):
    result = subprocess.run(
        [media.FFMPEG, "-v", "error", "-i", str(store.asset_path(name)), "-f", "null", "-"], capture_output=True
    )
    return result.returncode == 0, result.stderr


@pytest.mark.parametrize("fit", ["crop", "contain", "blur"])
def test_real_render(project, fit):
    result = media.render(
        project, Export(width=240, height=320, fit=fit, font_size=22), Settings(), no_progress, not_cancelled
    )
    info = media.probe(store.asset_path(result["asset"]))
    assert info["width"] == 240 and info["height"] == 320
    assert abs(info["duration"] - 2) < 0.1 and info["audio"]
    ok, error = decodes_cleanly(result["asset"])
    assert ok, error
    metadata = subprocess.run([media.FFMPEG, "-i", str(store.asset_path(result["asset"]))], capture_output=True)
    text = metadata.stderr.decode(errors="replace")
    assert "h264" in text and "yuv420p" in text and "aac" in text
    assert "00:00:02,000" in store.asset_path(result["srt"]).read_text()


@pytest.mark.parametrize("transition", ["crossfade", "none"])
def test_transitions_keep_timeline(project, transition):
    write_silence("music.wav", 1)
    project.music = "music.wav"
    project.scenes[0].duration = 1.5
    options = Export(width=240, height=320, transition=transition, fade=0.5, font_size=22)
    result = media.render(project, options, Settings(), no_progress, not_cancelled)
    info = media.probe(store.asset_path(result["asset"]))
    assert abs(info["duration"] - 2.5) < 0.1 and info["audio"]
    assert (info["width"], info["height"]) == (240, 320)
    ok, error = decodes_cleanly(result["asset"])
    assert ok, error
    assert "00:00:01,500 --> 00:00:02,500" in store.asset_path(result["srt"]).read_text()


@pytest.mark.parametrize("motion", ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "none"])
def test_motions(project, motion):
    project.scenes = project.scenes[:1]
    project.scenes[0].motion = motion
    result = media.render(project, Export(width=240, height=320, captions=False), Settings(), no_progress, not_cancelled)
    assert abs(media.probe(store.asset_path(result["asset"]))["duration"] - 1) < 0.1


def test_caption_cues_split_long_text(project):
    text = "The river wakes before the city does. Boats drift past the old bridge. Then the bells begin to ring."
    chunks = media.caption_chunks(text, 40)
    assert len(chunks) == 3 and all(len(c) <= 40 for c in chunks)
    assert media.caption_chunks("Short line.", 40) == ["Short line."]
    assert len(media.caption_chunks("یہ پہلا جملہ ہے۔ یہ دوسرا جملہ ہے۔", 20)) == 2
    project.scenes = project.scenes[:1]
    project.scenes[0].text = text
    project.scenes[0].duration = 3
    result = media.render(
        project, Export(width=240, height=320, font_size=14, caption_chars=40), Settings(), no_progress, not_cancelled
    )
    srt = store.asset_path(result["srt"]).read_text()
    assert srt.count("-->") == 3 and "00:00:03,000" in srt


def test_narration_extends_image(project):
    write_silence("voice.wav", 2)
    project.scenes = project.scenes[:1]
    project.scenes[0].narration = "voice.wav"
    result = media.render(project, Export(width=240, height=320, captions=False), Settings(), no_progress, not_cancelled)
    assert result["duration"] == 2.2


def test_urdu_shaping():
    result = media.caption_png("یہ ایک خوبصورت نئی کہانی ہے", "ur", Export(width=540, height=960, font_size=42), Settings().font)
    assert Image.open(store.asset_path(result)).getbbox() is not None


def test_no_silent_slideshow(project):
    project.mode = "video"
    with pytest.raises(ValueError, match="requires video clips"):
        media.render(project, Export(), Settings(), no_progress, not_cancelled)


def test_api_validation_and_recovery():
    store.put("job", "interrupted", {"id": "interrupted", "project": "none", "status": "running"})
    with TestClient(app) as client:
        assert store.get("job", "interrupted")["status"] == "interrupted"
        assert client.put("/api/settings", json={"ollama": "https://external.example"}).status_code == 422
        assert client.post("/api/projects", json={"duration": -1}).status_code == 422
        assert client.post("/api/upload", files={"file": ("evil.mp4", b"not media", "video/mp4")}).status_code == 400
        assert client.post("/api/projects", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/projects/missing").status_code == 404
        p = client.post("/api/projects", json={}).json()
        j = client.post(f'/api/projects/{p["id"]}/jobs/render', json={}).json()
        for _ in range(50):
            current = store.get("job", j["id"])
            if current["status"] == "failed":
                break
            time.sleep(0.05)
        assert current["status"] == "failed" and "Add scenes" in current["stage"]


def test_duplicate_and_delete_project():
    Image.new("RGB", (64, 64), "red").save(store.asset_path("shared.png"))
    Image.new("RGB", (64, 64), "blue").save(store.asset_path("own.png"))
    with TestClient(app) as client:
        scenes = [{"id": "a", "asset": "shared.png"}]
        original = client.post("/api/projects", json={"title": "Trip", "scenes": scenes}).json()
        copy = client.post(f'/api/projects/{original["id"]}/duplicate').json()
        assert copy["title"] == "Trip (copy)" and copy["id"] != original["id"]
        assert copy["scenes"][0]["id"] != "a" and copy["scenes"][0]["asset"] == "shared.png"
        copy["scenes"].append({"id": "b", "asset": "own.png"})
        client.put(f'/api/projects/{copy["id"]}', json=copy)
        assert client.delete(f'/api/projects/{copy["id"]}').json()["files_removed"] == 1
        assert store.asset_path("shared.png").is_file() and not store.asset_path("own.png").exists()
        assert client.get(f'/api/projects/{copy["id"]}').status_code == 404
        client.delete(f'/api/projects/{original["id"]}')
        assert not store.asset_path("shared.png").exists()


def test_describe_photos_with_vision_model(project, monkeypatch):
    calls = []

    def fake_request(base, method, route, **kwargs):
        if route == "/api/show":
            return {"capabilities": ["completion", "vision", "thinking"]}
        body = kwargs["json"]
        calls.append(body)
        if body.get("images"):
            return {"response": json.dumps({"text": f"Line {len(calls)}", "prompt": "A green field"})}
        return {"response": json.dumps({"title": "Green days", "description": "A short film."})}

    monkeypatch.setattr(integrations, "request", fake_request)
    project.scenes[1].text = ""
    project.scenes[0].text = ""
    result = integrations.describe_photos(project, Settings(vision_model="qwen3-vl:8b"), not_cancelled, no_progress)
    assert [s.text for s in result.scenes] == ["Line 1", "Line 2"]
    assert result.title == "Green days"
    assert all(c["think"] is False for c in calls) and len(calls[0]["images"]) == 1
    assert "Line 1" in calls[1]["prompt"]
    with pytest.raises(ValueError, match="vision model"):
        integrations.describe_photos(project, Settings(), not_cancelled, no_progress)


@pytest.mark.skipif(os.name != "nt" or not integrations.windows_voices(), reason="needs an installed Windows voice")
def test_windows_voice_narration():
    settings = Settings(tts="windows")
    assert integrations.voice_info(settings)["available"]
    name = integrations.narrate(Scene(id="v", text="Hello from Frame."), "en", settings, not_cancelled)
    info = media.probe(store.asset_path(name))
    assert info["audio"] and info["duration"] > 0.5
    if not any(v["language"].startswith("ur") for v in integrations.windows_voices()):
        with pytest.raises(ValueError, match="Urdu"):
            integrations.narrate(Scene(id="u", text="سلام"), "ur", settings, not_cancelled)


def test_path_traversal():
    for name in ("../secret", "..\\secret", "C:\\Windows\\system.ini"):
        with pytest.raises(ValueError):
            store.asset_path(name)


def test_cancel(project):
    with pytest.raises(RuntimeError, match="Cancelled"):
        media.render(project, Export(width=240, height=320), Settings(), no_progress, lambda: True)


@pytest.mark.parametrize("size", [(1080, 1920), (1920, 1080), (1080, 1080), (1080, 1350)])
def test_social_sizes(project, size):
    project.scenes = project.scenes[:1]
    project.scenes[0].duration = 0.5
    result = media.render(
        project, Export(width=size[0], height=size[1], captions=False), Settings(), no_progress, not_cancelled
    )
    info = media.probe(store.asset_path(result["asset"]))
    assert (info["width"], info["height"]) == size
    assert result["upscaled"]


def test_music_logo_and_short_clip(project):
    write_silence("music.wav", 1)
    project.music = "music.wav"
    project.logo = "test.png"
    project.scenes = project.scenes[:1]
    result = media.render(project, Export(width=240, height=320), Settings(), no_progress, not_cancelled)
    assert media.probe(store.asset_path(result["asset"]))["audio"]
    project.scenes[0].asset = result["asset"]
    project.scenes[0].duration = 4
    project.mode = "video"
    with pytest.raises(ValueError, match="too short"):
        media.render(project, Export(width=240, height=320), Settings(), no_progress, not_cancelled)


def test_video_clips_crossfade(project):
    first = media.render(project, Export(width=240, height=320, captions=False), Settings(), no_progress, not_cancelled)
    project.mode = "video"
    for scene in project.scenes:
        scene.asset = first["asset"]
    result = media.render(
        project, Export(width=240, height=320, transition="crossfade", fade=0.4), Settings(), no_progress, not_cancelled
    )
    assert abs(media.probe(store.asset_path(result["asset"]))["duration"] - 2) < 0.1
