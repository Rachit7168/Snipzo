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
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
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
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Upload with progress reporting (fetch has no upload progress events). */
export function uploadProject(
  token: string,
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<Project> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/projects`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // ignore
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as Project);
      } else {
        const detail = (body as { detail?: unknown } | null)?.detail;
        reject(new ApiError(xhr.status, typeof detail === "string" ? detail : xhr.statusText));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error: is the API running?"));
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
