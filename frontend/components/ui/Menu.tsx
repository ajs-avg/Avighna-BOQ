"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface MenuItem {
  key: string;
  label: ReactNode;
  icon?: ReactNode;
  onSelect?: () => void;
  danger?: boolean;
  disabled?: boolean;
  /** Render a separator above this item. */
  separator?: boolean;
}

export interface MenuProps {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  items: MenuItem[];
  align?: "left" | "right";
  header?: ReactNode;
  className?: string;
  width?: number;
}

/** Minimal dropdown menu: closes on outside click, Escape, or item selection. */
export function Menu({ trigger, items, align = "right", header, className, width = 224 }: MenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={cn("relative inline-block", className)}>
      {trigger({ open, toggle: () => setOpen((v) => !v) })}
      {open ? (
        <div
          role="menu"
          style={{ width }}
          className={cn(
            "absolute z-[60] mt-1.5 overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-pop animate-pop-in",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {header ? <div className="border-b border-line px-3 py-2.5">{header}</div> : null}
          {items.map((item) => (
            <div key={item.key}>
              {item.separator ? <div className="my-1 border-t border-line" /> : null}
              <button
                type="button"
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  setOpen(false);
                  item.onSelect?.();
                }}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2 text-left text-[13px] transition-colors [&>svg]:size-4",
                  item.danger ? "text-danger hover:bg-danger-soft" : "text-ink hover:bg-surface-2",
                  item.disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
                )}
              >
                {item.icon ? <span className="text-muted [&>svg]:size-4">{item.icon}</span> : null}
                {item.label}
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
