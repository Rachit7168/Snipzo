import Script from "next/script";

/**
 * Privacy-friendly analytics hook.
 * Disabled by default: renders nothing unless NEXT_PUBLIC_PLAUSIBLE_DOMAIN is configured.
 */
export default function Analytics() {
  const domain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN?.trim();
  const enabled = process.env.NEXT_PUBLIC_ANALYTICS_ENABLED !== "false";
  if (!domain || !enabled) {
    return null;
  }

  const src =
    process.env.NEXT_PUBLIC_PLAUSIBLE_SRC?.trim() ||
    "https://plausible.io/js/script.js";

  return (
    <Script
      defer
      data-domain={domain}
      src={src}
      strategy="afterInteractive"
    />
  );
}
