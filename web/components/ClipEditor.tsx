"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useToast } from "@/components/Toast";
import { mapApiError, sanitizeJobErrorText } from "@/lib/errors";
import {
  apiFetch,
  formatSeconds,
  type CaptionLine,
  type ClipEditor as EditorData,
  type ClipEditResult,
} from "@/lib/api";

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
    load().catch((err: unknown) => setError(mapApiError(err, "Could not load clip editor.").message));
  }, [load]);

  const trimmed = data ? Math.abs(start - data.clip.start) > 0.01 || Math.abs(end - data.clip.end) > 0.01 : false;
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
      setNotice(result.trimmed ? "Saved. Trim changed, so captions were regenerated." : "Saved and re-rendered.");
    } catch (err) {
      const mapped = mapApiError(err, "Save failed.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
    } finally {
      setSaving(false);
    }
  }

  if (error && !data) return <p className="text-red-400">{error}</p>;
  if (!data) return <p className="text-neutral-400">Loading editor...</p>;

  const duration = data.source_duration;
  const pct = (value: number) => `${(value / duration) * 100}%`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href={`/projects/${projectId}`} className="text-sm text-neutral-400 hover:text-white">
            ← Back to project
          </Link>
          <h1 className="text-2xl font-bold">Edit {data.clip.clip_id}</h1>
        </div>
        <button className="btn" onClick={save} disabled={saving || !data.source_url}>
          {saving ? "Saving..." : "Save & re-render"}
        </button>
      </div>
      {!data.source_url && (
        <p className="card text-sm text-yellow-300">
          The source video was deleted after the retention window, so this clip can no longer be re-rendered.
        </p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {notice && <p className="text-sm text-emerald-300">{notice}</p>}

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">Live preview</h2>
          <div className="relative mx-auto aspect-[9/16] w-full max-w-[340px] overflow-hidden rounded-2xl bg-black">
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
          <p className="text-center text-xs text-neutral-500">
            Preview approximates the final framing; the render uses face tracking.
          </p>
          {data.clip.download_url && (
            <div className="space-y-1">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">
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

        <section className="space-y-5">
          <div className="card space-y-3">
            <h2 className="font-semibold">Trim</h2>
            <div className="relative h-8 rounded-md bg-neutral-800">
              <div
                className="absolute inset-y-0 rounded-md bg-brand/40 ring-2 ring-brand"
                style={{ left: pct(start), width: pct(Math.max(0, end - start)) }}
              />
              <div className="absolute inset-y-0 w-0.5 bg-white" style={{ left: pct(Math.min(time, duration)) }} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="text-neutral-400">Start {formatSeconds(start)}</span>
                <input
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
                  className="w-full accent-yellow-400"
                />
                <button type="button" className="btn-ghost w-full py-1 text-xs" onClick={() => setStart(round(Math.min(time, end - 3)))}>
                  Set start to playhead
                </button>
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-neutral-400">End {formatSeconds(end)} · length {Math.round(end - start)}s</span>
                <input
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
                  className="w-full accent-yellow-400"
                />
                <button type="button" className="btn-ghost w-full py-1 text-xs" onClick={() => setEnd(round(Math.max(time, start + 3)))}>
                  Set end to playhead
                </button>
              </label>
            </div>
          </div>

          <div className="card space-y-3">
            <h2 className="font-semibold">Title and metadata</h2>
            <label className="block space-y-1 text-sm">
              <span className="text-neutral-400">Hook title (burned in for the first seconds)</span>
              <input className="input" value={hookTitle} maxLength={120} onChange={(e) => setHookTitle(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-neutral-400">YouTube title ({title.length}/100)</span>
              <input className="input" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-neutral-400">Description</span>
              <textarea className="input min-h-24" value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-neutral-400">Hashtags (#Shorts is always included)</span>
              <input className="input" value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-neutral-400">Caption style</span>
              <select className="input" value={styleId} onChange={(e) => setStyleId(e.target.value)}>
                {data.styles.map((style) => (
                  <option key={style} value={style}>
                    {style}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="card space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Captions</h2>
              {trimmed && <span className="text-xs text-yellow-300">Trim changed: captions will be regenerated.</span>}
            </div>
            <ol className="max-h-96 space-y-2 overflow-y-auto pr-1">
              {captions.map((line, index) => (
                <li key={`${line.start}-${index}`} className="flex items-center gap-2">
                  <button
                    type="button"
                    className="w-20 shrink-0 text-left text-xs text-neutral-500 hover:text-white"
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
          </div>
        </section>
      </div>
    </div>
  );
}
