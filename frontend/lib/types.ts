/**
 * TypeScript mirror of docs/API_CONTRACT.md (source of truth:
 * backend/app/models/schemas.py). Keep in sync by hand.
 */

export type Module = "structural" | "fitout";
export type JobStatus =
  | "queued"
  | "converting"
  | "analysing"
  | "extracting"
  | "quantifying"
  | "ready"
  | "approved"
  | "failed";
export type Role = "engineer" | "reviewer" | "admin";

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string | null;
  role: Role;
  must_set_password: boolean;
  is_active: boolean;
  created_at?: string | null;
  last_sign_in_at?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  profile: UserProfile;
}

export interface SetPasswordRequest {
  password: string;
  current_password?: string | null;
}

export interface InviteRequest {
  email: string;
  full_name?: string | null;
  role: Role;
  temporary_password?: string | null;
}

export interface InviteResponse {
  profile: UserProfile;
  temporary_password: string;
}

export interface RoleUpdate {
  role?: Role | null;
  is_active?: boolean | null;
  full_name?: string | null;
}

export interface AIStatus {
  enabled: boolean;
  provider: string;
  model_fast?: string | null;
  model_pro?: string | null;
  message: string;
}

export interface ConverterStatus {
  oda: boolean;
  libredwg: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  converters: ConverterStatus;
  ai: AIStatus;
}

/** Job counters as returned by GET /api/v1/stats and inside SystemInfo. */
export interface JobStats {
  jobs_total: number;
  jobs_this_month: number;
  steel_t: number;
  boq_lines: number;
  awaiting_review: number;
  approved: number;
  failed: number;
}

export interface SystemInfo {
  version: string;
  ai: AIStatus;
  converters: ConverterStatus;
  libredwg_bin: string;
  db_path: string;
  data_dir: string;
  db_mb: number;
  data_mb: number;
  worker_threads: number;
  max_upload_mb: number;
  stats: JobStats;
  users: number;
}

export interface AuditEntry {
  id: number;
  at: string;
  user_email?: string | null;
  action: string;
  target?: string | null;
  detail?: string | null;
}

/** GET /api/v1/admin/audit wraps the rows: `{ items: AuditEntry[] }`. */
export interface AuditListResponse {
  items: AuditEntry[];
}

export interface RejectRequest {
  reason: string;
}

export interface Standards {
  ld_factor: number;
  anchorage_extra_d: number;
  cover_beam_mm: number;
  cover_slab_mm: number;
  cover_column_mm: number;
  cover_wall_mm: number;
  cover_stair_mm: number;
  hook_length_d: number;
  stirrup_corners: number;
  bend_deduction_d: number;
  min_straight_anchorage_m: number;
  extra_bar_span_fraction: number;
  curtail_fraction: number;
  end_zone_span_fraction: number;
  stirrup_end_offset_m: number;
  slab_min_anchorage_m: number;
  slab_bentup_factor: number;
  slab_dist_end_fraction: number;
  slab_cont_edge_fraction: number;
  sfr_min_depth_m: number;
  unit_weight_kg_per_m: Record<string, number>;
  diameters_in_summary: number[];
}

// ---- structural -----------------------------------------------------------

export interface BarGroup {
  count: number;
  dia_mm: number;
  note?: string | null;
}

export type StirrupZoneKind = "end" | "mid" | "full";

export interface StirrupZone {
  dia_mm: number;
  spacing_mm: number;
  zone: StirrupZoneKind;
  legs: number;
}

export interface SlabLayer {
  dia_mm: number;
  spacing_mm: number;
  bent_up: boolean;
  note?: string | null;
}

export type ColumnTieKind = "main_ring" | "inner_tie" | "cross_tie";

export interface ColumnTie {
  dia_mm: number;
  spacing_mm: number;
  kind: ColumnTieKind;
  per_layer: number;
  leg_length_m?: number | null;
}

export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  space: "page" | "model";
}

export interface MemberBase {
  id: string;
  tag: string;
  nos: number;
  confidence: number;
  evidence: string[];
  source_sheet?: string | null;
  source_bbox?: BBox | null;
  remarks?: string | null;
}

export type SupportType = "end" | "continuous";

