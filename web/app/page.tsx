"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

import StatusBadge from "@/components/StatusBadge";
import UploadForm from "@/components/UploadForm";
import { apiFetch, formatSeconds, type Project } from "@/lib/api";

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
        .then((items) => active && setProjects(items))
        .catch((err: Error) => active && setError(err.message));
    load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [token]);

  if (!token) return <p className="text-neutral-400">Loading...</p>;

  return (
    <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
      <div className="space-y-4">
        <div>
          <h1 className="text-3xl font-black">Long video in, Shorts out.</h1>
          <p className="mt-2 text-neutral-400">
            Upload a talk, podcast, or interview. Snipzo finds the best moments and returns vertical
            1080×1920 Shorts with captions, a hook title, and metadata.
          </p>
        </div>
        <UploadForm token={token} />
      </div>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Your projects</h2>
        {error && <p className="text-sm text-red-400">{error}</p>}
        {projects === null ? (
          <p className="text-neutral-500">Loading projects...</p>
        ) : projects.length === 0 ? (
          <p className="card text-neutral-400">No projects yet. Upload a video to get started.</p>
        ) : (
          <ul className="space-y-3">
            {projects.map((project) => (
              <li key={project.id}>
                <Link
                  href={`/projects/${project.id}`}
                  className="card flex items-center justify-between gap-4 hover:border-neutral-600"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{project.title || project.source_filename}</p>
                    <p className="text-xs text-neutral-500">
                      {new Date(project.created_at).toLocaleString()} · {formatSeconds(project.duration_seconds)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {project.job && project.job.status === "running" && (
                      <span className="text-xs text-neutral-400">
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
