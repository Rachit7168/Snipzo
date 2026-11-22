const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;

function rootHost(host: string): string {
  const lowered = host.toLowerCase().split(":")[0] ?? "";
  return lowered.startsWith("www.") ? lowered.slice(4) : lowered;
}

function isYoutubeHost(host: string): boolean {
  const root = rootHost(host);
  return (
    root === "youtube.com" ||
    root === "youtu.be" ||
    root === "youtube-nocookie.com" ||
    root.endsWith(".youtube.com") ||
    root.endsWith(".youtube-nocookie.com")
  );
}

function isBlockedSocial(host: string): boolean {
  const root = rootHost(host);
  return (
    root === "tiktok.com" ||
    root === "instagram.com" ||
    root.endsWith(".tiktok.com") ||
    root.endsWith(".instagram.com")
  );
}

export type SourceUrlCheck =
  | { ok: true; kind: "youtube"; id: string }
  | { ok: true; kind: "file" }
  | { ok: false; error: string };

export function checkSourceUrl(raw: string): SourceUrlCheck {
  const value = raw.trim();
  if (!value) {
    return { ok: false, error: "Paste a YouTube link or a direct link to a video file." };
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return { ok: false, error: "Source URL must be an http(s) link." };
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return { ok: false, error: "Source URL must be an http(s) link." };
  }
  if (isBlockedSocial(parsed.hostname)) {
    return {
      ok: false,
      error:
        "TikTok and Instagram links aren't supported yet. Upload the file, or paste a YouTube or direct video link.",
    };
  }
  if (!isYoutubeHost(parsed.hostname)) {
    return { ok: true, kind: "file" };
  }

  const path = decodeURIComponent(parsed.pathname).replace(/\/$/, "");
  const parts = path.split("/").filter(Boolean);
  const root = rootHost(parsed.hostname);

  if (root === "youtu.be") {
    const id = parts[0] ?? "";
    if (VIDEO_ID.test(id)) return { ok: true, kind: "youtube", id };
    return { ok: false, error: "That YouTube link is missing a video id." };
  }

  if (path === "/watch" || parts[0] === "watch") {
    const id = parsed.searchParams.get("v") ?? (parts[1] ?? "");
    if (VIDEO_ID.test(id)) return { ok: true, kind: "youtube", id };
    if (parsed.searchParams.get("list")) {
      return { ok: false, error: "Paste a link to a single video, not a playlist." };
    }
    return { ok: false, error: "That YouTube link is missing a video id." };
  }

  if (parts[0] === "playlist") {
    return { ok: false, error: "Paste a link to a single video, not a playlist." };
  }

  if (parts.length >= 2 && ["shorts", "live", "embed", "v", "e"].includes(parts[0] ?? "")) {
    const id = (parts[1] ?? "").split("?")[0] ?? "";
    if (VIDEO_ID.test(id)) return { ok: true, kind: "youtube", id };
    return { ok: false, error: "That YouTube link is missing a video id." };
  }

  const first = parts[0] ?? "";
  if (["channel", "c", "user", "feed", "results", "hashtag"].includes(first) || first.startsWith("@")) {
    return {
      ok: false,
      error: "Paste a link to a single YouTube video, not a channel or playlist.",
    };
  }

  return {
    ok: false,
    error: "Paste a link to a single YouTube video (watch, Shorts, youtu.be, or embed).",
  };
}
