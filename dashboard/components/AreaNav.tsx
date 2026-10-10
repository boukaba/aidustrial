"use client";

import { useState } from "react";
import type { Packet } from "@/lib/types";
import {
  AreaId,
  Plain,
  cropSummary,
  livestockSummary,
  milkSummary,
  LEVEL_STYLE,
  LEVEL_LABEL,
} from "@/lib/explain";

function Ring({ pct, level }: { pct: number; level: Plain["level"] }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const stroke =
    level === "stop" ? "#ef4444" : level === "act" ? "#f59e0b" : level === "watch" ? "#fbbf24" : "#2dd4bf";
  return (
    <svg viewBox="0 0 64 64" className="h-16 w-16 shrink-0">
      <circle cx="32" cy="32" r={r} fill="none" stroke="#1d2632" strokeWidth="6" />
      <circle
        cx="32"
        cy="32"
        r={r}
        fill="none"
        stroke={stroke}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c - (c * Math.max(2, Math.min(100, pct))) / 100}
        transform="rotate(-90 32 32)"
        className="transition-all duration-700"
      />
    </svg>
  );
}

export interface AreaCardSpec {
  id: AreaId;
  icon: string;
  name: string;
  area: string;
  plain: Plain;
  metric: string;
  metricLabel: string;
  pct: number;
}

export function areaCards(p: Packet): AreaCardSpec[] {
  const e = p.environment;
  const c = p.crop_production;
  const l = p.livestock;
  const m = p.milk_production;

  const wilting = c.fields.filter((f) => f.soil_moisture_pct <= 9).length;
  const stressedPct = (wilting / Math.max(c.fields.length, 1)) * 100;

  const nonProdPct = (l.non_productive_head / Math.max(l.total_head, 1)) * 100;

  const worstScc = m.bulk_scc_k > m.scc_limit_k ? 100 : (m.bulk_scc_k / 400) * 100;

  const infraIssues =
    e.pivots.filter((x) => x.health !== "nominal").length +
    (p.logistics.tankers.filter((t) => t.status !== "nominal").length);

  return [
    {
      id: "crop",
      icon: "🌾",
      name: "Growing the feed",
      area: "CROP PRODUCTION",
      plain: cropSummary({
        standing_t: c.standing_t,
        water_stressed_ha: c.water_stressed_ha,
        status: c.status,
        harvested_t: c.harvested_t,
      }),
      metric: `${Math.round(c.standing_t).toLocaleString()} t`,
      metricLabel: "forage standing in the field",
      pct: 100 - stressedPct,
    },
    {
      id: "livestock",
      icon: "🐄",
      name: "The herd",
      area: "LIVESTOCK",
      plain: livestockSummary({
        non_productive_head: l.non_productive_head,
        total_head: l.total_head,
        calf_mortality_7d: l.calf_mortality_7d,
        status: l.status,
      }),
      metric: l.total_head.toLocaleString(),
      metricLabel: "animals on site",
      pct: 100 - nonProdPct,
    },
    {
      id: "milk",
      icon: "🥛",
      name: "Making the milk",
      area: "MILK PRODUCTION",
      plain: milkSummary({
        bulk_scc_k: m.bulk_scc_k,
        scc_limit_k: m.scc_limit_k,
        bulk_temp_c: m.bulk_temp_c,
        downtime_min_24h: m.downtime_min_24h,
        capture_ratio: m.capture_ratio,
      }),
      metric: `${(m.daily_milk_kg / 1000).toFixed(0)} t`,
      metricLabel: "milk per day",
      pct: m.capture_ratio,
    },
    {
      id: "infrastructure",
      icon: "💧",
      name: "Water and machinery",
      area: "INFRASTRUCTURE",
      plain:
        infraIssues > 0
          ? {
              line: `${infraIssues} piece${infraIssues > 1 ? "s" : ""} of equipment need attention.`,
              because: "A failed pivot costs a field for the day.",
              level: "act",
            }
          : {
              line: "All machinery is running normally.",
              because: `Water is using ${e.aquifer_budget_used_pct.toFixed(0)}% of its sustainable yearly limit.`,
              level: "ok",
            },
      metric: `${e.aquifer_budget_used_pct.toFixed(0)}%`,
      metricLabel: "of the water budget",
      pct: 100 - e.aquifer_budget_used_pct,
    },
    {
      id: "mesh",
      icon: "🤖",
      name: "The agents talking",
      area: "AGENT SWARM",
      plain: (() => {
        const answered = new Set((p.board ?? []).map((m) => m.in_reply_to).filter(Boolean));
        const open = (p.board ?? []).filter(
          (m) => m.expects_reply && !answered.has(m.message_id),
        ).length;
        return open
          ? {
              line: `The agents have ${open} question still open.`,
              because: "One agent is waiting on another's answer before deciding.",
              level: "watch",
            }
          : {
              line: "The agents agree on what to do.",
              because: `${(p.board ?? []).length} messages exchanged, no open questions.`,
              level: "ok",
            };
      })(),
      metric: String((p.board ?? []).length),
      metricLabel: "messages exchanged",
      pct: 100,
    },
  ];
}

