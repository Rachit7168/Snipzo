"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useEffect, useRef, useState } from "react";

import StatusBadge from "@/components/StatusBadge";
import UploadForm from "@/components/UploadForm";
import WelcomeOnboardingModal from "@/components/WelcomeOnboardingModal";
import {
  Alert,
  Badge,
  Button,
  buttonClasses,
  Card,
  ProjectListSkeleton,
} from "@/components/ui";
import { apiFetch, formatSeconds, type BillingUsage, type Project, type UserProfile } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { mapApiError } from "@/lib/errors";

const WELCOME_DISMISSED_KEY = "snipzo_welcome_dismissed";
const CHECKLIST_DISMISSED_KEY = "snipzo_checklist_dismissed";

export default function DashboardClient() {
  const { data: session } = useSession();
  const token = session?.accessToken;
  const uploadSectionRef = useRef<HTMLDivElement | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const { showToast } = useToast();
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [resendingVerify, setResendingVerify] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [checklistDismissed, setChecklistDismissed] = useState(true);

  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const isWelcome = params.get("welcome") === "1";
      const alreadySeen = window.localStorage.getItem(WELCOME_DISMISSED_KEY) === "1";
      if (isWelcome && !alreadySeen) {
        setWelcomeOpen(true);
      }
      setChecklistDismissed(window.localStorage.getItem(CHECKLIST_DISMISSED_KEY) === "1");
    } catch {
      setChecklistDismissed(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    let active = true;
    const load = () =>
      apiFetch<Project[]>("/projects", token)
        .then((items) => {
          if (active) {
            setProjects(items);
            setError(null);
          }
        })
        .catch((err: unknown) => {
          if (active) setError(mapApiError(err, "Could not load projects.").message);
        });
    load();
    apiFetch<BillingUsage>("/billing/me", token)
      .then((info) => {
        if (active) setUsage(info);
      })
      .catch(() => {
        // optional usage summary
      });
    apiFetch<UserProfile>("/auth/me", token)
      .then((me) => {
        if (active) setProfile(me);
      })
      .catch(() => {
        // optional profile banner
      });
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [token]);

  function closeWelcome() {
    setWelcomeOpen(false);
    try {
      window.localStorage.setItem(WELCOME_DISMISSED_KEY, "1");
      const url = new URL(window.location.href);
      if (url.searchParams.has("welcome")) {
        url.searchParams.delete("welcome");
        window.history.replaceState({}, "", url.pathname + url.search);
      }
    } catch {
      // ignore storage errors
    }
  }

  async function resendVerification() {
    if (!token || resendingVerify) return;
    setResendingVerify(true);
    try {
      const res = await apiFetch<{ sent: boolean; already_verified: boolean }>(
        "/auth/verify-email/resend",
        token,
        { method: "POST" },
      );
      if (res.already_verified) {
        setProfile((prev) => (prev ? { ...prev, email_verified: true } : prev));
        showToast({ title: "Already verified", message: "Your email is verified.", tone: "success" });
      } else {
        showToast({
          title: "Verification email sent",
          message: "Check your inbox (or server logs in dev) for the link.",
          tone: "success",
        });
      }
    } catch (err) {
      showToast({
        title: "Could not send verification",
        message: mapApiError(err, "Please try again in a moment.").message,
        tone: "error",
      });
    } finally {
      setResendingVerify(false);
    }
  }

  function dismissChecklist() {
    setChecklistDismissed(true);
    try {
      window.localStorage.setItem(CHECKLIST_DISMISSED_KEY, "1");
    } catch {
      // ignore
    }
  }

  function focusUpload() {
    uploadSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    const titleInput = document.getElementById("upload-title");
    if (titleInput instanceof HTMLElement) {
      titleInput.focus({ preventScroll: true });
    }
  }

  if (!token) {
    return (
      <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
        <Card className="space-y-4">
          <div className="h-7 w-2/3 animate-pulse rounded-lg bg-surface-muted" />
          <div className="h-24 animate-pulse rounded-lg bg-surface-muted" />
        </Card>
        <ProjectListSkeleton />
      </div>
    );
  }

  const hasProjects = projects !== null && projects.length > 0;
  const hasCompleteProject = projects !== null && projects.some((p) => p.status === "complete");
  const showChecklist = !checklistDismissed && (!hasCompleteProject || (projects?.length ?? 0) <= 1);
  const planName = usage?.plan.name || (session?.plan ? session.plan.toUpperCase() : "Free");

  return (
    <>
      <WelcomeOnboardingModal
        open={welcomeOpen}
        onClose={closeWelcome}
        onStartUpload={focusUpload}
        videosPerMonth={usage?.plan.videos_per_month}
        minutesPerMonth={usage?.plan.minutes_per_month}
      />

      <div className="grid gap-8 lg:grid-cols-[390px_1fr]">
        <div ref={uploadSectionRef} className="space-y-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand">{planName} plan</Badge>
              <Link href="/billing" className="text-xs font-medium text-ink-muted hover:text-ink">
                View limits →
              </Link>
              <Link href="/pricing" className="text-xs font-medium text-ink-subtle hover:text-ink">
                Pricing
              </Link>
            </div>
            <h1 className="text-3xl font-black tracking-tight text-ink">
              Long video in, Shorts out.
            </h1>
            <p className="text-sm leading-relaxed text-ink-muted">
              Upload a talk, podcast, or interview — or paste a YouTube video link. Snipzo picks
              the best moments and renders vertical Shorts with captions, a hook title, and metadata.
            </p>
          </div>

          {usage ? (
            <div className="rounded-control border border-line bg-surface px-3.5 py-2.5 text-xs text-ink-muted">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <strong className="text-ink">
                    {usage.videos_used}/{usage.plan.videos_per_month}
                  </strong>{" "}
                  {usage.plan.videos_per_month === 1 ? "video" : "videos"} ·{" "}
                  <strong className="text-ink">
                    {usage.minutes_used.toFixed(0)}/{usage.plan.minutes_per_month}
                  </strong>{" "}
                  min used this month
                </span>
                <span className="text-ink-subtle">
                  {usage.plan.max_resolution}
                  {usage.plan.watermark ? " · watermarked" : " · clean"}
                </span>
              </div>
            </div>
          ) : (
            <div className="rounded-control border border-line bg-surface px-3.5 py-2.5 text-xs text-ink-muted">
              720p with Snipzo watermark on Free (3 videos / 30 min per month); 1080p watermark-free
              on Creator &amp; Pro.
            </div>
          )}

          <UploadForm token={token} />
        </div>

        <section className="min-w-0 space-y-4" aria-labelledby="projects-heading">
          {profile && !profile.email_verified && (
            <Alert tone="warning" title="Verify your email address">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span>
                  Confirm <strong className="text-ink">{profile.email}</strong> so you can recover
                  your account anytime. Uploads still work right away.
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    loading={resendingVerify}
                    onClick={resendVerification}
                  >
                    Resend email
                  </Button>
                  <Link href="/settings" className="text-xs font-medium text-ink underline">
                    Settings
                  </Link>
                </div>
              </div>
            </Alert>
          )}
          {showChecklist && (
            <Card className="space-y-3 border-brand/30 bg-surface/90">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold text-ink">Getting started</h2>
                  <p className="text-xs text-ink-muted">
                    Go from raw video to ready-to-post Shorts without a card or YouTube login.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={dismissChecklist}
                  className="text-xs font-medium text-ink-subtle hover:text-ink"
                >
                  Dismiss
                </button>
              </div>
              <ol className="grid gap-2 text-xs sm:grid-cols-3">
                {[
                  { label: "Create account", done: true },
                  { label: "Upload or paste a link", done: hasProjects },
                  { label: "Edit or download Short", done: hasCompleteProject },
                ].map((step, idx) => (
                  <li
                    key={step.label}
                    className={`flex items-center gap-2 rounded-control border px-3 py-2 font-medium ${
                      step.done
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                        : "border-line bg-surface-muted/60 text-ink-muted"
                    }`}
                  >
                    <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-current text-[10px] font-bold">
                      {step.done ? "✓" : idx + 1}
                    </span>
                    <span className="truncate">{step.label}</span>
                  </li>
                ))}
              </ol>
            </Card>
          )}

          <div className="flex items-center justify-between">
            <h2 id="projects-heading" className="text-lg font-bold tracking-tight text-ink">
              Your projects
            </h2>
            {projects && projects.length > 0 && (
              <span className="text-xs text-ink-subtle">
                {projects.length} {projects.length === 1 ? "project" : "projects"}
              </span>
            )}
          </div>

          {error && <Alert tone="error">{error}</Alert>}

          {projects === null ? (
            <ProjectListSkeleton />
          ) : projects.length === 0 ? (
            <Card className="grid items-center gap-6 p-6 sm:grid-cols-[1fr_180px]">
              <div className="space-y-3">
                <Badge tone="neutral">First run</Badge>
                <h3 className="text-xl font-bold tracking-tight text-ink">
                  Upload your first video
                </h3>
                <p className="text-sm leading-relaxed text-ink-muted">
                  Drop a video you own on the left or paste a public YouTube link. In a few
                  minutes you&apos;ll have vertical Shorts with speaker-centered framing and burned-in
                  captions ready to edit or download.
                </p>
                <div className="flex flex-wrap items-center gap-2.5 pt-1">
                  <Button type="button" onClick={focusUpload}>
                    Upload your first video
                  </Button>
                  <Link href="/pricing" className={buttonClasses({ variant: "ghost", size: "md" })}>
                    See plan limits
                  </Link>
                </div>
              </div>
              <div className="mx-auto w-full max-w-[180px] space-y-1.5">
                <div className="aspect-[9/16] overflow-hidden rounded-xl border border-line bg-black">
                  <video
                    src="/demo-short.mp4"
                    poster="/demo-poster.jpg"
                    autoPlay
                    loop
                    muted
                    playsInline
                    preload="metadata"
                    aria-label="Sample vertical Short preview"
                    className="h-full w-full object-cover"
                  />
                </div>
                <p className="text-center text-[11px] text-ink-subtle">
                  Sample output · 9:16 + captions
                </p>
              </div>
            </Card>
          ) : (
            <ul className="space-y-3">
              {projects.map((project) => (
                <li key={project.id}>
                  <Link
                    href={`/projects/${project.id}`}
                    className="card flex flex-col gap-3 transition hover:border-line-strong sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      {project.source_thumbnail_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={project.source_thumbnail_url}
                          alt=""
                          className="h-12 w-20 shrink-0 rounded-md bg-surface-muted object-cover"
                        />
                      )}
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-ink">
                          {project.title || project.source_filename}
                        </p>
                        <p className="text-xs text-ink-subtle">
                          {new Date(project.created_at).toLocaleString()} ·{" "}
                          {formatSeconds(project.duration_seconds)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between gap-3 sm:justify-end">
                      {project.job && project.job.status === "running" && (
                        <span className="text-xs font-medium text-ink-muted">
                          {Math.round(project.job.progress * 100)}%
                        </span>
                      )}
                      <StatusBadge status={project.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
