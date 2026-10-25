"use client";

import { AgentGlyph } from "@/components/Icons";
import { LiveNumber } from "@/components/Live";
import { agent } from "@/lib/identity";
import type { Packet, Summary } from "@/lib/types";
import { Status, STATUS_WORD, statusColour, TERM } from "@/lib/language";

/**
 * The simplified home screen.
 *
 * Design intent: a first-time visitor should understand this in under fifteen
 * seconds without reading a single number. One status sentence, three cards,
 * everything numeric behind a disclosure.
 *
 * Restyled to match the agents view: each card inherits the identity colour and
 * glyph of the specialist that owns that part of the farm, and the headline
 * number flashes when it changes, so the screen reads as live rather than as a
 * screenshot of a report.
 */

const TONE: Record<Status, "ok" | "act" | "stop"> = {
  good: "ok",
  watch: "act",
  act: "act",
  stop: "stop",
};

export function StatusPill({ s }: { s: Status }) {
  return <span className={`pill border ${statusColour(s)}`}>{STATUS_WORD[s]}</span>;
}

function Card(props: {
  agentId: string;
  title: string;
  big: number;
  bigUnit: string;
  bigDp?: number;
  sub: string;
  status: Status;
  detail: string;
  term: string;
  onClick: () => void;
}) {
  const ident = agent(props.agentId);
  const tone = TONE[props.status];
  const railHex =
    props.status === "stop" ? "#f87171" : props.status === "good" ? `${ident.hex}66` : ident.hex;

  return (
    <button
      onClick={props.onClick}
      className="card rail group flex h-full w-full flex-col p-4 text-left transition-all duration-300 hover:-translate-y-0.5"
      style={{ ["--agent" as string]: railHex }}
    >
      <div className="flex items-start gap-3">
        <AgentGlyph id={props.agentId} className="mt-0.5 h-5 w-5 shrink-0" strokeWidth={1.6} />
        <div className="min-w-0 flex-1">
          <div className="text-[12.5px] font-medium text-slate-400">{props.title}</div>
          <div
            className="metric mt-0.5 text-[27px] font-bold leading-none tracking-tightest text-slate-50"
            style={{ color: ident.hex }}
          >
            <LiveNumber value={props.big} unit={props.bigUnit} dp={props.bigDp} tone={tone} />
          </div>
          <div className="mt-1 text-[11px] leading-snug text-slate-500">{props.sub}</div>
        </div>
        <StatusPill s={props.status} />
      </div>

      <p className="mt-3 text-[12.5px] leading-relaxed text-slate-400">{props.detail}</p>

      <details className="mt-auto w-full pt-2" onClick={(e) => e.stopPropagation()}>
        <summary className="cursor-pointer text-[10px] text-slate-600 transition hover:text-slate-400">
          What does this mean?
        </summary>
        <p className="mt-1.5 rounded border border-white/[0.06] bg-ink-950/60 p-2 text-[11px] leading-relaxed text-slate-400">
          {props.term}
        </p>
      </details>
    </button>
  );
}

/* ------------------------------------------------------------ status logic */

export function overallStatus(s: Summary, pending: boolean): Status {
  if (pending) return "act";
  if (s.heat_stress_band === "severe") return "stop";
  if (s.heat_stress_band === "moderate") return "act";
  if (s.aquifer_pct >= 100) return "stop";
  if (s.aquifer_pct >= 85) return "act";
  if (s.feed_hours < 24) return "stop";
  if (s.rumination_deficit >= 10 || s.feed_hours < 72 || s.aquifer_pct >= 60) return "watch";
  return "good";
}

export function headline(s: Summary, pending: boolean): { text: string; sub: string } {
  if (pending) {
    return {
      text: "There's a decision waiting for you.",
      sub: "The farm has paused until you choose. Nothing else will happen until you do.",
    };
  }
  if (s.heat_stress_band === "severe") {
    return {
      text: "The heat is dangerous for the cows right now.",
      sub: "They can't cool themselves down. The herd team is watching it closely.",
    };
  }
  if (s.heat_stress_band === "moderate") {
    return {
      text: "The cows are hot and losing milk.",
      sub: "Not dangerous yet, but it needs sorting out today.",
    };
  }
  if (s.aquifer_pct >= 85) {
    return {
      text: "The farm is using a lot of underground water.",
      sub: "This water never refills, so it has to be managed carefully.",
    };
  }
  if (s.feed_hours < 72) {
    return {
      text: "Food for the cows is running low.",
      sub: "There's enough for a few days. More is on its way.",
    };
  }
  return {
    text: "Everything is running normally.",
    sub: "The cows, the fields and the milking are all where they should be.",
  };
}

/* ---------------------------------------------------------------- the three */

