import type { MetadataRoute } from "next";

import { getSiteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  const base = getSiteUrl();
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/pricing", "/privacy", "/terms", "/takedown"],
        disallow: ["/projects", "/billing", "/channels", "/api"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
