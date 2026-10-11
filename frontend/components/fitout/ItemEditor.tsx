"use client";

import { Save, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { BASIS_META } from "@/lib/constants";
import { unitLabel } from "@/lib/format";
import { DIVISIONS, DIVISION_LABELS, QTY_BASES, UNITS, type Division, type FitoutItem, type QtyBasis, type Unit } from "@/lib/types";
import { cn, errorMessage, newId, splitList } from "@/lib/utils";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Field, Input, NumberInput, Textarea } from "../ui/Input";
import { Select } from "../ui/Select";

export function blankItem(defaults: Partial<FitoutItem> = {}): FitoutItem {
  return {
    id: newId(),
    division: "finishes",
    section: "",
    code: null,
    description: "",
    unit: "m2",
    qty: 0,
    qty_basis: "manual",
    rooms: [],
    size_label: null,
    specification: null,
    confidence: 1,
    evidence: [],
    source_sheet: null,
    source_bbox: null,
    rate: null,
    remarks: null,
    ...defaults,
  };
}

export interface ItemEditorProps {
  initial?: FitoutItem | null;
  defaults?: Partial<FitoutItem>;
  /** Existing section names, offered as suggestions. */
  sections?: string[];
  rooms?: string[];
  currency: string;
  onSave: (item: FitoutItem) => Promise<void>;
  onCancel: () => void;
  className?: string;
}

export function ItemEditor({ initial, defaults, sections = [], rooms = [], currency, onSave, onCancel, className }: ItemEditorProps) {
  const [draft, setDraft] = useState<FitoutItem>(() => (initial ? structuredClone(initial) : blankItem(defaults)));
  const [roomsText, setRoomsText] = useState<string>(() => (initial?.rooms ?? defaults?.rooms ?? []).join(", "));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isNew = !initial;

  const set = <K extends keyof FitoutItem>(k: K, v: FitoutItem[K]) => setDraft((d) => ({ ...d, [k]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!draft.description.trim()) {
      setError("Description is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const item: FitoutItem = {
        ...draft,
        description: draft.description.trim(),
        section: draft.section.trim(),
        code: draft.code?.trim() || null,
        rooms: splitList(roomsText),
        // Any hand edit to the quantity is "manual" unless the reviewer says otherwise.
        qty_basis: initial && initial.qty !== draft.qty && draft.qty_basis === initial.qty_basis ? "manual" : draft.qty_basis,
      };
      await onSave(item);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  const sectionListId = `sections-${draft.id}`;
  const roomsListId = `rooms-${draft.id}`;

  return (
    <form onSubmit={submit} className={cn("space-y-4", className)}>
      <div>
        <h4 className="text-[14px] font-semibold text-ink">{isNew ? "Add BOQ item" : `Edit ${initial?.code ? `${initial.code} · ` : ""}${initial?.description ?? ""}`}</h4>
        <p className="text-[12px] text-muted">Saving recalculates the BOQ sections and totals.</p>
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Division" required>
          {(id) => (
            <Select id={id} value={draft.division} onChange={(e) => set("division", e.target.value as Division)} options={DIVISIONS.map((d) => ({ value: d, label: DIVISION_LABELS[d] }))} disabled={busy} />
          )}
        </Field>
        <Field label="Section" hint="e.g. Floor Finishes, Joinery, Chairs">
          {(id) => (
            <>
              <Input id={id} value={draft.section} onChange={(e) => set("section", e.target.value)} list={sectionListId} placeholder="Section" disabled={busy} />
              <datalist id={sectionListId}>
                {sections.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </>
          )}
        </Field>
        <Field label="Code" hint="From the finishes / FF&E legend">
          {(id) => <Input id={id} value={draft.code ?? ""} onChange={(e) => set("code", e.target.value || null)} placeholder="FC-201" className="font-mono" disabled={busy} />}
        </Field>
        <Field label="Basis">
          {(id) => (
            <Select id={id} value={draft.qty_basis} onChange={(e) => set("qty_basis", e.target.value as QtyBasis)} options={QTY_BASES.map((b) => ({ value: b, label: BASIS_META[b].label }))} disabled={busy} />
          )}
        </Field>
        <Field label="Description" required className="sm:col-span-2 lg:col-span-4">
          {(id) => <Textarea id={id} value={draft.description} onChange={(e) => set("description", e.target.value)} className="min-h-[64px]" required disabled={busy} />}
        </Field>
        <Field label="Quantity" required>
          {(id) => <NumberInput id={id} value={draft.qty} onValueChange={(v) => set("qty", v === "" ? 0 : v)} min={0} step={0.01} disabled={busy} />}
        </Field>
        <Field label="Unit" required>
          {(id) => <Select id={id} value={draft.unit} onChange={(e) => set("unit", e.target.value as Unit)} options={UNITS.map((u) => ({ value: u, label: unitLabel(u) }))} disabled={busy} />}
        </Field>
        <Field label={`Rate (${currency})`} hint="Optional — enables amounts">
          {(id) => <NumberInput id={id} value={draft.rate ?? ""} onValueChange={(v) => set("rate", v === "" ? null : v)} min={0} step={0.01} placeholder="—" disabled={busy} />}
        </Field>
        <Field label="Size">
          {(id) => <Input id={id} value={draft.size_label ?? ""} onChange={(e) => set("size_label", e.target.value || null)} placeholder="3375 L × 700 W × 1100 H" disabled={busy} />}
        </Field>
        <Field label="Rooms / spaces" hint="Comma separated" className="sm:col-span-2">
          {(id) => (
            <>
              <Input id={id} value={roomsText} onChange={(e) => setRoomsText(e.target.value)} list={roomsListId} placeholder="Reception, Sales lounge" disabled={busy} />
              <datalist id={roomsListId}>
                {rooms.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>
            </>
          )}
        </Field>
        <Field label="Specification" className="sm:col-span-2">
          {(id) => <Input id={id} value={draft.specification ?? ""} onChange={(e) => set("specification", e.target.value || null)} placeholder="Brand / model / finish reference" disabled={busy} />}
        </Field>
        <Field label="Remarks" className="sm:col-span-2 lg:col-span-4">
          {(id) => <Input id={id} value={draft.remarks ?? ""} onChange={(e) => set("remarks", e.target.value || null)} placeholder="Optional" disabled={busy} />}
        </Field>
      </div>

      {initial?.evidence.length ? (
        <div className="rounded-lg border border-line bg-surface-2/60 px-3 py-2">
          <p className="text-[11.5px] font-semibold uppercase tracking-[0.05em] text-muted">Evidence</p>
          <ul className="mt-1 space-y-0.5 font-mono text-[11.5px] text-muted">
            {initial.evidence.map((ev, i) => (
              <li key={i} className="truncate" title={ev}>
                {ev}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" leftIcon={<X />} onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" leftIcon={<Save />} loading={busy}>
          {isNew ? "Add item" : "Save & recalculate"}
        </Button>
      </div>
    </form>
  );
}
