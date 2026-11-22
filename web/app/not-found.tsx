import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-16 text-center">
      <span className="rounded-full border border-neutral-800 bg-neutral-900 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-brand">
        404 · Not found
      </span>
      <h1 className="mt-4 text-3xl font-black tracking-tight text-white">
        This page doesn&apos;t exist
      </h1>
      <p className="mt-2 text-sm text-neutral-400">
        The link may be outdated, or the project or Short you&apos;re looking for was removed.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link href="/" className="btn">
          Go to Snipzo
        </Link>
        <Link href="/channels" className="btn-ghost">
          Channels
        </Link>
      </div>
    </div>
  );
}
