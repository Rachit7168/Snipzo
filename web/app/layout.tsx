import type { Metadata } from "next";
import type { ReactNode } from "react";

import Nav from "@/components/Nav";
import Providers from "@/components/Providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Snipzo: long videos to Shorts",
  description: "Upload a long-form video and get ready-to-post vertical Shorts.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <Nav />
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
