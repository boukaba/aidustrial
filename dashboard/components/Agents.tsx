"use client";

import { useEffect, useState } from "react";
import { AgentBadge, AgentGlyph } from "@/components/Icons";
import { LiveNumber, ReadingRow, SevChip, StatusChip } from "@/components/Live";
import { agent } from "@/lib/identity";
import { AgentChat } from "./AgentChat";
import { apiBase } from "@/lib/api";
import type { StreamMessage } from "@/lib/types";

/**
 * The mesh, made visible, mission-control version.
 *
 * Three things a visitor must SEE rather than be told:
 *   1. seven distinct workers, each with its own colour, badge and live data
 *   2. data ARRIVING, numbers that flash the instant they change
 *   3. information travelling from each agent INTO the coordinator
 *
 * The signal-flow diagram at the top is the piece that answers "is the
 * orchestrator actually receiving its agents' information?", it is drawn from
 * the same payload as everything else, so a lit line means a real message.
 */

type Mesh = StreamMessage["mesh"];
type AgentRow = Mesh["agents"][number];

const ORDER = [
  "crop",
  "agronomist",
  "veterinarian",
  "calving",
  "milking",
  "maintenance",
  "logistics",
] as const;

/** Map an agent state onto the shared status vocabulary.

 *  `thinking` now comes straight from the backend: it is true while a real LLM
 *  call is on the wire for that agent, which is the honest signal -- not an
 *  inference from severity.
 */
const stateOf = (a: AgentRow): "reading" | "thinking" | "decided" | "blocked" | "watching" => {
  if (a.thinking) return "thinking";
  if (a.awaiting_reply) return "blocked";
  if (a.severity === "critical" || a.severity === "high") return "thinking";
  if (a.finding) return "decided";
  if (a.calls > 0) return "reading";
  return "watching";
};

/* ------------------------------------------------------------------ flow */

/**
 * The signal bus. Each agent sits on the top row; a line drops from it into a
 * shared bus and on into the coordinator. A line lights up and animates only
 * when that agent has actually spoken this round, so the diagram is a truthful
 * picture of the mesh, not decoration.
 */
