"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { Alert, Button, Card, Checkbox, Input, Tabs } from "@/components/ui";
import { uploadProject } from "@/lib/api";
import { mapApiError } from "@/lib/errors";
import { checkSourceUrl } from "@/lib/youtubeUrl";

const SOURCE_TABS = [
  { id: "file" as const, label: "Upload" },
  { id: "url" as const, label: "Paste URL" },
];

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
    <Card>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold tracking-tight text-ink">New project</h2>
          <Tabs
            label="Video source type"
            items={SOURCE_TABS}
            value={mode}
            onChange={(next) => {
              setMode(next);
              setFieldErrors({});
              setFormError(null);
            }}
          />
        </div>

        <Input
          id="upload-title"
          name="title"
          label="Title (optional)"
          placeholder="My podcast highlight"
        />

        {mode === "file" ? (
          <Input
            id="upload-file"
            name="file"
            type="file"
            label="Video file"
            accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv,.m4v"
            error={fieldErrors.file}
            className="file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-1 file:text-xs file:font-semibold file:text-brand-fg"
          />
        ) : (
          <Input
            id="upload-url"
            name="source_url"
            type="url"
            label="YouTube or direct video URL"
            placeholder="https://www.youtube.com/watch?v=… or a direct .mp4 link"
            error={fieldErrors.source_url}
            hint="Paste any YouTube video link (watch, Shorts, youtu.be, live replay, or embed) or a direct link to a video file. Playlists, channels, TikTok, and Instagram are not supported."
          />
        )}

        <Checkbox
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
          label="I own or have rights to this content."
          error={fieldErrors.rights_confirmed}
        />

        {formError && <Alert tone="error">{formError}</Alert>}

        {progress !== null && (
          <div className="space-y-1.5">
            <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
              <div
                className="h-full bg-brand transition-all"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
            <p className="text-xs text-ink-muted">
              {progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : "Uploaded. Starting the job..."}
            </p>
          </div>
        )}

        <Button type="submit" fullWidth loading={progress !== null}>
          {progress !== null ? "Uploading..." : "Make Shorts"}
        </Button>
      </form>
    </Card>
  );
}
