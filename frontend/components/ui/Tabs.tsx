"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TabItem<K extends string = string> {
  key: K;
  label: ReactNode;
  count?: number | null;
  icon?: ReactNode;
  disabled?: boolean;
}

export interface TabsProps<K extends string> {
  items: TabItem<K>[];
  value: K;
  onChange: (key: K) => void;
  className?: string;
  size?: "sm" | "md";
}

export function Tabs<K extends string>({ items, value, onChange, className, size = "md" }: TabsProps<K>) {
  return (
    <div
      role="tablist"
      className={cn(
        "scrollbar-thin -mb-px flex gap-1 overflow-x-auto border-b border-line",
        className,
      )}
    >
      {items.map((item) => {
        const active = item.key === value;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={item.disabled}
            onClick={() => onChange(item.key)}
            className={cn(
              "relative inline-flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 font-medium transition-colors",
              size === "md" ? "h-11 text-[13.5px]" : "h-9 text-[13px]",
              active ? "border-brand text-ink" : "border-transparent text-muted hover:border-line-strong hover:text-ink",
              item.disabled && "cursor-not-allowed opacity-50",
              "[&>svg]:size-4",
            )}
          >
            {item.icon}
            {item.label}
            {typeof item.count === "number" ? (
              <span
                className={cn(
                  "tnum inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold",
                  active ? "bg-brand-soft text-brand" : "bg-surface-3 text-muted",
                )}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
