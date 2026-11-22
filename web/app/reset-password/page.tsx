"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { Alert, Button, buttonClasses, Card, Input } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

function ResetPasswordForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("Missing reset token. Open the full link from your email.");
      return;
    }
    if (password.length < 8) {
      setError("Use at least 8 characters for your new password.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      await apiFetch<{ ok: boolean; message: string }>("/auth/reset-password", undefined, {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      setDone(true);
    } catch (err) {
      setError(mapApiError(err, "Could not reset password.").message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mx-auto mt-6 max-w-md sm:mt-10">
      {done ? (
        <div className="space-y-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-ink">Password updated</h1>
            <p className="text-sm text-ink-muted">
              Your password has been reset. You can sign in now with your new password.
            </p>
          </div>
          <Link href="/login" className={buttonClasses({ variant: "primary", fullWidth: true })}>
            Sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-ink">Choose a new password</h1>
            <p className="text-sm text-ink-muted">Enter a new password for your Snipzo account.</p>
          </div>

          {!token && (
            <Alert tone="warning">
              No reset token was found in the URL. Request a new link from{" "}
              <Link href="/forgot-password" className="underline">
                forgot password
              </Link>
              .
            </Alert>
          )}

          <Input
            id="reset-password"
            type="password"
            label="New password"
            placeholder="At least 8 characters"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Input
            id="reset-confirm"
            type="password"
            label="Confirm new password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />

          {error && <Alert tone="error">{error}</Alert>}

          <Button type="submit" fullWidth loading={busy} disabled={!token}>
            {busy ? "Resetting..." : "Set new password"}
          </Button>
        </form>
      )}
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
