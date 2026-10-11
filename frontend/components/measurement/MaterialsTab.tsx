"use client";

import { Package } from "lucide-react";
import { useMemo } from "react";
import { formatInt, formatNumber, qtyDigits } from "@/lib/format";
import type { MaterialRow } from "@/lib/types";
import { Chip } from "../ui/Badge";
import { Card, CardHeader } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Table, TableWrap } from "../ui/Table";

export interface MaterialsTabProps {
  materials: MaterialRow[];
}

interface MaterialTotal {
  material: string;
  unit: string;
  required: number;
  items: number;
}

/** Material requirement per BOQ item plus a roll-up by material. */
export function MaterialsTab({ materials }: MaterialsTabProps) {
  const totals = useMemo<MaterialTotal[]>(() => {
    const map = new Map<string, MaterialTotal>();
    for (const m of materials) {
      const key = `${m.material}|${m.norm_unit}`;
      const t = map.get(key) ?? { material: m.material, unit: m.norm_unit, required: 0, items: 0 };
      t.required += m.required;
      t.items += 1;
      map.set(key, t);
    }
    return Array.from(map.values());
  }, [materials]);

  if (materials.length === 0) {
    return (
      <Card>
        <EmptyState icon={<Package />} title="No materials yet" description="Material requirements are derived from the BOQ using the company norms. Add elements and save to compute them." />
      </Card>
    );
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <Card className="overflow-hidden">
        <CardHeader title="Material requirement" description={`${formatInt(materials.length)} rows · norm × BOQ qty × (1 + wastage)`} className="py-3" />
        <TableWrap flush maxHeight={720}>
          <Table>
            <thead>
              <tr>
                <th className="min-w-[160px]">Material</th>
                <th>For item</th>
                <th className="num">BOQ qty</th>
                <th>Unit</th>
                <th className="num">Norm</th>
                <th className="num">Wastage %</th>
                <th className="num">Required</th>
                <th>Material unit</th>
                <th>Basis</th>
              </tr>
            </thead>
            <tbody>
              {materials.map((m, i) => (
                <tr key={`${m.for_item_code}-${m.material}-${i}`} className="row-hover">
                  <td className="font-medium text-ink">{m.material}</td>
                  <td>
                    <Chip>{m.for_item_code}</Chip>
                  </td>
                  <td className="num">{formatNumber(m.boq_qty, qtyDigits(m.boq_unit))}</td>
                  <td className="text-muted">{m.boq_unit}</td>
                  <td className="num" title={`${m.norm} ${m.norm_unit} per ${m.boq_unit}`}>
                    {formatNumber(m.norm, 3)}
                  </td>
                  <td className="num">{formatNumber(m.wastage_pct, 1)}</td>
                  <td className="num font-semibold text-ink">{formatNumber(m.required, 2)}</td>
                  <td className="text-muted">{m.norm_unit}</td>
                  <td className="max-w-[220px] truncate text-[12px] text-muted" title={m.basis || undefined}>
                    {m.basis || <span className="text-muted/50">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      </Card>

      <Card className="h-fit overflow-hidden">
        <CardHeader title="Summary by material" description="Required quantities summed across items." className="py-3" />
        <TableWrap flush>
          <Table>
            <thead>
              <tr>
                <th>Material</th>
                <th className="num">Required</th>
                <th>Unit</th>
              </tr>
            </thead>
            <tbody>
              {totals.map((t) => (
                <tr key={`${t.material}|${t.unit}`}>
                  <td className="font-medium text-ink" title={`${t.items} item${t.items === 1 ? "" : "s"}`}>
                    {t.material}
                  </td>
                  <td className="num font-semibold text-brand">{formatNumber(t.required, 2)}</td>
                  <td className="text-muted">{t.unit}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      </Card>
    </div>
  );
}
