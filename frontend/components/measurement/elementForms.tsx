"use client";

/**
 * Schema-driven forms for the elements read from a drawing (rooms, openings, walls, slabs,
 * columns & beams, other items) and the project assumptions.
 *
 * Each element kind has a `KindDef`: a list of typed field specs, a blank draft for "Add",
 * and explicit `toDraft` / `fromDraft` converters. Drafts keep numbers as `number | ""`
 * while the user types; `fromDraft` runs only after `validateFields` passed, so every
 * required number is present and > 0 (counts ≥ 1).
 */

import { useId } from "react";
import {
  CONSTRUCTIONS,
  MEMBER_EL_KINDS,
  MISC_UNITS,
  OPENING_KINDS,
  WALL_TYPES,
  type Construction,
  type ElBase,
  type MeasurementExtraction,
  type MemberEl,
  type MemberElKind,
  type MiscEl,
  type MiscUnit,
  type OpeningEl,
  type OpeningKind,
  type ProjectAssumptions,
  type RoomEl,
  type SlabEl,
  type WallEl,
  type WallType,
} from "@/lib/types";
import { cn, newId } from "@/lib/utils";
import { Field, Input, NumberInput, Textarea } from "../ui/Input";
import { Select, type SelectOption } from "../ui/Select";
import { Switch } from "../ui/Switch";

/* ------------------------------------------------------------------------- */
/* Draft types                                                                 */
/* ------------------------------------------------------------------------- */

export type Num = number | "";
export type DraftValue = string | number | boolean | null | undefined | string[];
export type DraftRecord = Record<string, DraftValue>;
/** Element → form draft: every number (nullable ones included) becomes `number | ""` while typing. */
export type Draft<T> = { [K in keyof T]-?: NonNullable<T[K]> extends number ? Num : T[K] };
type KeysOfType<T, V> = { [K in keyof T]-?: T[K] extends V ? K : never }[keyof T];

export type ListName = "rooms" | "levels" | "walls" | "trades";
export type SuggestionLists = Partial<Record<ListName, readonly string[]>>;

interface FieldBase {
  label: string;
  hint?: string;
  /** Show the required asterisk (numbers are required unless `optional`). */
  required?: boolean;
  /** Grid columns to span (of 3). */
  span?: 2 | 3;
}
export interface TextFieldSpec<D> extends FieldBase {
  kind: "text";
  key: KeysOfType<D, string | null | undefined>;
  placeholder?: string;
  mono?: boolean;
  multiline?: boolean;
  list?: ListName;
}
export interface NumberFieldSpec<D> extends FieldBase {
  kind: "number";
  key: KeysOfType<D, Num>;
  min?: number;
  step?: number;
  suffix?: string;
  /** Whole number ≥ 1 (counts). */
  integer?: boolean;
  /** Blank allowed (stored as null / 0 by `fromDraft`). */
  optional?: boolean;
  /** 0 allowed (default: must be > 0). */
  zero?: boolean;
  placeholder?: string;
}
export interface SelectFieldSpec<D> extends FieldBase {
  kind: "select";
  key: KeysOfType<D, string>;
  options: SelectOption[];
}
export interface SwitchFieldSpec<D> extends FieldBase {
  kind: "switch";
  key: KeysOfType<D, boolean>;
  description?: string;
}
export type FieldSpec<D> = TextFieldSpec<D> | NumberFieldSpec<D> | SelectFieldSpec<D> | SwitchFieldSpec<D>;

/* ------------------------------------------------------------------------- */
/* Validation                                                                  */
/* ------------------------------------------------------------------------- */

