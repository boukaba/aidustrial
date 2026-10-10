"use client";

import { useEffect, useRef, useState } from "react";
import type { StreamMessage, ActionPayload } from "@/lib/types";

const API =
  process.env.NEXT_PUBLIC_AGENT_API ?? "http://localhost:8781";

export function useFarmStream(threadId = "demo", speed = 14) {
  const [data, setData] = useState<StreamMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [speedState, setSpeedState] = useState(speed);
  const retry = useRef(0);

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
        retry.current = 0;
      };
      ws.onmessage = (ev) => {
        try {
          setData(JSON.parse(ev.data) as StreamMessage);
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onerror = () => setError("stream error");
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
  }, [threadId, speedState]);

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

  return { data, connected, error, decide, setSpeed, speed: speedState };
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
          Human decision required
        </span>
        <span className="label">Agent swarm halted at gate</span>
        <span className="ml-auto metric text-xs text-slate-500">{simTime}</span>
      </div>

      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="metric text-xl font-semibold text-slate-100">{action.action}</h2>
        <span className="metric text-sm text-slate-400">{action.target}</span>
        <span className="pill border-slate-600/50 bg-slate-700/30 text-slate-300">
          by {action.requested_by}
        </span>
        <span className="pill border-slate-600/50 bg-slate-700/30 text-slate-300">
          {action.urgency_band}
        </span>
      </div>

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

        <div className="space-y-3.5">
          <ScoreBar score={action.urgency_score} label="Urgency" tone="crit" />
          <ScoreBar score={action.risk_score} label="Risk" tone="warn" />
          <div className="rounded border border-ink-700 bg-ink-950/60 p-2.5">
            <div className="label mb-1">Reversible</div>
            <div className="metric text-xs text-slate-300">
              {action.reversible ? "Yes — reversible" : "No — one-way"}
            </div>
          </div>
        </div>
      </div>

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