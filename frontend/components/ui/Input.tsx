"use client";

import { useId, type ComponentPropsWithoutRef, type ReactNode, type Ref } from "react";
import { cn } from "@/lib/utils";

export interface FieldProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  className?: string;
  children: ReactNode | ((id: string, describedBy: string | undefined) => ReactNode);
  /** Put label and control on one row (used in dense editors). */
  inline?: boolean;
  id?: string;
}

/** Label + control + hint / error wrapper. */
export function Field({ label, hint, error, required, className, children, inline, id: idProp }: FieldProps) {
  const autoId = useId();
  const id = idProp ?? autoId;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;
  const control = typeof children === "function" ? children(id, describedBy) : children;
  return (
    <div className={cn(inline ? "grid grid-cols-[minmax(0,160px)_1fr] items-center gap-3" : "flex flex-col gap-1.5", className)}>
      {label ? (
        <label htmlFor={id} className="text-[12.5px] font-medium text-ink">
          {label}
          {required ? <span className="ml-0.5 text-brand">*</span> : null}
        </label>
      ) : null}
      <div className="min-w-0">
        {control}
        {error ? (
          <p id={errorId} className="mt-1 text-[12px] text-danger">
            {error}
          </p>
        ) : hint ? (
          <p id={hintId} className="mt-1 text-[12px] text-muted">
            {hint}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export interface InputProps extends ComponentPropsWithoutRef<"input"> {
  ref?: Ref<HTMLInputElement>;
  invalid?: boolean;
  leftIcon?: ReactNode;
  rightSlot?: ReactNode;
  /** Suffix text rendered inside the control (e.g. "mm"). */
  suffix?: ReactNode;
}

export function Input({ className, invalid, leftIcon, rightSlot, suffix, ref, ...rest }: InputProps) {
  if (!leftIcon && !rightSlot && !suffix) {
    return <input ref={ref} aria-invalid={invalid || undefined} className={cn("field", className)} {...rest} />;
  }
  return (
    <div className="relative">
      {leftIcon ? (
        <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted [&>svg]:size-4">
          {leftIcon}
        </span>
      ) : null}
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn("field", leftIcon && "pl-9", (rightSlot || suffix) && "pr-10", className)}
        {...rest}
      />
      {suffix ? (
        <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-[12px] text-muted">
          {suffix}
        </span>
      ) : null}
      {rightSlot ? <span className="absolute inset-y-0 right-0 flex items-center pr-1.5">{rightSlot}</span> : null}
    </div>
  );
}

export interface NumberInputProps extends Omit<InputProps, "value" | "onChange" | "type"> {
  value: number | "";
  onValueChange: (value: number | "") => void;
}

/** Numeric input that keeps "" while the user is typing and emits numbers otherwise. */
export function NumberInput({ value, onValueChange, className, ...rest }: NumberInputProps) {
  return (
    <Input
      type="number"
      inputMode="decimal"
      value={value}
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === "") {
          onValueChange("");
          return;
        }
        const n = Number(raw);
        onValueChange(Number.isFinite(n) ? n : "");
      }}
      className={cn("tnum", className)}
      {...rest}
    />
  );
}

export interface TextareaProps extends ComponentPropsWithoutRef<"textarea"> {
  invalid?: boolean;
  ref?: Ref<HTMLTextAreaElement>;
}

export function Textarea({ className, invalid, ref, ...rest }: TextareaProps) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn("field h-auto min-h-[84px] resize-y py-2 leading-5", className)}
      {...rest}
    />
  );
}
