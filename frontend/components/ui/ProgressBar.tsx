import { cn } from "@/lib/utils";

export interface ProgressBarProps {
  value: number; // 0..100
  tone?: "brand" | "success" | "danger" | "ink";
  size?: "xs" | "sm" | "md";
  indeterminate?: boolean;
  className?: string;
  label?: string;
}

const TONE = {
  brand: "bg-brand",
  success: "bg-success",
  danger: "bg-danger",
  ink: "bg-ink",
};

export function ProgressBar({ value, tone = "brand", size = "sm", indeterminate, className, label }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(pct)}
      aria-label={label}
      className={cn(
        "relative w-full overflow-hidden rounded-full bg-surface-3",
        size === "xs" && "h-1",
        size === "sm" && "h-1.5",
        size === "md" && "h-2.5",
        className,
      )}
    >
      {indeterminate ? (
        <div
          className={cn("absolute inset-y-0 w-1/3 rounded-full", TONE[tone])}
          style={{ animation: "progress-indeterminate 1.4s ease-in-out infinite" }}
        />
      ) : (
        <div
          className={cn("h-full rounded-full transition-[width] duration-500 ease-out", TONE[tone])}
          style={{ width: `${pct}%` }}
        />
      )}
      <style>{`@keyframes progress-indeterminate{0%{left:-35%}100%{left:100%}}`}</style>
    </div>
  );
}
