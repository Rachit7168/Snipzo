"use client";

import type { KeyboardEvent } from "react";

export type TabItem<T extends string> = {
  id: T;
  label: string;
};

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
  className = "",
}: {
  items: ReadonlyArray<TabItem<T>>;
  value: T;
  onChange: (next: T) => void;
  label: string;
  className?: string;
}) {
  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = items[(index + delta + items.length) % items.length];
    onChange(next.id);
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      className={`inline-flex rounded-control border border-line bg-surface-elevated p-1 ${className}`}
    >
      {items.map((item, index) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
              selected
                ? "bg-surface text-ink shadow-sm"
                : "text-ink-muted hover:text-ink"
            }`}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
