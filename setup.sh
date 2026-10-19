#!/usr/bin/env sh
# Setup for Linux and macOS. Needs Python 3.11+ and Node.js 22+ (Node only to build the web interface).
set -eu
cd "$(dirname "$0")"

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "Python 3.11 or newer was not found. Install it (e.g. sudo apt install python3.12-venv, or brew install python) and run setup again." >&2
    exit 1
fi

[ -x .venv/bin/python ] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade --disable-pip-version-check -r backend/requirements.txt

if [ -f frontend/package.json ] && command -v npm >/dev/null 2>&1; then
    (cd frontend && npm ci && npm run build)
elif [ ! -f frontend/out/index.html ]; then
    echo "Node.js 22+ is needed to build the web interface. Install it from https://nodejs.org and run setup again." >&2
    exit 1
fi

.venv/bin/python -m scripts.sample
echo "Setup complete. Run ./start.sh"
