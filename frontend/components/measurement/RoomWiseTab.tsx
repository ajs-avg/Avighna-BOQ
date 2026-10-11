"use client";

import { ChevronDown, LayoutGrid } from "lucide-react";
import { useMemo, useState } from "react";
import { formatInt, formatNumber, formatShareQty, humanize, qtyDigits, totalsByTradeParts } from "@/lib/format";
import type { MeasurementResult, RoomBreakdown, RoomItemLine } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge, Chip } from "../ui/Badge";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Select, type SelectOption } from "../ui/Select";
import { Table, TableWrap } from "../ui/Table";

export interface RoomWiseTabProps {
  measurement: MeasurementResult;
  className?: string;
}

const ALL = "all";
const COMMON = "common";

/** Stable key for a room card / selector option (room_id is null only for the common section). */
const roomKey = (room: RoomBreakdown, index: number): string => room.room_id ?? `room-${index}`;

/**
 * Room-wise view: one collapsible card per room with that room's share of every item,
 * its openings and misc items, and the materials derived from that share. Items that
 * belong to no single room (RCC, slabs, members, "various") sit in a final common card.
 * Everything is computed by the backend; this tab only groups and formats.
 */
export function RoomWiseTab({ measurement, className }: RoomWiseTabProps) {
  const rooms = useMemo(() => measurement.room_breakdown ?? [], [measurement.room_breakdown]);
  const common = measurement.common_breakdown ?? null;
  const [selected, setSelected] = useState<string>(ALL);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set());

  const options = useMemo<SelectOption[]>(
    () => [
      { value: ALL, label: "All rooms" },
      ...rooms.map((r, i) => ({ value: roomKey(r, i), label: r.level ? `${r.name} · ${r.level}` : r.name })),
      ...(common ? [{ value: COMMON, label: "Common / whole floor" }] : []),
    ],
    [rooms, common],
  );

  const floorArea = rooms.reduce((n, r) => n + (Number.isFinite(r.area_m2) ? r.area_m2 : 0), 0);
  const commonCount = common ? common.items.length + common.openings.length + common.misc.length : 0;

  if (rooms.length === 0 && !common) {
    return (
      <Card className={className}>
        <EmptyState
          icon={<LayoutGrid />}
          title="Room-wise view needs a recompute"
          description="Open Elements and press Save & recompute to build the per-room breakdown from the saved elements."
        />
      </Card>
    );
  }

  // A room that is not in the selector any more (e.g. after a recompute) falls back to "All rooms".
  const current = options.some((o) => o.value === selected) ? selected : ALL;
  const visibleRooms = current === ALL ? rooms.map((room, index) => ({ room, key: roomKey(room, index) })) : rooms.flatMap((room, index) => (roomKey(room, index) === current ? [{ room, key: roomKey(room, index) }] : []));
  const showCommon = !!common && (current === ALL || current === COMMON);
  const visibleKeys = [...visibleRooms.map((v) => v.key), ...(showCommon ? [COMMON] : [])];
  const allCollapsed = visibleKeys.length > 0 && visibleKeys.every((k) => collapsed.has(k));

  const toggle = (key: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const onSelect = (value: string) => {
    setSelected(value);
    // A freshly chosen room always opens expanded.
    setCollapsed(new Set());
  };

  return (
    <div className={cn("space-y-5", className)}>
      <div className="sticky top-16 z-20 -mx-1 px-1 pt-1">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card border border-line bg-surface/95 px-4 py-2.5 shadow-card backdrop-blur supports-[backdrop-filter]:bg-surface/85">
          <label className="flex items-center gap-2 text-[13px] font-semibold text-ink">
            <span className="inline-flex size-7 items-center justify-center rounded-lg bg-brand-soft text-brand">
              <LayoutGrid className="size-4" />
            </span>
            <span className="sr-only">Room</span>
            <span className="w-60">
              <Select size="sm" options={options} value={current} onChange={(e) => onSelect(e.target.value)} aria-label="Room" />
            </span>
          </label>
          <ul className="flex flex-wrap items-center gap-1.5" aria-label="Summary">
            <li>
              <Badge tone="neutral" size="sm" className="bg-surface-2 text-ink">
                <span className="tnum font-semibold">{formatInt(rooms.length)}</span>
                <span className="text-muted">room{rooms.length === 1 ? "" : "s"}</span>
              </Badge>
            </li>
            <li>
              <Badge tone="neutral" size="sm" className="bg-surface-2 text-ink">
                <span className="tnum font-semibold">{formatNumber(floorArea, 1)}</span>
                <span className="text-muted">sqm floor area</span>
              </Badge>
            </li>
            <li>
              <Badge tone="neutral" size="sm" className="bg-surface-2 text-ink">
                <span className="tnum font-semibold">{formatInt(commonCount)}</span>
                <span className="text-muted">common item{commonCount === 1 ? "" : "s"}</span>
              </Badge>
            </li>
          </ul>
          {visibleKeys.length > 1 ? (
            <button
              type="button"
              className="ml-auto text-[12.5px] font-medium text-brand hover:underline"
              onClick={() => setCollapsed(allCollapsed ? new Set() : new Set(visibleKeys))}
            >
              {allCollapsed ? "Expand all" : "Collapse all"}
            </button>
          ) : null}
        </div>
        <p className="px-1 pt-2 text-[12px] text-muted">Each room shows its own share of every item; rooms + common add up to the Measurement Sheet totals.</p>
      </div>

      {visibleRooms.map(({ room, key }) => (
        <RoomCard key={key} room={room} open={!collapsed.has(key)} onToggle={() => toggle(key)} />
      ))}
      {showCommon && common ? <RoomCard room={common} common open={!collapsed.has(COMMON)} onToggle={() => toggle(COMMON)} /> : null}
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Room card                                                                   */
/* ------------------------------------------------------------------------- */

function RoomCard({ room, common = false, open, onToggle }: { room: RoomBreakdown; common?: boolean; open: boolean; onToggle: () => void }) {
  const parts = totalsByTradeParts(room.totals_by_trade);
  const bodyId = `room-body-${room.room_id ?? "common"}`;
  const counts = `${room.items.length} item${room.items.length === 1 ? "" : "s"} · ${room.openings.length + room.misc.length} opening${room.openings.length + room.misc.length === 1 ? "" : "s"}/misc · ${room.materials.length} material row${room.materials.length === 1 ? "" : "s"}`;

  return (
    <Card className={cn("overflow-hidden border-l-4", common ? "border-l-line-strong" : "border-l-brand")}>
      <div
        className={cn("flex cursor-pointer flex-wrap items-start justify-between gap-3 px-5 py-3", open ? "border-b border-line bg-surface-2/60" : "bg-surface-2/30")}
        onClick={onToggle}
      >
        <div className="flex min-w-0 flex-1 items-start gap-2.5">
          <button
            type="button"
            aria-expanded={open}
            aria-controls={bodyId}
            aria-label={open ? `Collapse ${room.name}` : `Expand ${room.name}`}
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
            className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md border border-line bg-surface text-muted hover:text-ink"
          >
            <ChevronDown className={cn("size-3.5 transition-transform", !open && "-rotate-90")} />
          </button>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-[15px] font-semibold leading-6 text-ink">{room.name}</h3>
              {room.level ? <Chip title="Level">{room.level}</Chip> : null}
              {room.wet_area ? (
                <Badge tone="info" size="xs">
                  Wet area
                </Badge>
              ) : null}
              {common ? (
                <Badge tone="neutral" size="xs">
                  Common
                </Badge>
              ) : null}
            </div>
            {common ? (
              <p className="mt-1 text-[12.5px] text-muted">Items not tied to a single room: RCC, slabs, columns &amp; beams, and anything marked &lsquo;various&rsquo;.</p>
            ) : (
              <>
                <p className="tnum mt-1 text-[12.5px] text-ink/85">
                  <span className="text-muted">L × W × H</span> {formatNumber(room.length_m, 2)} × {formatNumber(room.width_m, 2)} × {formatNumber(room.height_m, 2)} m
                  <span className="text-muted"> · Area</span> {formatNumber(room.area_m2, 2)} sqm
                  <span className="text-muted"> · Perimeter</span> {formatNumber(room.perimeter_m, 2)} m
                </p>
                <p className="mt-0.5 text-[12px] text-muted">
                  Floor: <span className="text-ink/85">{room.floor_finish || "—"}</span> · Walls: <span className="text-ink/85">{room.wall_finish || "—"}</span> · Ceiling:{" "}
                  <span className="text-ink/85">{room.ceiling_finish || "—"}</span>
                </p>
              </>
            )}
            {!open ? <p className="mt-0.5 text-[11.5px] text-muted">{counts}</p> : null}
          </div>
        </div>
        {parts.length ? (
          <ul className="tnum flex max-w-[380px] flex-wrap justify-end gap-x-1.5 gap-y-0.5 text-[12px] leading-5 text-muted" aria-label="Totals by trade">
            {parts.map((p, i) => (
              <li key={`${p.trade}-${p.unit}`} className="whitespace-nowrap">
                {i > 0 ? <span className="mr-1.5 text-line-strong">·</span> : null}
                {p.trade} <span className="font-semibold text-ink">{formatNumber(p.value, qtyDigits(p.unit) === 0 ? 0 : 1)}</span> {p.unit}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {open ? (
        <div id={bodyId}>
          <WorkItems items={room.items} />
          <Openings room={room} />
          <Materials room={room} />
        </div>
      ) : null}
    </Card>
  );
}

function SectionHeading({ title, meta }: { title: string; meta?: string }) {
  return (
    <p className="flex items-baseline gap-2 px-5 pb-2 pt-4 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">
      {title}
      {meta ? <span className="tnum font-normal normal-case tracking-normal">· {meta}</span> : null}
    </p>
  );
}

function SectionEmpty({ children }: { children: string }) {
  return <p className="px-5 pb-4 text-[12.5px] text-muted">{children}</p>;
}

/* ------------------------------------------------------------------------- */
/* Sections                                                                    */
/* ------------------------------------------------------------------------- */

interface TradeGroup {
  trade: string;
  lines: RoomItemLine[];
}

function WorkItems({ items }: { items: RoomItemLine[] }) {
  const groups = useMemo<TradeGroup[]>(() => {
    const map = new Map<string, TradeGroup>();
    for (const line of items) {
      const g = map.get(line.trade) ?? { trade: line.trade, lines: [] };
      g.lines.push(line);
      map.set(line.trade, g);
    }
    return Array.from(map.values());
  }, [items]);

  return (
    <section>
      <SectionHeading title="Work items" meta={items.length ? `${items.length} item${items.length === 1 ? "" : "s"} · ${groups.length} trade${groups.length === 1 ? "" : "s"}` : undefined} />
      {items.length === 0 ? (
        <SectionEmpty>No measured items in this room</SectionEmpty>
      ) : (
        <TableWrap flush className="border-b border-line">
          <Table>
            <thead>
              <tr>
                <th className="w-24">Item code</th>
                <th className="min-w-[320px]">Description</th>
                <th className="num w-28">Qty</th>
                <th className="w-16">Unit</th>
              </tr>
            </thead>
            {groups.map((g) => (
              <tbody key={g.trade}>
                <tr>
                  <td colSpan={4} className="!bg-surface-3/70 py-1.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">
                    {g.trade}
                    <span className="tnum ml-2 font-normal normal-case tracking-normal">
                      · {g.lines.length} item{g.lines.length === 1 ? "" : "s"}
                    </span>
                  </td>
                </tr>
                {g.lines.map((line) => (
                  <tr key={line.item_code} className="row-hover">
                    <td>
                      <Chip>{line.item_code}</Chip>
                    </td>
                    <td className="max-w-[560px]">
                      <span className="line-clamp-2 text-ink" title={line.item_title}>
                        {line.item_title}
                      </span>
                    </td>
                    <td className="num font-semibold text-ink">{formatShareQty(line.qty, line.unit)}</td>
                    <td className="text-muted">{line.unit}</td>
                  </tr>
                ))}
              </tbody>
            ))}
          </Table>
        </TableWrap>
      )}
    </section>
  );
}

function Openings({ room }: { room: RoomBreakdown }) {
  const total = room.openings.length + room.misc.length;
  return (
    <section>
      <SectionHeading
        title="Doors, windows & other items"
        meta={total ? `${room.openings.length} opening${room.openings.length === 1 ? "" : "s"} · ${room.misc.length} other` : undefined}
      />
      {total === 0 ? (
        <SectionEmpty>None</SectionEmpty>
      ) : (
        <TableWrap flush className="border-b border-line">
          <Table>
            <thead>
              <tr>
                <th className="w-24">Tag</th>
                <th className="w-28">Type</th>
                <th className="w-36">Size (W × H m)</th>
                <th className="num w-24">Nos</th>
                <th className="min-w-[260px]">Description</th>
              </tr>
            </thead>
            <tbody>
              {room.openings.map((o, i) => (
                <tr key={`o-${o.tag}-${i}`} className="row-hover">
                  <td>{o.tag ? <Chip>{o.tag}</Chip> : <span className="text-muted/50">—</span>}</td>
                  <td className="text-ink">{humanize(o.kind)}</td>
                  <td className="tnum">
                    {formatNumber(o.width_m, 2)} × {formatNumber(o.height_m, 2)}
                  </td>
                  <td className="num font-semibold text-ink">{formatShareQty(o.count, "nos")}</td>
                  <td className="max-w-[460px]">
                    <span className="line-clamp-2" title={o.description}>
                      {o.description || <span className="text-muted/50">—</span>}
                    </span>
                  </td>
                </tr>
              ))}
              {room.misc.map((m, i) => (
                <tr key={`m-${m.tag}-${i}`} className="row-hover">
                  <td>{m.tag ? <Chip>{m.tag}</Chip> : <span className="text-muted/50">—</span>}</td>
                  <td className="text-ink">{m.trade || "—"}</td>
                  <td className="text-muted/50">—</td>
                  <td className="num font-semibold text-ink">
                    {formatShareQty(m.qty, m.unit)} <span className="font-normal text-muted">{m.unit}</span>
                  </td>
                  <td className="max-w-[460px]">
                    <span className="line-clamp-2" title={m.description}>
                      {m.description || <span className="text-muted/50">—</span>}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      )}
    </section>
  );
}

function Materials({ room }: { room: RoomBreakdown }) {
  return (
    <section>
      <SectionHeading title={`Materials for this ${room.room_id ? "room" : "section"}`} meta={room.materials.length ? `${room.materials.length} row${room.materials.length === 1 ? "" : "s"} · norm × qty × (1 + wastage)` : undefined} />
      {room.materials.length === 0 ? (
        <SectionEmpty>No materials (no measured items)</SectionEmpty>
      ) : (
        <div className="grid gap-4 px-5 pb-5 2xl:grid-cols-[minmax(0,1fr)_300px]">
          <TableWrap maxHeight={420}>
            <Table>
              <thead>
                <tr>
                  <th className="min-w-[150px]">Material</th>
                  <th>For item</th>
                  <th className="num">Qty</th>
                  <th className="num">Norm</th>
                  <th className="num whitespace-nowrap">Wastage %</th>
                  <th className="num">Required</th>
                  <th>Unit</th>
                </tr>
              </thead>
              <tbody>
                {room.materials.map((m, i) => (
                  <tr key={`${m.for_item_code}-${m.material}-${i}`} className="row-hover">
                    <td className="font-medium text-ink">{m.material}</td>
                    <td>
                      <Chip className="max-w-[170px]" title={m.for_item_code}>
                        <span className="min-w-0 truncate">{m.for_item_code}</span>
                      </Chip>
                    </td>
                    <td className="num whitespace-nowrap">
                      {formatShareQty(m.boq_qty, m.boq_unit)} <span className="text-muted">{m.boq_unit}</span>
                    </td>
                    <td className="num" title={`${m.norm} ${m.norm_unit} per ${m.boq_unit}`}>
                      {formatNumber(m.norm, 3)}
                    </td>
                    <td className="num">{formatNumber(m.wastage_pct, 1)}</td>
                    <td className="num font-semibold text-ink">{formatNumber(m.required, 2)}</td>
                    <td className="text-muted">{m.norm_unit}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
          <div className="h-fit max-w-md overflow-hidden rounded-card border border-line 2xl:max-w-none">
            <p className="border-b border-line bg-surface-2 px-3 py-2 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">Summary by material</p>
            <Table>
              <thead className="sr-only">
                <tr>
                  <th>Material</th>
                  <th>Required</th>
                  <th>Unit</th>
                </tr>
              </thead>
              <tbody>
                {room.material_totals.map((t) => (
                  <tr key={`${t.material}|${t.unit}`}>
                    <td className="font-medium text-ink">{t.material}</td>
                    <td className="num font-semibold text-brand">{formatNumber(t.required, 2)}</td>
                    <td className="text-muted">{t.unit}</td>
                  </tr>
                ))}
                {room.material_totals.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="text-muted">
                      —
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </Table>
          </div>
        </div>
      )}
    </section>
  );
}
