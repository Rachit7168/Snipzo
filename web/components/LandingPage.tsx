import Link from "next/link";

import FaqAccordion from "@/components/FaqAccordion";
import PricingSection from "@/components/PricingSection";
import { Badge, buttonClasses, Card } from "@/components/ui";

const WORKFLOW_STEPS = [
  {
    step: "01",
    title: "Upload a file or paste a URL",
    body: "Drop an MP4, MOV, WebM, or MKV up to 2 GB, or paste a public YouTube watch or Shorts link.",
  },
  {
    step: "02",
    title: "AI finds the sharpest moments",
    body: "Whisper generates word-level timestamps and Snipzo scores hooks, insights, and punchlines.",
  },
  {
    step: "03",
    title: "Face-tracked 9:16 + captions",
    body: "Each clip is reframed vertically around the speaker with bold animated subtitles burned in.",
  },
  {
    step: "04",
    title: "Edit, download, or publish",
    body: "Trim timestamps or tweak captions in the browser, download the MP4, or publish straight to YouTube Shorts.",
  },
];

const FEATURES = [
  {
    title: "Word-accurate Whisper captions",
    description:
      "Active-word highlighting and customizable caption styles built straight into every vertical export.",
    badge: "Captions",
  },
  {
    title: "Speaker-centered 9:16 crop",
    description:
      "Face tracking keeps the person speaking framed in the center of vertical Shorts instead of chopping off edges.",
    badge: "Reframe",
  },
  {
    title: "AI highlight scoring & hooks",
    description:
      "Automatically surfaces standalone 20–60s moments with ready-to-use hook titles, descriptions, and tags.",
    badge: "Highlights",
  },
  {
    title: "In-browser clip editor",
    description:
      "Fine-tune start and end trims, edit transcript words or titles, and re-render individual clips in seconds.",
    badge: "Editor",
  },
  {
    title: "Direct YouTube Shorts upload",
    description:
      "Connect your channel via Google OAuth to publish Shorts with title, description, and privacy controls.",
    badge: "YouTube",
  },
  {
    title: "Private by design",
    description:
      "Source videos auto-expire after 14 days by default, and deleting a project wipes all media immediately.",
    badge: "Retention",
  },
];

const SUPPORTED_INPUTS = [
  { label: "MP4 / MOV / WebM / MKV", detail: "Direct file upload up to 2 GB" },
  { label: "YouTube watch & Shorts URLs", detail: "Paste a link, skip manual downloads" },
  { label: "Podcasts, talks & interviews", detail: "Multi-minute to multi-hour recordings" },
];

const SUPPORTED_OUTPUTS = [
  { label: "YouTube Shorts", detail: "Direct OAuth publish or MP4 download" },
  { label: "TikTok & Instagram Reels", detail: "Standard 9:16 H.264 MP4 exports" },
  { label: "LinkedIn & X vertical video", detail: "720p on Free · 1080p clean on paid plans" },
];

const CREATOR_GROUPS = [
  { role: "Podcasters", note: "Turn 60-min episodes into a week of clips" },
  { role: "YouTubers", note: "Repurpose long uploads into Shorts funnels" },
  { role: "Educators", note: "Extract key takeaways with readable captions" },
  { role: "Founders & Teams", note: "Ship demos and webinars across every feed" },
];

