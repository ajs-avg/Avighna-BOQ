import { DoorOpen } from "lucide-react";
import { formatNumber } from "@/lib/format";
import type { RoomRecord } from "@/lib/types";
import { ConfidenceBadge } from "../ConfidenceBadge";
import { Chip } from "../ui/Badge";
import { EmptyState } from "../ui/EmptyState";
import { EmptyRow, Table, TableWrap } from "../ui/Table";

export function RoomsTable({ rooms }: { rooms: RoomRecord[] }) {
  const totalArea = rooms.reduce((s, r) => s + (r.area_m2 ?? 0), 0);
  return (
    <TableWrap maxHeight={640}>
      <Table>
        <thead>
          <tr>
            <th className="min-w-[180px]">Room / space</th>
            <th className="num">Area (m²)</th>
            <th className="num">Perimeter (m)</th>
            <th className="num">Ceiling ht (m)</th>
            <th>Floor finish</th>
            <th>Wall finishes</th>
            <th>Ceiling finish</th>
            <th>Source</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {rooms.length === 0 ? (
            <EmptyRow colSpan={9}>
              <EmptyState compact icon={<DoorOpen />} title="No rooms detected" description="Room areas appear here once the GA / setting-out plans have been read." />
            </EmptyRow>
          ) : (
            rooms.map((r) => (
              <tr key={r.id}>
                <td className="font-medium">{r.name}</td>
                <td className="num">{r.area_m2 != null ? formatNumber(r.area_m2, 2) : "—"}</td>
                <td className="num">{r.perimeter_m != null ? formatNumber(r.perimeter_m, 2) : "—"}</td>
                <td className="num">{r.ceiling_height_m != null ? formatNumber(r.ceiling_height_m, 2) : "—"}</td>
                <td>{r.floor_finish ? <Chip>{r.floor_finish}</Chip> : <span className="text-muted/60">—</span>}</td>
                <td>
                  <div className="flex flex-wrap gap-1">
                    {r.wall_finishes.length ? r.wall_finishes.map((w, i) => <Chip key={`${w}-${i}`}>{w}</Chip>) : <span className="text-muted/60">—</span>}
                  </div>
                </td>
                <td>{r.ceiling_finish ? <Chip>{r.ceiling_finish}</Chip> : <span className="text-muted/60">—</span>}</td>
                <td className="max-w-[160px] truncate text-[12px] text-muted" title={r.source_sheet ?? undefined}>
                  {r.source_sheet ?? "—"}
                </td>
                <td>
                  <ConfidenceBadge value={r.confidence} size="xs" />
                </td>
              </tr>
            ))
          )}
        </tbody>
        {rooms.length ? (
          <tfoot>
            <tr>
              <td>{rooms.length} rooms</td>
              <td className="num text-brand">{formatNumber(totalArea, 2)}</td>
              <td colSpan={7} />
            </tr>
          </tfoot>
        ) : null}
      </Table>
    </TableWrap>
  );
}
