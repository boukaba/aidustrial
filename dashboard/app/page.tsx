"use client";

import { useState } from "react";
import { AgentsLive } from "@/components/Agents";
import { DecisionGate, useFarmStream } from "@/components/Control";
import { ControlPanel } from "@/components/ControlPanel";
import { AreaDetail } from "@/components/AreaDetail";
import {
  CowFoodCard,
  HerdCard,
  MilkCard,
  WaterStrip,
  headline,
  overallStatus,
} from "@/components/Home";
import { EventsPanel, FindingsPanel, TraceFeed } from "@/components/Panels";
import { Sidebar } from "@/components/Sidebar";
import { GuidedTour } from "@/components/Tour";
import { NavId, statusColour } from "@/lib/language";

export default function Command() {
  const { data, connected, error, elapsed, retryNow, decide, setSpeed, speed } =
    useFarmStream("demo", 14);
  const [nav, setNav] = useState<NavId>("home");
  const [rail, setRail] = useState(true);
  const [panel, setPanel] = useState(false);

  if (!data) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <div className="card w-full max-w-md p-6 text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-sig-500 border-t-transparent" />
          <p className="text-sm text-slate-200">
            {error ? "Cannot reach the agent service" : `Connecting to the farm… (${elapsed}s)`}
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

  const { packet, summary, pending, findings, trace, mesh } = data;
  const status = overallStatus(summary, Boolean(pending));
  const line = headline(summary, Boolean(pending));

  const openArea = (n: NavId) => {
    if (n === "home") return "home";
    if (n === "agents") return "agents";
    if (n === "decisions") return "decisions";
    if (n === "system") return "mesh";
    return n as "crop" | "livestock" | "milk" | "infrastructure";
  };

  const margin = `${rail ? "pl-[248px]" : "pl-[68px]"} ${panel ? "pr-[420px]" : "pr-6"}`;

  return (
    <div className={`${margin} transition-all duration-300`}>
      <Sidebar
        active={nav}
        onSelect={setNav}
        open={rail}
        onToggle={() => setRail((v) => !v)}
        badge={pending ? 1 : 0}
      />

      <main className="mx-auto max-w-[1080px] p-5 lg:p-7">
        {/* ------------------------------------------------------ status */}
        <header className="mb-5">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold text-slate-50">
              {nav === "home"
                ? "The Adrar Dairy Farm"
                : nav === "agents"
                  ? "Agents at work"
                  : nav === "decisions"
                  ? "Decisions"
                  : nav === "system"
                    ? "How the system works"
                    : { crop: "Cow food", livestock: "The herd", milk: "The milk", infrastructure: "Water & machines" }[nav] ?? "The Adrar Dairy Farm"}
            </h1>
            <span className={`pill border ${statusColour(status)}`}>
              Day {summary.day} · {summary.phase}
            </span>
            <div className="ml-auto flex items-center gap-2">
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
              <button
                onClick={() => setPanel((v) => !v)}
                className={`rounded border px-2.5 py-1 text-[11px] transition ${
                  panel
                    ? "border-sig-500/50 bg-sig-500/15 text-sig-400"
                    : "border-ink-700 text-slate-400 hover:text-slate-200"
                }`}
              >
                ⚙ Panel
              </button>
            </div>
          </div>

          <div className={`rounded-lg border p-4 ${statusColour(status)}`}>
            <p className="text-lg font-medium leading-snug">{line.text}</p>
            <p className="mt-1 text-sm opacity-80">{line.sub}</p>
          </div>
        </header>

        {/* ---------------------------------------------------- decision */}
        {pending && nav !== "decisions" && (
          <div className="mb-5">
            <DecisionGate
              action={pending.action}
              queued={pending.queued}
              simTime={pending.sim_time}
              onDecide={decide}
            />
          </div>
        )}

        {/* ------------------------------------------------------- HOME */}
        {nav === "home" && (
          <>
            <div className="mb-4">
              <GuidedTour
                p={packet}
                onSelectArea={(a) => setNav((a as NavId) ?? "home")}
                hasPending={Boolean(pending)}
              />
            </div>

            <div className="grid gap-3 lg:grid-cols-3">
              <CowFoodCard p={packet} onClick={() => setNav("crop")} />
              <HerdCard p={packet} onClick={() => setNav("livestock")} />
              <MilkCard p={packet} onClick={() => setNav("milk")} />
            </div>

            <WaterStrip p={packet} onClick={() => setNav("infrastructure")} />
          </>
        )}

        {/* ------------------------------------------- AGENTS AT WORK */}
        {nav === "agents" && mesh && <AgentsLive mesh={mesh} />}

        {/* ----------------------------------------------- AREA DETAIL */}
        {nav !== "home" && nav !== "agents" && nav !== "decisions" && nav !== "system" && (
          <AreaDetail p={packet} area={openArea(nav) as "crop" | "livestock" | "milk" | "infrastructure"} />
        )}

        {/* -------------------------------------------------- DECISIONS */}
        {nav === "decisions" && (
          <div className="space-y-4">
            {pending ? (
              <DecisionGate
                action={pending.action}
                queued={pending.queued}
                simTime={pending.sim_time}
                onDecide={decide}
              />
            ) : (
              <div className="card p-5 text-sm text-slate-400">
                Nothing is waiting for you right now. Anything important will appear here.
              </div>
            )}

            <div className="card p-5">
              <h2 className="mb-3 text-sm font-semibold text-slate-200">
                Your decisions this session
              </h2>
              {data.decision_log.length === 0 && (
                <p className="text-xs text-slate-600">
                  You have not had to decide anything yet.
                </p>
              )}
              <div className="space-y-2">
                {data.decision_log.map((x, i) => (
                  <div
                    key={i}
                    className={`flex flex-wrap items-center gap-3 rounded border px-3 py-2 ${
                      x.approved
                        ? "border-sig-500/25 bg-sig-500/5"
                        : "border-crit-500/25 bg-crit-500/5"
                    }`}
                  >
                    <span
                      className={`pill border ${
                        x.approved
                          ? "border-sig-500/40 bg-sig-500/10 text-sig-400"
                          : "border-crit-500/40 bg-crit-500/10 text-crit-400"
                      }`}
                    >
                      {x.approved ? "approved" : "rejected"}
                    </span>
                    <span className="text-xs text-slate-200">
                      {x.action.replace(/_/g, " ")}
                    </span>
                    <span className="text-[10px] text-slate-500">{x.target}</span>
                    <span className="metric ml-auto text-[10px] text-slate-500">
                      {x.sim_time}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ----------------------------------------------------- SYSTEM */}
        {nav === "system" && (
          <div className="space-y-4">
            <div className="card p-5">
              <h2 className="mb-2 text-sm font-semibold text-slate-200">
                How the farm is run
              </h2>
              <p className="text-sm leading-relaxed text-slate-300">
                Seven specialists each watch one part of the farm. They do not decide alone — they
                ask each other questions first. Only when they agree, and only if the decision is
                important enough, does the farm stop and wait for you.
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {[
                  ["🌾", "Crop", "Fields, irrigation, growing feed"],
                  ["💧", "Irrigation", "Water supply and pivots"],
                  ["🐄", "Herd health", "Cows, heat, sickness"],
                  ["🍼", "Youngstock", "Calves and breeding"],
                  ["🥛", "Milking", "Parlour, cooling, quality"],
                  ["🔧", "Machinery", "Pumps, conveyors, repairs"],
                  ["🚚", "Supplies", "Feed and transport"],
                ].map(([i, n, d]) => (
                  <div key={n} className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
                    <div className="flex items-center gap-2">
                      <span aria-hidden>{i}</span>
                      <span className="text-xs font-medium text-slate-200">{n}</span>
                    </div>
                    <p className="mt-0.5 text-[10px] text-slate-500">{d}</p>
                  </div>
                ))}
              </div>
            </div>

            <AreaDetail p={packet} area="mesh" />
            <TraceFeed trace={trace} />
            <FindingsPanel findings={findings} />
            <EventsPanel p={packet} />
          </div>
        )}

        <footer className="mt-8 border-t border-ink-800 pt-3">
          <p className="text-[10px] leading-relaxed text-slate-600">
            This is a working model of the Baladna Algeria project in Adrar — a $3.5bn dairy
            farm under construction, whose first 30,000 animals are mostly heifers that will not
            give milk for about 18 months. That is why automated monitoring is worth putting in
            now, before the animals arrive. Every reading is simulated from published project
            parameters.{" "}
            <button
              onClick={() => setPanel(true)}
              className="text-slate-500 underline decoration-dotted underline-offset-2"
            >
              Open the panel
            </button>{" "}
            for how the system works.
          </p>
        </footer>
      </main>

      <ControlPanel
        d={data}
        open={panel}
        onToggle={() => setPanel((v) => !v)}
        speed={speed}
        onSpeed={setSpeed}
        onDecide={decide}
      />
    </div>
  );
}
