#!/bin/sh
# Start backend (port 8000) and frontend (port 3000) together for local use.
# Usage: tools/dev.sh        (Ctrl+C stops both)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/backend/data/logs"
cd "$ROOT/backend" && [ -f .env ] || cp .env.example .env
( cd "$ROOT/backend" && exec ./run.sh ) &
API_PID=$!
( cd "$ROOT/frontend" && exec npm run dev ) &
WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null' INT TERM EXIT
echo "Avighna BOQ: API http://localhost:8000  |  Web http://localhost:3000  (Ctrl+C to stop)"
wait
