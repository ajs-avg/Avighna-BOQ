import { Badge, type BadgeProps } from "./ui/Badge";

export interface ConfidenceBadgeProps extends Omit<BadgeProps, "tone" | "children"> {
  value: number; // 0..1
  showPct?: boolean;
}

export function confidenceMeta(value: number): { label: string; tone: "success" | "warning" | "danger" } {
  if (value >= 0.85) return { label: "High", tone: "success" };
  if (value >= 0.6) return { label: "Check", tone: "warning" };
  return { label: "Low", tone: "danger" };
}

export function ConfidenceBadge({ value, showPct = true, ...rest }: ConfidenceBadgeProps) {
  const v = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
  const meta = confidenceMeta(v);
  return (
    <Badge tone={meta.tone} dot title={`Confidence ${(v * 100).toFixed(0)}%`} {...rest}>
      {meta.label}
      {showPct ? <span className="tnum opacity-75">{Math.round(v * 100)}%</span> : null}
    </Badge>
  );
}
