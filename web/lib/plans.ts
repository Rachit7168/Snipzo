export interface MarketingPlan {
  id: "free" | "creator" | "pro";
  name: string;
  priceUsd: number;
  tagline: string;
  videosPerMonth: number;
  minutesPerMonth: number;
  features: string[];
  ctaLabel: string;
  highlight?: boolean;
  badge?: string;
}

export const MARKETING_PLANS: MarketingPlan[] = [
  {
    id: "free",
    name: "Free",
    priceUsd: 0,
    tagline: "Test Snipzo on your next video with zero commitment.",
    videosPerMonth: 3,
    minutesPerMonth: 30,
    features: [
      "720p vertical MP4 exports",
      "Snipzo watermark",
      "AI highlight detection & captions",
      "YouTube URL import or file upload",
    ],
    ctaLabel: "Start free",
  },
  {
    id: "creator",
    name: "Creator",
    priceUsd: 19,
    tagline: "Built for weekly podcasters, educators, and channels.",
    videosPerMonth: 30,
    minutesPerMonth: 600,
    features: [
      "1080p full-HD exports",
      "No watermark",
      "In-browser clip & caption editor",
      "Direct YouTube Shorts publishing",
    ],
    ctaLabel: "Choose Creator",
    highlight: true,
    badge: "Popular",
  },
  {
    id: "pro",
    name: "Pro",
    priceUsd: 49,
    tagline: "High-volume clipping for studios, agencies, and daily shows.",
    videosPerMonth: 100,
    minutesPerMonth: 3000,
    features: [
      "Everything in Creator",
      "3,000 source minutes / month",
      "Higher monthly project limits",
      "Priority render queue",
    ],
    ctaLabel: "Choose Pro",
  },
];

export interface FaqItem {
  question: string;
  answer: string;
}

export const FAQ_ITEMS: FaqItem[] = [
  {
    question: "What video files and links can I import?",
    answer:
      "Upload MP4, MOV, WebM, or MKV files up to 2 GB directly from your computer, or paste a public YouTube watch, Shorts, or live-replay URL. Snipzo extracts the audio, transcribes every word, and generates vertical 9:16 Shorts automatically.",
  },
  {
    question: "What does the Free plan include?",
    answer:
      "The Free plan includes 3 videos and up to 30 source minutes per month at no cost, rendered in 720p with a subtle Made with Snipzo watermark. Upgrade to Creator ($19/mo) or Pro ($49/mo) anytime for 1080p watermark-free exports and higher limits.",
  },
  {
    question: "Can I edit the timestamps, titles, and captions before exporting?",
    answer:
      "Yes. Every generated Short opens in the clip editor where you can trim start and end times, tweak the hook title and description, adjust caption styling or wording, and re-render cleanly.",
  },
  {
    question: "How does direct YouTube Shorts publishing work?",
    answer:
      "Connect your YouTube channel from the Channels page using official Google OAuth. Once connected, you can publish any rendered Short directly to your channel or schedule it as private or unlisted first — and disconnect in one click whenever you want.",
  },
  {
    question: "Who owns the videos and Shorts I create?",
    answer:
      "You keep full ownership of your source videos and every Short rendered by Snipzo. Only upload or import content that you own or have permission to clip and distribute.",
  },
  {
    question: "How long are uploaded source videos kept?",
    answer:
      "Uploaded source files are automatically deleted after the 14-day retention window by default, and deleting any project immediately removes its source video, transcript, and rendered clips.",
  },
];
