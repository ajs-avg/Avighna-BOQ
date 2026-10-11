"use client";

import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type ToastTone = "success" | "error" | "info" | "warning";

export interface ToastOptions {
  title: ReactNode;
  description?: ReactNode;
  tone?: ToastTone;
  durationMs?: number;
}

interface ToastItem extends Required<Pick<ToastOptions, "tone" | "durationMs">> {
  id: number;
  title: ReactNode;
  description?: ReactNode;
}

export interface ToastApi {
  toast: (options: ToastOptions) => number;
  success: (title: ReactNode, description?: ReactNode) => number;
  error: (title: ReactNode, description?: ReactNode) => number;
  info: (title: ReactNode, description?: ReactNode) => number;
  warning: (title: ReactNode, description?: ReactNode) => number;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const ICON: Record<ToastTone, ReactNode> = {
  success: <CheckCircle2 className="text-success" />,
  error: <XCircle className="text-danger" />,
  info: <Info className="text-info" />,
  warning: <AlertTriangle className="text-warning" />,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (options: ToastOptions) => {
      counter.current += 1;
      const id = counter.current;
      const item: ToastItem = {
        id,
        title: options.title,
        description: options.description,
        tone: options.tone ?? "info",
        durationMs: options.durationMs ?? (options.tone === "error" ? 7000 : 4000),
      };
      setItems((prev) => [...prev.slice(-4), item]);
      return id;
    },
    [],
  );

  const api = useMemo<ToastApi>(
    () => ({
      toast,
      dismiss,
      success: (title, description) => toast({ title, description, tone: "success" }),
      error: (title, description) => toast({ title, description, tone: "error" }),
      info: (title, description) => toast({ title, description, tone: "info" }),
      warning: (title, description) => toast({ title, description, tone: "warning" }),
    }),
    [toast, dismiss],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[90] flex flex-col items-center gap-2 p-4 sm:items-end"
        aria-live="polite"
        aria-relevant="additions"
      >
        {items.map((t) => (
          <ToastCard key={t.id} item={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  useEffect(() => {
    const t = window.setTimeout(onDismiss, item.durationMs);
    return () => window.clearTimeout(t);
  }, [item.durationMs, onDismiss]);

  return (
    <div
      role={item.tone === "error" ? "alert" : "status"}
      className={cn(
        "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-line bg-surface p-3.5 pr-2 shadow-pop animate-slide-in-right",
      )}
    >
      <span className="mt-0.5 shrink-0 [&>svg]:size-[18px]">{ICON[item.tone]}</span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-ink">{item.title}</p>
        {item.description ? <p className="mt-0.5 break-words text-[12.5px] text-muted">{item.description}</p> : null}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="-mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-ink"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
