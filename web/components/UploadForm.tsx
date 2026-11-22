"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { uploadProject } from "@/lib/api";
import { checkSourceUrl } from "@/lib/youtubeUrl";

export default function UploadForm({ token }: { token: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<"file" | "url">("file");
  const [rights, setRights] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const source = new FormData(event.currentTarget);
    const form = new FormData();
    form.set("rights_confirmed", rights ? "true" : "false");
    const title = String(source.get("title") || "").trim();
    if (title) form.set("title", title);
    if (mode === "file") {
      const file = source.get("file");
      if (!(file instanceof File) || !file.name) {
        setError("Choose a video file.");
        return;
      }
      form.set("file", file);
    } else {
      const pasted = String(source.get("source_url") || "");
      const check = checkSourceUrl(pasted);
      if (!check.ok) {
        setError(check.error);
        return;
      }
      form.set("source_url", pasted.trim());
    }
    setProgress(0);
    try {
      const project = await uploadProject(token, form, setProgress);
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setProgress(null);
    }
  }

  return (
    <form onSubmit={onSubmit} className="card space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">New project</h2>
        <div className="flex gap-1 rounded-lg bg-neutral-800 p-1 text-sm">
          {(["file", "url"] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setMode(item)}
              className={`rounded-md px-3 py-1 ${mode === item ? "bg-neutral-950 text-white" : "text-neutral-400"}`}
            >
              {item === "file" ? "Upload" : "Paste URL"}
            </button>
          ))}
        </div>
      </div>
      <input className="input" name="title" placeholder="Title (optional)" />
      {mode === "file" ? (
        <input
          className="input file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-1 file:font-semibold file:text-neutral-950"
          type="file"
          name="file"
          accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv,.m4v"
        />
      ) : (
        <div className="space-y-1">
          <input
            className="input"
            name="source_url"
            type="url"
            placeholder="https://www.youtube.com/watch?v=… or a direct .mp4 link"
          />
          <p className="text-xs text-neutral-500">
            Paste any YouTube video link (watch, Shorts, youtu.be, live replay, or embed) or a
            direct link to a video file. Playlists, channel pages, TikTok, and Instagram are not
            supported. You must own or have rights to the content.
          </p>
        </div>
      )}
      <label className="flex items-start gap-2 text-sm text-neutral-300">
        <input
          type="checkbox"
          className="mt-1 accent-yellow-400"
          checked={rights}
          onChange={(event) => setRights(event.target.checked)}
        />
        <span>I own or have rights to this content.</span>
      </label>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {progress !== null && (
        <div className="space-y-1">
          <div className="h-2 overflow-hidden rounded-full bg-neutral-800">
            <div className="h-full bg-brand transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
          <p className="text-xs text-neutral-400">
            {progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : "Uploaded. Starting the job..."}
          </p>
        </div>
      )}
      <button className="btn w-full" disabled={!rights || progress !== null}>
        Make Shorts
      </button>
    </form>
  );
}
