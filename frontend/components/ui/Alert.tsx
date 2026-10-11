import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "@/lib/utils";

export type AlertTone = "info" | "success" | "warning" | "danger";

const TONE: Record<AlertTone, { box: string; icon: ReactNode }> = {
  info: { box: "border-info/25 bg-info-soft text-ink [&_svg]:text-info", icon: <Info /> },
  success: { box: "border-success/25 bg-success-soft text-ink [&_svg]:text-success", icon: <CheckCircle2 /> },
  warning: { box: "border-warning/30 bg-warning-soft text-ink [&_svg]:text-warning", icon: <AlertTriangle /> },
  danger: { box: "border-danger/30 bg-danger-soft text-ink [&_svg]:text-danger", icon: <XCircle /> },
};

export interface AlertProps extends Omit<ComponentPropsWithoutRef<"div">, "title"> {
  tone?: AlertTone;
  title?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
}

export function Alert({ tone = "info", title, actions, icon, className, children, ...rest }: AlertProps) {
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex gap-3 rounded-card border px-4 py-3", TONE[tone].box, className)} {...rest}>
      <span className="mt-0.5 shrink-0 [&>svg]:size-[18px]">{icon ?? TONE[tone].icon}</span>
      <div className="min-w-0 flex-1 text-[13px]">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={cn(title && "mt-0.5", "text-ink/85")}>{children}</div> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
