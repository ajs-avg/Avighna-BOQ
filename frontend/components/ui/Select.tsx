"use client";

import { ChevronDown } from "lucide-react";
import type { ComponentPropsWithoutRef, Ref } from "react";
import { cn } from "@/lib/utils";

export interface SelectOption<T extends string = string> {
  value: T;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<ComponentPropsWithoutRef<"select">, "size"> {
  ref?: Ref<HTMLSelectElement>;
  options?: SelectOption[];
  placeholder?: string;
  invalid?: boolean;
  size?: "sm" | "md";
}

export function Select({ className, options, placeholder, invalid, children, size = "md", ref, ...rest }: SelectProps) {
  return (
    <div className="relative">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn(
          "field appearance-none pr-9",
          size === "sm" && "h-8 text-[12.5px]",
          rest.value === "" && placeholder && "text-muted",
          className,
        )}
        {...rest}
      >
        {placeholder ? (
          <option value="" disabled={rest.required}>
            {placeholder}
          </option>
        ) : null}
        {options
          ? options.map((o) => (
              <option key={o.value} value={o.value} disabled={o.disabled}>
                {o.label}
              </option>
            ))
          : children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
    </div>
  );
}
