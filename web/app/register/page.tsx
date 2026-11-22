"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";
import { useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { apiFetch } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

export default function RegisterPage() {
  const { showToast } = useToast();
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    setFieldErrors({});
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "");
    const password = String(form.get("password") || "");
    const name = String(form.get("name") || "").trim();

    try {
      await apiFetch("/auth/register", undefined, {
        method: "POST",
        body: JSON.stringify({ email, password, name: name || null }),
      });
      const result = await signIn("credentials", { email, password, redirect: false });
      if (result?.error === "SERVICE_UNAVAILABLE") {
        throw new Error("Account created, but we can't reach the sign-in service right now.");
      }
      if (!result?.ok) throw new Error("Account created, but automatic sign-in failed. Try signing in.");
      window.location.assign("/");
    } catch (err) {
      const mapped = mapApiError(err, "Could not create the account.");
      if (mapped.fields && Object.keys(mapped.fields).length > 0) {
        setFieldErrors(mapped.fields);
      } else {
        setFormError(mapped.message);
        showToast({ title: mapped.title, message: mapped.message, tone: "error" });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card mx-auto mt-10 max-w-md space-y-4">
      <h1 className="text-2xl font-bold">Create your account</h1>

      <div className="space-y-1">
        <label htmlFor="register-name" className="block text-xs font-medium text-neutral-300">
          Name (optional)
        </label>
        <input
          id="register-name"
          className="input"
          name="name"
          placeholder="Your name"
          aria-invalid={Boolean(fieldErrors.name)}
          aria-describedby={fieldErrors.name ? "register-name-error" : undefined}
        />
        {fieldErrors.name && (
          <p id="register-name-error" className="text-xs text-red-400">
            {fieldErrors.name}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="register-email" className="block text-xs font-medium text-neutral-300">
          Email
        </label>
        <input
          id="register-email"
          className="input"
          name="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          required
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? "register-email-error" : undefined}
        />
        {fieldErrors.email && (
          <p id="register-email-error" className="text-xs text-red-400">
            {fieldErrors.email}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="register-password" className="block text-xs font-medium text-neutral-300">
          Password
        </label>
        <input
          id="register-password"
          className="input"
          name="password"
          type="password"
          placeholder="8+ characters"
          autoComplete="new-password"
          minLength={8}
          required
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby={fieldErrors.password ? "register-password-error" : undefined}
        />
        {fieldErrors.password && (
          <p id="register-password-error" className="text-xs text-red-400">
            {fieldErrors.password}
          </p>
        )}
      </div>

      {formError && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {formError}
        </div>
      )}

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
