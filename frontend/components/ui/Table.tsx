import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TableWrapProps extends ComponentPropsWithoutRef<"div"> {
  /** Max height of the scroll container; header stays sticky. */
  maxHeight?: number | string;
  /** Drop the rounded border (when the table already sits inside a card). */
  flush?: boolean;
}

/** Scroll container for `.table-dense` tables (sticky header, zebra rows). */
export function TableWrap({ maxHeight, flush, className, style, children, ...rest }: TableWrapProps) {
  return (
    <div
      className={cn(
        "scrollbar-thin relative overflow-auto",
        !flush && "rounded-card border border-line bg-surface",
        className,
      )}
      style={{ maxHeight, ...style }}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Table({ className, ...rest }: ComponentPropsWithoutRef<"table">) {
  return <table className={cn("table-dense", className)} {...rest} />;
}

export interface EmptyRowProps {
  colSpan: number;
  children: ReactNode;
  className?: string;
}

export function EmptyRow({ colSpan, children, className }: EmptyRowProps) {
  return (
    <tr>
      <td colSpan={colSpan} className={cn("!bg-surface py-10 text-center text-[13px] text-muted", className)}>
        {children}
      </td>
    </tr>
  );
}

/** Skeleton rows for a loading table. */
export function SkeletonRows({ rows = 5, cols }: { rows?: number; cols: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r}>
          {Array.from({ length: cols }).map((__, c) => (
            <td key={c}>
              <div className="skeleton h-3.5" style={{ width: `${40 + ((r * 7 + c * 13) % 50)}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
