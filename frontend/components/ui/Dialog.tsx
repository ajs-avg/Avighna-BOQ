"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { IconButton } from "./Button";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  /** Prevent closing via overlay click / Escape (e.g. while submitting). */
  locked?: boolean;
  icon?: ReactNode;
  tone?: "default" | "danger";
  hideClose?: boolean;
}

const SIZE = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  locked,
  icon,
  tone = "default",
  hideClose,
}: DialogProps) {
  const [mounted, setMounted] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !locked) onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // focus the first focusable element in the panel
    const t = window.setTimeout(() => {
      const el = panelRef.current?.querySelector<HTMLElement>(
        "[data-autofocus], input:not([type=hidden]), select, textarea, button:not([data-dialog-close])",
      );
      el?.focus();
    }, 10);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      window.clearTimeout(t);
    };
  }, [open, locked, onClose]);

  if (!mounted || !open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-end justify-center sm:items-center sm:p-4" role="presentation">
      <div
        className="absolute inset-0 bg-ink/40 backdrop-blur-[2px] animate-fade-in"
        onMouseDown={() => {
          if (!locked) onClose();
        }}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descId : undefined}
        className={cn(
          "relative flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-surface shadow-modal sm:rounded-2xl animate-pop-in",
          SIZE[size],
        )}
      >
        {title || !hideClose ? (
          <div className="flex items-start gap-3 px-6 pt-5 pb-3">
            {icon ? (
              <span
                className={cn(
                  "inline-flex size-10 shrink-0 items-center justify-center rounded-xl [&>svg]:size-5",
                  tone === "danger" ? "bg-danger-soft text-danger" : "bg-brand-soft text-brand",
                )}
              >
                {icon}
              </span>
            ) : null}
            <div className="min-w-0 flex-1">
              {title ? (
                <h2 id={titleId} className="text-[16px] font-semibold leading-6 text-ink">
                  {title}
                </h2>
              ) : null}
              {description ? (
                <p id={descId} className="mt-1 text-[13px] text-muted">
                  {description}
                </p>
              ) : null}
            </div>
            {!hideClose ? (
              <IconButton label="Close" onClick={onClose} disabled={locked} data-dialog-close className="-mr-2 -mt-1">
                <X />
              </IconButton>
            ) : null}
          </div>
        ) : null}
        {children ? <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-6 pb-5">{children}</div> : null}
        {footer ? <div className="flex items-center justify-end gap-2 border-t border-line bg-surface-2/60 px-6 py-3.5">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
