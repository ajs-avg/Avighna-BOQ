"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  className?: string;
  size?: "sm" | "md";
}

export function Switch({ checked, onCheckedChange, label, description, disabled, className, size = "md" }: SwitchProps) {
  const track = size === "sm" ? "h-5 w-9" : "h-6 w-11";
  const knob = size === "sm" ? "size-4" : "size-5";
  const shift = size === "sm" ? "translate-x-4" : "translate-x-5";
  return (
    <label className={cn("inline-flex cursor-pointer select-none items-start gap-3", disabled && "cursor-not-allowed opacity-60", className)}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          "relative inline-flex shrink-0 items-center rounded-full border border-transparent transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
          track,
          checked ? "bg-brand" : "bg-line-strong",
        )}
      >
        <span
          className={cn(
            "inline-block translate-x-0.5 rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,0.25)] transition-transform",
            knob,
            checked && shift,
          )}
        />
      </button>
      {label || description ? (
        <span className="flex flex-col">
          {label ? <span className="text-[13px] font-medium text-ink">{label}</span> : null}
          {description ? <span className="text-[12px] text-muted">{description}</span> : null}
        </span>
      ) : null}
    </label>
  );
}

export interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
  className?: string;
}

export function Checkbox({ checked, onCheckedChange, label, disabled, className }: CheckboxProps) {
  return (
    <label className={cn("inline-flex cursor-pointer select-none items-center gap-2 text-[13px] text-ink", disabled && "cursor-not-allowed opacity-60", className)}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onCheckedChange(e.target.checked)}
        className="size-4 cursor-pointer rounded border-line-strong accent-brand"
      />
      {label}
    </label>
  );
}
