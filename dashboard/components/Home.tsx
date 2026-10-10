"use client";

import type { Packet, Summary } from "@/lib/types";
import { Status, STATUS_WORD, statusColour, TERM } from "@/lib/language";

/**
 * The simplified home screen.
 *
 * Design intent: a first-time visitor should understand this in under fifteen
 * seconds without reading a single number. One sentence of status, one clear
 * action if there is one, three cards. Everything numeric lives behind a
 * disclosure.
 *
 * Note on style: all copy is concatenated into a local before being passed to
 * JSX. Template literals with bracket access inside a JSX attribute trip the
 * parser, and inline ternaries in props hurt readability anyway.
 */

export function StatusPill({ s }: { s: Status }) {
  return <span className={`pill border ${statusColour(s)}`}>{STATUS_WORD[s]}</span>;
}

function Card(props: {
  icon: string;
  title: string;
  big: string;
  sub: string;
  status: Status;
  detail: string;
  term: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={props.onClick}
      className="group flex w-full flex-col rounded-xl border border-ink-700 bg-ink-900/70 p-4 text-left transition hover:border-ink-600 hover:bg-ink-900"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden>
          {props.icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-medium text-slate-300">{props.title}</div>
          <div className="mt-0.5 font-mono text-2xl leading-tight text-slate-50">{props.big}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">{props.sub}</div>
        </div>
        <StatusPill s={props.status} />
      </div>

      <p className="mt-3 text-sm leading-relaxed text-slate-300">{props.detail}</p>

      <details className="mt-2 w-full" onClick={(e) => e.stopPropagation()}>
        <summary className="cursor-pointer text-[10px] text-slate-600 hover:text-slate-400">
          What does this mean?
        </summary>
        <p className="mt-1.5 rounded border border-ink-700 bg-ink-950/60 p-2 text-[11px] leading-relaxed text-slate-400">
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
  const tonnes = Math.round(c.standing_t).toLocaleString();
  const cut = Math.round(c.harvested_t).toLocaleString();

  const detail =
    status === "stop"
      ? dry + " of " + n + " fields have run out of water and the crop has stopped growing. This is a permanent loss for this season, not a delay."
      : status === "watch"
        ? drying + " field(s) are drying out and will need water soon. Everything else is growing well."
        : "All " + n + " fields have enough water. There is " + tonnes + " tonnes of feed growing right now.";

  const cropTerm =
    TERM["Standing DM"] +
    " Feed grows here and is cut for silage, then stored and fed to the cows all year." +
    (c.harvested_t > 0 ? " " + cut + " tonnes have been cut and stored so far." : "");

  return (
    <Card
      icon="🌾"
      title="Food for the cows"
      big={tonnes + " t"}
      sub="tonnes of feed growing in the fields"
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
      : "The cows, calves and young stock are all where they should be. Most of them are heifers, meaning animals that arrived by air and will start giving milk in about 18 months.";

  const herdTerm = [TERM.Heifer, TERM["Breeding weight"], TERM["Dry cow"]].join(" ");

  return (
    <Card
      icon="🐄"
      title="The herd"
      big={l.total_head.toLocaleString()}
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
      icon="🥛"
      title="The milk"
      big={(m.daily_milk_kg / 1000).toFixed(0) + " t"}
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
  const machines = faulted ? faulted + " machine(s) need attention." : "All machines running.";
  const cooling = e.misters_on
    ? ""
    : " Cooling is off, and 4 of 8 cow sheds have no cooling equipment at all.";

  const line =
    (status === "good"
      ? "Using " + pct.toFixed(0) + "% of the year's water allowance. " + machines
      : "Using " + pct.toFixed(0) + "% of the year's water allowance — this water never refills. ") + cooling;

  return (
    <button
      onClick={onClick}
      className="mt-3 flex w-full items-center gap-4 rounded-xl border border-ink-700 bg-ink-900/50 px-4 py-3 text-left transition hover:border-ink-600 hover:bg-ink-900"
    >
      <span className="text-xl" aria-hidden>
        💧
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium text-slate-300">Water &amp; machines</span>
          <StatusPill s={status} />
        </div>
        <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{line}</p>
      </div>
      <span className="shrink-0 text-[10px] text-slate-500">Open →</span>
    </button>
  );
}