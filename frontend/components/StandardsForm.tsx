"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { STANDARD_DIAMETERS } from "@/lib/constants";
import type { Standards } from "@/lib/types";
import { cn, toNumber } from "@/lib/utils";
import { Button, IconButton } from "./ui/Button";
import { Field, NumberInput } from "./ui/Input";

type NumericKey = {
  [K in keyof Standards]: Standards[K] extends number ? K : never;
}[keyof Standards];

interface FieldDef {
  key: NumericKey;
  label: string;
  unit?: string;
  step?: number;
  hint?: string;
}

interface Group {
  title: string;
  description: string;
  fields: FieldDef[];
}

const GROUPS: Group[] = [
  {
    title: "Development & anchorage",
    description: "How bar ends are extended and bent.",
    fields: [
      { key: "ld_factor", label: "Development length Ld", unit: "× d", step: 1, hint: "Ld = 39d by default" },
      { key: "anchorage_extra_d", label: "Extra at L-bend", unit: "× d", step: 1, hint: "(Ld + 10)d anchorage" },
      { key: "min_straight_anchorage_m", label: "Min straight anchorage", unit: "m", step: 0.05, hint: "MAX(10d, 0.3 m)" },
      { key: "hook_length_d", label: "Hook length per end", unit: "× d", step: 1 },
      { key: "bend_deduction_d", label: "Bend deduction per corner", unit: "× d", step: 0.1 },
      { key: "stirrup_corners", label: "Stirrup bend corners", unit: "nos", step: 1 },
    ],
  },
  {
    title: "Clear covers",
    description: "Nominal cover to reinforcement, by member type.",
    fields: [
      { key: "cover_beam_mm", label: "Beam", unit: "mm", step: 5 },
      { key: "cover_slab_mm", label: "Slab", unit: "mm", step: 5 },
      { key: "cover_column_mm", label: "Column", unit: "mm", step: 5 },
      { key: "cover_wall_mm", label: "Wall", unit: "mm", step: 5 },
      { key: "cover_stair_mm", label: "Staircase", unit: "mm", step: 5 },
    ],
  },
  {
    title: "Beam rules",
    description: "Zoning of extra bars, curtailment and stirrups.",
    fields: [
      { key: "extra_bar_span_fraction", label: "Extra top bar length", unit: "× L", step: 0.01 },
      { key: "curtail_fraction", label: "Bottom curtail from support", unit: "× L", step: 0.01 },
      { key: "end_zone_span_fraction", label: "Close-spacing stirrup zone", unit: "× L", step: 0.01 },
      { key: "stirrup_end_offset_m", label: "First stirrup offset", unit: "m", step: 0.01 },
      { key: "sfr_min_depth_m", label: "Side-face reinf. from depth", unit: "m", step: 0.05 },
    ],
  },
  {
    title: "Slab rules",
    description: "Anchorage, bent-up bars and top-bar zones.",
    fields: [
      { key: "slab_min_anchorage_m", label: "Min anchorage", unit: "m", step: 0.05, hint: "MAX(10d, 0.2 m)" },
      { key: "slab_bentup_factor", label: "Bent-up extra factor", unit: "× (D − 2c)", step: 0.01 },
      { key: "slab_dist_end_fraction", label: "Top zone at discontinuous edge", unit: "× L", step: 0.01 },
      { key: "slab_cont_edge_fraction", label: "Top zone at continuous edge", unit: "× L", step: 0.01 },
    ],
  },
];

export interface StandardsFormProps {
  value: Standards;
  onChange: (next: Standards) => void;
  readOnly?: boolean;
  /** Tighter layout for the collapsible panel on the New Measurement page. */
  compact?: boolean;
  className?: string;
}

