"""Word timings for word-synced captions.

Timings come from, in order of precision: Windows speech (exact, recorded while speaking),
faster-whisper alignment of the narration audio, or an estimate spread over the scene.
Every timing is relative to the start of the scene's narration.
"""

import difflib
import re
import threading

from .store import ROOT

WHISPER_DIR = ROOT / "models" / "whisper"
SENTENCE_END = ".!?۔؟"
_models = {}
_model_lock = threading.Lock()


def normalize(word):
    return re.sub(r"[^\w]", "", word.lower())


def estimate(text, duration):
    """Spread words over the duration in proportion to their length."""
    words = text.split()
    total = sum(len(w) + 1 for w in words) or 1
    timed, start = [], 0.0
    for word in words:
        end = start + duration * (len(word) + 1) / total
        timed.append({"text": word, "start": round(start, 3), "end": round(end, 3)})
        start = end
    return timed


def align(script, recognized):
    """Keep the script's spelling but take timings from recognized words.

    Script words without a recognized match get times interpolated from their neighbours.
    """
    words = script.split()
    if not words:
        return [dict(w) for w in recognized]
    if not recognized:
        return []
    timed = [None] * len(words)
    matcher = difflib.SequenceMatcher(
        a=[normalize(w) for w in words], b=[normalize(w["text"]) for w in recognized], autojunk=False
    )
    for a, b, size in matcher.get_matching_blocks():
        for i in range(size):
            timed[a + i] = (recognized[b + i]["start"], recognized[b + i]["end"])
    start_all, end_all = recognized[0]["start"], recognized[-1]["end"]
    index = 0
    while index < len(words):
        if timed[index]:
            index += 1
            continue
        gap_end = index
        while gap_end < len(words) and not timed[gap_end]:
            gap_end += 1
        left = timed[index - 1][1] if index else start_all
        right = timed[gap_end][0] if gap_end < len(words) else end_all
        right = max(right, left)
        span = (right - left) / (gap_end - index)
        for k in range(index, gap_end):
            timed[k] = (left + span * (k - index), left + span * (k - index + 1))
        index = gap_end
    return [{"text": w, "start": round(s, 3), "end": round(e, 3)} for w, (s, e) in zip(words, timed)]


def whisper_available():
    import importlib.util

    return importlib.util.find_spec("faster_whisper") is not None


def whisper_model(size):
    from faster_whisper import WhisperModel

    with _model_lock:
        if size not in _models:
            _models.clear()
            WHISPER_DIR.mkdir(parents=True, exist_ok=True)
            _models[size] = WhisperModel(size, device="cpu", compute_type="int8", download_root=str(WHISPER_DIR))
        return _models[size]


def whisper_downloaded(size):
    return any(WHISPER_DIR.glob(f"models--Systran--faster-whisper-{size}/snapshots/*/model.bin"))


def load_audio(path):
    """Decode to 16 kHz mono float samples with the bundled FFmpeg, the format Whisper expects."""
    import subprocess

    import numpy

    from .media import FFMPEG

    result = subprocess.run(
        [FFMPEG, "-v", "error", "-protocol_whitelist", "file,pipe", "-i", str(path),
         "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, timeout=600,
    )
    if result.returncode:
        raise RuntimeError("Could not read narration audio: " + result.stderr.decode(errors="replace")[-500:])
    return numpy.frombuffer(result.stdout, numpy.float32)


def transcribe(path, language, size="base"):
    if not whisper_available():
        raise ValueError("Word timing for uploaded or Piper narration needs faster-whisper. Run setup again.")
    audio = load_audio(path)
    segments, _ = whisper_model(size).transcribe(audio, language=language, word_timestamps=True, vad_filter=False)
    return [
        {"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
        for segment in segments
        for w in (segment.words or [])
        if w.word.strip()
    ]


def phrases(words, max_chars=22, max_words=5, pause=0.45):
    """Group timed words into short on-screen phrases, breaking at sentence ends and pauses."""
    groups, current = [], []
    for index, word in enumerate(words):
        current.append(word)
        text = " ".join(w["text"] for w in current)
        following = words[index + 1] if index + 1 < len(words) else None
        next_text = f"{text} {following['text']}" if following else text
        if (
            not following
            or word["text"][-1] in SENTENCE_END + ",،"
            or len(current) >= max_words
            or len(next_text) > max_chars
            or following["start"] - word["end"] > pause
        ):
            groups.append(current)
            current = []
    return groups
