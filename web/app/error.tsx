"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Badge, Button, buttonClasses } from "@/components/ui";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Snipzo UI error boundary caught:", error.digest || error.message);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-16 text-center">
      <Badge tone="danger">Something went wrong</Badge>
      <h1 className="mt-4 text-3xl font-black tracking-tight text-ink">
        We hit an unexpected snag
      </h1>
      <p className="mt-2 text-sm text-ink-muted">
        Your work is safe. Try reloading this view, or head back to your projects.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button onClick={reset}>Try again</Button>
        <Link href="/projects" className={buttonClasses({ variant: "ghost" })}>
          Back to projects
        </Link>
      </div>
    </div>
  );
}
