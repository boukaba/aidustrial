"use client";

import { DecisionGate, useFarmStream } from "@/components/Control";
import {
  EventsPanel,
  FindingsPanel,
  HerdPanel,
  LogisticsPanel,
  SiteHeader,
  StatStrip,
  TraceFeed,
  WaterPanel,
} from "@/components/Panels";

export default function Command() {
  const { data, connected, error, decide, setSpeed, speed } = useFarmStream("demo", 14);

  if (!data) {
    return (
      <main className="mx-auto flex min-h-screen max-w-[1500px] items-center justify-center p-8">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-sig-500 border-t-transparent" />
          <p className="metric text-sm text-slate-400">
            {error ? `Agent API unreachable (${error})` : "Connecting to agent stream…"}
          </p>
          <p className="mt-2 text-[11px] text-slate-600">
            Start the backend: <code className="text-slate-400">uv run uvicorn aidustrial.server.app:app --app-dir src --port 8781</code>
          </p>
        </div>
      </main>
    );
  }

  const { packet, summary, pending, findings, trace } = data;

  return (
    <main className="mx-auto max-w-[1500px] p-4 lg:p-6">
      <SiteHeader s={summary} speed={speed} onSpeed={setSpeed} />
      <StatStrip s={summary} />

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

      {!pending && (
        <div className="card mb-4 flex items-center gap-3 border-sig-500/20 p-3">
          <span className="h-2 w-2 rounded-full bg-sig-500" />
          <p className="text-xs text-slate-400">
            Swarm operating autonomously. No action currently exceeds the risk ceiling.
          </p>
          <span className="label ml-auto">
            {connected ? "stream live" : "stream reconnecting"}
          </span>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1.1fr]">
        <div className="space-y-4">
          <HerdPanel p={packet} />
          <EventsPanel p={packet} />
        </div>
        <div className="space-y-4">
          <WaterPanel p={packet} />
          <LogisticsPanel p={packet} />
        </div>
        <div className="space-y-4">
          <TraceFeed trace={trace} />
          <FindingsPanel findings={findings} />
        </div>
      </div>

      <footer className="mt-6 border-t border-ink-800 pt-3">
        <p className="text-[10px] leading-relaxed text-slate-600">
          Digital twin seeded with researched Baladna Algeria parameters (117,000 ha
          concession, 270,000 head target, 33,250 head Phase 1 infrastructure, 45 wells
          / 186 permits, Albien non-renewable aquifer, 30,000-head US airlift). The Adrar
          site is under construction — first milk powder targeted late 2027 — so all
          telemetry is simulated and labelled as such. See{" "}
          <code className="text-slate-500">docs/DATA_PROVENANCE.md</code> for the full
          sourced / derived / modelled split.
        </p>
      </footer>
    </main>
  );
}