export default function LandingPage() {
  return (
    <div className="space-y-20 pb-8 sm:space-y-24">
      {/* Hero */}
      <section className="grid items-center gap-10 pt-2 lg:grid-cols-[1.15fr_0.85fr] lg:gap-12 lg:pt-6">
        <div className="min-w-0 space-y-6">
          <Badge tone="brand">Long-form video to vertical Shorts</Badge>
          <h1 className="text-4xl font-black tracking-tight text-ink sm:text-5xl lg:text-[3.35rem] lg:leading-[1.08]">
            Turn one long video into ready-to-post{" "}
            <span className="text-brand-text">vertical Shorts</span>.
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-ink-muted sm:text-lg">
            Upload a podcast, interview, or talk — or paste any public YouTube link. Snipzo finds
            the strongest hooks, centers the speaker in 9:16, burns in word-level captions, and
            renders crisp Shorts in minutes.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <Link href="/register" className={buttonClasses({ variant: "primary", size: "lg" })}>
              Get started free
            </Link>
            <a
              href="#how-it-works"
              className={buttonClasses({ variant: "ghost", size: "lg" })}
            >
              See how it works
            </a>
          </div>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-subtle">
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden="true" />3 free
              videos &amp; 30 minutes/month
            </span>
            <span>No credit card required</span>
            <span>MP4, MOV, WebM &amp; YouTube URLs</span>
          </div>
        </div>

        {/* Rendered Demo Short Preview */}
        <div className="mx-auto w-full max-w-[300px] sm:max-w-[320px]">
          <div className="relative rounded-[2rem] border border-line-strong bg-surface p-3 shadow-card">
            <div className="mb-2.5 flex items-center justify-between px-1.5 text-[11px] font-medium text-ink-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden="true" />
                Rendered Short
              </span>
              <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[10px] text-ink-subtle">
                9:16 · Captions
              </span>
            </div>

            <div className="relative aspect-[9/16] overflow-hidden rounded-[1.35rem] border border-line bg-black">
              <video
                src="/demo-short.mp4"
                poster="/demo-poster.jpg"
                autoPlay
                loop
                muted
                playsInline
                preload="metadata"
                aria-label="Example vertical Short rendered by Snipzo with burned-in captions"
                className="h-full w-full object-cover"
              />
            </div>

            <div className="mt-3 flex items-center justify-between gap-2 rounded-xl border border-line bg-surface-elevated/80 px-3 py-2 text-xs">
              <div className="min-w-0">
                <p className="truncate font-semibold text-ink">Highlight #1 · 00:38</p>
                <p className="truncate text-[11px] text-ink-subtle">
                  Face-tracked · Hook &amp; tags included
                </p>
              </div>
              <Badge tone="success">Ready</Badge>
            </div>
          </div>
        </div>
      </section>

      {/* Creator workflows strip */}
      <section aria-label="Built for video creators" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {CREATOR_GROUPS.map((group) => (
          <Card key={group.role} className="space-y-1 bg-surface/70 p-4">
            <p className="text-sm font-bold text-ink">{group.role}</p>
            <p className="text-xs leading-relaxed text-ink-muted">{group.note}</p>
          </Card>
        ))}
      </section>

      {/* How it works */}
      <section id="how-it-works" aria-labelledby="how-heading" className="scroll-mt-24 space-y-8">
        <div className="max-w-2xl space-y-2">
          <Badge tone="neutral">How it works</Badge>
          <h2 id="how-heading" className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
            From raw recording to published Short in four steps
          </h2>
          <p className="text-sm text-ink-muted sm:text-base">
            Skip manual timeline scrubbing, crop keyframes, and subtitle timing.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {WORKFLOW_STEPS.map((item) => (
            <Card key={item.step} className="flex flex-col gap-3 p-5">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-subtle text-xs font-black text-brand-text">
                {item.step}
              </span>
              <h3 className="text-base font-bold text-ink">{item.title}</h3>
              <p className="text-sm leading-relaxed text-ink-muted">{item.body}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" aria-labelledby="features-heading" className="scroll-mt-24 space-y-8">
        <div className="max-w-2xl space-y-2">
          <Badge tone="neutral">Features</Badge>
          <h2 id="features-heading" className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
            Everything you need to clip, polish, and ship
          </h2>
          <p className="text-sm text-ink-muted sm:text-base">
            Automated first draft, full creative control whenever you want to tweak a frame or word.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} className="space-y-3 p-5">
              <Badge tone="brand">{feature.badge}</Badge>
              <h3 className="text-base font-bold text-ink">{feature.title}</h3>
              <p className="text-sm leading-relaxed text-ink-muted">{feature.description}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Supported inputs & platforms */}
      <section id="platforms" aria-labelledby="platforms-heading" className="scroll-mt-24 space-y-6">
        <div className="max-w-2xl space-y-2">
          <Badge tone="neutral">Inputs &amp; platforms</Badge>
          <h2 id="platforms-heading" className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
            Bring any long video, export for every vertical feed
          </h2>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Card className="space-y-4 p-6">
            <h3 className="text-base font-bold text-ink">Supported inputs</h3>
            <ul className="space-y-3">
              {SUPPORTED_INPUTS.map((item) => (
                <li
                  key={item.label}
                  className="flex items-start justify-between gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0"
                >
                  <span className="text-sm font-semibold text-ink">{item.label}</span>
                  <span className="text-right text-xs text-ink-muted">{item.detail}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card className="space-y-4 p-6">
            <h3 className="text-base font-bold text-ink">Where your Shorts go</h3>
            <ul className="space-y-3">
              {SUPPORTED_OUTPUTS.map((item) => (
                <li
                  key={item.label}
                  className="flex items-start justify-between gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0"
                >
                  <span className="text-sm font-semibold text-ink">{item.label}</span>
                  <span className="text-right text-xs text-ink-muted">{item.detail}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </section>

      {/* Pricing */}
      <PricingSection />

      {/* FAQ */}
      <FaqAccordion />

      {/* Bottom CTA */}
      <Card highlight className="flex flex-col items-start justify-between gap-6 p-6 sm:flex-row sm:items-center sm:p-8">
        <div className="max-w-xl space-y-2">
          <h2 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">
            Ready to turn your next recording into Shorts?
          </h2>
          <p className="text-sm text-ink-muted">
            Create a free account and generate your first vertical clips in minutes — no credit card
            needed.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-3">
          <Link href="/register" className={buttonClasses({ variant: "primary", size: "lg" })}>
            Get started free
          </Link>
          <Link href="/login" className={buttonClasses({ variant: "ghost", size: "lg" })}>
            Sign in
          </Link>
        </div>
      </Card>
    </div>
  );
}
