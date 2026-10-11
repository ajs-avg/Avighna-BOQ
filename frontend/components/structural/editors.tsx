"use client";

import { Plus, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { STANDARD_DIAMETERS } from "@/lib/constants";
import type { BarGroup, ColumnTie, ColumnTieKind, SlabLayer, StairFlight, StirrupZone, StirrupZoneKind } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button, IconButton } from "../ui/Button";
import { Input, NumberInput } from "../ui/Input";
import { Select } from "../ui/Select";
import { Switch } from "../ui/Switch";

/* ------------------------------------------------------------------------- */
/* Shared bits                                                                */
/* ------------------------------------------------------------------------- */

const DIA_OPTIONS = STANDARD_DIAMETERS.map((d) => ({ value: String(d), label: `T${d}` }));

export function DiaSelect({ value, onChange, disabled, ariaLabel }: { value: number; onChange: (dia: number) => void; disabled?: boolean; ariaLabel?: string }) {
  const options = DIA_OPTIONS.some((o) => o.value === String(value)) ? DIA_OPTIONS : [...DIA_OPTIONS, { value: String(value), label: `T${value}` }];
  return <Select size="sm" aria-label={ariaLabel ?? "Diameter"} value={String(value)} onChange={(e) => onChange(Number(e.target.value))} options={options} disabled={disabled} />;
}

export function EditorSection({ title, hint, children, className, actions }: { title: ReactNode; hint?: ReactNode; children: ReactNode; className?: string; actions?: ReactNode }) {
  return (
    <section className={cn("rounded-card border border-line bg-surface", className)}>
      <header className="flex items-center justify-between gap-2 border-b border-line bg-surface-2/60 px-3.5 py-2">
        <div>
          <h5 className="text-[12.5px] font-semibold text-ink">{title}</h5>
          {hint ? <p className="text-[11.5px] text-muted">{hint}</p> : null}
        </div>
        {actions}
      </header>
      <div className="p-3.5">{children}</div>
    </section>
  );
}

function RowShell({ children, onRemove, disabled }: { children: ReactNode; onRemove: () => void; disabled?: boolean }) {
  return (
    <div className="flex items-end gap-2">
      <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-4">{children}</div>
      <IconButton label="Remove row" size="sm" className="mb-0.5 text-muted hover:bg-danger-soft hover:text-danger" onClick={onRemove} disabled={disabled}>
        <Trash2 />
      </IconButton>
    </div>
  );
}

function Labeled({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn("flex flex-col gap-1", className)}>
      <span className="text-[11px] font-medium uppercase tracking-[0.05em] text-muted">{label}</span>
      {children}
    </label>
  );
}

/* ------------------------------------------------------------------------- */
/* Bar groups: count × dia                                                    */
/* ------------------------------------------------------------------------- */

