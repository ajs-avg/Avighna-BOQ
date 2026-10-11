import { Check, X } from "lucide-react";
import { PIPELINE_STEPS, STATUS_META, isProcessing } from "@/lib/constants";
import { formatDate, formatTime } from "@/lib/format";
import type { JobEvent, JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface TimelineProps {
  events: JobEvent[];
  status: JobStatus;
  className?: string;
}

/** Vertical event timeline: real events first, then the pending pipeline steps greyed out. */
export function Timeline({ events, status, className }: TimelineProps) {
  const sorted = [...events].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  const seen = new Set(sorted.map((e) => e.status));
  const pending = isProcessing(status) ? PIPELINE_STEPS.filter((s) => !seen.has(s)) : [];
  const busy = isProcessing(status);

  return (
    <ol className={cn("relative ml-2 space-y-0 border-l border-line pl-5", className)}>
      {sorted.map((e, i) => {
        const isLast = i === sorted.length - 1;
        const failed = e.status === "failed";
        const done = !isLast || !busy;
        return (
          <li key={`${e.at}-${i}`} className="relative pb-5 last:pb-0">
            <span
              className={cn(
                "absolute -left-[26px] top-0.5 flex size-[15px] items-center justify-center rounded-full border-2 bg-surface",
                failed
                  ? "border-danger bg-danger text-white"
                  : e.status === "approved"
                    ? "border-ink bg-ink text-white"
                    : done
                      ? "border-success bg-success text-white"
                      : "border-brand",
              )}
            >
              {failed ? (
                <X className="size-2.5" strokeWidth={3} />
              ) : done ? (
                <Check className="size-2.5" strokeWidth={3} />
              ) : (
                <span className="size-1.5 animate-pulse-dot rounded-full bg-brand" />
              )}
            </span>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
              <p className={cn("text-[13px] font-semibold", failed ? "text-danger" : "text-ink")}>{STATUS_META[e.status]?.label ?? e.status}</p>
              <time dateTime={e.at} title={formatDate(e.at)} className="tnum text-[11.5px] text-muted">
                {formatTime(e.at)}
              </time>
            </div>
            {e.message ? <p className="mt-0.5 text-[12.5px] leading-5 text-muted">{e.message}</p> : null}
          </li>
        );
      })}
      {pending.map((s) => (
        <li key={s} className="relative pb-5 last:pb-0">
          <span className="absolute -left-[26px] top-0.5 size-[15px] rounded-full border-2 border-dashed border-line-strong bg-surface" />
          <p className="text-[13px] font-medium text-muted/70">{STATUS_META[s].label}</p>
        </li>
      ))}
      {sorted.length === 0 && pending.length === 0 ? <li className="text-[13px] text-muted">No events yet.</li> : null}
    </ol>
  );
}
