"use client";

import { ChevronLeft, ChevronRight, Download, RefreshCw, X, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState, type PointerEvent as ReactPointerEvent, type RefObject } from "react";
import { createPortal } from "react-dom";
import { getPreviewBlobUrl } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { SheetRecord } from "@/lib/types";
import { clamp, cn, slugify } from "@/lib/utils";
import { Badge } from "./ui/Badge";
import { Button, IconButton, buttonClasses } from "./ui/Button";
import { Spinner } from "./ui/Spinner";

export interface PreviewLightboxProps {
  jobId: string;
  /** The navigable set (normally the sheets that have a preview). */
  sheets: SheetRecord[];
  /** Index into `sheets` of the sheet being shown. */
  index: number;
  open: boolean;
  onClose: () => void;
  onIndexChange?: (index: number) => void;
  /** Already-loaded thumb object URLs by sheet id — shown blurred while the full render downloads. */
  thumbUrls?: Record<string, string | undefined>;
}

const MIN_SCALE = 0.1;
const MAX_SCALE = 8;
const FIT_PADDING = 24;
const DOUBLE_CLICK_SCALE = 2;

interface Size {
  w: number;
  h: number;
}

interface LoadedImage extends Size {
  url: string;
}

/** translate(x, y) scale(s) with the origin at the image's top-left corner. */
interface View {
  x: number;
  y: number;
  s: number;
}

/** "Model" on page 1 is the DWG default and says nothing; other layouts / pages are worth naming. */
function sheetLabel(sheet: SheetRecord): string {
  if (sheet.page_no === 1 && sheet.layout === "Model") return "Model space";
  return `${sheet.layout} · p.${sheet.page_no}`;
}

function downloadName(sheet: SheetRecord): string {
  const base = sheet.file_name.replace(/\.[a-z0-9]+$/i, "");
  return `${base}-${slugify(`${sheet.layout} p${sheet.page_no}`) || "sheet"}.png`;
}

function loadImage(url: string): Promise<Size> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
    img.onerror = () => reject(new Error("The preview could not be decoded"));
    img.src = url;
  });
}

/* ------------------------------------------------------------------------- */
/* Zoom & pan                                                                 */
/* ------------------------------------------------------------------------- */

interface ZoomPan {
  view: View;
  fitScale: number | null;
  isFit: boolean;
  dragging: boolean;
  fit: () => void;
  actual: () => void;
  zoomBy: (factor: number) => void;
  toggleFit: (cx?: number, cy?: number) => void;
  onPointerDown: (e: ReactPointerEvent<HTMLDivElement>) => void;
  onPointerMove: (e: ReactPointerEvent<HTMLDivElement>) => void;
  onPointerUp: (e: ReactPointerEvent<HTMLDivElement>) => void;
}

/**
 * Pure CSS-transform zoom & pan for one image inside `viewportRef`.
 * Wheel zooms around the cursor, click-drag pans, two pointers pinch.
 * `onBackdropClick` fires for a plain click (no drag) on the viewport itself (not the image).
 */