export function AreaNav({
  p,
  active,
  onSelect,
}: {
  p: Packet;
  active: AreaId;
  onSelect: (a: AreaId) => void;
}) {
  const cards = areaCards(p);
  const [hover, setHover] = useState<AreaId | null>(null);

  return (
    <nav aria-label="Production areas" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {cards.map((a) => {
        const isActive = active === a.id;
        const show = isActive || hover === a.id;
        return (
          <button
            key={a.id}
            onClick={() => onSelect(a.id)}
            onMouseEnter={() => setHover(a.id)}
            onMouseLeave={() => setHover(null)}
            aria-pressed={isActive}
            aria-label={`${a.area}: ${a.plain.line}`}
            className={`group relative flex flex-col rounded-lg border p-4 text-left transition-all duration-200 ${
              isActive
                ? "border-sig-500/60 bg-sig-500/[0.07] shadow-lg shadow-sig-500/5"
                : "border-ink-700 bg-ink-900/70 hover:border-ink-600 hover:bg-ink-900"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-base" aria-hidden>
                    {a.icon}
                  </span>
                  <span className="text-[9px] font-bold tracking-[0.14em] text-slate-500">
                    {a.area}
                  </span>
                </div>
                <h3 className="mt-1 text-sm font-semibold text-slate-100">{a.name}</h3>
              </div>
              <Ring pct={a.pct} level={a.plain.level} />
            </div>

            <div className={`pill mt-2 self-start border ${LEVEL_STYLE[a.plain.level]}`}>
              {LEVEL_LABEL[a.plain.level]}
            </div>

            <div className="mt-2">
              <div className="metric text-xl text-slate-100">{a.metric}</div>
              <div className="text-[10px] text-slate-500">{a.metricLabel}</div>
            </div>

            <p
              className={`mt-2 text-[11px] leading-relaxed text-slate-300 transition-opacity ${
                show ? "opacity-100" : "opacity-70"
              }`}
            >
              {a.plain.line}
            </p>

            <span
              className={`mt-2 text-[10px] font-semibold transition-colors ${
                isActive ? "text-sig-400" : "text-slate-500 group-hover:text-sig-500"
              }`}
            >
              {isActive ? "▼ Showing below" : "Click to explore →"}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

/** A plain-language banner with an optional second sentence. */
export function PlainNote({ plain, className = "" }: { plain: Plain; className?: string }) {
  return (
    <div className={`rounded border p-3 ${LEVEL_STYLE[plain.level]} ${className}`}>
      <p className="text-sm font-medium">{plain.line}</p>
      {plain.because && <p className="mt-1 text-xs opacity-80">{plain.because}</p>}
    </div>
  );
}

/** Hover/click term explanation for judges who don't know the jargon. */
export function Term({ children, term }: { children: React.ReactNode; term: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onClick={() => setOpen((v) => !v)}
      tabIndex={0}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      role="button"
      aria-label={`What does ${String(children)} mean?`}
    >
      <span className="cursor-help underline decoration-dotted decoration-slate-600 underline-offset-4">
        {children}
      </span>
      {open && (
        <span className="absolute bottom-full left-1/2 z-50 mb-1.5 w-56 -translate-x-1/2 rounded border border-ink-600 bg-ink-950 p-2.5 text-[11px] font-normal leading-relaxed text-slate-300 shadow-xl">
          {term}
        </span>
      )}
    </span>
  );
}