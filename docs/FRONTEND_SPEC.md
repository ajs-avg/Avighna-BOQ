> **Status (2026-10-11):** the auth section below (Supabase) is superseded — the shipped build uses local
> accounts and JWT as described in `API_CONTRACT.md`, which is the authoritative contract. The rest of this
> file (brand, pages, components, quality bar) still describes the delivered frontend.

# Avighna BOQ — Frontend Specification (frontend)

Product: **Avighna BOQ** — "Drop a drawing, get a measurement sheet."
Users drop structural drawings (DWG / DXF / PDF / PNG / JPG). The backend converts, reads,
interprets them with Gemini, runs a deterministic Bar Bending Schedule (BBS) engine and
produces an Excel measurement sheet in Avighna's existing format. The frontend is the
review/approval cockpit.

## Stack (pinned, do not change)
- Next.js 15.5.x (App Router), React 19, TypeScript 5 strict.
- Tailwind CSS v4 (`@import "tailwindcss";` in `app/globals.css`, theme via `@theme`), `postcss.config.mjs` with `@tailwindcss/postcss`.
- `@supabase/ssr` + `@supabase/supabase-js` v2 for auth (email + password only, admin invites).
- `lucide-react` icons, `clsx` + `tailwind-merge` for class merging. No other UI libraries. No shadcn CLI (hand-write components).
- `next/font/google` Inter.
- The developer machine cannot run `npm install` right now, so code must be written carefully and conservatively: standard APIs only, no experimental features, strict TypeScript that will compile on Vercel first try.

## Brand / theme (red & white)
Tokens in `app/globals.css` under `@theme`:
```
--color-brand: #ED1C24;        /* Avighna red */
--color-brand-dark: #C8102E;   /* hover */
--color-brand-soft: #FDECED;   /* tinted backgrounds */
--color-ink: #231F20;          /* primary text */
--color-muted: #6B6B70;
--color-line: #E6E6E9;
--color-surface: #FFFFFF;
--color-surface-2: #F7F7F8;
--color-success: #1F9D55;
--color-warning: #D97706;
--color-danger: #ED1C24;
```
White page background, red used for primary actions, active nav, progress, key totals.
Logo: `public/brand/avighna-logo.svg` (wordmark, 240x39.76 viewBox, already red/black) and
`public/brand/avighna-mark.png` (red square mark). Render the logo with `next/image` or `<img>`.
Header: white, bottom border, logo left, user menu right. Sidebar 240px: Dashboard, New Measurement, Jobs, Standards, Users (admin only).
Cards: 12px radius, 1px line border, subtle shadow. Tables: dense, zebra, sticky header.
Everything must look premium and consistent; seniors will judge it.

