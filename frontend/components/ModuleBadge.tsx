import { Armchair, Layers, Ruler } from "lucide-react";
import { MODULE_META } from "@/lib/constants";
import type { Module } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ModuleIcon({ module, className }: { module: Module; className?: string }) {
  if (module === "structural") return <Layers className={className} aria-hidden />;
  if (module === "fitout") return <Armchair className={className} aria-hidden />;
  return <Ruler className={className} aria-hidden />;
}

const STYLE: Record<Module, string> = {
  measurement: "border-brand/20 bg-brand-soft text-brand",
  structural: "border-ink/15 bg-surface-2 text-ink",
  fitout: "border-line bg-surface-2 text-muted",
};

/**
 * Module chip. Measurement is the only module offered for new jobs, so lists only
 * show this badge for the legacy structural / fit-out jobs (callers decide).
 */
export function ModuleBadge({ module, className, long = false }: { module: Module; className?: string; long?: boolean }) {
  const meta = MODULE_META[module];
  return (
    <span
      className={cn("inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-[11.5px] font-medium leading-none", STYLE[module], className)}
      title={meta.label}
    >
      <ModuleIcon module={module} className="size-3.5" />
      {long ? meta.output : meta.short}
    </span>
  );
}
