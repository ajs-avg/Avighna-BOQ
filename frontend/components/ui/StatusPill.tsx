import { Check, X } from "lucide-react";
import { STATUS_META } from "@/lib/constants";
import type { JobStatus } from "@/lib/types";
import { Badge, type BadgeProps } from "./Badge";

export interface StatusPillProps extends Omit<BadgeProps, "tone" | "children"> {
  status: JobStatus;
  progress?: number;
}

export function StatusPill({ status, progress, ...rest }: StatusPillProps) {
  const meta = STATUS_META[status];
  const showPct = meta.busy && typeof progress === "number" && progress > 0 && progress < 100;
  return (
    <Badge
      tone={meta.tone}
      dot={status !== "approved" && status !== "failed"}
      pulse={meta.busy}
      icon={status === "approved" ? <Check strokeWidth={3} /> : status === "failed" ? <X strokeWidth={3} /> : undefined}
      {...rest}
    >
      {meta.label}
      {showPct ? <span className="tnum opacity-80">{Math.round(progress)}%</span> : null}
    </Badge>
  );
}
