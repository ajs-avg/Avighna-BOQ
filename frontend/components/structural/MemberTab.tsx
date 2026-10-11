"use client";

import { AlertTriangle, ChevronDown, Layers, Pencil, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { addMember, deleteMember, patchMember } from "@/lib/api";
import { MEMBER_KIND_META } from "@/lib/constants";
import { formatInt, formatKg, memberBarsSummary, memberSizeLabel } from "@/lib/format";
import type { JobRecord, MemberKind, MemberResult, MemberSpec } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { ConfidenceBadge } from "../ConfidenceBadge";
import { EditedByNote } from "../EditedByNote";
import { Badge } from "../ui/Badge";
import { Button, IconButton } from "../ui/Button";
import { Card } from "../ui/Card";
import { useConfirm } from "../ui/ConfirmDialog";
import { EmptyState } from "../ui/EmptyState";
import { EmptyRow, Table, TableWrap } from "../ui/Table";
import { useToast } from "../ui/Toast";
import { BarRowsTable } from "./BarRowsTable";
import { MemberEditor } from "./MemberEditor";

export interface MemberTabProps {
  job: JobRecord;
  kind: MemberKind;
  onJobUpdate: (job: JobRecord) => void;
  readOnly?: boolean;
}

export function MemberTab({ job, kind, onJobUpdate, readOnly }: MemberTabProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const meta = MEMBER_KIND_META[kind];

  const members = useMemo(() => job.members.filter((m) => m.kind === kind), [job.members, kind]);
  const results = useMemo(() => {
    const map = new Map<string, MemberResult>();
    for (const r of job.result?.members ?? []) map.set(r.member_id, r);
    return map;
  }, [job.result]);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const totalKg = members.reduce((s, m) => s + (results.get(m.id)?.weight_kg ?? 0), 0);

  const save = async (spec: MemberSpec) => {
    const updated = await patchMember(job.id, spec.id, spec);
    onJobUpdate(updated);
    setEditingId(null);
    toast.success(`${meta.label} ${spec.tag} updated`, "Schedule recalculated.");
  };

  const add = async (spec: MemberSpec) => {
    const updated = await addMember(job.id, spec);
    onJobUpdate(updated);
    setAdding(false);
    toast.success(`${meta.label} ${spec.tag} added`);
  };

  const remove = async (m: MemberSpec) => {
    const ok = await confirm({
      title: `Delete ${meta.label.toLowerCase()} ${m.tag}?`,
      message: "The member and its bar rows are removed and the summary recalculated.",
      confirmLabel: "Delete",
      danger: true,
      onConfirm: async () => {
        setDeletingId(m.id);
        try {
          const updated = await deleteMember(job.id, m.id);
          onJobUpdate(updated);
        } catch (err) {
          toast.error("Could not delete", errorMessage(err));
          throw err;
        } finally {
          setDeletingId(null);
        }
      },
    });
    if (ok) toast.success(`${meta.label} ${m.tag} deleted`);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-muted">
          <span className="font-semibold text-ink">{formatInt(members.length)}</span> {members.length === 1 ? meta.label.toLowerCase() : meta.plural.toLowerCase()}
          {members.length ? (
            <>
              {" "}
              · <span className="tnum font-semibold text-ink">{formatKg(totalKg)}</span> of steel
            </>
          ) : null}
        </p>
        {!readOnly ? (
          <Button size="sm" leftIcon={<Plus />} onClick={() => setAdding(true)} disabled={adding}>
            Add {meta.label.toLowerCase()}
          </Button>
        ) : null}
      </div>

      {adding ? (
        <Card className="border-brand/40 p-5 shadow-pop animate-pop-in">
          <MemberEditor kind={kind} onSave={add} onCancel={() => setAdding(false)} />
        </Card>
      ) : null}

      <TableWrap>
        <Table>
          <thead>
            <tr>
              <th className="w-8" />
              <th>Tag</th>
              <th className="num">Nos</th>
              <th>Size</th>
              <th className="min-w-[260px]">Reinforcement</th>
              <th className="num">Rows</th>
              <th className="num">Weight (kg)</th>
              <th>Confidence</th>
              <th className="w-20" />
            </tr>
          </thead>
          <tbody>
            {members.length === 0 ? (
              <EmptyRow colSpan={9}>
                <EmptyState
                  compact
                  icon={<Layers />}
                  title={`No ${meta.plural.toLowerCase()} extracted`}
                  description={readOnly ? "Nothing was found on the relevant sheets." : "Nothing was found on the relevant sheets. You can add one manually."}
                  action={
                    !readOnly ? (
                      <Button size="sm" variant="secondary" leftIcon={<Plus />} onClick={() => setAdding(true)}>
                        Add {meta.label.toLowerCase()}
                      </Button>
                    ) : undefined
                  }
                />
              </EmptyRow>
            ) : (
              members.map((m) => {
                const r = results.get(m.id);
                const isOpen = expanded.has(m.id) || editingId === m.id;
                const warnings = r?.warnings ?? [];
                return (
                  <MemberRows
                    key={m.id}
                    member={m}
                    result={r}
                    open={isOpen}
                    editing={editingId === m.id}
                    deleting={deletingId === m.id}
                    readOnly={!!readOnly}
                    warnings={warnings}
                    onToggle={() => toggle(m.id)}
                    onEdit={() => {
                      setEditingId(m.id);
                      setExpanded((prev) => new Set(prev).add(m.id));
                    }}
                    onCancelEdit={() => setEditingId(null)}
                    onSave={save}
                    onDelete={() => void remove(m)}
                  />
                );
              })
            )}
          </tbody>
          {members.length ? (
            <tfoot>
              <tr>
                <td colSpan={6} className="text-right">
                  {meta.plural} total
                </td>
                <td className="num text-brand">{formatKg(totalKg, false)}</td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          ) : null}
        </Table>
      </TableWrap>
    </div>
  );
}

function MemberRows({
  member,
  result,
  open,
  editing,
  deleting,
  readOnly,
  warnings,
  onToggle,
  onEdit,
  onCancelEdit,
  onSave,
  onDelete,
}: {
  member: MemberSpec;
  result?: MemberResult;
  open: boolean;
  editing: boolean;
  deleting: boolean;
  readOnly: boolean;
  warnings: string[];
  onToggle: () => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSave: (spec: MemberSpec) => Promise<void>;
  onDelete: () => void;
}) {
  return (
    <>
      <tr className={cn("row-hover cursor-pointer", open && "[&>td]:!bg-brand-tint/70")} onClick={onToggle} aria-expanded={open}>
        <td>
          <ChevronDown className={cn("size-4 text-muted transition-transform", open && "rotate-180")} />
        </td>
        <td className="font-semibold">
          {member.tag}
          {warnings.length ? (
            <span className="ml-1.5 inline-flex align-middle text-warning" title={warnings.join("\n")}>
              <AlertTriangle className="size-3.5" />
            </span>
          ) : null}
        </td>
        <td className="num">{formatInt(member.nos)}</td>
        <td className="whitespace-nowrap text-[12.5px]">{result?.size_label || memberSizeLabel(member)}</td>
        <td className="max-w-[420px] text-[12.5px] text-ink/85">
          <p className="truncate" title={memberBarsSummary(member)}>
            {memberBarsSummary(member)}
          </p>
          <EditedByNote evidence={member.evidence} />
        </td>
        <td className="num text-muted">{result ? formatInt(result.rows.length) : "—"}</td>
        <td className="num font-semibold">{result ? formatKg(result.weight_kg, false) : <span className="text-muted">—</span>}</td>
        <td>
          <ConfidenceBadge value={member.confidence} size="xs" />
        </td>
        <td onClick={(e) => e.stopPropagation()}>
          {!readOnly ? (
            <div className="flex justify-end gap-0.5">
              <IconButton label="Edit member" size="xs" onClick={onEdit} disabled={editing}>
                <Pencil />
              </IconButton>
              <IconButton label="Delete member" size="xs" className="text-muted hover:bg-danger-soft hover:text-danger" onClick={onDelete} loading={deleting}>
                <Trash2 />
              </IconButton>
            </div>
          ) : null}
        </td>
      </tr>
      {open ? (
        <tr>
          <td colSpan={9} className="!bg-surface-2/50 !p-0">
            <div className="space-y-4 border-l-[3px] border-brand p-4">
              {editing ? (
                <Card className="p-5">
                  <MemberEditor kind={member.kind} initial={member} onSave={onSave} onCancel={onCancelEdit} />
                </Card>
              ) : (
                <>
                  {warnings.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {warnings.map((w, i) => (
                        <Badge key={i} tone="warning" icon={<AlertTriangle />}>
                          {w}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                  {member.remarks ? <p className="text-[12.5px] text-muted">Remarks: {member.remarks}</p> : null}
                  {result ? (
                    <BarRowsTable rows={result.rows} />
                  ) : (
                    <p className="text-[13px] text-muted">No calculation result for this member yet — run Recalculate.</p>
                  )}
                  {member.source_sheet ? <p className="text-[12px] text-muted">Source sheet: {member.source_sheet}</p> : null}
                </>
              )}
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
