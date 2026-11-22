"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { useToast } from "@/components/Toast";
import {
  Alert,
  Button,
  Card,
  CardGridSkeleton,
  Checkbox,
  EmptyState,
  Skeleton,
} from "@/components/ui";
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

  if (!token || !status) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading channels">
        <Skeleton className="h-8 w-40" />
        <CardGridSkeleton count={2} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Channels</h1>
          <p className="text-sm text-ink-muted">
            Connect your YouTube channel to publish Shorts directly and import videos you own.
          </p>
        </div>
        {status.configured && <Button onClick={connect}>Connect YouTube</Button>}
      </div>

      {!status.configured && (
        <Alert tone="info">
          YouTube publishing is not available yet. You can still paste any YouTube video link on the dashboard to make Shorts.
        </Alert>
      )}
      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      {status.channels.length === 0 ? (
        <EmptyState
          title="No channels connected yet"
          description={
            status.configured
              ? "Connect your YouTube channel to import owned videos and publish Shorts in one click."
              : "Direct YouTube publishing will appear here once channel connections are enabled."
          }
          action={status.configured ? <Button onClick={connect}>Connect YouTube</Button> : undefined}
        />
      ) : (
        status.channels.map((channel) => (
          <Card key={channel.id} className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-ink">{channel.title || channel.external_id}</h2>
                <p className="text-xs text-ink-subtle">YouTube · {channel.external_id}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => disconnect(channel.id)}>
                Disconnect
              </Button>
            </div>
            <Checkbox
              checked={rights}
              onChange={(e) => setRights(e.target.checked)}
              label="I own or have rights to this content."
            />
            {!status.import_enabled && (
              <p className="text-xs text-ink-subtle">
                Channel import isn&apos;t available right now. Upload the original file instead.
              </p>
            )}
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(videos[channel.id] ?? []).map((video) => (
                <li key={video.id} className="flex flex-col justify-between gap-3 rounded-xl border border-line p-3">
                  <p className="line-clamp-2 text-sm font-medium text-ink">{video.title}</p>
                  <Button
                    size="sm"
                    fullWidth
                    disabled={!rights}
                    onClick={() => importVideo(channel.id, video.id)}
                  >
                    Import
                  </Button>
                </li>
              ))}
            </ul>
          </Card>
        ))
      )}
    </div>
  );
}
