# Avighna BOQ

**Drop a drawing, get a measurement sheet.** A red-and-white platform for Avighna Group where engineers upload
construction drawings (DWG / DXF / PDF / images) and receive an audited Excel measurement sheet.

Two modules on one platform:

| Module | Input | Output |
|---|---|---|
| **Structural** | RC drawings (beam / column / slab schedules, framing plans) | Bar Bending Schedule in Avighna's own sheet layout, dia-wise tonnage summary, live Excel formulas |
| **Interior fit-out** | ID drawings (finishes plans, RCP, joinery details, FF&E / lighting plans) | Bill of Quantities in the KR-style DIV-09 / DIV-13 / FF&E layout with a measurement back-up tab |

How it works: files are converted (DWG → DXF), every sheet is read (vector text, tables, CAD geometry),
classified, then read into structured members / items (Gemini vision with the exact machine text, or a
deterministic fallback when AI is off). All arithmetic runs in a deterministic engine that mirrors the
company's Excel formulas; reviewers correct inputs in the UI and approve before the Excel is released.

## Repository
```
frontend/   Next.js 15 web app (React 19, Tailwind v4)
backend/    FastAPI API: auth, jobs, drawing readers, engines, Excel export
database/   SQLite file + schema.sql + migrations + seed (see database/README.md)
docs/       ARCHITECTURE.md, API_CONTRACT.md (shared types + endpoints), FRONTEND_SPEC.md
samples/    sample drawings        tools/  helper scripts        brand/  Avighna logo assets
```

## Run locally (this Mac)
One command for both servers:
```bash
tools/dev.sh
```
Or separately. Backend (first time: create the uv virtual environment, then run):
```bash
cd backend && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
```
```bash
cd backend && ./run.sh
```
Frontend (deps already installed):
```bash
cd frontend && npm run dev
```
Open http://localhost:3000 and sign in with the first admin from `backend/.env` (`BOOTSTRAP_ADMIN_EMAIL` /
`BOOTSTRAP_ADMIN_PASSWORD`); you are asked to set a new password on first login. Admins invite other users
from the Users page (a temporary password is shown once).

Add `GEMINI_API_KEY=...` to `backend/.env` to turn on AI reading of sheets. Without it the app still runs:
sheets are classified by keywords, fit-out quantities come from CAD geometry only, and structural members
are read from schedule text where the tag, size and bars sit on one line.

### DWG conversion
`LibreDWG dwg2dxf` is used locally (`/opt/anaconda3/envs/dwgtools/bin/dwg2dxf`, installed via conda). It reads
most plans but fails on some AutoCAD 2024 files (joinery details, elevations). ODA File Converter is the
robust option but needs macOS 13+; this machine runs macOS 12. When a DWG cannot be converted, the job keeps
going with the other files and reports the skipped file; upload the PDF plot or a DXF export instead.

## Samples and demos
- `samples/sample_beam_schedule_14th_floor.pdf` — a synthetic beam + column schedule in Avighna's notation
  (regenerate with `python3 tools/make_sample_structural_pdf.py`). Upload it as a Structural job to see the BBS flow.
- The Dubai office package in `~/Downloads/20250930 Detail Design Submission R1/` is the fit-out reference: upload the
  `Drawing Package/cad/.../KR-AGO-ID-GA-10x` DWGs (plus `Xref_Base Plan.dwg`) and/or pages of the DD PDF as a Fit-out job.

## Deploy (Vercel + Render + Supabase)
Cloud mode is switched on by environment variables only: `DATABASE_URL` (Supabase Postgres),
`STORAGE_BACKEND=supabase` (files in Supabase Storage) and `CORS_ORIGINS` (your Vercel URL).
`render.yaml` + `Dockerfile` (repo root) deploy the API on Render; the frontend deploys on Vercel with
root directory `frontend`. Step by step: [docs/DEPLOY.md](docs/DEPLOY.md).

## Tests
```bash
cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests -q   # 38 tests: API, engines vs reference sheet, CAD measurer, Excel writers, AI path (fake client)
cd frontend && npm run typecheck && npm run lint && npm run build
tools/test_postgres.sh        # same suite on an embedded PostgreSQL (Supabase code path)
```
Engine regression tests are pinned to Avighna's own 14th-floor sheet (stirrup counts, cut lengths and weights match) and
to the consultant's Dubai BOQ (floor-finish areas measured from the DXF within 2%).
