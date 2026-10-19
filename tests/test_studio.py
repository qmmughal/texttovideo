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

import httpx

from backend import cpu_images, integrations, media, safety, store, system, words
from backend.main import app
from backend.models import Export, Project, Scene, Settings


REAL_REVIEW = safety.review


@pytest.fixture(autouse=True)
def allow_content(monkeypatch):
    """Tests never call a live model for the safety review; test_acceptable_use covers it with a fake one."""
    monkeypatch.setattr(safety, "review", lambda *args, **kwargs: None)


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
    name, x, y = media.caption_png("یہ ایک خوبصورت نئی کہانی ہے", "ur", Export(width=540, height=960, font_size=42), Settings().font)
    image = Image.open(store.asset_path(name))
    assert image.getbbox() is not None and image.width < 540 and y > 400


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
    name, timed = integrations.narrate(Scene(id="v", text="Hello from Frame."), "en", settings, not_cancelled)
    info = media.probe(store.asset_path(name))
    assert info["audio"] and info["duration"] > 0.5
    assert [w["text"] for w in timed] == ["Hello", "from", "Frame"]
    assert all(a["start"] < b["start"] for a, b in zip(timed, timed[1:])) and timed[-1]["end"] <= info["duration"] + 0.01
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


def test_word_timing_helpers():
    estimated = words.estimate("one two three", 3)
    assert estimated[0]["start"] == 0 and abs(estimated[-1]["end"] - 3) < 0.01
    heard = [
        {"text": "The", "start": 0.1, "end": 0.3},
        {"text": "son", "start": 0.3, "end": 0.6},
        {"text": "rises", "start": 0.6, "end": 1.0},
        {"text": "today", "start": 1.4, "end": 1.9},
    ]
    aligned = words.align("The sun rises slowly today", heard)
    assert [w["text"] for w in aligned] == ["The", "sun", "rises", "slowly", "today"]
    assert aligned[3]["start"] == 1.0 and aligned[3]["end"] == 1.4 and aligned[4]["start"] == 1.4
    groups = words.phrases(words.estimate("Hello there. This is a longer sentence that needs splitting", 6))
    assert [w["text"] for w in groups[0]] == ["Hello", "there."]
    assert all(len(" ".join(w["text"] for w in g)) <= 22 or len(g) == 1 for g in groups)
    events = [{"start": 0.1, "at": 0, "length": 5}, {"start": 0.6, "at": 6, "length": 5}]
    assert integrations.speech_words("Hello world", events, 1.2) == [
        {"text": "Hello", "start": 0.1, "end": 0.6},
        {"text": "world", "start": 0.6, "end": 1.2},
    ]


@pytest.mark.parametrize("language", ["en", "ur"])
def test_word_synced_render(project, language):
    write_silence("speech.wav", 1.5)
    scene = project.scenes[0]
    scene.text = "Every story starts with a little light" if language == "en" else "ہر کہانی تھوڑی سی روشنی سے شروع ہوتی ہے"
    scene.narration = "speech.wav"
    scene.words = words.estimate(scene.text, 1.5)
    scene.words_for = "speech.wav"
    project.language = language
    project.scenes = [scene]
    options = Export(width=240, height=320, font_size=24, caption_style="words")
    result = media.render(project, options, Settings(), no_progress, not_cancelled)
    srt = store.asset_path(result["srt"]).read_text(encoding="utf-8")
    assert srt.count("-->") >= 2 and srt.startswith("1\n00:00:00,000")
    ok, error = decodes_cleanly(result["asset"])
    assert ok, error


def test_highlighted_phrase_image():
    options = Export(width=360, height=640, font_size=30, highlight="#ff0000")
    name, x, y = media.phrase_png(["Make", "it", "move"], 2, options, Settings().font)
    colors = {c[:3] for _, c in Image.open(store.asset_path(name)).convert("RGBA").getcolors(100000) if c[3] == 255}
    assert (255, 0, 0) in colors and (255, 255, 255) in colors and x > 0


@pytest.mark.parametrize(
    "ram, gpus, tier, model",
    [(6, [], "Light", "qwen3:1.7b"), (12, [], "Standard (CPU)", "qwen3:4b"),
     (32, [], "Strong (CPU)", "qwen3:8b"), (32, [{"name": "RTX", "vram_gb": 12}], "GPU", "qwen3:8b")],
)
def test_recommendations(ram, gpus, tier, model):
    plan = system.recommend({"ram_gb": ram, "nvidia": gpus})
    assert plan["name"] == tier and plan["text_model"][0] == model and plan["video"] == bool(gpus)


