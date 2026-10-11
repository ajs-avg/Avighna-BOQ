import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface StatTileProps {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: "default" | "brand";
  loading?: boolean;
  className?: string;
}

export function StatTile({ label, value, unit, hint, icon, tone = "default", loading, className }: StatTileProps) {
  return (
    <div
      className={cn(
        "card relative overflow-hidden p-5",
        tone === "brand" && "border-brand/30 bg-gradient-to-br from-brand to-brand-dark text-white shadow-[0_8px_24px_-12px_rgba(237,28,36,0.6)]",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className={cn("text-[12px] font-medium uppercase tracking-[0.06em]", tone === "brand" ? "text-white/80" : "text-muted")}>
          {label}
        </p>
        {icon ? (
          <span
            className={cn(
              "inline-flex size-8 shrink-0 items-center justify-center rounded-lg [&>svg]:size-4",
              tone === "brand" ? "bg-white/15 text-white" : "bg-brand-soft text-brand",
            )}
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div className="mt-3 flex items-baseline gap-1.5">
        {loading ? (
          <div className={cn("skeleton h-8 w-24", tone === "brand" && "bg-white/20")} />
        ) : (
          <>
            <span className="tnum text-[28px] font-semibold leading-none tracking-tight">{value}</span>
            {unit ? <span className={cn("text-[13px] font-medium", tone === "brand" ? "text-white/80" : "text-muted")}>{unit}</span> : null}
          </>
        )}
      </div>
      {hint ? <p className={cn("mt-2 text-[12px]", tone === "brand" ? "text-white/75" : "text-muted")}>{hint}</p> : null}
    </div>
  );
}
