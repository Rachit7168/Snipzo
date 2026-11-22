import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-neutral-800">
      <div className="mx-auto flex max-w-6xl flex-wrap gap-4 px-6 py-6 text-xs text-neutral-500">
        <span>© Snipzo</span>
        <Link href="/privacy" className="hover:text-white">
          Privacy
        </Link>
        <Link href="/terms" className="hover:text-white">
          Terms
        </Link>
        <Link href="/takedown" className="hover:text-white">
          Copyright &amp; takedown
        </Link>
      </div>
    </footer>
  );
}
