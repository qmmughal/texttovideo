import json
import os
import sqlite3
import uuid
from pathlib import Path

ROOT = Path(os.environ.get("LOCAL_VIDEO_DATA", Path(__file__).resolve().parents[1] / "data")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)


def connect():
    db = sqlite3.connect(ROOT / "studio.db", timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))")
    return db


def put(kind, key, value):
    with connect() as db:
        db.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?)",
            (kind, key, json.dumps(value, ensure_ascii=False)),
        )


def get(kind, key):
    with connect() as db:
        row = db.execute("SELECT value FROM documents WHERE kind=? AND id=?", (kind, key)).fetchone()
    if not row:
        raise KeyError(key)
    return json.loads(row[0])


def delete(kind, key):
    with connect() as db:
        db.execute("DELETE FROM documents WHERE kind=? AND id=?", (kind, key))


def all_docs(kind):
    with connect() as db:
        rows = db.execute("SELECT value FROM documents WHERE kind=? ORDER BY rowid DESC", (kind,))
        return [json.loads(row[0]) for row in rows]


def uid():
    return uuid.uuid4().hex


def asset_path(name):
    if not name or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Invalid asset name")
    path = (ROOT / name).resolve()
    if path.parent != ROOT:
        raise ValueError("Invalid asset path")
    return path


def project_assets(project):
    """Every asset file name a stored project document refers to."""
    names = {project.get("music", ""), project.get("logo", "")}
    for scene in project.get("scenes", []):
        names.update((scene.get("asset", ""), scene.get("narration", "")))
    for output in project.get("exports", []):
        names.update((output.get("asset", ""), output.get("srt", "")))
    return {name for name in names if name}
