# Avighna BOQ — API contract (v1, local-first build)

Base URL: `${NEXT_PUBLIC_API_URL}` (default `http://localhost:8000`). JSON unless noted.
Auth: local accounts. `POST /api/v1/auth/login` returns a JWT; send `Authorization: Bearer <token>` on every other call.
Errors: `{ "detail": string }` with 4xx/5xx. 401 = not logged in, 403 = role not allowed.

## Modules
Every job has `module`: `"structural"` (RCC drawings → Bar Bending Schedule, output in tons) or
`"fitout"` (interior design drawings → Bill of Quantities, output in m² / lm / nos).
Result fields differ: structural fills `members` + `result` (BBSResult); fit-out fills `fitout_items` + `rooms` + `boq` (BOQResult).


## Measurement module (THE product — default `module: "measurement"`)
Drawing → elements (rooms, openings, walls, slabs, members, misc) → measurement sheet blocks (IS 1200) → BOQ abstract → materials.
`JobRecord.elements: MeasurementExtraction` (what was read; editable) and `JobRecord.measurement: MeasurementResult` (computed).
| Method | Path | Body | Returns | Role |
|---|---|---|---|---|
| PUT | `/api/v1/jobs/{id}/elements` | `{elements: MeasurementExtraction}` (whole set after edits) | `JobRecord` (recomputed) | any (job must be ready/approved/failed) |

```ts
export type WallType = 'rcc'|'block'|'partition'|'glass'|'other';
export type OpeningKind = 'door'|'window'|'opening'|'ventilator';
interface ElBase { id:string; confidence:number; evidence:string[]; source_sheet?:string|null }
export interface RoomEl extends ElBase { name:string; level:string; length_m:number; width_m:number; height_m:number; area_m2?:number|null; perimeter_m?:number|null; floor_finish:string; wall_finish:string; ceiling_finish:string; skirting_mm:number; dado_height_m:number; wet_area:boolean; plastered:boolean; remarks?:string|null }
export interface OpeningEl extends ElBase { tag:string; kind:OpeningKind; width_m:number; height_m:number; count:number; room:string; wall_tag:string; description:string; level:string }
export interface WallEl extends ElBase { tag:string; wall_type:WallType; length_m:number; thickness_m:number; height_m:number; count:number; room:string; level:string; both_faces:boolean }
export interface SlabEl extends ElBase { tag:string; length_m:number; width_m:number; thickness_m:number; count:number; level:string; beam_width_m:number }
export interface MemberEl extends ElBase { tag:string; kind:'column'|'beam'; width_m:number; depth_m:number; length_m:number; count:number; level:string; slab_thickness_m:number }
export interface MiscEl extends ElBase { tag?:string|null; description:string; unit:'nos'|'sqm'|'rmt'|'cum'|'kg'|'LS'; qty:number; trade:string; room:string; level:string }
export interface ProjectAssumptions { floor_height_m:number; wall_thickness_m:number; slab_thickness_m:number; construction:'mivan'|'conventional'; concrete_grade:string; notes:string[] }
export interface MeasurementExtraction { rooms:RoomEl[]; openings:OpeningEl[]; walls:WallEl[]; slabs:SlabEl[]; members:MemberEl[]; misc:MiscEl[]; assumptions:ProjectAssumptions; warnings:string[] }
export interface MeasurementRow { sr:number; location:string; nos:number; l_m?:number|null; b_m?:number|null; h_m?:number|null; qty:number; deduction:boolean; rule:string; element_id?:string|null }
export interface MeasurementBlock { item_code:string; item_title:string; unit:string; trade:string; rows:MeasurementRow[]; total:number }
export interface BOQAbstractLine { item_no:number; item_code:string; trade:string; description:string; unit:string; qty:number; rate?:number|null; amount?:number|null; basis:'measured'|'thumb_rule'|'manual' }
export interface MaterialRow { material:string; for_item_code:string; boq_qty:number; boq_unit:string; norm:number; norm_unit:string; wastage_pct:number; required:number; basis:string }
export interface MeasurementResult { blocks:MeasurementBlock[]; boq:BOQAbstractLine[]; materials:MaterialRow[]; totals_by_trade:Record<string,Record<string,number>>; warnings:string[] }
// JobRecord gains: module:'measurement'|'structural'|'fitout'; elements?:MeasurementExtraction|null; measurement?:MeasurementResult|null
// POST /api/v1/jobs: `module` defaults to "measurement"; fields project_name, level (floor/wing), location?, contractor?, drawn_by?
```
Measurement rows are computed from elements only (never typed directly); to change a quantity the user edits the element (room size, opening, wall) or adds a `MiscEl` row.

