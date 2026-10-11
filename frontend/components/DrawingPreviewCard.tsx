"use client";

import { FileImage, Image as ImageIcon, Maximize2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { getPreviewBlobUrl, getSheets } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { JobRecord, SheetRecord } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { PreviewLightbox } from "./PreviewLightbox";
import { IconButton } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { Skeleton } from "./ui/Skeleton";

/**
 * Thumb object URLs for the given sheet ids, loaded once each and revoked on unmount
 * (and for ids that disappear, e.g. after a reprocess).
 */
function useThumbUrls(jobId: string, ids: string[]): { urls: Record<string, string>; failed: ReadonlySet<string> } {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [failed, setFailed] = useState<ReadonlySet<string>>(new Set());
  const urlsRef = useRef<Record<string, string>>({});
  const pending = useRef(new Set<string>());
  const wantedRef = useRef(new Set<string>());
  const alive = useRef(true);
  const idsKey = ids.join("|");

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      for (const u of Object.values(urlsRef.current)) URL.revokeObjectURL(u);
      urlsRef.current = {};
    };
  }, [jobId]);

  useEffect(() => {
    const wanted = new Set(idsKey ? idsKey.split("|") : []);
    wantedRef.current = wanted;
    // Drop URLs for sheets that no longer exist.
    let changed = false;
    for (const id of Object.keys(urlsRef.current)) {
      if (!wanted.has(id)) {
        URL.revokeObjectURL(urlsRef.current[id]);
        delete urlsRef.current[id];
        changed = true;
      }
    }
    if (changed) setUrls({ ...urlsRef.current });

    for (const id of wanted) {
      if (urlsRef.current[id] || pending.current.has(id)) continue;
      pending.current.add(id);
      getPreviewBlobUrl(jobId, id, "thumb")
        .then((u) => {
          pending.current.delete(id);
          // Discard a late result if we unmounted, the sheet went away, or a duplicate request already landed.
          if (!alive.current || !wantedRef.current.has(id) || urlsRef.current[id]) {
            URL.revokeObjectURL(u);
            return;
          }
          urlsRef.current = { ...urlsRef.current, [id]: u };
          setUrls(urlsRef.current);
        })
        .catch(() => {
          pending.current.delete(id);
          if (alive.current) setFailed((prev) => new Set(prev).add(id));
        });
    }
  }, [jobId, idsKey]);

  return { urls, failed };
}

