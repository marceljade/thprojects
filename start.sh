#!/usr/bin/env bash
# Start unter Linux/macOS (zum Testen). Unter Windows start.bat verwenden.
cd "$(dirname "$0")/backend"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
