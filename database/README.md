# database/
SQLite, zero-admin, one file: `database/boq.db` (created on first backend start, git-ignored).

| File | Purpose |
|---|---|
| `schema.sql` | Full schema, applied on every start (idempotent) |
| `migrations/*.sql` | One-off changes for existing databases, applied in order once |
| `seed/standards.default.json` | Company BBS constants loaded when no standards are saved yet |

Tables: `users`, `jobs` (JobRecord JSON), `sheets` (SheetRecord JSON), `settings`, `audit_log`, `schema_migrations`.
Backup: copy `boq.db` (or use the admin "Download backup" button). Uploads, previews and exports are files
under `backend/data/`, keyed by job id.
