"use client";

import { useState } from "react";

import { Badge } from "@/components/ui";
import { FAQ_ITEMS } from "@/lib/plans";

export default function FaqAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" aria-labelledby="faq-heading" className="scroll-mt-24 space-y-8">
      <div className="mx-auto max-w-2xl text-center">
        <Badge tone="neutral">FAQ</Badge>
        <h2
          id="faq-heading"
          className="mt-3 text-3xl font-black tracking-tight text-ink sm:text-4xl"
        >
          Common questions
        </h2>
        <p className="mt-2 text-sm text-ink-muted sm:text-base">
          Everything you need to know about inputs, exports, YouTube publishing, and privacy.
        </p>
      </div>

      <div className="mx-auto max-w-3xl divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
        {FAQ_ITEMS.map((item, idx) => {
          const isOpen = openIndex === idx;
          const panelId = `faq-panel-${idx}`;
          const buttonId = `faq-trigger-${idx}`;
          return (
            <div key={item.question}>
              <h3>
                <button
                  id={buttonId}
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={panelId}
                  onClick={() => setOpenIndex(isOpen ? null : idx)}
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-semibold text-ink transition hover:bg-surface-elevated sm:px-6 sm:text-base"
                >
                  <span>{item.question}</span>
                  <svg
                    viewBox="0 0 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    aria-hidden="true"
                    className={`h-4 w-4 shrink-0 text-ink-muted transition-transform ${
                      isOpen ? "rotate-180" : ""
                    }`}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 7.5l5 5 5-5" />
                  </svg>
                </button>
              </h3>
              {isOpen && (
                <div
                  id={panelId}
                  role="region"
                  aria-labelledby={buttonId}
                  className="px-5 pb-5 text-sm leading-relaxed text-ink-muted sm:px-6"
                >
                  {item.answer}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
