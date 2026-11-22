import Link from "next/link";

import { Badge, buttonClasses, Card } from "@/components/ui";
import type { Clip } from "@/lib/api";
import { formatSeconds } from "@/lib/api";

export default function ClipCard({ clip, editHref }: { clip: Clip; editHref?: string }) {
  return (
    <Card className="flex flex-col gap-3">
      {clip.download_url ? (
        <video
          className="aspect-[9/16] w-full rounded-xl bg-black object-contain"
          src={clip.download_url}
          controls
          preload="metadata"
          playsInline
        />
      ) : (
        <div className="flex aspect-[9/16] items-center justify-center rounded-xl bg-surface-muted text-sm text-ink-subtle">
          Rendering...
        </div>
      )}
      <div className="flex items-center justify-between gap-2 text-xs text-ink-muted">
        <span>
          #{clip.rank} · {formatSeconds(clip.start)}–{formatSeconds(clip.end)} ({Math.round(clip.duration)}s)
        </span>
        <Badge tone="brand">score {clip.score.toFixed(2)}</Badge>
      </div>
      <h3 className="font-semibold leading-snug text-ink">{clip.title || clip.hook_title}</h3>
      <p className="text-sm text-ink-muted">
        <span className="font-medium text-ink">Why: </span>
        {clip.reason}
      </p>
      {clip.hashtags.length > 0 && (
        <p className="text-xs text-sky-400">{clip.hashtags.join(" ")}</p>
      )}
      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        {clip.download_url && (
          <a
            className={buttonClasses({ variant: "primary", size: "md", className: "flex-1" })}
            href={clip.download_url}
            download={`${clip.clip_id}.mp4`}
          >
            Download MP4
          </a>
        )}
        {editHref && (
          <Link className={buttonClasses({ variant: "ghost", size: "md" })} href={editHref}>
            Edit
          </Link>
        )}
      </div>
    </Card>
  );
}
