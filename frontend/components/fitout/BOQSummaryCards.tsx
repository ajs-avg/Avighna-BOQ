import { Armchair, DoorOpen, Hammer, Lamp, PaintBucket, Plug, ScrollText, Boxes } from "lucide-react";
import type { ReactNode } from "react";
import { formatInt, formatMoney, formatNumber, formatQtyByUnit } from "@/lib/format";
import type { BOQResult, Division } from "@/lib/types";
import { cn } from "@/lib/utils";

const DIVISION_ICON: Record<Division, ReactNode> = {
  preliminaries: <ScrollText />,
  finishes: <PaintBucket />,
  joinery: <Hammer />,
  doors: <DoorOpen />,
  lighting: <Lamp />,
  ffe: <Armchair />,
  mep: <Plug />,
  other: <Boxes />,
};

export function BOQSummaryCards({ boq, currency, onSelectDivision }: { boq: BOQResult; currency: string; onSelectDivision?: (d: Division) => void }) {
  const s = boq.summary;
  const priced = s.priced_lines > 0;
  const qtyBySection = new Map<Division, Record<string, number>>();
  for (const sec of boq.sections) {
    const cur = qtyBySection.get(sec.division) ?? {};
    for (const [u, q] of Object.entries(sec.qty_by_unit)) cur[u] = (cur[u] ?? 0) + q;
    qtyBySection.set(sec.division, cur);
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {s.divisions.map((d) => {
          const qty = formatQtyByUnit(qtyBySection.get(d.division));
          const Btn = onSelectDivision ? "button" : "div";
          return (
            <Btn
              key={d.division}
              type={onSelectDivision ? "button" : undefined}
              onClick={onSelectDivision ? () => onSelectDivision(d.division) : undefined}
              className={cn("card flex flex-col p-5 text-left", onSelectDivision && "transition-shadow hover:border-line-strong hover:shadow-pop")}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">{d.label}</p>
                <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand [&>svg]:size-4">
                  {DIVISION_ICON[d.division] ?? <Boxes />}
                </span>
              </div>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="tnum text-[26px] font-semibold leading-none tracking-tight text-ink">{formatInt(d.line_count)}</span>
                <span className="text-[12.5px] text-muted">line{d.line_count === 1 ? "" : "s"}</span>
              </div>
              {qty ? <p className="tnum mt-2 text-[12.5px] text-ink/80">{qty}</p> : null}
              {priced && d.amount ? <p className="tnum mt-1 text-[12.5px] font-medium text-brand">{formatMoney(d.amount, currency)}</p> : null}
            </Btn>
          );
        })}
        {s.divisions.length === 0 ? <p className="text-[13px] text-muted">No BOQ lines yet.</p> : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="card p-5">
          <p className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">Quantities by unit</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(s.qty_by_unit)
              .filter(([, q]) => q > 0)
              .map(([u, q]) => (
                <span key={u} className="inline-flex items-baseline gap-1 rounded-lg border border-line bg-surface-2 px-3 py-1.5">
                  <span className="tnum text-[16px] font-semibold text-ink">{formatNumber(q, u === "nos" || u === "item" || u === "ls" ? 0 : 1)}</span>
                  <span className="text-[12px] text-muted">{u === "m2" ? "m²" : u === "m3" ? "m³" : u}</span>
                </span>
              ))}
            {Object.keys(s.qty_by_unit).length === 0 ? <span className="text-[13px] text-muted">—</span> : null}
          </div>
          <p className="mt-3 text-[12.5px] text-muted">
            {formatInt(s.line_count)} lines · {formatInt(s.priced_lines)} priced
          </p>
        </div>

        <div
          className={cn(
            "card relative overflow-hidden p-5",
            priced ? "border-brand/30 bg-gradient-to-br from-brand to-brand-dark text-white shadow-[0_12px_32px_-12px_rgba(237,28,36,0.55)]" : "bg-surface-2/60",
          )}
        >
          {priced ? <div className="pointer-events-none absolute -right-10 -top-10 size-36 rounded-full bg-white/10 blur-2xl" aria-hidden /> : null}
          <p className={cn("text-[11.5px] font-semibold uppercase tracking-[0.06em]", priced ? "text-white/80" : "text-muted")}>Grand total</p>
          {priced ? (
            <>
              <p className="tnum mt-2 text-[26px] font-semibold leading-none tracking-tight">{formatMoney(s.grand_total, currency)}</p>
              <dl className="mt-4 space-y-1 text-[12.5px] text-white/85">
                <div className="flex justify-between">
                  <dt>Subtotal</dt>
                  <dd className="tnum">{formatMoney(s.subtotal, currency)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>VAT {formatNumber(s.vat_pct, 0)}%</dt>
                  <dd className="tnum">{formatMoney(s.vat, currency)}</dd>
                </div>
              </dl>
            </>
          ) : (
            <>
              <p className="mt-2 text-[15px] font-semibold text-ink">Unpriced</p>
              <p className="mt-1 text-[12.5px] text-muted">Enter rates on BOQ lines to see amounts, VAT ({formatNumber(s.vat_pct, 0)}%) and the grand total in {currency}.</p>
            </>
          )}
        </div>
      </div>

      {boq.warnings.length ? (
        <div className="card border-warning/30 bg-warning-soft p-4">
          <p className="text-[12.5px] font-semibold text-ink">Warnings</p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-[12.5px] text-ink/85">
            {boq.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
