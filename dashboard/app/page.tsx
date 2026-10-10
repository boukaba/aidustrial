"use client";

import { useState } from "react";
import { AreaDetail } from "@/components/AreaDetail";
import { AreaNav, areaCards } from "@/components/AreaNav";
import { DecisionGate, useFarmStream } from "@/components/Control";
import {
  EventsPanel,
  FindingsPanel,
  HerdPanel,
  LogisticsPanel,
  TraceFeed,
  WaterPanel,
} from "@/components/Panels";
import { GuidedTour } from "@/components/Tour";
import { AreaId, LEVEL_STYLE, explainHeatLoad, explainRumination } from "@/lib/explain";
import { bandColor } from "@/lib/types";

export default function Command() {
  const { data, connected, error, elapsed, retryNow, decide, setSpeed, speed } =
    useFarmStream("demo", 14);
  const [area, setArea] = useState<AreaId>("crop");
  const [showOps, setShowOps] = useState(false);

  if (!data) {
    return (
      <main className="mx-auto flex min-h-screen max-w-[1500px] items-center justify-center p-8">
        <div className="card w-full max-w-md p-6 text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-sig-500 border-t-transparent" />
          <p className="text-sm text-slate-200">
            {error ? "Cannot reach the agent service" : `Connecting to the farm… (${elapsed}s)`}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            The dashboard shows live data from the agent swarm running on a local service.
          </p>
          <div className="mt-4 rounded border border-ink-700 bg-ink-950 p-3 text-left">
            <p className="label mb-1">Start the agent service</p>
            <code className="block text-[11px] text-slate-300">
              uv run uvicorn aidustrial.server.app:app --app-dir src --port 8781
            </code>
          </div>
          <button
            onClick={retryNow}
            className="mt-4 rounded bg-sig-600 px-4 py-2 text-xs font-semibold text-ink-950 transition hover:bg-sig-500"
          >
            Try again
          </button>
        </div>
      </main>
    );
  }

  const { packet, summary, pending, findings, trace } = data;
  const heat = explainHeatLoad(summary.effective_heat_load, summary.heat_stress_band);
  const rum = explainRumination(summary.rumination_deficit);
  const worst = areaCards(packet).reduce((acc, a) =>
    a.plain.level === "stop" ? a : acc, areaCards(packet)[0],
  );

  return (
    <main className="mx-auto max-w-[1500px] p-4 lg:p-6">
      {/* ---------------------------------------------------------- header */}
      <header className="card mb-4 p-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-2">
            <span className="rounded bg-sig-600/15 px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-sig-400">
              AIDUSTRIAL
            </span>
            <h1 className="text-sm font-semibold text-slate-200">Adrar Operations Command</h1>
          </div>

          <span className="text-[11px] text-slate-500">
            Baladna Algeria &middot; Adrar Province, Algeria
          </span>

          <div className="ml-auto flex flex-wrap items-center gap-2">
            <span className={`pill border ${bandColor(summary.heat_stress_band)}`}>
              {summary.heat_stress_band} heat
            </span>
            <span className="metric rounded border border-ink-700 px-2.5 py-1 text-xs text-slate-300">
              Day {summary.day} &middot; {Math.floor(summary.hour)}:00
            </span>
            <div className="flex items-center gap-1 rounded border border-ink-700 px-2 py-1">
              <span className="label">Speed</span>
              {[4, 14, 40].map((v) => (
                <button
                  key={v}
                  onClick={() => setSpeed(v)}
                  className={`metric rounded px-1.5 text-[11px] transition ${
                    speed === v ? "bg-sig-600 text-ink-950" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {v}&times;
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* The one-line verdict a non-specialist can act on. */}
        <div
          className={`mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded border p-2.5 ${
            LEVEL_STYLE[pending ? "act" : heat.level]
          }`}
        >
          <span className="text-sm font-medium">
            {pending
              ? "A decision is waiting for you."
              : heat.line}
          </span>
          <span className="text-xs opacity-75">
            {pending ? "Scroll down — nothing runs until you answer." : heat.because}
          </span>
        </div>
      </header>

      {/* ----------------------------------------------------------- tour */}
      <div className="mb-4">
        <GuidedTour
          p={packet}
          onSelectArea={(a) => setArea(a ?? "crop")}
          hasPending={Boolean(pending)}
        />
      </div>

      {/* --------------------------------------------------------- decision */}
      {pending && (
        <div className="mb-4">
          <DecisionGate
            action={pending.action}
            queued={pending.queued}
            simTime={pending.sim_time}
            onDecide={decide}
          />
        </div>
      )}

      {/* ------------------------------------------------------ area tiles */}
      <div className="mb-2 flex items-baseline gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
          The site at a glance
        </h2>
        <span className="text-[11px] text-slate-600">
          click any tile to open it &middot; most pressing: {worst.name.toLowerCase()}
        </span>
      </div>
      <div className="mb-4">
        <AreaNav p={packet} active={area} onSelect={setArea} />
      </div>

      {/* ---------------------------------------------------------- detail */}
      <AreaDetail p={packet} area={area} />

      {/* ------------------------------------------------- operations ops */}
      <div className="mt-6">
        <button
          onClick={() => setShowOps((v) => !v)}
          className="mb-3 flex w-full items-center gap-2 rounded border border-ink-700 bg-ink-900/50 px-4 py-2.5 text-left transition hover:bg-ink-900"
        >
          <span className="text-[10px] font-bold tracking-[0.14em] text-slate-500">
            OPERATIONS DETAIL
          </span>
          <span className="text-[11px] text-slate-500">
            pivots, barns, feed, agent findings and full reasoning
          </span>
          <span className="ml-auto text-slate-500">{showOps ? "▲" : "▼"}</span>
        </button>

        {showOps && (
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1.1fr]">
            <div className="space-y-4">
              <WaterPanel p={packet} />
              <HerdPanel p={packet} />
              <EventsPanel p={packet} />
            </div>
            <div className="space-y-4">
              <LogisticsPanel p={packet} />
              <FindingsPanel findings={findings} />
            </div>
            <div className="space-y-4">
              <TraceFeed trace={trace} />
            </div>
          </div>
        )}
      </div>

      {/* ---------------------------------------------------------- footer */}
      <footer className="mt-6 border-t border-ink-800 pt-3">
        <p className="text-[10px] leading-relaxed text-slate-600">
          Three production areas — growing the feed, the herd, making the milk — watched by a
          seven-agent mesh that answers each other&apos;s questions before escalating to a human.
          The Adrar site is genuinely under construction (first milk powder targeted late 2027, so
          the herd is mostly heifers that do not yet produce), which is why the system is deployed
          now: the highest-value window for agentic operations is before the first animal arrives.
          All telemetry is simulated from researched Baladna parameters &mdash; see{" "}
          <code className="text-slate-500">docs/DATA_PROVENANCE.md</code>.
        </p>
        <p className="mt-1 text-[10px] text-slate-700">
          {connected ? "stream live" : "stream reconnecting"} &middot;{" "}
          {rum.line.toLowerCase()}
        </p>
      </footer>
    </main>
  );
}