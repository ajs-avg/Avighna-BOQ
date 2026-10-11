"use client";

import { Save, X } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { MEMBER_KIND_META } from "@/lib/constants";
import type { BeamSpec, ColumnShape, ColumnSpec, MemberKind, MemberSpec, SlabSpec, StairSpec, SupportType, WallSpec } from "@/lib/types";
import { cn, errorMessage, newId } from "@/lib/utils";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Field, Input, NumberInput, Textarea } from "../ui/Input";
import { Select } from "../ui/Select";
import { Switch } from "../ui/Switch";
import {
  BarGroupListEditor,
  ColumnTieListEditor,
  EditorSection,
  OptionalLayerEditor,
  SlabLayerListEditor,
  StairFlightListEditor,
  StirrupZoneListEditor,
} from "./editors";

/* ------------------------------------------------------------------------- */
/* Blank specs                                                                 */
/* ------------------------------------------------------------------------- */

function base(tag: string) {
  return { id: newId(), tag, nos: 1, confidence: 1, evidence: [] as string[], source_sheet: null, source_bbox: null, remarks: null };
}

export function blankMember(kind: MemberKind): MemberSpec {
  switch (kind) {
    case "beam":
      return {
        ...base("B1"),
        kind: "beam",
        span_m: 4.5,
        width_m: 0.23,
        depth_m: 0.6,
        bottom_bars: [{ count: 3, dia_mm: 16, note: null }],
        top_bars: [{ count: 2, dia_mm: 12, note: null }],
        extra_top_left: [],
        extra_top_right: [],
        extra_bottom_mid: [],
        bottom_curtail: [],
        sfr_bars: [],
        stirrups: [{ dia_mm: 8, spacing_mm: 150, zone: "full", legs: 2 }],
        left_support: "continuous",
        right_support: "continuous",
      };
    case "slab":
      return {
        ...base("S1"),
        kind: "slab",
        length_m: 3.5,
        width_m: 4.5,
        thickness_m: 0.15,
        short_main: { dia_mm: 10, spacing_mm: 150, bent_up: true, note: null },
        long_main: { dia_mm: 8, spacing_mm: 150, bent_up: true, note: null },
        short_top_dist_end: null,
        long_top_dist_end: null,
        short_top_cont_edge: null,
        long_top_cont_edge: null,
        extra_top: [],
        one_way: false,
      };
    case "column":
      return {
        ...base("C1"),
        kind: "column",
        length_m: 0.3,
        width_m: 0.6,
        height_m: 3.0,
        vertical_bars: [{ count: 8, dia_mm: 16, note: null }],
        ties: [{ dia_mm: 8, spacing_mm: 150, kind: "main_ring", per_layer: 1, leg_length_m: null }],
        lap_at_floor: true,
        shape: "rectangular",
      };
    case "wall":
      return {
        ...base("W1"),
        kind: "wall",
        length_m: 3.0,
        thickness_m: 0.2,
        height_m: 3.0,
        vertical: { dia_mm: 10, spacing_mm: 150, bent_up: false, note: null },
        horizontal: { dia_mm: 8, spacing_mm: 150, bent_up: false, note: null },
        faces: 2,
        starter_lap: true,
      };
    case "stair":
      return {
        ...base("ST1"),
        kind: "stair",
        flights: [
          {
            name: "Flight 1",
            width_m: 1.2,
            waist_m: 0.15,
            going_m: 2.7,
            rise_m: 1.5,
            landing_a_m: 1.2,
            landing_b_m: 0,
            main: { dia_mm: 12, spacing_mm: 150, bent_up: false, note: null },
            dist: { dia_mm: 8, spacing_mm: 200, bent_up: false, note: null },
          },
        ],
      };
  }
}

/* ------------------------------------------------------------------------- */
/* Editor                                                                      */
/* ------------------------------------------------------------------------- */

export interface MemberEditorProps {
  kind: MemberKind;
  initial?: MemberSpec | null;
  onSave: (spec: MemberSpec) => Promise<void>;
  onCancel: () => void;
  className?: string;
}

