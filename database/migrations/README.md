# Migrations
Numbered SQL files (`0002_add_x.sql`, …) applied once each, in order, at backend start.
`schema.sql` always describes the full current schema (CREATE IF NOT EXISTS), so a fresh
database never needs the migrations; they exist for databases created by an older build.
