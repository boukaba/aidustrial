import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#080b10", 900: "#0d1117", 800: "#141b24", 700: "#1d2632", 600: "#2a3543" },
        sig: { 400: "#5eead4", 500: "#2dd4bf", 600: "#14b8a6" },
        warn: { 400: "#fbbf24", 500: "#f59e0b" },
        crit: { 400: "#f87171", 500: "#ef4444" },
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [],
} satisfies Config;
