"use client";

import { useEffect, useState } from "react";
import type { StreamMessage, ActionPayload } from "@/lib/types";
import { AGENT_COLOR, KIND_COLOR } from "@/lib/types";

export type Tab = "agents" | "orchestrator" | "hitl" | "control" | "capture";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "agents", label: "Agents", icon: "🧠" },
  { id: "orchestrator", label: "Orchestrator", icon: "🎛" },
  { id: "hitl", label: "HITL", icon: "🖐" },
  { id: "control", label: "Control", icon: "🎚" },
  { id: "capture", label: "Capture", icon: "📸" },
];

/* ------------------------------------------------------------------ AGENTS */

function AgentsTab({ d }: { d: StreamMessage }) {
  const act = d.activity;
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setPulse((n) => n + 1), 700);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-4">
      <p className="text-[11px] leading-relaxed text-slate-400">
        Every row below is <span className="text-slate-200">real tool telemetry</span> recorded by
        the sensor layer, which agent called which tool, how long it took, and what came back.
        Not a narrative written after the fact.
      </p>

      <div>
        <div className="label mb-2">Specialists this tick</div>
        <div className="space-y-1.5">
          {act.agents.map((a) => (
            <div
              key={a.agent}
              className="rounded border border-ink-800 bg-ink-950/40 p-2.5"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    a.last_ok ? "bg-sig-500" : "bg-crit-500"
                  }`}
                />
                <span className={`metric text-xs font-semibold ${AGENT_COLOR[a.agent] ?? "text-slate-300"}`}>
                  {a.agent}
                </span>
                <span className="label ml-auto">{a.total_calls} tool calls</span>
              </div>
              <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2 text-[11px]">
                <span className="metric text-slate-300">{a.last_tool}</span>
                <span className="metric text-[10px] text-slate-600">{a.last_ms.toFixed(1)} ms</span>
              </div>
              <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{a.last_summary}</p>
              {a.recent.length > 1 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {a.recent.map((t) => (
                    <span
                      key={t}
                      className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[9px] text-slate-500"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="label mb-2">Live tool stream</div>
        <div className="max-h-[300px] space-y-1 overflow-y-auto">
          {[...act.recent_calls].reverse().map((c) => (
            <div
              key={c.seq}
              className={`flex items-baseline gap-2 rounded border px-2 py-1.5 text-[10px] ${
                c.ok
                  ? "border-ink-800 bg-ink-950/40"
                  : "border-crit-500/40 bg-crit-500/5"
              }`}
            >
              <span className="metric text-slate-700">#{c.seq}</span>
              <span className={`metric w-[86px] shrink-0 ${AGENT_COLOR[c.agent] ?? "text-slate-400"}`}>
                {c.agent}
              </span>
              <span className="metric flex-1 truncate text-slate-300">{c.tool}</span>
              <span className="metric shrink-0 text-slate-600">{c.ms.toFixed(1)}ms</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ ORCHESTRATOR */

export function OrchestratorTab({ d, wide = false }: { d: StreamMessage; wide?: boolean }) {
  const o = d.orchestration ?? {
    converged: true,
    messages: 0,
    unresolved: 0,
    contested: 0,
    unresolved_detail: [],
  };
  const dispatched = (d.trace.find((t) => t.phase === "triage")?.agent && null) || null;
  void dispatched;

  return (
    <div className="space-y-4">
      <div
        className={`rounded border p-3 ${
          o.converged
            ? "border-sig-500/30 bg-sig-500/5"
            : "border-warn-500/40 bg-warn-500/10"
        }`}
      >
        <div className="mb-1 flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${o.converged ? "bg-sig-500" : "bg-warn-500"}`}
          />
          <span className="text-sm font-semibold text-slate-100">
            {o.converged ? "Swarm converged" : `${o.unresolved} question(s) open`}
          </span>
        </div>
        <p className="text-[11px] leading-relaxed text-slate-400">
          {o.converged
            ? "Every question one specialist asked another has been answered. The orchestrator now gates."
            : "A specialist is waiting on another's answer before it can decide. The orchestrator will not gate until that resolves."}
        </p>
        <div className="mt-2 grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="metric text-lg text-slate-100">{o.messages}</div>
            <div className="label">messages</div>
          </div>
          <div>
            <div className="metric text-lg text-slate-100">{o.unresolved}</div>
            <div className="label">open</div>
          </div>
          <div>
            <div className="metric text-lg text-slate-100">{o.contested}</div>
            <div className="label">contested</div>
          </div>
        </div>
      </div>

      <div>
        <div className="label mb-2">Dispatch, why each specialist woke</div>
        <div className={`${wide ? "max-h-[420px]" : "max-h-[220px]"} space-y-1.5 overflow-y-auto`}>
          {d.trace
            .filter((t) => t.phase === "triage")
            .slice(-6)
            .reverse()
            .map((t, i) => (
              <div key={i} className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
                <p className="text-[11px] leading-relaxed text-slate-300">{t.message}</p>
              </div>
            ))}
        </div>
      </div>

      <div>
        <div className="label mb-2">Routing, round 2 responders</div>
        <div className="space-y-1.5">
          {d.trace
            .filter((t) => t.phase === "mesh" || t.phase === "respond")
            .slice(-6)
            .map((t, i) => (
              <div key={i} className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
                <div className="flex items-center gap-2">
                  <span className="label">{t.phase}</span>
                  <span className={`metric text-[10px] ${AGENT_COLOR[t.agent] ?? "text-slate-400"}`}>
                    {t.agent}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{t.message}</p>
              </div>
            ))}
        </div>
      </div>

      {d.packet.board.length > 0 && (
        <div>
          <div className="label mb-2">Blackboard</div>
          <div className="max-h-[240px] space-y-1.5 overflow-y-auto">
            {d.packet.board.map((m) => (
              <div
                key={m.message_id}
                className="rounded border border-ink-800 bg-ink-950/40 px-2.5 py-2"
              >
                <div className="mb-1 flex items-center gap-1.5">
                  <span className={`pill border ${KIND_COLOR[m.kind] ?? ""}`}>{m.kind}</span>
                  <span className={`metric text-[10px] ${AGENT_COLOR[m.sender] ?? "text-slate-400"}`}>
                    {m.sender}
                  </span>
                  <span className="text-[10px] text-slate-600">&rarr;</span>
                  <span className={`metric text-[10px] ${AGENT_COLOR[m.recipient] ?? "text-slate-500"}`}>
                    {m.recipient === "*" ? "broadcast" : m.recipient}
                  </span>
                </div>
                <p className="text-[11px] leading-relaxed text-slate-400">{m.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------- HITL */

function HitlTab({
  d,
  onDecide,
}: {
  d: StreamMessage;
  onDecide: (approved: boolean, note: string) => Promise<void>;
}) {
  const [note, setNote] = useState("");
  const pending = d.pending;

  return (
    <div className="space-y-4">
      <div
        className={`rounded border p-3 ${
          pending ? "border-fuchsia-500/40 bg-fuchsia-500/10" : "border-sig-500/30 bg-sig-500/5"
        }`}
      >
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${pending ? "bg-fuchsia-500" : "bg-sig-500"}`} />
          <span className="text-sm font-semibold text-slate-100">
            {pending ? "System halted, awaiting your decision" : "Swarm operating autonomously"}
          </span>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
          {pending
            ? "Nothing runs above the risk ceiling until you rule on it. That is the whole design."
            : "No action currently exceeds the risk ceiling, so nothing is waiting on you."}
        </p>
      </div>

      {pending && (
        <div className="rounded border border-fuchsia-500/30 bg-ink-950/40 p-3">
          <div className="text-sm font-semibold text-slate-50">
            {pending.action.action} &middot; {pending.action.target}
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{pending.action.rationale}</p>
          <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
            <div className="rounded border border-sig-500/25 bg-sig-500/5 p-2">
              <div className="label mb-0.5 text-sig-400">If you approve</div>
              <span className="text-slate-300">{pending.action.blast_radius}</span>
            </div>
            <div className="rounded border border-warn-500/25 bg-warn-500/5 p-2">
              <div className="label mb-0.5 text-warn-400">If you do nothing</div>
              <span className="text-slate-300">{pending.action.cost_of_inaction}</span>
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-3 text-[10px] text-slate-500">
            <span>
              urgency <span className="metric text-slate-300">{pending.action.urgency_score.toFixed(0)}</span>
            </span>
            <span>
              risk <span className="metric text-slate-300">{pending.action.risk_score.toFixed(0)}</span>
            </span>
            <span>
              reversible{" "}
              <span className="text-slate-300">{pending.action.reversible ? "yes" : "no"}</span>
            </span>
          </div>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Decision note (recorded)"
            className="mt-3 w-full rounded border border-ink-700 bg-ink-950 px-2.5 py-1.5 text-[11px] text-slate-200 outline-none placeholder:text-slate-600 focus:border-fuchsia-500/60"
          />
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => onDecide(true, note)}
              className="flex-1 rounded bg-sig-600 px-3 py-1.5 text-xs font-semibold text-ink-950 transition hover:bg-sig-500"
            >
              Approve
            </button>
            <button
              onClick={() => onDecide(false, note)}
              className="flex-1 rounded border border-crit-500/50 px-3 py-1.5 text-xs font-semibold text-crit-400 transition hover:bg-crit-500/10"
            >
              Reject
            </button>
          </div>
          {pending.queued.length > 0 && (
            <p className="mt-2 text-[10px] text-slate-500">
              {pending.queued.length} more decision(s) queued behind this one
            </p>
          )}
        </div>
      )}

      <div>
        <div className="label mb-2">Audit trail, your decisions</div>
        {d.decision_log.length === 0 && (
          <p className="text-[11px] text-slate-600">No decisions recorded yet this session.</p>
        )}
        <div className="max-h-[260px] space-y-1.5 overflow-y-auto">
          {d.decision_log.map((x, i) => (
            <div
              key={i}
              className={`rounded border px-2.5 py-2 ${
                x.approved ? "border-sig-500/25 bg-sig-500/5" : "border-crit-500/25 bg-crit-500/5"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`pill border ${
                    x.approved
                      ? "border-sig-500/40 bg-sig-500/10 text-sig-400"
                      : "border-crit-500/40 bg-crit-500/10 text-crit-400"
                  }`}
                >
                  {x.approved ? "approved" : "rejected"}
                </span>
                <span className="metric text-[11px] text-slate-200">{x.action}</span>
                <span className="ml-auto metric text-[10px] text-slate-500">{x.sim_time}</span>
              </div>
              <p className="mt-0.5 text-[10px] text-slate-500">
                {x.result ?? `${x.target} · risk ${x.risk?.toFixed(0)} · ${x.urgency}`}
              </p>
              {x.note && <p className="mt-0.5 text-[10px] text-slate-400">“{x.note}”</p>}
            </div>
          ))}
        </div>
      </div>

      {d.auto_executed.length > 0 && (
        <div>
          <div className="label mb-2">Ran automatically (below the risk ceiling)</div>
          <div className="space-y-1">
            {d.auto_executed.slice(-8).map((x, i) => (
              <div key={i} className="rounded border border-ink-800 bg-ink-950/40 px-2.5 py-1.5">
                <div className="flex items-baseline gap-2">
                  <span className="metric text-[11px] text-slate-300">{x.action}</span>
                  <span className="metric text-[10px] text-slate-500">{x.target}</span>
                </div>
                <p className="text-[10px] text-slate-600">{x.result}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- CONTROL */

function ControlTab({
  d,
  speed,
  onSpeed,
  onClear,
}: {
  d: StreamMessage;
  speed: number;
  onSpeed: (v: number) => void;
  onClear: () => void;
}) {
  const s = d.summary;
  const counts = d.packet.board.reduce<Record<string, number>>((acc, m) => {
    acc[m.kind] = (acc[m.kind] ?? 0) + 1;
    return acc;
  }, {});
  const calls = d.activity.agents.reduce((a, x) => a + x.total_calls, 0);

  return (
    <div className="space-y-4">
      <div>
        <div className="label mb-2">Simulation speed</div>
        <div className="flex gap-1.5">
          {[1, 4, 14, 40, 80].map((v) => (
            <button
              key={v}
              onClick={() => onSpeed(v)}
              className={`metric flex-1 rounded px-2 py-1.5 text-[11px] transition ${
                speed === v
                  ? "bg-sig-600 text-ink-950"
                  : "border border-ink-700 text-slate-400 hover:bg-ink-800"
              }`}
            >
              {v}&times;
            </button>
          ))}
        </div>
        <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500">
          The world pauses at the gate regardless of speed, it will not run past a decision.
        </p>
      </div>

      <div>
        <div className="label mb-2">Clock</div>
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
          <div className="metric text-lg text-slate-100">
            Day {s.day} · {Math.floor(s.hour)}:00
          </div>
          <div className="text-[10px] text-slate-500">{s.phase} · {s.heat_stress_band} heat</div>
        </div>
      </div>

      <div>
        <div className="label mb-2">Session</div>
        <div className="rounded border border-ink-800 bg-ink-950/40 p-2.5 text-[11px]">
          <div className="flex justify-between py-0.5">
            <span className="text-slate-500">Tool calls this tick</span>
            <span className="metric text-slate-200">{calls}</span>
          </div>
          <div className="flex justify-between py-0.5">
            <span className="text-slate-500">Board messages</span>
            <span className="metric text-slate-200">{d.packet.board.length}</span>
          </div>
          <div className="flex justify-between py-0.5">
            <span className="text-slate-500">Human decisions</span>
            <span className="metric text-slate-200">{d.decision_log.length}</span>
          </div>
          <div className="flex justify-between py-0.5">
            <span className="text-slate-500">Findings</span>
            <span className="metric text-slate-200">{d.findings.length}</span>
          </div>
        </div>
      </div>

      {Object.keys(counts).length > 0 && (
        <div>
          <div className="label mb-2">Message mix this round</div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(counts).map(([k, v]) => (
              <span
                key={k}
                className={`pill border ${KIND_COLOR[k] ?? "border-ink-700 bg-ink-800 text-slate-400"}`}
              >
                {k} {v}
              </span>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={onClear}
        className="w-full rounded border border-ink-700 px-3 py-2 text-[11px] text-slate-400 transition hover:bg-ink-800 hover:text-slate-200"
      >
        Reset session (reload)
      </button>
    </div>
  );
}

/* ---------------------------------------------------------------- CAPTURE */

function CaptureTab() {
  const frames = [
    {
      name: "01, the problem",
      note: "Three production areas, one glance. The tiles say what a non-specialist needs to know before anything else.",
      key: "Click any tile",
    },
    {
      name: "02, the plain-language layer",
      note: "Every number paired with a consequence. Hover any term for its definition.",
      key: "Hover a metric",
    },
    {
      name: "03, the constraint that is not obvious",
      note: "Cooling competes with hardware, not water. Four misting banks draw 53 m³/h against 27,000 for the pivots.",
      key: "Open Infrastructure",
    },
    {
      name: "04, the economics of the herd",
      note: "The airlifted animals are mostly heifers. They eat for 18 months before producing anything.",
      key: "Open Livestock",
    },
    {
      name: "05, the agents arguing",
      note: "Seven specialists, one blackboard, two rounds. Nobody decides on a single point of view.",
      key: "Open the mesh",
    },
    {
      name: "06, the human gate",
      note: "Approve or reject, with the consequence of each stated in plain English. Both recorded.",
      key: "Approve a decision",
    },
    {
      name: "07, the evidence",
      note: "Panel → Agents. Real telemetry: which agent called which tool, and what came back.",
      key: "Open this panel",
    },
  ];
  return (
    <div className="space-y-4">
      <p className="text-[11px] leading-relaxed text-slate-400">
        A suggested shot list for the deck. Each state below is reachable from the UI, set the
        scene, then capture a clean frame of the main canvas (hide this panel for full-bleed
        slides).
      </p>
      <div className="space-y-1.5">
        {frames.map((f) => (
          <div key={f.name} className="rounded border border-ink-800 bg-ink-950/40 p-2.5">
            <div className="flex items-baseline gap-2">
              <span className="metric text-[11px] font-semibold text-sig-400">{f.name}</span>
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-300">{f.note}</p>
            <p className="mt-1 text-[10px] text-slate-600">{f.key}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- SHELL */

export function ControlPanel({
  d,
  open,
  onToggle,
  speed,
  onSpeed,
  onDecide,
}: {
  d: StreamMessage;
  open: boolean;
  onToggle: () => void;
  speed: number;
  onSpeed: (v: number) => void;
  onDecide: (approved: boolean, note: string) => Promise<void>;
}) {
  const [tab, setTab] = useState<Tab>("agents");
  const pendingCount = d.pending ? 1 : 0;

  return (
    <>
      {/* Tab rail */}
      <div className="fixed right-0 top-1/2 z-40 -translate-y-1/2">
        {!open && (
          <button
            onClick={onToggle}
            aria-label="Open the operations panel"
            title="Open the operations panel, orchestrator, HITL, tool calls"
            className="flex items-center gap-2 rounded-l-lg border border-r-0 border-sig-500/60 bg-ink-800/95 px-2.5 py-5 text-sig-300 shadow-2xl shadow-black/40 backdrop-blur transition hover:bg-ink-700 hover:text-sig-200"
            style={{ writingMode: "vertical-rl" }}
          >
            <span className="text-[15px]">⚙</span>
            <span className="text-[10.5px] font-bold uppercase tracking-[0.22em]">Panel</span>
            <span className="text-sm leading-none">‹</span>
            {pendingCount > 0 && (
              <span className="h-2 w-2 rounded-full bg-fuchsia-500" />
            )}
          </button>
        )}
      </div>

      <aside
        className={`fixed right-0 top-0 z-40 flex h-screen w-[420px] flex-col border-l border-ink-700 bg-ink-950/97 backdrop-blur transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        aria-label="Control panel"
      >
        <header className="flex items-center gap-2 border-b border-ink-800 p-3">
          <span className="rounded bg-sig-600/15 px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-sig-400">
            CONTROL
          </span>
          <span className="text-[11px] text-slate-500">Adrar Operations Command</span>
          <button
            onClick={onToggle}
            aria-label="Close control panel"
            className="ml-auto rounded px-2 py-1 text-slate-400 transition hover:bg-ink-800 hover:text-slate-200"
          >
            ✕
          </button>
        </header>

        <nav className="flex gap-0.5 border-b border-ink-800 p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative flex-1 rounded px-1 py-1.5 text-[10px] font-semibold transition ${
                tab === t.id ? "bg-ink-800 text-slate-100" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              <span className="block">{t.icon}</span>
              <span className="block truncate">{t.label}</span>
              {t.id === "hitl" && pendingCount > 0 && (
                <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-fuchsia-500" />
              )}
            </button>
          ))}
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {tab === "agents" && <AgentsTab d={d} />}
          {tab === "orchestrator" && <OrchestratorTab d={d} />}
          {tab === "hitl" && <HitlTab d={d} onDecide={onDecide} />}
          {tab === "control" && (
            <ControlTab
              d={d}
              speed={speed}
              onSpeed={onSpeed}
              onClear={() => window.location.reload()}
            />
          )}
          {tab === "capture" && <CaptureTab />}
        </div>
      </aside>

      {open && (
        <button
          onClick={onToggle}
          aria-label="Close control panel"
          className="fixed inset-0 z-30 cursor-default bg-ink-950/60"
        />
      )}
    </>
  );
}