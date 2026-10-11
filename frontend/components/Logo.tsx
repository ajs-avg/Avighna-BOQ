import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

export interface LogoProps {
  /** Wordmark height in px (the SVG is 240.05 × 39.76). */
  height?: number;
  href?: string | null;
  className?: string;
  /** Show only the square mark. */
  markOnly?: boolean;
  priority?: boolean;
}

const RATIO = 240.05 / 39.76;

export function Logo({ height = 28, href = "/", className, markOnly = false, priority = false }: LogoProps) {
  const img = markOnly ? (
    <Image
      src="/brand/avighna-mark.png"
      alt="Avighna"
      width={height}
      height={height}
      priority={priority}
      className="rounded-md"
      style={{ width: height, height }}
    />
  ) : (
    // The wordmark is an SVG: served as-is, no optimizer pass needed.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/brand/avighna-logo.svg"
      alt="Avighna Group"
      width={Math.round(RATIO * height)}
      height={height}
      fetchPriority={priority ? "high" : undefined}
      decoding="async"
      style={{ height, width: "auto" }}
    />
  );
  if (!href) return <span className={cn("inline-flex items-center", className)}>{img}</span>;
  return (
    <Link href={href} className={cn("inline-flex items-center", className)} aria-label="Avighna BOQ home">
      {img}
    </Link>
  );
}

/** "Avighna BOQ" product badge rendered next to the wordmark. */
export function ProductTag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-md bg-ink px-1.5 text-[10.5px] font-bold uppercase tracking-[0.08em] text-white",
        className,
      )}
    >
      BOQ
    </span>
  );
}
