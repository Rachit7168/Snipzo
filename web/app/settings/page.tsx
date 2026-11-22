"use client";

import Link from "next/link";
import { signOut, useSession } from "next-auth/react";
import { useEffect, useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import {
  Alert,
  Badge,
  Button,
  buttonClasses,
  Card,
  Input,
  Modal,
  Skeleton,
  Textarea,
} from "@/components/ui";
import { apiFetch, type BillingUsage, type UserProfile } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

export default function SettingsPage() {
  const { data: session, update: updateSession } = useSession();
  const token = session?.accessToken;
  const { showToast } = useToast();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Profile form state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [resending, setResending] = useState(false);

  // Password form state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwFields, setPwFields] = useState<Record<string, string>>({});

  // Deletion modal state
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteReason, setDeleteReason] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    apiFetch<UserProfile>("/auth/me", token)
      .then((me) => {
        if (!active) return;
        setProfile(me);
        setName(me.name || "");
        setEmail(me.email);
        setLoadError(null);
      })
      .catch((err) => {
        if (active) setLoadError(mapApiError(err, "Could not load account settings.").message);
      });
    apiFetch<BillingUsage>("/billing/me", token)
      .then((info) => {
        if (active) setUsage(info);
      })
      .catch(() => {
        // optional
      });
    return () => {
      active = false;
    };
  }, [token]);

  const emailChanged = profile !== null && email.trim().toLowerCase() !== profile.email.toLowerCase();

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !profile) return;
    setProfileError(null);

    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setProfileError("Enter a valid email address.");
      return;
    }
    if (emailChanged && !emailPassword) {
      setProfileError("Enter your current password to change your email address.");
      return;
    }

    setProfileBusy(true);
    try {
      const updated = await apiFetch<UserProfile>("/auth/me", token, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          email: emailChanged ? trimmedEmail : undefined,
          current_password: emailChanged ? emailPassword : undefined,
        }),
      });
      setProfile(updated);
      setName(updated.name || "");
      setEmail(updated.email);
      setEmailPassword("");
      await updateSession({ name: updated.name, email: updated.email });
      showToast({
        title: emailChanged ? "Email updated — verify your new address" : "Profile saved",
        message: emailChanged
          ? `We sent a verification link to ${updated.email}.`
          : "Your account details are up to date.",
        tone: "success",
      });
    } catch (err) {
      setProfileError(mapApiError(err, "Could not save profile.").message);
    } finally {
      setProfileBusy(false);
    }
  }

  async function resendVerification() {
    if (!token || resending) return;
    setResending(true);
    try {
      const res = await apiFetch<{ sent: boolean; already_verified: boolean }>(
        "/auth/verify-email/resend",
        token,
        { method: "POST" },
      );
      if (res.already_verified) {
        setProfile((prev) => (prev ? { ...prev, email_verified: true } : prev));
        showToast({ title: "Email verified", message: "Your email is already verified.", tone: "success" });
      } else {
        showToast({
          title: "Verification link sent",
          message: `Check ${profile?.email} for your verification link.`,
          tone: "success",
        });
      }
    } catch (err) {
      showToast({
        title: "Could not send link",
        message: mapApiError(err, "Please try again in a moment.").message,
        tone: "error",
      });
    } finally {
      setResending(false);
    }
  }

  async function submitPasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setPwError(null);
    setPwFields({});

    const nextFields: Record<string, string> = {};
    if (!currentPassword) nextFields.current = "Enter your current password.";
    if (newPassword.length < 8) nextFields.next = "Use at least 8 characters.";
    if (newPassword !== confirmPassword) nextFields.confirm = "Passwords do not match.";
    if (Object.keys(nextFields).length > 0) {
      setPwFields(nextFields);
      return;
    }

    setPwBusy(true);
    try {
      await apiFetch<{ ok: boolean; message: string }>("/auth/change-password", token, {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      showToast({
        title: "Password updated",
        message: "Use your new password the next time you sign in.",
        tone: "success",
      });
    } catch (err) {
      setPwError(mapApiError(err, "Could not update password.").message);
    } finally {
      setPwBusy(false);
    }
  }

  async function submitDeleteRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setDeleteError(null);
    if (!deletePassword) {
      setDeleteError("Enter your password to confirm.");
      return;
    }

    setDeleteBusy(true);
    try {
      const updated = await apiFetch<UserProfile>("/auth/delete-request", token, {
        method: "POST",
        body: JSON.stringify({
          password: deletePassword,
          reason: deleteReason.trim() || undefined,
        }),
      });
      setProfile(updated);
      setDeletePassword("");
      setDeleteReason("");
      setDeleteOpen(false);
      showToast({
        title: "Deletion requested",
        message: "Your account is queued for deletion.",
        tone: "success",
      });
    } catch (err) {
      setDeleteError(mapApiError(err, "Could not submit deletion request.").message);
    } finally {
      setDeleteBusy(false);
    }
  }

  if (!token || (!profile && !loadError)) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-3xl font-black tracking-tight text-ink">Account settings</h1>
          <p className="text-sm text-ink-muted">
            Manage your profile, email verification, password, and connected workspace.
          </p>
        </div>
        <Link href="/projects" className={buttonClasses({ variant: "ghost", size: "sm" })}>
          ← Back to projects
        </Link>
      </div>

      {loadError && <Alert tone="error">{loadError}</Alert>}

      {profile && (
        <>
          {/* Profile & email verification */}
          <Card className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-ink">Profile &amp; email</h2>
                <p className="text-xs text-ink-muted">
                  Your email is used for sign-in, verification, and password recovery.
                </p>
              </div>
              {profile.email_verified ? (
                <Badge tone="success">Email verified</Badge>
              ) : (
                <Badge tone="warning">Unverified email</Badge>
              )}
            </div>

            {!profile.email_verified && (
              <Alert tone="warning" title="Email verification pending">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span>
                    We sent a confirmation link to <strong className="text-ink">{profile.email}</strong>.
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    loading={resending}
                    onClick={resendVerification}
                  >
                    Resend verification email
                  </Button>
                </div>
              </Alert>
            )}

            <form onSubmit={saveProfile} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  id="settings-name"
                  label="Display name"
                  placeholder="Your name or channel"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <Input
                  id="settings-email"
                  type="email"
                  label="Email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              {emailChanged && (
                <Input
                  id="settings-email-password"
                  type="password"
                  label="Current password (required to change email)"
                  placeholder="Enter your current password"
                  autoComplete="current-password"
                  value={emailPassword}
                  onChange={(e) => setEmailPassword(e.target.value)}
                />
              )}

              {profileError && <Alert tone="error">{profileError}</Alert>}

              <div className="flex justify-end">
                <Button type="submit" loading={profileBusy}>
                  {profileBusy ? "Saving..." : "Save profile"}
                </Button>
              </div>
            </form>
          </Card>

          {/* Password */}
          <Card className="space-y-5">
            <div>
              <h2 className="text-lg font-bold text-ink">Password</h2>
              <p className="text-xs text-ink-muted">
                Choose a strong password of at least 8 characters.
              </p>
            </div>

            <form onSubmit={submitPasswordChange} className="space-y-4">
              <Input
                id="pw-current"
                type="password"
                label="Current password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                error={pwFields.current}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  id="pw-new"
                  type="password"
                  label="New password"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  error={pwFields.next}
                />
                <Input
                  id="pw-confirm"
                  type="password"
                  label="Confirm new password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  error={pwFields.confirm}
                />
              </div>

              {pwError && <Alert tone="error">{pwError}</Alert>}

              <div className="flex justify-end">
                <Button type="submit" variant="secondary" loading={pwBusy}>
                  {pwBusy ? "Updating..." : "Update password"}
                </Button>
              </div>
            </form>
          </Card>

          {/* Plan, channels, and session */}
          <Card className="space-y-4">
            <h2 className="text-lg font-bold text-ink">Workspace &amp; connections</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-control border border-line bg-canvas/40 p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium uppercase tracking-wider text-ink-subtle">
                    Current plan
                  </span>
                  <Badge tone="brand">{usage?.plan.name || profile.plan.toUpperCase()}</Badge>
                </div>
                <p className="mt-2 text-xs text-ink-muted">
                  {usage
                    ? `${usage.videos_used}/${usage.plan.videos_per_month} videos · ${usage.minutes_used.toFixed(0)}/${usage.plan.minutes_per_month} min used this month`
                    : "Manage your subscription, usage limits, and invoices."}
                </p>
                <Link
                  href="/billing"
                  className="mt-3 inline-block text-xs font-semibold text-brand-text hover:underline"
                >
                  Manage plan &amp; billing →
                </Link>
              </div>

              <div className="rounded-control border border-line bg-canvas/40 p-4">
                <span className="text-xs font-medium uppercase tracking-wider text-ink-subtle">
                  YouTube channels
                </span>
                <p className="mt-2 text-xs text-ink-muted">
                  Connect or disconnect your YouTube channels for one-click uploads and imports.
                </p>
                <Link
                  href="/channels"
                  className="mt-3 inline-block text-xs font-semibold text-brand-text hover:underline"
                >
                  Manage YouTube channels →
                </Link>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
              <span className="text-xs text-ink-muted">
                Signed in as <strong className="text-ink">{profile.email}</strong>
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => signOut({ callbackUrl: "/login" })}
              >
                Sign out
              </Button>
            </div>
          </Card>

          {/* Danger zone */}
          <Card className="space-y-4 border-danger/30">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-ink">Delete account</h2>
                <p className="text-xs text-ink-muted">
                  Request permanent removal of your account, projects, and rendered clips.
                </p>
              </div>
              {profile.deletion_requested_at ? (
                <Badge tone="warning">Deletion requested</Badge>
              ) : null}
            </div>

            {profile.deletion_requested_at ? (
              <Alert tone="warning" title="Account deletion requested">
                Your deletion request was logged on{" "}
                {new Date(profile.deletion_requested_at).toLocaleDateString()}. Contact{" "}
                <a href="mailto:support@snipzo.app" className="underline">
                  support@snipzo.app
                </a>{" "}
                if you changed your mind.
              </Alert>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-ink-muted">
                  We confirm ownership with your password before queuing account removal.
                </p>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    setDeleteError(null);
                    setDeleteOpen(true);
                  }}
                >
                  Request account deletion
                </Button>
              </div>
            )}
          </Card>

          <Modal
            open={deleteOpen}
            onClose={() => setDeleteOpen(false)}
            title="Request account deletion"
            description="Your projects, uploaded videos, and rendered Shorts will be queued for permanent deletion."
          >
            <form onSubmit={submitDeleteRequest} className="space-y-4">
              <Input
                id="delete-password"
                type="password"
                label="Confirm your password"
                autoComplete="current-password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                required
              />
              <Textarea
                id="delete-reason"
                label="Reason (optional)"
                placeholder="Tell us what could have worked better"
                rows={3}
                value={deleteReason}
                onChange={(e) => setDeleteReason(e.target.value)}
              />
              {deleteError && <Alert tone="error">{deleteError}</Alert>}
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setDeleteOpen(false)}
                  disabled={deleteBusy}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="danger" loading={deleteBusy}>
                  {deleteBusy ? "Submitting..." : "Confirm deletion request"}
                </Button>
              </div>
            </form>
          </Modal>
        </>
      )}
    </div>
  );
}
