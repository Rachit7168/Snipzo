"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { Suspense, useEffect, useState } from "react";

import { Alert, buttonClasses, Card } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

function VerifyEmailInner() {
  const params = useSearchParams();
  const { data: session } = useSession();
  const token = params.get("token") || "";

  const [state, setState] = useState<"verifying" | "verified" | "error">(
    token ? "verifying" : "error",
  );
  const [verifiedEmail, setVerifiedEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(
    token ? null : "Missing verification token. Open the link from your email.",
  );

  useEffect(() => {
    if (!token) return;
    let active = true;
    apiFetch<{ verified: boolean; email: string }>("/auth/verify-email", undefined, {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then((res) => {
        if (!active) return;
        setVerifiedEmail(res.email);
        setState("verified");
      })
      .catch((err) => {
        if (!active) return;
        setError(mapApiError(err, "Could not verify email address.").message);
        setState("error");
      });
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <Card className="mx-auto mt-6 max-w-md space-y-4 sm:mt-10">
      {state === "verifying" && (
        <>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Verifying your email…</h1>
          <p className="text-sm text-ink-muted">Confirming your verification link.</p>
        </>
      )}

      {state === "verified" && (
        <>
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-ink">Email verified</h1>
            <p className="text-sm text-ink-muted">
              <strong className="text-ink">{verifiedEmail}</strong> is confirmed on your Snipzo
              account.
            </p>
          </div>
          <Link
            href={session ? "/projects" : "/login"}
            className={buttonClasses({ variant: "primary", fullWidth: true })}
          >
            {session ? "Go to projects" : "Sign in"}
          </Link>
        </>
      )}

      {state === "error" && (
        <>
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-ink">Verification failed</h1>
            <p className="text-sm text-ink-muted">
              This verification link may have expired or already been used.
            </p>
          </div>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="flex flex-wrap gap-2">
            <Link
              href={session ? "/settings" : "/login"}
              className={buttonClasses({ variant: "primary", fullWidth: true })}
            >
              {session ? "Request a new link in Settings" : "Sign in to resend"}
            </Link>
          </div>
        </>
      )}
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailInner />
    </Suspense>
  );
}
