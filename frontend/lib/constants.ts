import type { BOQBasis, JobStatus, MemberKind, Module, QtyBasis, Role } from "./types";

export const APP_NAME = "Avighna BOQ";
export const TAGLINE = "Drop a drawing, get a measurement sheet.";

export const TOKEN_KEY = "avighna.token";
export const PROFILE_KEY = "avighna.profile";
export const TOKEN_COOKIE = "avighna_token";

export const POLL_INTERVAL_MS = 2500;

export const ACCEPTED_EXTENSIONS = [".dwg", ".dxf", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"];
export const ACCEPT_ATTR = ACCEPTED_EXTENSIONS.join(",");

export const PROCESSING_STATUSES: JobStatus[] = [
  "queued",
  "converting",
  "analysing",
  "extracting",
  "quantifying",
];

/** Ordered pipeline steps for the timeline / progress. */
export const PIPELINE_STEPS: JobStatus[] = [
  "queued",
  "converting",
  "analysing",
  "extracting",
  "quantifying",
  "ready",
];

export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "brand" | "ink";

export const STATUS_META: Record<JobStatus, { label: string; tone: Tone; busy: boolean }> = {
  queued: { label: "Queued", tone: "neutral", busy: true },
  converting: { label: "Converting", tone: "info", busy: true },
  analysing: { label: "Analysing", tone: "info", busy: true },
  extracting: { label: "Extracting", tone: "info", busy: true },
  quantifying: { label: "Quantifying", tone: "info", busy: true },
  ready: { label: "Ready for review", tone: "success", busy: false },
  approved: { label: "Approved", tone: "ink", busy: false },
  failed: { label: "Failed", tone: "danger", busy: false },
};

export function isProcessing(status: JobStatus): boolean {
  return PROCESSING_STATUSES.includes(status);
}

export const MODULE_META: Record<
  Module,
  { label: string; short: string; description: string; output: string; unit: string }
> = {
  measurement: {
    label: "Measurement",
    short: "Measurement",
    description: "Drawing → measurement sheet (IS 1200), BOQ abstract and material requirement.",
    output: "Measurement",
    unit: "cum / sqm / rmt / nos",
  },
  structural: {
    label: "Structural — Reinforcement BBS",
    short: "Structural",
    description: "RCC beam, slab, column, wall and staircase drawings → bar bending schedule in tons.",
    output: "Bar Bending Schedule",
    unit: "t",
  },
  fitout: {
    label: "Interior Fit-out — BOQ",
    short: "Fit-out",
    description: "Interior design drawings → bill of quantities in m², lm and nos by division.",
    output: "Bill of Quantities",
    unit: "m² / lm / nos",
  },
};

export const ROLE_META: Record<Role, { label: string; description: string }> = {
  engineer: { label: "Engineer", description: "Upload, review and edit measurements." },
  reviewer: { label: "Reviewer", description: "Everything an engineer can do, plus approve." },
  admin: { label: "Admin", description: "Full access incl. standards and user management." },
};

export const ROLES: Role[] = ["engineer", "reviewer", "admin"];

export const MEMBER_KIND_META: Record<MemberKind, { label: string; plural: string; category: string }> = {
  beam: { label: "Beam", plural: "Beams", category: "Beam" },
  slab: { label: "Slab", plural: "Slabs", category: "Slab" },
  column: { label: "Column", plural: "Columns", category: "Column" },
  wall: { label: "Wall", plural: "Walls", category: "Wall" },
  stair: { label: "Staircase", plural: "Staircase", category: "Staircase" },
};

export const MEMBER_KINDS: MemberKind[] = ["beam", "slab", "column", "wall", "stair"];

export const BASIS_META: Record<QtyBasis, { label: string; tone: Tone; hint: string }> = {
  measured: { label: "Measured", tone: "success", hint: "Measured from drawing geometry" },
  counted: { label: "Counted", tone: "info", hint: "Counted symbols / blocks on the drawing" },
  estimated: { label: "Estimated", tone: "warning", hint: "Estimated — verify before approval" },
  manual: { label: "Manual", tone: "neutral", hint: "Entered or edited by a reviewer" },
};

/** Basis of a BOQ abstract line (measurement module). */
export const BOQ_BASIS_META: Record<BOQBasis, { label: string; tone: Tone; hint: string }> = {
  measured: { label: "Measured", tone: "success", hint: "Measured from the elements per IS 1200" },
  thumb_rule: { label: "Thumb rule", tone: "warning", hint: "Thumb rule — replace with bar bending schedule" },
  manual: { label: "Manual", tone: "neutral", hint: "Entered by a reviewer" },
};

export const CURRENCIES = ["AED", "INR", "USD"] as const;

export const DEFAULTS = {
  measurement: {
    project_name: "Nishika Elysium (Avighna)",
  },
  structural: {
    project_name: "Nishika Elysium (Avighna)",
    contractor: "Mehta Jaising Builders LLP",
  },
  fitout: {
    project_name: "Avighna Group Office & Sales Center",
    location: "Dubai, U.A.E.",
    currency: "AED",
  },
} as const;

export const STANDARD_DIAMETERS = [6, 8, 10, 12, 16, 20, 25, 32, 40];
