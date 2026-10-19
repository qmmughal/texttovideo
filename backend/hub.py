"""Resumable, cancellable downloads of model repositories from Hugging Face into data/models."""

import re
import time

import httpx

from .store import ROOT

MODELS_DIR = ROOT / "models"
HF = "https://huggingface.co"
RETRIES = 6


def folder_for(repo):
    return MODELS_DIR / re.sub(r"[^A-Za-z0-9_.-]", "_", repo)


def is_downloaded(repo):
    return (folder_for(repo) / ".complete").is_file()


def download(repo, label, cancelled, progress, skip=(), client=None):
    """Fetch every file of a repository, skipping files already complete and paths starting with `skip`."""
    folder = folder_for(repo)
    folder.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(60, read=300), trust_env=True, follow_redirects=True)
    try:
        listing = client.get(f"{HF}/api/models/{repo}/tree/main", params={"recursive": "true"})
        listing.raise_for_status()
        skip = (".", *skip)
        files = [f for f in listing.json() if f["type"] == "file" and not f["path"].startswith(skip)]
        total = sum(f.get("size", 0) for f in files) or 1
        done = 0
        for file in files:
            target = (folder / file["path"]).resolve()
            if folder.resolve() not in target.parents:
                raise ValueError("Unsafe file path in model repository")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file() and target.stat().st_size == file.get("size"):
                done += file.get("size", 0)
                continue
            partial = target.with_name(target.name + ".part")
            url = f"{HF}/{repo}/resolve/main/{file['path']}"
            for attempt in range(RETRIES):
                have = partial.stat().st_size if partial.is_file() else 0
                try:
                    headers = {"Range": f"bytes={have}-"} if have else {}
                    with client.stream("GET", url, headers=headers) as response:
                        response.raise_for_status()
                        resumed = response.status_code == 206
                        done += have if resumed else 0
                        with partial.open("ab" if resumed else "wb") as out:
                            for chunk in response.iter_bytes(1024 * 1024):
                                if cancelled():
                                    raise RuntimeError("Cancelled. Downloaded files are kept and the next attempt resumes.")
                                out.write(chunk)
                                done += len(chunk)
                                progress(f"Downloading {label} · {done / 1024**3:.2f} of {total / 1024**3:.2f} GB",
                                         min(done / total * 100, 99.9))
                    break
                except httpx.TransportError:
                    # Connections drop on slow networks; resume from what arrived instead of failing the job.
                    done -= partial.stat().st_size if partial.is_file() else 0
                    if attempt == RETRIES - 1:
                        raise
                    progress(f"Connection dropped, resuming {label} (attempt {attempt + 2} of {RETRIES})", None)
                    time.sleep(min(2**attempt, 20))
            partial.replace(target)
        (folder / ".complete").write_text(repo, encoding="utf-8")
    finally:
        if own_client:
            client.close()
