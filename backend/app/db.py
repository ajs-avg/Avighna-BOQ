"""Database layer: SQLite (local, zero-admin) or PostgreSQL / Supabase (DATABASE_URL set).

The rest of the app writes SQLite-style SQL with ``?`` placeholders; this module translates it
for Postgres (``%s``), returns rows as dict-like objects for both engines, and loads the matching
schema file from database/ on start.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.config import get_settings

_lock = threading.RLock()
_conn: Any = None
_backend: str = "sqlite"


def backend() -> str:
    """'sqlite' or 'postgres' (decided by DATABASE_URL)."""
    return "postgres" if get_settings().database_url.startswith(("postgres://", "postgresql://")) else "sqlite"


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ----------------------------------------------------------------------------- schema
FALLBACK_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, full_name TEXT,
  role TEXT NOT NULL DEFAULT 'engineer', password_hash TEXT NOT NULL, must_set_password INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, last_sign_in_at TEXT);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, module TEXT NOT NULL, status TEXT NOT NULL, project_name TEXT NOT NULL,
  level TEXT NOT NULL, created_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sheets (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, seq INTEGER NOT NULL, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, doc TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, user_email TEXT,
  action TEXT NOT NULL, target TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
"""


def _schema_sql() -> str:
    name = "schema.postgres.sql" if backend() == "postgres" else "schema.sql"
    path = get_settings().database_dir / name
    if path.exists():
        return path.read_text()
    if backend() == "postgres":
        return FALLBACK_SCHEMA_SQLITE.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    return FALLBACK_SCHEMA_SQLITE


def _split_statements(script: str) -> List[str]:
    """Split an SQL script into statements (drops -- comments; good enough for our DDL)."""
    cleaned = "\n".join(line for line in script.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def _translate(sql: str) -> str:
    return sql.replace("?", "%s") if backend() == "postgres" else sql


# ----------------------------------------------------------------------------- connection
def connect() -> Any:
    global _conn, _backend
    with _lock:
        if _conn is not None:
            return _conn
        _backend = backend()
        if _backend == "postgres":
            import psycopg
            from psycopg.rows import dict_row
            conn = psycopg.connect(get_settings().database_url, row_factory=dict_row, autocommit=True)
            for stmt in _split_statements(_schema_sql()):
                conn.execute(stmt)
        else:
            path: Path = get_settings().db_path
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_schema_sql())
        _conn = conn
        _apply_migrations()
        return _conn


def _apply_migrations() -> None:
    mig_dir = get_settings().database_dir / "migrations"
    if not mig_dir.exists():
        return
    suffix = ".postgres.sql" if backend() == "postgres" else ".sql"
    done = {r["version"] for r in query("SELECT version FROM schema_migrations")}
    for f in sorted(mig_dir.glob("*.sql")):
        if f.name.endswith(".postgres.sql") != (suffix == ".postgres.sql"):
            continue
        version = f.name[: -len(suffix)]
        if version in done:
            continue
        with tx() as conn:
            if backend() == "postgres":
                for stmt in _split_statements(f.read_text()):
                    conn.execute(stmt)
            else:
                conn.executescript(f.read_text())
            conn.execute(_translate("INSERT INTO schema_migrations(version, applied_at) VALUES(?,?)"), (version, now_iso()))


class _Tx:
    """Thin wrapper so callers can keep writing conn.execute(sql_with_?, params)."""

    def __init__(self, raw: Any):
        self._raw = raw

    def execute(self, sql: str, params: Tuple = ()) -> Any:
        return self._raw.execute(_translate(sql), params)

    def executescript(self, script: str) -> None:
        if backend() == "postgres":
            for stmt in _split_statements(script):
                self._raw.execute(stmt)
        else:
            self._raw.executescript(script)


@contextmanager
def tx() -> Iterator[_Tx]:
    """Serialised write transaction (one writer at a time keeps SQLite happy; harmless on Postgres)."""
    conn = connect()
    with _lock:
        if backend() == "postgres":
            with conn.transaction():
                yield _Tx(conn)
        else:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield _Tx(conn)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise


def _reconnect() -> Any:
    global _conn
    with _lock:
        try:
            if _conn is not None:
                _conn.close()
        except Exception:
            pass
        _conn = None
    return connect()


def query(sql: str, params: Tuple = ()) -> List[Any]:
    conn = connect()
    for attempt in (1, 2):
        try:
            with _lock:
                cur = conn.execute(_translate(sql), params)
                return list(cur.fetchall())
        except Exception as exc:  # dropped pooled connection (Supabase idles them out) -> reconnect once
            if attempt == 2 or backend() != "postgres" or "closed" not in str(exc).lower() and "connection" not in str(exc).lower():
                raise
            conn = _reconnect()
    return []


def query_one(sql: str, params: Tuple = ()) -> Optional[Any]:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: Tuple = ()) -> None:
    with tx() as conn:
        conn.execute(sql, params)


def get_setting(key: str) -> Optional[Dict[str, Any]]:
    row = query_one("SELECT doc FROM settings WHERE key=?", (key,))
    return json.loads(row["doc"]) if row else None


def put_setting(key: str, doc: Dict[str, Any]) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO settings(key, doc, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET doc=excluded.doc, updated_at=excluded.updated_at",
            (key, json.dumps(doc), now_iso()),
        )


def audit(action: str, user_email: Optional[str], target: Optional[str] = None, detail: Optional[str] = None) -> None:
    """Append-only audit trail (who did what, when)."""
    try:
        with tx() as conn:
            conn.execute("INSERT INTO audit_log(at, user_email, action, target, detail) VALUES(?,?,?,?,?)",
                         (now_iso(), user_email, action, target, (detail or "")[:500]))
    except Exception:  # never let auditing break a request
        pass


def recent_audit(limit: int = 100) -> List[Dict[str, Any]]:
    return [dict(r) for r in query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]


def export_snapshot(out_path: Path) -> Path:
    """Consistent backup: SQLite -> copy via the online backup API; Postgres -> JSON dump of all tables."""
    conn = connect()
    if backend() == "sqlite":
        dst = sqlite3.connect(str(out_path))
        with _lock, dst:
            conn.backup(dst)
        dst.close()
        return out_path
    dump: Dict[str, List[Dict[str, Any]]] = {}
    for table in ("users", "jobs", "sheets", "settings", "audit_log", "schema_migrations"):
        dump[table] = [dict(r) for r in query(f"SELECT * FROM {table}")]
    out_path = out_path.with_suffix(".json")
    out_path.write_text(json.dumps(dump, default=str))
    return out_path


def reset_for_tests(path: Optional[Path] = None) -> None:  # pragma: no cover - test helper
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
