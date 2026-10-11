"use client";

import { FileImage, Image as ImageIcon, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getPreviewBlobUrl, getSheets } from "@/lib/api";
import { formatInt, humanize } from "@/lib/format";
import type { Module, SheetRecord } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Alert } from "./ui/Alert";
import { Badge, Chip } from "./ui/Badge";
import { Button } from "./ui/Button";
import { EmptyState } from "./ui/EmptyState";
import { Skeleton } from "./ui/Skeleton";

export function SheetsTab({ jobId, module, refreshKey }: { jobId: string; module: Module; refreshKey?: string | number }) {
  const [sheets, setSheets] = useState<SheetRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSheets(await getSheets(jobId));
    } catch (err) {
      setError(errorMessage(err));
      setSheets([]);
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (error) {
    return (
      <Alert tone="danger" title="Could not load sheets" actions={<Button size="sm" variant="secondary" leftIcon={<RefreshCw />} onClick={() => void load()}>Retry</Button>}>
        {error}
      </Alert>
    );
  }

  if (sheets === null) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card overflow-hidden">
            <Skeleton className="aspect-[4/3] rounded-none" />
            <div className="space-y-2 p-4">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (sheets.length === 0) {
    return (
      <div className="card">
        <EmptyState icon={<FileImage />} title="No sheets yet" description="Sheets appear once the drawings have been converted and classified." />
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {sheets.map((s) => (
        <SheetCard key={s.id} sheet={s} module={module} />
      ))}
    </div>
  );
}

function SheetCard({ sheet, module }: { sheet: SheetRecord; module: Module }) {
  const c = sheet.classification;
  // Measurement sheets are quantity take-offs, so they share the BOQ relevance flag.
  const relevant = module === "structural" ? c.relevant_for_bbs : c.relevant_for_boq;
  const relevantLabel = module === "structural" ? "BBS relevant" : module === "fitout" ? "BOQ relevant" : "Measured";
  return (
    <article className="card flex flex-col overflow-hidden">
      <SheetPreview jobId={sheet.job_id} sheetId={sheet.id} hasPreview={!!sheet.preview_path} alt={`${sheet.file_name} page ${sheet.page_no}`} />
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-[13.5px] font-semibold text-ink" title={c.title ?? sheet.file_name}>
              {c.title || sheet.file_name}
            </p>
            <p className="truncate text-[12px] text-muted" title={sheet.file_name}>
              {sheet.file_name}
              {sheet.page_no > 1 || sheet.layout !== "Model" ? ` · p.${sheet.page_no} · ${sheet.layout}` : ""}
            </p>
          </div>
          <Badge tone={relevant ? "success" : "neutral"} size="xs">
            {relevant ? relevantLabel : "Not used"}
          </Badge>
        </div>

        <div className="flex flex-wrap gap-1.5">
          <Chip>{humanize(c.sheet_type)}</Chip>
          <Chip>{humanize(c.discipline)}</Chip>
          {c.drawing_number ? <Chip title="Drawing number">{c.drawing_number}</Chip> : null}
          {c.level ? <Chip title="Level">{c.level}</Chip> : null}
          {c.scale ? <Chip title="Scale">{c.scale}</Chip> : null}
          {c.units !== "unknown" ? <Chip title="Units">{c.units}</Chip> : null}
        </div>

        {c.summary ? <p className="line-clamp-3 text-[12.5px] leading-5 text-muted">{c.summary}</p> : null}

        <div className="mt-auto flex items-center justify-between pt-1 text-[12px] text-muted">
          <span>{formatInt(sheet.text_count)} text entities</span>
          <ConfidenceBadge value={c.confidence} size="xs" />
        </div>

        {sheet.processing_notes.length ? (
          <details className="rounded-lg border border-line bg-surface-2/60 px-3 py-2 text-[12px]">
            <summary className="cursor-pointer font-medium text-ink">Processing notes ({sheet.processing_notes.length})</summary>
            <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-muted">
              {sheet.processing_notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </article>
  );
}

function SheetPreview({ jobId, sheetId, hasPreview, alt }: { jobId: string; sheetId: string; hasPreview: boolean; alt: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!hasPreview) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    getPreviewBlobUrl(jobId, sheetId)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u);
          return;
        }
        objectUrl = u;
        setUrl(u);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [jobId, sheetId, hasPreview]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <div className={cn("relative aspect-[4/3] w-full overflow-hidden border-b border-line bg-surface-2", url && "cursor-zoom-in")} onClick={() => url && setOpen(true)}>
        {url ? (
          // Blob URLs cannot go through next/image's optimizer.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={alt} className="size-full object-contain" />
        ) : failed || !hasPreview ? (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-muted">
            <ImageIcon className="size-6" />
            <span className="text-[12px]">{hasPreview ? "Preview unavailable" : "No preview"}</span>
          </div>
        ) : (
          <Skeleton className="size-full rounded-none" />
        )}
      </div>
      {open && url ? (
        <div className="fixed inset-0 z-[85] flex items-center justify-center bg-ink/80 p-4 animate-fade-in" onClick={() => setOpen(false)} role="dialog" aria-modal="true" aria-label={alt}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt={alt} className="max-h-full max-w-full rounded-lg bg-white object-contain shadow-modal" />
        </div>
      ) : null}
    </>
  );
}
