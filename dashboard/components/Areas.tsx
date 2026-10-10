"use client";

import type { Packet } from "@/lib/types";
import { healthColor } from "@/lib/types";

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

function AreaHeader({
  title,
  area,
  status,
  right,
}: {
  title: string;
  area: string;
  status: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <span className="rounded bg-ink-700 px-1.5 py-0.5 text-[9px] font-bold tracking-[0.16em] text-slate-400">
        {area}
      </span>
      <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
      <span className={`pill border ${status === "nominal" ? "border-sig-500/30 bg-sig-500/10 text-sig-500" : status === "degraded" ? "border-warn-500/40 bg-warn-500/10 text-warn-400" : "border-crit-500/40 bg-crit-500/10 text-crit-400"}`}>
        {status}
      </span>
      {right && <span className="label ml-auto">{right}</span>}
    </div>
  );
}

/* ------------------------------------------------------------------ CROP */

export function CropArea({ p }: { p: Packet }) {
  const c = p.crop_production;
  const pctOfTarget = (c.standing_t / c.annual_target_t) * 100;
  return (
    <section className="card p-4">
      <AreaHeader title="Crop production" area="AREA 1" status={c.status} right={`${c.fields.length} fields`} />

      <div className="mb-3 grid grid-cols-3 gap-2">
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="label">Standing DM</div>
          <div className="metric text-lg text-slate-100">
            {c.standing_t.toFixed(0)}
            <span className="ml-1 text-[10px] text-slate-500">t</span>
          </div>
          <Bar pct={pctOfTarget} tone={pctOfTarget < 10 ? "bg-crit-500" : "bg-sig-500"} />
        </div>
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="label">Harvested</div>
          <div className="metric text-lg text-slate-100">
            {c.harvested_t.toFixed(0)}
            <span className="ml-1 text-[10px] text-slate-500">t · {c.cuts_completed} cuts</span>
          </div>
        </div>
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="label">Crude protein</div>
          <div className="metric text-lg text-slate-100">
            {c.protein_pct.toFixed(1)}
            <span className="ml-1 text-[10px] text-slate-500">%</span>
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        {c.fields.map((f) => {
          const dry = f.soil_moisture_pct <= 9;
          return (
            <div key={f.field_id} className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
              <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="metric text-xs font-semibold text-slate-200">{f.field_id}</span>
                <span className="text-[10px] text-slate-500">{f.crop.replace("_", " ")}</span>
                <span className="metric text-[10px] text-slate-500">{f.area_ha.toFixed(0)} ha</span>
                {f.ready_for_cut && (
                  <span className="pill border border-sig-500/40 bg-sig-500/10 text-sig-400">
                    cut-ready
                  </span>
                )}
                {f.water_stress_days > 0 && (
                  <span className="pill border border-crit-500/40 bg-crit-500/10 text-crit-400">
                    water-stress {f.water_stress_days}d
                  </span>
                )}
                <span className={`metric ml-auto text-[11px] ${healthColor(f.health)}`}>
                  {f.biomass_t_ha.toFixed(1)} t DM/ha
                </span>
              </div>
              <div className="grid grid-cols-[46px_1fr_46px] items-center gap-2">
                <span className="label">soil</span>
                <Bar
                  pct={(f.soil_moisture_pct / 38) * 100}
                  tone={dry ? "bg-crit-500" : f.soil_moisture_pct < 22 ? "bg-warn-500" : "bg-sig-500"}
                />
                <span className={`metric text-right text-[11px] ${healthColor(f.health)}`}>
                  {f.soil_moisture_pct.toFixed(1)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 border-t border-ink-800 pt-2 text-[10px] leading-relaxed text-slate-600">
        Below the 9% wilting point biomass accrual is <em>zero</em> — a missed irrigation is a
        permanent loss for that season, not a delay.
      </p>
    </section>
  );
}

/* -------------------------------------------------------------- LIVESTOCK */

export function LivestockArea({ p }: { p: Packet }) {
  const l = p.livestock;
  const nonProdPct = (l.non_productive_head / Math.max(l.total_head, 1)) * 100;
  return (
    <section className="card p-4">
      <AreaHeader
        title="Livestock"
        area="AREA 2"
        status={l.status}
        right={`${l.total_head.toLocaleString()} head`}
      />

      <div className="mb-3 rounded border border-warn-500/25 bg-warn-500/5 p-2.5">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="label text-warn-400">Non-productive head</span>
          <span className="metric text-sm text-warn-400">{nonProdPct.toFixed(0)}%</span>
        </div>
        <Bar pct={nonProdPct} tone="bg-warn-500" />
        <p className="mt-2 text-[10px] leading-relaxed text-slate-400">
          {l.non_productive_head.toLocaleString()} of {l.total_head.toLocaleString()} head eat
          feed but produce no milk. The airlifted cohort is{" "}
          <span className="text-slate-300">
            {(l.airlift_mix.heifer ?? 0).toLocaleString()} heifers
          </span>{" "}
          and {(l.airlift_mix.dry ?? 0).toLocaleString()} dry cows — a heifer does not milk for
          roughly 18 months after landing.
        </p>
      </div>

      <div className="label mb-1.5">Heifers — breeding weight</div>
      <div className="mb-3 space-y-1.5">
        {l.heifers.map((g) => {
          const ok = g.weight_pct_of_target >= 88;
          return (
            <div key={g.group_id} className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
              <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="metric text-xs font-semibold text-slate-200">{g.group_id}</span>
                <span className="metric text-[10px] text-slate-500">{g.head.toLocaleString()} hd</span>
                <span className="text-[10px] text-slate-500">{g.age_months.toFixed(0)} mo</span>
                {g.pregnant && (
                  <span className="pill border border-sig-500/40 bg-sig-500/10 text-sig-400">
                    pregnant
                  </span>
                )}
                <span className={`metric ml-auto text-[11px] ${healthColor(g.status)}`}>
                  {g.weight_pct_of_target.toFixed(0)}% target
                </span>
              </div>
              <Bar
                pct={(g.weight_pct_of_target / 110) * 100}
                tone={ok ? "bg-sig-500" : "bg-warn-500"}
              />
              <div className="mt-1 flex justify-between text-[9px] text-slate-600">
                <span>
                  {g.avg_weight_kg.toFixed(0)} / {g.target_weight_kg} kg
                </span>
                <span>+{g.daily_gain_kg.toFixed(2)} kg/d</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="label mb-1">Calves</div>
          {l.calves.length === 0 && <p className="text-[10px] text-slate-600">None in system.</p>}
          {l.calves.map((c) => (
            <div key={c.group_id} className="rounded border border-ink-800 bg-ink-950/40 p-2">
              <div className="flex items-baseline justify-between">
                <span className="metric text-[11px] text-slate-300">{c.group_id}</span>
                <span className={`metric text-[10px] ${healthColor(c.status)}`}>
                  {c.scours_rate_pct.toFixed(1)}% scours
                </span>
              </div>
              <div className="text-[9px] text-slate-600">
                {c.head.toLocaleString()} hd · {c.age_days.toFixed(0)}d · {c.mortality_7d} mort
              </div>
            </div>
          ))}
        </div>
        <div>
          <div className="label mb-1">Dry cows</div>
          {l.dry_cows.length === 0 && <p className="text-[10px] text-slate-600">None.</p>}
          {l.dry_cows.map((c) => (
            <div key={c.group_id} className="rounded border border-ink-800 bg-ink-950/40 p-2">
              <div className="flex items-baseline justify-between">
                <span className="metric text-[11px] text-slate-300">{c.group_id}</span>
                <span className={`metric text-[10px] ${healthColor(c.status)}`}>
                  {c.days_to_calving.toFixed(0)}d to calving
                </span>
              </div>
              <div className="text-[9px] text-slate-600">
                {c.head.toLocaleString()} hd · BCS {c.bcs.toFixed(1)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ MILK */

export function MilkArea({ p }: { p: Packet }) {
  const m = p.milk_production;
  const sccTone = m.bulk_scc_k > 300 ? "bg-crit-500" : m.bulk_scc_k > m.scc_limit_k ? "bg-warn-500" : "bg-sig-500";
  const tempTone = m.bulk_temp_c > 8 ? "bg-crit-500" : m.bulk_temp_c > 6.5 ? "bg-warn-500" : "bg-sig-500";
  return (
    <section className="card p-4">
      <AreaHeader
        title="Milk production"
        area="AREA 3"
        status={m.status}
        right={`${m.milkings_per_day}× daily · ${m.units} units`}
      />

      <div className="mb-3 grid grid-cols-2 gap-2">
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="label">Daily production</div>
          <div className="metric text-lg text-slate-100">
            {(m.daily_milk_kg / 1000).toFixed(1)}
            <span className="ml-1 text-[10px] text-slate-500">t/day</span>
          </div>
          <div className="text-[9px] text-slate-600">
            capture {m.capture_ratio.toFixed(0)}% · loss {(m.daily_loss_kg / 1000).toFixed(2)} t
          </div>
        </div>
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="label">Bulk SCC</div>
          <div
            className={`metric text-lg ${m.bulk_scc_k > m.scc_limit_k ? "text-warn-400" : "text-slate-100"}`}
          >
            {m.bulk_scc_k.toFixed(0)}
            <span className="ml-1 text-[10px] text-slate-500">k / limit {m.scc_limit_k}</span>
          </div>
          <Bar pct={(m.bulk_scc_k / 400) * 100} tone={sccTone} />
        </div>
      </div>

      <div className="space-y-2">
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="label">Parlour</span>
            <span className={`metric text-[11px] ${healthColor(m.downtime_min_24h > 180 ? "critical" : m.downtime_min_24h > 60 ? "degraded" : "nominal")}`}>
              {m.downtime_min_24h.toFixed(0)} min downtime
            </span>
          </div>
          <div className="text-[9px] text-slate-600">
            {m.throughput_cows_per_hour.toFixed(0)} cows/h × {m.units} units
          </div>
        </div>

        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="label">Bulk tank</span>
            <span className={`metric text-[11px] ${m.bulk_temp_c > 6.5 ? "text-warn-400" : "text-sig-400"}`}>
              {m.bulk_temp_c.toFixed(1)}°C
            </span>
          </div>
          <Bar pct={m.bulk_fill_pct} tone={tempTone} />
          <div className="mt-1 flex justify-between text-[9px] text-slate-600">
            <span>{(m.bulk_tank_kg / 1000).toFixed(1)} t held ({m.bulk_fill_pct.toFixed(0)}%)</span>
            <span>condenser {m.condenser_fouling_pct.toFixed(0)}% fouled</span>
          </div>
        </div>

        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="label">Powder silo</span>
            <span className="metric text-[11px] text-slate-300">{m.silo_fill_pct.toFixed(0)}%</span>
          </div>
          <Bar
            pct={m.silo_fill_pct}
            tone={m.silo_fill_pct > 92 ? "bg-crit-500" : "bg-sig-500"}
          />
          <div className="mt-1 text-[9px] text-slate-600">
            {m.powder_live ? "commissioned" : "pre-commissioning — first production late 2027"}
          </div>
        </div>
      </div>
      <p className="mt-3 border-t border-ink-800 pt-2 text-[10px] leading-relaxed text-slate-600">
        Volume and quality are separate failures. The parlour can run at full throughput with the
        load still rejected on SCC — which originates in the barns, not the plant.
      </p>
    </section>
  );
}