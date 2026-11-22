import type { HTMLAttributes, ReactNode } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  interactive?: boolean;
  highlight?: boolean;
}

export function Card({
  children,
  interactive = false,
  highlight = false,
  className = "",
  ...rest
}: CardProps) {
  return (
    <div
      className={[
        "rounded-card border bg-surface p-5 shadow-card",
        highlight ? "border-brand shadow-glow" : "border-line",
        interactive ? "transition hover:border-line-strong" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`space-y-1 ${className}`}>{children}</div>;
}

export function CardTitle({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <h2 className={`text-lg font-bold tracking-tight text-ink ${className}`}>{children}</h2>;
}

export function CardDescription({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`text-sm text-ink-muted ${className}`}>{children}</p>;
}
