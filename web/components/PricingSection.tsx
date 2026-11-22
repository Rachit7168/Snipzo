import Link from "next/link";

import { Badge, buttonClasses, Card } from "@/components/ui";
import { MARKETING_PLANS } from "@/lib/plans";

interface PricingSectionProps {
  headingAs?: "h1" | "h2";
  ctaMode?: "register" | "billing";
}

export default function PricingSection({
  headingAs = "h2",
  ctaMode = "register",
}: PricingSectionProps) {
  const Heading = headingAs;

  return (
    <section id="pricing" aria-labelledby="pricing-heading" className="scroll-mt-24 space-y-8">
      <div className="mx-auto max-w-2xl text-center">
        <Badge tone="brand">Simple, honest pricing</Badge>
        <Heading
          id="pricing-heading"
          className="mt-3 text-3xl font-black tracking-tight text-ink sm:text-4xl"
        >
          Start free, scale when your channel does
        </Heading>
        <p className="mt-3 text-sm leading-relaxed text-ink-muted sm:text-base">
          Every plan includes AI highlight selection, 9:16 face-tracked reframing, and word-level
          captions. Upgrade only when you need 1080p exports without a watermark or higher monthly
          volume.
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-3">
        {MARKETING_PLANS.map((plan) => {
          const href =
            ctaMode === "billing"
              ? "/billing"
              : plan.id === "free"
                ? "/register"
                : `/register?plan=${plan.id}`;
          return (
            <Card
              key={plan.id}
              highlight={plan.highlight}
              className="flex flex-col justify-between gap-6 p-6"
            >
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-bold text-ink">{plan.name}</h3>
                    <p className="mt-1 text-xs leading-relaxed text-ink-muted">{plan.tagline}</p>
                  </div>
                  {plan.badge && <Badge tone="brand">{plan.badge}</Badge>}
                </div>

                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-black tracking-tight text-ink">
                    ${plan.priceUsd}
                  </span>
                  <span className="text-sm text-ink-muted">/month</span>
                </div>

                <div className="rounded-control border border-line bg-surface-muted/70 px-3.5 py-2.5 text-xs font-medium text-ink">
                  {plan.videosPerMonth} {plan.videosPerMonth === 1 ? "video" : "videos"} / month ·{" "}
                  {plan.minutesPerMonth.toLocaleString()} source minutes / month
                </div>

                <ul className="space-y-2.5 text-sm text-ink-muted">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-start gap-2.5">
                      <svg
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        aria-hidden="true"
                        className="mt-0.5 h-4 w-4 shrink-0 text-brand-text"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.704 5.29a1 1 0 01.006 1.414l-7.25 7.3a1 1 0 01-1.42-.004L3.29 9.21a1 1 0 011.42-1.408l4.04 4.072 6.54-6.588a1 1 0 011.414.004z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <Link
                href={href}
                className={buttonClasses({
                  variant: plan.highlight ? "primary" : "secondary",
                  size: "lg",
                  fullWidth: true,
                })}
              >
                {plan.ctaLabel}
              </Link>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
