"use client";

import Link from "next/link";

import { Badge, Button, Modal } from "@/components/ui";

const STEPS = [
  {
    num: "1",
    title: "Upload a video you own",
    body: "Drop an MP4, MOV, WebM, or MKV file — or paste a public YouTube link.",
  },
  {
    num: "2",
    title: "Wait while Snipzo finds clips",
    body: "We transcribe audio, pick the best moments, center the speaker in 9:16, and burn captions.",
  },
  {
    num: "3",
    title: "Edit, download, or publish",
    body: "Trim timestamps or edit captions in your browser, download the MP4, or connect YouTube.",
  },
];

export default function WelcomeOnboardingModal({
  open,
  onClose,
  onStartUpload,
  videosPerMonth = 3,
  minutesPerMonth = 30,
}: {
  open: boolean;
  onClose: () => void;
  onStartUpload: () => void;
  videosPerMonth?: number;
  minutesPerMonth?: number;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Welcome to Snipzo"
      description="Turn your first long video into vertical Shorts in three quick steps."
    >
      <div className="space-y-4">
        <ol className="space-y-3">
          {STEPS.map((step) => (
            <li
              key={step.num}
              className="flex items-start gap-3 rounded-control border border-line bg-surface-muted/60 p-3"
            >
              <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-black text-brand-fg">
                {step.num}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{step.title}</p>
                <p className="text-xs leading-relaxed text-ink-muted">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="rounded-control border border-line bg-surface-elevated/70 p-3 text-xs text-ink-muted">
          <div className="mb-1 flex items-center gap-2">
            <Badge tone="brand">Free plan</Badge>
            <span className="font-medium text-ink">No credit card or YouTube login needed</span>
          </div>
          <p>
            Includes {videosPerMonth} {videosPerMonth === 1 ? "video" : "videos"} and {minutesPerMonth} source minutes per month at 720p with a subtle Snipzo
            watermark.{" "}
            <Link href="/pricing" onClick={onClose} className="font-medium text-brand-text hover:underline">
              Compare plans
            </Link>
          </p>
        </div>

        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Explore first
          </Button>
          <Button
            onClick={() => {
              onClose();
              onStartUpload();
            }}
          >
            Upload my first video
          </Button>
        </div>
      </div>
    </Modal>
  );
}