## Environment variables
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000      # FastAPI backend (Render in prod)
```

## Auth flow
- `middleware.ts` refreshes the Supabase session cookie and redirects unauthenticated users to `/login` (except `/login`, `/auth/*`, `/set-password`, static assets).
- `/login`: email + password form (Supabase `signInWithPassword`). Error states. Link "Forgot password" → `/forgot-password` (sends `resetPasswordForEmail` with redirect to `/auth/callback?next=/set-password`).
- `/auth/callback/route.ts`: exchanges `code` for session (`exchangeCodeForSession`) then redirects to `next`.
- `/set-password`: for invited users / reset: `updateUser({ password })` then redirect `/`.
- Role comes from `GET {API}/api/v1/me` (returns `UserProfile`). Keep it in a client context after load.
- Every backend call: `Authorization: Bearer <session.access_token>` (get via `supabase.auth.getSession()` on the client).

## Backend API contract (FastAPI, JSON unless noted) — base `${NEXT_PUBLIC_API_URL}`
| Method | Path | Body / Query | Returns |
|---|---|---|---|
| GET | `/healthz` | — | `{status, version, converters:{oda:boolean, libredwg:boolean}, gemini_model}` |
| GET | `/api/v1/me` | — | `UserProfile` |
| POST | `/api/v1/jobs` | multipart form: `files` (1..n), `project_name`, `level`, `contractor?`, `drawn_by?`, `standards?` (JSON string of `Standards`) | `{job_id, status}` |
| GET | `/api/v1/jobs?limit=&offset=` | — | `{items: JobSummaryRecord[], total}` |
| GET | `/api/v1/jobs/{id}` | — | `JobRecord` |
| GET | `/api/v1/jobs/{id}/sheets` | — | `SheetRecord[]` |
| GET | `/api/v1/jobs/{id}/sheets/{sheetId}/preview` | — | image/png (needs bearer; fetch as blob → object URL) |
| PATCH | `/api/v1/jobs/{id}/members/{memberId}` | `{member: Partial<MemberSpec>}` | `JobRecord` (recalculated) |
| POST | `/api/v1/jobs/{id}/members` | `MemberSpec` | `JobRecord` |
| DELETE | `/api/v1/jobs/{id}/members/{memberId}` | — | `JobRecord` |
| POST | `/api/v1/jobs/{id}/recalculate` | `{standards?: Standards}` | `JobRecord` |
| POST | `/api/v1/jobs/{id}/reprocess` | — | `JobRecord` (status back to queued) |
| POST | `/api/v1/jobs/{id}/approve` | — | `JobRecord` (reviewer/admin only) |
| GET | `/api/v1/jobs/{id}/export.xlsx` | — | xlsx file (fetch blob, trigger download) |
| DELETE | `/api/v1/jobs/{id}` | — | 204 |
| GET | `/api/v1/standards` | — | `Standards` |
| PUT | `/api/v1/standards` | `Standards` | `Standards` (admin) |
| GET | `/api/v1/admin/users` | — | `UserProfile[]` (admin) |
| POST | `/api/v1/admin/invite` | `{email, full_name?, role}` | `UserProfile` (admin) |
| PATCH | `/api/v1/admin/users/{id}` | `{role}` | `UserProfile` (admin) |
| DELETE | `/api/v1/admin/users/{id}` | — | 204 (admin) |

Errors: `{detail: string}` with HTTP 4xx/5xx.

## Types (mirror exactly in `lib/types.ts`; source of truth is `backend/app/models/schemas.py`)
```ts
export type JobStatus = 'queued'|'converting'|'analysing'|'extracting'|'quantifying'|'ready'|'approved'|'failed';
export interface Standards { ld_factor:number; anchorage_extra_d:number; cover_beam_mm:number; cover_slab_mm:number; cover_column_mm:number; cover_wall_mm:number; cover_stair_mm:number; hook_length_d:number; stirrup_corners:number; bend_deduction_d:number; min_straight_anchorage_m:number; extra_bar_span_fraction:number; curtail_fraction:number; end_zone_span_fraction:number; stirrup_end_offset_m:number; slab_min_anchorage_m:number; slab_bentup_factor:number; slab_dist_end_fraction:number; slab_cont_edge_fraction:number; sfr_min_depth_m:number; unit_weight_kg_per_m:Record<string,number>; diameters_in_summary:number[]; }
export interface BarGroup { count:number; dia_mm:number; note?:string|null }
export interface StirrupZone { dia_mm:number; spacing_mm:number; zone:'end'|'mid'|'full'; legs:number }
export interface SlabLayer { dia_mm:number; spacing_mm:number; bent_up:boolean; note?:string|null }
export interface ColumnTie { dia_mm:number; spacing_mm:number; kind:'main_ring'|'inner_tie'|'cross_tie'; per_layer:number; leg_length_m?:number|null }
export interface BBox { x0:number; y0:number; x1:number; y1:number; space:'page'|'model' }
interface MemberBase { id:string; tag:string; nos:number; confidence:number; evidence:string[]; source_sheet?:string|null; source_bbox?:BBox|null; remarks?:string|null }
export interface BeamSpec extends MemberBase { kind:'beam'; span_m:number; width_m:number; depth_m:number; bottom_bars:BarGroup[]; top_bars:BarGroup[]; extra_top_left:BarGroup[]; extra_top_right:BarGroup[]; extra_bottom_mid:BarGroup[]; bottom_curtail:BarGroup[]; sfr_bars:BarGroup[]; stirrups:StirrupZone[]; left_support:'end'|'continuous'; right_support:'end'|'continuous' }
export interface SlabSpec extends MemberBase { kind:'slab'; length_m:number; width_m:number; thickness_m:number; short_main?:SlabLayer|null; long_main?:SlabLayer|null; short_top_dist_end?:SlabLayer|null; long_top_dist_end?:SlabLayer|null; short_top_cont_edge?:SlabLayer|null; long_top_cont_edge?:SlabLayer|null; extra_top:SlabLayer[]; one_way:boolean }
export interface ColumnSpec extends MemberBase { kind:'column'; length_m:number; width_m:number; height_m:number; vertical_bars:BarGroup[]; ties:ColumnTie[]; lap_at_floor:boolean; shape:'rectangular'|'L'|'T'|'circular' }
export interface WallSpec extends MemberBase { kind:'wall'; length_m:number; thickness_m:number; height_m:number; vertical?:SlabLayer|null; horizontal?:SlabLayer|null; faces:number; starter_lap:boolean }
export interface StairFlight { name:string; width_m:number; waist_m:number; going_m:number; rise_m:number; landing_a_m:number; landing_b_m:number; main?:SlabLayer|null; dist?:SlabLayer|null }
export interface StairSpec extends MemberBase { kind:'stair'; flights:StairFlight[] }
export type MemberSpec = BeamSpec|SlabSpec|ColumnSpec|WallSpec|StairSpec;
export interface BarRow { seq:number; description:string; dia_mm:number; members:number; bars_per_member:number; total_bars:number; spacing_mm?:number|null; span_m?:number|null; a:number;b:number;c:number;d:number;e:number;f:number;g:number; bend_corners:number; cut_length_m:number; weight_kg:number; formula:string; shape:string }
export interface MemberResult { member_id:string; kind:string; tag:string; nos:number; size_label:string; rows:BarRow[]; weight_kg:number; weight_by_dia_kg:Record<string,number>; confidence:number; warnings:string[] }
export interface CategorySummary { category:string; weight_by_dia_t:Record<string,number>; total_t:number; member_count:number }
export interface BBSSummary { level:string; categories:CategorySummary[]; total_by_dia_t:Record<string,number>; grand_total_t:number }
export interface BBSResult { standards:Standards; members:MemberResult[]; summary:BBSSummary }
export interface SourceFile { name:string; size_bytes:number; format:'dwg'|'dxf'|'pdf'|'image'|'unknown'; storage_path:string; mime:string }
export interface SheetClassification { sheet_type:string; discipline:string; drawing_number?:string|null; title?:string|null; level?:string|null; scale?:string|null; units:string; project?:string|null; relevant_for_bbs:boolean; confidence:number; summary:string }
export interface SheetRecord { id:string; job_id:string; file_name:string; page_no:number; layout:string; classification:SheetClassification; preview_path?:string|null; text_count:number; width:number; height:number; processing_notes:string[] }
export interface JobEvent { at:string; status:JobStatus; message:string; progress:number }
export interface JobRecord { id:string; project_name:string; level:string; contractor?:string|null; work_description:string; drawn_by?:string|null; drawing_refs:string[]; status:JobStatus; progress:number; error?:string|null; standards:Standards; source_files:SourceFile[]; members:MemberSpec[]; result?:BBSResult|null; events:JobEvent[]; created_by?:string|null; created_by_email?:string|null; created_at:string; updated_at:string; approved_by?:string|null; approved_at?:string|null; export_path?:string|null; export_version:number }
export interface JobSummaryRecord { id:string; project_name:string; level:string; status:JobStatus; progress:number; created_at:string; updated_at:string; created_by_email?:string|null; member_count:number; grand_total_t?:number|null; file_names:string[] }
export interface UserProfile { id:string; email:string; full_name?:string|null; role:'engineer'|'reviewer'|'admin'; created_at?:string|null; last_sign_in_at?:string|null }
```

## Pages (App Router)
- `app/layout.tsx` — html/body, Inter font, metadata title "Avighna BOQ".
- `app/(auth)/login/page.tsx`, `app/(auth)/forgot-password/page.tsx`, `app/(auth)/set-password/page.tsx`, `app/auth/callback/route.ts` — centered card on white with red accent bar, logo on top.
- `app/(app)/layout.tsx` — authenticated shell: sidebar + header; loads `/api/v1/me`; provides `useUser()` context (`{profile, session, loading}`).
- `app/(app)/page.tsx` **Dashboard**: stat tiles (Jobs this month, Tons quantified, Awaiting review, Approved), recent jobs table, big red CTA "New measurement".
- `app/(app)/new/page.tsx` **New Measurement**: drag-and-drop zone (multi-file, accepts .dwg .dxf .pdf .png .jpg .jpeg .tif .tiff; shows file chips with detected type by extension and size), fields: Project name (default "Nishika Elysium (Avighna)"), Level (e.g. "14th Floor"), Contractor (default "Mehta Jaising Builders LLP"), Drawn by; collapsible "Standards" panel pre-filled from `GET /api/v1/standards` (LD factor, covers, unit weights table) ; Submit → `POST /api/v1/jobs` with progress → redirect `/jobs/{id}`.
- `app/(app)/jobs/page.tsx` **Jobs**: table with status pill, progress, project, level, files, members, total tons, created by/at; row click → detail; filter by status; delete (admin/owner) with confirm.
- `app/(app)/jobs/[id]/page.tsx` **Job detail** (the heart of the app):
  - Header: project / level / status pill / progress bar / actions: Reprocess, Recalculate, Approve (reviewer/admin, only when `ready`), Download Excel (when `ready` or `approved`).
  - While processing: poll `GET /api/v1/jobs/{id}` every 2.5 s; show vertical timeline of `events` (queued → converting → analysing → extracting → quantifying → ready) with timestamps.
  - Tabs: **Summary** (dia-wise tonnage table per category like the Excel summary: columns 8/10/12/16/20/25/32 mm + total; grand total card in red), **Beams**, **Slabs**, **Columns**, **Walls**, **Staircase**, **Sheets**.
  - Member tabs: table of members (tag, nos, size, bars summary, weight kg, confidence badge: ≥0.85 green "High", ≥0.6 amber "Check", else red "Low"); expand row → bar rows table (Sr, Description, Dia, Members, Bars/member, Total bars, a..g, Bend corners, Cut length, Weight, Formula trace) + an inline **edit form** for the member's inputs (span/width/depth, bar groups editor: count + dia rows with add/remove, stirrup zones editor, support types) → PATCH → table refreshes. "Add member" button opens the same form blank. Delete member.
  - **Sheets** tab: cards per sheet with preview image (fetched with bearer → blob URL), classification (type, drawing no, title, level, scale, confidence), relevance flag, processing notes.
  - Status `failed`: red alert with `error` and a Reprocess button.
- `app/(app)/standards/page.tsx` — view/edit company standards (admin can save via PUT; others read-only). Unit weight table editable.
- `app/(app)/users/page.tsx` — admin only: list users, invite (email, name, role), change role, remove.

## Components (components/)
`Logo`, `AppShell` (sidebar+header), `Button` (variants: primary red, secondary, ghost, danger; sizes), `Card`, `Input`, `Select`, `Badge`, `StatusPill`, `ProgressBar`, `Tabs`, `Table` helpers, `Dropzone`, `Timeline`, `ConfidenceBadge`, `StatTile`, `EmptyState`, `Spinner`, `ConfirmDialog`, `MemberEditor` (per kind), `BarRowsTable`, `SummaryTable`, `Toast` (simple context).

## lib/
- `lib/supabase/client.ts` (`createBrowserClient`), `lib/supabase/server.ts` (`createServerClient` with cookies for RSC/route handlers), `lib/supabase/middleware.ts` (`updateSession`).
- `lib/api.ts`: `apiFetch<T>(path, init)` adds bearer token from the browser client; helpers `getJob`, `listJobs`, `createJob(formData, onProgress)` (XHR for progress), `patchMember`, `addMember`, `deleteMember`, `recalculate`, `approve`, `reprocess`, `downloadExport`, `getSheets`, `getPreviewBlobUrl`, `getStandards`, `putStandards`, `getMe`, `adminListUsers`, `adminInvite`, `adminSetRole`, `adminDeleteUser`.
- `lib/types.ts` as above. `lib/format.ts` (formatTons, formatKg, formatDate, bars summary string like "2-T20 + 2-T16").
- `lib/utils.ts` (`cn`).

## Quality bar
- Mobile responsive (sidebar collapses to a top drawer below 1024px).
- Loading skeletons, empty states, error toasts.
- No `any` leaks; strict TS; all imports resolvable with the pinned deps.
- `package.json` scripts: dev, build, start, lint, typecheck (`tsc --noEmit`).
