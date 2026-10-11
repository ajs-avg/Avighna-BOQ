import { formatInt, formatKg, formatM, formatNumber } from "@/lib/format";
import type { BarRow } from "@/lib/types";
import { Chip } from "../ui/Badge";
import { Table, TableWrap } from "../ui/Table";

const DIM_KEYS = ["a", "b", "c", "d", "e", "f", "g"] as const;

export function BarRowsTable({ rows, className }: { rows: BarRow[]; className?: string }) {
  const total = rows.reduce((s, r) => s + r.weight_kg, 0);
  const dim = (v: number) => (v ? formatM(v) : <span className="text-muted/40">·</span>);
  return (
    <TableWrap className={className} maxHeight={520}>
      <Table className="text-[12.5px]">
        <thead>
          <tr>
            <th className="num">Sr</th>
            <th className="min-w-[200px]">Description</th>
            <th className="num">Dia</th>
            <th className="num">Members</th>
            <th className="num">Bars / mbr</th>
            <th className="num">Total bars</th>
            {DIM_KEYS.map((k) => (
              <th key={k} className="num">
                {k}
              </th>
            ))}
            <th className="num">Bends</th>
            <th className="num">Cut len (m)</th>
            <th className="num">Weight (kg)</th>
            <th className="min-w-[260px]">Formula trace</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.seq}>
              <td className="num text-muted">{r.seq}</td>
              <td>
                <span className="font-medium">{r.description}</span>
                {r.spacing_mm && !r.description.includes("@") ? <span className="ml-1.5 text-muted">@ {formatNumber(r.spacing_mm, 0)} c/c</span> : null}
                <Chip className="ml-2 align-middle">{r.shape}</Chip>
              </td>
              <td className="num font-semibold">T{r.dia_mm}</td>
              <td className="num">{formatInt(r.members)}</td>
              <td className="num">{formatNumber(r.bars_per_member, Number.isInteger(r.bars_per_member) ? 0 : 2)}</td>
              <td className="num">{formatNumber(r.total_bars, Number.isInteger(r.total_bars) ? 0 : 2)}</td>
              {DIM_KEYS.map((k) => (
                <td key={k} className="num">
                  {dim(r[k])}
                </td>
              ))}
              <td className="num">{r.bend_corners || <span className="text-muted/40">·</span>}</td>
              <td className="num">{formatM(r.cut_length_m)}</td>
              <td className="num font-semibold">{formatKg(r.weight_kg, false)}</td>
              <td className="max-w-[420px] truncate font-mono text-[11.5px] text-muted" title={r.formula}>
                {r.formula}
              </td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={17} className="py-6 text-center text-muted">
                No bar rows — recalculate after editing the member.
              </td>
            </tr>
          ) : null}
        </tbody>
        {rows.length ? (
          <tfoot>
            <tr>
              <td colSpan={15} className="text-right">
                Member total
              </td>
              <td className="num text-brand">{formatKg(total, false)}</td>
              <td />
            </tr>
          </tfoot>
        ) : null}
      </Table>
    </TableWrap>
  );
}
