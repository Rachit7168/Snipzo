import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";

import LandingPage from "@/components/LandingPage";
import { authOptions } from "@/lib/auth";
import { FAQ_ITEMS } from "@/lib/plans";
import { getSiteUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: "Snipzo — Turn long videos into vertical Shorts",
  description:
    "Upload a podcast, interview, or talk — or paste a YouTube URL. Snipzo finds highlights, reframes 9:16 around the speaker, burns in captions, and exports ready-to-post Shorts.",
  alternates: { canonical: "/" },
};

export default async function HomePage() {
  const session = await getServerSession(authOptions);
  if (session) {
    redirect("/projects");
  }

  const siteUrl = getSiteUrl();
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        name: "Snipzo",
        url: siteUrl,
      },
      {
        "@type": "SoftwareApplication",
        name: "Snipzo",
        applicationCategory: "MultimediaApplication",
        operatingSystem: "Web",
        url: siteUrl,
        description:
          "Turn long-form videos and YouTube links into vertical Shorts with AI highlights, face-tracked 9:16 cropping, and burned-in captions.",
        offers: [
          {
            "@type": "Offer",
            name: "Free",
            price: "0",
            priceCurrency: "USD",
          },
          {
            "@type": "Offer",
            name: "Creator",
            price: "19",
            priceCurrency: "USD",
          },
          {
            "@type": "Offer",
            name: "Pro",
            price: "49",
            priceCurrency: "USD",
          },
        ],
      },
      {
        "@type": "FAQPage",
        mainEntity: FAQ_ITEMS.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: {
            "@type": "Answer",
            text: item.answer,
          },
        })),
      },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
      <LandingPage />
    </>
  );
}
