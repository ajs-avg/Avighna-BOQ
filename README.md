# Avighna BOQ

**Drop a drawing, get a measurement sheet.** A red-and-white platform for Avighna Group where engineers upload
construction drawings (DWG / DXF / PDF / images) and receive an audited Excel measurement sheet.

One simple flow: **drop the drawing → measurement sheet → BOQ abstract → material requirement**, in one Excel file.

| Tab | What it holds |
|---|---|
| **Measurement Sheet** | Item-wise blocks (RCC walls, formwork, flooring, skirting, plaster, paint, doors…). Each row is one object from the drawing with Nos × L × B × H; deductions are minus rows per IS 1200; totals are live `=SUM()` formulas |
| **BOQ (Abstract)** | One line per item with a CPWD-style description, quantity linked to the measurement sheet, unit. Rates are left blank on purpose |
| **Material Requirement** | Cement bags, sand, aggregate, steel kg, tiles nos, paint litres… = BOQ qty × consumption norm × wastage, plus a summary by material |
| **Tender vs Site** | Template to compare tender quantities with site measurements |
| **Elements (from drawing)** | The rooms / openings / walls / slabs / members the AI read, with confidence and evidence, for checking |

How it works: files are converted (DWG → DXF), every sheet is read (vector text, dimensions, CAD geometry such as
room outlines, hatch areas and door tags), classified, then Gemini 2.5 Pro reads rooms, openings, walls, slabs,
columns/beams and other items from the image plus the exact machine text. All arithmetic runs in a deterministic
measurement engine (IS 1200 rules, formwork contact areas, steel thumb rules, material norms); reviewers correct
the elements in the UI, recompute, and approve before the Excel is released. The earlier structural BBS and
KR-style fit-out BOQ engines are still in the API for old jobs but are not offered for new ones.

## User guide
The full user & operations guide (roles, step-by-step, Excel tabs, measurement rules, admin, troubleshooting) is in
[docs/Avighna_BOQ_User_Guide.pdf](docs/Avighna_BOQ_User_Guide.pdf) (source: `docs/guide-src/`).

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
sheets are classified by keywords and rooms/doors come from CAD outlines and tags only (sizes shown as
equivalent squares, marked low confidence), so the AI key is strongly recommended.

### DWG conversion
`LibreDWG dwg2dxf` 0.13.4 is used (built from source at `~/.local/opt/libredwg-0.13.4` on the Mac, built in the
Docker image on Render); it converts every AutoCAD-2024 file of the reference packages. Its DXF output needs two
fixes the backend applies automatically: sort tables ezdxf rejects are stripped, and layers written as "off"
(negative colour) are switched on, otherwise nothing renders. When a DWG still cannot be converted, the job
keeps going with the other files and reports the skipped file; upload the PDF plot or a DXF export instead.

## Samples and demos
- The Dubai office package in `~/Downloads/20250930 Detail Design Submission R1/` is the reference: upload the
  `Drawing Package/cad/.../KR-AGO-ID-GA-100`, `GA-103` and `DS-601-602` DWGs (or pages of the DD PDF) as one job.
- `samples/sample_beam_schedule_14th_floor.pdf` — a synthetic beam + column schedule (old structural module;
  regenerate with `python3 tools/make_sample_structural_pdf.py`).

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
