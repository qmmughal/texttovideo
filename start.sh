#!/usr/bin/env sh
# Start Frame on Linux or macOS. Use --dev for the hot-reloading frontend on port 3000.
set -eu
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run ./setup.sh first." >&2; exit 1; }

if [ "${1:-}" = "--dev" ]; then
    .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
    BACKEND=$!
    trap 'kill $BACKEND 2>/dev/null' EXIT INT TERM
    echo "Open http://127.0.0.1:3000 — press Ctrl+C to stop."
    (cd frontend && npm run dev)
    exit 0
fi

[ -f frontend/out/index.html ] || { echo "The web interface is not built. Run ./setup.sh again." >&2; exit 1; }
URL=http://127.0.0.1:8000
echo "Frame is starting at $URL — press Ctrl+C to stop."
(
    for _ in $(seq 1 60); do
        if curl -fs "$URL/api/settings" >/dev/null 2>&1; then
            if command -v open >/dev/null 2>&1; then open "$URL"; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"; fi
            exit 0
        fi
        sleep 1
    done
) &
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