def test_image_model_download(monkeypatch):
    files = {"model_index.json": b"{}", "unet/openvino_model.bin": b"x" * 3000, "safety_checker/model.bin": b"big"}

    def handler(request):
        if "/api/models/" in request.url.path:
            return httpx.Response(200, json=[{"type": "directory", "path": "unet"}] + [
                {"type": "file", "path": k, "size": len(v)} for k, v in files.items()])
        return httpx.Response(200, content=files[request.url.path.split("/resolve/main/")[1]])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert not cpu_images.is_downloaded("lcm-dreamshaper")
    with pytest.raises(ValueError, match="not downloaded"):
        cpu_images.generate("a hill", "Cinematic", Settings(), not_cancelled, no_progress)
    with pytest.raises(RuntimeError, match="Cancelled"):
        cpu_images.download("lcm-dreamshaper", lambda: True, no_progress, client)
    cpu_images.download("lcm-dreamshaper", not_cancelled, no_progress, client)
    folder = cpu_images.model_dir("lcm-dreamshaper")
    assert (folder / "unet/openvino_model.bin").stat().st_size == 3000 and cpu_images.is_downloaded("lcm-dreamshaper")
    assert not (folder / "safety_checker").exists()
    assert cpu_images.size_for(9 / 16) == (512, 768) and cpu_images.size_for(16 / 9) == (768, 512)


def test_setup_api_and_align_job(project, monkeypatch):
    write_silence("talk.wav", 1)
    monkeypatch.setattr(words, "transcribe", lambda path, language, size: [
        {"text": "hello", "start": 0.1, "end": 0.4}, {"text": "world", "start": 0.5, "end": 0.9}])
    with TestClient(app) as client:
        setup = client.get("/api/setup").json()
        assert {"hardware", "plan", "ollama", "images", "words"} <= setup.keys()
        assert setup["hardware"]["threads"] >= 1 and setup["plan"]["text_model"][0]
        assert client.post("/api/setup/jobs/format_disk", json={}).status_code == 400
        assert client.post("/api/setup/jobs/image_model", json={"key": "../../evil"}).status_code == 400
        scenes = [{"id": "s", "asset": "test.png", "narration": "talk.wav", "text": ""}]
        p = client.post("/api/projects", json={"scenes": scenes}).json()
        job = client.post(f'/api/projects/{p["id"]}/jobs/align', json={}).json()
        for _ in range(100):
            if store.get("job", job["id"])["status"] not in ("queued", "running"):
                break
            time.sleep(0.05)
        assert store.get("job", job["id"])["status"] == "completed"
        scene = client.get(f'/api/projects/{p["id"]}').json()["scenes"][0]
        assert scene["text"] == "hello world" and scene["words_for"] == "talk.wav" and scene["words"][1]["start"] == 0.5


