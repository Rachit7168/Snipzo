"use client";

import Link from "next/link";

import { useRouter } from "next/navigation";
import {
  useRef,
  useState,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { useToast } from "@/components/Toast";
import { Alert, Button, Card, Checkbox, Input, Tabs } from "@/components/ui";
import {
  formatBytes,
  UploadCancelledError,
  uploadProject,
  type UploadProgress,
} from "@/lib/api";
import { mapApiError } from "@/lib/errors";
import { checkSourceUrl } from "@/lib/youtubeUrl";

const SOURCE_TABS = [
  { id: "file" as const, label: "Upload" },
  { id: "url" as const, label: "Paste URL" },
];

const ALLOWED_EXTENSIONS = new Set([".mp4", ".mov", ".webm", ".mkv", ".m4v"]);

function validateVideoFile(file: File): string | null {
  const dot = file.name.lastIndexOf(".");
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return "Unsupported video type. Choose an MP4, MOV, WebM, MKV, or M4V file.";
  }
  if (file.size === 0) {
    return "This file is empty (0 bytes). Choose a valid video file.";
  }
  return null;
}

export default function UploadForm({ token }: { token: string }) {
  const router = useRouter();
  const { showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [mode, setMode] = useState<"file" | "url">("file");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [rights, setRights] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function pickFile(file: File | null) {
    if (!file) return;
    const err = validateVideoFile(file);
    if (err) {
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setFieldErrors((prev) => ({ ...prev, file: err }));
      return;
    }
    setSelectedFile(file);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.file;
      return next;
    });
  }

  function clearFile() {
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
    if (submitting) return;
    const dropped = event.dataTransfer.files?.[0] || null;
    pickFile(dropped);
  }

  function onDropZoneKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (submitting) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInputRef.current?.click();
    }
  }

  function cancelUpload() {
    abortRef.current?.abort();
  }

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
      const inputFile = source.get("file");
      const file =
        selectedFile || (inputFile instanceof File && inputFile.name ? inputFile : null);
      if (!file) {
        setFieldErrors({ file: "Drop a video file here or browse to choose one." });
        return;
      }
      const fileErr = validateVideoFile(file);
      if (fileErr) {
        setFieldErrors({ file: fileErr });
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

    const controller = new AbortController();
    abortRef.current = controller;
    setSubmitting(true);
    setUploadProgress(
      mode === "file" ? { loaded: 0, total: selectedFile?.size || 0, fraction: 0 } : null,
    );

    try {
      const project = await uploadProject(
        token,
        form,
        (next) => {
          if (mode === "file") setUploadProgress(next);
        },
        { signal: controller.signal },
      );
      router.push(`/projects/${project.id}`);
    } catch (err) {
      if (err instanceof UploadCancelledError) {
        showToast({ title: "Upload cancelled", message: "No project was created.", tone: "info" });
      } else {
        const mapped = mapApiError(err, "Upload failed.");
        if (mapped.fields && Object.keys(mapped.fields).length > 0) {
          setFieldErrors(mapped.fields);
        } else {
          setFormError(mapped.message);
          showToast({ title: mapped.title, message: mapped.message, tone: "error" });
        }
      }
      setSubmitting(false);
      setUploadProgress(null);
      abortRef.current = null;
    }
  }

  const pct = uploadProgress ? Math.round(uploadProgress.fraction * 100) : 0;

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
              if (submitting) return;
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
          disabled={submitting}
        />

        {mode === "file" ? (
          <div className="space-y-1.5">
            <label htmlFor="upload-file" className="block text-sm font-medium text-ink">
              Video file
            </label>
            <input
              ref={fileInputRef}
              id="upload-file"
              name="file"
              type="file"
              accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv,.m4v"
              disabled={submitting}
              onChange={(event) => pickFile(event.target.files?.[0] || null)}
              className="sr-only"
            />
            {selectedFile ? (
              <div
                className={`flex items-center justify-between gap-3 rounded-card border p-3.5 ${
                  fieldErrors.file ? "border-red-500/70 bg-red-500/5" : "border-line bg-surface-muted/70"
                }`}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-subtle text-brand-text">
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{selectedFile.name}</p>
                    <p className="text-xs text-ink-muted">{formatBytes(selectedFile.size)}</p>
                  </div>
                </div>
                {!submitting && (
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Change
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label="Remove selected file"
                      onClick={clearFile}
                    >
                      Remove
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <div
                role="button"
                tabIndex={0}
                aria-label="Upload video file. Drop a file here or press Enter to browse."
                aria-describedby={fieldErrors.file ? "upload-file-error" : "upload-file-hint"}
                onClick={() => !submitting && fileInputRef.current?.click()}
                onKeyDown={onDropZoneKeyDown}
                onDragEnter={(event) => {
                  event.preventDefault();
                  if (!submitting) setIsDragging(true);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  if (!submitting) setIsDragging(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setIsDragging(false);
                }}
                onDrop={onDrop}
                className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-card border border-dashed px-4 py-6 text-center transition ${
                  isDragging
                    ? "border-brand bg-brand-subtle/70"
                    : fieldErrors.file
                      ? "border-red-500/70 bg-red-500/5 hover:border-red-400"
                      : "border-line-strong bg-surface-muted/40 hover:border-brand/60 hover:bg-surface-muted/80"
                }`}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-elevated text-brand-text">
                  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0l-4 4m4-4l4 4M4 17v1a2 2 0 002 2h12a2 2 0 002-2v-1" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-ink">
                    {isDragging ? "Drop video to select" : "Drag & drop your video here"}
                  </p>
                  <p id="upload-file-hint" className="mt-0.5 text-xs text-ink-muted">
                    or <span className="font-semibold text-brand-text underline">browse files</span> · MP4, MOV, WebM, MKV
                  </p>
                </div>
              </div>
            )}
            {fieldErrors.file && (
              <p id="upload-file-error" role="alert" className="text-xs text-red-400">
                {fieldErrors.file}
              </p>
            )}
          </div>
        ) : (
          <Input
            id="upload-url"
            name="source_url"
            type="url"
            label="YouTube or direct video URL"
            placeholder="https://www.youtube.com/watch?v=… or a direct .mp4 link"
            disabled={submitting}
            error={fieldErrors.source_url}
            hint="Paste any YouTube video link (watch, Shorts, youtu.be, live replay, or embed) or a direct link to a video file. Playlists, channels, TikTok, and Instagram are not supported."
          />
        )}

        <Checkbox
          checked={rights}
          disabled={submitting}
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

        <p className="text-xs leading-relaxed text-ink-subtle">
          Upload recordings you filmed, podcasts or talks you host, or clips where you hold
          distribution rights.{" "}
          <Link href="/terms" className="font-medium text-ink-muted underline hover:text-ink">
            Terms
          </Link>{" "}
          ·{" "}
          <Link href="/takedown" className="font-medium text-ink-muted underline hover:text-ink">
            Copyright policy
          </Link>
        </p>

        {formError && <Alert tone="error">{formError}</Alert>}

        {submitting && (
          <div className="space-y-2 rounded-control border border-line bg-surface-muted/60 p-3" aria-live="polite">
            {mode === "file" && uploadProgress ? (
              <>
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-medium text-ink">
                    {pct < 100
                      ? `Uploading ${pct}%${
                          uploadProgress.total > 0
                            ? ` (${formatBytes(uploadProgress.loaded)} / ${formatBytes(uploadProgress.total)})`
                            : ""
                        }`
                      : "Upload received — starting pipeline..."}
                  </span>
                  {pct < 100 && (
                    <button
                      type="button"
                      onClick={cancelUpload}
                      className="font-semibold text-ink-muted underline hover:text-ink"
                    >
                      Cancel
                    </button>
                  )}
                </div>
                <div
                  role="progressbar"
                  aria-label="File upload progress"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  className="h-2 overflow-hidden rounded-full bg-surface"
                >
                  <div
                    className="h-full rounded-full bg-brand transition-all duration-150"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                {pct >= 100 && (
                  <p className="text-[11px] text-ink-subtle">
                    Opening project view — longer sources can take several minutes to process.
                  </p>
                )}
              </>
            ) : (
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="font-medium text-ink">
                  Checking link and starting pipeline...
                </span>
                <button
                  type="button"
                  onClick={cancelUpload}
                  className="font-semibold text-ink-muted underline hover:text-ink"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}

        <Button type="submit" fullWidth loading={submitting}>
          {submitting
            ? mode === "file" && pct < 100
              ? `Uploading ${pct}%...`
              : "Starting pipeline..."
            : "Make Shorts"}
        </Button>
      </form>
    </Card>
  );
}
