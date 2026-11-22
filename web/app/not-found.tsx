import Link from "next/link";

import { Badge, buttonClasses } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-16 text-center">
      <Badge tone="brand">404 · Not found</Badge>
      <h1 className="mt-4 text-3xl font-black tracking-tight text-ink">
        This page doesn&apos;t exist
      </h1>
      <p className="mt-2 text-sm text-ink-muted">
        The link may be outdated, or the project or Short you&apos;re looking for was removed.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link href="/" className={buttonClasses({ variant: "primary" })}>
          Go to Snipzo
        </Link>
        <Link href="/channels" className={buttonClasses({ variant: "ghost" })}>
          Channels
        </Link>
      </div>
    </div>
  );
}
