"use client";

import type { Packet } from "@/lib/types";
import { AGENT_COLOR, KIND_COLOR } from "@/lib/types";

/**
 * The agent mesh. Shows who spoke to whom this round, which is the thing a
 * fan-out architecture cannot express: an agronomist answering a veterinarian's
 * question about water, a logistics agent pricing a calving agent's shortfall.
 */
export function MeshBoard({ p }: { p: Packet }) {
  const msgs = p.board ?? [];
  const answered = new Set(msgs.map((m) => m.in_reply_to).filter(Boolean));
  const open = msgs.filter((m) => m.expects_reply && !answered.has(m.message_id));

  return (
    <section className="card flex max-h-[420px] flex-col p-4">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-200">Agent mesh</h2>
        <span className="label">round 1 survey → round 2 respond</span>
        <span
          className={`pill ml-auto ${
            open.length
              ? "border-warn-500/40 bg-warn-500/10 text-warn-400"
              : "border-sig-500/40 bg-sig-500/10 text-sig-400"
          }`}
        >
          {open.length ? `${open.length} open` : "converged"}
        </span>
      </div>

      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
        {msgs.length === 0 && (
          <p className="text-xs text-slate-600">
            Board empty — no specialist woke, or none had anything to broadcast.
          </p>
        )}
        {msgs.map((m) => {
          const isReply = Boolean(m.in_reply_to);
          return (
            <div
              key={m.message_id}
              className={`rounded border px-2.5 py-2 ${
                isReply
                  ? "border-ink-800 bg-ink-950/30 ml-3"
                  : m.kind === "objection"
                    ? "border-crit-500/30 bg-crit-500/5"
                    : "border-ink-800 bg-ink-950/40"
              }`}
            >
              <div className="mb-1 flex flex-wrap items-center gap-1.5">
                <span className={`pill border ${KIND_COLOR[m.kind] ?? "border-ink-600/50 bg-ink-700/30 text-slate-400"}`}>
                  {m.kind}
                </span>
                <span className={`metric text-[10px] font-semibold ${AGENT_COLOR[m.sender] ?? "text-slate-400"}`}>
                  {m.sender}
                </span>
                <span className="text-[10px] text-slate-600">→</span>
                <span className={`metric text-[10px] ${m.recipient === "*" ? "text-slate-600" : AGENT_COLOR[m.recipient] ?? "text-slate-300"}`}>
                  {m.recipient === "*" ? "broadcast" : m.recipient}
                </span>
                {m.domains.slice(0, 3).map((d) => (
                  <span key={d} className="text-[9px] text-slate-600">
                    #{d}
                  </span>
                ))}
              </div>
              <p className="text-[11px] leading-relaxed text-slate-400">{m.content}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}