export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Job = {
  id: string;
  kind: string;
  status: string;
  stage: string | null;
  progress: number;
  message: string | null;
  error: string | null;
};

export type Clip = {
  clip_id: string;
  rank: number;
  start: number;
  end: number;
  duration: number;
  score: number;
  reason: string;
  hook_title: string | null;
  title: string | null;
  description: string | null;
  hashtags: string[];
  style_id: string;
  render_version: number | null;
  download_url: string | null;
};

export type Project = {
  id: string;
  title: string | null;
  status: string;
  source_kind: string;
  source_filename: string | null;
  source_title: string | null;
  source_thumbnail_url: string | null;
  source_page_url: string | null;
  duration_seconds: number | null;
  rights_confirmed: boolean;
  source_available: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
  job: Job | null;
  clips: Clip[];
};

export class ApiError extends Error {
  status: number;
  detail: unknown;
  requestId?: string;
  constructor(status: number, message: string, detail?: unknown, requestId?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.requestId = requestId;
  }
}

export async function apiFetch<T>(
  path: string,
  token: string | undefined,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("content-type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Service unavailable");
  }
  if (!response.ok) {
    let rawDetail: unknown = undefined;
    let requestId: string | undefined = response.headers.get("x-request-id") || undefined;
    let message = response.statusText || "Request failed";
    try {
      const body = (await response.json()) as { detail?: unknown; request_id?: string };
      rawDetail = body?.detail;
      if (body?.request_id) requestId = body.request_id;
      if (typeof body?.detail === "string" && body.detail.trim()) {
        message = body.detail;
      }
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, message, rawDetail, requestId);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type UploadProgress = {
  loaded: number;
  total: number;
  fraction: number;
};

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value >= 10 || idx === 0 ? Math.round(value) : value.toFixed(1)} ${units[idx]}`;
}

export class UploadCancelledError extends Error {
  constructor() {
    super("Upload cancelled.");
    this.name = "UploadCancelledError";
  }
}

/** Upload with byte-level progress reporting and cancellation support. */
export function uploadProject(
  token: string,
  form: FormData,
  onProgress: (progress: UploadProgress) => void,
  options?: { signal?: AbortSignal },
): Promise<Project> {
  return new Promise((resolve, reject) => {
    if (options?.signal?.aborted) {
      reject(new UploadCancelledError());
      return;
    }
    const xhr = new XMLHttpRequest();
    const cleanupAbort = () => {
      if (options?.signal) options.signal.removeEventListener("abort", onAbort);
    };
    const onAbort = () => {
      xhr.abort();
    };
    if (options?.signal) {
      options.signal.addEventListener("abort", onAbort, { once: true });
    }
    xhr.open("POST", `${API_URL}/projects`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress({
          loaded: event.loaded,
          total: event.total,
          fraction: Math.min(1, event.loaded / event.total),
        });
      }
    };
    xhr.onload = () => {
      cleanupAbort();
      let body: { detail?: unknown; request_id?: string } | null = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // ignore
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as unknown as Project);
      } else {
        const detail = body?.detail;
        const message =
          typeof detail === "string" && detail.trim() ? detail : xhr.statusText || "Upload failed";
        reject(new ApiError(xhr.status, message, detail, body?.request_id));
      }
    };
    xhr.onerror = () => {
      cleanupAbort();
      reject(new ApiError(0, "Service unavailable"));
    };
    xhr.onabort = () => {
      cleanupAbort();
      reject(new UploadCancelledError());
    };
    xhr.send(form);
  });
}

export const STAGES = ["ingest", "transcribe", "pick", "metadata", "reframe", "render"];

export function formatSeconds(value: number | null | undefined): string {
  if (value == null) return "–";
  const total = Math.round(value);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export type CaptionLine = { start: number; end: number; text: string };

export type ClipEditor = {
  project_id: string;
  clip: Clip;
  captions: CaptionLine[];
  captions_edited: boolean;
  styles: string[];
  source_duration: number;
  source_url: string | null;
  job: Job | null;
};

export type ClipEditResult = { clip: Clip; trimmed: boolean; job: Job | null };

export type Channel = {
  id: string;
  provider: string;
  external_id: string;
  title: string | null;
  connected_at: string;
};

export type YouTubeStatus = { configured: boolean; import_enabled: boolean; channels: Channel[] };

export type OwnedVideo = {
  id: string;
  title: string;
  published_at: string | null;
  thumbnail: string | null;
};

export type Publication = {
  id: string;
  clip_id: string;
  channel_id: string;
  status: string;
  external_id: string | null;
  url: string | null;
  privacy_status: string;
  publish_at: string | null;
  contains_synthetic_media: boolean;
  error: string | null;
  created_at: string;
};

export type PlanInfo = {
  id: string;
  name: string;
  price_usd: number;
  videos_per_month: number;
  minutes_per_month: number;
  max_resolution: string;
  watermark: boolean;
  features: string[];
  purchasable: boolean;
};

export type BillingUsage = {
  plan: PlanInfo;
  videos_used: number;
  minutes_used: number;
  period_start: string;
  billing_configured: boolean;
  has_subscription: boolean;
};
