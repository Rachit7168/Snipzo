"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";
import { useState, type FormEvent } from "react";

import { apiFetch } from "@/lib/api";

export default function RegisterPage() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    try {
      await apiFetch("/auth/register", undefined, {
        method: "POST",
        body: JSON.stringify({ email, password, name: form.get("name") || null }),
      });
      const result = await signIn("credentials", { email, password, redirect: false });
      if (!result?.ok) throw new Error("Account created, but sign-in failed.");
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="card mx-auto mt-10 max-w-md space-y-4">
      <h1 className="text-2xl font-bold">Create your account</h1>
      <input className="input" name="name" placeholder="Name (optional)" />
      <input className="input" name="email" type="email" placeholder="you@example.com" required />
      <input
        className="input"
        name="password"
        type="password"
        placeholder="Password (8+ characters)"
        minLength={8}
        required
      />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button className="btn w-full" disabled={busy}>
        {busy ? "Creating..." : "Create account"}
      </button>
      <p className="text-sm text-neutral-400">
        Already have an account?{" "}
        <Link className="text-brand" href="/login">
          Sign in
        </Link>
      </p>
    </form>
  );
}
