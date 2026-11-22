"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";
import { useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { Alert, Button, Card, Input } from "@/components/ui";
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
      window.location.assign("/projects?welcome=1");
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
    <Card className="mx-auto mt-6 max-w-md sm:mt-10">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-ink">Create your account</h1>
          <p className="text-sm text-ink-muted">Start turning long videos into Shorts in minutes.</p>
        </div>

        <Input
          id="register-name"
          name="name"
          label="Name (optional)"
          placeholder="Your name"
          error={fieldErrors.name}
        />

        <Input
          id="register-email"
          name="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          autoComplete="email"
          required
          error={fieldErrors.email}
        />

        <Input
          id="register-password"
          name="password"
          type="password"
          label="Password"
          placeholder="8+ characters"
          autoComplete="new-password"
          minLength={8}
          required
          error={fieldErrors.password}
        />

        {formError && <Alert tone="error">{formError}</Alert>}

        <Button type="submit" fullWidth loading={busy}>
          {busy ? "Creating..." : "Create account"}
        </Button>

        <p className="text-sm text-ink-muted">
          Already have an account?{" "}
          <Link className="font-medium text-brand-text hover:underline" href="/login">
            Sign in
          </Link>
        </p>
      </form>
    </Card>
  );
}
