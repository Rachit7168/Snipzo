import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "rgb(var(--brand-rgb) / <alpha-value>)",
          hover: "var(--brand-hover)",
          dark: "var(--brand-hover)",
          fg: "var(--brand-fg)",
          text: "var(--brand-text)",
          subtle: "var(--brand-subtle)",
        },
        surface: {
          DEFAULT: "var(--surface)",
          elevated: "var(--surface-elevated)",
          muted: "var(--surface-muted)",
        },
        canvas: "var(--bg)",
        ink: {
          DEFAULT: "var(--text)",
          muted: "var(--text-muted)",
          subtle: "var(--text-subtle)",
        },
        line: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      borderRadius: {
        card: "1rem",
        control: "0.625rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0, 0, 0, 0.25), 0 8px 24px -12px rgba(0, 0, 0, 0.35)",
        glow: "0 0 0 1px rgba(250, 204, 21, 0.2), 0 12px 32px -12px rgba(250, 204, 21, 0.18)",
      },
    },
  },
  plugins: [],
};

export default config;
