"use client";

import { AlertTriangle, CheckCircle2, Image as ImageIcon, Maximize2, X } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getPreviewBlobUrl, getSheets } from "@/lib/api";
import type { ElBase, JobRecord, MemberEl, MeasurementExtraction, SheetRecord, SlabEl, WallEl } from "@/lib/types";
import { cn } from "@/lib/utils";
import { EvidenceButton } from "./EvidenceButton";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";

/**
 * The Review tab: the whole floor at a glance, in plain words.
 *
 * 1. The coloured check picture (green = read cleanly, amber = flagged) when the
 *    structural reader produced one; otherwise the sheet preview.
 * 2. "Needs your look": every flagged element with its reason, first.
 * 3. Section-wise detail: columns & walls, beams, slabs — name, size, length, state.
 */

const flagsOf = (e: ElBase): string[] => e.flags ?? [];
const needsLook = (e: ElBase): boolean => flagsOf(e).length > 0 || e.confidence < 0.6;

export function reviewAttentionCount(ex: MeasurementExtraction | null | undefined): number {
  if (!ex) return 0;
  const lists: ElBase[][] = [ex.rooms, ex.openings, ex.walls, ex.slabs, ex.members, ex.misc];
  return lists.reduce((n, l) => n + l.filter(needsLook).length, 0);
}

/** B2 before B10, C1 before C1A. */
function naturalCompare(a: string, b: string): number {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}

const mm = (m: number) => Math.round(m * 1000);
const m2 = (v: number) => (Math.round(v * 100) / 100).toFixed(2);

function StateDot({ el }: { el: ElBase }) {
  if (needsLook(el)) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-warning">
        <AlertTriangle className="size-3.5" /> Check
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-success">
      <CheckCircle2 className="size-3.5" /> OK
    </span>
  );
}

function Stat({ value, label, tone }: { value: number; label: string; tone?: "warning" }) {
  return (
    <div
      className={cn(
        "flex-1 rounded-xl border px-4 py-3 text-center",
        tone === "warning" && value > 0 ? "border-warning/40 bg-warning-soft" : "border-line bg-surface-2/60",
      )}
    >
      <p className={cn("tnum text-[26px] font-semibold leading-none", tone === "warning" && value > 0 ? "text-warning" : "text-ink")}>{value}</p>
      <p className="mt-1.5 text-[11.5px] font-medium uppercase tracking-[0.06em] text-muted">{label}</p>
    </div>
  );
}

/** The check picture (or sheet preview), expandable to full screen. */
function CheckPicture({ job }: { job: JobRecord }) {
  const [sheet, setSheet] = useState<SheetRecord | null | undefined>(undefined); // undefined = loading
  const [url, setUrl] = useState<string | null>(null);
  const [isCheck, setIsCheck] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    let obj: string | null = null;
    (async () => {
      try {
        const sheets = await getSheets(job.id);
        const withCheck = sheets.find((s) => s.check_picture_path);
        const chosen = withCheck ?? sheets.find((s) => s.preview_path) ?? null;
        if (!alive) return;
        setSheet(chosen);
        setIsCheck(!!withCheck);
        if (chosen) {
          obj = await getPreviewBlobUrl(job.id, chosen.id, withCheck ? "check" : "thumb");
          if (alive) setUrl(obj);
          else if (obj) URL.revokeObjectURL(obj);
        }
      } catch {
        if (alive) setSheet(null);
      }
    })();
    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [job.id, job.updated_at]);

  if (sheet === undefined) return <Skeleton className="aspect-[16/10] w-full rounded-xl" />;
  if (!sheet || !url) {
    return (
      <div className="flex aspect-[16/10] w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line bg-surface-2 text-muted">
        <ImageIcon className="size-6" />
        <span className="text-[12.5px]">No drawing picture for this job yet.</span>
      </div>
    );
  }
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group relative block w-full cursor-zoom-in overflow-hidden rounded-xl border border-line bg-white hover:border-brand/50"
        title="Open full size"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt="Check picture of the floor" className="max-h-[520px] w-full object-contain" />
        <span className="pointer-events-none absolute right-2.5 top-2.5 inline-flex size-8 items-center justify-center rounded-md bg-white/90 text-ink opacity-0 shadow-card transition-opacity group-hover:opacity-100 [&>svg]:size-4">
          <Maximize2 />
        </span>
        {isCheck ? (
          <span className="pointer-events-none absolute bottom-2.5 left-2.5 rounded-md bg-ink/80 px-2 py-1 text-[11.5px] font-medium text-white">
            Green = read cleanly · Amber = check it · Grey = small member, no schedule row
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="fixed inset-0 z-50 overflow-auto bg-ink/90 p-4" role="dialog" aria-label="Check picture, full size" onClick={() => setOpen(false)}>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="fixed right-4 top-4 z-10 inline-flex size-10 items-center justify-center rounded-full bg-white text-ink shadow-card [&>svg]:size-5"
            aria-label="Close"
          >
            <X />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt="Check picture, full size" className="mx-auto min-w-[900px] max-w-[1800px]" onClick={(e) => e.stopPropagation()} />
        </div>
      ) : null}
    </>
  );
}

