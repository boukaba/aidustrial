"use client";

import type { StreamMessage } from "@/lib/types";
import { AGENT_NAME, AGENT_ROLE } from "@/lib/language";

/**
 * The mesh, made visible.
 *
 * A judge should be able to watch three things without being told them:
 *   1. data ARRIVING at each agent (live readings, ticking values)
 *   2. each agent THINKING (its current state + the tool it is calling)
 *   3. each agent DECIDING (its finding and what it proposes)
 * and then see the orchestrator RECEIVE those inputs as the feed assembles.
 */

type Mesh = StreamMessage["mesh"];
type AgentRow = Mesh["agents"][number];

const STATE_COPY: Record<string, { label: string; tone: string; pulse: boolean }> = {
  idle: { label: "watching", tone: "text-slate-400", pulse: false },
  reading: { label: "reading data", tone: "text-sky-300", pulse: true },
  thinking: { label: "thinking", tone: "text-amber-300", pulse: true },
  decided: { label: "decided", tone: "text-sig-400", pulse: false },
  blocked: { label: "waiting for a human", tone: "text-fuchsia-300", pulse: true },
};

const SEV_STYLE: Record<string, string> = {
  critical: "border-crit-500/50 bg-crit-500/10 text-crit-300",
  high: "border-warn-500/50 bg-warn-500/10 text-warn-300",
  medium: "border-warn-500/30 bg-warn-500/5 text-warn-300",
  low: "border-sig-500/40 bg-sig-500/10 text-sig-400",
  info: "border-slate-600/50 bg-slate-700/20 text-slate-400",
};

function Reading({ r }: { r: AgentRow["readings"][number] }) {
  const dot =
    r.status === "stop" ? "bg-crit-400" : r.status === "act" ? "bg-warn-400" : "bg-sig-400";
  const val = typeof r.value === "number" ? r.value.toLocaleString() : r.value;
  return (
    <div className="flex items-baseline gap-2 border-t border-slate-800/70 py-1.5 first:border-t-0">
      <span className={`h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full ${dot}`} />
      <span className="flex-1 text-[11px] leading-tight text-slate-400">{r.label}</span>
      <span className="shrink-0 font-mono text-[11px] font-semibold text-slate-100">
        {val}
        <span className="ml-1 font-sans text-[10px] font-normal text-slate-500">{r.unit}</span>
      </span>
    </div>
  );
}

function AgentCard({ a }: { a: AgentRow }) {
  const st = STATE_COPY[a.state] ?? STATE_COPY.idle;
  const sev = SEV_STYLE[a.severity] ?? SEV_STYLE.info;
  const border =
    a.worst === "stop" ? "border-crit-500/40" : a.worst === "act" ? "border-warn-500/25" : "border-slate-800";

  return (
    <article className={`card flex flex-col border ${border} p-3`}>
      <header className="mb-2 flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-slate-100">{AGENT_NAME[a.agent] ?? a.agent}</h3>
          <p className="truncate text-[11px] text-slate-500">{AGENT_ROLE[a.agent] ?? a.agent}</p>
        </div>
        <span className={`flex shrink-0 items-center gap-1.5 text-[10px] font-medium ${st.tone}`}>
          {st.pulse && (
            <span className="relative flex h-1.5 w-1.5">
              <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-70 ${st.tone.replace("text-", "bg-")}`} />
              <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${st.tone.replace("text-", "bg-")}`} />
            </span>
          )}
          {st.label}
        </span>
      </header>

      {/* 1. data arriving */}
      <section className="rounded-md bg-slate-900/50 p-2" aria-label="live readings">
        <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-slate-600">
          reading now
        </p>
        {a.readings.map((r) => (
          <Reading key={r.label} r={r} />
        ))}
      </section>

      {/* 2. thinking */}
      {a.calls > 0 && (
        <p className="mt-2 flex items-center gap-1.5 truncate text-[10px] text-slate-500">
          <span className="text-slate-600">calling</span>
          <code className="truncate rounded bg-slate-800/70 px-1 py-0.5 font-mono text-[10px] text-sky-300">
            {a.last_tool}
          </code>
          <span className="text-slate-700">·</span>
          <span className="shrink-0">{a.calls} reads</span>
        </p>
      )}

      {/* 3. deciding */}
      <section className="mt-2 border-t border-slate-800 pt-2">
        {a.finding ? (
          <>
            <p className={`inline-block rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${sev}`}>
              {a.severity === "info" ? "noted" : a.severity}
            </p>
            <p className="mt-1.5 text-[11px] leading-snug text-slate-300">{a.finding}</p>
            {a.implies && (
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                <span className="text-slate-600">proposes → </span>
                {a.implies}
              </p>
            )}
          </>
        ) : (
          <p className="text-[11px] text-slate-600">
            {a.calls > 0 ? "checking — nothing needs saying yet" : "watching, nothing to raise"}
          </p>
        )}
      </section>

      {(a.messages > 0 || a.open_questions > 0) && (
        <footer className="mt-2 flex items-center gap-3 border-t border-slate-800 pt-2 text-[10px] text-slate-600">
          <span>{a.messages} sent to the mesh</span>
          {a.open_questions > 0 && (
            <span className="text-warn-400">
              {a.open_questions} waiting for an answer
            </span>
          )}
        </footer>
      )}
    </article>
  );
}

