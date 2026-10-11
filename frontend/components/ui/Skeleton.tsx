import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...rest }: ComponentPropsWithoutRef<"div">) {
  return <div className={cn("skeleton", className)} aria-hidden {...rest} />;
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)} aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton h-3.5" style={{ width: `${i === lines - 1 ? 55 : 85 + ((i * 11) % 15)}%` }} />
      ))}
    </div>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("card p-5", className)} aria-hidden>
      <div className="skeleton mb-3 h-3 w-24" />
      <div className="skeleton h-8 w-32" />
    </div>
  );
}