export function BarGroupListEditor({
  value,
  onChange,
  disabled,
  defaultDia = 16,
  addLabel = "Add bars",
}: {
  value: BarGroup[];
  onChange: (next: BarGroup[]) => void;
  disabled?: boolean;
  defaultDia?: number;
  addLabel?: string;
}) {
  const update = (i: number, patch: Partial<BarGroup>) => onChange(value.map((g, idx) => (idx === i ? { ...g, ...patch } : g)));
  return (
    <div className="space-y-2">
      {value.map((g, i) => (
        <RowShell key={i} onRemove={() => onChange(value.filter((_, idx) => idx !== i))} disabled={disabled}>
          <Labeled label="Nos">
            <NumberInput className="h-8" value={g.count} onValueChange={(v) => update(i, { count: v === "" ? 0 : Math.max(0, Math.round(v)) })} min={0} step={1} disabled={disabled} />
          </Labeled>
          <Labeled label="Dia">
            <DiaSelect value={g.dia_mm} onChange={(d) => update(i, { dia_mm: d })} disabled={disabled} />
          </Labeled>
          <Labeled label="Note" className="col-span-2">
            <Input className="h-8" value={g.note ?? ""} onChange={(e) => update(i, { note: e.target.value || null })} placeholder="Optional" disabled={disabled} />
          </Labeled>
        </RowShell>
      ))}
      <Button variant="ghost" size="xs" leftIcon={<Plus />} onClick={() => onChange([...value, { count: 2, dia_mm: defaultDia, note: null }])} disabled={disabled} className="text-brand hover:bg-brand-soft">
        {addLabel}
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Stirrup zones                                                              */
/* ------------------------------------------------------------------------- */

const ZONE_OPTIONS: { value: StirrupZoneKind; label: string }[] = [
  { value: "full", label: "Full length" },
  { value: "end", label: "End zones" },
  { value: "mid", label: "Mid span" },
];

export function StirrupZoneListEditor({ value, onChange, disabled }: { value: StirrupZone[]; onChange: (next: StirrupZone[]) => void; disabled?: boolean }) {
  const update = (i: number, patch: Partial<StirrupZone>) => onChange(value.map((z, idx) => (idx === i ? { ...z, ...patch } : z)));
  return (
    <div className="space-y-2">
      {value.map((z, i) => (
        <RowShell key={i} onRemove={() => onChange(value.filter((_, idx) => idx !== i))} disabled={disabled}>
          <Labeled label="Dia">
            <DiaSelect value={z.dia_mm} onChange={(d) => update(i, { dia_mm: d })} disabled={disabled} />
          </Labeled>
          <Labeled label="Spacing (mm)">
            <NumberInput className="h-8" value={z.spacing_mm} onValueChange={(v) => update(i, { spacing_mm: v === "" ? 0 : v })} min={0} step={5} disabled={disabled} />
          </Labeled>
          <Labeled label="Zone">
            <Select size="sm" value={z.zone} onChange={(e) => update(i, { zone: e.target.value as StirrupZoneKind })} options={ZONE_OPTIONS} disabled={disabled} />
          </Labeled>
          <Labeled label="Legs">
            <NumberInput className="h-8" value={z.legs} onValueChange={(v) => update(i, { legs: v === "" ? 2 : Math.max(1, Math.round(v)) })} min={1} step={1} disabled={disabled} />
          </Labeled>
        </RowShell>
      ))}
      <Button variant="ghost" size="xs" leftIcon={<Plus />} onClick={() => onChange([...value, { dia_mm: 8, spacing_mm: 150, zone: value.length ? "mid" : "full", legs: 2 }])} disabled={disabled} className="text-brand hover:bg-brand-soft">
        Add stirrup zone
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Slab / wall layers: dia @ spacing (+ bent-up)                               */
/* ------------------------------------------------------------------------- */

export function SlabLayerFields({ value, onChange, disabled, showBentUp = true }: { value: SlabLayer; onChange: (next: SlabLayer) => void; disabled?: boolean; showBentUp?: boolean }) {
  return (
    <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-4">
      <Labeled label="Dia">
        <DiaSelect value={value.dia_mm} onChange={(d) => onChange({ ...value, dia_mm: d })} disabled={disabled} />
      </Labeled>
      <Labeled label="Spacing (mm)">
        <NumberInput className="h-8" value={value.spacing_mm} onValueChange={(v) => onChange({ ...value, spacing_mm: v === "" ? 0 : v })} min={0} step={5} disabled={disabled} />
      </Labeled>
      {showBentUp ? (
        <div className="flex items-end pb-1">
          <Switch size="sm" checked={value.bent_up} onCheckedChange={(b) => onChange({ ...value, bent_up: b })} label="Alternate bent-up" disabled={disabled} />
        </div>
      ) : null}
      <Labeled label="Note" className={showBentUp ? "" : "col-span-2"}>
        <Input className="h-8" value={value.note ?? ""} onChange={(e) => onChange({ ...value, note: e.target.value || null })} placeholder="Optional" disabled={disabled} />
      </Labeled>
    </div>
  );
}

/** An optional layer: a toggle that enables the fields. */
export function OptionalLayerEditor({
  label,
  hint,
  value,
  onChange,
  disabled,
  defaultDia = 10,
  defaultSpacing = 150,
  showBentUp = true,
}: {
  label: string;
  hint?: string;
  value: SlabLayer | null | undefined;
  onChange: (next: SlabLayer | null) => void;
  disabled?: boolean;
  defaultDia?: number;
  defaultSpacing?: number;
  showBentUp?: boolean;
}) {
  const enabled = !!value;
  return (
    <div className={cn("rounded-lg border px-3 py-2.5", enabled ? "border-line bg-surface" : "border-dashed border-line bg-surface-2/40")}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[12.5px] font-semibold text-ink">{label}</p>
          {hint ? <p className="text-[11.5px] text-muted">{hint}</p> : null}
        </div>
        <Switch
          size="sm"
          checked={enabled}
          onCheckedChange={(b) => onChange(b ? { dia_mm: defaultDia, spacing_mm: defaultSpacing, bent_up: false, note: null } : null)}
          disabled={disabled}
        />
      </div>
      {value ? (
        <div className="mt-2.5">
          <SlabLayerFields value={value} onChange={onChange} disabled={disabled} showBentUp={showBentUp} />
        </div>
      ) : null}
    </div>
  );
}

export function SlabLayerListEditor({ value, onChange, disabled, addLabel = "Add layer" }: { value: SlabLayer[]; onChange: (next: SlabLayer[]) => void; disabled?: boolean; addLabel?: string }) {
  return (
    <div className="space-y-2">
      {value.map((l, i) => (
        <div key={i} className="flex items-end gap-2">
          <SlabLayerFields value={l} onChange={(next) => onChange(value.map((x, idx) => (idx === i ? next : x)))} disabled={disabled} />
          <IconButton label="Remove layer" size="sm" className="mb-0.5 text-muted hover:bg-danger-soft hover:text-danger" onClick={() => onChange(value.filter((_, idx) => idx !== i))} disabled={disabled}>
            <Trash2 />
          </IconButton>
        </div>
      ))}
      <Button variant="ghost" size="xs" leftIcon={<Plus />} onClick={() => onChange([...value, { dia_mm: 10, spacing_mm: 150, bent_up: false, note: null }])} disabled={disabled} className="text-brand hover:bg-brand-soft">
        {addLabel}
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Column ties                                                                 */
/* ------------------------------------------------------------------------- */

const TIE_OPTIONS: { value: ColumnTieKind; label: string }[] = [
  { value: "main_ring", label: "Main ring" },
  { value: "inner_tie", label: "Inner tie" },
  { value: "cross_tie", label: "Cross tie" },
];

export function ColumnTieListEditor({ value, onChange, disabled }: { value: ColumnTie[]; onChange: (next: ColumnTie[]) => void; disabled?: boolean }) {
  const update = (i: number, patch: Partial<ColumnTie>) => onChange(value.map((t, idx) => (idx === i ? { ...t, ...patch } : t)));
  return (
    <div className="space-y-2">
      {value.map((t, i) => (
        <div key={i} className="flex items-end gap-2">
          <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-5">
            <Labeled label="Dia">
              <DiaSelect value={t.dia_mm} onChange={(d) => update(i, { dia_mm: d })} disabled={disabled} />
            </Labeled>
            <Labeled label="Spacing (mm)">
              <NumberInput className="h-8" value={t.spacing_mm} onValueChange={(v) => update(i, { spacing_mm: v === "" ? 0 : v })} min={0} step={5} disabled={disabled} />
            </Labeled>
            <Labeled label="Kind">
              <Select size="sm" value={t.kind} onChange={(e) => update(i, { kind: e.target.value as ColumnTieKind })} options={TIE_OPTIONS} disabled={disabled} />
            </Labeled>
            <Labeled label="Per layer">
              <NumberInput className="h-8" value={t.per_layer} onValueChange={(v) => update(i, { per_layer: v === "" ? 1 : Math.max(1, Math.round(v)) })} min={1} step={1} disabled={disabled} />
            </Labeled>
            <Labeled label="Leg length (m)">
              <NumberInput
                className="h-8"
                value={t.leg_length_m ?? ""}
                onValueChange={(v) => update(i, { leg_length_m: v === "" ? null : v })}
                min={0}
                step={0.01}
                placeholder="auto"
                disabled={disabled || t.kind === "main_ring"}
              />
            </Labeled>
          </div>
          <IconButton label="Remove tie" size="sm" className="mb-0.5 text-muted hover:bg-danger-soft hover:text-danger" onClick={() => onChange(value.filter((_, idx) => idx !== i))} disabled={disabled}>
            <Trash2 />
          </IconButton>
        </div>
      ))}
      <Button
        variant="ghost"
        size="xs"
        leftIcon={<Plus />}
        onClick={() => onChange([...value, { dia_mm: 8, spacing_mm: 150, kind: value.length ? "inner_tie" : "main_ring", per_layer: 1, leg_length_m: null }])}
        disabled={disabled}
        className="text-brand hover:bg-brand-soft"
      >
        Add tie
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Stair flights                                                               */
/* ------------------------------------------------------------------------- */

export function StairFlightListEditor({ value, onChange, disabled }: { value: StairFlight[]; onChange: (next: StairFlight[]) => void; disabled?: boolean }) {
  const update = (i: number, patch: Partial<StairFlight>) => onChange(value.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  return (
    <div className="space-y-3">
      {value.map((f, i) => (
        <div key={i} className="rounded-lg border border-line p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <Input className="h-8 max-w-[220px] font-medium" value={f.name} onChange={(e) => update(i, { name: e.target.value })} placeholder="Flight name" aria-label="Flight name" disabled={disabled} />
            <IconButton label="Remove flight" size="sm" className="text-muted hover:bg-danger-soft hover:text-danger" onClick={() => onChange(value.filter((_, idx) => idx !== i))} disabled={disabled}>
              <Trash2 />
            </IconButton>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {(
              [
                ["width_m", "Width (m)"],
                ["waist_m", "Waist (m)"],
                ["going_m", "Going (m)"],
                ["rise_m", "Rise (m)"],
                ["landing_a_m", "Landing A (m)"],
                ["landing_b_m", "Landing B (m)"],
              ] as const
            ).map(([key, label]) => (
              <Labeled key={key} label={label}>
                <NumberInput className="h-8" value={f[key]} onValueChange={(v) => update(i, { [key]: v === "" ? 0 : v })} min={0} step={0.01} disabled={disabled} />
              </Labeled>
            ))}
          </div>
          <div className="mt-2 grid gap-2 lg:grid-cols-2">
            <OptionalLayerEditor label="Main bars" value={f.main} onChange={(l) => update(i, { main: l })} disabled={disabled} defaultDia={12} defaultSpacing={150} />
            <OptionalLayerEditor label="Distribution bars" value={f.dist} onChange={(l) => update(i, { dist: l })} disabled={disabled} defaultDia={8} defaultSpacing={200} showBentUp={false} />
          </div>
        </div>
      ))}
      <Button
        variant="ghost"
        size="xs"
        leftIcon={<Plus />}
        onClick={() =>
          onChange([
            ...value,
            {
              name: `Flight ${value.length + 1}`,
              width_m: 1.2,
              waist_m: 0.15,
              going_m: 2.7,
              rise_m: 1.5,
              landing_a_m: 0,
              landing_b_m: 0,
              main: { dia_mm: 12, spacing_mm: 150, bent_up: false, note: null },
              dist: { dia_mm: 8, spacing_mm: 200, bent_up: false, note: null },
            },
          ])
        }
        disabled={disabled}
        className="text-brand hover:bg-brand-soft"
      >
        Add flight
      </Button>
    </div>
  );
}
