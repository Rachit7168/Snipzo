"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, Button, Card, Input } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const cleaned = email.trim();
    if (!cleaned || !cleaned.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }
    setBusy(true);
    try {
      await apiFetch<{ ok: boolean; message: string }>("/auth/forgot-password", undefined, {
        method: "POST",
        body: JSON.stringify({ email: cleaned }),
      });
      setSubmitted(true);
    } catch (err) {
      setError(mapApiError(err, "Could not request a password reset.").message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mx-auto mt-6 max-w-md sm:mt-10">
      {submitted ? (
        <div className="space-y-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-ink">Check your inbox</h1>
            <p className="text-sm text-ink-muted">
              If an account exists for <strong className="text-ink">{email.trim()}</strong>, we
              sent a password reset link that expires in 1 hour.
            </p>
          </div>
          <Alert tone="info">
            Running locally? Check the API console logs for the reset link when using the default
            console email backend.
          </Alert>
          <Link href="/login" className="inline-block text-sm font-medium text-brand-text hover:underline">
            ← Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-ink">Reset your password</h1>
            <p className="text-sm text-ink-muted">
              Enter your account email and we will send you a link to set a new password.
            </p>
          </div>
          <Input
            id="forgot-email"
            type="email"
            label="Email"
            placeholder="you@example.com"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" fullWidth loading={busy}>
            {busy ? "Sending link..." : "Send reset link"}
          </Button>
          <p className="text-sm text-ink-muted">
            Remembered it?{" "}
            <Link href="/login" className="font-medium text-brand-text hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </Card>
  );
}
