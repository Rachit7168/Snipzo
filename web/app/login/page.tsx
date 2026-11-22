"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Suspense, useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";

function LoginForm() {
  const params = useSearchParams();
  const { showToast } = useToast();
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");

    const nextFields: Record<string, string> = {};
    if (!email || !email.includes("@")) {
      nextFields.email = "Enter a valid email address.";
    }
    if (!password) {
      nextFields.password = "Password is required.";
    }
    if (Object.keys(nextFields).length > 0) {
      setFieldErrors(nextFields);
      return;
    }

    setBusy(true);
    try {
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });
      if (result?.ok) {
        // Full navigation so cached middleware redirects from before sign-in are dropped.
        window.location.assign(params.get("callbackUrl") || "/");
        return;
      }
      if (result?.error === "SERVICE_UNAVAILABLE") {
        const message = "Can't reach the Snipzo service right now. Please try again in a moment.";
        setFormError(message);
        showToast({ title: "Service unavailable", message, tone: "error" });
      } else {
        setFormError("Wrong email or password.");
      }
    } catch {
      const message = "Can't reach the Snipzo service right now. Please try again in a moment.";
      setFormError(message);
      showToast({ title: "Service unavailable", message, tone: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card mx-auto mt-10 max-w-md space-y-4">
      <h1 className="text-2xl font-bold">Sign in</h1>

      <div className="space-y-1">
        <label htmlFor="login-email" className="block text-xs font-medium text-neutral-300">
          Email
        </label>
        <input
          id="login-email"
          className="input"
          name="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          required
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? "login-email-error" : undefined}
        />
        {fieldErrors.email && (
          <p id="login-email-error" className="text-xs text-red-400">
            {fieldErrors.email}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="login-password" className="block text-xs font-medium text-neutral-300">
          Password
        </label>
        <input
          id="login-password"
          className="input"
          name="password"
          type="password"
          placeholder="Password"
          autoComplete="current-password"
          required
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby={fieldErrors.password ? "login-password-error" : undefined}
        />
        {fieldErrors.password && (
          <p id="login-password-error" className="text-xs text-red-400">
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
