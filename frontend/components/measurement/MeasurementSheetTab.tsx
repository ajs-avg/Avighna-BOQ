"use client";

import { ClipboardList, Ruler } from "lucide-react";
import { formatInt, formatM, formatNumber, qtyDigits, totalsByTradeParts } from "@/lib/format";
import type { MeasurementBlock, MeasurementResult, MeasurementRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Alert } from "../ui/Alert";
import { Badge, Chip } from "../ui/Badge";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Table, TableWrap } from "../ui/Table";

export interface MeasurementSheetTabProps {
  measurement: MeasurementResult;
  className?: string;
}

/** IS 1200 style measurement sheet: one card per item, deductions shaded, totals in red. */
export function MeasurementSheetTab({ measurement, className }: MeasurementSheetTabProps) {
  const { blocks, warnings } = measurement;
  const parts = totalsByTradeParts(measurement.totals_by_trade);
  const rowCount = blocks.reduce((n, b) => n + b.rows.length, 0);

  return (
    <div className={cn("space-y-5", className)}>
      <div className="sticky top-16 z-20 -mx-1 px-1 pt-1">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card border border-line bg-surface/95 px-4 py-2.5 shadow-card backdrop-blur supports-[backdrop-filter]:bg-surface/85">
          <p className="flex items-center gap-2 text-[13px] font-semibold text-ink">
            <span className="inline-flex size-7 items-center justify-center rounded-lg bg-brand-soft text-brand">
              <Ruler className="size-4" />
            </span>
            {formatInt(blocks.length)} item{blocks.length === 1 ? "" : "s"}
            <span className="font-normal text-muted">· {formatInt(rowCount)} measurement rows</span>
          </p>
          {parts.length ? (
            <ul className="flex flex-wrap items-center gap-1.5" aria-label="Totals by trade">
              {parts.map((p) => (
                <li key={`${p.trade}-${p.unit}`}>
                  <Badge tone="neutral" size="sm" className="bg-surface-2 text-ink">
                    <span className="text-muted">{p.trade}</span>
                    <span className="tnum font-semibold">{formatNumber(p.value, qtyDigits(p.unit) === 0 ? 0 : 1)}</span>
                    <span className="text-muted">{p.unit}</span>
                  </Badge>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      {warnings.length ? (
        <Alert tone="warning" title={`${warnings.length} warning${warnings.length === 1 ? "" : "s"} from the reading`}>
          <ul className="list-disc space-y-0.5 pl-4">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {blocks.length === 0 ? (
        <Card>
          <EmptyState icon={<ClipboardList />} title="Nothing measured yet" description="No rooms, walls, openings or slabs were read from the drawings. Add them in the Elements tab and save to compute the sheet." />
        </Card>
      ) : (
        blocks.map((b) => <BlockCard key={b.item_code} block={b} />)
      )}
    </div>
  );
}

function BlockCard({ block }: { block: MeasurementBlock }) {
  const digits = qtyDigits(block.unit);
  const deductions = block.rows.filter((r) => r.deduction).length;
  return (
    <Card id={`item-${block.item_code}`} className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line bg-surface-2/60 px-5 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Chip className="font-semibold">{block.item_code}</Chip>
            <Badge size="xs">{block.trade}</Badge>
            <span className="text-[11.5px] text-muted">
              {block.rows.length} row{block.rows.length === 1 ? "" : "s"}
              {deductions ? ` · ${deductions} deduction${deductions === 1 ? "" : "s"}` : ""}
            </span>
          </div>
          <h3 className="mt-1 text-[14px] font-semibold leading-5 text-ink">{block.item_title}</h3>
        </div>
        <div className="text-right">
          <p className="tnum text-[20px] font-semibold leading-none tracking-tight text-brand">
            {formatNumber(block.total, digits)}
            <span className="ml-1 text-[12.5px] font-medium text-muted">{block.unit}</span>
          </p>
          <p className="mt-1 text-[11px] uppercase tracking-[0.06em] text-muted">Total</p>
        </div>
      </div>
      <TableWrap flush>
        <Table>
          <thead>
            <tr>
              <th className="w-12">Sr</th>
              <th className="min-w-[260px]">Location</th>
              <th className="num w-16">No.</th>
              <th className="num w-20">L (m)</th>
              <th className="num w-20">B (m)</th>
              <th className="num w-20">H (m)</th>
              <th className="num w-28">Qty ({block.unit})</th>
              <th className="min-w-[200px]">Rule / ref</th>
            </tr>
          </thead>
          <tbody>
            {block.rows.map((r) => (
              <SheetRow key={`${r.sr}-${r.element_id ?? ""}`} row={r} digits={digits} />
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={6} className="!bg-brand-soft text-right text-brand">
                Total {block.item_code}
              </td>
              <td className="num !bg-brand-soft text-brand">{formatNumber(block.total, digits)}</td>
              <td className="!bg-brand-soft text-[12px] font-medium text-brand/80">{block.unit}</td>
            </tr>
          </tfoot>
        </Table>
      </TableWrap>
    </Card>
  );
}

function SheetRow({ row, digits }: { row: MeasurementRow; digits: number }) {
  const dim = (v: number | null | undefined) => (v === null || v === undefined ? <span className="text-muted/50">—</span> : formatM(v));
  const nos = Number.isInteger(row.nos) ? formatNumber(row.nos, 0) : formatNumber(row.nos, 2);
  // The engine already writes "Deduct: …" on some rows; only add the prefix when it is missing.
  const location = row.deduction && !/^deduct/i.test(row.location.trim()) ? `Deduct: ${row.location}` : row.location;
  return (
    <tr className={cn(row.deduction && "[&>td]:!bg-surface-3 [&>td]:text-muted")} title={row.deduction ? "Deduction" : undefined}>
      <td className="tnum text-muted">{row.sr}</td>
      <td className={cn("max-w-[460px]", row.deduction && "pl-6")}>
        <span className={cn("line-clamp-2", row.deduction ? "italic" : "text-ink")} title={location}>
          {location}
        </span>
      </td>
      <td className="num">{nos}</td>
      <td className="num">{dim(row.l_m)}</td>
      <td className="num">{dim(row.b_m)}</td>
      <td className="num">{dim(row.h_m)}</td>
      <td className={cn("num font-semibold", row.deduction ? "text-danger" : "text-ink")}>
        {row.deduction ? `− ${formatNumber(Math.abs(row.qty), digits)}` : formatNumber(row.qty, digits)}
      </td>
      <td className="max-w-[320px] text-[12px] text-muted">
        <span className="line-clamp-2" title={row.rule}>
          {row.rule || <span className="text-muted/50">—</span>}
        </span>
      </td>
    </tr>
  );
}