/** What the orchestrator is holding right now: everything the agents sent it. */
function OrchestratorFeed({ m }: { m: Mesh }) {
  return (
    <section className="card p-4">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-200">What the coordinator received</h2>
        <span className="label">every message an agent sent this round</span>
        <span
          className={`pill ml-auto ${
            m.unresolved
              ? "border-warn-500/40 bg-warn-500/10 text-warn-400"
              : "border-sig-500/40 bg-sig-500/10 text-sig-400"
          }`}
        >
          {m.messages} received · {m.unresolved} unanswered
        </span>
      </header>

      {m.summary && (
        <p className="mb-3 rounded-md border border-slate-700/60 bg-slate-800/30 p-2.5 text-xs leading-relaxed text-slate-300">
          {m.summary}
        </p>
      )}

      {m.feed.length === 0 ? (
        <p className="text-xs text-slate-600">
          No messages yet — agents are still surveying. The first round posts here
          the moment any specialist has something to say.
        </p>
      ) : (
        <ol className="space-y-1.5">
          {m.feed.map((f, i) => (
            <li
              key={f.message_id ?? i}
              className="rounded-md border border-slate-800 bg-slate-900/40 px-2.5 py-1.5"
            >
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="text-[11px] font-semibold text-slate-200">
                  {AGENT_NAME[f.sender] ?? f.sender}
                </span>
                <span className="text-[10px] text-slate-600">
                  → {f.recipient === "*" ? "everyone" : AGENT_NAME[f.recipient] ?? f.recipient}
                </span>
                <span className="ml-auto rounded bg-slate-800 px-1 py-0.5 text-[9px] uppercase tracking-wide text-slate-500">
                  {f.kind}
                </span>
              </div>
              <p className="mt-0.5 text-[11px] leading-snug text-slate-400">{f.content}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function AgentsLive({ mesh }: { mesh: Mesh }) {
  const acting = mesh.agents.filter((a) => a.calls > 0 || a.finding).length;
  return (
    <div className="space-y-4">
      <header className="card flex flex-wrap items-center gap-3 p-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-base font-semibold text-slate-100">The seven specialists, working</h1>
          <p className="mt-0.5 text-xs text-slate-400">
            Each card is one specialist. The numbers under &ldquo;reading now&rdquo; come straight
            from the farm sensors and change every second — nothing here is a stored report.
          </p>
        </div>
        <div className="flex shrink-0 gap-2 text-center">
          <div className="rounded-md bg-slate-900/60 px-3 py-1.5">
            <p className="font-mono text-sm font-semibold text-slate-100">{mesh.agents.length}</p>
            <p className="text-[9px] uppercase tracking-wider text-slate-500">agents</p>
          </div>
          <div className="rounded-md bg-slate-900/60 px-3 py-1.5">
            <p className="font-mono text-sm font-semibold text-sky-300">{acting}</p>
            <p className="text-[9px] uppercase tracking-wider text-slate-500">acting</p>
          </div>
          <div className="rounded-md bg-slate-900/60 px-3 py-1.5">
            <p className="font-mono text-sm font-semibold text-violet-300">{mesh.messages}</p>
            <p className="text-[9px] uppercase tracking-wider text-slate-500">messages</p>
          </div>
        </div>
      </header>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {mesh.agents.map((a) => (
          <AgentCard key={a.agent} a={a} />
        ))}
      </div>

      <OrchestratorFeed m={mesh} />
    </div>
  );
}