export function DrawingPreviewCard({ job }: { job: JobRecord }) {
  const [sheets, setSheets] = useState<SheetRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setSheets(await getSheets(job.id));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
      setSheets((prev) => prev ?? []);
    }
  }, [job.id]);

  // Reload on mount and whenever the pipeline moves on: previews appear while the job is still processing.
  useEffect(() => {
    void load();
  }, [load, job.status, job.sheet_count]);

  const previewable = (sheets ?? []).filter((s) => !!s.preview_path);
  const previewIds = previewable.map((s) => s.id);
  const { urls, failed } = useThumbUrls(job.id, previewIds);

  const activeIndex = Math.max(
    0,
    previewable.findIndex((s) => s.id === activeId),
  );
  const active: SheetRecord | null = previewable[activeIndex] ?? sheets?.[0] ?? null;
  const activeUrl = active ? urls[active.id] : undefined;
  const hasPreviews = previewable.length > 0;

  const openLightbox = () => {
    if (hasPreviews) setOpen(true);
  };

  return (
    <Card>
      <CardHeader
        title="Drawing preview"
        description={hasPreviews ? "Click to expand" : undefined}
        className="py-3"
        actions={
          hasPreviews ? (
            <IconButton label="Expand" onClick={openLightbox}>
              <Maximize2 />
            </IconButton>
          ) : undefined
        }
      />
      <CardBody className="space-y-3 py-3">
        {sheets === null ? (
          <div className="space-y-2" aria-busy>
            <Skeleton className="aspect-[4/3] w-full rounded-lg" />
            <Skeleton className="h-3.5 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        ) : error && sheets.length === 0 ? (
          <div className="flex items-center justify-between gap-2 text-[12.5px] text-muted">
            <span className="min-w-0 truncate" title={error}>
              Could not load previews.
            </span>
            <IconButton label="Retry" size="xs" onClick={() => void load()}>
              <RefreshCw />
            </IconButton>
          </div>
        ) : !active ? (
          <div className="flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line bg-surface-2 px-4 text-center text-muted">
            <FileImage className="size-6" />
            <span className="text-[12.5px]">Previews appear once the sheets are read.</span>
          </div>
        ) : (
          <>
            {active.preview_path && activeUrl ? (
              <button
                type="button"
                onClick={openLightbox}
                className="group relative block aspect-[4/3] w-full cursor-zoom-in overflow-hidden rounded-lg border border-line bg-white transition-colors hover:border-brand/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                title="Open full-size preview"
              >
                {/* Blob URLs cannot go through next/image's optimizer. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={activeUrl} alt={`${active.file_name} preview`} className="size-full object-contain transition-transform duration-300 group-hover:scale-[1.02]" />
                {previewable.length > 0 ? (
                  <span className="pointer-events-none absolute bottom-2 left-2 rounded-md bg-ink/75 px-1.5 py-0.5 text-[11px] font-medium leading-4 text-white">
                    Sheet {activeIndex + 1} of {previewable.length}
                  </span>
                ) : null}
                <span className="pointer-events-none absolute right-2 top-2 inline-flex size-7 items-center justify-center rounded-md bg-white/90 text-ink opacity-0 shadow-card transition-opacity group-hover:opacity-100 [&>svg]:size-3.5">
                  <Maximize2 />
                </span>
              </button>
            ) : (
              <div className="flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 rounded-lg border border-line bg-surface-2 text-muted">
                {active.preview_path && !failed.has(active.id) ? (
                  <Skeleton className="size-full rounded-lg" />
                ) : (
                  <>
                    <ImageIcon className="size-6" />
                    <span className="text-[12.5px]">{active.preview_path ? "Preview unavailable" : "No preview for this sheet"}</span>
                  </>
                )}
              </div>
            )}

            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium text-ink" title={active.file_name}>
                {active.file_name}
              </p>
              <p className="truncate text-[12px] text-muted">
                {active.page_no === 1 && active.layout === "Model" ? "Model space" : `${active.layout} · p.${active.page_no}`} · {humanize(active.classification.sheet_type)}
              </p>
            </div>

            {previewable.length > 1 ? (
              <div className="scrollbar-thin -mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="listbox" aria-label="Sheets">
                {previewable.map((s, i) => {
                  const u = urls[s.id];
                  const selected = i === activeIndex;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      onClick={() => setActiveId(s.id)}
                      onDoubleClick={() => {
                        setActiveId(s.id);
                        setOpen(true);
                      }}
                      title={`${s.file_name} — ${humanize(s.classification.sheet_type)}`}
                      className={cn(
                        "relative h-14 w-[74px] shrink-0 overflow-hidden rounded-md border bg-white transition-[border-color,box-shadow]",
                        selected ? "border-brand ring-2 ring-brand/30" : "border-line hover:border-line-strong",
                      )}
                    >
                      {u ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={u} alt="" className="size-full object-contain" />
                      ) : failed.has(s.id) ? (
                        <span className="flex size-full items-center justify-center text-muted">
                          <ImageIcon className="size-4" />
                        </span>
                      ) : (
                        <Skeleton className="size-full rounded-none" />
                      )}
                      <span className="pointer-events-none absolute bottom-0.5 right-0.5 rounded bg-ink/70 px-1 text-[9.5px] font-medium leading-3.5 text-white">{i + 1}</span>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </>
        )}
      </CardBody>

      <PreviewLightbox
        jobId={job.id}
        sheets={previewable}
        index={activeIndex}
        open={open && hasPreviews}
        onClose={() => setOpen(false)}
        onIndexChange={(i) => setActiveId(previewable[i]?.id ?? null)}
        thumbUrls={urls}
      />
    </Card>
  );
}
