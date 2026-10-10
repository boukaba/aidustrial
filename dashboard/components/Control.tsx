"use client";

import { useEffect, useRef, useState } from "react";
import type { StreamMessage, ActionPayload } from "@/lib/types";

const API =
  process.env.NEXT_PUBLIC_AGENT_API ?? "http://localhost:8781";

export function useFarmStream(threadId = "demo", speed = 14) {
  const [data, setData] = useState<StreamMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [speedState, setSpeedState] = useState(speed);
  const retry = useRef(0);

  // A judge staring at a spinner for 30 seconds with no explanation is a
  // failed demo. Show elapsed time and an explicit manual retry.
  useEffect(() => {
    if (data || error) return;
    const t = setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [data, error]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let timer: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (closed) return;
      const url = `${API.replace(/^http/, "ws")}/ws/stream?thread_id=${threadId}&speed=${speedState}`;
      ws = new WebSocket(url);

      ws.onopen = () => {
        setConnected(true);
        setError(null);
        setAttempt(0);
        retry.current = 0;
      };
      ws.onmessage = (ev) => {
        try {
          setData(JSON.parse(ev.data) as StreamMessage);
          setConnected(true);
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onerror = () => setError("could not reach the agent service");
      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        retry.current = Math.min(retry.current + 1, 6);
        timer = setTimeout(connect, 400 * retry.current);
      };
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, [threadId, speedState, attempt]);

  const decide = async (approved: boolean, note = "") => {
    await fetch(`${API}/api/decide/${threadId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved, note }),
    });
  };

  const setSpeed = async (v: number) => {
    setSpeedState(v);
    await fetch(`${API}/api/session/${threadId}/speed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ speed: v }),
    });
  };

  const retryNow = () => {
    setError(null);
    setAttempt((n) => n + 1);
  };

  return { data, connected, error, elapsed, retryNow, decide, setSpeed, speed: speedState };
}

export function ScoreBar({
  score,
  label,
  tone = "warn",
}: {
  score: number;
  label: string;
  tone?: "warn" | "crit" | "sig";
}) {
  const colour =
    tone === "crit" ? "bg-crit-500" : tone === "sig" ? "bg-sig-500" : "bg-warn-500";
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="label">{label}</span>
        <span className="metric text-xs text-slate-300">{score.toFixed(0)}/100</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
        <div
          className={`h-full rounded-full transition-all duration-500 ${colour}`}
          style={{ width: `${Math.max(2, Math.min(100, score))}%` }}
        />
      </div>
    </div>
  );
}

