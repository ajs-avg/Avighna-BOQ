-- Avighna BOQ — SQLite schema (source of truth; applied with CREATE IF NOT EXISTS on every start).
-- Documents (jobs, sheets) are stored as JSON in `doc` so the pydantic models in
-- backend/app/models/schemas.py stay the single definition of their shape.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'engineer',          -- engineer | reviewer | admin
    password_hash TEXT NOT NULL,                     -- bcrypt
    must_set_password INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_sign_in_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    module TEXT NOT NULL,                            -- structural | fitout
    status TEXT NOT NULL,                            -- queued ... ready | approved | failed
    project_name TEXT NOT NULL,
    level TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    doc TEXT NOT NULL                                -- JobRecord JSON
);
CREATE INDEX IF NOT EXISTS jobs_created_idx ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status);
CREATE INDEX IF NOT EXISTS jobs_module_idx ON jobs(module);

CREATE TABLE IF NOT EXISTS sheets (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    doc TEXT NOT NULL                                -- SheetRecord JSON
);
CREATE INDEX IF NOT EXISTS sheets_job_idx ON sheets(job_id, seq);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,                            -- e.g. 'standards'
    doc TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    user_email TEXT,
    action TEXT NOT NULL,                            -- login | job.create | job.approve | member.edit | ...
    target TEXT,                                     -- job id / user id
    detail TEXT                                      -- short free text
);
CREATE INDEX IF NOT EXISTS audit_at_idx ON audit_log(at DESC);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
