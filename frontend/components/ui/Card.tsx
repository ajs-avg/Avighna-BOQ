import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...rest }: ComponentPropsWithoutRef<"div">) {
  return <div className={cn("card", className)} {...rest} />;
}

export interface CardHeaderProps extends Omit<ComponentPropsWithoutRef<"div">, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
}

export function CardHeader({ title, description, actions, icon, className, children, ...rest }: CardHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-line px-5 py-4", className)} {...rest}>
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand [&>svg]:size-4">
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          {title ? <h3 className="text-[15px] font-semibold leading-6 text-ink">{title}</h3> : null}
          {description ? <p className="mt-0.5 text-[13px] text-muted">{description}</p> : null}
          {children}
        </div>
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function CardBody({ className, ...rest }: ComponentPropsWithoutRef<"div">) {
  return <div className={cn("px-5 py-4", className)} {...rest} />;
}

export function CardFooter({ className, ...rest }: ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className={cn("flex items-center justify-end gap-2 rounded-b-card border-t border-line bg-surface-2/60 px-5 py-3", className)}
      {...rest}
    />
  );
}
