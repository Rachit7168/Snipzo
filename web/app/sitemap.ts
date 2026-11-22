import type { MetadataRoute } from "next";

import { getSiteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = getSiteUrl();
  const routes = ["/", "/pricing", "/login", "/register", "/privacy", "/terms", "/takedown"];
  const now = new Date();
  return routes.map((route) => ({
    url: `${base}${route}`,
    lastModified: now,
    changeFrequency: route === "/" || route === "/pricing" ? "weekly" : "monthly",
    priority: route === "/" ? 1 : route === "/pricing" ? 0.9 : 0.5,
  }));
}
