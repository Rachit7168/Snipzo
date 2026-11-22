"use client";

import Link from "next/link";
import { useEffect } from "react";

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
      <span className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-red-300">
        Something went wrong
      </span>
      <h1 className="mt-4 text-3xl font-black tracking-tight text-white">
        We hit an unexpected snag
      </h1>
      <p className="mt-2 text-sm text-neutral-400">
        Your work is safe. Try reloading this view, or head back to your projects.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button type="button" onClick={reset} className="btn">
          Try again
        </button>
        <Link href="/" className="btn-ghost">
          Back to projects
        </Link>
      </div>
    </div>
  );
}
