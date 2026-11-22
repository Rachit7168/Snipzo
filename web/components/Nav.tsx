"use client";

import Link from "next/link";
import { signOut, useSession } from "next-auth/react";

export default function Nav() {
  const { data: session } = useSession();
  return (
    <header className="border-b border-neutral-800">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-xl font-black tracking-tight">
          Snip<span className="text-brand">zo</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm text-neutral-300">
          {session ? (
            <>
              <Link href="/" className="hover:text-white">
                Projects
              </Link>
              <Link href="/channels" className="hover:text-white">
                Channels
              </Link>
              <span className="hidden sm:inline">{session.user?.email}</span>
              <button className="btn-ghost py-1" onClick={() => signOut({ callbackUrl: "/login" })}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="hover:text-white">
                Sign in
              </Link>
              <Link href="/register" className="btn py-1">
                Create account
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
