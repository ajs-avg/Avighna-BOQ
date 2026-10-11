"use client";

import { Check, Columns3, DoorOpen, LayoutGrid, Lock, Package, Pencil, Plus, RotateCcw, Save, Sliders, Square, Trash2, BrickWall } from "lucide-react";
import { useEffect, useId, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { putElements } from "@/lib/api";
import { formatInt, formatM, formatNumber } from "@/lib/format";
import type { ElBase, JobRecord, MeasurementExtraction, MemberEl, MiscEl, OpeningEl, RoomEl, SlabEl, WallEl } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { cn, errorMessage } from "@/lib/utils";
import { ConfidenceBadge } from "../ConfidenceBadge";
import { EditedByNote } from "../EditedByNote";
import { Alert } from "../ui/Alert";
import { Badge, Chip } from "../ui/Badge";
import { Button, IconButton } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { useConfirm } from "../ui/ConfirmDialog";
import { Dialog } from "../ui/Dialog";
import { EmptyRow, Table, TableWrap } from "../ui/Table";
import { useToast } from "../ui/Toast";
import { EvidenceButton } from "./EvidenceButton";
import {
  ASSUMPTION_FIELDS,
  DEFAULT_TRADES,
  ElementFields,
  MEMBER_DEF,
  MISC_DEF,
  OPENING_DEF,
  ROOM_DEF,
  SLAB_DEF,
  WALL_DEF,
  assumptionsFromDraft,
  assumptionsToDraft,
  countElements,
  emptyExtraction,
  finalizeEdit,
  removeById,
  stableStringify,
  upsertById,
  validateFields,
  type AssumptionsDraft,
  type BlankContext,
  type DraftRecord,
  type KindDef,
  type SuggestionLists,
} from "./elementForms";

export interface ElementsTabProps {
  job: JobRecord;
  /** Receives the recomputed job after "Save & recompute". */
  onJobUpdate: (job: JobRecord) => void;
  readOnly?: boolean;
  /** Shown in the save bar when `readOnly`. */
  readOnlyReason?: ReactNode;
  /** Lets the page block Approve while there are unsaved element edits. */
  onDirtyChange?: (dirty: boolean) => void;
}

type ListKey = "rooms" | "openings" | "walls" | "slabs" | "members" | "misc";

interface Editing {
  list: ListKey;
  /** null = adding a new row */
  id: string | null;
}

function withoutId(d: MeasurementExtraction, list: ListKey, id: string): MeasurementExtraction {
  switch (list) {
    case "rooms":
      return { ...d, rooms: removeById(d.rooms, id) };
    case "openings":
      return { ...d, openings: removeById(d.openings, id) };
    case "walls":
      return { ...d, walls: removeById(d.walls, id) };
    case "slabs":
      return { ...d, slabs: removeById(d.slabs, id) };
    case "members":
      return { ...d, members: removeById(d.members, id) };
    case "misc":
      return { ...d, misc: removeById(d.misc, id) };
  }
}

const uniq = (values: string[]): string[] => Array.from(new Set(values.map((v) => v.trim()).filter(Boolean))).sort();

/**
 * Where the reviewer corrects what the AI read. Edits stay local until "Save & recompute"
 * sends the WHOLE element set to PUT /jobs/{id}/elements; the response replaces the job,
 * which refreshes the measurement sheet, BOQ and materials.
 */
export function ElementsTab({ job, onJobUpdate, readOnly = false, readOnlyReason, onDirtyChange }: ElementsTabProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const { profile } = useUser();

  const server = useMemo<MeasurementExtraction>(() => job.elements ?? emptyExtraction(), [job.elements]);
  const [draft, setDraft] = useState<MeasurementExtraction>(() => structuredClone(server));
  const [assump, setAssump] = useState<AssumptionsDraft>(() => assumptionsToDraft(server.assumptions));
  const [editing, setEditing] = useState<Editing | null>(null);
  const [saving, setSaving] = useState(false);

  const assumpErrors = useMemo(() => validateFields(assump, ASSUMPTION_FIELDS), [assump]);
  const hasErrors = Object.keys(assumpErrors).length > 0;
  const pending = useMemo<MeasurementExtraction>(() => ({ ...draft, assumptions: assumptionsFromDraft(assump) }), [draft, assump]);
  const dirty = useMemo(() => stableStringify(pending) !== stableStringify(server), [pending, server]);
  const total = countElements(draft);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);

  const ctx = useMemo<BlankContext>(() => ({ level: job.level, assumptions: pending.assumptions }), [job.level, pending.assumptions]);

  const lists = useMemo<SuggestionLists>(
    () => ({
      rooms: uniq(draft.rooms.map((r) => r.name)),
      levels: uniq([
        job.level,
        ...draft.rooms.map((r) => r.level),
        ...draft.openings.map((o) => o.level),
        ...draft.walls.map((w) => w.level),
        ...draft.slabs.map((s) => s.level),
        ...draft.members.map((m) => m.level),
        ...draft.misc.map((m) => m.level),
      ]),
      walls: uniq(draft.walls.map((w) => w.tag)),
      trades: uniq([...DEFAULT_TRADES, ...draft.misc.map((m) => m.trade)]),
    }),
    [draft, job.level],
  );

  const close = () => setEditing(null);

  const remove = async (list: ListKey, el: ElBase, label: string) => {
    const ok = await confirm({
      title: `Delete ${label}?`,
      message: "Measurement rows that depend on it disappear when you save & recompute.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setDraft((d) => withoutId(d, list, el.id));
  };

  const discard = () => {
    setDraft(structuredClone(server));
    setAssump(assumptionsToDraft(server.assumptions));
  };

  const save = async () => {
    if (!dirty || hasErrors || saving) return;
    setSaving(true);
    try {
      const updated = await putElements(job.id, pending);
      onJobUpdate(updated);
      toast.success("Recomputed", "Measurement sheet, BOQ and materials now reflect your elements.");
    } catch (err) {
      toast.error("Could not save elements", errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  /** Typed dialog for whichever list is being edited (one branch per element kind keeps the generics concrete). */
  const dialogFor = <T extends ElBase, D extends DraftRecord>(def: KindDef<T, D>, items: T[], apply: (next: T[]) => void) => {
    const initial = editing?.id ? (items.find((e) => e.id === editing.id) ?? null) : null;
    return (
      <ElementDialog
        def={def}
        initial={initial}
        ctx={ctx}
        lists={lists}
        onClose={close}
        onSave={(el) => {
          apply(upsertById(items, finalizeEdit(initial, el, profile?.email)));
          close();
        }}
      />
    );
  };

  const dialog = (() => {
    if (!editing) return null;
    switch (editing.list) {
      case "rooms":
        return dialogFor(ROOM_DEF, draft.rooms, (rooms) => setDraft((d) => ({ ...d, rooms })));
      case "openings":
        return dialogFor(OPENING_DEF, draft.openings, (openings) => setDraft((d) => ({ ...d, openings })));
      case "walls":
        return dialogFor(WALL_DEF, draft.walls, (walls) => setDraft((d) => ({ ...d, walls })));
      case "slabs":
        return dialogFor(SLAB_DEF, draft.slabs, (slabs) => setDraft((d) => ({ ...d, slabs })));
      case "members":
        return dialogFor(MEMBER_DEF, draft.members, (members) => setDraft((d) => ({ ...d, members })));
      case "misc":
        return dialogFor(MISC_DEF, draft.misc, (misc) => setDraft((d) => ({ ...d, misc })));
    }
  })();

  return (
    <div className="space-y-5">
      {/* Save bar */}
      <div className="sticky top-16 z-20 -mx-1 px-1 pt-1">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface/95 px-4 py-2.5 shadow-card backdrop-blur supports-[backdrop-filter]:bg-surface/85">
          <p className="flex min-w-0 items-center gap-2 text-[13px] text-ink">
            {readOnly ? (
              <>
                <Lock className="size-4 shrink-0 text-muted" />
                <span className="text-muted">{readOnlyReason ?? "Editing is locked."}</span>
              </>
            ) : dirty ? (
              <>
                <span className="size-2 shrink-0 animate-pulse-dot rounded-full bg-brand" aria-hidden />
                <span>
                  <span className="font-semibold">Unsaved changes.</span> <span className="text-muted">The sheet, BOQ and materials are recomputed when you save.</span>
                </span>
              </>
            ) : (
              <>
                <Check className="size-4 shrink-0 text-success" />
                <span className="text-muted">
                  {formatInt(total)} element{total === 1 ? "" : "s"} · nothing to save
                </span>
              </>
            )}
          </p>
          {!readOnly ? (
            <div className="flex items-center gap-2">
              <Button variant="secondary" leftIcon={<RotateCcw />} onClick={discard} disabled={!dirty || saving}>
                Discard
              </Button>
              <Button leftIcon={<Save />} onClick={() => void save()} loading={saving} disabled={!dirty || hasErrors} title={hasErrors ? "Fix the assumptions first" : undefined}>
                Save &amp; recompute
              </Button>
            </div>
          ) : null}
        </div>
      </div>

      {/* Assumptions */}
      <Card>
        <CardHeader icon={<Sliders />} title="Assumptions" description="Used where the drawing is silent; new rooms and walls start from these." className="py-3" />
        <CardBody>
          <ElementFields fields={ASSUMPTION_FIELDS} draft={assump} onChange={setAssump} errors={assumpErrors} disabled={readOnly} className="md:grid-cols-5" />
          {assump.notes.length ? (
            <ul className="mt-3 list-disc space-y-0.5 pl-4 text-[12.5px] text-muted">
              {assump.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          ) : null}
        </CardBody>
      </Card>

      <ElementSection
        icon={<LayoutGrid />}
        title="Rooms"
        description="Internal clear sizes drive flooring, skirting, plaster, paint and dado."
        items={draft.rooms}
        columns={ROOM_COLUMNS}
        labelOf={ROOM_DEF.labelOf}
        readOnly={readOnly}
        onAdd={() => setEditing({ list: "rooms", id: null })}
        onEdit={(el) => setEditing({ list: "rooms", id: el.id })}
        onDelete={(el) => void remove("rooms", el, `room ${el.name}`)}
        emptyText="No rooms read. Add one to start measuring finishes."
      />
      <ElementSection
        icon={<DoorOpen />}
        title="Openings"
        description="Doors, windows and ventilators — deducted from plaster and paint per IS 1200."
        items={draft.openings}
        columns={OPENING_COLUMNS}
        labelOf={OPENING_DEF.labelOf}
        readOnly={readOnly}
        onAdd={() => setEditing({ list: "openings", id: null })}
        onEdit={(el) => setEditing({ list: "openings", id: el.id })}
        onDelete={(el) => void remove("openings", el, `opening ${el.tag}`)}
        emptyText="No openings read."
      />
      <ElementSection
        icon={<BrickWall />}
        title="Walls"
        description="RCC walls go to concrete and formwork; block walls to masonry."
        items={draft.walls}
        columns={WALL_COLUMNS}
        labelOf={WALL_DEF.labelOf}
        readOnly={readOnly}
        onAdd={() => setEditing({ list: "walls", id: null })}
        onEdit={(el) => setEditing({ list: "walls", id: el.id })}
        onDelete={(el) => void remove("walls", el, `wall ${el.tag}`)}
        emptyText="No walls read."
      />
      <ElementSection
        icon={<Square />}
        title="Slabs"
        description="Slab concrete, soffit formwork and ceiling finish."
        items={draft.slabs}
        columns={SLAB_COLUMNS}
        labelOf={SLAB_DEF.labelOf}
        readOnly={readOnly}
        onAdd={() => setEditing({ list: "slabs", id: null })}
        onEdit={(el) => setEditing({ list: "slabs", id: el.id })}
        onDelete={(el) => void remove("slabs", el, `slab ${el.tag}`)}
        emptyText="No slabs read."
      />
      <ElementSection
        icon={<Columns3 />}
        title="Columns & beams"
        description="Concrete and formwork for columns and beams (steel by thumb rule until a BBS is attached)."
        items={draft.members}
        columns={MEMBER_COLUMNS}
        labelOf={MEMBER_DEF.labelOf}
        readOnly={readOnly}
        onAdd={() => setEditing({ list: "members", id: null })}
        onEdit={(el) => setEditing({ list: "members", id: el.id })}
        onDelete={(el) => void remove("members", el, `${el.kind} ${el.tag}`)}
        emptyText="No columns or beams read."
      />
      <ElementSection
        icon={<Package />}
        title="Other items"
        description="Anything countable that is not a room, wall or opening: fixtures, joinery, lights, sanitary ware."
        items={draft.misc}
        columns={MISC_COLUMNS}
        labelOf={MISC_DEF.labelOf}
        readOnly={readOnly}
        onAdd={() => setEditing({ list: "misc", id: null })}
        onEdit={(el) => setEditing({ list: "misc", id: el.id })}
        onDelete={(el) => void remove("misc", el, el.description)}
        emptyText="No other items read. Add fixtures, joinery or sanitary ware here."
      />

      {dialog}
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Dialog                                                                      */
/* ------------------------------------------------------------------------- */

function ElementDialog<T extends ElBase, D extends DraftRecord>({
  def,
  initial,
  ctx,
  lists,
  onSave,
  onClose,
}: {
  def: KindDef<T, D>;
  initial: T | null;
  ctx: BlankContext;
  lists: SuggestionLists;
  onSave: (el: T) => void;
  onClose: () => void;
}) {
  const formId = useId();
  const [draft, setDraft] = useState<D>(() => (initial ? def.toDraft(initial) : def.blankDraft(ctx)));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const errorCount = Object.keys(errors).length;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const errs = validateFields(draft, def.fields);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    onSave(def.fromDraft(draft));
  };

  return (
    <Dialog
      open
      onClose={onClose}
      size="lg"
      title={initial ? `Edit ${def.singular} · ${def.labelOf(initial)}` : `Add ${def.singular}`}
      description={initial ? "Changes apply locally; the sheet is recomputed on Save & recompute." : "New rows are marked as added manually with full confidence."}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={formId} leftIcon={<Check />}>
            {initial ? "Apply" : `Add ${def.singular}`}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="space-y-4" noValidate>
        {errorCount ? (
          <Alert tone="danger">
            Fix {errorCount} field{errorCount === 1 ? "" : "s"} before applying.
          </Alert>
        ) : null}
        <ElementFields
          fields={def.fields}
          draft={draft}
          onChange={(next) => {
            setDraft(next);
            if (errorCount) setErrors(validateFields(next, def.fields));
          }}
          errors={errors}
          lists={lists}
        />
        {initial ? (
          <div className="rounded-lg border border-line bg-surface-2/60 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11.5px] font-semibold uppercase tracking-[0.05em] text-muted">Read from the drawing</p>
              <ConfidenceBadge value={initial.confidence} size="xs" />
            </div>
            {initial.source_sheet ? (
              <p className="mt-1 text-[12px] text-muted">
                Sheet <Chip>{initial.source_sheet}</Chip>
              </p>
            ) : null}
            {initial.evidence.length ? (
              <ul className="mt-1 space-y-0.5 font-mono text-[11.5px] text-muted">
                {initial.evidence.map((ev, i) => (
                  <li key={i} className="truncate" title={ev}>
                    {ev}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-[12px] text-muted">No evidence recorded.</p>
            )}
          </div>
        ) : null}
      </form>
    </Dialog>
  );
}

/* ------------------------------------------------------------------------- */
/* Section table                                                               */
/* ------------------------------------------------------------------------- */

interface Column<T> {
  header: ReactNode;
  cell: (el: T) => ReactNode;
  className?: string;
}

function ElementSection<T extends ElBase>({
  icon,
  title,
  description,
  items,
  columns,
  labelOf,
  readOnly,
  onAdd,
  onEdit,
  onDelete,
  emptyText,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  items: T[];
  columns: Column<T>[];
  labelOf: (el: T) => string;
  readOnly: boolean;
  onAdd: () => void;
  onEdit: (el: T) => void;
  onDelete: (el: T) => void;
  emptyText: string;
}) {
  const colSpan = columns.length + 2;
  return (
    <Card className="overflow-hidden">
      <CardHeader
        icon={icon}
        title={
          <span className="flex items-center gap-2">
            {title}
            <Badge size="xs" tone={items.length ? "brand" : "neutral"}>
              {items.length}
            </Badge>
          </span>
        }
        description={description}
        className="py-3"
        actions={
          !readOnly ? (
            <Button size="sm" variant="secondary" leftIcon={<Plus />} onClick={onAdd}>
              Add
            </Button>
          ) : undefined
        }
      />
      <TableWrap flush maxHeight={560}>
        <Table>
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th key={i} className={c.className}>
                  {c.header}
                </th>
              ))}
              <th>Confidence</th>
              <th className="w-28" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <EmptyRow colSpan={colSpan}>{emptyText}</EmptyRow>
            ) : (
              items.map((el) => (
                <tr key={el.id} className={cn("row-hover", !readOnly && "cursor-pointer")} onClick={() => !readOnly && onEdit(el)} title={readOnly ? undefined : "Click to edit"}>
                  {columns.map((c, i) => (
                    <td key={i} className={c.className}>
                      {c.cell(el)}
                    </td>
                  ))}
                  <td>
                    <ConfidenceBadge value={el.confidence} size="xs" />
                    <EditedByNote evidence={el.evidence} />
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-end gap-0.5">
                      <EvidenceButton evidence={el.evidence} sourceSheet={el.source_sheet} subject={labelOf(el)} />
                      {!readOnly ? (
                        <>
                          <IconButton label={`Edit ${labelOf(el)}`} size="xs" onClick={() => onEdit(el)}>
                            <Pencil />
                          </IconButton>
                          <IconButton label={`Delete ${labelOf(el)}`} size="xs" className="text-muted hover:bg-danger-soft hover:text-danger" onClick={() => onDelete(el)}>
                            <Trash2 />
                          </IconButton>
                        </>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </Table>
      </TableWrap>
    </Card>
  );
}

/* ------------------------------------------------------------------------- */
/* Columns per element kind                                                    */
/* ------------------------------------------------------------------------- */

const dash = <span className="text-muted/50">—</span>;
const text = (v: string | null | undefined): ReactNode => (v && v.trim() ? v : dash);
const mm = (v: number): string => formatNumber(v * 1000, 0);
const capital = (v: string): string => v.charAt(0).toUpperCase() + v.slice(1);

const ROOM_COLUMNS: Column<RoomEl>[] = [
  { header: "Room / space", cell: (r) => <span className="font-medium text-ink">{r.name}</span>, className: "min-w-[140px]" },
  { header: "Level", cell: (r) => text(r.level), className: "whitespace-nowrap text-muted" },
  {
    header: "L × W × H (m)",
    className: "whitespace-nowrap",
    cell: (r) => (
      <span className="tnum">
        {formatM(r.length_m)} × {formatM(r.width_m)} × {formatM(r.height_m)}
      </span>
    ),
  },
  { header: "Area (sqm)", className: "num", cell: (r) => formatNumber(r.area_m2 ?? r.length_m * r.width_m, 2) },
  {
    header: "Finishes",
    className: "min-w-[220px]",
    cell: (r) => (
      <div className="flex flex-col text-[12px] leading-4 text-muted">
        <span className="truncate" title={`Floor: ${r.floor_finish}`}>
          <span className="font-semibold">F</span> {r.floor_finish || "—"}
        </span>
        <span className="truncate" title={`Wall: ${r.wall_finish}`}>
          <span className="font-semibold">W</span> {r.wall_finish || "—"}
        </span>
        <span className="truncate" title={`Ceiling: ${r.ceiling_finish}`}>
          <span className="font-semibold">C</span> {r.ceiling_finish || "—"}
        </span>
      </div>
    ),
  },
  {
    header: "Skirting / dado",
    className: "whitespace-nowrap",
    cell: (r) => (
      <span className="tnum">
        {r.skirting_mm ? `${formatNumber(r.skirting_mm, 0)} mm` : "—"} · {r.dado_height_m ? `${formatM(r.dado_height_m)} m` : "—"}
      </span>
    ),
  },
  {
    header: "Flags",
    cell: (r) => (
      <div className="flex flex-wrap gap-1">
        {r.wet_area ? (
          <Badge tone="info" size="xs">
            Wet
          </Badge>
        ) : null}
        {!r.plastered ? <Badge size="xs">No plaster</Badge> : null}
        {!r.wet_area && r.plastered ? dash : null}
      </div>
    ),
  },
];

const OPENING_COLUMNS: Column<OpeningEl>[] = [
  { header: "Tag", cell: (o) => <Chip>{o.tag}</Chip> },
  { header: "Kind", cell: (o) => capital(o.kind), className: "whitespace-nowrap" },
  {
    header: "W × H (m)",
    className: "whitespace-nowrap",
    cell: (o) => (
      <span className="tnum">
        {formatM(o.width_m)} × {formatM(o.height_m)}
      </span>
    ),
  },
  { header: "Nos", className: "num", cell: (o) => formatInt(o.count) },
  { header: "Room", cell: (o) => text(o.room) },
  { header: "Wall", cell: (o) => (o.wall_tag ? <Chip>{o.wall_tag}</Chip> : dash) },
  {
    header: "Description",
    className: "min-w-[200px]",
    cell: (o) => (
      <span className="line-clamp-2 text-muted" title={o.description}>
        {o.description || "—"}
      </span>
    ),
  },
  { header: "Level", cell: (o) => text(o.level), className: "whitespace-nowrap text-muted" },
];

const WALL_COLUMNS: Column<WallEl>[] = [
  { header: "Tag", cell: (w) => <Chip>{w.tag}</Chip> },
  { header: "Type", cell: (w) => (w.wall_type === "rcc" ? "RCC" : capital(w.wall_type)), className: "whitespace-nowrap" },
  { header: "Length (m)", className: "num", cell: (w) => formatM(w.length_m) },
  { header: "Thk (mm)", className: "num", cell: (w) => mm(w.thickness_m) },
  { header: "Height (m)", className: "num", cell: (w) => formatM(w.height_m) },
  { header: "Nos", className: "num", cell: (w) => formatInt(w.count) },
  { header: "Room", cell: (w) => text(w.room) },
  { header: "Level", cell: (w) => text(w.level), className: "whitespace-nowrap text-muted" },
  { header: "Faces", cell: (w) => (w.both_faces ? "Both" : "One"), className: "whitespace-nowrap text-muted" },
];

const SLAB_COLUMNS: Column<SlabEl>[] = [
  { header: "Tag", cell: (s) => <Chip>{s.tag}</Chip> },
  {
    header: "L × W (m)",
    className: "whitespace-nowrap",
    cell: (s) => (
      <span className="tnum">
        {formatM(s.length_m)} × {formatM(s.width_m)}
      </span>
    ),
  },
  { header: "Thk (mm)", className: "num", cell: (s) => mm(s.thickness_m) },
  { header: "Nos", className: "num", cell: (s) => formatInt(s.count) },
  { header: "Beam width (mm)", className: "num", cell: (s) => (s.beam_width_m ? mm(s.beam_width_m) : "—") },
  { header: "Level", cell: (s) => text(s.level), className: "whitespace-nowrap text-muted" },
];

const MEMBER_COLUMNS: Column<MemberEl>[] = [
  { header: "Tag", cell: (m) => <Chip>{m.tag}</Chip> },
  { header: "Kind", cell: (m) => capital(m.kind), className: "whitespace-nowrap" },
  {
    header: "W × D (mm)",
    className: "whitespace-nowrap",
    cell: (m) => (
      <span className="tnum">
        {mm(m.width_m)} × {mm(m.depth_m)}
      </span>
    ),
  },
  { header: "Height / span (m)", className: "num", cell: (m) => formatM(m.length_m) },
  { header: "Nos", className: "num", cell: (m) => formatInt(m.count) },
  { header: "Slab thk (mm)", className: "num", cell: (m) => (m.slab_thickness_m ? mm(m.slab_thickness_m) : "—") },
  { header: "Level", cell: (m) => text(m.level), className: "whitespace-nowrap text-muted" },
];

const MISC_COLUMNS: Column<MiscEl>[] = [
  { header: "Tag", cell: (m) => (m.tag ? <Chip>{m.tag}</Chip> : dash) },
  {
    header: "Description",
    className: "min-w-[220px]",
    cell: (m) => (
      <span className="line-clamp-2 font-medium text-ink" title={m.description}>
        {m.description}
      </span>
    ),
  },
  { header: "Qty", className: "num", cell: (m) => formatNumber(m.qty, m.unit === "nos" || m.unit === "LS" ? 0 : 2) },
  { header: "Unit", cell: (m) => m.unit, className: "text-muted" },
  { header: "Trade", cell: (m) => text(m.trade) },
  { header: "Room", cell: (m) => text(m.room) },
  { header: "Level", cell: (m) => text(m.level), className: "whitespace-nowrap text-muted" },
];
