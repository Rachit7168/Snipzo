"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useToast } from "@/components/Toast";
import { Alert, Button, Card, Input, Select, Skeleton, Tabs, Textarea } from "@/components/ui";
import {
  apiFetch,
  formatSeconds,
  type CaptionLine,
  type ClipEditor as EditorData,
  type ClipEditResult,
} from "@/lib/api";
import { mapApiError, sanitizeJobErrorText } from "@/lib/errors";

const STYLE_PREVIEW: Record<string, { caption: string; hook: string }> = {
  "bold-yellow": {
    caption: "text-white text-2xl font-black [text-shadow:_0_0_6px_#000,_0_0_3px_#000]",
    hook: "bg-black/40 text-white text-xl font-black uppercase",
  },
  "clean-white": {
    caption: "text-white text-xl font-bold [text-shadow:_0_0_3px_#222]",
    hook: "text-white text-lg font-bold uppercase [text-shadow:_0_0_3px_#222]",
  },
};

const EDITOR_TABS = [
  { id: "trim" as const, label: "Trim" },
  { id: "details" as const, label: "Details" },
  { id: "captions" as const, label: "Captions" },
];

function round(value: number) {
  return Math.round(value * 10) / 10;
}

export default function ClipEditor({
  projectId,
  clipId,
  token,
}: {
  projectId: string;
  clipId: string;
  token: string;
}) {
  const { showToast } = useToast();
  const [data, setData] = useState<EditorData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<"trim" | "details" | "captions">("trim");
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [hookTitle, setHookTitle] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [styleId, setStyleId] = useState("bold-yellow");
  const [captions, setCaptions] = useState<CaptionLine[]>([]);
  const [captionsDirty, setCaptionsDirty] = useState(false);
  const [time, setTime] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  const load = useCallback(async () => {
    const editor = await apiFetch<EditorData>(
      `/projects/${projectId}/clips/${clipId}/editor`,
      token,
    );
    setData(editor);
    setStart(editor.clip.start);
    setEnd(editor.clip.end);
    setHookTitle(editor.clip.hook_title ?? "");
    setTitle(editor.clip.title ?? "");
    setDescription(editor.clip.description ?? "");
    setHashtags(editor.clip.hashtags.join(" "));
    setStyleId(editor.clip.style_id in STYLE_PREVIEW ? editor.clip.style_id : "bold-yellow");
    setCaptions(editor.captions);
    setCaptionsDirty(false);
    return editor;
  }, [projectId, clipId, token]);

  useEffect(() => {
    load().catch((err: unknown) =>
      setError(mapApiError(err, "Could not load clip editor.").message),
    );
  }, [load]);

  const trimmed = data
    ? Math.abs(start - data.clip.start) > 0.01 || Math.abs(end - data.clip.end) > 0.01
    : false;
  const relative = time - start;
  const activeCaption = useMemo(
    () => captions.find((line) => relative >= line.start && relative < line.end + 0.05),
    [captions, relative],
  );
  const preview = STYLE_PREVIEW[styleId] ?? STYLE_PREVIEW["bold-yellow"];

  function onTimeUpdate() {
    const video = videoRef.current;
    if (!video) return;
    if (video.currentTime >= end || video.currentTime < start - 0.5) {
      video.currentTime = start;
    }
    setTime(video.currentTime);
  }

  function seek(value: number) {
    if (videoRef.current) videoRef.current.currentTime = value;
    setTime(value);
  }

  async function pollJob(jobId: string) {
    for (let attempt = 0; attempt < 400; attempt += 1) {
      const editor = await apiFetch<EditorData>(
        `/projects/${projectId}/clips/${clipId}/editor`,
        token,
      );
      if (editor.job && editor.job.id === jobId && ["succeeded", "failed"].includes(editor.job.status)) {
        return editor.job;
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    return null;
  }

  async function save() {
    if (!data) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiFetch<ClipEditResult>(`/projects/${projectId}/clips/${clipId}`, token, {
        method: "PATCH",
        body: JSON.stringify({
          start: trimmed ? round(start) : undefined,
          end: trimmed ? round(end) : undefined,
          hook_title: hookTitle,
          title,
          description,
          hashtags: hashtags.split(/[\s,]+/).filter(Boolean),
          style_id: styleId,
          captions: captionsDirty && !trimmed ? captions : undefined,
          rerender: true,
        }),
      });
      let job = result.job;
      if (job && !["succeeded", "failed"].includes(job.status)) {
        setNotice("Re-rendering...");
        job = await pollJob(job.id);
      }
      if (job?.status === "failed") throw new Error(sanitizeJobErrorText(job.error));
      await load();
      const msg = result.trimmed
        ? "Saved. Trim changed, so captions were regenerated."
        : "Saved and re-rendered.";
      setNotice(msg);
      showToast({ title: "Clip updated", message: msg, tone: "success" });
    } catch (err) {
      const mapped = mapApiError(err, "Save failed.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
    } finally {
      setSaving(false);
    }
  }

  if (error && !data) {
    return (
      <Alert tone="error" title="Could not open editor">
        {error}
      </Alert>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading editor">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-44" />
          <Skeleton className="h-9 w-36" />
        </div>
        <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
          <Skeleton className="aspect-[9/16] w-full max-w-[340px] rounded-2xl" />
          <div className="space-y-4">
            <Skeleton className="h-36 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      </div>
    );
  }

  const duration = data.source_duration;
  const pct = (value: number) => `${(value / duration) * 100}%`;

  const trimCard = (
    <Card className="space-y-3">
      <h2 className="font-semibold text-ink">Trim</h2>
      <div className="relative h-8 rounded-md bg-surface-muted">
        <div
          className="absolute inset-y-0 rounded-md bg-brand/40 ring-2 ring-brand"
          style={{ left: pct(start), width: pct(Math.max(0, end - start)) }}
        />
        <div className="absolute inset-y-0 w-0.5 bg-white" style={{ left: pct(Math.min(time, duration)) }} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2 text-sm">
          <label htmlFor="trim-start" className="block text-ink-muted">
            Start {formatSeconds(start)}
          </label>
          <input
            id="trim-start"
            aria-label="Trim start"
            type="range"
            min={0}
            max={duration}
            step={0.1}
            value={start}
            onChange={(event) => {
              const value = Math.min(Number(event.target.value), end - 3);
              setStart(Math.max(0, value));
              seek(Math.max(0, value));
            }}
            className="w-full accent-brand"
          />
          <Button
            variant="ghost"
            size="sm"
            fullWidth
            onClick={() => setStart(round(Math.min(time, end - 3)))}
          >
            Set start to playhead
          </Button>
        </div>
        <div className="space-y-2 text-sm">
          <label htmlFor="trim-end" className="block text-ink-muted">
            End {formatSeconds(end)} · length {Math.round(end - start)}s
          </label>
          <input
            id="trim-end"
            aria-label="Trim end"
            type="range"
            min={0}
            max={duration}
            step={0.1}
            value={end}
            onChange={(event) => {
              const value = Math.max(Number(event.target.value), start + 3);
              setEnd(Math.min(duration, value));
              seek(Math.max(start, Math.min(duration, value) - 2));
            }}
            className="w-full accent-brand"
          />
          <Button
            variant="ghost"
            size="sm"
            fullWidth
            onClick={() => setEnd(round(Math.max(time, start + 3)))}
          >
            Set end to playhead
          </Button>
        </div>
      </div>
    </Card>
  );

  const detailsCard = (
    <Card className="space-y-3">
      <h2 className="font-semibold text-ink">Title and metadata</h2>
      <Input
        label="Hook title (burned in for the first seconds)"
        value={hookTitle}
        maxLength={120}
        onChange={(e) => setHookTitle(e.target.value)}
      />
      <Input
        label={`YouTube title (${title.length}/100)`}
        value={title}
        maxLength={100}
        onChange={(e) => setTitle(e.target.value)}
      />
      <Textarea
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <Input
        label="Hashtags (#Shorts is always included)"
        value={hashtags}
        onChange={(e) => setHashtags(e.target.value)}
      />
      <Select
        label="Caption style"
        value={styleId}
        onChange={(e) => setStyleId(e.target.value)}
      >
        {data.styles.map((style) => (
          <option key={style} value={style}>
            {style}
          </option>
        ))}
      </Select>
    </Card>
  );

  const captionsCard = (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-ink">Captions</h2>
        {trimmed && (
          <span className="text-xs text-amber-300">Trim changed: captions will be regenerated.</span>
        )}
      </div>
      <ol className="max-h-96 space-y-2 overflow-y-auto pr-1">
        {captions.map((line, index) => (
          <li key={`${line.start}-${index}`} className="flex items-center gap-2">
            <button
              type="button"
              className="w-20 shrink-0 text-left text-xs text-ink-subtle hover:text-ink"
              onClick={() => seek(start + line.start)}
            >
              {line.start.toFixed(1)}–{line.end.toFixed(1)}s
            </button>
            <input
              aria-label={`Caption ${index + 1}`}
              className="input py-1"
              value={line.text}
              disabled={trimmed}
              onChange={(event) => {
                const next = captions.slice();
                next[index] = { ...line, text: event.target.value };
                setCaptions(next);
                setCaptionsDirty(true);
              }}
            />
          </li>
        ))}
      </ol>
    </Card>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href={`/projects/${projectId}`} className="text-sm text-ink-muted hover:text-ink">
            ← Back to project
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Edit {data.clip.clip_id}</h1>
        </div>
        <Button onClick={save} loading={saving} disabled={!data.source_url}>
          {saving ? "Saving..." : "Save & re-render"}
        </Button>
      </div>

      {!data.source_url && (
        <Alert tone="warning">
          The source video was deleted after the retention window, so this clip can no longer be re-rendered.
        </Alert>
      )}
      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <section className="space-y-3 lg:sticky lg:top-20 lg:self-start">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
            Live preview
          </h2>
          <div className="relative mx-auto aspect-[9/16] w-full max-w-[260px] overflow-hidden rounded-2xl bg-black sm:max-w-[320px] lg:max-w-[340px]">
            {data.source_url && (
              <video
                ref={videoRef}
                src={`${data.source_url}#t=${start}`}
                className="h-full w-full object-cover"
                onTimeUpdate={onTimeUpdate}
                onLoadedMetadata={() => seek(start)}
                controls
                playsInline
              />
            )}
            {relative >= 0 && relative < 3 && hookTitle && (
              <div className={`pointer-events-none absolute inset-x-3 top-6 rounded-lg px-2 py-1 text-center ${preview.hook}`}>
                {hookTitle}
              </div>
            )}
            {activeCaption && (
              <div className={`pointer-events-none absolute inset-x-4 bottom-[22%] text-center ${preview.caption}`}>
                {activeCaption.text}
              </div>
            )}
          </div>
          <p className="text-center text-xs text-ink-subtle">
            Preview approximates the final framing; the render uses face tracking.
          </p>
          {data.clip.download_url && (
            <div className="hidden space-y-1 lg:block">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Current render (v{data.clip.render_version})
              </h2>
              <video
                key={data.clip.download_url}
                className="mx-auto aspect-[9/16] w-full max-w-[340px] rounded-2xl bg-black"
                src={data.clip.download_url}
                controls
                preload="metadata"
              />
            </div>
          )}
        </section>

        {/* Mobile tabbed controls */}
        <section className="space-y-4 lg:hidden">
          <Tabs
            label="Editor sections"
            items={EDITOR_TABS}
            value={mobileTab}
            onChange={setMobileTab}
            className="w-full justify-between"
          />
          {mobileTab === "trim" && trimCard}
          {mobileTab === "details" && detailsCard}
          {mobileTab === "captions" && captionsCard}
        </section>

        {/* Desktop stacked workspace */}
        <section className="hidden space-y-5 lg:block">
          {trimCard}
          {detailsCard}
          {captionsCard}
        </section>
      </div>
    </div>
  );
}
