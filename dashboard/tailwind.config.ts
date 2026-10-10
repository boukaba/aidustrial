import type { Config } from "tailwindcss";

/**
 * Mission-control palette.
 *
 * One accent per specialist, chosen so seven live agents read as seven
 * DISTINCT signals at a glance rather than seven identical dark cards. The hues
 * are evenly spaced around the wheel and all sit bright enough to glow on a
 * near-black ground without vibrating.
 */
const AGENT = {
  crop: "#a3e635",
  agronomist: "#22d3ee",
  veterinarian: "#34d399",
  calving: "#c084fc",
  milking: "#38bdf8",
  maintenance: "#fbbf24",
  logistics: "#fb7185",
  orchestrator: "#e2e8f0",
};

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // near-black ground, four steps of panel
        ink: {
          1000: "#04060a",
          950: "#070a10",
          900: "#0b0f16",
          800: "#10161f",
          700: "#18212c",
          600: "#232f3d",
          500: "#354353",
        },
        sig: { 300: "#99f6e4", 400: "#5eead4", 500: "#2dd4bf", 600: "#14b8a6" },
        warn: { 300: "#fcd34d", 400: "#fbbf24", 500: "#f59e0b" },
        crit: { 300: "#fca5a5", 400: "#f87171", 500: "#ef4444" },
        // per-agent identity
        agent: AGENT,
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SF Mono",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      letterSpacing: {
        // tighter than tailwind's default, which tracks numbers out badly
        tightest: "-0.03em",
        data: "-0.02em",
      },
      boxShadow: {
        glow: "0 0 24px -6px var(--glow, rgba(45,212,191,0.35))",
        "glow-sm": "0 0 12px -3px var(--glow, rgba(45,212,191,0.3))",
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 20px 40px -24px rgba(0,0,0,0.9)",
      },
      animation: {
        "pulse-ring": "pulse-ring 1.9s cubic-bezier(0.4,0,0.6,1) infinite",
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
        "pulse-slow": "pulse-slow 3.2s ease-in-out infinite",
        flash: "flash 0.7s ease-out",
        scan: "scan 7s linear infinite",
        drift: "drift 40s linear infinite",
        flow: "flow 1.4s linear infinite",
        "slide-in": "slide-in 0.4s cubic-bezier(0.16,1,0.3,1)",
        "fade-up": "fade-up 0.5s cubic-bezier(0.16,1,0.3,1) both",
        sweep: "sweep 3.6s ease-in-out infinite",
      },
      keyframes: {
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 var(--ring, rgba(45,212,191,0.5))" },
          "70%": { boxShadow: "0 0 0 12px rgba(0,0,0,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(0,0,0,0)" },
        },
        "pulse-dot": {
          "0%,100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.45", transform: "scale(0.82)" },
        },
        "pulse-slow": {
          "0%,100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        flash: {
          "0%": {
            color: "var(--flash, #99f6e4)",
            textShadow: "0 0 14px var(--flash, rgba(153,246,228,0.8))",
          },
          "100%": { textShadow: "0 0 0 rgba(0,0,0,0)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(1400%)" },
        },
        drift: {
          "0%": { backgroundPosition: "0 0" },
          "100%": { backgroundPosition: "0 -400px" },
        },
        flow: {
          "0%": { strokeDashoffset: "24" },
          "100%": { strokeDashoffset: "0" },
        },
        "slide-in": {
          "0%": { opacity: "0", transform: "translateX(14px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        sweep: {
          "0%,100%": { opacity: "0.25" },
          "50%": { opacity: "0.85" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
