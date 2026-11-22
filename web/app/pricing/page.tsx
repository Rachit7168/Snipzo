import type { Metadata } from "next";

import FaqAccordion from "@/components/FaqAccordion";
import PricingSection from "@/components/PricingSection";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Compare Snipzo Free, Creator ($19/mo), and Pro ($49/mo) plans for turning long videos into vertical Shorts.",
  alternates: { canonical: "/pricing" },
};

export default function PricingPage() {
  return (
    <div className="space-y-20 pb-8 pt-2 sm:pt-4">
      <PricingSection headingAs="h1" />
      <FaqAccordion />
    </div>
  );
}
