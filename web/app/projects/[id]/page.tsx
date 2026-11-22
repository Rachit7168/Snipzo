"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

import ClipCard from "@/components/ClipCard";
import PublishPanel from "@/components/PublishPanel";
import StatusBadge from "@/components/StatusBadge";
import { apiFetch, formatSeconds, STAGES, type Project } from "@/lib/api";

const DONE = new Set(["complete", "failed"]);

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { data: session } = useSession();
  const token = session?.accessToken;
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        if (active) setError(err instanceof Error ? err.message : "Could not load project.");
      }
    };
    load();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [token, id]);

  if (error) return <p className="text-red-400">{error}</p>;
  if (!project) return <p className="text-neutral-400">Loading project...</p>;

  const job = project.job;
  const stageIndex = job?.stage ? STAGES.indexOf(job.stage) : -1;
  const running = job && !["succeeded", "failed"].includes(job.status);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/" className="text-sm text-neutral-400 hover:text-white">
            ← Projects
          </Link>
          <h1 className="text-2xl font-bold">{project.title || project.source_filename}</h1>
          <p className="text-sm text-neutral-500">
            {project.source_filename} · {formatSeconds(project.duration_seconds)}
          </p>
        </div>
        <StatusBadge status={project.status} />
      </div>

      {job && (running || job.status === "failed") && (
        <section className="card space-y-3">
          <div className="flex justify-between text-sm">
            <span>{job.message || "Queued..."}</span>
            <span>{Math.round(job.progress * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-neutral-800">
            <div className="h-full bg-brand transition-all" style={{ width: `${Math.round(job.progress * 100)}%` }} />
          </div>
          <ol className="grid grid-cols-3 gap-2 text-xs sm:grid-cols-6">
            {STAGES.map((stage, index) => (
              <li
                key={stage}
                className={`rounded-md px-2 py-1 text-center ${
                  index < stageIndex || job.status === "succeeded"
                    ? "bg-emerald-500/15 text-emerald-300"
                    : index === stageIndex
                      ? "bg-yellow-500/15 text-yellow-300"
                      : "bg-neutral-800 text-neutral-500"
                }`}
              >
                {stage}
              </li>
            ))}
          </ol>
          {job.error && <p className="text-sm text-red-400">{job.error}</p>}
        </section>
      )}

      {project.clips.length > 0 && token && project.status === "complete" && (
        <PublishPanel projectId={project.id} clips={project.clips} token={token} />
      )}

      {project.clips.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{project.clips.length} Shorts</h2>
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
    </div>
  );
}