## Endpoints
| Method | Path | Body / Query | Returns | Role |
|---|---|---|---|---|
| GET | `/healthz` | — | `{status, version, converters:{oda:boolean, libredwg:boolean}, ai: AIStatus}` | public |
| POST | `/api/v1/auth/login` | `LoginRequest` | `TokenResponse` | public |
| POST | `/api/v1/auth/set-password` | `SetPasswordRequest` | `UserProfile` | any (clears `must_set_password`) |
| GET | `/api/v1/me` | — | `UserProfile` | any |
| GET | `/api/v1/ai/status` | — | `AIStatus` | any |
| GET | `/api/v1/stats` | — | `{jobs_total, jobs_this_month, steel_t, boq_lines, awaiting_review, approved, failed}` | any |
| GET | `/api/v1/system` | — | `SystemInfo` (version, ai, converters, libredwg_bin, db/data paths + sizes, stats, users) | any |
| POST | `/api/v1/jobs` | multipart: `files` (1..n), `module`, `project_name`, `level`, `contractor?`, `drawn_by?`, `location?`, `currency?` (fit-out, default AED), `standards?` (JSON string) | `{job_id, status}` | any |
| GET | `/api/v1/jobs?limit=&offset=&module=&status=` | — | `{items: JobSummaryRecord[], total}` | any |
| GET | `/api/v1/jobs/{id}` | — | `JobRecord` | any |
| GET | `/api/v1/jobs/{id}/sheets` | — | `SheetRecord[]` | any |
| GET | `/api/v1/jobs/{id}/sheets/{sheetId}/preview` | — | image/png (bearer required; fetch as blob) | any |
| PATCH | `/api/v1/jobs/{id}/members/{memberId}` | `{member: Partial<MemberSpec>}` | `JobRecord` (recalculated) | any (structural) |
| POST | `/api/v1/jobs/{id}/members` | `MemberSpec` | `JobRecord` | any |
| DELETE | `/api/v1/jobs/{id}/members/{memberId}` | — | `JobRecord` | any |
| PATCH | `/api/v1/jobs/{id}/items/{itemId}` | `{item: Partial<FitoutItem>}` | `JobRecord` (BOQ recalculated) | any (fit-out) |
| POST | `/api/v1/jobs/{id}/items` | `FitoutItem` | `JobRecord` | any |
| DELETE | `/api/v1/jobs/{id}/items/{itemId}` | — | `JobRecord` | any |
| POST | `/api/v1/jobs/{id}/recalculate` | `{standards?: Standards, currency?: string}` | `JobRecord` | any |
| POST | `/api/v1/jobs/{id}/reprocess` | — | `JobRecord` (status → queued, pipeline re-run) | any |
| POST | `/api/v1/jobs/{id}/approve` | — | `JobRecord` | reviewer, admin (only when `ready`, and the job has members/items) |
| POST | `/api/v1/jobs/{id}/reject` | `{reason}` (3..500 chars) | `JobRecord` (status → `ready`, approval cleared, reason in `events`) | reviewer, admin (when `ready` or `approved`) |
| GET | `/api/v1/jobs/{id}/export.xlsx` | — | xlsx (bearer; fetch blob → download). Works when `ready` or `approved` | any |
| DELETE | `/api/v1/jobs/{id}` | — | 204 | owner or admin |
| GET | `/api/v1/standards` | — | `Standards` | any |
| PUT | `/api/v1/standards` | `Standards` | `Standards` | admin |
| GET | `/api/v1/admin/users` | — | `UserProfile[]` | admin |
| POST | `/api/v1/admin/invite` | `InviteRequest` | `InviteResponse` (temporary password shown once) | admin |
| PATCH | `/api/v1/admin/users/{id}` | `RoleUpdate` | `UserProfile` | admin |
| DELETE | `/api/v1/admin/users/{id}` | — | 204 | admin |

