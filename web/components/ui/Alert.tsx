import type { ReactNode } from "react";

export type AlertTone = "info" | "success" | "warning" | "error";

const TONE_CLASSES: Record<AlertTone, string> = {
  info: "border-line-strong bg-surface text-ink-muted",
  success: "border-emerald-500/30 bg-emerald-950/25 text-emerald-200",
  warning: "border-amber-500/30 bg-amber-950/25 text-amber-200",
  error: "border-red-500/30 bg-red-950/25 text-red-200",
};

export function Alert({
  tone = "info",
  title,
  children,
  action,
  className = "",
}: {
  tone?: AlertTone;
  title?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === "error" || tone === "warning" ? "alert" : "status"}
      className={`rounded-card border p-4 text-sm ${TONE_CLASSES[tone]} ${className}`}
    >
      <div className="space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        <div className="opacity-95">{children}</div>
      </div>
      {action && <div className="mt-3 flex flex-wrap gap-2">{action}</div>}
    </div>
  );
}