export function StandardsForm({ value, onChange, readOnly, compact, className }: StandardsFormProps) {
  const [newDia, setNewDia] = useState<number | "">("");

  const set = <K extends keyof Standards>(key: K, v: Standards[K]) => onChange({ ...value, [key]: v });

  const dias = Object.keys(value.unit_weight_kg_per_m)
    .map((k) => Number(k))
    .filter((n) => Number.isFinite(n))
    .sort((a, b) => a - b);

  const setWeight = (dia: number, w: number | "") => {
    const next = { ...value.unit_weight_kg_per_m, [String(dia)]: w === "" ? 0 : w };
    set("unit_weight_kg_per_m", next);
  };

  const removeDia = (dia: number) => {
    const next = { ...value.unit_weight_kg_per_m };
    delete next[String(dia)];
    set("unit_weight_kg_per_m", next);
    set("diameters_in_summary", value.diameters_in_summary.filter((d) => d !== dia));
  };

  const addDia = () => {
    const d = toNumber(newDia, 0);
    if (!d || value.unit_weight_kg_per_m[String(d)] !== undefined) return;
    const w = Math.round(((d * d) / 162) * 1000) / 1000; // IS 1786 d²/162
    set("unit_weight_kg_per_m", { ...value.unit_weight_kg_per_m, [String(d)]: w });
    setNewDia("");
  };

  const toggleSummaryDia = (dia: number) => {
    const has = value.diameters_in_summary.includes(dia);
    const next = has ? value.diameters_in_summary.filter((d) => d !== dia) : [...value.diameters_in_summary, dia].sort((a, b) => a - b);
    set("diameters_in_summary", next);
  };

  return (
    <div className={cn("space-y-6", className)}>
      {GROUPS.map((g) => (
        <section key={g.title}>
          <header className="mb-3">
            <h4 className="text-[13.5px] font-semibold text-ink">{g.title}</h4>
            <p className="text-[12px] text-muted">{g.description}</p>
          </header>
          <div className={cn("grid gap-x-4 gap-y-3", compact ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4")}>
            {g.fields.map((f) => (
              <Field key={f.key} label={f.label} hint={f.hint}>
                {(id) => (
                  <NumberInput
                    id={id}
                    value={value[f.key]}
                    onValueChange={(v) => set(f.key, v === "" ? 0 : v)}
                    step={f.step ?? 0.01}
                    min={0}
                    suffix={f.unit}
                    disabled={readOnly}
                  />
                )}
              </Field>
            ))}
          </div>
        </section>
      ))}

      <section>
        <header className="mb-3">
          <h4 className="text-[13.5px] font-semibold text-ink">Unit weights</h4>
          <p className="text-[12px] text-muted">kg per metre by bar diameter (IS 1786: d² / 162). Tick the diameters to show as columns in the summary.</p>
        </header>
        <div className="overflow-hidden rounded-card border border-line">
          <table className="table-dense">
            <thead>
              <tr>
                <th className="w-24">Dia (mm)</th>
                <th className="w-40">Unit weight (kg/m)</th>
                <th className="w-32">In summary</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {dias.map((d) => (
                <tr key={d}>
                  <td className="tnum font-semibold">T{d}</td>
                  <td>
                    <NumberInput
                      aria-label={`Unit weight for ${d} mm`}
                      value={value.unit_weight_kg_per_m[String(d)] ?? ""}
                      onValueChange={(v) => setWeight(d, v)}
                      step={0.001}
                      min={0}
                      disabled={readOnly}
                      className="h-8 max-w-[140px]"
                    />
                  </td>
                  <td>
                    <label className="inline-flex items-center gap-2 text-[12.5px]">
                      <input
                        type="checkbox"
                        className="size-4 accent-brand"
                        checked={value.diameters_in_summary.includes(d)}
                        onChange={() => toggleSummaryDia(d)}
                        disabled={readOnly}
                      />
                      Show
                    </label>
                  </td>
                  <td className="text-right">
                    {!readOnly ? (
                      <IconButton label={`Remove ${d} mm`} size="xs" className="text-muted hover:bg-danger-soft hover:text-danger" onClick={() => removeDia(d)}>
                        <Trash2 />
                      </IconButton>
                    ) : null}
                  </td>
                </tr>
              ))}
              {!readOnly ? (
                <tr>
                  <td colSpan={4} className="!bg-surface">
                    <div className="flex items-center gap-2">
                      <NumberInput
                        aria-label="New diameter"
                        placeholder="Dia"
                        value={newDia}
                        onValueChange={setNewDia}
                        min={4}
                        step={1}
                        list="standard-dias"
                        className="h-8 w-24"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addDia();
                          }
                        }}
                      />
                      <datalist id="standard-dias">
                        {STANDARD_DIAMETERS.filter((d) => !dias.includes(d)).map((d) => (
                          <option key={d} value={d} />
                        ))}
                      </datalist>
                      <Button variant="secondary" size="sm" leftIcon={<Plus />} onClick={addDia} disabled={newDia === ""}>
                        Add diameter
                      </Button>
                    </div>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
