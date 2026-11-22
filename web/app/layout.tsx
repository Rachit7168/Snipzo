import type { Metadata } from "next";
import type { ReactNode } from "react";

import Analytics from "@/components/Analytics";
import Footer from "@/components/Footer";
import Nav from "@/components/Nav";
import Providers from "@/components/Providers";
import { getSiteUrl } from "@/lib/site";

import "./globals.css";

const siteUrl = getSiteUrl();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Snipzo — Turn long videos into vertical Shorts",
    template: "%s · Snipzo",
  },
  description:
    "Upload a long-form video or paste a YouTube URL and get ready-to-post 9:16 vertical Shorts with captions and hook titles.",
  keywords: [
    "youtube shorts generator",
    "ai video clipping",
    "long video to shorts",
    "vertical video captions",
    "podcast clips",
  ],
  openGraph: {
    type: "website",
    siteName: "Snipzo",
    title: "Snipzo — Turn long videos into vertical Shorts",
    description:
      "AI highlight detection, speaker-centered 9:16 reframing, burned-in captions, and direct YouTube Shorts publishing.",
    url: "/",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "Snipzo — Long videos to vertical Shorts",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Snipzo — Turn long videos into vertical Shorts",
    description:
      "Upload a long-form video or paste a YouTube URL and get ready-to-post vertical Shorts.",
    images: ["/opengraph-image"],
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <Providers>
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-brand focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-brand-fg"
          >
            Skip to content
          </a>
          <Nav />
          <main id="main-content" className="mx-auto min-h-[72vh] max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
            {children}
          </main>
          <Footer />
        </Providers>
        <Analytics />
      </body>
    </html>
  );
}