/** Field key → message. Empty object = valid. */
export function validateFields<D extends DraftRecord>(draft: D, fields: readonly FieldSpec<D>[]): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const f of fields) {
    const key = String(f.key);
    const v = draft[f.key];
    if (f.kind === "text") {
      if (f.required && (typeof v !== "string" || v.trim() === "")) errors[key] = "Required";
    } else if (f.kind === "select") {
      if (f.required !== false && (typeof v !== "string" || v === "")) errors[key] = "Required";
    } else if (f.kind === "number") {
      if (v === "" || v === null || v === undefined) {
        if (!f.optional) errors[key] = "Required";
        continue;
      }
      if (typeof v !== "number" || !Number.isFinite(v)) {
        errors[key] = "Enter a number";
        continue;
      }
      if (f.integer && !Number.isInteger(v)) {
        errors[key] = "Whole number";
        continue;
      }
      const min = f.min ?? (f.integer ? 1 : f.zero ? 0 : null);
      if (min === null ? v <= 0 : v < min) errors[key] = min === null ? "Must be greater than 0" : `Must be at least ${min}`;
    }
  }
  return errors;
}

/* ------------------------------------------------------------------------- */
/* Renderer                                                                    */
/* ------------------------------------------------------------------------- */

export interface ElementFieldsProps<D extends DraftRecord> {
  fields: readonly FieldSpec<D>[];
  draft: D;
  onChange: (next: D) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
  lists?: SuggestionLists;
  className?: string;
}

