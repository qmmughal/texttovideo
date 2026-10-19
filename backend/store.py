import json, os, sqlite3, uuid
from pathlib import Path

ROOT = Path(os.environ.get('LOCAL_VIDEO_DATA', Path(__file__).resolve().parents[1] / 'data')).resolve()
ROOT.mkdir(parents=True, exist_ok=True)

def connect():
    db = sqlite3.connect(ROOT / 'studio.db', timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))')
    return db

def put(kind, key, value):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?)', (kind,key,json.dumps(value,ensure_ascii=False)))

def get(kind, key):
    with connect() as db:
        row = db.execute('SELECT value FROM documents WHERE kind=? AND id=?',(kind,key)).fetchone()
    if not row: raise KeyError(key)
    return json.loads(row[0])

def all_docs(kind):
    with connect() as db:
        return [json.loads(r[0]) for r in db.execute('SELECT value FROM documents WHERE kind=? ORDER BY rowid DESC',(kind,))]

def uid(): return uuid.uuid4().hex

def asset_path(name):
    if not name or Path(name).name != name or '/' in name or '\\' in name: raise ValueError('Invalid asset name')
    p = (ROOT / name).resolve()
    if p.parent != ROOT: raise ValueError('Invalid asset path')
    return p
