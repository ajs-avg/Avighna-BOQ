"use client";

import { ClipboardList } from "lucide-react";
import { useMemo } from "react";
import { BOQ_BASIS_META } from "@/lib/constants";
import { formatInt, formatNumber, qtyDigits } from "@/lib/format";
import type { BOQAbstractLine, BOQBasis } from "@/lib/types";
import { Badge, Chip } from "../ui/Badge";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Table, TableWrap } from "../ui/Table";

export interface MeasurementBOQTabProps {
  boq: BOQAbstractLine[];
}

interface TradeGroup {
  trade: string;
  lines: BOQAbstractLine[];
}

/** Read-only BOQ abstract grouped by trade. Rates are left blank on purpose. */
export function MeasurementBOQTab({ boq }: MeasurementBOQTabProps) {
  const groups = useMemo<TradeGroup[]>(() => {
    const map = new Map<string, TradeGroup>();
    for (const line of boq) {
      const g = map.get(line.trade) ?? { trade: line.trade, lines: [] };
      g.lines.push(line);
      map.set(line.trade, g);
    }
    return Array.from(map.values());
  }, [boq]);

  const thumb = boq.filter((l) => l.basis === "thumb_rule").length;

  if (boq.length === 0) {
    return (
      <Card>
        <EmptyState icon={<ClipboardList />} title="No BOQ items yet" description="The abstract is built from the measurement sheet. Add elements and save to compute it." />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-muted">
          <span className="font-semibold text-ink">{formatInt(boq.length)}</span> item{boq.length === 1 ? "" : "s"} across {groups.length} trade{groups.length === 1 ? "" : "s"}
          {thumb ? (
            <>
              {" "}
              · <span className="text-warning">{thumb} by thumb rule</span>
            </>
          ) : null}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-[11.5px] text-muted">
          <span>Basis:</span>
          {(Object.keys(BOQ_BASIS_META) as BOQBasis[]).map((b) => (
            <BasisBadge key={b} basis={b} />
          ))}
        </div>
      </div>

      <Card className="overflow-hidden">
        <TableWrap flush>
          <Table>
            <thead>
              <tr>
                <th className="w-16">Item no</th>
                <th className="min-w-[360px]">Description</th>
                <th className="num w-28">Qty</th>
                <th className="w-16">Unit</th>
                <th className="w-28">Basis</th>
              </tr>
            </thead>
            {groups.map((g) => (
              <tbody key={g.trade}>
                <tr>
                  <td colSpan={5} className="!bg-surface-3/70 py-1.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">
                    {g.trade}
                    <span className="tnum ml-2 font-normal normal-case tracking-normal">
                      · {g.lines.length} item{g.lines.length === 1 ? "" : "s"}
                    </span>
                  </td>
                </tr>
                {g.lines.map((line) => (
                  <tr key={line.item_no} className="row-hover">
                    <td className="tnum font-semibold text-muted">{line.item_no}</td>
                    <td className="max-w-[560px]">
                      <div className="flex items-start gap-2">
                        <Chip className="mt-0.5 shrink-0">{line.item_code}</Chip>
                        <span className="text-ink" title={line.description}>
                          {line.description}
                        </span>
                      </div>
                    </td>
                    <td className="num font-semibold">{formatNumber(line.qty, qtyDigits(line.unit))}</td>
                    <td className="text-muted">{line.unit}</td>
                    <td>
                      <BasisBadge basis={line.basis} />
                    </td>
                  </tr>
                ))}
              </tbody>
            ))}
          </Table>
        </TableWrap>
        <p className="border-t border-line bg-surface-2/60 px-5 py-2.5 text-[12px] text-muted">Rates are left blank on purpose; quantities only.</p>
      </Card>
    </div>
  );
}

function BasisBadge({ basis }: { basis: BOQBasis }) {
  const meta = BOQ_BASIS_META[basis];
  return (
    <Badge tone={meta.tone} size="xs" title={meta.hint} className={basis === "thumb_rule" ? "cursor-help" : undefined}>
      {meta.label}
    </Badge>
  );
}
