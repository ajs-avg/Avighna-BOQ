import { formatInt, formatTons } from "@/lib/format";
import type { BBSSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Table, TableWrap } from "../ui/Table";

export interface SummaryTableProps {
  summary: BBSSummary;
  diameters: number[];
  className?: string;
}

/** Dia-wise tonnage per category — mirrors the "Summary" sheet of the Excel. */
export function SummaryTable({ summary, diameters, className }: SummaryTableProps) {
  const dias = diameters.length ? diameters : [8, 10, 12, 16, 20, 25, 32];
  const cell = (map: Record<string, number>, dia: number) => {
    const v = map[String(dia)] ?? 0;
    return v ? formatTons(v, false) : <span className="text-muted/50">—</span>;
  };
  return (
    <TableWrap className={className}>
      <Table>
        <thead>
          <tr>
            <th className="min-w-[140px]">Category</th>
            <th className="num">Members</th>
            {dias.map((d) => (
              <th key={d} className="num">
                T{d}
                <span className="ml-1 font-normal normal-case tracking-normal text-muted/70">t</span>
              </th>
            ))}
            <th className="num min-w-[110px]">Total (t)</th>
          </tr>
        </thead>
        <tbody>
          {summary.categories.map((c) => (
            <tr key={c.category}>
              <td className="font-semibold">{c.category}</td>
              <td className="num text-muted">{formatInt(c.member_count)}</td>
              {dias.map((d) => (
                <td key={d} className="num">
                  {cell(c.weight_by_dia_t, d)}
                </td>
              ))}
              <td className="num font-semibold">{formatTons(c.total_t, false)}</td>
            </tr>
          ))}
          {summary.categories.length === 0 ? (
            <tr>
              <td colSpan={dias.length + 3} className="py-8 text-center text-muted">
                No quantities yet.
              </td>
            </tr>
          ) : null}
        </tbody>
        <tfoot>
          <tr>
            <td>Total</td>
            <td className="num text-muted">{formatInt(summary.categories.reduce((s, c) => s + c.member_count, 0))}</td>
            {dias.map((d) => (
              <td key={d} className={cn("num", !(summary.total_by_dia_t[String(d)] ?? 0) && "text-muted/50")}>
                {summary.total_by_dia_t[String(d)] ? formatTons(summary.total_by_dia_t[String(d)], false) : "—"}
              </td>
            ))}
            <td className="num text-brand">{formatTons(summary.grand_total_t, false)}</td>
          </tr>
        </tfoot>
      </Table>
    </TableWrap>
  );
}
