"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";
import type { ComponentPropsWithoutRef, ReactNode, Ref } from "react";
import { cn } from "@/lib/utils";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "danger-outline" | "link";
export type ButtonSize = "xs" | "sm" | "md" | "lg";

const VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-brand text-white shadow-[0_1px_2px_rgba(200,16,46,0.3)] hover:bg-brand-dark active:bg-brand-dark border border-transparent disabled:bg-brand/50",
  secondary:
    "bg-surface text-ink border border-line shadow-card hover:bg-surface-2 hover:border-line-strong active:bg-surface-3 disabled:text-muted",
  ghost: "bg-transparent text-ink border border-transparent hover:bg-surface-2 active:bg-surface-3 disabled:text-muted",
  danger:
    "bg-danger text-white border border-transparent shadow-[0_1px_2px_rgba(200,16,46,0.3)] hover:bg-brand-dark disabled:bg-danger/50",
  "danger-outline":
    "bg-surface text-danger border border-danger/40 hover:bg-danger-soft hover:border-danger disabled:text-muted disabled:border-line",
  link: "bg-transparent text-brand border border-transparent underline-offset-4 hover:underline px-0 h-auto",
};

const SIZE: Record<ButtonSize, string> = {
  xs: "h-7 px-2.5 text-[12px] gap-1.5 rounded-md",
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
  md: "h-9 px-3.5 text-[13px] gap-2 rounded-lg",
  lg: "h-11 px-5 text-[14px] gap-2 rounded-lg",
};

const ICON_SIZE: Record<ButtonSize, string> = {
  xs: "[&>svg]:size-3.5",
  sm: "[&>svg]:size-4",
  md: "[&>svg]:size-4",
  lg: "[&>svg]:size-[18px]",
};

export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", extra?: string): string {
  return cn(
    "inline-flex shrink-0 items-center justify-center whitespace-nowrap font-medium transition-colors select-none",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
    "disabled:cursor-not-allowed disabled:shadow-none",
    VARIANT[variant],
    variant === "link" ? "" : SIZE[size],
    ICON_SIZE[size],
    extra,
  );
}

export interface ButtonProps extends ComponentPropsWithoutRef<"button"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  block?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  leftIcon,
  rightIcon,
  block = false,
  className,
  children,
  disabled,
  type = "button",
  ref,
  ...rest
}: ButtonProps) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClasses(variant, size, cn(block && "w-full", className))}
      {...rest}
    >
      {loading ? <Loader2 className="animate-spin" aria-hidden /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
}

export interface ButtonLinkProps extends ComponentPropsWithoutRef<typeof Link> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  block?: boolean;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  leftIcon,
  rightIcon,
  block = false,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link className={buttonClasses(variant, size, cn(block && "w-full", className))} {...rest}>
      {leftIcon}
      {children}
      {rightIcon}
    </Link>
  );
}

/** Square icon-only button with an accessible label. */
export interface IconButtonProps extends ComponentPropsWithoutRef<"button"> {
  label: string;
  size?: ButtonSize;
  variant?: ButtonVariant;
  loading?: boolean;
}

const ICON_BTN_SIZE: Record<ButtonSize, string> = {
  xs: "size-7 rounded-md [&>svg]:size-3.5",
  sm: "size-8 rounded-lg [&>svg]:size-4",
  md: "size-9 rounded-lg [&>svg]:size-4",
  lg: "size-11 rounded-lg [&>svg]:size-5",
};

export function IconButton({
  label,
  size = "sm",
  variant = "ghost",
  loading = false,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      disabled={disabled || loading}
      className={cn(
        "inline-flex shrink-0 items-center justify-center transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed",
        VARIANT[variant],
        ICON_BTN_SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="animate-spin" aria-hidden /> : children}
    </button>
  );
}