export function MemberEditor({ kind, initial, onSave, onCancel, className }: MemberEditorProps) {
  const [draft, setDraft] = useState<MemberSpec>(() => (initial ? structuredClone(initial) : blankMember(kind)));
  const [verify, setVerify] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isNew = !initial;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!draft.tag.trim()) {
      setError("Member tag is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSave({ ...draft, tag: draft.tag.trim(), confidence: verify ? 1 : draft.confidence });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className={cn("space-y-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="text-[14px] font-semibold text-ink">
            {isNew ? `Add ${MEMBER_KIND_META[kind].label.toLowerCase()}` : `Edit ${MEMBER_KIND_META[kind].label.toLowerCase()} ${initial?.tag ?? ""}`}
          </h4>
          <p className="text-[12px] text-muted">Saving recalculates the schedule and the summary.</p>
        </div>
        <Switch size="sm" checked={verify} onCheckedChange={setVerify} label="Mark as verified" description="Sets confidence to 100%" disabled={busy} />
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}

      <EditorSection title="Identity">
        <div className="grid gap-3 sm:grid-cols-[1fr_120px_2fr]">
          <Field label="Tag" required>
            {(id) => <Input id={id} value={draft.tag} onChange={(e) => setDraft({ ...draft, tag: e.target.value })} placeholder="e.g. B1A" disabled={busy} />}
          </Field>
          <Field label="Nos">
            {(id) => <NumberInput id={id} value={draft.nos} onValueChange={(v) => setDraft({ ...draft, nos: v === "" ? 1 : Math.max(1, Math.round(v)) })} min={1} step={1} disabled={busy} />}
          </Field>
          <Field label="Remarks">
            {(id) => <Input id={id} value={draft.remarks ?? ""} onChange={(e) => setDraft({ ...draft, remarks: e.target.value || null })} placeholder="Optional" disabled={busy} />}
          </Field>
        </div>
      </EditorSection>

      {draft.kind === "beam" ? <BeamForm draft={draft} onChange={setDraft} busy={busy} /> : null}
      {draft.kind === "slab" ? <SlabForm draft={draft} onChange={setDraft} busy={busy} /> : null}
      {draft.kind === "column" ? <ColumnForm draft={draft} onChange={setDraft} busy={busy} /> : null}
      {draft.kind === "wall" ? <WallForm draft={draft} onChange={setDraft} busy={busy} /> : null}
      {draft.kind === "stair" ? <StairForm draft={draft} onChange={setDraft} busy={busy} /> : null}

      {initial?.evidence.length ? (
        <EditorSection title="Evidence from the drawing" hint="Verbatim fragments the extractor relied on.">
          <ul className="space-y-1 font-mono text-[11.5px] text-muted">
            {initial.evidence.map((ev, i) => (
              <li key={i} className="truncate" title={ev}>
                {ev}
              </li>
            ))}
          </ul>
        </EditorSection>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" leftIcon={<X />} onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" leftIcon={<Save />} loading={busy}>
          {isNew ? "Add member" : "Save & recalculate"}
        </Button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------------- */
/* Per-kind forms                                                              */
/* ------------------------------------------------------------------------- */

function Dims({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{children}</div>;
}

function NumField({ label, value, onChange, unit, step = 0.01, busy, hint }: { label: string; value: number; onChange: (v: number) => void; unit?: string; step?: number; busy?: boolean; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => <NumberInput id={id} value={value} onValueChange={(v) => onChange(v === "" ? 0 : v)} min={0} step={step} suffix={unit} disabled={busy} />}
    </Field>
  );
}

const SUPPORT_OPTIONS: { value: SupportType; label: string }[] = [
  { value: "continuous", label: "Continuous" },
  { value: "end", label: "End (discontinuous)" },
];

function BeamForm({ draft, onChange, busy }: { draft: BeamSpec; onChange: (d: BeamSpec) => void; busy: boolean }) {
  const set = <K extends keyof BeamSpec>(k: K, v: BeamSpec[K]) => onChange({ ...draft, [k]: v });
  return (
    <>
      <EditorSection title="Geometry" hint="Clear span and section (m).">
        <Dims>
          <NumField label="Span L" value={draft.span_m} onChange={(v) => set("span_m", v)} unit="m" busy={busy} />
          <NumField label="Width B" value={draft.width_m} onChange={(v) => set("width_m", v)} unit="m" step={0.005} busy={busy} />
          <NumField label="Depth D" value={draft.depth_m} onChange={(v) => set("depth_m", v)} unit="m" step={0.005} busy={busy} />
          <Field label="Left support">
            {(id) => <Select id={id} value={draft.left_support} onChange={(e) => set("left_support", e.target.value as SupportType)} options={SUPPORT_OPTIONS} disabled={busy} />}
          </Field>
          <Field label="Right support">
            {(id) => <Select id={id} value={draft.right_support} onChange={(e) => set("right_support", e.target.value as SupportType)} options={SUPPORT_OPTIONS} disabled={busy} />}
          </Field>
        </Dims>
      </EditorSection>
      <div className="grid gap-4 lg:grid-cols-2">
        <EditorSection title="Bottom bars" hint="Through bars at the bottom.">
          <BarGroupListEditor value={draft.bottom_bars} onChange={(v) => set("bottom_bars", v)} disabled={busy} defaultDia={16} />
        </EditorSection>
        <EditorSection title="Top bars" hint="Through bars at the top.">
          <BarGroupListEditor value={draft.top_bars} onChange={(v) => set("top_bars", v)} disabled={busy} defaultDia={12} />
        </EditorSection>
        <EditorSection title="Extra top — left" hint="L/3 extra at the left support.">
          <BarGroupListEditor value={draft.extra_top_left} onChange={(v) => set("extra_top_left", v)} disabled={busy} defaultDia={16} />
        </EditorSection>
        <EditorSection title="Extra top — right" hint="L/3 extra at the right support.">
          <BarGroupListEditor value={draft.extra_top_right} onChange={(v) => set("extra_top_right", v)} disabled={busy} defaultDia={16} />
        </EditorSection>
        <EditorSection title="Extra bottom — mid" hint="Extra bottom bars in mid-span.">
          <BarGroupListEditor value={draft.extra_bottom_mid} onChange={(v) => set("extra_bottom_mid", v)} disabled={busy} defaultDia={16} />
        </EditorSection>
        <EditorSection title="Bottom curtail" hint="Bottom bars stopping 0.1L from supports.">
          <BarGroupListEditor value={draft.bottom_curtail} onChange={(v) => set("bottom_curtail", v)} disabled={busy} defaultDia={16} />
        </EditorSection>
        <EditorSection title="Side-face reinforcement" hint="Per face; used when depth ≥ SFR threshold.">
          <BarGroupListEditor value={draft.sfr_bars} onChange={(v) => set("sfr_bars", v)} disabled={busy} defaultDia={10} />
        </EditorSection>
        <EditorSection title="Stirrups" hint="Zones: end (close spacing) / mid / full length.">
          <StirrupZoneListEditor value={draft.stirrups} onChange={(v) => set("stirrups", v)} disabled={busy} />
        </EditorSection>
      </div>
    </>
  );
}

function SlabForm({ draft, onChange, busy }: { draft: SlabSpec; onChange: (d: SlabSpec) => void; busy: boolean }) {
  const set = <K extends keyof SlabSpec>(k: K, v: SlabSpec[K]) => onChange({ ...draft, [k]: v });
  return (
    <>
      <EditorSection title="Geometry" hint="Short span Lx, long span Ly and thickness (m).">
        <Dims>
          <NumField label="Short span Lx" value={draft.length_m} onChange={(v) => set("length_m", v)} unit="m" busy={busy} />
          <NumField label="Long span Ly" value={draft.width_m} onChange={(v) => set("width_m", v)} unit="m" busy={busy} />
          <NumField label="Thickness" value={draft.thickness_m} onChange={(v) => set("thickness_m", v)} unit="m" step={0.005} busy={busy} />
          <div className="flex items-end pb-1">
            <Switch size="sm" checked={draft.one_way} onCheckedChange={(b) => set("one_way", b)} label="One-way slab" disabled={busy} />
          </div>
        </Dims>
      </EditorSection>
      <div className="grid gap-3 lg:grid-cols-2">
        <OptionalLayerEditor label="Short-span main" hint="Bottom bars along Lx" value={draft.short_main} onChange={(l) => set("short_main", l)} disabled={busy} defaultDia={10} />
        <OptionalLayerEditor label="Long-span main" hint="Bottom bars along Ly" value={draft.long_main} onChange={(l) => set("long_main", l)} disabled={busy} defaultDia={8} />
        <OptionalLayerEditor label="Short top — discontinuous edge" hint="L/7 zone" value={draft.short_top_dist_end} onChange={(l) => set("short_top_dist_end", l)} disabled={busy} showBentUp={false} />
        <OptionalLayerEditor label="Long top — discontinuous edge" hint="L/7 zone" value={draft.long_top_dist_end} onChange={(l) => set("long_top_dist_end", l)} disabled={busy} showBentUp={false} />
        <OptionalLayerEditor label="Short top — continuous edge" hint="0.3L zone" value={draft.short_top_cont_edge} onChange={(l) => set("short_top_cont_edge", l)} disabled={busy} showBentUp={false} />
        <OptionalLayerEditor label="Long top — continuous edge" hint="0.3L zone" value={draft.long_top_cont_edge} onChange={(l) => set("long_top_cont_edge", l)} disabled={busy} showBentUp={false} />
      </div>
      <EditorSection title="Extra top layers" hint="Additional top reinforcement (full length).">
        <SlabLayerListEditor value={draft.extra_top} onChange={(v) => set("extra_top", v)} disabled={busy} addLabel="Add extra top layer" />
      </EditorSection>
    </>
  );
}

const SHAPE_OPTIONS: { value: ColumnShape; label: string }[] = [
  { value: "rectangular", label: "Rectangular" },
  { value: "L", label: "L-shaped" },
  { value: "T", label: "T-shaped" },
  { value: "circular", label: "Circular" },
];

function ColumnForm({ draft, onChange, busy }: { draft: ColumnSpec; onChange: (d: ColumnSpec) => void; busy: boolean }) {
  const set = <K extends keyof ColumnSpec>(k: K, v: ColumnSpec[K]) => onChange({ ...draft, [k]: v });
  return (
    <>
      <EditorSection title="Geometry" hint="Section a × b and floor-to-floor height (m).">
        <Dims>
          <NumField label="Section a" value={draft.length_m} onChange={(v) => set("length_m", v)} unit="m" step={0.005} busy={busy} />
          <NumField label="Section b" value={draft.width_m} onChange={(v) => set("width_m", v)} unit="m" step={0.005} busy={busy} />
          <NumField label="Height" value={draft.height_m} onChange={(v) => set("height_m", v)} unit="m" busy={busy} />
          <Field label="Shape">{(id) => <Select id={id} value={draft.shape} onChange={(e) => set("shape", e.target.value as ColumnShape)} options={SHAPE_OPTIONS} disabled={busy} />}</Field>
          <div className="flex items-end pb-1">
            <Switch size="sm" checked={draft.lap_at_floor} onCheckedChange={(b) => set("lap_at_floor", b)} label="Lap at floor level" disabled={busy} />
          </div>
        </Dims>
      </EditorSection>
      <div className="grid gap-4 lg:grid-cols-2">
        <EditorSection title="Vertical bars">
          <BarGroupListEditor value={draft.vertical_bars} onChange={(v) => set("vertical_bars", v)} disabled={busy} defaultDia={16} />
        </EditorSection>
        <EditorSection title="Ties" hint="Main ring plus inner / cross ties per layer.">
          <ColumnTieListEditor value={draft.ties} onChange={(v) => set("ties", v)} disabled={busy} />
        </EditorSection>
      </div>
    </>
  );
}

function WallForm({ draft, onChange, busy }: { draft: WallSpec; onChange: (d: WallSpec) => void; busy: boolean }) {
  const set = <K extends keyof WallSpec>(k: K, v: WallSpec[K]) => onChange({ ...draft, [k]: v });
  return (
    <>
      <EditorSection title="Geometry" hint="Length, thickness and height (m).">
        <Dims>
          <NumField label="Length" value={draft.length_m} onChange={(v) => set("length_m", v)} unit="m" busy={busy} />
          <NumField label="Thickness" value={draft.thickness_m} onChange={(v) => set("thickness_m", v)} unit="m" step={0.005} busy={busy} />
          <NumField label="Height" value={draft.height_m} onChange={(v) => set("height_m", v)} unit="m" busy={busy} />
          <Field label="Mesh faces">
            {(id) => (
              <Select
                id={id}
                value={String(draft.faces)}
                onChange={(e) => set("faces", Number(e.target.value))}
                options={[
                  { value: "1", label: "Single mesh" },
                  { value: "2", label: "Double mesh" },
                ]}
                disabled={busy}
              />
            )}
          </Field>
          <div className="flex items-end pb-1">
            <Switch size="sm" checked={draft.starter_lap} onCheckedChange={(b) => set("starter_lap", b)} label="Starter lap" disabled={busy} />
          </div>
        </Dims>
      </EditorSection>
      <div className="grid gap-3 lg:grid-cols-2">
        <OptionalLayerEditor label="Vertical bars" value={draft.vertical} onChange={(l) => set("vertical", l)} disabled={busy} showBentUp={false} defaultDia={10} />
        <OptionalLayerEditor label="Horizontal bars" value={draft.horizontal} onChange={(l) => set("horizontal", l)} disabled={busy} showBentUp={false} defaultDia={8} />
      </div>
    </>
  );
}

function StairForm({ draft, onChange, busy }: { draft: StairSpec; onChange: (d: StairSpec) => void; busy: boolean }) {
  return (
    <EditorSection title="Flights" hint="Each flight with its landings and reinforcement.">
      <StairFlightListEditor value={draft.flights} onChange={(v) => onChange({ ...draft, flights: v })} disabled={busy} />
    </EditorSection>
  );
}

/** Convenience used by the fit-out editor as well: textarea with label. */
export function RemarksField({ value, onChange, disabled }: { value: string | null | undefined; onChange: (v: string | null) => void; disabled?: boolean }) {
  return <Field label="Remarks">{(id) => <Textarea id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} disabled={disabled} />}</Field>;
}
