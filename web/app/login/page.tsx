"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Suspense, useState, type FormEvent } from "react";

function LoginForm() {
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const result = await signIn("credentials", {
      email: String(form.get("email")),
      password: String(form.get("password")),
      redirect: false,
    });
    setBusy(false);
    if (result?.ok) {
      // Full navigation so cached middleware redirects from before sign-in are dropped.
      window.location.assign(params.get("callbackUrl") || "/");
    } else {
      setError("Wrong email or password.");
    }
  }

  return (
    <form onSubmit={onSubmit} className="card mx-auto mt-10 max-w-md space-y-4">
      <h1 className="text-2xl font-bold">Sign in</h1>
      <input className="input" name="email" type="email" placeholder="you@example.com" required />
      <input className="input" name="password" type="password" placeholder="Password" autoComplete="current-password" required />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button className="btn w-full" disabled={busy}>
        {busy ? "Signing in..." : "Sign in"}
      </button>
      <p className="text-sm text-neutral-400">
        New here?{" "}
        <Link className="text-brand" href="/register">
          Create an account
        </Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
