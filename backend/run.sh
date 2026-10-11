#!/bin/sh
# Start the Avighna BOQ API locally. Prefers the uv virtual environment in backend/.venv when present.
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
mkdir -p data/logs
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec env PYTHONPATH=. PYTHONWARNINGS=ignore "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" "$@"
