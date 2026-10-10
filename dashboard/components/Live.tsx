"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Live-reading primitives.
 *
 * The core problem with the previous version: numbers updated over the socket
 * but nothing on screen SIGNALLED the change, so a genuinely live feed looked
 * like a static screenshot. A viewer has to be told "this just moved" — by the
 * interface, not by a caption.
 */

/**
 * Bumps a counter every time `value` changes. Used as a React `key` so the
 * animation restarts rather than only firing the first time.
 */
export function useChangeKey(value: unknown): number {
  const [k, setK] = useState(0);
  const prev = useRef(value);
  useEffect(() => {
    if (prev.current !== value) {
      prev.current = value;
      setK((n) => n + 1);
    }
  }, [value]);
  return k;
}

/**
 * A number that flashes in the agent's colour the instant it changes.
 *
 * `tone` drives the flash colour, so a value crossing into a warning state
 * flashes amber rather than teal.
 */
export function LiveNumber({
  value,
  unit,
  tone = "ok",
  className = "",
  dp = 0,
}: {
  value: number | string;
  unit?: string;
  tone?: "ok" | "act" | "stop";
  className?: string;
  dp?: number;
}) {
  const key = useChangeKey(value);
  const hex = tone === "stop" ? "#f87171" : tone === "act" ? "#fbbf24" : "#99f6e4";

  const text =
    typeof value === "number"
      ? value.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })
      : String(value);

  return (
    <span className={`inline-flex items-baseline gap-1 ${className}`} style={{ ["--flash" as string]: hex }}>
      <span key={key} className="animate-flash font-mono tabular font-semibold tracking-data text-slate-50">
        {text}
      </span>
      {unit && <span className="font-sans text-[10px] font-normal tracking-normal text-slate-500">{unit}</span>}
    </span>
  );
}

/**
 * A status chip that reads at a distance. Colour + motion, not grey 10px text.
 */
export function StatusChip({
  state,
  className = "",
}: {
  state: "watching" | "reading" | "thinking" | "decided" | "blocked" | "idle";
  className?: string;
}) {
  const map = {
    reading: { label: "reading", hex: "#38bdf8", live: true },
    thinking: { label: "thinking", hex: "#fbbf24", live: true },
    decided: { label: "decided", hex: "#34d399", live: false },
    blocked: { label: "paused for a human", hex: "#e879f9", live: true },
    watching: { label: "watching", hex: "#64748b", live: false },
    idle: { label: "watching", hex: "#64748b", live: false },
  }[state];

  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-[3px] text-[10px] font-semibold uppercase tracking-[0.1em] ${className}`}
      style={{ color: map.hex, borderColor: `${map.hex}44`, background: `${map.hex}12` }}
    >
      <span className="relative flex h-1.5 w-1.5">
        {map.live && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
            style={{ background: map.hex }}
          />
        )}
        <span
          className={`relative inline-flex h-1.5 w-1.5 rounded-full ${map.live ? "animate-pulse-dot" : ""}`}
          style={{ background: map.hex }}
        />
      </span>
      {map.label}
    </span>
  );
}

/** Severity chip, colour-coded, used on agent findings. */
export function SevChip({ sev }: { sev: string }) {
  const map: Record<string, { label: string; hex: string }> = {
    critical: { label: "critical", hex: "#f87171" },
    high: { label: "high", hex: "#fbbf24" },
    medium: { label: "medium", hex: "#fbbf24" },
    low: { label: "low", hex: "#34d399" },
    info: { label: "noted", hex: "#64748b" },
  };
  const m = map[sev] ?? map.info;
  return (
    <span
      className="inline-flex items-center rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em]"
      style={{ color: m.hex, borderColor: `${m.hex}44`, background: `${m.hex}12` }}
    >
      {m.label}
    </span>
  );
}

/** A labelled live reading row. The workhorse of the agents view. */
export function ReadingRow({
  label,
  value,
  unit,
  tone = "ok",
  dp = 0,
}: {
  label: string;
  value: number | string;
  unit?: string;
  tone?: "ok" | "act" | "stop";
  dp?: number;
}) {
  const dot = tone === "stop" ? "#f87171" : tone === "act" ? "#fbbf24" : "#22c55e";
  return (
    <div className="flex items-baseline gap-2 border-t border-white/[0.05] py-[7px] first:border-t-0">
      <span
        className="h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full"
        style={{ background: dot, boxShadow: `0 0 7px ${dot}` }}
      />
      <span className="flex-1 text-[11px] leading-tight text-slate-400">{label}</span>
      <LiveNumber value={value} unit={unit} tone={tone} dp={dp} className="shrink-0 text-[12px]" />
    </div>
  );
}
