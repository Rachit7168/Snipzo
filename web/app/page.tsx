"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

import StatusBadge from "@/components/StatusBadge";
import UploadForm from "@/components/UploadForm";
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  ProjectListSkeleton,
} from "@/components/ui";
import { apiFetch, formatSeconds, type Project } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

export default function Dashboard() {
  const { data: session } = useSession();
  const token = session?.accessToken;
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [token]);

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

  return (
    <div className="grid gap-8 lg:grid-cols-[390px_1fr]">
      <div className="space-y-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">
              {session?.plan ? `${session.plan.toUpperCase()} plan` : "Workspace"}
            </Badge>
            <Link href="/billing" className="text-xs font-medium text-ink-muted hover:text-ink">
              View limits →
            </Link>
          </div>
          <h1 className="text-3xl font-black tracking-tight text-ink">
            Long video in, Shorts out.
          </h1>
          <p className="text-sm leading-relaxed text-ink-muted">
            Upload a talk, podcast, or interview — or paste a YouTube video link. Snipzo picks the
            best moments and renders vertical Shorts with captions, a hook title, and metadata
            (720p with watermark on Free; 1080p watermark-free on Creator &amp; Pro).
          </p>
        </div>
        <UploadForm token={token} />
      </div>

      <section className="min-w-0 space-y-3" aria-labelledby="projects-heading">
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
          <EmptyState
            title="No projects yet"
            description="Upload a long-form video or paste a YouTube link on the left to generate your first Shorts."
            icon={
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            }
          />
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
  );
}
