"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

import ClipCard from "@/components/ClipCard";
import PipelineProgress from "@/components/PipelineProgress";
import PublishPanel from "@/components/PublishPanel";
import StatusBadge from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import {
  Alert,
  Button,
  buttonClasses,
  CardGridSkeleton,
  Modal,
  Skeleton,
} from "@/components/ui";
import { apiFetch, formatSeconds, type Project } from "@/lib/api";
import { mapApiError, sanitizeJobErrorText } from "@/lib/errors";

const DONE = new Set(["complete", "failed"]);

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: session } = useSession();
  const { showToast } = useToast();
  const token = session?.accessToken;
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!token || !id) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const data = await apiFetch<Project>(`/projects/${id}`, token);
        if (!active) return;
        setProject(data);
        const jobRunning = data.job && !["succeeded", "failed"].includes(data.job.status);
        if (!DONE.has(data.status) || jobRunning) timer = setTimeout(load, 2500);
      } catch (err) {
        if (active) setError(mapApiError(err, "Could not load project.").message);
      }
    };
    load();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [token, id]);

  async function handleDelete() {
    if (!token || !project) return;
    setDeleting(true);
    try {
      await apiFetch(`/projects/${project.id}`, token, { method: "DELETE" });
      showToast({ title: "Project deleted", message: "Removed source and clips.", tone: "success" });
      router.push("/projects");
    } catch (err) {
      const mapped = mapApiError(err, "Could not delete project.");
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg">
        <Alert
          tone="error"
          title="Couldn't open this project"
          action={
            <Link href="/projects" className={buttonClasses({ variant: "primary", size: "md" })}>
              Back to projects
            </Link>
          }
        >
          {error}
        </Alert>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading project">
        <div className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-64" />
        </div>
        <CardGridSkeleton count={3} />
      </div>
    );
  }

  const job = project.job;
  const running = job && !["succeeded", "failed"].includes(job.status);
  const failed = project.status === "failed" || job?.status === "failed";
  const friendlyFailure = failed ? sanitizeJobErrorText(job?.error || project.error) : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <Link href="/projects" className="inline-block text-sm text-ink-muted hover:text-ink">
            ← Projects
          </Link>
          <div className="flex items-start gap-3">
            {project.source_thumbnail_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={project.source_thumbnail_url}
                alt={project.source_title || project.title || "Source video"}
                className="h-16 w-28 shrink-0 rounded-md bg-surface-muted object-cover"
              />
            )}
            <div className="min-w-0">
              <h1 className="break-words text-2xl font-bold tracking-tight text-ink">
                {project.title || project.source_filename}
              </h1>
              <p className="truncate text-sm text-ink-subtle">
                {project.source_title || project.source_filename} ·{" "}
                {formatSeconds(project.duration_seconds)}
              </p>
              {project.source_page_url && (
                <a
                  href={project.source_page_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-ink-muted hover:text-ink"
                >
                  Open source on YouTube
                </a>
              )}
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <StatusBadge status={project.status} />
          <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
            Delete
          </Button>
        </div>
      </div>

      {job && running && (
        <PipelineProgress job={job} durationSeconds={project.duration_seconds} />
      )}

      {failed && friendlyFailure && (
        <Alert
          tone="error"
          title="We couldn't finish processing this video"
          action={
            <>
              <Link href="/projects" className={buttonClasses({ variant: "primary", size: "md" })}>
                Try another file
              </Link>
              <Link href="/takedown" className={buttonClasses({ variant: "ghost", size: "md" })}>
                Contact support
              </Link>
            </>
          }
        >
          {friendlyFailure}
        </Alert>
      )}

      {project.clips.length > 0 && project.status === "complete" && (
        <Alert
          tone="success"
          title="Your Shorts are ready — what would you like to do next?"
          action={
            <div className="flex flex-wrap gap-2">
              <Link
                href={`/projects/${project.id}/clips/${project.clips[0].clip_id}`}
                className={buttonClasses({ variant: "primary", size: "sm" })}
              >
                Open clip editor
              </Link>
              {project.clips[0].download_url && (
                <a
                  href={project.clips[0].download_url}
                  download={`${project.clips[0].clip_id}.mp4`}
                  className={buttonClasses({ variant: "secondary", size: "sm" })}
                >
                  Download top Short
                </a>
              )}
              <Link
                href="/channels"
                className={buttonClasses({ variant: "ghost", size: "sm" })}
              >
                Connect YouTube
              </Link>
            </div>
          }
        >
          Preview your vertical clips below, trim or edit captions in the editor, download MP4s,
          or publish straight to YouTube Shorts.
        </Alert>
      )}

      {project.clips.length > 0 && token && project.status === "complete" && (
        <PublishPanel projectId={project.id} clips={project.clips} token={token} />
      )}

      {project.clips.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold tracking-tight text-ink">
            {project.clips.length} {project.clips.length === 1 ? "Short" : "Shorts"}
          </h2>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {project.clips.map((clip) => (
              <ClipCard
                key={clip.clip_id}
                clip={clip}
                editHref={`/projects/${project.id}/clips/${clip.clip_id}`}
              />
            ))}
          </div>
        </section>
      )}

      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete project?"
        description="This permanently removes the uploaded source, transcript, and rendered Shorts."
      >
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmDelete(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} loading={deleting}>
            {deleting ? "Deleting..." : "Delete project"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