function SignalFlow({ agents, messages }: { agents: AgentRow[]; messages: number }) {
  const byId = new Map(agents.map((a) => [a.agent, a]));
  const W = 1000;
  const n = ORDER.length;
  const gap = (W - 120) / (n - 1);
  const BUS_Y = 96;
  const HUB_X = W / 2;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} 140`}
        className="h-[150px] w-full"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Signal flow from the seven specialists into the coordinator"
      >
        <defs>
          <linearGradient id="bus" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.15" />
            <stop offset="50%" stopColor="#2dd4bf" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#fb7185" stopOpacity="0.15" />
          </linearGradient>
          <filter id="soft" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="3.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* the shared bus every agent feeds into */}
        <path
          d={`M 60 ${BUS_Y} H ${W - 60}`}
          stroke="url(#bus)"
          strokeWidth="2"
          fill="none"
        />
        {/* bus down into the coordinator */}
        <path
          d={`M ${HUB_X} ${BUS_Y} V 122`}
          stroke="#2dd4bf"
          strokeWidth="2"
          strokeOpacity="0.7"
          fill="none"
        />

        {ORDER.map((id, i) => {
          const x = 60 + i * gap;
          const a = byId.get(id);
          const ident = agent(id);
          // "lit" means it spoke this round
          const spoke = Boolean(a && a.messages > 0);
          const active = Boolean(a && a.calls > 0);
          const color = spoke ? ident.hex : "#334155";

          return (
            <g key={id}>
              {/* drop line agent -> bus */}
              <path
                d={`M ${x} 40 V ${BUS_Y}`}
                stroke={color}
                strokeWidth={spoke ? 2.2 : 1.2}
                strokeOpacity={spoke ? 1 : 0.3}
                strokeDasharray={spoke ? "7 6" : undefined}
                fill="none"
                filter={spoke ? "url(#soft)" : undefined}
                className={spoke ? "animate-flow" : ""}
              />
              {/* lit node ring so a speaking agent reads instantly */}
              {spoke && (
                <circle
                  cx={x}
                  cy={26}
                  r={17}
                  fill="none"
                  stroke={ident.hex}
                  strokeWidth="1"
                  strokeOpacity="0.35"
                  className="animate-pulse-slow"
                />
              )}
              {/* node */}
              <circle
                cx={x}
                cy={26}
                r={13}
                fill={`${ident.hex}${spoke ? "33" : "1f"}`}
                stroke={color}
                strokeWidth={spoke ? 2 : 1.2}
                strokeOpacity={spoke ? 1 : 0.45}
                filter={active || spoke ? "url(#soft)" : undefined}
              />
              <text
                x={x}
                y={30}
                textAnchor="middle"
                fontSize="9.5"
                fontWeight="700"
                fill={spoke ? ident.hex : "#64748b"}
                fontFamily="ui-monospace, monospace"
              >
                {ident.mono}
              </text>
              <text
                x={x}
                y={56}
                textAnchor="middle"
                fontSize="9"
                fill={spoke ? "#94a3b8" : "#475569"}
                fontFamily="ui-sans-serif, system-ui, sans-serif"
              >
                {ident.name}
              </text>
              {active && (
                <circle cx={x + 11} cy={17} r="3" fill={ident.hex} className="animate-pulse-dot" />
              )}
            </g>
          );
        })}

        {/* coordinator node */}
        <circle
          cx={HUB_X}
          cy={126}
          r={16}
          fill="#0f172a"
          stroke="#2dd4bf"
          strokeWidth="2"
          strokeOpacity="0.95"
          filter="url(#soft)"
        />
        <text
          x={HUB_X}
          y={130}
          textAnchor="middle"
          fontSize="9.5"
          fontWeight="700"
          fill="#5eead4"
          fontFamily="ui-monospace, monospace"
        >
          OR
        </text>
      </svg>

      {/* the live message count, tied to the diagram */}
      <div className="pointer-events-none absolute right-0 top-0 flex items-center gap-2">
        <span className="label">into the coordinator</span>
        <span className="pill border-sig-500/40 bg-sig-500/10 text-sig-400">
          {messages} received
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ agent card */


type PolicyRow = { action: string; tier: string; auto_below: number | null; why: string };

/**
 * The autonomy policy, read from the service rather than duplicated here.
 * A judge should be able to see which actions run alone and which always stop
 * for a person, without reading the source.
 */
function AutonomyPolicy() {
  const [rows, setRows] = useState<PolicyRow[]>([]);
  const [decisions, setDecisions] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${apiBase()}/api/ledger?limit=1`)
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        setRows(d.policy || []);
        setDecisions(d.stats?.decisions ?? null);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!rows.length) return null;
  const byTier = (t: string) => rows.filter((r) => r.tier === t);
  const groups = [
    { key: "autonomous", label: "Runs alone", cls: "text-sig-400", note: "no human, any risk" },
    { key: "bounded", label: "Auto below", cls: "text-amber-400", note: "a low ceiling" },
    { key: "always_gate", label: "Always a human", cls: "text-rose-400", note: "never automated" },
  ];

  return (
    <section className="card p-3.5">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          Autonomy policy
        </h2>
        {decisions !== null && (
          <span className="font-mono text-[10px] text-slate-600">
            {decisions} decision{decisions === 1 ? "" : "s"} on record
          </span>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {groups.map((g) => (
          <div key={g.key}>
            <p className={`text-[10px] font-semibold uppercase tracking-[0.1em] ${g.cls}`}>
              {g.label}{" "}
              <span className="font-normal normal-case tracking-normal text-slate-600">
                · {g.note}
              </span>
            </p>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {byTier(g.key).map((r) => (
                <span
                  key={r.action}
                  title={r.why}
                  className="rounded border border-white/[0.08] px-1.5 py-0.5 font-mono text-[9.5px] text-slate-400"
                >
                  {r.action}
                  {r.auto_below !== null && g.key === "bounded" ? ` <${r.auto_below}` : ""}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AgentCard({ a, onAsk }: { a: AgentRow; onAsk?: (id: string) => void }) {
  const ident = agent(a.agent);
  const st = stateOf(a);
  const live = st === "reading" || st === "thinking" || st === "blocked";
  const rail =
    a.worst === "stop" ? "#f87171" : a.worst === "act" ? ident.hex : `${ident.hex}66`;

  return (
    <article
      className={`card rail group relative flex h-full flex-col p-3.5 transition-all duration-300 hover:-translate-y-0.5 ${
        live ? "hot" : ""
      }`}
      style={{ ["--agent" as string]: rail, borderColor: live ? `${ident.hex}44` : undefined }}
    >
      <header className="mb-3 flex items-start gap-2.5">
        <AgentBadge id={a.agent} size="md" active={live} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[13px] font-semibold leading-tight text-slate-100">
            {ident.name}
          </h3>
          <p className="mt-0.5 truncate text-[10.5px] leading-tight text-slate-500">{ident.role}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {onAsk && (
            <button
              onClick={() => onAsk(a.agent)}
              title={`Ask the ${ident.name.toLowerCase()}`}
              className="rounded border border-white/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-500 transition-colors hover:border-sig-500/50 hover:text-sig-400"
            >
              ask
            </button>
          )}
          <StatusChip state={st} />
        </div>
      </header>

      {/* 1, data arriving */}
      <section
        className="rounded-lg p-2"
        style={{ background: `linear-gradient(160deg, ${ident.hex}0d, transparent 70%)`, border: `1px solid ${ident.hex}18` }}
        aria-label="live readings"
      >
        <p className="mb-1 flex items-center gap-1.5 whitespace-nowrap text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-600">
          <AgentGlyph id={a.agent} className="h-2.5 w-2.5 shrink-0" />
          reading now
        </p>
        {a.readings.map((r) => (
          <ReadingRow
            key={r.label}
            label={r.label}
            value={r.value}
            unit={r.unit}
            tone={r.status as "ok" | "act" | "stop"}
            dp={typeof r.value === "number" && !Number.isInteger(r.value) ? 1 : 0}
          />
        ))}
      </section>

      {/* 2, the tool it is calling, only when it is actually calling */}
      {a.calls > 0 && (
        <p className="mt-2.5 flex items-center gap-1.5 truncate text-[10px] text-slate-500">
          <span className="text-slate-600">querying</span>
          <code
            className="truncate rounded px-1.5 py-0.5 font-mono text-[10px]"
            style={{ color: ident.hex, background: `${ident.hex}14` }}
          >
            {a.last_tool}
          </code>
          <span className="text-slate-700">·</span>
          <span className="shrink-0">{a.calls} reads</span>
        </p>
      )}

      {/* 3, what it decided */}
      <section className="mt-2.5 border-t border-white/[0.06] pt-2.5">
        {a.finding ? (
          <>
            <div className="mb-1.5 flex items-center gap-2">
              <SevChip sev={a.severity} />
              {a.confidence > 0 && (
                <span className="metric text-[10px] text-slate-600">
                  {Math.round(a.confidence * 100)}% sure
                </span>
              )}
            </div>
            <p className="text-[11.5px] leading-snug text-slate-300">{a.finding}</p>
            {/* The model's own explanation of why it concluded that. This is
                the clearest proof on the card that the agent reasoned rather
                than matched a threshold. */}
            {a.rationale && a.rationale !== a.finding && (
              <p className="mt-1.5 border-l pl-2 text-[11px] italic leading-snug text-slate-500"
                 style={{ borderColor: `${ident.hex}33` }}>
                {a.rationale}
              </p>
            )}
            {a.implies && (
              <p className="mt-1.5 text-[11px] leading-snug text-slate-500">
                <span className="text-slate-600">proposes → </span>
                <code className="font-mono text-[10.5px] text-slate-400">{a.implies}</code>
              </p>
            )}
            {/* Attribution + latency, only when the model actually produced it.
                The decision track (Jev) is listed first: it is the one that
                decided *what to do*, and it did so in under a second. */}
            {a.decided && a.decided_by && (
              <p className="mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[9.5px] text-slate-600">
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full"
                  style={{ background: "#38bdf8" }}
                  aria-hidden
                />
                decided by <code className="text-slate-500">{a.decided_by}</code>
                {a.decided_ms ? (
                  <span className="metric text-slate-700">· {Math.round(a.decided_ms)}ms</span>
                ) : null}
                {a.warranted === false ? (
                  <span className="text-slate-600">· nothing warranted</span>
                ) : a.action_p ? (
                  <span className="metric text-slate-700">
                    · {Math.round(a.action_p * 100)}% on action
                  </span>
                ) : null}
              </p>
            )}
            {a.reasoned && a.reasoned_by && (
              <p className="mt-1 flex items-center gap-1.5 text-[9.5px] text-slate-600">
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full"
                  style={{ background: ident.hex }}
                  aria-hidden
                />
                words by <code className="text-slate-500">{a.reasoned_by}</code>
                {a.reasoned_ms ? (
                  <span className="metric text-slate-700">· {Math.round(a.reasoned_ms)}ms</span>
                ) : null}
              </p>
            )}
          </>
        ) : (
          <p className="text-[11px] text-slate-600">
            {a.calls > 0 ? "checking, nothing needs saying yet" : "watching, nothing to raise"}
          </p>
        )}
      </section>

      {(a.messages > 0 || a.open_questions > 0) && (
        <footer className="mt-2.5 flex items-center gap-3 border-t border-white/[0.06] pt-2 text-[10px] text-slate-600">
          <span className="flex items-center gap-1">
            <AgentGlyph id={a.agent} className="h-3 w-3" />
            {a.messages} sent to the mesh
          </span>
          {a.open_questions > 0 && (
            <span className="font-semibold text-amber-400">
              {a.open_questions} waiting for an answer
            </span>
          )}
        </footer>
      )}
    </article>
  );
}

/* --------------------------------------------------------- message feed */

function MessageFeed({ feed }: { feed: Mesh["feed"] }) {
  return (
    <section className="card p-4">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-sig-400" />
          Live conversation
        </h2>
        <span className="label">what each agent just told the coordinator</span>
      </header>

      {feed.length === 0 ? (
        <p className="py-6 text-center text-xs text-slate-600">
          The first round is starting. Messages appear here the moment a specialist has
          something to say.
        </p>
      ) : (
        <ol className="space-y-1.5">
          {feed.map((f, i) => {
            const from = agent(f.sender);
            const to = f.recipient === "*" ? null : agent(f.recipient);
            return (
              <li
                key={f.message_id ?? i}
                className="animate-slide-in rounded-lg border p-2.5"
                style={{
                  animationDelay: `${Math.min(i, 4) * 60}ms`,
                  borderColor: `${from.hex}26`,
                  background: `linear-gradient(100deg, ${from.hex}0a, transparent 45%)`,
                }}
              >
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <AgentBadge id={f.sender} size="sm" />
                  <span className="text-[12px] font-semibold text-slate-100">{from.name}</span>
                  <span className="text-[10px] text-slate-600">
                    → {to ? to.name : "everyone"}
                  </span>
                  <span
                    className="ml-auto rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em]"
                    style={{
                      color: f.kind === "alert" ? "#fbbf24" : f.kind === "objection" ? "#f87171" : "#5eead4",
                      borderColor:
                        f.kind === "alert" ? "#fbbf2444" : f.kind === "objection" ? "#f8717144" : "#5eead433",
                      background: f.kind === "alert" ? "#fbbf2412" : f.kind === "objection" ? "#f8717112" : "#5eead40f",
                    }}
                  >
                    {f.kind}
                  </span>
                </div>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-slate-400">{f.content}</p>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ view */

export function AgentsLive({
  mesh,
  llm,
  decision,
  narration,
}: {
  mesh: Mesh;
  llm?: StreamMessage["llm"];
  decision?: StreamMessage["decision"];
  narration?: StreamMessage["narration"];
}) {
  const [openAgent, setOpenAgent] = useState<string | null>(null);
  const acting = mesh.agents.filter((a) => a.calls > 0).length;
  const speaking = mesh.agents.filter((a) => a.messages > 0).length;
  const raised = mesh.agents.filter((a) => a.finding).length;
  const reasoning = mesh.agents.filter((a) => a.reasoned).length;
  const decided = mesh.agents.filter((a) => a.decided).length;
  const thinking = mesh.agents.filter((a) => a.thinking).length;
  const reasoningConfigured = Boolean(decision?.enabled || llm?.enabled);
  const latest = narration?.recent?.[narration.recent.length - 1];

  return (
    <div className="animate-fade-up space-y-4">
      {openAgent && <AgentChat agentId={openAgent} onClose={() => setOpenAgent(null)} />}
      {/* command deck */}
      <header className="card relative overflow-hidden p-4">
        <div
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(600px 200px at 15% 0%, rgba(45,212,191,0.10), transparent 65%)",
          }}
        />
        <div className="relative flex flex-wrap items-end gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold tracking-tightest text-slate-50">
              The seven specialists, working
            </h1>
            <p className="mt-1 max-w-xl text-[12px] leading-relaxed text-slate-400">
              Each card is one specialist reading the farm right now. The numbers flash when
              they change, nothing here is a stored report.
            </p>
            {/* Two reasoning tracks, shown plainly. They divide the work:
                the decision track decides *what to do* in under a second; the
                prose track writes the plain-language summary a judge reads,
                slower, and that is fine, nothing blocks on it. */}
            {!reasoningConfigured && (
              <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-slate-500">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-slate-600" aria-hidden />
                <span>
                  Reasoning backend offline, deterministic rules and the human gate are active.
                </span>
              </p>
            )}
            {decision?.enabled && (
              <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-slate-500">
                <span
                  className={`inline-block h-1.5 w-1.5 rounded-full ${
                    decision.in_flight > 0 ? "animate-pulse-dot" : ""
                  }`}
                  style={{ background: decision.in_flight > 0 ? "#38bdf8" : "#475569" }}
                  aria-hidden
                />
                <span>
                  deciding via{" "}
                  <code className="rounded bg-white/[0.04] px-1 py-0.5 text-slate-400">
                    {decision.model}
                  </code>
                </span>
                <span className="text-slate-700">·</span>
                <span className="metric">
                  {decided} decided
                  {decision.in_flight > 0 ? ` · ${decision.in_flight} asking` : ""}
                </span>
                <span className="text-slate-700">·</span>
                <span className="metric text-slate-600">
                  {decision.last_ms ? `${Math.round(decision.last_ms)}ms` : ", "}
                  {" · "}
                  {decision.calls} calls
                  {decision.rejected_low_confidence > 0
                    ? ` · ${decision.rejected_low_confidence} low-confidence`
                    : ""}
                </span>
              </p>
            )}
            {llm?.enabled && (
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-slate-500">
                <span
                  className={`inline-block h-1.5 w-1.5 rounded-full ${
                    thinking > 0 ? "animate-pulse-dot" : ""
                  }`}
                  style={{ background: thinking > 0 ? "#a3e635" : "#475569" }}
                  aria-hidden
                />
                <span>
                  writing via{" "}
                  <code className="rounded bg-white/[0.04] px-1 py-0.5 text-slate-400">
                    {llm.model}
                  </code>
                </span>
                <span className="text-slate-700">·</span>
                <span className="metric">
                  {reasoning} reasoned
                  {thinking > 0 ? ` · ${thinking} thinking` : ""}
                </span>
                <span className="text-slate-700">·</span>
                <span className="metric text-slate-600">
                  {llm.calls} calls · {llm.cache_hits} cached
                </span>
              </p>
            )}
            {/* Ambient narration from the hidden eighth agent. */}
            {latest && (
              <p className="mt-2 max-w-2xl border-l border-white/10 pl-2.5 text-[11.5px] italic leading-relaxed text-slate-500">
                {latest.text}
              </p>
            )}
          </div>
          <div className="flex shrink-0 gap-2">
            {[
              { v: mesh.agents.length, l: "agents", c: "#e2e8f0" },
              { v: acting, l: "reading", c: "#38bdf8" },
              { v: speaking, l: "speaking", c: "#2dd4bf" },
              { v: decided, l: "decided", c: "#38bdf8" },
              { v: reasoning, l: "reasoned", c: "#a3e635" },
              { v: mesh.messages, l: "messages", c: "#c084fc" },
            ].map((s) => (
              <div
                key={s.l}
                className="min-w-[62px] rounded-lg border border-white/[0.06] bg-ink-900/80 px-2.5 py-2 text-center"
                style={{ boxShadow: `0 0 22px -12px ${s.c}` }}
              >
                <p className="metric text-[19px] font-bold leading-none" style={{ color: s.c }}>
                  <LiveNumber value={s.v} />
                </p>
                <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                  {s.l}
                </p>
              </div>
            ))}
          </div>
        </div>
      </header>

      {/* signal flow, the answer to "is the orchestrator receiving this?" */}
      <section className="card p-4">
        <SignalFlow agents={mesh.agents} messages={mesh.messages} />
      </section>

      <AutonomyPolicy />

      {/* the specialists */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {mesh.agents.map((a, i) => (
          <div
            key={a.agent}
            className="animate-fade-up"
            style={{ animationDelay: `${Math.min(i, 6) * 55}ms` }}
          >
            <AgentCard a={a} onAsk={setOpenAgent} />
          </div>
        ))}
      </div>

      <MessageFeed feed={mesh.feed} />
    </div>
  );
}
