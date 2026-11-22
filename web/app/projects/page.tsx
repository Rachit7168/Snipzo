import type { Metadata } from "next";

import DashboardClient from "@/components/DashboardClient";

export const metadata: Metadata = {
  title: "Projects",
  description: "Upload long-form videos or paste YouTube links to generate vertical Shorts.",
  robots: { index: false, follow: false },
};

export default function ProjectsPage() {
  return <DashboardClient />;
}
