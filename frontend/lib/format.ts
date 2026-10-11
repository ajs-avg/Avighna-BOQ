import type {
  BarGroup,
  ColumnTie,
  MemberSpec,
  SlabLayer,
  SourceFormat,
  StirrupZone,
  Unit,
} from "./types";

const nf = (digits: number, min = digits) =>
  new Intl.NumberFormat("en-IN", { minimumFractionDigits: min, maximumFractionDigits: digits });

const NF0 = nf(0);
const NF1 = nf(1);
const NF2 = nf(2);
const NF3 = nf(3);

/** Format a plain number with grouping and fixed decimals. */
export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  switch (digits) {
    case 0:
      return NF0.format(value);
    case 1:
      return NF1.format(value);
    case 3:
      return NF3.format(value);
    default:
      return NF2.format(value);
  }
}

/** Integer count with grouping. */
export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return NF0.format(Math.round(value));
}

/** Tons, 3 decimals, with unit. */
export function formatTons(value: number | null | undefined, withUnit = true): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const s = NF3.format(value);
  return withUnit ? `${s} t` : s;
}

/** Kilograms, 2 decimals, with unit. */
export function formatKg(value: number | null | undefined, withUnit = true): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const s = NF2.format(value);
  return withUnit ? `${s} kg` : s;
}

/** Metres, 3 decimals. */
export function formatM(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return NF3.format(value);
}

