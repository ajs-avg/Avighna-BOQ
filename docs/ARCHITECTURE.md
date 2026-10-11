# Avighna BOQ — Architecture

```
BOQ/
├── frontend/   Next.js 15 app (React 19, Tailwind v4). Talks only to the backend REST API.
├── backend/    FastAPI app (Python 3.9+). Auth, jobs, drawing readers, engines, Excel export.
│   ├── app/
│   │   ├── main.py          REST endpoints (see docs/API_CONTRACT.md)
│   │   ├── auth.py          bcrypt passwords, JWT tokens, role guards, first-admin bootstrap
│   │   ├── config.py        settings from .env (paths, Gemini, converters, limits)
│   │   ├── db.py            SQLite connection, schema/migrations loader, audit log
│   │   ├── repository.py    typed access to jobs / sheets / users / standards
│   │   ├── pipeline.py      job stages: convert → read → classify → extract → quantify
│   │   ├── extract/         format detection, DWG→DXF, DXF/PDF/image readers, CAD geometry
│   │   │                    measurer (hatch areas, leaders, tag counts), schedule-table rebuild,
│   │   │                    regex callouts, heuristic (no-AI) readers, isolated DXF renderer
│   │   ├── ai/              Gemini client (auto model pick, strict JSON), prompts, mappers
│   │   ├── engine/          deterministic maths: beam / slab / column / wall / stair BBS, BOQ
│   │   ├── export/          Excel writers (BBS replica of Avighna's sheet, KR-style BOQ)
│   │   └── models/          pydantic schemas = the single data contract
│   ├── tests/               pytest (API, engines vs reference sheet, CAD measurer, Excel, AI path)
│   └── data/                runtime files: uploads/, work/, previews/, exports/, logs/ (git-ignored)
├── database/   SQLite file (boq.db), schema.sql, migrations/, seed/ — see database/README.md
├── docs/       API_CONTRACT.md (types + endpoints), FRONTEND_SPEC.md, this file
├── samples/    sample drawings for demos/tests
├── tools/      helper scripts (sample generator)
└── brand/      Avighna logo assets
```

## Request flow
1. User signs in (`POST /auth/login`) → JWT in `Authorization: Bearer`.
2. User drops files on **New Measurement** → `POST /jobs` (multipart). Files are saved under
   `backend/data/uploads/<job>/`, a `JobRecord` is stored, and the job is queued on a thread pool.
3. The UI polls `GET /jobs/{id}` every 2.5 s and shows the event timeline.
4. When `ready`, reviewers edit members/items (`PATCH`), the engine recalculates instantly, a
   reviewer approves (`POST /approve`) or sends back with a reason (`POST /reject`), and anyone
   downloads the Excel (`GET /export.xlsx`). Every sensitive action lands in `audit_log`.

## Pipeline stages (backend/app/pipeline.py)
| Stage | What happens | Where |
|---|---|---|
| converting | detect real format from bytes; DWG → DXF via LibreDWG 0.13.4 (several builds tried); the DXF is sanitised (sort tables stripped, all-off layers switched on) | extract/detect.py, extract/dwg_convert.py |
| analysing | read every sheet into a text inventory (exact vector text + coordinates), render a preview PNG (DXF in an isolated subprocess), classify (Gemini fast model, else keyword heuristic) | extract/pdf_reader.py, dxf_reader.py, render_cli.py, heuristics.py |
| extracting | **measurement (default)**: per sheet, deterministic CAD facts (room outlines with area/perimeter, hatch areas with finish codes, door/window tag counts, polyline lengths) + the exact vector text go to Gemini pro with the preview image → `MeasurementExtraction` (rooms, openings, walls, slabs, columns/beams, misc items, assumptions, each with confidence + evidence); sheets are merged (dedupe by tag + level). If a preview failed the model still reads text-only; if the model fails the CAD-outline fallback is used and a visible job event says so. Old modules: **structural** → `BeamSpec`…, **fit-out** → `FitoutItem`/`RoomRecord` | ai/prompts.py (`measurement_prompt`), ai/mappers.py, extract/fitout_geometry.py, heuristics.py |
| quantifying | deterministic engines. Measurement: `engine/measurement.py` builds item-wise blocks (one row per drawing object, Nos × L × B × H, IS 1200 deductions as minus rows: plaster openings ≤0.5 none / 0.5–3 one face / >3 both faces + jambs, skirting minus doors, formwork contact areas, slab over beams, steel thumb rules), the BOQ abstract (one line per item, rate blank) and the material requirement (qty × norm × wastage). Old: BBS rows or KR-style BOQ | engine/* |
| ready | result stored; export generated on demand and cached per version. Measurement workbook: Measurement Sheet, BOQ (Abstract), Material Requirement, Tender vs Site, Elements (from drawing) — live `=C*D*E*F` and `=SUM()` formulas | export/measurement_xlsx.py, export/* |

## Design rules
- The AI never does arithmetic that matters; it reads sheets into structured facts with evidence and
  confidence. All quantities come from the engines, which mirror Avighna's Excel formulas.
- Vector text from PDF/DXF is passed to the model so digits are exact; images are for layout.
- Everything the model or engine decides is traceable: evidence strings, formula traces, audit tabs
  in the Excel, event timeline, audit_log table.
- Local-first: one Mac runs everything; no cloud except the optional Gemini API.
