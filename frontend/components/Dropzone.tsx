"use client";

import { File, FileBox, FileImage, FileText, Upload, X } from "lucide-react";
import { useCallback, useId, useRef, useState, type DragEvent } from "react";
import { ACCEPTED_EXTENSIONS, ACCEPT_ATTR } from "@/lib/constants";
import { detectFormat, formatBytes } from "@/lib/format";
import type { SourceFormat } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface DropzoneProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
  disabled?: boolean;
  maxFiles?: number;
  className?: string;
}

const FORMAT_META: Record<SourceFormat, { label: string; icon: typeof File; tone: string }> = {
  dwg: { label: "DWG", icon: FileBox, tone: "bg-ink text-white" },
  dxf: { label: "DXF", icon: FileBox, tone: "bg-ink/80 text-white" },
  pdf: { label: "PDF", icon: FileText, tone: "bg-brand text-white" },
  image: { label: "IMG", icon: FileImage, tone: "bg-info text-white" },
  unknown: { label: "?", icon: File, tone: "bg-surface-3 text-muted" },
};

function isAccepted(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function Dropzone({ files, onFilesChange, disabled, maxFiles = 40, className }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const id = useId();

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      const list = Array.from(incoming);
      const bad = list.filter((f) => !isAccepted(f)).map((f) => f.name);
      const good = list.filter(isAccepted);
      setRejected(bad);
      if (!good.length) return;
      const existing = new Set(files.map((f) => `${f.name}:${f.size}`));
      const merged = [...files, ...good.filter((f) => !existing.has(`${f.name}:${f.size}`))].slice(0, maxFiles);
      onFilesChange(merged);
    },
    [files, maxFiles, onFilesChange],
  );

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  };

  const remove = (index: number) => onFilesChange(files.filter((_, i) => i !== index));

  const total = files.reduce((s, f) => s + f.size, 0);

  return (
    <div className={cn("space-y-3", className)}>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled || undefined}
        aria-describedby={`${id}-hint`}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "group relative flex cursor-pointer flex-col items-center justify-center rounded-card border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging ? "border-brand bg-brand-tint" : "border-line-strong bg-surface-2/50 hover:border-brand/60 hover:bg-brand-tint/60",
          disabled && "cursor-not-allowed opacity-60 hover:border-line-strong hover:bg-surface-2/50",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT_ATTR}
          className="sr-only"
          disabled={disabled}
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <span
          className={cn(
            "mb-3 inline-flex size-12 items-center justify-center rounded-2xl bg-surface shadow-card transition-transform group-hover:-translate-y-0.5",
            dragging ? "text-brand" : "text-brand",
          )}
        >
          <Upload className="size-5" />
        </span>
        <p className="text-[14px] font-semibold text-ink">
          Drop drawings here, or <span className="text-brand underline-offset-2 group-hover:underline">browse</span>
        </p>
        <p id={`${id}-hint`} className="mt-1 text-[12.5px] text-muted">
          DWG, DXF, PDF, PNG, JPG, TIFF · multiple files allowed
        </p>
      </div>

      {rejected.length ? (
        <p className="text-[12px] text-danger">
          Skipped unsupported file{rejected.length > 1 ? "s" : ""}: {rejected.join(", ")}
        </p>
      ) : null}

      {files.length ? (
        <div className="rounded-card border border-line bg-surface">
          <ul className="divide-y divide-line">
            {files.map((f, i) => {
              const fmt = detectFormat(f.name);
              const meta = FORMAT_META[fmt];
              const Icon = meta.icon;
              return (
                <li key={`${f.name}-${f.size}-${i}`} className="flex items-center gap-3 px-3 py-2">
                  <span className={cn("inline-flex size-8 shrink-0 items-center justify-center rounded-lg", meta.tone)}>
                    <Icon className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-ink" title={f.name}>
                      {f.name}
                    </p>
                    <p className="text-[11.5px] text-muted">
                      <span className="font-semibold">{meta.label}</span>
                      <span className="mx-1.5 text-line-strong">·</span>
                      {formatBytes(f.size)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => remove(i)}
                    disabled={disabled}
                    aria-label={`Remove ${f.name}`}
                    className="inline-flex size-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-danger-soft hover:text-danger disabled:opacity-50"
                  >
                    <X className="size-4" />
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="flex items-center justify-between border-t border-line bg-surface-2/60 px-3 py-2 text-[12px] text-muted">
            <span>
              {files.length} file{files.length === 1 ? "" : "s"} · {formatBytes(total)}
            </span>
            <button type="button" onClick={() => onFilesChange([])} disabled={disabled} className="font-medium text-brand hover:underline disabled:opacity-50">
              Clear all
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
