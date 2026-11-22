"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { uploadProject } from "@/lib/api";
import { mapApiError } from "@/lib/errors";
import { checkSourceUrl } from "@/lib/youtubeUrl";

export default function UploadForm({ token }: { token: string }) {
  const router = useRouter();
  const { showToast } = useToast();
  const [mode, setMode] = useState<"file" | "url">("file");
  const [rights, setRights] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});

    const source = new FormData(event.currentTarget);
    const form = new FormData();
    form.set("rights_confirmed", rights ? "true" : "false");
    const title = String(source.get("title") || "").trim();
    if (title) form.set("title", title);

    if (!rights) {
      setFieldErrors({ rights_confirmed: "Confirm that you own or have rights to this content." });
      return;
    }

    if (mode === "file") {
      const file = source.get("file");
      if (!(file instanceof File) || !file.name) {
        setFieldErrors({ file: "Choose a video file to upload." });
        return;
      }
      form.set("file", file);
    } else {
      const pasted = String(source.get("source_url") || "");
      const check = checkSourceUrl(pasted);
      if (!check.ok) {
        setFieldErrors({ source_url: check.error });
        return;
      }
      form.set("source_url", pasted.trim());
    }

    setProgress(0);
    try {
      const project = await uploadProject(token, form, setProgress);
      router.push(`/projects/${project.id}`);
    } catch (err) {
      const mapped = mapApiError(err, "Upload failed.");
      if (mapped.fields && Object.keys(mapped.fields).length > 0) {
        setFieldErrors(mapped.fields);
      } else {
        setFormError(mapped.message);
        showToast({ title: mapped.title, message: mapped.message, tone: "error" });
      }
      setProgress(null);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">New project</h2>
        <div className="flex gap-1 rounded-lg bg-neutral-800 p-1 text-sm">
          {(["file", "url"] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                setMode(item);
                setFieldErrors({});
                setFormError(null);
              }}
              className={`rounded-md px-3 py-1 ${mode === item ? "bg-neutral-950 text-white" : "text-neutral-400"}`}
            >
              {item === "file" ? "Upload" : "Paste URL"}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-1">
        <label htmlFor="upload-title" className="block text-xs font-medium text-neutral-300">
          Title (optional)
        </label>
        <input id="upload-title" className="input" name="title" placeholder="My podcast highlight" />
      </div>

      {mode === "file" ? (
        <div className="space-y-1">
          <label htmlFor="upload-file" className="block text-xs font-medium text-neutral-300">
            Video file
          </label>
          <input
            id="upload-file"
            className="input file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-1 file:font-semibold file:text-neutral-950"
            type="file"
            name="file"
            accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv,.m4v"
            aria-invalid={Boolean(fieldErrors.file)}
            aria-describedby={fieldErrors.file ? "upload-file-error" : undefined}
          />
          {fieldErrors.file && (
            <p id="upload-file-error" className="text-xs text-red-400">
              {fieldErrors.file}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          <label htmlFor="upload-url" className="block text-xs font-medium text-neutral-300">
            YouTube or direct video URL
          </label>
          <input
            id="upload-url"
            className="input"
            name="source_url"
            type="url"
            placeholder="https://www.youtube.com/watch?v=… or a direct .mp4 link"
            aria-invalid={Boolean(fieldErrors.source_url)}
            aria-describedby={fieldErrors.source_url ? "upload-url-error" : undefined}
          />
          {fieldErrors.source_url && (
            <p id="upload-url-error" className="text-xs text-red-400">
              {fieldErrors.source_url}
            </p>
          )}
          <p className="text-xs text-neutral-500">
            Paste any YouTube video link (watch, Shorts, youtu.be, live replay, or embed) or a
            direct link to a video file. Playlists, channel pages, TikTok, and Instagram are not
            supported. You must own or have rights to the content.
          </p>
        </div>
      )}

      <div className="space-y-1">
        <label className="flex items-start gap-2 text-sm text-neutral-300">
          <input
            type="checkbox"
            className="mt-1 accent-yellow-400"
            checked={rights}
            onChange={(event) => {
              setRights(event.target.checked);
              if (event.target.checked) {
                setFieldErrors((prev) => {
                  const next = { ...prev };
                  delete next.rights_confirmed;
                  return next;
                });
              }
            }}
            aria-invalid={Boolean(fieldErrors.rights_confirmed)}
          />
          <span>I own or have rights to this content.</span>
        </label>
        {fieldErrors.rights_confirmed && (
          <p className="text-xs text-red-400">{fieldErrors.rights_confirmed}</p>
        )}
      </div>

      {formError && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {formError}
        </div>
      )}

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
      <button className="btn w-full" disabled={progress !== null}>
        Make Shorts
      </button>
    </form>
  );
}
