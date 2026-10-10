"use client";

import type { Packet } from "@/lib/types";
import { AreaId, GLOSSARY, LEVEL_LABEL, LEVEL_STYLE, explainAquifer, explainBulkTemp, explainCropHealth, explainFeed, explainHeiferWeight, explainHeatLoad, explainMisting, explainParlour, explainRumination, explainScours, explainScc, explainSoilMoisture } from "@/lib/explain";
import { PlainNote, Term } from "@/components/AreaNav";
import { MeshBoard } from "@/components/Mesh";

function Bar({ pct, tone = "bg-sig-500" }: { pct: number; tone?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
      <div
        className={`h-full rounded-full transition-all duration-700 ${tone}`}
        style={{ width: `${Math.max(1, Math.min(100, pct))}%` }}
      />
    </div>
  );
}

function Row({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-ink-800 py-1.5 last:border-0">
      <span className="label">{label}</span>
      <span className="text-right">
        <span className="metric text-xs text-slate-200">{value}</span>
        {sub && <span className="ml-1.5 text-[10px] text-slate-500">{sub}</span>}
      </span>
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="card p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">
        {title}
        {hint && <span className="ml-2 text-[10px] font-normal text-slate-500">{hint}</span>}
      </h3>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------- CROP */

function CropDetail({ p }: { p: Packet }) {
  const c = p.crop_production;
  return (
    <div className="space-y-4">
      <Section title="Each field" hint="click a metric to learn what it means">
        <div className="space-y-2">
          {c.fields.map((f) => {
            const soil = explainSoilMoisture(f.soil_moisture_pct);
            const growth = explainCropHealth(f.health, f.water_stress_days);
            return (
              <div key={f.field_id} className="rounded border border-ink-800 bg-ink-950/40 p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="metric text-xs font-semibold text-slate-100">{f.field_id}</span>
                  <span className="text-[11px] text-slate-400">{f.crop.replace(/_/g, " ")}</span>
                  <span className="metric text-[10px] text-slate-500">{f.area_ha.toFixed(0)} ha</span>
                  {f.ready_for_cut && (
                    <span className="pill border border-sig-500/40 bg-sig-500/10 text-sig-400">
                      ready to cut
                    </span>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <div className="mb-1 flex items-baseline justify-between">
                      <span className="label">Soil water</span>
                      <span className="metric text-[11px] text-slate-300">
                        {f.soil_moisture_pct.toFixed(1)}%
                      </span>
                    </div>
                    <Bar
                      pct={(f.soil_moisture_pct / 38) * 100}
                      tone={
                        f.soil_moisture_pct <= 9
                          ? "bg-crit-500"
                          : f.soil_moisture_pct < 22
                            ? "bg-warn-500"
                            : "bg-sig-500"
                      }
                    />
                    <p className="mt-1.5 text-[10px] leading-relaxed text-slate-400">{soil.line}</p>
                  </div>
                  <div>
                    <div className="mb-1 flex items-baseline justify-between">
                      <span className="label">
                        <Term term={GLOSSARY["Standing DM"]}>Crop mass</Term>
                      </span>
                      <span className="metric text-[11px] text-slate-300">
                        {f.biomass_t_ha.toFixed(1)} t/ha
                      </span>
                    </div>
                    <Bar
                      pct={(f.biomass_t_ha / 20) * 100}
                      tone={f.biomass_t_ha < 1 ? "bg-crit-500" : "bg-sig-500"}
                    />
                    <p className="mt-1.5 text-[10px] leading-relaxed text-slate-400">{growth.line}</p>
                  </div>
                </div>

                {f.water_stress_days > 0 && (
                  <p className="mt-2 border-t border-ink-800 pt-2 text-[10px] text-crit-400">
                    {f.water_stress_days} consecutive day
                    {f.water_stress_days === 1 ? "" : "s"} without enough water — growth stopped.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Programme totals">
          <Row label="Forage standing" value={`${Math.round(c.standing_t).toLocaleString()} t`} />
          <Row label="Harvested so far" value={`${Math.round(c.harvested_t).toLocaleString()} t`} sub={`${c.cuts_completed} cuts`} />
          <Row label="Fields run dry" value={`${c.water_stressed_ha.toFixed(0)} ha`} />
          <Row label="Average protein" value={`${c.protein_pct.toFixed(1)}%`} />
          <Row label="Annual target" value={`${(c.annual_target_t / 1e6).toFixed(1)} Mt`} />
        </Section>
        <Section title="Why this area is hard">
          <p className="text-xs leading-relaxed text-slate-400">
            The whole forage programme has to be grown with groundwater that does not refill. The
            project&apos;s own numbers imply roughly{" "}
            <span className="text-slate-200">2.1 kg of crop per cubic metre of water</span>.
            That ratio is the entire feasibility question, and it is why a missed irrigation is
            treated as a permanent loss rather than a delay.
          </p>
        </Section>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- LIVESTOCK */

function LivestockDetail({ p }: { p: Packet }) {
  const l = p.livestock;
  const nonProdPct = (l.non_productive_head / Math.max(l.total_head, 1)) * 100;
  return (
    <div className="space-y-4">
      <PlainNote
        plain={{
          line: `${nonProdPct.toFixed(0)}% of the animals on site produce no milk yet.`,
          because:
            "Most of the herd is heifers and calves. They arrived from the United States and will not start giving milk for roughly 18 months. Until then they eat feed and water without paying anything back — that is the real cash-flow shape of this project.",
          level: "watch",
        }}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Herd structure">
          <Row label="Total animals" value={l.total_head.toLocaleString()} />
          <Row label="Producing milk" value={l.lactating_head.toLocaleString()} />
          <Row label="Not producing yet" value={l.non_productive_head.toLocaleString()} />
          {Object.entries(l.by_class).map(([k, v]) => (
            <Row key={k} label={k.replace("_", " ")} value={v.toLocaleString()} />
          ))}
        </Section>

        <Section title="What arrived by air" hint="109 flights from 9 US states">
          <Row label="Animals airlifted" value={l.airlift_head.toLocaleString()} />
          {Object.entries(l.airlift_mix).map(([k, v]) => (
            <Row key={k} label={k} value={v.toLocaleString()} />
          ))}
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            Livestock exporters sell breeding animals, so the shipment is mostly heifers and dry
            cows — not cows in milk. That is why the projected milk yield takes years to arrive.
          </p>
        </Section>
      </div>

      <Section title="Heifers — growth toward breeding weight" hint="target 570 kg at 23 months">
        <div className="space-y-2">
          {l.heifers.map((g) => {
            const w = explainHeiferWeight(g.weight_pct_of_target);
            return (
              <div key={g.group_id} className="rounded border border-ink-800 bg-ink-950/40 p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="metric text-xs font-semibold text-slate-100">{g.group_id}</span>
                  <span className="metric text-[10px] text-slate-500">
                    {g.head.toLocaleString()} head
                  </span>
                  <span className="text-[10px] text-slate-500">{g.age_months.toFixed(0)} months old</span>
                  {g.pregnant && (
                    <span className="pill border border-sig-500/40 bg-sig-500/10 text-sig-400">
                      pregnant
                    </span>
                  )}
                  <span className={`pill ml-auto border ${LEVEL_STYLE[w.level]}`}>
                    {LEVEL_LABEL[w.level]}
                  </span>
                </div>
                <Bar
                  pct={(g.weight_pct_of_target / 110) * 100}
                  tone={g.weight_pct_of_target >= 88 ? "bg-sig-500" : "bg-warn-500"}
                />
                <div className="mt-1.5 flex justify-between text-[10px] text-slate-500">
                  <span>
                    {g.avg_weight_kg.toFixed(0)} of {g.target_weight_kg} kg ({g.weight_pct_of_target.toFixed(0)}%)
                  </span>
                  <span>gaining {g.daily_gain_kg.toFixed(2)} kg/day</span>
                </div>
                <p className="mt-1.5 text-[10px] leading-relaxed text-slate-400">{w.line}</p>
              </div>
            );
          })}
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Calves">
          {l.calves.length === 0 && (
            <p className="text-xs text-slate-500">No calves in the system right now.</p>
          )}
          {l.calves.map((c) => {
            const s = explainScours(c.scours_rate_pct);
            return (
              <div key={c.group_id} className="mb-2 rounded border border-ink-800 bg-ink-950/40 p-3 last:mb-0">
                <div className="mb-1 flex items-center gap-2">
                  <span className="metric text-xs text-slate-100">{c.group_id}</span>
                  <span className="metric text-[10px] text-slate-500">{c.head.toLocaleString()} hd</span>
                  <span className={`pill ml-auto border ${LEVEL_STYLE[s.level]}`}>{LEVEL_LABEL[s.level]}</span>
                </div>
                <p className="text-[11px] text-slate-400">{s.line}</p>
              </div>
            );
          })}
        </Section>
        <Section title="Dry cows — waiting to calve">
          {l.dry_cows.length === 0 && (
            <p className="text-xs text-slate-500">None in the dry period.</p>
          )}
          {l.dry_cows.map((c) => (
            <div key={c.group_id} className="mb-2 rounded border border-ink-800 bg-ink-950/40 p-3 last:mb-0">
              <div className="flex items-baseline justify-between">
                <span className="metric text-xs text-slate-100">{c.group_id}</span>
                <span className="metric text-[11px] text-slate-300">
                  {c.days_to_calving.toFixed(0)} days to calving
                </span>
              </div>
              <div className="text-[10px] text-slate-500">
                {c.head.toLocaleString()} head · body condition {c.bcs.toFixed(1)} / 5
              </div>
            </div>
          ))}
        </Section>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- MILK */

function MilkDetail({ p }: { p: Packet }) {
  const m = p.milk_production;
  const scc = explainScc(m.bulk_scc_k, m.scc_limit_k);
  const temp = explainBulkTemp(m.bulk_temp_c);
  const parl = explainParlour(m.downtime_min_24h);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <Section title="Output">
          <div className="mb-2">
            <div className="metric text-3xl text-slate-100">{(m.daily_milk_kg / 1000).toFixed(1)}</div>
            <div className="text-[11px] text-slate-500">tonnes per day</div>
          </div>
          <Row label="Collected" value={`${m.capture_ratio.toFixed(0)}%`} />
          <Row label="Lost in the chain" value={`${(m.daily_loss_kg / 1000).toFixed(2)} t`} />
          <Row label="From" value={`${m.lactating_head.toLocaleString()} head`} />
        </Section>

        <Section title="Quality">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="label">
              <Term term={GLOSSARY["SCC"]}>Cell count</Term>
            </span>
            <span
              className={`metric text-lg ${m.bulk_scc_k > m.scc_limit_k ? "text-warn-400" : "text-sig-400"}`}
            >
              {m.bulk_scc_k.toFixed(0)}k
            </span>
          </div>
          <Bar pct={(m.bulk_scc_k / 400) * 100} tone={m.bulk_scc_k > m.scc_limit_k ? "bg-warn-500" : "bg-sig-500"} />
          <div className="mt-1 text-right text-[10px] text-slate-500">legal limit {m.scc_limit_k}k</div>
          <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{scc.line}</p>
        </Section>

        <Section title="Cold chain">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="label">Bulk tank</span>
            <span className={`metric text-lg ${m.bulk_temp_c > 6.5 ? "text-warn-400" : "text-sig-400"}`}>
              {m.bulk_temp_c.toFixed(1)}°C
            </span>
          </div>
          <Bar pct={m.bulk_fill_pct} tone={m.bulk_temp_c > 8 ? "bg-crit-500" : "bg-sig-500"} />
          <div className="mt-1 flex justify-between text-[10px] text-slate-500">
            <span>{(m.bulk_tank_kg / 1000).toFixed(1)} t held</span>
            <span>refrigerator {m.condenser_fouling_pct.toFixed(0)}% fouled</span>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{temp.line}</p>
        </Section>
      </div>

      <Section title="Parlour" hint={`${m.milkings_per_day}× daily, ${m.units} units`}>
        <Row label="Throughput" value={`${m.throughput_cows_per_hour.toFixed(0)} cows/h`} />
        <Row label="Lost time today" value={`${m.downtime_min_24h.toFixed(0)} min`} />
        <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{parl.line}</p>
      </Section>

      <Section title="Powder plant">
        <Row label="Silo full" value={`${m.silo_fill_pct.toFixed(0)}%`} />
        <Row
          label="Status"
          value={m.powder_live ? "Commissioned" : "Pre-commissioning"}
        />
        <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
          On the real project the powder line is not running yet — first production is targeted
          for late 2027. Until then milk leaves as liquid product.
        </p>
      </Section>
    </div>
  );
}

/* ---------------------------------------------------------- INFRASTRUCTURE */

function InfraDetail({ p }: { p: Packet }) {
  const e = p.environment;
  const aq = explainAquifer(e.aquifer_budget_used_pct);
  const heat = explainHeatLoad(e.effective_heat_load, e.heat_stress_band);
  const feed = explainFeed(p.logistics.feed_hours_of_cover);
  const mist = explainMisting(e.misters_on, 4, 8);
  return (
    <div className="space-y-4">
      <PlainNote plain={heat} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="The water" hint="the site's binding constraint">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="label">Yearly budget used</span>
            <span className={`metric text-lg ${e.aquifer_budget_used_pct >= 100 ? "text-crit-400" : e.aquifer_budget_used_pct >= 85 ? "text-warn-400" : "text-sig-400"}`}>
              {e.aquifer_budget_used_pct.toFixed(1)}%
            </span>
          </div>
          <Bar
            pct={e.aquifer_budget_used_pct}
            tone={e.aquifer_budget_used_pct >= 100 ? "bg-crit-500" : e.aquifer_budget_used_pct >= 85 ? "bg-warn-500" : "bg-sig-500"}
          />
          <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{aq.line}</p>
          <Row label="Drawing now" value={`${e.water_use_m3h.toFixed(0)} m³/h`} />
          <Row label="Wells completed" value="45" sub="186 permits" />
        </Section>

        <Section title="Cooling hardware" hint="the real bottleneck on this site">
          <Row label="Barns with misting" value="4 of 8" />
          <Row label="Currently running" value={e.misters_on ? "Yes" : "No"} />
          <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{mist.line}</p>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            {mist.because}
          </p>
        </Section>
      </div>

      <Section title="Pivots">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {e.pivots.map((piv) => (
            <div
              key={piv.name}
              className="rounded border border-ink-800 bg-ink-950/40 p-2.5"
            >
              <div className="mb-1 flex items-baseline justify-between">
                <span
                  className={`metric text-[11px] ${piv.health === "nominal" ? "text-sig-400" : piv.health === "degraded" ? "text-warn-400" : "text-crit-400"}`}
                >
                  {piv.name}
                </span>
                <span className="text-[10px] text-slate-500">{piv.running ? "running" : "idle"}</span>
              </div>
              <div className="mb-1 flex justify-between text-[9px] text-slate-500">
                <span>soil {piv.soil_moisture_pct.toFixed(1)}%</span>
                <span>{piv.nozzles_blocked} blocked</span>
              </div>
              <Bar
                pct={(piv.soil_moisture_pct / 38) * 100}
                tone={piv.soil_moisture_pct <= 9 ? "bg-crit-500" : piv.soil_moisture_pct < 22 ? "bg-warn-500" : "bg-sig-500"}
              />
              <div className="mt-1 flex justify-between text-[9px] text-slate-600">
                <span>{piv.bearing_temp_c.toFixed(0)}°C</span>
                <span>{piv.vibration_mm_s.toFixed(1)} mm/s</span>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Feed">
        <Row label="In store" value={`${Math.round(p.logistics.feed_total_t).toLocaleString()} t`} />
        <Row label="Days of cover" value={`${(p.logistics.feed_hours_of_cover / 24).toFixed(1)}`} />
        <Row label="Daily requirement" value={`${p.logistics.daily_demand_t.toFixed(1)} t`} />
        <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{feed.line}</p>
      </Section>
    </div>
  );
}

/* ---------------------------------------------------------------- ROUTER */

export function AreaDetail({ p, area }: { p: Packet; area: AreaId }) {
  if (area === "crop") return <CropDetail p={p} />;
  if (area === "livestock") return <LivestockDetail p={p} />;
  if (area === "milk") return <MilkDetail p={p} />;
  if (area === "infrastructure") return <InfraDetail p={p} />;
  return (
    <div className="space-y-4">
      <PlainNote
        plain={{
          line: "The specialists are not independent dashboards — they argue with each other.",
          because:
            "A cooling decision belongs to the herd specialist, but whether the water and the hardware exist belongs to the agronomist and the logistics agent. The system routes those questions between them and only escalates to a human once they have answered each other.",
          level: "ok",
        }}
      />
      <MeshBoard p={p} />
    </div>
  );
}