/** Human readable file size. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "11 Oct 2026, 14:32" */
export function formatDate(value: string | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "11 Oct 2026" */
export function formatDay(value: string | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/** "14:32:05" */
export function formatTime(value: string | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** "3 min ago", "2 h ago", "yesterday", else formatDay. */
export function formatRelative(value: string | Date | null | undefined, now = new Date()): string {
  const d = toDate(value);
  if (!d) return "—";
  const diff = Math.max(0, now.getTime() - d.getTime());
  const s = Math.floor(diff / 1000);
  if (s < 45) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ago`;
  const days = Math.floor(h / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return formatDay(d);
}

/** Currency amount, e.g. "AED 1,24,500.00" (en-IN grouping to match the Excel). */
export function formatMoney(value: number | null | undefined, currency = "AED"): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${currency} ${NF2.format(value)}`;
}

/** Display label for a BOQ unit. */
export function unitLabel(unit: Unit | string): string {
  switch (unit) {
    case "m2":
      return "m²";
    case "m3":
      return "m³";
    case "lm":
      return "lm";
    case "nos":
      return "nos";
    case "item":
      return "item";
    case "ls":
      return "LS";
    case "kg":
      return "kg";
    default:
      return unit;
  }
}

/** Quantity with its unit: "1,240.00 m²". Whole numbers for counts. */
export function formatQty(qty: number | null | undefined, unit: Unit | string): string {
  if (qty === null || qty === undefined || !Number.isFinite(qty)) return "—";
  const isCount = unit === "nos" || unit === "item" || unit === "ls";
  return `${isCount ? NF0.format(qty) : NF2.format(qty)} ${unitLabel(unit)}`;
}

/** "1,240 m² · 310 lm · 96 nos" from a qty_by_unit map. */
export function formatQtyByUnit(map: Record<string, number> | null | undefined): string {
  if (!map) return "";
  const order: string[] = ["m2", "lm", "nos", "m3", "kg", "item", "ls"];
  const keys = Object.keys(map).sort((a, b) => {
    const ia = order.indexOf(a);
    const ib = order.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  return keys
    .filter((k) => map[k] > 0)
    .map((k) => {
      const isCount = k === "nos" || k === "item" || k === "ls";
      return `${isCount ? NF0.format(map[k]) : NF0.format(Math.round(map[k]))} ${unitLabel(k)}`;
    })
    .join(" · ");
}

/** Decimals to show for a measurement quantity in `unit` (IS 1200 sheets: counts whole, others 2 dp). */
export function qtyDigits(unit: string): number {
  const u = unit.toLowerCase();
  if (u === "nos" || u === "ls" || u === "item") return 0;
  return 2;
}

/** Measurement quantity with its unit, e.g. "11.63 cum" / "4 nos". */
export function formatMeasure(qty: number | null | undefined, unit: string): string {
  if (qty === null || qty === undefined || !Number.isFinite(qty)) return "—";
  return `${formatNumber(qty, qtyDigits(unit))} ${unit}`;
}

/** Preferred display order for trades in the measurement totals strip. */
const TRADE_ORDER = ["RCC", "Formwork", "Steel", "Blockwork", "Plaster", "Flooring", "Skirting", "Dado", "Painting", "Waterproofing", "Doors", "Windows"];

/**
 * "RCC 11.6 cum · Flooring 14.4 sqm · Painting 66 sqm" from `MeasurementResult.totals_by_trade`.
 * Returns the parts so callers can render chips; join with " · " for a one-liner.
 */
export function totalsByTradeParts(totals: Record<string, Record<string, number>> | null | undefined): { trade: string; unit: string; value: number; label: string }[] {
  if (!totals) return [];
  const trades = Object.keys(totals).sort((a, b) => {
    const ia = TRADE_ORDER.indexOf(a);
    const ib = TRADE_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  const out: { trade: string; unit: string; value: number; label: string }[] = [];
  for (const trade of trades) {
    for (const [unit, value] of Object.entries(totals[trade] ?? {})) {
      if (!Number.isFinite(value) || value === 0) continue;
      const digits = qtyDigits(unit) === 0 ? 0 : 1;
      out.push({ trade, unit, value, label: `${trade} ${formatNumber(value, digits)} ${unit}` });
    }
  }
  return out;
}

/** "2-T20 + 2-T16" */
export function formatBars(groups: BarGroup[] | null | undefined): string {
  if (!groups || groups.length === 0) return "—";
  return groups
    .filter((g) => g.count > 0)
    .map((g) => `${g.count}-T${g.dia_mm}`)
    .join(" + ");
}

/** "T8 @ 150 (end) · T8 @ 200 (mid)" */
export function formatStirrups(zones: StirrupZone[] | null | undefined): string {
  if (!zones || zones.length === 0) return "—";
  return zones
    .map((z) => `T${z.dia_mm} @ ${formatNumber(z.spacing_mm, 0)}${z.zone !== "full" ? ` (${z.zone})` : ""}${z.legs > 2 ? ` ${z.legs}L` : ""}`)
    .join(" · ");
}

/** "T10 @ 150 c/c" */
export function formatLayer(layer: SlabLayer | null | undefined): string {
  if (!layer) return "—";
  return `T${layer.dia_mm} @ ${formatNumber(layer.spacing_mm, 0)}${layer.bent_up ? " (bent-up)" : ""}`;
}

/** "T8 @ 150 ring + 2× T8 @ 150 inner" */
export function formatTies(ties: ColumnTie[] | null | undefined): string {
  if (!ties || ties.length === 0) return "—";
  const kindLabel: Record<ColumnTie["kind"], string> = {
    main_ring: "ring",
    inner_tie: "inner",
    cross_tie: "cross",
  };
  return ties
    .map((t) => `${t.per_layer > 1 ? `${t.per_layer}× ` : ""}T${t.dia_mm} @ ${formatNumber(t.spacing_mm, 0)} ${kindLabel[t.kind]}`)
    .join(" + ");
}

/** Size label for a member spec, e.g. "230 × 600" or "L 4.500 × 3.200 × 150". */
export function memberSizeLabel(m: MemberSpec): string {
  const mm = (v: number) => Math.round(v * 1000).toString();
  switch (m.kind) {
    case "beam":
      return `${mm(m.width_m)} × ${mm(m.depth_m)} · L ${formatM(m.span_m)} m`;
    case "slab":
      return `${formatM(m.length_m)} × ${formatM(m.width_m)} m · ${mm(m.thickness_m)} thk`;
    case "column":
      return `${mm(m.length_m)} × ${mm(m.width_m)} · H ${formatM(m.height_m)} m`;
    case "wall":
      return `${formatM(m.length_m)} m × ${mm(m.thickness_m)} thk · H ${formatM(m.height_m)} m`;
    case "stair":
      return `${m.flights.length} flight${m.flights.length === 1 ? "" : "s"}`;
    default:
      return "";
  }
}

/** One-line reinforcement summary for a member spec. */
export function memberBarsSummary(m: MemberSpec): string {
  switch (m.kind) {
    case "beam": {
      const parts: string[] = [];
      if (m.bottom_bars.length) parts.push(`Bot ${formatBars(m.bottom_bars)}`);
      if (m.top_bars.length) parts.push(`Top ${formatBars(m.top_bars)}`);
      if (m.stirrups.length) parts.push(`Stp ${formatStirrups(m.stirrups)}`);
      return parts.join(" · ") || "—";
    }
    case "slab": {
      const parts: string[] = [];
      if (m.short_main) parts.push(`Short ${formatLayer(m.short_main)}`);
      if (m.long_main) parts.push(`Long ${formatLayer(m.long_main)}`);
      return parts.join(" · ") || "—";
    }
    case "column": {
      const parts: string[] = [];
      if (m.vertical_bars.length) parts.push(`Vert ${formatBars(m.vertical_bars)}`);
      if (m.ties.length) parts.push(`Ties ${formatTies(m.ties)}`);
      return parts.join(" · ") || "—";
    }
    case "wall": {
      const parts: string[] = [];
      if (m.vertical) parts.push(`V ${formatLayer(m.vertical)}`);
      if (m.horizontal) parts.push(`H ${formatLayer(m.horizontal)}`);
      parts.push(`${m.faces === 2 ? "double" : "single"} mesh`);
      return parts.join(" · ");
    }
    case "stair":
      return m.flights
        .map((f) => `${f.name}: ${formatLayer(f.main)} / ${formatLayer(f.dist)}`)
        .join(" · ") || "—";
    default:
      return "—";
  }
}

/** Detect the source format from a file name's extension. */
export function detectFormat(fileName: string): SourceFormat {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "dwg") return "dwg";
  if (ext === "dxf") return "dxf";
  if (ext === "pdf") return "pdf";
  if (["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"].includes(ext)) return "image";
  return "unknown";
}

/** Percentage string from a 0..1 confidence. */
export function formatPct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Title case a snake_case label. */
export function humanize(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * The reviewer stamp the API appends to `evidence` on manual edits
 * ("edited by a@b.com on 11-Oct-2026 09:12 UTC") as "Edited by a@b.com on …", or null when the row was never edited.
 * The API keeps a single stamp per row, but scan from the end in case older data carries several.
 */
export function editedByNote(evidence: string[] | null | undefined): string | null {
  if (!evidence || evidence.length === 0) return null;
  const prefix = /^edited by\s+/i;
  for (let i = evidence.length - 1; i >= 0; i -= 1) {
    const line = (evidence[i] ?? "").trim();
    if (prefix.test(line)) {
      const rest = line.replace(prefix, "").trim();
      return rest ? `Edited by ${rest}` : null;
    }
  }
  return null;
}

/** "1.5 MB" from a megabyte count (two decimals under 1 MB so small SQLite files don't read as zero). */
export function formatMb(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${formatNumber(value, value < 1 ? 2 : 1)} MB`;
}

/** Initials for an avatar: "Shubham Mishra" → "SM". */
export function initials(name: string | null | undefined, email?: string | null): string {
  const src = (name && name.trim()) || (email ? email.split("@")[0] : "") || "?";
  const parts = src.replace(/[._-]+/g, " ").trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "?";
  const second = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + second).toUpperCase();
}
