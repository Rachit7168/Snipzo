import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-line bg-canvas">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-6 text-xs text-ink-subtle sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center gap-2">
          <span className="font-bold text-ink">Snipzo</span>
          <span>·</span>
          <span>Long videos to vertical Shorts</span>
        </div>
        <div className="flex flex-wrap gap-4">
          <Link href="/privacy" className="hover:text-ink">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-ink">
            Terms
          </Link>
          <Link href="/takedown" className="hover:text-ink">
            Copyright &amp; takedown
          </Link>
        </div>
      </div>
    </footer>
  );
}