export interface BeamSpec extends MemberBase {
  kind: "beam";
  span_m: number;
  width_m: number;
  depth_m: number;
  bottom_bars: BarGroup[];
  top_bars: BarGroup[];
  extra_top_left: BarGroup[];
  extra_top_right: BarGroup[];
  extra_bottom_mid: BarGroup[];
  bottom_curtail: BarGroup[];
  sfr_bars: BarGroup[];
  stirrups: StirrupZone[];
  left_support: SupportType;
  right_support: SupportType;
}

export interface SlabSpec extends MemberBase {
  kind: "slab";
  length_m: number;
  width_m: number;
  thickness_m: number;
  short_main?: SlabLayer | null;
  long_main?: SlabLayer | null;
  short_top_dist_end?: SlabLayer | null;
  long_top_dist_end?: SlabLayer | null;
  short_top_cont_edge?: SlabLayer | null;
  long_top_cont_edge?: SlabLayer | null;
  extra_top: SlabLayer[];
  one_way: boolean;
}

export type ColumnShape = "rectangular" | "L" | "T" | "circular";

export interface ColumnSpec extends MemberBase {
  kind: "column";
  length_m: number;
  width_m: number;
  height_m: number;
  vertical_bars: BarGroup[];
  ties: ColumnTie[];
  lap_at_floor: boolean;
  shape: ColumnShape;
}

export interface WallSpec extends MemberBase {
  kind: "wall";
  length_m: number;
  thickness_m: number;
  height_m: number;
  vertical?: SlabLayer | null;
  horizontal?: SlabLayer | null;
  faces: number;
  starter_lap: boolean;
}

export interface StairFlight {
  name: string;
  width_m: number;
  waist_m: number;
  going_m: number;
  rise_m: number;
  landing_a_m: number;
  landing_b_m: number;
  main?: SlabLayer | null;
  dist?: SlabLayer | null;
}

export interface StairSpec extends MemberBase {
  kind: "stair";
  flights: StairFlight[];
}

export type MemberSpec = BeamSpec | SlabSpec | ColumnSpec | WallSpec | StairSpec;
export type MemberKind = MemberSpec["kind"];

export interface BarRow {
  seq: number;
  description: string;
  dia_mm: number;
  members: number;
  bars_per_member: number;
  total_bars: number;
  spacing_mm?: number | null;
  span_m?: number | null;
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
  g: number;
  bend_corners: number;
  cut_length_m: number;
  weight_kg: number;
  formula: string;
  shape: string;
}

export interface MemberResult {
  member_id: string;
  kind: string;
  tag: string;
  nos: number;
  size_label: string;
  rows: BarRow[];
  weight_kg: number;
  weight_by_dia_kg: Record<string, number>;
  confidence: number;
  warnings: string[];
}

export interface CategorySummary {
  category: string;
  weight_by_dia_t: Record<string, number>;
  total_t: number;
  member_count: number;
}

export interface BBSSummary {
  level: string;
  categories: CategorySummary[];
  total_by_dia_t: Record<string, number>;
  grand_total_t: number;
}

export interface BBSResult {
  standards: Standards;
  members: MemberResult[];
  summary: BBSSummary;
}

export interface GeneralNotes {
  ld_factor?: number | null;
  cover_beam_mm?: number | null;
  cover_slab_mm?: number | null;
  cover_column_mm?: number | null;
  concrete_grade?: string | null;
  steel_grade?: string | null;
  notes: string[];
}

// ---- fit-out --------------------------------------------------------------

export type Division =
  | "preliminaries"
  | "finishes"
  | "joinery"
  | "doors"
  | "lighting"
  | "ffe"
  | "mep"
  | "other";
export type Unit = "m2" | "lm" | "nos" | "m3" | "kg" | "item" | "ls";
export type QtyBasis = "measured" | "counted" | "estimated" | "manual";

export const DIVISION_LABELS: Record<Division, string> = {
  preliminaries: "DIV-01 - PRELIMINARIES",
  finishes: "DIV-09 - FINISHES",
  joinery: "DIV-09 - JOINERY",
  doors: "DIV-08 - DOORS",
  lighting: "DIV-13 - LIGHTING",
  ffe: "FF&E",
  mep: "DIV-15 - MEP",
  other: "OTHER",
};

export const DIVISIONS: Division[] = [
  "preliminaries",
  "finishes",
  "joinery",
  "doors",
  "lighting",
  "ffe",
  "mep",
  "other",
];
export const UNITS: Unit[] = ["m2", "lm", "nos", "m3", "kg", "item", "ls"];
export const QTY_BASES: QtyBasis[] = ["measured", "counted", "estimated", "manual"];