Rules: member/item edits and recalculate are accepted only when the job is `ready`, `approved` or `failed`; an edit on an
`approved` job clears the approval (back to `ready`). Edits stamp `confidence = 1` and an evidence line
"edited by <email> on <date>". Login is throttled (8 failures per email → 60 s lock, HTTP 429). Jobs interrupted by a
server restart are re-queued automatically. Every sensitive action is written to `audit_log`.

Job status flow: `queued → converting → analysing → extracting → quantifying → ready → approved`, or `failed`.
`progress` 0..100; `events[]` has one entry per transition with `message`.

## Types (TypeScript mirror; source of truth `backend/app/models/schemas.py`)
```ts
export type Module = 'structural' | 'fitout';
export type JobStatus = 'queued'|'converting'|'analysing'|'extracting'|'quantifying'|'ready'|'approved'|'failed';
export type Role = 'engineer'|'reviewer'|'admin';
export interface UserProfile { id:string; email:string; full_name?:string|null; role:Role; must_set_password:boolean; is_active:boolean; created_at?:string|null; last_sign_in_at?:string|null }
export interface LoginRequest { email:string; password:string }
export interface TokenResponse { access_token:string; token_type:'bearer'; expires_in:number; profile:UserProfile }
export interface SetPasswordRequest { password:string; current_password?:string|null }
export interface InviteRequest { email:string; full_name?:string|null; role:Role; temporary_password?:string|null }
export interface InviteResponse { profile:UserProfile; temporary_password:string }
export interface RoleUpdate { role?:Role|null; is_active?:boolean|null; full_name?:string|null }
export interface AIStatus { enabled:boolean; provider:string; model_fast?:string|null; model_pro?:string|null; message:string }
export interface SystemInfo { version:string; ai:AIStatus; converters:{oda:boolean; libredwg:boolean}; libredwg_bin:string; db_path:string; data_dir:string; db_mb:number; data_mb:number; worker_threads:number; max_upload_mb:number; stats:{jobs_total:number; jobs_this_month:number; steel_t:number; boq_lines:number; awaiting_review:number; approved:number; failed:number}; users:number }
export interface AuditEntry { id:number; at:string; user_email?:string|null; action:string; target?:string|null; detail?:string|null }
export interface RejectRequest { reason:string }

export interface Standards { ld_factor:number; anchorage_extra_d:number; cover_beam_mm:number; cover_slab_mm:number; cover_column_mm:number; cover_wall_mm:number; cover_stair_mm:number; hook_length_d:number; stirrup_corners:number; bend_deduction_d:number; min_straight_anchorage_m:number; extra_bar_span_fraction:number; curtail_fraction:number; end_zone_span_fraction:number; stirrup_end_offset_m:number; slab_min_anchorage_m:number; slab_bentup_factor:number; slab_dist_end_fraction:number; slab_cont_edge_fraction:number; sfr_min_depth_m:number; unit_weight_kg_per_m:Record<string,number>; diameters_in_summary:number[] }

// ---- structural (unchanged from FRONTEND_SPEC.md) ----
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
export interface GeneralNotes { ld_factor?:number|null; cover_beam_mm?:number|null; cover_slab_mm?:number|null; cover_column_mm?:number|null; concrete_grade?:string|null; steel_grade?:string|null; notes:string[] }

// ---- fit-out ----
export type Division = 'preliminaries'|'finishes'|'joinery'|'doors'|'lighting'|'ffe'|'mep'|'other';
export type Unit = 'm2'|'lm'|'nos'|'m3'|'kg'|'item'|'ls';
export type QtyBasis = 'measured'|'counted'|'estimated'|'manual';
export const DIVISION_LABELS: Record<Division,string> = { preliminaries:'DIV-01 - PRELIMINARIES', finishes:'DIV-09 - FINISHES', joinery:'DIV-09 - JOINERY', doors:'DIV-08 - DOORS', lighting:'DIV-13 - LIGHTING', ffe:'FF&E', mep:'DIV-15 - MEP', other:'OTHER' };
export interface FitoutItem { id:string; division:Division; section:string; code?:string|null; description:string; unit:Unit; qty:number; qty_basis:QtyBasis; rooms:string[]; size_label?:string|null; specification?:string|null; confidence:number; evidence:string[]; source_sheet?:string|null; source_bbox?:BBox|null; rate?:number|null; remarks?:string|null }
export interface RoomRecord { id:string; name:string; area_m2?:number|null; perimeter_m?:number|null; ceiling_height_m?:number|null; floor_finish?:string|null; wall_finishes:string[]; ceiling_finish?:string|null; source_sheet?:string|null; confidence:number; evidence:string[] }
export interface BOQLine { seq:number; item_ref:string; item_id:string; division:Division; section:string; code?:string|null; description:string; unit:Unit; qty:number; rate?:number|null; amount?:number|null; qty_basis:QtyBasis; rooms:string[]; confidence:number; evidence:string[]; source_sheet?:string|null; formula:string }
export interface BOQSection { division:Division; division_label:string; section:string; lines:BOQLine[]; qty_by_unit:Record<string,number>; amount:number }
export interface BOQSummary { currency:string; vat_pct:number; divisions:{division:Division; label:string; line_count:number; amount:number}[]; line_count:number; qty_by_unit:Record<string,number>; priced_lines:number; subtotal:number; vat:number; grand_total:number }
export interface BOQResult { sections:BOQSection[]; rooms:RoomRecord[]; summary:BOQSummary; warnings:string[] }

// ---- jobs ----
export interface SourceFile { name:string; size_bytes:number; format:'dwg'|'dxf'|'pdf'|'image'|'unknown'; storage_path:string; mime:string }
export interface SheetClassification { sheet_type:string; discipline:string; drawing_number?:string|null; title?:string|null; level?:string|null; scale?:string|null; units:string; project?:string|null; relevant_for_bbs:boolean; relevant_for_boq:boolean; confidence:number; summary:string }
export interface SheetRecord { id:string; job_id:string; file_name:string; page_no:number; layout:string; classification:SheetClassification; preview_path?:string|null; text_count:number; width:number; height:number; processing_notes:string[] }
export interface JobEvent { at:string; status:JobStatus; message:string; progress:number }
export interface JobRecord { id:string; module:Module; project_name:string; level:string; currency:string; location?:string|null; contractor?:string|null; work_description:string; drawn_by?:string|null; drawing_refs:string[]; status:JobStatus; progress:number; error?:string|null; standards:Standards; source_files:SourceFile[]; members:MemberSpec[]; result?:BBSResult|null; fitout_items:FitoutItem[]; rooms:RoomRecord[]; legend:Record<string,string>; boq?:BOQResult|null; general_notes:GeneralNotes; sheet_count:number; events:JobEvent[]; created_by?:string|null; created_by_email?:string|null; created_at:string; updated_at:string; approved_by?:string|null; approved_at?:string|null; export_path?:string|null; export_version:number }
export interface JobSummaryRecord { id:string; module:Module; project_name:string; level:string; status:JobStatus; progress:number; created_at:string; updated_at:string; created_by_email?:string|null; member_count:number; grand_total_t?:number|null; grand_total_amount?:number|null; headline:string; file_names:string[] }
```

## Frontend auth flow (local accounts, replaces the Supabase flow in FRONTEND_SPEC.md)
- `/login`: email + password → `POST /api/v1/auth/login`. Store `access_token` + `profile` in `localStorage` (`avighna.token`, `avighna.profile`) and also set a cookie `avighna_token` (path=/, SameSite=Lax, max-age = expires_in) so `middleware.ts` can redirect unauthenticated users to `/login`.
- If `profile.must_set_password` is true after login → redirect to `/set-password` (calls `POST /api/v1/auth/set-password`, then back to `/`).
- `useUser()` context loads `GET /api/v1/me` on mount; on 401 clear storage and redirect to `/login`.
- Logout: clear storage + cookie, go to `/login`.
- No Supabase packages are used in this build; keep `lib/api.ts` as the single fetch layer.
