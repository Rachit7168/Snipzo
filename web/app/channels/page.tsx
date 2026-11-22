"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { useToast } from "@/components/Toast";
import { apiFetch, type OwnedVideo, type YouTubeStatus } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

export default function ChannelsPage() {
  const router = useRouter();
  const { data: session } = useSession();
  const { showToast } = useToast();
  const token = session?.accessToken;
  const [status, setStatus] = useState<YouTubeStatus | null>(null);
  const [videos, setVideos] = useState<Record<string, OwnedVideo[]>>({});
  const [rights, setRights] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    const data = await apiFetch<YouTubeStatus>("/youtube/status", token);
    setStatus(data);
    for (const channel of data.channels) {
      apiFetch<OwnedVideo[]>(`/youtube/channels/${channel.id}/videos`, token)
        .then((items) => setVideos((prev) => ({ ...prev, [channel.id]: items })))
        .catch((err: unknown) => {
          const mapped = mapApiError(err, "Could not load channel videos.");
          setError(mapped.message);
        });
    }
  }, [token]);

  useEffect(() => {
    load().catch((err: unknown) => {
      const mapped = mapApiError(err, "Could not load channels.");
      setError(mapped.message);
    });
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected")) setMessage("YouTube channel connected.");
    if (params.get("error")) setError("Google sign-in was cancelled or could not be completed.");
  }, [load]);

  async function connect() {
    try {
      const { auth_url } = await apiFetch<{ auth_url: string }>("/youtube/connect", token);
      window.location.assign(auth_url);
    } catch (err) {
      const mapped = mapApiError(err, "Could not start Google sign-in.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
    }
  }

  async function disconnect(channelId: string) {
    try {
      await apiFetch(`/youtube/channels/${channelId}`, token, { method: "DELETE" });
      await load();
      showToast({ title: "Channel disconnected", message: "Removed your YouTube channel.", tone: "success" });
    } catch (err) {
      const mapped = mapApiError(err, "Could not disconnect channel.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
    }
  }

  async function importVideo(channelId: string, videoId: string) {
    setError(null);
    try {
      const result = await apiFetch<{ project_id: string }>(
        `/youtube/channels/${channelId}/import`,
        token,
        { method: "POST", body: JSON.stringify({ video_id: videoId, rights_confirmed: rights }) },
      );
      router.push(`/projects/${result.project_id}`);
    } catch (err) {
      const mapped = mapApiError(err, "Import failed.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
    }
  }

  if (!token || !status) return <p className="text-neutral-400">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Channels</h1>
          <p className="text-sm text-neutral-400">
            Connect your YouTube channel to publish Shorts directly and import videos you own.
          </p>
        </div>
        {status.configured && (
          <button className="btn" onClick={connect}>
            Connect YouTube
          </button>
        )}
      </div>
      {!status.configured && (
        <p className="card text-sm text-neutral-300">
          YouTube publishing is not available yet. You can still paste any YouTube video link on the dashboard to make Shorts.
        </p>
      )}
      {message && <p className="text-sm text-emerald-300">{message}</p>}
      {error && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}
      {status.channels.length === 0 ? (
        <p className="card text-neutral-400">No channels connected yet.</p>
      ) : (
        status.channels.map((channel) => (
          <section key={channel.id} className="card space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold">{channel.title || channel.external_id}</h2>
                <p className="text-xs text-neutral-500">YouTube · {channel.external_id}</p>
              </div>
              <button className="btn-ghost py-1 text-sm" onClick={() => disconnect(channel.id)}>
                Disconnect
              </button>
            </div>
            <label className="flex items-center gap-2 text-sm text-neutral-300">
              <input type="checkbox" className="accent-yellow-400" checked={rights} onChange={(e) => setRights(e.target.checked)} />
              I own or have rights to this content.
            </label>
            {!status.import_enabled && (
              <p className="text-xs text-neutral-500">
                Channel import isn&apos;t available right now. Upload the original file instead.
              </p>
            )}
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(videos[channel.id] ?? []).map((video) => (
                <li key={video.id} className="rounded-xl border border-neutral-800 p-3">
                  <p className="line-clamp-2 text-sm font-medium">{video.title}</p>
                  <button
                    className="btn mt-2 w-full py-1 text-sm"
                    disabled={!rights}
                    onClick={() => importVideo(channel.id, video.id)}
                  >
                    Import
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
