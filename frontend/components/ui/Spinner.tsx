import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function Spinner({ className, size = 16 }: { className?: string; size?: number }) {
  return <Loader2 className={cn("animate-spin text-muted", className)} style={{ width: size, height: size }} aria-hidden />;
}

export function PageSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-muted" role="status">
      <Spinner size={24} className="text-brand" />
      <span className="text-[13px]">{label}</span>
    </div>
  );
}
