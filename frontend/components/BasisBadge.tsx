import { BASIS_META } from "@/lib/constants";
import type { QtyBasis } from "@/lib/types";
import { Badge, type BadgeProps } from "./ui/Badge";

export function BasisBadge({ basis, ...rest }: { basis: QtyBasis } & Omit<BadgeProps, "tone" | "children">) {
  const meta = BASIS_META[basis] ?? BASIS_META.manual;
  return (
    <Badge tone={meta.tone} size="xs" title={meta.hint} {...rest}>
      {meta.label}
    </Badge>
  );
}
