import type { ComponentPropsWithoutRef, ReactNode } from "react";
import type { Tone } from "@/lib/constants";
import { cn } from "@/lib/utils";

const TONE: Record<Tone, string> = {
  neutral: "bg-surface-3 text-muted border-line",
  info: "bg-info-soft text-info border-info/20",
  success: "bg-success-soft text-success border-success/20",
  warning: "bg-warning-soft text-warning border-warning/25",
  danger: "bg-danger-soft text-danger border-danger/20",
  brand: "bg-brand-soft text-brand border-brand/20",
  ink: "bg-ink text-white border-ink",
};

export interface BadgeProps extends ComponentPropsWithoutRef<"span"> {
  tone?: Tone;
  size?: "xs" | "sm" | "md";
  dot?: boolean;
  pulse?: boolean;
  icon?: ReactNode;
}

export function Badge({ tone = "neutral", size = "sm", dot, pulse, icon, className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border font-medium leading-none",
        size === "xs" && "h-5 px-1.5 text-[10.5px]",
        size === "sm" && "h-6 px-2 text-[11.5px]",
        size === "md" && "h-7 px-2.5 text-[12.5px]",
        TONE[tone],
        className,
      )}
      {...rest}
    >
      {dot ? (
        <span className={cn("size-1.5 rounded-full bg-current", pulse && "animate-pulse-dot")} aria-hidden />
      ) : null}
      {icon ? <span className="[&>svg]:size-3">{icon}</span> : null}
      {children}
    </span>
  );
}

/** Small mono chip, e.g. a finish code or a file extension. */
export function Chip({ className, ...rest }: ComponentPropsWithoutRef<"span">) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] leading-4 text-ink",
        className,
      )}
      {...rest}
    />
  );
}
