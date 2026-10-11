#!/bin/sh
# Run the backend test suite against an embedded PostgreSQL (pgserver) instead of SQLite.
# Proves the Supabase/Postgres code path without any cloud account.
set -e
cd "$(dirname "$0")/../backend"
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
TEST_POSTGRES=1 PYTHONPATH=. "$PY" -W ignore -m pytest tests -q "$@"