function useZoomPan(viewportRef: RefObject<HTMLDivElement | null>, natural: Size | null, onBackdropClick: () => void): ZoomPan {
  const [view, setView] = useState<View>({ x: 0, y: 0, s: 1 });
  const [dragging, setDragging] = useState(false);
  const viewRef = useRef<View>(view);
  const fitRef = useRef<number | null>(null);
  const [fitScale, setFitScale] = useState<number | null>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const drag = useRef<{ startX: number; startY: number; originX: number; originY: number; moved: boolean; onBackdrop: boolean } | null>(null);
  const pinch = useRef<{ dist: number; midX: number; midY: number } | null>(null);

  const commit = useCallback((next: View) => {
    viewRef.current = next;
    setView(next);
  }, []);

  const computeFit = useCallback((): View | null => {
    const vp = viewportRef.current;
    if (!vp || !natural || natural.w <= 0 || natural.h <= 0) return null;
    const { width: vw, height: vh } = vp.getBoundingClientRect();
    // Never upscale past the natural size on Fit: a crisp image beats a blurry full-width one.
    // Fit may go below MIN_SCALE on small screens (a 4500 px sheet on a phone); the floor then follows it.
    const s = clamp(Math.min((vw - FIT_PADDING * 2) / natural.w, (vh - FIT_PADDING * 2) / natural.h, 1), 0.01, MAX_SCALE);
    return { s, x: (vw - natural.w * s) / 2, y: (vh - natural.h * s) / 2 };
  }, [natural, viewportRef]);

  const minScale = useCallback(() => Math.min(MIN_SCALE, fitRef.current ?? MIN_SCALE), []);

  const fit = useCallback(() => {
    const next = computeFit();
    if (!next) return;
    fitRef.current = next.s;
    setFitScale(next.s);
    commit(next);
  }, [commit, computeFit]);

  /** Zoom to `scale`, keeping the image point under (cx, cy) — viewport coordinates — fixed. Defaults to the centre. */
  const zoomTo = useCallback(
    (scale: number, cx?: number, cy?: number) => {
      const vp = viewportRef.current;
      if (!vp) return;
      const r = vp.getBoundingClientRect();
      const px = cx ?? r.width / 2;
      const py = cy ?? r.height / 2;
      const cur = viewRef.current;
      const s = clamp(scale, minScale(), MAX_SCALE);
      const ix = (px - cur.x) / cur.s;
      const iy = (py - cur.y) / cur.s;
      commit({ s, x: px - ix * s, y: py - iy * s });
    },
    [commit, minScale, viewportRef],
  );

  const zoomBy = useCallback((factor: number) => zoomTo(viewRef.current.s * factor), [zoomTo]);
  const actual = useCallback(() => zoomTo(1), [zoomTo]);

  const isFitNow = useCallback(() => fitRef.current !== null && Math.abs(viewRef.current.s - fitRef.current) < 0.001, []);

  const toggleFit = useCallback(
    (cx?: number, cy?: number) => {
      if (isFitNow()) zoomTo(DOUBLE_CLICK_SCALE, cx, cy);
      else fit();
    },
    [fit, isFitNow, zoomTo],
  );

  // A new image (or a new natural size) starts at Fit.
  useEffect(() => {
    fit();
  }, [fit]);

  // Keep a fitted image fitted when the window is resized.
  useEffect(() => {
    const onResize = () => {
      if (isFitNow()) fit();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [fit, isFitNow]);

  // Wheel must be non-passive so trackpad pinch (ctrl+wheel) does not zoom the whole page.
  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = vp.getBoundingClientRect();
      const delta = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * 400 : e.deltaY;
      const factor = Math.exp(-delta * (e.ctrlKey ? 0.01 : 0.0018));
      zoomTo(viewRef.current.s * factor, e.clientX - r.left, e.clientY - r.top);
    };
    vp.addEventListener("wheel", onWheel, { passive: false });
    return () => vp.removeEventListener("wheel", onWheel);
  }, [viewportRef, zoomTo]);

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      const vp = e.currentTarget;
      // Presses on the prev / next arrows (or any control inside the viewport) are clicks, not pans:
      // capturing the pointer here would retarget their `click` to the viewport and swallow it.
      if (e.target instanceof Element && e.target !== vp && e.target.closest("button, a")) return;
      vp.setPointerCapture(e.pointerId);
      pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.current.size === 1) {
        drag.current = {
          startX: e.clientX,
          startY: e.clientY,
          originX: viewRef.current.x,
          originY: viewRef.current.y,
          moved: false,
          onBackdrop: e.target === vp,
        };
        setDragging(true);
      } else if (pointers.current.size === 2) {
        const [a, b] = Array.from(pointers.current.values());
        pinch.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), midX: (a.x + b.x) / 2, midY: (a.y + b.y) / 2 };
        drag.current = null;
      }
    },
    [],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (!pointers.current.has(e.pointerId)) return;
      pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.current.size >= 2 && pinch.current) {
        const [a, b] = Array.from(pointers.current.values());
        const dist = Math.hypot(a.x - b.x, a.y - b.y);
        const midX = (a.x + b.x) / 2;
        const midY = (a.y + b.y) / 2;
        const r = e.currentTarget.getBoundingClientRect();
        const factor = pinch.current.dist > 0 ? dist / pinch.current.dist : 1;
        const cur = viewRef.current;
        // Pan by the midpoint's movement, then zoom around the new midpoint.
        viewRef.current = { ...cur, x: cur.x + (midX - pinch.current.midX), y: cur.y + (midY - pinch.current.midY) };
        zoomTo(viewRef.current.s * factor, midX - r.left, midY - r.top);
        pinch.current = { dist, midX, midY };
        return;
      }
      const d = drag.current;
      if (!d) return;
      const dx = e.clientX - d.startX;
      const dy = e.clientY - d.startY;
      if (!d.moved && Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
      if (d.moved) commit({ ...viewRef.current, x: d.originX + dx, y: d.originY + dy });
    },
    [commit, zoomTo],
  );

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (!pointers.current.has(e.pointerId)) return;
      pointers.current.delete(e.pointerId);
      if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
      if (pointers.current.size < 2) pinch.current = null;
      if (pointers.current.size === 0) {
        const wasPlainClick = drag.current !== null && !drag.current.moved && drag.current.onBackdrop;
        drag.current = null;
        setDragging(false);
        if (wasPlainClick) onBackdropClick();
      }
    },
    [onBackdropClick],
  );

  return {
    view,
    fitScale,
    isFit: fitScale !== null && Math.abs(view.s - fitScale) < 0.001,
    dragging,
    fit,
    actual,
    zoomBy,
    toggleFit,
    onPointerDown,
    onPointerMove,
    onPointerUp,
  };
}

