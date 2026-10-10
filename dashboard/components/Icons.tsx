"use client";

import { agent } from "@/lib/identity";

/**
 * All iconography for the app, as stroked SVG on a 24x24 grid.
 *
 * The emoji that used to sit in the sidebar and the cards read as a 2015 emoji
 * picker on top of an otherwise serious interface. A consistent stroke system
 * makes the whole thing look built rather than assembled.
 */

interface GlyphProps {
  className?: string;
  strokeWidth?: number;
  color?: string;
}

function Stroke({
  d,
  className,
  strokeWidth = 1.7,
  color,
}: GlyphProps & { d: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      stroke={color ?? "currentColor"}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}

/** An agent's own glyph, in that agent's colour. */
export function AgentGlyph({
  id,
  className = "h-4 w-4",
  strokeWidth = 1.7,
}: {
  id: string;
  className?: string;
  strokeWidth?: number;
}) {
  const a = agent(id);
  return <Stroke d={a.glyph} className={className} strokeWidth={strokeWidth} color={a.hex} />;
}

/**
 * The agent avatar: a monogram badge ringed in the agent's colour. This is the
 * single strongest cue that seven cards are seven DIFFERENT workers.
 */
export function AgentBadge({
  id,
  size = "md",
  active = false,
}: {
  id: string;
  size?: "sm" | "md" | "lg";
  active?: boolean;
}) {
  const a = agent(id);
  const dim = { sm: "h-6 w-6 text-[9px]", md: "h-8 w-8 text-[11px]", lg: "h-10 w-10 text-[13px]" }[size];
  return (
    <span
      className={`relative inline-flex ${dim} shrink-0 items-center justify-center rounded-md border font-mono font-bold tracking-tight`}
      style={{
        color: a.hex,
        borderColor: `${a.hex}55`,
        background: `linear-gradient(140deg, ${a.hex}22, ${a.hex}08)`,
        boxShadow: active ? `0 0 14px -3px ${a.hex}88` : "none",
      }}
    >
      {a.mono}
      {active && (
        <span
          className="absolute -bottom-0.5 -right-0.5 h-1.5 w-1.5 animate-pulse-dot rounded-full"
          style={{ background: a.hex, boxShadow: `0 0 6px ${a.hex}` }}
        />
      )}
    </span>
  );
}

/** Nav glyphs. Keys match the NAV ids in lib/language. */
export const NAV_GLYPH: Record<string, string> = {
  home: "M3 11.5 12 4l9 7.5 M5.5 10v9.5h13V10 M9.5 19.5v-5h5v5",
  agents: "M9 9m-2.2 0a2.2 2.2 0 1 0 4.4 0a2.2 2.2 0 1 0-4.4 0 M16.5 10.5m-1.8 0a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0-3.6 0 M4 19c0-2.8 2.2-4.5 5-4.5s5 1.7 5 4.5 M14.5 19c0-2.2 1.2-3.6 3-4",
  crop: "M12 21V11 M12 11c0-3-2-5-6-5 0 4 2 5 6 5z M12 13c0-3 2-5 6-5 0 4-2 5-6 5z",
  livestock: "M4 14c0-3 2.5-5 5.5-5S15 11 15 14v3H4v-3z M15 12h3.5a2 2 0 0 1 2 2v3H15v-5z M7 17v2 M12.5 17v2 M6 9.5 5 6 M13 9.5 14 6",
  milk: "M8 3h8v3a4 4 0 0 1-8 0V3z M12 10v11 M8 21h8",
  infrastructure: "M4 20V9 M9 20V4 M14 20v-8 M19 20v-5 M3 20h18",
  decisions: "M12 3v3 M5.6 9.6l2.1 2.1 M18.4 9.6l-2.1 2.1 M3 18h18 M6.5 18a5.5 5.5 0 0 1 11 0",
  system: "M12 12m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M12 4v5.5 M12 14.5V20 M5 8l4.2 2.4 M14.8 13.6L19 16 M5 16l4.2-2.4 M14.8 10.4L19 8",
};

export function NavGlyph({ id, className = "h-[18px] w-[18px]" }: { id: string; className?: string }) {
  const d = NAV_GLYPH[id];
  if (!d) return <span className={className} />;
  return <Stroke d={d} className={className} strokeWidth={1.6} />;
}

/** Utility glyphs used in chrome. */
export const UI = {
  close: "M6 6l12 12 M18 6 6 18",
  chevronRight: "M9 6l6 6-6 6",
  chevronLeft: "M15 6l-6 6 6 6",
  chevronDown: "M6 9l6 6 6-6",
  chevronUp: "M6 15l6-6 6 6",
  check: "M5 12.5 9.5 17 19 7",
  x: "M6 6l12 12 M18 6 6 18",
  arrowRight: "M5 12h14 M13 6l6 6-6 6",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 8 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H2a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 8a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V2a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H22a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z",
  bolt: "M13 2 4 14h6l-1 8 9-12h-6l1-8z",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  radio: "M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M7.8 7.8a6 6 0 0 0 0 8.4 M16.2 16.2a6 6 0 0 0 0-8.4 M5 5a10 10 0 0 0 0 14 M19 19a10 10 0 0 0 0-14",
} as const;

export function UiGlyph({
  name,
  className = "h-4 w-4",
  strokeWidth = 1.8,
}: {
  name: keyof typeof UI;
  className?: string;
  strokeWidth?: number;
}) {
  return <Stroke d={UI[name]} className={className} strokeWidth={strokeWidth} />;
}
