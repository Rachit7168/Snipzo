"use client";

import Link from "next/link";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        <main className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
          <p className="text-xl font-black tracking-tight">
            Snip<span className="text-yellow-400">zo</span>
          </p>
          <h1 className="mt-4 text-3xl font-black tracking-tight text-white">
            Something went wrong
          </h1>
          <p className="mt-2 text-sm text-neutral-400">
            We couldn&apos;t load the page right now. Try refreshing, or return home.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={reset}
              className="inline-flex items-center justify-center rounded-lg bg-yellow-400 px-4 py-2 text-sm font-semibold text-neutral-950 hover:bg-yellow-500"
            >
              Reload page
            </button>
            <Link
              href="/"
              className="inline-flex items-center justify-center rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-200 hover:bg-neutral-800"
            >
              Go home
            </Link>
          </div>
        </main>
      </body>
    </html>
  );
}
