import { Badge, Card } from "@/components/ui";
import { STAGES, type Job } from "@/lib/api";

const STAGE_META: Record<string, { label: string; detail: string }> = {
  ingest: {
    label: "Ingest",
    detail: "Validating video & extracting audio",
  },
  transcribe: {
    label: "Transcribe",
    detail: "Generating word-level timestamps",
  },
  pick: {
    label: "Find clips",
    detail: "Scoring & selecting highlight moments",
  },
  metadata: {
    label: "Titles & tags",
    detail: "Writing hooks, descriptions & hashtags",
  },
  reframe: {
    label: "Reframe",
    detail: "Tracking speakers for 9:16 crop",
  },
  render: {
    label: "Render",
    detail: "Burning captions & encoding vertical MP4s",
  },
};

export default function PipelineProgress({
  job,
  durationSeconds,
}: {
  job: Job;
  durationSeconds?: number | null;
}) {
  const stageIndex = job.stage ? STAGES.indexOf(job.stage) : -1;
  const pct = Math.max(
    job.status === "queued" ? 4 : 8,
    Math.min(100, Math.round(job.progress * 100)),
  );
  const currentMeta = job.stage ? STAGE_META[job.stage] : null;
  const statusHeadline =
    job.message || currentMeta?.detail || (job.status === "queued" ? "Queued for processing..." : "Processing...");

  const durationMinutes = durationSeconds ? durationSeconds / 60 : 0;
  const timeExpectation =
    durationMinutes >= 10
      ? "Longer videos can take several minutes to transcribe and render. You can leave this tab open or return from Projects anytime."
      : "This can take a couple of minutes depending on source length. You can keep this page open while clips render.";

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <Badge tone="brand">{job.status === "queued" ? "Queued" : "Processing"}</Badge>
          <span className="text-sm font-semibold text-ink" aria-live="polite">
            {statusHeadline}
          </span>
        </div>
        <span className="text-sm font-bold tabular-nums text-ink-muted">{pct}%</span>
      </div>

      <div
        role="progressbar"
        aria-label="Pipeline progress"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2.5 overflow-hidden rounded-full bg-surface-muted"
      >
        <div
          className="h-full rounded-full bg-brand transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3 lg:grid-cols-6">
        {STAGES.map((stage, index) => {
          const done = job.status === "succeeded" || (stageIndex > index && stageIndex !== -1);
          const current = stageIndex === index && job.status !== "succeeded";
          const meta = STAGE_META[stage] || { label: stage, detail: "" };
          return (
            <li
              key={stage}
              aria-current={current ? "step" : undefined}
              className={`flex items-center gap-2 rounded-control border px-2.5 py-2 font-medium transition ${
                done
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : current
                    ? "border-brand/50 bg-brand-subtle text-brand-text"
                    : "border-line bg-surface-muted/60 text-ink-subtle"
              }`}
            >
              {done ? (
                <svg
                  viewBox="0 0 16 16"
                  fill="currentColor"
                  aria-hidden="true"
                  className="h-3.5 w-3.5 shrink-0 text-emerald-400"
                >
                  <path
                    fillRule="evenodd"
                    d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : current ? (
                <span
                  className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-brand"
                  aria-hidden="true"
                />
              ) : (
                <span
                  className="h-2 w-2 shrink-0 rounded-full bg-ink-subtle/40"
                  aria-hidden="true"
                />
              )}
              <span className="truncate">{meta.label}</span>
            </li>
          );
        })}
      </ol>

      <p className="text-xs text-ink-subtle">{timeExpectation}</p>
    </Card>
  );
}