export interface FitoutItem {
  id: string;
  division: Division;
  section: string;
  code?: string | null;
  description: string;
  unit: Unit;
  qty: number;
  qty_basis: QtyBasis;
  rooms: string[];
  size_label?: string | null;
  specification?: string | null;
  confidence: number;
  evidence: string[];
  source_sheet?: string | null;
  source_bbox?: BBox | null;
  rate?: number | null;
  remarks?: string | null;
}

export interface RoomRecord {
  id: string;
  name: string;
  area_m2?: number | null;
  perimeter_m?: number | null;
  ceiling_height_m?: number | null;
  floor_finish?: string | null;
  wall_finishes: string[];
  ceiling_finish?: string | null;
  source_sheet?: string | null;
  confidence: number;
  evidence: string[];
}

export interface BOQLine {
  seq: number;
  item_ref: string;
  item_id: string;
  division: Division;
  section: string;
  code?: string | null;
  description: string;
  unit: Unit;
  qty: number;
  rate?: number | null;
  amount?: number | null;
  qty_basis: QtyBasis;
  rooms: string[];
  confidence: number;
  evidence: string[];
  source_sheet?: string | null;
  formula: string;
}

export interface BOQSection {
  division: Division;
  division_label: string;
  section: string;
  lines: BOQLine[];
  qty_by_unit: Record<string, number>;
  amount: number;
}

export interface BOQDivisionSummary {
  division: Division;
  label: string;
  line_count: number;
  amount: number;
}

export interface BOQSummary {
  currency: string;
  vat_pct: number;
  divisions: BOQDivisionSummary[];
  line_count: number;
  qty_by_unit: Record<string, number>;
  priced_lines: number;
  subtotal: number;
  vat: number;
  grand_total: number;
}

export interface BOQResult {
  sections: BOQSection[];
  rooms: RoomRecord[];
  summary: BOQSummary;
  warnings: string[];
}

// ---- jobs -----------------------------------------------------------------

export type SourceFormat = "dwg" | "dxf" | "pdf" | "image" | "unknown";

export interface SourceFile {
  name: string;
  size_bytes: number;
  format: SourceFormat;
  storage_path: string;
  mime: string;
}

export interface SheetClassification {
  sheet_type: string;
  discipline: string;
  drawing_number?: string | null;
  title?: string | null;
  level?: string | null;
  scale?: string | null;
  units: string;
  project?: string | null;
  relevant_for_bbs: boolean;
  relevant_for_boq: boolean;
  confidence: number;
  summary: string;
}

export interface SheetRecord {
  id: string;
  job_id: string;
  file_name: string;
  page_no: number;
  layout: string;
  classification: SheetClassification;
  preview_path?: string | null;
  text_count: number;
  width: number;
  height: number;
  processing_notes: string[];
}

export interface JobEvent {
  at: string;
  status: JobStatus;
  message: string;
  progress: number;
}

export interface JobRecord {
  id: string;
  module: Module;
  project_name: string;
  level: string;
  currency: string;
  location?: string | null;
  contractor?: string | null;
  work_description: string;
  drawn_by?: string | null;
  drawing_refs: string[];
  status: JobStatus;
  progress: number;
  error?: string | null;
  standards: Standards;
  source_files: SourceFile[];
  members: MemberSpec[];
  result?: BBSResult | null;
  fitout_items: FitoutItem[];
  rooms: RoomRecord[];
  legend: Record<string, string>;
  boq?: BOQResult | null;
  general_notes: GeneralNotes;
  sheet_count: number;
  events: JobEvent[];
  created_by?: string | null;
  created_by_email?: string | null;
  created_at: string;
  updated_at: string;
  approved_by?: string | null;
  approved_at?: string | null;
  export_path?: string | null;
  export_version: number;
}

export interface JobSummaryRecord {
  id: string;
  module: Module;
  project_name: string;
  level: string;
  status: JobStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  created_by_email?: string | null;
  member_count: number;
  grand_total_t?: number | null;
  grand_total_amount?: number | null;
  headline: string;
  file_names: string[];
}

export interface JobListResponse {
  items: JobSummaryRecord[];
  total: number;
}

export interface CreateJobResponse {
  job_id: string;
  status: JobStatus;
}

export interface ApiErrorBody {
  detail: string;
}
