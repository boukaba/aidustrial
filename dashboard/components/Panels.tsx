"use client";

import type { Packet, Summary, TraceEvent } from "@/lib/types";
import { AGENT_COLOR, bandColor, healthColor, sevColor } from "@/lib/types";

function Stat({
  label,
  value,
  unit,
  sub,
  tone = "text-slate-100",
}: {
  label: string;
  value: string | number;
  unit?: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="card p-3">
      <div className="label">{label}</div>
      <div className={`metric mt-1 text-xl ${tone}`}>
        {value}
        {unit && <span className="ml-1 text-[11px] text-slate-500">{unit}</span>}
      </div>
      {sub && <div className="mt-0.5 text-[10px] text-slate-500">{sub}</div>}
    </div>
  );
}

function Bar({ pct, tone = "bg-sig-500" }: { pct: number; tone?: string }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-ink-700">
      <div
        className={`h-full rounded-full transition-all duration-700 ${tone}`}
        style={{ width: `${Math.max(1, Math.min(100, pct))}%` }}
      />
    </div>
  );
}

export function SiteHeader({ s, speed, onSpeed }: { s: Summary; speed: number; onSpeed: (v: number) => void }) {
  return (
    <header className="card mb-4 flex flex-wrap items-center gap-4 p-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="rounded bg-sig-600/15 px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-sig-400">
            AIDUSTRIAL
          </span>
          <h1 className="text-sm font-semibold text-slate-200">
            Adrar Operations Command
          </h1>
        </div>
        <p className="mt-0.5 text-[11px] text-slate-500">
          Baladna Algeria S.P.A. · Adrar Province · 51% Baladna Q.P.S.C. / 49% FNI
        </p>
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <span className={`pill border ${bandColor(s.heat_stress_band)}`}>
          {s.heat_stress_band}
        </span>
        <span className="metric rounded border border-ink-700 px-2.5 py-1 text-xs text-slate-300">
          {s.sim_time} · {s.phase}
        </span>
        <div className="flex items-center gap-1 rounded border border-ink-700 px-2 py-1">
          <span className="label">Speed</span>
          {[4, 14, 40].map((v) => (
            <button
              key={v}
              onClick={() => onSpeed(v)}
              className={`metric rounded px-1.5 text-[11px] transition ${
                speed === v ? "bg-sig-600 text-ink-950" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {v}x
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}

export function StatStrip({ s }: { s: Summary }) {
  const aqTone =
    s.aquifer_pct >= 100 ? "text-crit-400" : s.aquifer_pct >= 85 ? "text-warn-400" : "text-slate-100";
  const rumTone = s.rumination_deficit >= 10 ? "text-crit-400" : s.rumination_deficit >= 5 ? "text-warn-400" : "text-slate-100";

  return (
    <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
      <Stat label="Air temp" value={s.temperature_c.toFixed(1)} unit="°C" sub={`RH ${s.temperature_c > 35 ? "low" : "—"}`} />
      <Stat
        label="Effective heat load"
        value={s.effective_heat_load.toFixed(1)}
        sub={`air THI ${s.thi_air.toFixed(1)} + solar`}
        tone="text-sig-400"
      />
      <Stat
        label="Aquifer budget"
        value={s.aquifer_pct.toFixed(1)}
        unit="%"
        sub={s.aquifer_status}
        tone={aqTone}
      />
      <Stat label="Herd" value={s.herd_head.toLocaleString()} unit="head" sub="Phase 1 built" />
      <Stat
        label="Rumination deficit"
        value={s.rumination_deficit.toFixed(1)}
        unit="%"
        sub="early-warning signal"
        tone={rumTone}
      />
      <Stat
        label="Feed cover"
        value={s.feed_hours.toFixed(0)}
        unit="h"
        sub={`${(s.feed_hours / 24).toFixed(1)} days`}
        tone={s.feed_hours < 24 ? "text-crit-400" : s.feed_hours < 72 ? "text-warn-400" : "text-slate-100"}
      />
    </div>
  );
}

export function HerdPanel({ p }: { p: Packet }) {
  return (
    <section className="card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Herd — barn level</h2>
        <span className="label">{p.herd.head.toLocaleString()} head</span>
      </div>
      <div className="space-y-1.5">
        {p.herd.groups.map((g) => {
          const rumTone =
            g.rumination_pct < 85 ? "bg-crit-500" : g.rumination_pct < 95 ? "bg-warn-500" : "bg-sig-500";
          return (
            <div key={g.name} className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
              <div className="mb-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
                <span className="metric text-xs font-semibold text-slate-200">{g.name}</span>
                <span className="metric text-[10px] text-slate-500">{g.head.toLocaleString()} hd</span>
                <span className={`pill border ${sevColor(g.heat_stress)}`}>{g.heat_stress}</span>
                <span className="metric text-[10px] text-slate-500">
                  {g.milk_yield_pct.toFixed(0)}% yield
                </span>
                {g.misters_available === 0 ? (
                  <span className="pill border border-crit-500/40 bg-crit-500/10 text-crit-400">
                    no misting
                  </span>
                ) : g.misting_enabled ? (
                  <span className="pill border border-sig-500/40 bg-sig-500/10 text-sig-400">
                    misting on
                  </span>
                ) : (
                  <span className="pill border border-ink-600/50 bg-ink-700/40 text-slate-500">
                    misting idle
                  </span>
                )}
              </div>
              <div className="grid grid-cols-[52px_1fr_52px] items-center gap-2">
                <span className="label">rum</span>
                <Bar pct={g.rumination_pct} tone={rumTone} />
                <span className={`metric text-right text-[11px] ${healthColor(g.status)}`}>
                  {g.rumination_pct.toFixed(0)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 border-t border-ink-800 pt-2 text-[10px] leading-relaxed text-slate-600">
        Phase 1 installed misting hardware in 4 of 8 barns. Cooling allocation is a
        scarcity decision, which is why it reaches the Farm Director.
      </p>
    </section>
  );
}

export function WaterPanel({ p }: { p: Packet }) {
  const e = p.environment;
  const over = e.aquifer_budget_used_pct >= 100;
  return (
    <section className="card p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Water &amp; pivots</h2>

      <div className="mb-3 rounded border border-ink-800 bg-ink-950/40 p-3">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="label">Projected annual draw vs envelope</span>
          <span className={`metric text-sm ${over ? "text-crit-400" : e.aquifer_budget_used_pct >= 85 ? "text-warn-400" : "text-sig-400"}`}>
            {e.aquifer_budget_used_pct.toFixed(1)}%
          </span>
        </div>
        <Bar pct={e.aquifer_budget_used_pct} tone={over ? "bg-crit-500" : "bg-sig-500"} />
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          Albien fossil aquifer — non-renewable. Judged on projected annual draw, not
          today&apos;s reading, because a single wet year cannot be recovered.
        </p>
      </div>

      <div className="space-y-1.5">
        {e.pivots.map((piv) => (
          <div
            key={piv.name}
            className="grid grid-cols-[62px_1fr_auto] items-center gap-2 rounded border border-ink-800 bg-ink-950/40 px-2.5 py-1.5"
          >
            <div className="min-w-0">
              <div className={`metric text-[11px] ${healthColor(piv.health)}`}>{piv.name}</div>
              <div className="text-[9px] text-slate-600">
                {piv.running ? "running" : "idle"}
              </div>
            </div>
            <div className="min-w-0">
              <div className="mb-0.5 flex justify-between text-[9px] text-slate-500">
                <span>soil {piv.soil_moisture_pct.toFixed(1)}%</span>
                <span>{piv.nozzles_blocked} blk</span>
              </div>
              <Bar
                pct={(piv.soil_moisture_pct / 38) * 100}
                tone={
                  piv.soil_moisture_pct <= 9
                    ? "bg-crit-500"
                    : piv.soil_moisture_pct < 22
                      ? "bg-warn-500"
                      : "bg-sig-500"
                }
              />
            </div>
            <div className="text-right">
              <div className={`metric text-[10px] ${healthColor(piv.health)}`}>
                {piv.bearing_temp_c.toFixed(0)}°C
              </div>
              <div className="text-[9px] text-slate-600">{piv.vibration_mm_s.toFixed(1)}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function LogisticsPanel({ p }: { p: Packet }) {
  const l = p.logistics;
  return (
    <section className="card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Feed &amp; cold chain</h2>
        <span className="label">{l.silos.length} silos</span>
      </div>

      <div className="mb-3 rounded border border-ink-800 bg-ink-950/40 p-3">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="label">Feed inventory</span>
          <span className="metric text-sm text-slate-200">
            {l.feed_hours_of_cover.toFixed(0)}h
          </span>
        </div>
        <Bar
          pct={(l.feed_hours_of_cover / 168) * 100}
          tone={
            l.feed_hours_of_cover < 24
              ? "bg-crit-500"
              : l.feed_hours_of_cover < 72
                ? "bg-warn-500"
                : "bg-sig-500"
          }
        />
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          {l.airlift.delivered.toLocaleString()} of {l.airlift.target.toLocaleString()} head
          airlifted · herd arrives before the arable programme can feed it.
        </p>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-1.5">
        {l.silos.map((s) => (
          <div key={s.name} className="rounded border border-ink-800 bg-ink-950/40 px-2.5 py-1.5">
            <div className="flex items-baseline justify-between">
              <span className="metric text-[11px] text-slate-300">{s.name}</span>
              <span className={`metric text-[10px] ${healthColor(s.status)}`}>
                {s.fill_pct.toFixed(0)}%
              </span>
            </div>
            <div className="mt-1 flex items-center gap-1">
              <div className="min-w-0 flex-1">
                <Bar
                  pct={s.fill_pct}
                  tone={
                    s.status === "critical"
                      ? "bg-crit-500"
                      : s.status === "degraded"
                        ? "bg-warn-500"
                        : "bg-sig-500"
                  }
                />
              </div>
              {s.inlet_type === "conveyor" && !s.inlet_operational && (
                <span className="pill border border-crit-500/40 bg-crit-500/10 text-crit-400">
                  stall
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-1">
        {l.tankers.map((t) => (
          <div
            key={t.name}
            className="flex items-center gap-2 rounded border border-ink-800 bg-ink-950/40 px-2.5 py-1.5"
          >
            <span className="metric text-[11px] text-slate-300">{t.name}</span>
            <span className="pill border border-ink-600/50 bg-ink-700/40 text-slate-400">
              {t.leg}
            </span>
            <span className="metric ml-auto text-[11px] text-slate-300">
              {(t.load_kg / 1000).toFixed(1)} t
            </span>
            <span
              className={`metric w-14 text-right text-[11px] ${
                t.coolant_temp_c > 8
                  ? "text-crit-400"
                  : t.coolant_temp_c > 6.5
                    ? "text-warn-400"
                    : "text-sig-500"
              }`}
            >
              {t.coolant_temp_c.toFixed(1)}°C
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function TraceFeed({ trace }: { trace: TraceEvent[] }) {
  return (
    <section className="card flex max-h-[560px] flex-col p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Agent trace</h2>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
        {trace.length === 0 && (
          <p className="text-xs text-slate-600">Awaiting first tick…</p>
        )}
        {trace.map((t, i) => (
          <div key={i} className="rounded border border-ink-800 bg-ink-950/40 px-2.5 py-1.5">
            <div className="flex items-baseline gap-2">
              <span
                className={`metric text-[10px] font-semibold uppercase tracking-wider ${AGENT_COLOR[t.agent] ?? "text-slate-400"}`}
              >
                {t.agent}
              </span>
              <span className="label">{t.phase}</span>
            </div>
            <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{t.message}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function FindingsPanel({
  findings,
}: {
  findings: { agent: string; summary: string; severity: string; implies: string; confidence: number }[];
}) {
  return (
    <section className="card p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Findings</h2>
      <div className="max-h-[300px] space-y-1.5 overflow-y-auto">
        {findings.length === 0 && (
          <p className="text-xs text-slate-600">No findings this tick.</p>
        )}
        {findings.map((f, i) => (
          <div key={i} className="rounded border border-ink-800 bg-ink-950/40 px-2.5 py-2">
            <div className="mb-1 flex items-center gap-2">
              <span className={`pill border ${sevColor(f.severity)}`}>{f.severity}</span>
              <span className={`metric text-[10px] ${AGENT_COLOR[f.agent] ?? "text-slate-400"}`}>
                {f.agent}
              </span>
              {f.implies && (
                <span className="label ml-auto">→ {f.implies}</span>
              )}
            </div>
            <p className="text-[11px] leading-relaxed text-slate-400">{f.summary}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function EventsPanel({ p }: { p: Packet }) {
  return (
    <section className="card p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Site events</h2>
      <div className="space-y-1.5">
        {p.events.length === 0 && <p className="text-xs text-slate-600">Quiet.</p>}
        {[...p.events].reverse().map((e, i) => (
          <div key={i} className="flex items-start gap-2.5">
            <span className="metric shrink-0 text-[10px] text-slate-600">{e.time}</span>
            <span className={`pill shrink-0 border ${sevColor(e.severity)}`}>{e.kind}</span>
            <span className="text-[11px] leading-relaxed text-slate-400">{e.message}</span>
          </div>
        ))}
      </div>
    </section>
  );
}