"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Suspense, useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { Alert, Button, Card, Input } from "@/components/ui";

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
        window.location.assign(params.get("callbackUrl") || "/projects");
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
    <Card className="mx-auto mt-6 max-w-md sm:mt-10">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-ink">Sign in</h1>
          <p className="text-sm text-ink-muted">Welcome back to Snipzo.</p>
        </div>

        <Input
          id="login-email"
          name="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          autoComplete="email"
          required
          error={fieldErrors.email}
        />

        <Input
          id="login-password"
          name="password"
          type="password"
          label="Password"
          placeholder="Password"
          autoComplete="current-password"
          required
          error={fieldErrors.password}
        />

        {formError && <Alert tone="error">{formError}</Alert>}

        <Button type="submit" fullWidth loading={busy}>
          {busy ? "Signing in..." : "Sign in"}
        </Button>

        <p className="text-sm text-ink-muted">
          New here?{" "}
          <Link className="font-medium text-brand-text hover:underline" href="/register">
            Create an account
          </Link>
        </p>
      </form>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