function Section({ title, hint, children, count }: { title: string; hint: string; count: number; children: ReactNode }) {
  return (
    <Card>
      <CardHeader title={`${title} (${count})`} description={hint} className="py-3" />
      {children}
    </Card>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  if (rows.length === 0) return <CardBody className="py-4 text-[13px] text-muted">None found on this drawing.</CardBody>;
  return (
    <div className="scrollbar-thin max-h-[420px] overflow-auto">
      <table className="w-full text-[13px]">
        <thead className="sticky top-0 bg-surface-1">
          <tr className="border-b border-line text-left text-[11.5px] uppercase tracking-[0.05em] text-muted">
            {head.map((h, i) => (
              <th key={i} className={cn("px-5 py-2 font-semibold", i >= head.length - 1 && "text-right")}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((cells, i) => (
            <tr key={i} className="hover:bg-surface-2/50">
              {cells.map((c, j) => (
                <td key={j} className={cn("px-5 py-2", j >= cells.length - 1 && "text-right")}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReviewTab({ job }: { job: JobRecord }) {
  const ex = job.elements;
  const walls = useMemo(() => [...(ex?.walls ?? [])].sort((a, b) => naturalCompare(a.tag, b.tag)), [ex]);
  const columns = useMemo(() => (ex?.members ?? []).filter((m) => m.kind === "column").sort((a, b) => naturalCompare(a.tag, b.tag)), [ex]);
  const beams = useMemo(() => (ex?.members ?? []).filter((m) => m.kind === "beam").sort((a, b) => naturalCompare(a.tag, b.tag)), [ex]);
  const slabs = useMemo(() => [...(ex?.slabs ?? [])].sort((a, b) => naturalCompare(a.tag, b.tag)), [ex]);

  const flagged: { el: ElBase; label: string; kind: string }[] = useMemo(() => {
    const out: { el: ElBase; label: string; kind: string }[] = [];
    for (const w of walls) if (needsLook(w)) out.push({ el: w, label: w.tag, kind: "wall" });
    for (const c of columns) if (needsLook(c)) out.push({ el: c, label: c.tag, kind: "column" });
    for (const b of beams) if (needsLook(b)) out.push({ el: b, label: b.tag, kind: "beam" });
    for (const s of slabs) if (needsLook(s)) out.push({ el: s, label: s.tag, kind: "slab" });
    for (const r of ex?.rooms ?? []) if (needsLook(r)) out.push({ el: r, label: r.name, kind: "room" });
    for (const m of ex?.misc ?? []) if (needsLook(m)) out.push({ el: m, label: m.description, kind: "item" });
    return out;
  }, [ex, walls, columns, beams, slabs]);

  if (!ex) {
    return (
      <Card>
        <CardBody className="py-8 text-center text-[13px] text-muted">Nothing read yet — this fills in once the drawing is processed.</CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {/* 1 — what was read, in numbers */}
      <div className="flex flex-wrap gap-3">
        <Stat value={columns.length + walls.length} label="Columns & walls" />
        <Stat value={beams.length} label="Beams" />
        <Stat value={slabs.length} label="Slabs" />
        <Stat value={flagged.length} label="Need your look" tone="warning" />
      </div>

      {/* 2 — the drawing itself, coloured */}
      <CheckPicture job={job} />

      {/* 3 — flagged first */}
      {flagged.length > 0 ? (
        <Card className="border-warning/40">
          <CardHeader
            title={`Needs your look (${flagged.length})`}
            description="The reader found these but something disagrees. Open the Elements tab to correct one."
            className="py-3"
          />
          <ul className="divide-y divide-line">
            {flagged.map(({ el, label, kind }) => (
              <li key={el.id} className="flex items-start gap-3 px-5 py-2.5">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-ink">
                    {label} <span className="font-normal text-muted">· {kind}</span>
                  </p>
                  <p className="text-[12.5px] text-ink/80">
                    {flagsOf(el).length ? flagsOf(el).join("; ") : "Read with low confidence — worth a glance."}
                  </p>
                </div>
                <EvidenceButton evidence={el.evidence} sourceSheet={el.source_sheet} subject={label} />
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <Card className="border-success/40">
          <CardBody className="flex items-center gap-2.5 py-3.5 text-[13px] font-medium text-success">
            <CheckCircle2 className="size-4.5" /> Nothing is flagged — every element read cleanly.
          </CardBody>
        </Card>
      )}

      {/* 4 — section-wise detail */}
      <Section title="Columns & walls" hint="Size is the drawn shape; height is assumed until the section drawing is added." count={columns.length + walls.length}>
        <Table
          head={["Name", "Size (mm)", "Height (m)", "State"]}
          rows={[
            ...columns.map((c: MemberEl) => [
              <b key="n">{c.tag}</b>,
              `${mm(c.width_m)} × ${mm(c.depth_m)}`,
              c.length_m.toFixed(2),
              <StateDot key="s" el={c} />,
            ]),
            ...walls.map((w: WallEl) => [
              <b key="n">{w.tag}</b>,
              `${mm(w.thickness_m)} × ${mm(w.length_m)}`,
              w.height_m.toFixed(2),
              <StateDot key="s" el={w} />,
            ]),
          ]}
        />
      </Section>

      <Section title="Beams" hint="Length is traced along the drawn lines, face to face of the supports." count={beams.length}>
        <Table
          head={["Name", "Size (mm)", "Length (m)", "State"]}
          rows={beams.map((b: MemberEl) => [
            <b key="n">{b.tag}</b>,
            `${mm(b.width_m)} × ${mm(b.depth_m)}`,
            b.length_m.toFixed(2),
            <StateDot key="s" el={b} />,
          ])}
        />
      </Section>

      <Section title="Slabs" hint="Area is the real panel between the beams (L-shapes kept), not a guessed rectangle." count={slabs.length}>
        <Table
          head={["Mark", "Area (m²)", "Thickness (mm)", "State"]}
          rows={slabs.map((s: SlabEl) => [
            <b key="n">{s.tag}</b>,
            m2(s.length_m * s.width_m),
            mm(s.thickness_m),
            <StateDot key="s" el={s} />,
          ])}
        />
      </Section>
    </div>
  );
}