/* ------------------------------------------------------------------------- */
/* Lightbox                                                                   */
/* ------------------------------------------------------------------------- */

export function PreviewLightbox(props: PreviewLightboxProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted || !props.open || props.sheets.length === 0) return null;
  return createPortal(<LightboxPanel {...props} />, document.body);
}

function LightboxPanel({ jobId, sheets, index, onClose, onIndexChange, thumbUrls }: PreviewLightboxProps) {
  const safeIndex = clamp(index, 0, sheets.length - 1);
  const sheet = sheets[safeIndex];
  const thumbUrl = thumbUrls?.[sheet.id] ?? null;
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [full, setFull] = useState<LoadedImage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const goTo = useCallback(
    (next: number) => {
      if (sheets.length < 2) return;
      onIndexChange?.(((next % sheets.length) + sheets.length) % sheets.length);
    },
    [onIndexChange, sheets.length],
  );

  // Load the full render for the current sheet; revoke it when the sheet changes or the lightbox closes.
  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setFull(null);
    setError(null);
    getPreviewBlobUrl(jobId, sheet.id, "full")
      .then(async (url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        const size = await loadImage(url);
        if (!cancelled) setFull({ url, ...size });
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error && err.message ? err.message : "Preview unavailable");
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [jobId, sheet.id, attempt]);

  const zoom = useZoomPan(viewportRef, full, onClose);

  // Scroll lock, keyboard, and focus management (restore focus to the opener on close).
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(() => panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus(), 10);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.clearTimeout(t);
      opener?.focus();
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target instanceof HTMLElement ? e.target : null;
      const typing = target ? target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable : false;
      switch (e.key) {
        case "Escape":
          e.preventDefault();
          onClose();
          return;
        case "ArrowLeft":
          if (!typing) goTo(safeIndex - 1);
          return;
        case "ArrowRight":
          if (!typing) goTo(safeIndex + 1);
          return;
        case "+":
        case "=":
          if (!typing) zoom.zoomBy(1.25);
          return;
        case "-":
        case "_":
          if (!typing) zoom.zoomBy(0.8);
          return;
        case "0":
          if (!typing) zoom.fit();
          return;
        case "1":
          if (!typing) zoom.actual();
          return;
        case "Tab": {
          // Keep Tab inside the panel.
          const panel = panelRef.current;
          if (!panel) return;
          const focusable = Array.from(panel.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), [tabindex]:not([tabindex='-1'])")).filter(
            (el) => el.offsetParent !== null,
          );
          if (focusable.length === 0) return;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          const active = document.activeElement;
          if (e.shiftKey && (active === first || !panel.contains(active))) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && (active === last || !panel.contains(active))) {
            e.preventDefault();
            first.focus();
          }
          return;
        }
        default:
          return;
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [goTo, onClose, safeIndex, zoom]);

  const loading = !full && !error;
  const highRes = !!sheet.preview_full_path;
  const pct = Math.round(zoom.view.s * 100);

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-[95] flex flex-col bg-ink/95 animate-fade-in"
    >
      {/* Top bar */}
      <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-white/10 bg-surface px-4 py-2 shadow-pop">
        {/* Title block: one line on wide screens; on narrow ones the name truncates on its own line and the meta wraps beneath. */}
        <div className="min-w-0 flex-1 basis-[260px] sm:flex sm:items-center sm:gap-x-2">
          <h2 id={titleId} className="min-w-0 shrink truncate text-[14px] font-semibold text-ink" title={sheet.file_name}>
            {sheet.file_name}
          </h2>
          <div className="flex shrink-0 flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] text-muted">
            <span>
              <span className="hidden sm:inline">· </span>
              {sheetLabel(sheet)} · {humanize(sheet.classification.sheet_type)}
            </span>
            {highRes ? (
              <Badge tone="success" size="xs">
                High resolution
              </Badge>
            ) : (
              <Badge tone="neutral" size="xs" title="Reprocess the job for high resolution">
                Standard resolution<span className="hidden font-normal md:inline"> (reprocess the job for high resolution)</span>
              </Badge>
            )}
            {sheets.length > 1 ? (
              <span className="tnum text-[12px]">
                {safeIndex + 1} / {sheets.length}
              </span>
            ) : null}
          </div>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <div className="flex items-center rounded-lg border border-line bg-surface-2/60">
            <IconButton label="Zoom out" onClick={() => zoom.zoomBy(0.8)} disabled={!full} className="rounded-r-none">
              <ZoomOut />
            </IconButton>
            <button
              type="button"
              className="tnum h-8 min-w-[56px] border-x border-line px-2 text-[12.5px] font-medium text-ink hover:bg-surface-2 disabled:text-muted"
              onClick={zoom.actual}
              disabled={!full}
              title="Zoom to 100%"
            >
              {full ? `${pct}%` : "—"}
            </button>
            <IconButton label="Zoom in" onClick={() => zoom.zoomBy(1.25)} disabled={!full} className="rounded-l-none">
              <ZoomIn />
            </IconButton>
          </div>
          <Button size="sm" variant={zoom.isFit ? "primary" : "secondary"} onClick={zoom.fit} disabled={!full} title="Fit the whole sheet in the window (0)">
            Fit
          </Button>
          <Button size="sm" variant={full && Math.abs(zoom.view.s - 1) < 0.001 ? "primary" : "secondary"} onClick={zoom.actual} disabled={!full} title="Natural pixel size (1)">
            100%
          </Button>
          {full ? (
            <a href={full.url} download={downloadName(sheet)} className={buttonClasses("secondary", "sm")} title="Download this render as PNG">
              <Download />
              <span className="hidden sm:inline">Download</span>
            </a>
          ) : (
            <Button size="sm" variant="secondary" leftIcon={<Download />} disabled>
              <span className="hidden sm:inline">Download</span>
            </Button>
          )}
          <IconButton label="Close" onClick={onClose} data-autofocus className="ml-1">
            <X />
          </IconButton>
        </div>
      </div>

      {/* Viewport */}
      <div
        ref={viewportRef}
        className={cn("relative min-h-0 flex-1 touch-none overflow-hidden select-none", full ? (zoom.dragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default")}
        onPointerDown={zoom.onPointerDown}
        onPointerMove={zoom.onPointerMove}
        onPointerUp={zoom.onPointerUp}
        onPointerCancel={zoom.onPointerUp}
        onDoubleClick={(e) => {
          if (!full) return;
          const r = e.currentTarget.getBoundingClientRect();
          zoom.toggleFit(e.clientX - r.left, e.clientY - r.top);
        }}
      >
        {full ? (
          // Blob URLs cannot go through next/image's optimizer.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={full.url}
            alt={`${sheet.file_name} — ${sheetLabel(sheet)}`}
            width={full.w}
            height={full.h}
            draggable={false}
            onDragStart={(e) => e.preventDefault()}
            className="absolute left-0 top-0 max-w-none bg-white shadow-modal"
            style={{
              width: full.w,
              height: full.h,
              transform: `translate(${zoom.view.x}px, ${zoom.view.y}px) scale(${zoom.view.s})`,
              transformOrigin: "0 0",
              imageRendering: "auto",
              willChange: "transform",
            }}
          />
        ) : null}

        {loading && thumbUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbUrl}
            alt=""
            aria-hidden
            draggable={false}
            className="pointer-events-none absolute inset-0 m-auto max-h-[calc(100%-48px)] max-w-[calc(100%-48px)] object-contain opacity-60 blur-[2px]"
          />
        ) : null}

        {loading ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center" role="status" aria-live="polite">
            <span className="inline-flex items-center gap-2 rounded-full bg-ink/80 px-4 py-2 text-[13px] font-medium text-white shadow-pop">
              <Spinner size={16} className="text-white" />
              Loading {highRes ? "high-resolution" : ""} preview…
            </span>
          </div>
        ) : null}

        {error ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-white/80">
            <p className="text-[14px] font-medium text-white">Preview unavailable</p>
            <p className="max-w-sm text-center text-[12.5px]">{error}</p>
            <Button size="sm" variant="secondary" leftIcon={<RefreshCw />} onClick={() => setAttempt((n) => n + 1)}>
              Retry
            </Button>
          </div>
        ) : null}

        {sheets.length > 1 ? (
          <>
            <IconButton
              label="Previous sheet"
              size="lg"
              onClick={() => goTo(safeIndex - 1)}
              className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full bg-white/90 text-ink shadow-pop hover:bg-white"
            >
              <ChevronLeft />
            </IconButton>
            <IconButton
              label="Next sheet"
              size="lg"
              onClick={() => goTo(safeIndex + 1)}
              className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full bg-white/90 text-ink shadow-pop hover:bg-white"
            >
              <ChevronRight />
            </IconButton>
          </>
        ) : null}

        {full ? (
          <p className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-ink/70 px-3 py-1 text-[11.5px] text-white/85">
            {full.w} × {full.h} px · scroll to zoom · drag to pan · double-click for {zoom.isFit ? `${DOUBLE_CLICK_SCALE * 100}%` : "Fit"}
          </p>
        ) : null}
      </div>
    </div>
  );
}
