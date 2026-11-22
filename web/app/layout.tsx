import type { Metadata } from "next";
import type { ReactNode } from "react";

import Footer from "@/components/Footer";
import Nav from "@/components/Nav";
import Providers from "@/components/Providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Snipzo: long videos to Shorts",
  description: "Upload a long-form video and get ready-to-post vertical Shorts.",
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
      </body>
    </html>
  );
}
