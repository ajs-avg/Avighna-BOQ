"use client";

import { FileImage, Image as ImageIcon, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getPreviewBlobUrl, getSheets } from "@/lib/api";
import { formatInt, humanize } from "@/lib/format";
import type { Module, SheetRecord } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { PreviewLightbox } from "./PreviewLightbox";
import { Alert } from "./ui/Alert";
import { Badge, Chip } from "./ui/Badge";
import { Button } from "./ui/Button";
import { EmptyState } from "./ui/EmptyState";
import { Skeleton } from "./ui/Skeleton";

export function SheetsTab({ jobId, module, refreshKey }: { jobId: string; module: Module; refreshKey?: string | number }) {
  const [sheets, setSheets] = useState<SheetRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Sheet open in the lightbox; prev / next move through the sheets that have a preview.
  const [openId, setOpenId] = useState<string | null>(null);

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

  const previewable = sheets.filter((s) => !!s.preview_path);
  const openIndex = previewable.findIndex((s) => s.id === openId);

  return (
    <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sheets.map((s) => (
          <SheetCard key={s.id} sheet={s} module={module} onOpen={() => setOpenId(s.id)} />
        ))}
      </div>
      <PreviewLightbox
        jobId={jobId}
        sheets={previewable}
        index={Math.max(0, openIndex)}
        open={openIndex >= 0}
        onClose={() => setOpenId(null)}
        onIndexChange={(i) => setOpenId(previewable[i]?.id ?? null)}
      />
    </>
  );
}

function SheetCard({ sheet, module, onOpen }: { sheet: SheetRecord; module: Module; onOpen: () => void }) {
  const c = sheet.classification;
  // Measurement sheets are quantity take-offs, so they share the BOQ relevance flag.
  const relevant = module === "structural" ? c.relevant_for_bbs : c.relevant_for_boq;
  const relevantLabel = module === "structural" ? "BBS relevant" : module === "fitout" ? "BOQ relevant" : "Measured";
  return (
    <article className="card flex flex-col overflow-hidden">
      <SheetPreview jobId={sheet.job_id} sheetId={sheet.id} hasPreview={!!sheet.preview_path} alt={`${sheet.file_name} page ${sheet.page_no}`} onOpen={onOpen} />
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

function SheetPreview({ jobId, sheetId, hasPreview, alt, onOpen }: { jobId: string; sheetId: string; hasPreview: boolean; alt: string; onOpen: () => void }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

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

  if (url) {
    return (
      <button
        type="button"
        onClick={onOpen}
        title="Open full-size preview"
        className="relative block aspect-[4/3] w-full cursor-zoom-in overflow-hidden border-b border-line bg-white focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand"
      >
        {/* Blob URLs cannot go through next/image's optimizer. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt={alt} className="size-full object-contain" />
      </button>
    );
  }

  return (
    <div className={cn("relative aspect-[4/3] w-full overflow-hidden border-b border-line bg-surface-2")}>
      {failed || !hasPreview ? (
        <div className="flex size-full flex-col items-center justify-center gap-2 text-muted">
          <ImageIcon className="size-6" />
          <span className="text-[12px]">{hasPreview ? "Preview unavailable" : "No preview"}</span>
        </div>
      ) : (
        <Skeleton className="size-full rounded-none" />
      )}
    </div>
  );
}
