"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { apiFetch, type Clip, type Publication, type YouTubeStatus } from "@/lib/api";
import { mapApiError, sanitizeJobErrorText } from "@/lib/errors";

export default function PublishPanel({
  projectId,
  clips,
  token,
}: {
  projectId: string;
  clips: Clip[];
  token: string;
}) {
  const { showToast } = useToast();
  const [status, setStatus] = useState<YouTubeStatus | null>(null);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [yt, pubs] = await Promise.all([
      apiFetch<YouTubeStatus>("/youtube/status", token),
      apiFetch<Publication[]>(`/projects/${projectId}/publications`, token),
    ]);
    setStatus(yt);
    setPublications(pubs);
    return pubs;
  }, [projectId, token]);

  useEffect(() => {
    load().catch((err: unknown) => setError(mapApiError(err, "Could not load publish status.").message));
  }, [load]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const schedule = String(form.get("publish_at") || "");
    try {
      await apiFetch(`/projects/${projectId}/clips/${form.get("clip_id")}/publish`, token, {
        method: "POST",
        body: JSON.stringify({
          channel_id: form.get("channel_id"),
          privacy_status: form.get("privacy_status"),
          publish_at: schedule ? new Date(schedule).toISOString() : null,
          contains_synthetic_media: form.get("synthetic") === "on",
          made_for_kids: form.get("kids") === "on",
          rights_confirmed: form.get("rights") === "on",
        }),
      });
      for (let i = 0; i < 60; i += 1) {
        const pubs = await load();
        if (!pubs.some((pub) => ["queued", "uploading"].includes(pub.status))) break;
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
      showToast({ title: "Publish updated", message: "Check the status below.", tone: "success" });
    } catch (err) {
      const mapped = mapApiError(err, "Publish failed.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
    } finally {
      setBusy(false);
    }
  }

  if (!status) return null;
  if (!status.configured) return null;
  if (status.channels.length === 0) {
    return (
      <p className="card text-sm text-neutral-400">
        <Link href="/channels" className="text-brand">
          Connect a YouTube channel
        </Link>{" "}
        to publish these Shorts directly.
      </p>
    );
  }

  return (
    <section className="card space-y-4">
      <h2 className="text-lg font-semibold">Publish to YouTube</h2>
      <form onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <select name="clip_id" aria-label="Clip" className="input">
          {clips.map((clip) => (
            <option key={clip.clip_id} value={clip.clip_id}>
              {clip.clip_id}: {clip.title || clip.hook_title}
            </option>
          ))}
        </select>
        <select name="channel_id" aria-label="Channel" className="input">
          {status.channels.map((channel) => (
            <option key={channel.id} value={channel.id}>
              {channel.title || channel.external_id}
            </option>
          ))}
        </select>
        <select name="privacy_status" aria-label="Visibility" className="input" defaultValue="private">
          <option value="private">Private</option>
          <option value="unlisted">Unlisted</option>
          <option value="public">Public</option>
        </select>
        <input name="publish_at" type="datetime-local" className="input" aria-label="Schedule (optional)" />
        <label className="flex items-center gap-2 text-sm text-neutral-300 sm:col-span-2">
          <input type="checkbox" name="synthetic" className="accent-yellow-400" />
          Contains realistic altered or synthetic content (YouTube disclosure)
        </label>
        <label className="flex items-center gap-2 text-sm text-neutral-300">
          <input type="checkbox" name="kids" className="accent-yellow-400" />
          Made for kids
        </label>
        <label className="flex items-center gap-2 text-sm text-neutral-300">
          <input type="checkbox" name="rights" className="accent-yellow-400" required />
          I own or have rights to publish this
        </label>
        <button className="btn sm:col-span-2 lg:col-span-4" disabled={busy}>
          {busy ? "Publishing..." : "Publish"}
        </button>
      </form>
      {error && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}
      {publications.length > 0 && (
        <ul className="space-y-1 text-sm">
          {publications.map((pub) => (
            <li key={pub.id} className="flex flex-wrap gap-2 text-neutral-300">
              <span className="font-medium">{pub.clip_id}</span>
              <span>{pub.status}</span>
              {pub.publish_at && <span>· scheduled {new Date(pub.publish_at).toLocaleString()}</span>}
              {pub.url && (
                <a className="text-brand" href={pub.url} target="_blank" rel="noreferrer">
                  {pub.url}
                </a>
              )}
              {pub.error && <span className="text-red-400">{sanitizeJobErrorText(pub.error)}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
