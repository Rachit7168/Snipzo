import { ApiError } from "./api";

export type MappedError = {
  title: string;
  message: string;
  fields?: Record<string, string>;
  isNetwork?: boolean;
  requestId?: string;
};

type PydanticIssue = {
  type?: string;
  loc?: Array<string | number>;
  msg?: string;
  ctx?: Record<string, unknown>;
};

const FIELD_LABELS: Record<string, string> = {
  email: "Email",
  password: "Password",
  name: "Name",
  title: "Title",
  hook_title: "Hook title",
  description: "Description",
  hashtags: "Hashtags",
  style_id: "Caption style",
  source_url: "Video URL",
  file: "Video file",
  rights_confirmed: "Rights confirmation",
  reporter_name: "Your name",
  reporter_email: "Your email",
  content_url: "Short URL",
  original_url: "Original work URL",
  details: "Details",
  good_faith: "Good-faith confirmation",
  channel_id: "Channel",
  clip_id: "Clip",
  publish_at: "Schedule time",
};

function labelFor(field: string): string {
  return (
    FIELD_LABELS[field] ||
    field
      .replace(/_/g, " ")
      .replace(/^\w/, (ch) => ch.toUpperCase())
  );
}

export function scrubSensitiveText(text: string): string {
  return text
    .replace(/\bSNIPZO_[A-Z0-9_]+\b/g, "server configuration")
    .replace(/(?:\/tmp\/|\/var\/|\/home\/|\/workspace\/|\/app\/)[^\s,;"']+/g, "the file")
    .replace(/\bfor project [a-f0-9]{8,}\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function formatPydanticIssue(field: string, issue: PydanticIssue): string {
  const label = labelFor(field);
  const type = issue.type || "";
  const ctx = issue.ctx || {};
  if (type === "string_too_short" && typeof ctx.min_length === "number") {
    return `${label} must be at least ${ctx.min_length} characters.`;
  }
  if (type === "string_too_long" && typeof ctx.max_length === "number") {
    return `${label} must be at most ${ctx.max_length} characters.`;
  }
  if (type === "missing" || type.endsWith(".missing")) {
    return `${label} is required.`;
  }
  if (type.includes("email") || (field.includes("email") && (issue.msg || "").toLowerCase().includes("email"))) {
    return `Enter a valid ${label.toLowerCase()}.`;
  }
  if (type.startsWith("greater_than")) {
    return `${label} is too small.`;
  }
  if (type.startsWith("less_than")) {
    return `${label} is too large.`;
  }
  let msg = (issue.msg || "Invalid value").replace(/^Value error,\s*/i, "");
  msg = msg.replace(/^String should /i, `${label} must `);
  msg = scrubSensitiveText(msg);
  if (!/[.!?]$/.test(msg)) msg += ".";
  return msg;
}

function isPydanticDetailArray(detail: unknown): detail is PydanticIssue[] {
  return (
    Array.isArray(detail) &&
    detail.length > 0 &&
    typeof detail[0] === "object" &&
    detail[0] !== null &&
    ("loc" in detail[0] || "msg" in detail[0])
  );
}

function defaultMessageForStatus(status: number): { title: string; message: string } {
  switch (status) {
    case 0:
      return {
        title: "Service unavailable",
        message: "Can't reach Snipzo right now. Please check your connection or try again in a moment.",
      };
    case 400:
    case 422:
      return { title: "Check your input", message: "Please check your input and try again." };
    case 401:
      return { title: "Sign in required", message: "Please sign in again to continue." };
    case 402:
      return { title: "Plan limit reached", message: "You've reached your plan's limit for this month." };
    case 403:
      return { title: "Not allowed", message: "You don't have permission to do that." };
    case 404:
      return { title: "Not found", message: "We couldn't find what you were looking for." };
    case 409:
      return { title: "Conflict", message: "That action conflicts with the current state." };
    case 413:
      return { title: "File too large", message: "That file is too large to upload." };
    case 415:
      return {
        title: "Unsupported format",
        message: "Upload an MP4, MOV, WebM, MKV, M4V, or AVI video.",
      };
    case 429:
      return { title: "Too many requests", message: "Please wait a moment and try again." };
    case 500:
    case 502:
    case 503:
    case 504:
      return {
        title: "Service error",
        message: "Something went wrong on our side. Please try again in a moment.",
      };
    default:
      return { title: "Request failed", message: "Something went wrong. Please try again." };
  }
}

export function mapApiError(
  err: unknown,
  fallbackMessage = "Something went wrong. Please try again.",
): MappedError {
  if (err instanceof ApiError) {
    if (err.status === 0) {
      return { ...defaultMessageForStatus(0), isNetwork: true };
    }
    if (isPydanticDetailArray(err.detail)) {
      const fields: Record<string, string> = {};
      for (const issue of err.detail) {
        const loc = Array.isArray(issue.loc) ? issue.loc : [];
        const fieldParts = loc.filter(
          (part): part is string =>
            typeof part === "string" && !["body", "query", "path"].includes(part),
        );
        const field = fieldParts[fieldParts.length - 1] || "_form";
        if (!fields[field]) {
          fields[field] = formatPydanticIssue(field, issue);
        }
      }
      const firstMessage = Object.values(fields)[0] || "Please fix the highlighted fields.";
      return {
        title: "Check your input",
        message: firstMessage,
        fields,
        requestId: err.requestId,
      };
    }

    const base = defaultMessageForStatus(err.status);
    if (err.status >= 500) {
      const safeDetail =
        typeof err.detail === "string" &&
        err.detail.trim() &&
        err.status === 503 &&
        !/internal server error|traceback/i.test(err.detail)
          ? scrubSensitiveText(err.detail)
          : base.message;
      return {
        title: base.title,
        message: safeDetail,
        requestId: err.requestId,
      };
    }

    if (typeof err.detail === "string" && err.detail.trim()) {
      const cleaned = scrubSensitiveText(err.detail);
      if (cleaned && !cleaned.startsWith("[{") && !cleaned.startsWith("{")) {
        return { title: base.title, message: cleaned, requestId: err.requestId };
      }
    }
    return { ...base, requestId: err.requestId };
  }

  if (err instanceof TypeError || (err instanceof Error && /failed to fetch|fetch failed|network|econnrefused|load failed/i.test(err.message))) {
    return { ...defaultMessageForStatus(0), isNetwork: true };
  }

  if (err instanceof Error) {
    const cleaned = scrubSensitiveText(err.message);
    if (cleaned && !cleaned.startsWith("[{") && !cleaned.startsWith("{")) {
      return { title: "Something went wrong", message: cleaned };
    }
  }

  return { title: "Something went wrong", message: fallbackMessage };
}

export function sanitizeJobErrorText(raw: string | null | undefined): string {
  if (!raw) {
    return "Processing failed unexpectedly. Try another file or contact support.";
  }
  const lower = raw.toLowerCase();
  if (lower.includes("ffprobe") || lower.includes("moov atom") || lower.includes("invalid data found")) {
    return "We couldn't read this video file. Please upload a valid MP4, MOV, WebM, or MKV file.";
  }
  if (lower.includes("no audio stream")) {
    return "This video has no audio track. Snipzo needs spoken audio to create Shorts.";
  }
  if (lower.includes("transcription produced no text") || lower.includes("no speech")) {
    return "We couldn't find enough spoken dialogue in this video to create Shorts. Try a video with clearer speech.";
  }
  if (lower.includes("ffmpeg")) {
    return "Rendering one of the clips failed. Try again or upload a different video.";
  }
  const cleaned = scrubSensitiveText(raw);
  return cleaned || "Processing failed unexpectedly. Try another file or contact support.";
}