export function CowFoodCard({ p, onClick }: { p: Packet; onClick: () => void }) {
  const c = p.crop_production;
  const n = c.fields.length;
  const dry = c.fields.filter((f) => f.soil_moisture_pct <= 9).length;
  const drying = c.fields.filter(
    (f) => f.soil_moisture_pct > 9 && f.soil_moisture_pct < 22,
  ).length;
  const status: Status = dry > 0 ? "stop" : drying > 0 ? "watch" : "good";
  const tonnes = Math.round(c.standing_t);
  const cut = Math.round(c.harvested_t).toLocaleString();

  const detail =
    status === "stop"
      ? dry + " of " + n + " fields have run out of water and the crop has stopped growing. This is a permanent loss for this season, not a delay."
      : status === "watch"
        ? drying + " fields are drying out and will need water soon. Everything else is growing well."
        : "All " + n + " fields have enough water. " + tonnes.toLocaleString() + " tonnes of feed is growing right now.";

  const cropTerm =
    TERM["Standing DM"] +
    " Feed grows here and is cut for silage, then stored and fed to the cows all year." +
    (c.harvested_t > 0 ? " " + cut + " tonnes have been cut and stored so far." : "");

  return (
    <Card
      agentId="crop"
      title="Food for the cows"
      big={tonnes}
      bigUnit="t"
      sub="of feed growing in the fields"
      status={status}
      detail={detail}
      term={cropTerm}
      onClick={onClick}
    />
  );
}

export function HerdCard({ p, onClick }: { p: Packet; onClick: () => void }) {
  const l = p.livestock;
  const nonProd = (l.non_productive_head / Math.max(l.total_head, 1)) * 100;
  const deficient = l.heifers.filter((h) => h.weight_pct_of_target < 88);
  const status: Status = deficient.length > 2 ? "watch" : "good";

  const under = deficient.reduce((a, h) => a + h.head, 0).toLocaleString();
  const herdDetail =
    deficient.length > 0
      ? under +
        " young cows are a bit under the weight they need to have a calf on schedule. A small feed adjustment now saves a whole cycle later."
      : "The cows, calves and young stock are all where they should be. Most of them are heifers, animals that arrived by air and will start giving milk in about 18 months.";

  const herdTerm = [TERM.Heifer, TERM["Breeding weight"], TERM["Dry cow"]].join(" ");

  return (
    <Card
      agentId="calving"
      title="The herd"
      big={l.total_head}
      bigUnit=""
      sub={"animals on the farm · " + nonProd.toFixed(0) + "% not giving milk yet"}
      status={status}
      detail={herdDetail}
      term={herdTerm}
      onClick={onClick}
    />
  );
}

export function MilkCard({ p, onClick }: { p: Packet; onClick: () => void }) {
  const m = p.milk_production;
  const tooWarm = m.bulk_temp_c > 8;
  const badScc = m.bulk_scc_k > 300;
  const poorScc = m.bulk_scc_k > m.scc_limit_k;
  const lostTime = m.downtime_min_24h > 180;
  const someTime = m.downtime_min_24h > 60;

  const status: Status = tooWarm || badScc || lostTime
    ? "stop"
    : poorScc || someTime
      ? "act"
      : "good";

  const milkDetail =
    status === "stop"
      ? tooWarm
        ? "The milk waiting in the cooler is too warm and would be rejected. That milk would be lost entirely."
        : "Milk quality has dropped well outside the legal limit, or milking has lost a lot of time today."
      : status === "act"
        ? poorScc
          ? "Milk quality has drifted outside the legal limit. The cause is infection in the cows, not the plant."
          : "The milking equipment has lost time today. Every minute is a cow milked late, which costs milk for the whole lactation."
        : "The cows are being milked on time, the milk is kept cold, and it is within quality limits. " +
          m.capture_ratio.toFixed(0) +
          "% of what the herd produced has been collected.";

  const milkTerm = [
    TERM.Parlour,
    TERM["Bulk tank"],
    TERM["Somatic cell count"],
    TERM["Spray dryer"],
  ].join(" ");

  return (
    <Card
      agentId="milking"
      title="The milk"
      big={m.daily_milk_kg / 1000}
      bigUnit="t"
      bigDp={0}
      sub="produced each day"
      status={status}
      detail={milkDetail}
      term={milkTerm}
      onClick={onClick}
    />
  );
}

/* ------------------------------------------------------------- water strip */

export function WaterStrip({ p, onClick }: { p: Packet; onClick: () => void }) {
  const e = p.environment;
  const pct = e.aquifer_budget_used_pct;
  const status: Status =
    pct >= 100 ? "stop" : pct >= 85 ? "act" : pct >= 60 ? "watch" : "good";

  const faulted = e.pivots.filter((x) => x.health !== "nominal").length;
  const machines = faulted ? faulted + " machines need attention" : "all machines running";
  const cooling = e.misters_on
    ? "Cooling is on."
    : "Cooling is off, and 4 of 8 cow sheds have no cooling equipment at all.";

  const line =
    "Using " + pct.toFixed(0) + "% of the year's water allowance" +
    (status === "good" ? ", this water never refills. " : ". ") + machines + ". " + cooling;

  return (
    <button
      onClick={onClick}
      className="card rail mt-3 flex w-full items-center gap-4 px-4 py-3 text-left transition-all duration-300 hover:-translate-y-0.5"
      style={{ ["--agent" as string]: status === "stop" ? "#f87171" : agent("agronomist").hex }}
    >
      <AgentGlyph id="agronomist" className="h-5 w-5 shrink-0" strokeWidth={1.6} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[12.5px] font-medium text-slate-400">Water &amp; machines</span>
          <StatusPill s={status} />
        </div>
        <p className="mt-0.5 text-[11.5px] leading-relaxed text-slate-400">{line}</p>
      </div>
      <span className="shrink-0 text-[10px] text-slate-500 transition group-hover:text-slate-300">
        Open →
      </span>
    </button>
  );
}
