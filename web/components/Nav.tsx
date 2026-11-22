"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { useEffect, useState } from "react";

import { useTheme } from "@/components/ThemeProvider";
import { buttonClasses } from "@/components/ui";

const AUTH_LINKS = [
  { href: "/projects", label: "Projects" },
  { href: "/channels", label: "Channels" },
  { href: "/billing", label: "Billing" },
  { href: "/settings", label: "Settings" },
];

const PUBLIC_LINKS = [
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
];

export default function Nav() {
  const { data: session } = useSession();
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  function isActive(href: string) {
    if (href === "/projects") return pathname === "/projects" || pathname.startsWith("/projects/");
    return pathname.startsWith(href);
  }

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
        <Link
          href={session ? "/projects" : "/"}
          className="flex items-center gap-2 text-xl font-black tracking-tight text-ink"
        >
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-brand text-xs font-black text-brand-fg">
            S
          </span>
          <span>
            Snip<span className="text-brand-text">zo</span>
          </span>
        </Link>

        {/* Desktop nav */}
        <nav aria-label="Primary" className="hidden items-center gap-5 text-sm md:flex">
          {session ? (
            <>
              <div className="flex items-center gap-1">
                {AUTH_LINKS.map((item) => {
                  const active = isActive(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`rounded-lg px-3 py-1.5 font-medium transition ${
                        active
                          ? "bg-surface-elevated text-ink"
                          : "text-ink-muted hover:text-ink"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
              <div className="h-4 w-px bg-line" aria-hidden="true" />
              <button
                type="button"
                onClick={toggleTheme}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                className="rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-elevated hover:text-ink"
              >
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <span className="max-w-[180px] truncate text-xs text-ink-muted" title={session.user?.email || undefined}>
                {session.user?.email}
              </span>
              <button
                type="button"
                className={buttonClasses({ variant: "ghost", size: "sm" })}
                onClick={() => signOut({ callbackUrl: "/login" })}
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-1">
                {PUBLIC_LINKS.map((item) => {
                  const active = item.href === "/pricing" && pathname === "/pricing";
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`rounded-lg px-3 py-1.5 font-medium transition ${
                        active
                          ? "bg-surface-elevated text-ink"
                          : "text-ink-muted hover:text-ink"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
              <div className="h-4 w-px bg-line" aria-hidden="true" />
              <button
                type="button"
                onClick={toggleTheme}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                className="rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-elevated hover:text-ink"
              >
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <Link href="/login" className="font-medium text-ink-muted hover:text-ink">
                Sign in
              </Link>
              <Link href="/register" className={buttonClasses({ variant: "primary", size: "sm" })}>
                Get started free
              </Link>
            </>
          )}
        </nav>

        {/* Mobile menu trigger */}
        <div className="flex items-center gap-2 md:hidden">
          {!session && (
            <Link href="/register" className={buttonClasses({ variant: "primary", size: "sm" })}>
              Get started
            </Link>
          )}
          <button
            type="button"
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
            onClick={() => setMenuOpen((prev) => !prev)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-ink hover:bg-surface-elevated"
          >
            {menuOpen ? (
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu drawer */}
      {menuOpen && (
        <nav
          id="mobile-nav"
          aria-label="Mobile navigation"
          className="border-t border-line bg-surface px-4 py-4 md:hidden"
        >
          <div className="flex flex-col gap-2 text-sm">
            {session ? (
              <>
                {AUTH_LINKS.map((item) => {
                  const active = isActive(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`rounded-lg px-3 py-2 font-medium ${
                        active ? "bg-surface-elevated text-ink" : "text-ink-muted hover:text-ink"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
                <div className="my-1 border-t border-line" />
                <div className="flex items-center justify-between px-3 py-1">
                  <span className="truncate text-xs text-ink-muted">{session.user?.email}</span>
                  <button
                    type="button"
                    onClick={toggleTheme}
                    className="rounded-lg border border-line px-2.5 py-1 text-xs font-medium text-ink-muted"
                  >
                    {theme === "dark" ? "Light mode" : "Dark mode"}
                  </button>
                </div>
                <button
                  type="button"
                  className={buttonClasses({ variant: "ghost", size: "md", fullWidth: true })}
                  onClick={() => signOut({ callbackUrl: "/login" })}
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                {PUBLIC_LINKS.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className="rounded-lg px-3 py-2 font-medium text-ink-muted hover:bg-surface-elevated hover:text-ink"
                  >
                    {item.label}
                  </Link>
                ))}
                <div className="my-1 border-t border-line" />
                <Link
                  href="/login"
                  className="rounded-lg px-3 py-2 font-medium text-ink-muted hover:bg-surface-elevated hover:text-ink"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className={buttonClasses({ variant: "primary", size: "md", fullWidth: true })}
                >
                  Get started free
                </Link>
                <button
                  type="button"
                  onClick={toggleTheme}
                  className="mt-1 rounded-lg border border-line px-3 py-2 text-left text-xs font-medium text-ink-muted"
                >
                  Switch to {theme === "dark" ? "light" : "dark"} mode
                </button>
              </>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}
