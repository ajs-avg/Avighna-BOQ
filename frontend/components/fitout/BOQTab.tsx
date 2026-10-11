"use client";

import { ClipboardList, Pencil, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { addItem, deleteItem, patchItem } from "@/lib/api";
import { formatInt, formatMoney, formatNumber, formatQtyByUnit, unitLabel } from "@/lib/format";
import { DIVISION_LABELS, type BOQLine, type BOQSection, type Division, type FitoutItem, type JobRecord } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { BasisBadge } from "../BasisBadge";
import { ConfidenceBadge } from "../ConfidenceBadge";
import { EditedByNote } from "../EditedByNote";
import { Chip } from "../ui/Badge";
import { Button, IconButton } from "../ui/Button";
import { Card } from "../ui/Card";
import { useConfirm } from "../ui/ConfirmDialog";
import { EmptyState } from "../ui/EmptyState";
import { NumberInput } from "../ui/Input";
import { Table, TableWrap } from "../ui/Table";
import { useToast } from "../ui/Toast";
import { ItemEditor } from "./ItemEditor";

export interface BOQTabProps {
  job: JobRecord;
  onJobUpdate: (job: JobRecord) => void;
  readOnly?: boolean;
  focusDivision?: Division | null;
}

interface DivisionGroup {
  division: Division;
  label: string;
  sections: BOQSection[];
  lineCount: number;
  amount: number;
  qtyByUnit: Record<string, number>;
}

export function BOQTab({ job, onJobUpdate, readOnly, focusDivision }: BOQTabProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const currency = job.currency || job.boq?.summary.currency || "AED";

  const items = useMemo(() => new Map(job.fitout_items.map((i) => [i.id, i])), [job.fitout_items]);
  const sectionNames = useMemo(() => Array.from(new Set(job.fitout_items.map((i) => i.section).filter(Boolean))).sort(), [job.fitout_items]);
  const roomNames = useMemo(() => Array.from(new Set([...job.rooms.map((r) => r.name), ...job.fitout_items.flatMap((i) => i.rooms)])).sort(), [job.rooms, job.fitout_items]);

  const groups = useMemo<DivisionGroup[]>(() => {
    const map = new Map<Division, DivisionGroup>();
    for (const sec of job.boq?.sections ?? []) {
      const g = map.get(sec.division) ?? { division: sec.division, label: sec.division_label || DIVISION_LABELS[sec.division], sections: [], lineCount: 0, amount: 0, qtyByUnit: {} };
      g.sections.push(sec);
      g.lineCount += sec.lines.length;
      g.amount += sec.amount;
      for (const [u, q] of Object.entries(sec.qty_by_unit)) g.qtyByUnit[u] = (g.qtyByUnit[u] ?? 0) + q;
      map.set(sec.division, g);
    }
    return Array.from(map.values());
  }, [job.boq]);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState<Division | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const priced = (job.boq?.summary.priced_lines ?? 0) > 0;

  const save = async (item: FitoutItem) => {
    const updated = await patchItem(job.id, item.id, item);
    onJobUpdate(updated);
    setEditingId(null);
    toast.success("Item updated", "BOQ recalculated.");
  };

  const add = async (item: FitoutItem) => {
    const updated = await addItem(job.id, item);
    onJobUpdate(updated);
    setAdding(null);
    toast.success("Item added");
  };

  const setRate = async (line: BOQLine, rate: number | null) => {
    const current = items.get(line.item_id)?.rate ?? line.rate ?? null;
    if ((current ?? null) === (rate ?? null)) return;
    setBusyId(line.item_id);
    try {
      const updated = await patchItem(job.id, line.item_id, { rate });
      onJobUpdate(updated);
    } catch (err) {
      toast.error("Could not update rate", errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (line: BOQLine) => {
    const ok = await confirm({
      title: "Delete this BOQ item?",
      message: `${line.code ? `${line.code} · ` : ""}${line.description}`,
      confirmLabel: "Delete",
      danger: true,
      onConfirm: async () => {
        setBusyId(line.item_id);
        try {
          const updated = await deleteItem(job.id, line.item_id);
          onJobUpdate(updated);
        } catch (err) {
          toast.error("Could not delete", errorMessage(err));
          throw err;
        } finally {
          setBusyId(null);
        }
      },
    });
    if (ok) toast.success("Item deleted");
  };

  if (!job.boq || groups.length === 0) {
    return (
      <div className="space-y-4">
        {adding ? (
          <Card className="border-brand/40 p-5 shadow-pop animate-pop-in">
            <ItemEditor defaults={{ division: adding }} sections={sectionNames} rooms={roomNames} currency={currency} onSave={add} onCancel={() => setAdding(null)} />
          </Card>
        ) : null}
        <Card>
          <EmptyState
            icon={<ClipboardList />}
            title="No BOQ lines yet"
            description={readOnly ? "Nothing measurable was found on the drawings." : "Nothing measurable was found on the drawings. You can add items manually."}
            action={
              !readOnly && !adding ? (
                <Button size="sm" leftIcon={<Plus />} onClick={() => setAdding("finishes")}>
                  Add item
                </Button>
              ) : undefined
            }
          />
        </Card>
      </div>
    );
  }

  const columnCount = 11;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-muted">
          <span className="font-semibold text-ink">{formatInt(job.boq.summary.line_count)}</span> lines across {groups.length} division{groups.length === 1 ? "" : "s"}
          {priced ? (
            <>
              {" "}
              · <span className="tnum font-semibold text-ink">{formatMoney(job.boq.summary.grand_total, currency)}</span> incl. VAT
            </>
          ) : null}
        </p>
        {!readOnly ? (
          <Button size="sm" leftIcon={<Plus />} onClick={() => setAdding(focusDivision ?? groups[0].division)} disabled={!!adding}>
            Add item
          </Button>
        ) : null}
      </div>

      {adding ? (
        <Card className="border-brand/40 p-5 shadow-pop animate-pop-in">
          <ItemEditor defaults={{ division: adding }} sections={sectionNames} rooms={roomNames} currency={currency} onSave={add} onCancel={() => setAdding(null)} />
        </Card>
      ) : null}

      {groups.map((g) => (
        <Card key={g.division} id={`division-${g.division}`} className={cn("overflow-hidden", focusDivision === g.division && "ring-2 ring-brand/30")}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface-2/60 px-5 py-3">
            <div>
              <h3 className="text-[14px] font-semibold text-ink">{g.label}</h3>
              <p className="tnum text-[12px] text-muted">
                {formatInt(g.lineCount)} line{g.lineCount === 1 ? "" : "s"}
                {formatQtyByUnit(g.qtyByUnit) ? ` · ${formatQtyByUnit(g.qtyByUnit)}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {priced && g.amount ? <span className="tnum text-[14px] font-semibold text-brand">{formatMoney(g.amount, currency)}</span> : null}
              {!readOnly ? (
                <IconButton label={`Add item to ${g.label}`} size="xs" variant="secondary" onClick={() => setAdding(g.division)}>
                  <Plus />
                </IconButton>
              ) : null}
            </div>
          </div>
          <TableWrap flush>
            <Table>
              <thead>
                <tr>
                  <th className="w-12">Item</th>
                  <th>Code</th>
                  <th className="min-w-[280px]">Description</th>
                  <th className="min-w-[140px]">Rooms</th>
                  <th className="num">Qty</th>
                  <th>Unit</th>
                  <th className="num w-28">Rate</th>
                  <th className="num">Amount</th>
                  <th>Basis</th>
                  <th>Confidence</th>
                  <th className="w-20" />
                </tr>
              </thead>
              {g.sections.map((sec) => (
                <tbody key={`${sec.division}-${sec.section}`}>
                  <tr>
                    <td colSpan={columnCount} className="!bg-surface-3/70 py-1.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">
                      {sec.section || "General"}
                      {formatQtyByUnit(sec.qty_by_unit) ? <span className="tnum ml-2 font-normal normal-case tracking-normal">· {formatQtyByUnit(sec.qty_by_unit)}</span> : null}
                      {priced && sec.amount ? <span className="tnum ml-2 font-normal normal-case tracking-normal text-ink">· {formatMoney(sec.amount, currency)}</span> : null}
                    </td>
                  </tr>
                  {sec.lines.map((line) => {
                    const item = items.get(line.item_id);
                    const editing = editingId === line.item_id;
                    const busy = busyId === line.item_id;
                    return (
                      <LineRows
                        key={line.item_id}
                        line={line}
                        item={item}
                        editing={editing}
                        busy={busy}
                        readOnly={!!readOnly}
                        currency={currency}
                        sections={sectionNames}
                        rooms={roomNames}
                        columnCount={columnCount}
                        onEdit={() => setEditingId(line.item_id)}
                        onCancel={() => setEditingId(null)}
                        onSave={save}
                        onDelete={() => void remove(line)}
                        onRate={(r) => void setRate(line, r)}
                      />
                    );
                  })}
                </tbody>
              ))}
            </Table>
          </TableWrap>
        </Card>
      ))}
    </div>
  );
}

function LineRows({
  line,
  item,
  editing,
  busy,
  readOnly,
  currency,
  sections,
  rooms,
  columnCount,
  onEdit,
  onCancel,
  onSave,
  onDelete,
  onRate,
}: {
  line: BOQLine;
  item?: FitoutItem;
  editing: boolean;
  busy: boolean;
  readOnly: boolean;
  currency: string;
  sections: string[];
  rooms: string[];
  columnCount: number;
  onEdit: () => void;
  onCancel: () => void;
  onSave: (item: FitoutItem) => Promise<void>;
  onDelete: () => void;
  onRate: (rate: number | null) => void;
}) {
  const [rateDraft, setRateDraft] = useState<number | "">(line.rate ?? "");
  const isCount = line.unit === "nos" || line.unit === "item" || line.unit === "ls";
  const shownRooms = line.rooms.slice(0, 2);
  const extraRooms = line.rooms.length - shownRooms.length;

  return (
    <>
      <tr className={cn("row-hover", editing && "[&>td]:!bg-brand-tint/70")}>
        <td className="font-semibold text-muted">{line.item_ref}</td>
        <td>{line.code ? <Chip>{line.code}</Chip> : <span className="text-muted/50">—</span>}</td>
        <td className="max-w-[460px]">
          <p className="line-clamp-2 text-ink" title={line.description}>
            {line.description}
          </p>
          {item?.size_label || item?.specification ? (
            <p className="truncate text-[11.5px] text-muted" title={[item.size_label, item.specification].filter(Boolean).join(" · ")}>
              {[item.size_label, item.specification].filter(Boolean).join(" · ")}
            </p>
          ) : null}
          <EditedByNote evidence={item?.evidence ?? line.evidence} />
        </td>
        <td>
          <div className="flex flex-wrap gap-1" title={line.rooms.join(", ")}>
            {shownRooms.map((r) => (
              <Chip key={r} className="max-w-[120px] truncate font-sans">
                {r}
              </Chip>
            ))}
            {extraRooms > 0 ? <Chip className="font-sans text-muted">+{extraRooms}</Chip> : null}
            {line.rooms.length === 0 ? <span className="text-muted/50">—</span> : null}
          </div>
        </td>
        <td className="num font-semibold">{formatNumber(line.qty, isCount ? 0 : 2)}</td>
        <td className="text-muted">{unitLabel(line.unit)}</td>
        <td className="num">
          {readOnly ? (
            line.rate != null ? formatNumber(line.rate, 2) : <span className="text-muted/50">—</span>
          ) : (
            <NumberInput
              aria-label={`Rate for ${line.description}`}
              value={rateDraft}
              onValueChange={setRateDraft}
              onBlur={() => onRate(rateDraft === "" ? null : rateDraft)}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              min={0}
              step={0.01}
              placeholder="—"
              disabled={busy}
              className="h-7 w-24 text-right"
            />
          )}
        </td>
        <td className="num font-semibold">{line.amount != null ? formatMoney(line.amount, currency) : <span className="text-muted/50">—</span>}</td>
        <td>
          <BasisBadge basis={line.qty_basis} />
        </td>
        <td>
          <ConfidenceBadge value={line.confidence} size="xs" />
        </td>
        <td>
          {!readOnly ? (
            <div className="flex justify-end gap-0.5">
              <IconButton label="Edit item" size="xs" onClick={onEdit} disabled={editing || !item}>
                <Pencil />
              </IconButton>
              <IconButton label="Delete item" size="xs" className="text-muted hover:bg-danger-soft hover:text-danger" onClick={onDelete} loading={busy}>
                <Trash2 />
              </IconButton>
            </div>
          ) : null}
        </td>
      </tr>
      {editing && item ? (
        <tr>
          <td colSpan={columnCount} className="!bg-surface-2/50 !p-0">
            <div className="border-l-[3px] border-brand p-4">
              <Card className="p-5">
                <ItemEditor initial={item} sections={sections} rooms={rooms} currency={currency} onSave={onSave} onCancel={onCancel} />
              </Card>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
