import { Armchair, Layers } from "lucide-react";
import { MODULE_META } from "@/lib/constants";
import type { Module } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ModuleIcon({ module, className }: { module: Module; className?: string }) {
  return module === "structural" ? <Layers className={className} aria-hidden /> : <Armchair className={className} aria-hidden />;
}

export function ModuleBadge({ module, className, long = false }: { module: Module; className?: string; long?: boolean }) {
  const meta = MODULE_META[module];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-[11.5px] font-medium leading-none",
        module === "structural" ? "border-ink/15 bg-surface-2 text-ink" : "border-brand/20 bg-brand-soft text-brand",
        className,
      )}
      title={meta.label}
    >
      <ModuleIcon module={module} className="size-3.5" />
      {long ? meta.output : meta.short}
    </span>
  );
}
