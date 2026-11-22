import Link from "next/link";

import type { Clip } from "@/lib/api";
import { formatSeconds } from "@/lib/api";

export default function ClipCard({ clip, editHref }: { clip: Clip; editHref?: string }) {
  return (
    <article className="card flex flex-col gap-3">
      {clip.download_url ? (
        <video
          className="aspect-[9/16] w-full rounded-xl bg-black object-contain"
          src={clip.download_url}
          controls
          preload="metadata"
          playsInline
        />
      ) : (
        <div className="flex aspect-[9/16] items-center justify-center rounded-xl bg-neutral-800 text-neutral-500">
          Rendering...
        </div>
      )}
      <div className="flex items-center justify-between text-xs text-neutral-400">
        <span>
          #{clip.rank} · {formatSeconds(clip.start)}–{formatSeconds(clip.end)} ({Math.round(clip.duration)}s)
        </span>
        <span className="rounded-full bg-brand/15 px-2 py-0.5 font-semibold text-brand">
          score {clip.score.toFixed(2)}
        </span>
      </div>
      <h3 className="font-semibold leading-snug">{clip.title || clip.hook_title}</h3>
      <p className="text-sm text-neutral-400">
        <span className="font-medium text-neutral-300">Why: </span>
        {clip.reason}
      </p>
      {clip.hashtags.length > 0 && (
        <p className="text-xs text-sky-300">{clip.hashtags.join(" ")}</p>
      )}
      <div className="mt-auto flex gap-2">
        {clip.download_url && (
          <a className="btn flex-1" href={clip.download_url} download={`${clip.clip_id}.mp4`}>
            Download MP4
          </a>
        )}
        {editHref && (
          <Link className="btn-ghost" href={editHref}>
            Edit
          </Link>
        )}
      </div>
    </article>
  );
}