export function ElementFields<D extends DraftRecord>({ fields, draft, onChange, errors = {}, disabled, lists = {}, className }: ElementFieldsProps<D>) {
  const uid = useId();
  const set = (key: keyof D, value: DraftValue) => onChange({ ...draft, [key]: value });

  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 md:grid-cols-3", className)}>
      {fields.map((f) => {
        const key = String(f.key);
        const error = errors[key];
        const span = f.span === 3 ? "sm:col-span-2 md:col-span-3" : f.span === 2 ? "sm:col-span-2" : undefined;
        const v = draft[f.key];

        if (f.kind === "switch") {
          return (
            <div key={key} className={cn("flex items-center pt-5", span)}>
              <Switch checked={v === true} onCheckedChange={(c) => set(f.key, c)} label={f.label} description={f.description} disabled={disabled} size="sm" />
            </div>
          );
        }

        if (f.kind === "number") {
          const num: Num = typeof v === "number" ? v : "";
          return (
            <Field key={key} label={f.label} hint={f.hint} error={error} required={f.required ?? !f.optional} className={span}>
              {(id) => (
                <NumberInput
                  id={id}
                  value={num}
                  onValueChange={(n) => set(f.key, n)}
                  min={f.min ?? (f.integer ? 1 : 0)}
                  step={f.step ?? (f.integer ? 1 : 0.01)}
                  suffix={f.suffix}
                  placeholder={f.placeholder}
                  invalid={!!error}
                  disabled={disabled}
                />
              )}
            </Field>
          );
        }

        if (f.kind === "select") {
          const str = typeof v === "string" ? v : "";
          return (
            <Field key={key} label={f.label} hint={f.hint} error={error} required={f.required ?? true} className={span}>
              {(id) => <Select id={id} value={str} onChange={(e) => set(f.key, e.target.value)} options={f.options} invalid={!!error} disabled={disabled} />}
            </Field>
          );
        }

        const text = typeof v === "string" ? v : "";
        const suggestions = f.list ? (lists[f.list] ?? []) : [];
        const listId = f.list && suggestions.length ? `${uid}-${key}-list` : undefined;
        return (
          <Field key={key} label={f.label} hint={f.hint} error={error} required={f.required} className={span}>
            {(id) =>
              f.multiline ? (
                <Textarea id={id} value={text} onChange={(e) => set(f.key, e.target.value)} placeholder={f.placeholder} invalid={!!error} disabled={disabled} className="min-h-[64px]" />
              ) : (
                <>
                  <Input
                    id={id}
                    value={text}
                    onChange={(e) => set(f.key, e.target.value)}
                    placeholder={f.placeholder}
                    list={listId}
                    invalid={!!error}
                    disabled={disabled}
                    className={f.mono ? "font-mono" : undefined}
                  />
                  {listId ? (
                    <datalist id={listId}>
                      {suggestions.map((s) => (
                        <option key={s} value={s} />
                      ))}
                    </datalist>
                  ) : null}
                </>
              )
            }
          </Field>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Kind definitions                                                            */
/* ------------------------------------------------------------------------- */

/** Context for new rows: the job's level and current assumptions seed sensible defaults. */
export interface BlankContext {
  level: string;
  assumptions: ProjectAssumptions;
}

export interface KindDef<T extends ElBase, D extends DraftRecord> {
  singular: string;
  plural: string;
  fields: readonly FieldSpec<D>[];
  blankDraft: (ctx: BlankContext) => D;
  toDraft: (el: T) => D;
  fromDraft: (d: D) => T;
  /** Short row label for dialog titles and confirms. */
  labelOf: (el: T) => string;
}

const num = (v: Num, fallback = 0): number => (v === "" ? fallback : v);
const numOrNull = (v: Num): number | null => (v === "" ? null : v);
const str = (v: string | null | undefined): string => (v ?? "").trim();
const strOrNull = (v: string | null | undefined): string | null => {
  const t = (v ?? "").trim();
  return t ? t : null;
};
const opt = <V extends string>(values: readonly V[], label?: (v: V) => string): SelectOption[] =>
  values.map((v) => ({ value: v, label: label ? label(v) : v.charAt(0).toUpperCase() + v.slice(1) }));

/** Identity / provenance for a row the reviewer typed in (matches the backend `new_id()` shape). */
function manualBase(): Draft<ElBase> {
  return { id: newId(), confidence: 1, evidence: ["added manually"], source_sheet: null };
}

// ---- rooms

export type RoomDraft = Draft<RoomEl>;

export const ROOM_FIELDS: readonly FieldSpec<RoomDraft>[] = [
  { kind: "text", key: "name", label: "Room / space", required: true, placeholder: "Bedroom 1", span: 2 },
  { kind: "text", key: "level", label: "Level", placeholder: "6th floor", list: "levels" },
  { kind: "number", key: "length_m", label: "Length", suffix: "m", step: 0.01, hint: "Internal clear" },
  { kind: "number", key: "width_m", label: "Width", suffix: "m", step: 0.01, hint: "Internal clear" },
  { kind: "number", key: "height_m", label: "Height", suffix: "m", step: 0.01, hint: "Floor to ceiling" },
  { kind: "number", key: "area_m2", label: "Area", suffix: "sqm", step: 0.01, optional: true, hint: "Only if not rectangular" },
  { kind: "number", key: "perimeter_m", label: "Perimeter", suffix: "m", step: 0.01, optional: true, hint: "Only if not rectangular" },
  { kind: "number", key: "skirting_mm", label: "Skirting", suffix: "mm", step: 5, zero: true, hint: "0 = none" },
  { kind: "text", key: "floor_finish", label: "Floor finish", placeholder: "Vitrified tile 600x600" },
  { kind: "text", key: "wall_finish", label: "Wall finish", placeholder: "Putty + primer + emulsion" },
  { kind: "text", key: "ceiling_finish", label: "Ceiling finish", placeholder: "Putty + primer + emulsion" },
  { kind: "number", key: "dado_height_m", label: "Dado height", suffix: "m", step: 0.05, zero: true, hint: "Wall tiles, 0 = none" },
  { kind: "switch", key: "wet_area", label: "Wet area", description: "Bathroom / kitchen / utility → waterproofing" },
  { kind: "switch", key: "plastered", label: "Plastered", description: "Off for Mivan RCC walls (putty only)" },
  { kind: "text", key: "remarks", label: "Remarks", placeholder: "Optional", span: 3 },
];

export const ROOM_DEF: KindDef<RoomEl, RoomDraft> = {
  singular: "room",
  plural: "Rooms",
  fields: ROOM_FIELDS,
  blankDraft: (ctx) => ({
    ...manualBase(),
    name: "",
    level: ctx.level,
    length_m: "",
    width_m: "",
    height_m: ctx.assumptions.floor_height_m,
    area_m2: "",
    perimeter_m: "",
    floor_finish: "Vitrified tile flooring 600x600",
    wall_finish: "Putty + primer + emulsion",
    ceiling_finish: "Putty + primer + emulsion",
    skirting_mm: 100,
    dado_height_m: 0,
    wet_area: false,
    plastered: ctx.assumptions.construction !== "mivan",
    remarks: "",
  }),
  toDraft: (el) => ({
    ...el,
    area_m2: el.area_m2 ?? "",
    perimeter_m: el.perimeter_m ?? "",
    remarks: el.remarks ?? "",
    source_sheet: el.source_sheet ?? null,
  }),
  fromDraft: (d) => ({
    id: d.id,
    confidence: num(d.confidence, 1),
    evidence: d.evidence,
    source_sheet: d.source_sheet ?? null,
    name: str(d.name),
    level: str(d.level),
    length_m: num(d.length_m),
    width_m: num(d.width_m),
    height_m: num(d.height_m),
    area_m2: numOrNull(d.area_m2),
    perimeter_m: numOrNull(d.perimeter_m),
    floor_finish: str(d.floor_finish),
    wall_finish: str(d.wall_finish),
    ceiling_finish: str(d.ceiling_finish),
    skirting_mm: num(d.skirting_mm),
    dado_height_m: num(d.dado_height_m),
    wet_area: d.wet_area,
    plastered: d.plastered,
    remarks: strOrNull(d.remarks),
  }),
  labelOf: (el) => el.name,
};

// ---- openings

export type OpeningDraft = Draft<OpeningEl>;

const OPENING_KIND_OPTIONS = opt<OpeningKind>(OPENING_KINDS);

export const OPENING_FIELDS: readonly FieldSpec<OpeningDraft>[] = [
  { kind: "text", key: "tag", label: "Tag", required: true, placeholder: "D1", mono: true },
  { kind: "select", key: "kind", label: "Kind", options: OPENING_KIND_OPTIONS },
  { kind: "number", key: "count", label: "Count", integer: true, suffix: "nos" },
  { kind: "number", key: "width_m", label: "Width", suffix: "m", step: 0.01 },
  { kind: "number", key: "height_m", label: "Height", suffix: "m", step: 0.01 },
  { kind: "text", key: "level", label: "Level", placeholder: "6th floor", list: "levels" },
  { kind: "text", key: "room", label: "Room", placeholder: "Bedroom 1", list: "rooms", hint: "Deducted from that room's plaster / paint" },
  { kind: "text", key: "wall_tag", label: "Wall", placeholder: "W1", list: "walls", mono: true, hint: "Deducted from that wall, if known" },
  { kind: "text", key: "description", label: "Description", placeholder: "Flush door 35 mm with frame & hardware", span: 3 },
];

export const OPENING_DEF: KindDef<OpeningEl, OpeningDraft> = {
  singular: "opening",
  plural: "Openings",
  fields: OPENING_FIELDS,
  blankDraft: (ctx) => ({ ...manualBase(), tag: "", kind: "door", width_m: "", height_m: "", count: 1, room: "", wall_tag: "", description: "", level: ctx.level }),
  toDraft: (el) => ({ ...el, source_sheet: el.source_sheet ?? null }),
  fromDraft: (d) => ({
    id: d.id,
    confidence: num(d.confidence, 1),
    evidence: d.evidence,
    source_sheet: d.source_sheet ?? null,
    tag: str(d.tag),
    kind: d.kind,
    width_m: num(d.width_m),
    height_m: num(d.height_m),
    count: Math.max(1, Math.round(num(d.count, 1))),
    room: str(d.room),
    wall_tag: str(d.wall_tag),
    description: str(d.description),
    level: str(d.level),
  }),
  labelOf: (el) => `${el.tag} (${el.kind})`,
};

// ---- walls

export type WallDraft = Draft<WallEl>;

const WALL_TYPE_LABEL: Record<WallType, string> = { rcc: "RCC (Mivan / shear)", block: "Block masonry", partition: "Partition", glass: "Glass", other: "Other" };
const WALL_TYPE_OPTIONS = opt<WallType>(WALL_TYPES, (v) => WALL_TYPE_LABEL[v]);

export const WALL_FIELDS: readonly FieldSpec<WallDraft>[] = [
  { kind: "text", key: "tag", label: "Tag", required: true, placeholder: "W1", mono: true },
  { kind: "select", key: "wall_type", label: "Type", options: WALL_TYPE_OPTIONS },
  { kind: "number", key: "count", label: "Count", integer: true, suffix: "nos" },
  { kind: "number", key: "length_m", label: "Length", suffix: "m", step: 0.01 },
  { kind: "number", key: "thickness_m", label: "Thickness", suffix: "m", step: 0.005, hint: "0.230 = 230 mm" },
  { kind: "number", key: "height_m", label: "Height", suffix: "m", step: 0.01 },
  { kind: "text", key: "room", label: "Room", placeholder: "Bedroom 1", list: "rooms" },
  { kind: "text", key: "level", label: "Level", placeholder: "6th floor", list: "levels" },
  { kind: "switch", key: "both_faces", label: "Both faces", description: "Formwork / finish on both faces" },
];

export const WALL_DEF: KindDef<WallEl, WallDraft> = {
  singular: "wall",
  plural: "Walls",
  fields: WALL_FIELDS,
  blankDraft: (ctx) => ({
    ...manualBase(),
    tag: "",
    wall_type: ctx.assumptions.construction === "mivan" ? "rcc" : "block",
    length_m: "",
    thickness_m: ctx.assumptions.wall_thickness_m,
    height_m: ctx.assumptions.floor_height_m,
    count: 1,
    room: "",
    level: ctx.level,
    both_faces: true,
  }),
  toDraft: (el) => ({ ...el, source_sheet: el.source_sheet ?? null }),
  fromDraft: (d) => ({
    id: d.id,
    confidence: num(d.confidence, 1),
    evidence: d.evidence,
    source_sheet: d.source_sheet ?? null,
    tag: str(d.tag),
    wall_type: d.wall_type,
    length_m: num(d.length_m),
    thickness_m: num(d.thickness_m),
    height_m: num(d.height_m),
    count: Math.max(1, Math.round(num(d.count, 1))),
    room: str(d.room),
    level: str(d.level),
    both_faces: d.both_faces,
  }),
  labelOf: (el) => el.tag,
};

// ---- slabs

export type SlabDraft = Draft<SlabEl>;

export const SLAB_FIELDS: readonly FieldSpec<SlabDraft>[] = [
  { kind: "text", key: "tag", label: "Tag", required: true, placeholder: "S1", mono: true },
  { kind: "number", key: "count", label: "Count", integer: true, suffix: "nos" },
  { kind: "text", key: "level", label: "Level", placeholder: "6th floor", list: "levels" },
  { kind: "number", key: "length_m", label: "Length", suffix: "m", step: 0.01 },
  { kind: "number", key: "width_m", label: "Width", suffix: "m", step: 0.01 },
  { kind: "number", key: "thickness_m", label: "Thickness", suffix: "m", step: 0.005, hint: "0.150 = 150 mm" },
  { kind: "number", key: "beam_width_m", label: "Beam width", suffix: "m", step: 0.005, zero: true, hint: "Subtracted from soffit formwork" },
];

export const SLAB_DEF: KindDef<SlabEl, SlabDraft> = {
  singular: "slab",
  plural: "Slabs",
  fields: SLAB_FIELDS,
  blankDraft: (ctx) => ({ ...manualBase(), tag: "S1", length_m: "", width_m: "", thickness_m: ctx.assumptions.slab_thickness_m, count: 1, level: ctx.level, beam_width_m: 0.23 }),
  toDraft: (el) => ({ ...el, source_sheet: el.source_sheet ?? null }),
  fromDraft: (d) => ({
    id: d.id,
    confidence: num(d.confidence, 1),
    evidence: d.evidence,
    source_sheet: d.source_sheet ?? null,
    tag: str(d.tag),
    length_m: num(d.length_m),
    width_m: num(d.width_m),
    thickness_m: num(d.thickness_m),
    count: Math.max(1, Math.round(num(d.count, 1))),
    level: str(d.level),
    beam_width_m: num(d.beam_width_m),
  }),
  labelOf: (el) => el.tag,
};

// ---- columns & beams

export type MemberDraft = Draft<MemberEl>;

const MEMBER_KIND_OPTIONS = opt<MemberElKind>(MEMBER_EL_KINDS);

export const MEMBER_FIELDS: readonly FieldSpec<MemberDraft>[] = [
  { kind: "text", key: "tag", label: "Tag", required: true, placeholder: "C1 / B2", mono: true },
  { kind: "select", key: "kind", label: "Kind", options: MEMBER_KIND_OPTIONS },
  { kind: "number", key: "count", label: "Count", integer: true, suffix: "nos" },
  { kind: "number", key: "width_m", label: "Width", suffix: "m", step: 0.005 },
  { kind: "number", key: "depth_m", label: "Depth", suffix: "m", step: 0.005 },
  { kind: "number", key: "length_m", label: "Height / span", suffix: "m", step: 0.01, hint: "Height for columns, clear span for beams" },
  { kind: "number", key: "slab_thickness_m", label: "Slab thickness", suffix: "m", step: 0.005, zero: true, hint: "Beams: slab thickness included in depth" },
  { kind: "text", key: "level", label: "Level", placeholder: "6th floor", list: "levels" },
];

export const MEMBER_DEF: KindDef<MemberEl, MemberDraft> = {
  singular: "member",
  plural: "Columns & beams",
  fields: MEMBER_FIELDS,
  blankDraft: (ctx) => ({ ...manualBase(), tag: "", kind: "column", width_m: "", depth_m: "", length_m: ctx.assumptions.floor_height_m, count: 1, level: ctx.level, slab_thickness_m: 0 }),
  toDraft: (el) => ({ ...el, source_sheet: el.source_sheet ?? null }),
  fromDraft: (d) => ({
    id: d.id,
    confidence: num(d.confidence, 1),
    evidence: d.evidence,
    source_sheet: d.source_sheet ?? null,
    tag: str(d.tag),
    kind: d.kind,
    width_m: num(d.width_m),
    depth_m: num(d.depth_m),
    length_m: num(d.length_m),
    count: Math.max(1, Math.round(num(d.count, 1))),
    level: str(d.level),
    slab_thickness_m: num(d.slab_thickness_m),
  }),
  labelOf: (el) => `${el.tag} (${el.kind})`,
};

// ---- other items

export type MiscDraft = Draft<MiscEl>;

const MISC_UNIT_OPTIONS = opt<MiscUnit>(MISC_UNITS, (v) => v);
export const DEFAULT_TRADES = ["Plumbing", "Electrical", "Joinery", "Sanitary", "Miscellaneous"];

export const MISC_FIELDS: readonly FieldSpec<MiscDraft>[] = [
  { kind: "text", key: "tag", label: "Tag", placeholder: "Optional", mono: true },
  { kind: "text", key: "description", label: "Description", required: true, placeholder: "Wash basin with pedestal", span: 2 },
  { kind: "number", key: "qty", label: "Quantity", step: 0.01 },
  { kind: "select", key: "unit", label: "Unit", options: MISC_UNIT_OPTIONS },
  { kind: "text", key: "trade", label: "Trade", placeholder: "Plumbing", list: "trades" },
  { kind: "text", key: "room", label: "Room", placeholder: "Toilet 1", list: "rooms" },
  { kind: "text", key: "level", label: "Level", placeholder: "6th floor", list: "levels" },
];

export const MISC_DEF: KindDef<MiscEl, MiscDraft> = {
  singular: "item",
  plural: "Other items",
  fields: MISC_FIELDS,
  blankDraft: (ctx) => ({ ...manualBase(), tag: "", description: "", unit: "nos", qty: "", trade: "Miscellaneous", room: "", level: ctx.level }),
  toDraft: (el) => ({ ...el, tag: el.tag ?? "", source_sheet: el.source_sheet ?? null }),
  fromDraft: (d) => ({
    id: d.id,
    confidence: num(d.confidence, 1),
    evidence: d.evidence,
    source_sheet: d.source_sheet ?? null,
    tag: strOrNull(d.tag),
    description: str(d.description),
    unit: d.unit,
    qty: num(d.qty),
    trade: str(d.trade) || "Miscellaneous",
    room: str(d.room),
    level: str(d.level),
  }),
  labelOf: (el) => el.description,
};

// ---- assumptions

export type AssumptionsDraft = Draft<ProjectAssumptions>;

const CONSTRUCTION_OPTIONS = opt<Construction>(CONSTRUCTIONS, (v) => (v === "mivan" ? "Mivan (aluminium formwork)" : "Conventional"));

export const ASSUMPTION_FIELDS: readonly FieldSpec<AssumptionsDraft>[] = [
  { kind: "number", key: "floor_height_m", label: "Floor height", suffix: "m", step: 0.01 },
  { kind: "number", key: "wall_thickness_m", label: "Wall thickness", suffix: "m", step: 0.005 },
  { kind: "number", key: "slab_thickness_m", label: "Slab thickness", suffix: "m", step: 0.005 },
  { kind: "select", key: "construction", label: "Construction", options: CONSTRUCTION_OPTIONS },
  { kind: "text", key: "concrete_grade", label: "Concrete grade", required: true, placeholder: "M40", mono: true },
];

export const assumptionsToDraft = (a: ProjectAssumptions): AssumptionsDraft => ({ ...a });

export const assumptionsFromDraft = (d: AssumptionsDraft): ProjectAssumptions => ({
  floor_height_m: num(d.floor_height_m),
  wall_thickness_m: num(d.wall_thickness_m),
  slab_thickness_m: num(d.slab_thickness_m),
  construction: d.construction,
  concrete_grade: str(d.concrete_grade) || "M40",
  notes: d.notes,
});

/* ------------------------------------------------------------------------- */
/* Extraction helpers                                                          */
/* ------------------------------------------------------------------------- */

export function emptyExtraction(): MeasurementExtraction {
  return {
    rooms: [],
    openings: [],
    walls: [],
    slabs: [],
    members: [],
    misc: [],
    assumptions: { floor_height_m: 3, wall_thickness_m: 0.2, slab_thickness_m: 0.15, construction: "conventional", concrete_grade: "M40", notes: [] },
    warnings: [],
  };
}

export function countElements(ex: MeasurementExtraction | null | undefined): number {
  if (!ex) return 0;
  return ex.rooms.length + ex.openings.length + ex.walls.length + ex.slabs.length + ex.members.length + ex.misc.length;
}

/** Elements below the "check" threshold, across every list. */
export function lowConfidenceCount(ex: MeasurementExtraction | null | undefined, threshold = 0.6): number {
  if (!ex) return 0;
  const lists: ElBase[][] = [ex.rooms, ex.openings, ex.walls, ex.slabs, ex.members, ex.misc];
  return lists.reduce((n, list) => n + list.filter((e) => e.confidence < threshold).length, 0);
}

export function upsertById<T extends ElBase>(list: T[], el: T): T[] {
  const i = list.findIndex((e) => e.id === el.id);
  if (i === -1) return [...list, el];
  return list.map((e, idx) => (idx === i ? el : e));
}

export function removeById<T extends ElBase>(list: T[], id: string): T[] {
  return list.filter((e) => e.id !== id);
}

/** JSON with sorted keys so two objects with the same values compare equal regardless of key order. */
export function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? "null";
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`).join(",")}}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "edited by a@b.com on 11-Oct-2026 09:12 UTC" — the same stamp the API writes for member / item edits. */
export function editStamp(email: string | null | undefined, now = new Date()): string {
  const dd = String(now.getUTCDate()).padStart(2, "0");
  const hh = String(now.getUTCHours()).padStart(2, "0");
  const mm = String(now.getUTCMinutes()).padStart(2, "0");
  return `edited by ${email || "reviewer"} on ${dd}-${MONTHS[now.getUTCMonth()]}-${now.getUTCFullYear()} ${hh}:${mm} UTC`;
}

/**
 * Apply a reviewer edit: when anything other than provenance changed, stamp confidence = 1
 * and replace any previous "edited by …" evidence line with a fresh one (one stamp per row).
 */
export function finalizeEdit<T extends ElBase>(original: T | null, next: T, email: string | null | undefined): T {
  if (!original) return next;
  const a = stableStringify({ ...original, confidence: 0, evidence: [] });
  const b = stableStringify({ ...next, confidence: 0, evidence: [] });
  if (a === b) return next;
  const kept = next.evidence.filter((line) => !/^edited by\s+/i.test(line.trim()));
  return { ...next, confidence: 1, evidence: [...kept, editStamp(email)] };
}