def wait_for(job_id, seconds=60):
    for _ in range(int(seconds / 0.05)):
        job = store.get("job", job_id)
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_builtin_voices(monkeypatch, project):
    from backend import hub, voices

    settings = Settings(tts="builtin")
    assert not integrations.voice_info(settings)["available"]
    with pytest.raises(ValueError, match="No Urdu voice"):
        integrations.narrate(Scene(id="u", text="سلام"), "ur", settings, not_cancelled)
    # Pretend the Urdu voice is downloaded and synthesise a short tone instead of loading a model.
    folder = hub.folder_for(voices.CATALOG["ur_PK-fasih-medium"]["repo"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".complete").write_text("x")
    spoken = []
    monkeypatch.setattr(voices, "synthesize", lambda text, key, path, rate, threads: (spoken.append(key), write_silence(path.name, 1)))
    assert voices.pick("ur", "missing") == "ur_PK-fasih-medium" and voices.pick("en", "en_US-joe-medium") is None
    info = integrations.voice_info(settings)
    assert info["available"] and info["language"] == "ur"
    name, timed = integrations.narrate(Scene(id="u", text="سلام"), "ur", settings, not_cancelled)
    assert spoken == ["ur_PK-fasih-medium"] and timed == [] and media.probe(store.asset_path(name))["audio"]
    # Windows narration hands Urdu to the built-in voice when Windows has no Urdu voice.
    monkeypatch.setattr(integrations, "windows_voices", lambda: [{"name": "Zira", "language": "en-US"}])
    integrations.narrate(Scene(id="u2", text="سلام"), "ur", Settings(tts="windows"), not_cancelled)
    assert spoken == ["ur_PK-fasih-medium", "ur_PK-fasih-medium"]


def test_translate_project(monkeypatch, project):
    def fake_json(settings, model, prompt, schema, images=None):
        if "lines" in schema["properties"]:
            count = schema["properties"]["lines"]["minItems"]
            return {"lines": [f"ترجمہ {i + 1}" for i in range(count)]}
        return {"title": "نئی فلم", "description": "ایک مختصر فلم"}

    monkeypatch.setattr(integrations, "ollama_json", fake_json)
    write_silence("old.wav", 1)
    with TestClient(app) as client:
        scenes = [{"id": "a", "text": "Hello there", "narration": "old.wav", "asset": "test.png"},
                  {"id": "b", "text": "Goodbye", "asset": "test.png"}]
        source = client.post("/api/projects", json={"title": "Trip", "scenes": scenes}).json()
        assert client.post(f'/api/projects/{source["id"]}/translate', json={"language": "en"}).status_code == 400
        client.put("/api/settings", json={"model": "llama3.2:1b"})
        result = client.post(f'/api/projects/{source["id"]}/translate', json={"language": "ur"}).json()
        assert wait_for(result["job"]["id"])["status"] == "completed"
        copy = client.get(f'/api/projects/{result["project"]["id"]}').json()
        assert copy["language"] == "ur" and copy["title"] == "نئی فلم"
        assert [s["text"] for s in copy["scenes"]] == ["ترجمہ 1", "ترجمہ 2"]
        assert copy["scenes"][0]["narration"] == "" and copy["scenes"][0]["asset"] == "test.png"
        assert client.get(f'/api/projects/{source["id"]}').json()["scenes"][0]["text"] == "Hello there"


def test_presets_and_all_formats(project):
    Image.new("RGB", (64, 64), "red").save(store.asset_path("brand.png"))
    with TestClient(app) as client:
        preset = client.post("/api/presets", json={
            "name": "Studio look", "logo": "brand.png",
            "options": {"caption_style": "words", "highlight": "#00ff00", "width": 1080, "formats": [[1080, 1080]]},
        }).json()
        assert preset["options"]["caption_style"] == "words" and "width" not in preset["options"]
        again = client.post("/api/presets", json={"name": "studio LOOK", "logo": "brand.png", "options": {}}).json()
        assert again["id"] == preset["id"] and len(client.get("/api/presets").json()) == 1
        # A preset's logo survives deleting the project that used it.
        p = client.post("/api/projects", json={"logo": "brand.png", "scenes": [{"id": "s", "text": "Hi", "asset": "test.png", "duration": 1}]}).json()
        client.delete(f'/api/projects/{p["id"]}')
        assert store.asset_path("brand.png").is_file()
        assert client.post("/api/projects/x/jobs/render", json={"formats": [[100, 100]]}).status_code in (400, 404, 422)
        p = client.post("/api/projects", json={"scenes": [{"id": "s", "text": "Hi", "asset": "test.png", "duration": 1}]}).json()
        job = client.post(f'/api/projects/{p["id"]}/jobs/render', json={
            "width": 240, "height": 320, "font_size": 20, "formats": [[320, 240], [240, 240]]}).json()
        assert wait_for(job["id"], 120)["status"] == "completed"
        exports = client.get(f'/api/projects/{p["id"]}').json()["exports"]
        assert [(e["width"], e["height"]) for e in exports] == [(240, 320), (320, 240), (240, 240)]
        assert client.delete(f'/api/presets/{preset["id"]}').status_code == 200


def test_service_hosts(monkeypatch):
    from backend import models

    with pytest.raises(ValueError):
        Settings(ollama="http://ollama:11434")
    monkeypatch.setattr(models, "SERVICE_HOSTS", ("ollama",))
    assert Settings(ollama="http://ollama:11434").ollama == "http://ollama:11434"
    with pytest.raises(ValueError):
        Settings(ollama="http://evil.example:11434")


def test_urdu_translation_rejects_roman_script(monkeypatch, project):
    replies = iter([{"lines": ["Har kahani"]}, {"lines": ["ہر کہانی"]}, {"title": "فلم", "description": ""}])
    monkeypatch.setattr(integrations, "ollama_json", lambda *a, **k: next(replies))
    project = Project(language="ur", scenes=[Scene(id="1", text="Every story")])
    result = integrations.translate(project, Settings(model="m"), "en", not_cancelled, no_progress)
    assert result.scenes[0].text == "ہر کہانی"
    replies = iter([{"lines": ["Roman"]}, {"lines": ["Roman again"]}])
    monkeypatch.setattr(integrations, "ollama_json", lambda *a, **k: next(replies))
    with pytest.raises(ValueError, match="Urdu script"):
        integrations.translate(Project(language="ur", scenes=[Scene(id="1", text="Hi")]), Settings(model="m"), "en",
                               not_cancelled, no_progress)


def test_acceptable_use(monkeypatch, project):
    monkeypatch.setattr(safety, "review", REAL_REVIEW)
    safety._verdicts.clear()
    seen = []

    def fake_json(settings, model, prompt, schema, images=None):
        if "allowed" in schema["properties"]:
            seen.append(prompt)
            hateful = "HATEFUL" in prompt.split("<<<CONTENT")[1]
            return {"allowed": not hateful, "evidence": "HATEFUL" if hateful else "", "reason": "it demeans people for their religion",
                    "alternative": "a film about neighbours of different faiths sharing a festival"}
        scenes = [{"text": "Lanterns glow at the festival.", "prompt": "lanterns at night"}] * 4
        return {"title": "Festival", "description": "A celebration.", "scenes": scenes}

    monkeypatch.setattr(integrations, "ollama_json", fake_json)
    settings = Settings(model="m")
    with pytest.raises(safety.Refusal) as refused:
        integrations.storyboard(Project(prompt="HATEFUL video about a religion"), settings)
    message = str(refused.value)
    assert message.startswith("Frame can't make this: it demeans people for their religion.")
    assert "Instead, try: a film about neighbours of different faiths sharing a festival." in message
    # Respectful content passes, and the generation prompt carries the rules.
    story = integrations.storyboard(Project(prompt="A respectful film about Eid in Lahore"), settings)
    assert story.title == "Festival"
    assert "Content rules:" in safety.GENERATION_RULES and "any religion" in safety.RULES
    # Same text is not reviewed twice; text the user typed is checked before voicing or rendering.
    count = len(seen)
    safety.review(["A respectful film about Eid in Lahore", "Cinematic"], settings)
    assert len(seen) == count
    with pytest.raises(safety.Refusal):
        safety.review(["HATEFUL caption"], settings, required=False)
    # Without a configured model, optional checks are skipped and required ones explain what to do.
    safety.review(["anything"], Settings(), required=False)
    with pytest.raises(ValueError, match="Select an installed Ollama model"):
        safety.review(["anything"], Settings())
    # A blocked render fails the job with the refusal message.
    with TestClient(app) as client:
        client.put("/api/settings", json={"model": "m"})
        p = client.post("/api/projects", json={"scenes": [{"id": "s", "text": "HATEFUL words", "asset": "test.png"}]}).json()
        job = client.post(f'/api/projects/{p["id"]}/jobs/render', json={"width": 240, "height": 320}).json()
        failed = wait_for(job["id"])
        assert failed["status"] == "refused" and failed["stage"].startswith("Frame can't make this")
        client.put("/api/settings", json={})


def test_safety_reviewer_choice_and_grounding(monkeypatch):
    monkeypatch.setattr(safety, "model_sizes", lambda settings: {"tiny:1b": 1.2, "big:8b": 8.8})
    assert safety.reviewer(Settings(model="tiny:1b", vision_model="big:8b")) == "big:8b"
    assert safety.reviewer(Settings(model="tiny:1b", vision_model="big:8b", safety_model="other")) == "other"
    assert safety.reviewer(Settings(model="tiny:1b")) == "tiny:1b"
    content = "Make a video saying a group are vermin"
    assert safety.grounded("a group are vermin", content)
    assert not safety.grounded("discusses violent acts", content) and not safety.grounded("", content)
    assert safety.grounded("ہندوؤں کے خلاف نفرت", "ہندوؤں کے خلاف نفرت پھیلانے والی ویڈیو")