export function EvidenceBlock({ evidence }: { evidence: Record<string, unknown> }) {
  const entries = Object.entries(evidence).filter(([k, v]) => {
    if (v === null || typeof v === "object") return false;
    // A literal 0 headcount on an irrigation proposal reads like missing data
    // rather than "this action does not touch animals". Drop the field instead.
    if (k === "headcount_affected" && v === 0) return false;
    return true;
  });
  if (!entries.length) return null;
  return (
    <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 rounded border border-ink-700 bg-ink-950/60 p-2.5 sm:grid-cols-3">
      {entries.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="label truncate">{k.replace(/_/g, " ")}</dt>
          <dd className="metric truncate text-xs text-slate-300">
            {typeof v === "number" ? v.toLocaleString() : String(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function DecisionGate({
  action,
  queued,
  onDecide,
  simTime,
}: {
  action: ActionPayload;
  queued: ActionPayload[];
  onDecide: (approved: boolean, note: string) => Promise<void>;
  simTime: string;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async (ok: boolean) => {
    setBusy(true);
    await onDecide(ok, note);
    setNote("");
    setBusy(false);
  };

  return (
    <section className="card gate-live border-fuchsia-500/40 p-5">
      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <span className="pill border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-300">
          Your decision
        </span>
        <span className="label">The farm is paused until you answer</span>
        <span className="ml-auto metric text-xs text-slate-500">{simTime}</span>
      </div>

      <div className="mb-3">
        <h2 className="text-lg font-semibold leading-snug text-slate-50">
          {plainHeadline(action)}
        </h2>
        <p className="mt-0.5 text-[11px] text-slate-500">
          suggested by the {action.requested_by.replace("_", " ")} specialist &middot;{" "}
          <span className="text-slate-600">{action.target}</span>
        </p>
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        <div className="rounded border border-sig-500/25 bg-sig-500/5 p-3">
          <div className="label mb-1 text-sig-400">If you approve</div>
          <p className="text-xs leading-relaxed text-slate-300">{plainIf(action)}</p>
        </div>
        <div className="rounded border border-warn-500/25 bg-warn-500/5 p-3">
          <div className="label mb-1 text-warn-400">If you do nothing</div>
          <p className="text-xs leading-relaxed text-slate-300">
            {action.cost_of_inaction || plainDoNothing(action)}
          </p>
        </div>
      </div>

      <details className="mb-4">
        <summary className="cursor-pointer select-none text-[11px] font-semibold text-slate-400 hover:text-slate-200">
          Show technical detail and evidence
        </summary>
        <div className="mt-3 rounded border border-ink-800 bg-ink-950/30 p-3">
      <div className="grid gap-5 md:grid-cols-[1fr_200px]">
        <div>
          <p className="mb-3 text-sm leading-relaxed text-slate-300">{action.rationale}</p>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded border border-crit-500/20 bg-crit-500/5 p-2.5">
              <div className="label mb-1 text-crit-400">Blast radius</div>
              <p className="text-xs leading-relaxed text-slate-300">{action.blast_radius}</p>
            </div>
            <div className="rounded border border-warn-500/20 bg-warn-500/5 p-2.5">
              <div className="label mb-1 text-warn-400">Cost of inaction</div>
              <p className="text-xs leading-relaxed text-slate-300">
                {action.cost_of_inaction}
              </p>
            </div>
          </div>

          <div className="mt-3">
            <div className="label mb-1.5">Why this was escalated</div>
            <ul className="space-y-1">
              {action.risk_factors.map((f, i) => (
                <li key={i} className="flex gap-2 text-xs text-slate-400">
                  <span className="text-slate-600">▸</span>
                  {f}
                </li>
              ))}
            </ul>
          </div>

          <EvidenceBlock evidence={action.evidence} />
        </div>
        </div>
        </div>
      </details>

      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Decision note (recorded in the audit log)"
        className="mt-4 w-full rounded border border-ink-700 bg-ink-950 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-sig-500/60"
      />

      <div className="mt-3 flex items-center gap-3">
        <button
          disabled={busy}
          onClick={() => send(true)}
          className="rounded bg-sig-600 px-5 py-2 text-sm font-semibold text-ink-950 transition hover:bg-sig-500 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={busy}
          onClick={() => send(false)}
          className="rounded border border-crit-500/50 px-5 py-2 text-sm font-semibold text-crit-400 transition hover:bg-crit-500/10 disabled:opacity-50"
        >
          Reject
        </button>
        {queued.length > 0 && (
          <span className="label ml-auto">
            {queued.length} further decision{queued.length > 1 ? "s" : ""} queued
          </span>
        )}
      </div>
    </section>
  );
}

/* --------------------------------------------------------- plain language */

const HEADLINE: Record<string, string> = {
  enable_misters: "Start cooling for some of the cow barns",
  stop_misters: "Stop the barn cooling",
  start_pivot: "Turn on irrigation for some fields",
  stop_pivot: "Stop irrigation on some fields",
  shed_pivot: "Reduce the irrigation programme",
  transfer_water: "Move water from one field to another",
  repair_pivot: "Send someone to fix an irrigation pivot",
  shed_load: "Reduce the workload on barns that cannot be cooled",
  restart_inlet: "Restart a feed conveyor that has stopped",
  reroute_convoy: "Expedite a feed or milk delivery",
  quarantine_group: "Move a group of animals into isolation",
  harvest_field: "Cut and harvest a forage field",
  boost_heifer_rations: "Improve the feed given to the heifers",
  isolate_calves: "Move sick calves into isolation pens",
  service_parlour: "Service the milking equipment",
  clean_condenser: "Clean the milk cooler",
  cull_chronic_mastitis: "Cull cows with persistent mastitis",
  halt_intake: "Stop milk intake at the powder plant",
};

function plainHeadline(a: ActionPayload): string {
  if (HEADLINE[a.action]) return HEADLINE[a.action];
  const n = a.target ? a.target.split(",").length : 0;
  return `${a.action.replace(/_/g, " ")}${n > 1 ? ` (${n} items)` : ""}`;
}

function plainIf(a: ActionPayload): string {
  switch (a.action) {
    case "enable_misters":
      return "Cooling starts in the barns most under heat stress. Those cows should eat and milk normally again within hours.";
    case "start_pivot":
      return "The listed fields start receiving water and the crop resumes growing. Reversible — the pivots can be stopped again.";
    case "shed_pivot":
      return "Some fields stop irrigating to bring yearly water use back inside the sustainable limit. Those fields lose some growth.";
    case "repair_pivot":
      return "A technician clears the blocked nozzles and services the bearings. The field waters evenly again.";
    case "shed_load":
      return "Barns with no cooling take less throughput, protecting animals from a workload they cannot handle in this heat.";
    case "cull_chronic_mastitis":
      return "Chronically infected cows leave the herd. Milk quality improves; the site loses some cattle.";
    case "clean_condenser":
      return "The cooler is cleaned and pulls the tank back down to temperature. Milk that has warmed is saved.";
    case "isolate_calves":
      return "Affected calves move to separate pens and are treated. Some will still die, but fewer will.";
    case "harvest_field":
      return "Forage is cut and stored while at peak quality. Left standing, it loses both mass and digestibility.";
    case "reroute_convoy":
      return "A delivery is expedited, at a premium, to cover a feed or cold-chain shortfall.";
    case "boost_heifer_rations":
      return "Heifers get a better ration so they reach breeding weight on schedule and start earning earlier.";
    case "service_parlour":
      return "Downtime is cut. Cows are milked closer to schedule, which protects yield for that lactation.";
    default:
      return a.rationale;
  }
}

function plainDoNothing(a: ActionPayload): string {
  return "Nothing changes and the situation develops on its own.";
}
