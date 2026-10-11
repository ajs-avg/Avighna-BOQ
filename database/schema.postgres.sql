-- Avighna BOQ — PostgreSQL / Supabase schema (applied with CREATE IF NOT EXISTS on every start).
-- Same tables as schema.sql; only the auto-increment id differs.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'engineer',
    password_hash TEXT NOT NULL,
    must_set_password INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_sign_in_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    module TEXT NOT NULL,
    status TEXT NOT NULL,
    project_name TEXT NOT NULL,
    level TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_created_idx ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status);
CREATE INDEX IF NOT EXISTS jobs_module_idx ON jobs(module);

CREATE TABLE IF NOT EXISTS sheets (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sheets_job_idx ON sheets(job_id, seq);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    doc TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    at TEXT NOT NULL,
    user_email TEXT,
    action TEXT NOT NULL,
    target TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS audit_at_idx ON audit_log(at DESC);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
