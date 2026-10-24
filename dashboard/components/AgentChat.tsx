"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { agent } from "@/lib/identity";
import { apiBase } from "@/lib/api";


type Turn = {
  role: "user" | "agent";
  text: string;
  sources?: string[];
  model?: boolean;
};

const SUGGESTIONS: Record<string, string[]> = {
  veterinarian: [
    "Which barns are closest to heat stress?",
    "What does rumination tell you before the index does?",
  ],
  maintenance: [
    "Which pivot is closest to failure?",
    "What happened on PIVOT-3?",
  ],
  agronomist: [
    "How much water is left in this year's envelope?",
    "Which field is drying fastest?",
  ],
  logistics: ["How many hours of feed cover do we have?", "Any silo in trouble?"],
  milking: ["Is the milk good enough to sell?", "Why does parlour downtime matter?"],
  calving: ["How are the heifers tracking to target?", "Any calf groups at risk?"],
  crop: ["When should we cut the next field?", "Is soil moisture where it should be?"],
};

export function AgentChat({
  agentId,
  onClose,
}: {
  agentId: string;
  onClose: () => void;
}) {
  const ident = agent(agentId);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLDivElement | null>(null);
  // The card that opens this drawer is inside an animated, transformed
  // ancestor, and a transform makes that ancestor the containing block for
  // position:fixed -- the panel would size itself to the card instead of the
  // viewport. Portalling to <body> sidesteps it entirely.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setText("");
    setTurns((t) => [...t, { role: "user", text: q }]);
    setBusy(true);
    try {
      const res = await fetch(`${apiBase()}/api/agents/${agentId}/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: q }),
      });
      const data = await res.json();
      setTurns((t) => [
        ...t,
        {
          role: "agent",
          text: data.answer || data.error || "No answer.",
          sources: data.sources || [],
          model: Boolean(data.model),
        },
      ]);
    } catch {
      setTurns((t) => [
        ...t,
        { role: "agent", text: "I could not reach the site service just now." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[80] flex justify-end">
      <button
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
      />
      <aside
        className="relative flex h-full w-full max-w-[440px] flex-col border-l bg-ink-1000 shadow-2xl"
        style={{ borderColor: `${ident.hex}44` }}
      >
        <header
          className="flex items-start gap-3 border-b px-4 py-3.5"
          style={{ borderColor: "#1e2b36" }}
        >
          <span
            className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-[11px] font-bold"
            style={{ background: `${ident.hex}1f`, color: ident.hex, border: `1px solid ${ident.hex}44` }}
          >
            {ident.mono}
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-[13.5px] font-semibold text-slate-100">{ident.name}</h2>
            <p className="text-[10.5px] text-slate-500">
              {ident.role} · answers from readings, references and its own history
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded px-2 py-1 text-[11px] text-slate-500 hover:bg-white/5 hover:text-slate-200"
          >
            Close
          </button>
        </header>

        <div ref={scroller} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {turns.length === 0 && (
            <div className="space-y-2">
              <p className="text-[11.5px] leading-relaxed text-slate-500">
                Ask this agent about its domain. It answers from what it is reading now,
                the reference documents it works from, and what it has already seen here.
              </p>
              {(SUGGESTIONS[agentId] ?? []).map((s) => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  className="block w-full rounded-lg border border-white/[0.07] bg-white/[0.02] px-3 py-2 text-left text-[11.5px] text-slate-400 hover:border-white/15 hover:text-slate-200"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {turns.map((t, i) => (
            <div key={i} className={t.role === "user" ? "flex justify-end" : ""}>
              <div
                className={
                  t.role === "user"
                    ? "max-w-[85%] rounded-xl rounded-br-sm bg-sig-500/15 px-3 py-2 text-[12px] text-slate-200"
                    : "max-w-[92%] rounded-xl rounded-bl-sm border border-white/[0.07] bg-white/[0.02] px-3 py-2.5"
                }
              >
                <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-slate-300">
                  {t.text}
                </p>
                {t.role === "agent" && (t.sources?.length ?? 0) > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5 border-t border-white/[0.06] pt-2">
                    {t.sources!.map((s) => (
                      <span
                        key={s}
                        className="rounded border border-white/[0.08] px-1.5 py-0.5 font-mono text-[9px] text-slate-500"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}
                {t.role === "agent" && (
                  <p className="mt-1.5 text-[9px] uppercase tracking-[0.12em] text-slate-600">
                    {t.model ? "written by llm from retrieved sources" : "composed from retrieved sources"}
                  </p>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <p className="text-[11px] text-slate-500">
              {ident.name} is checking its readings and references…
            </p>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(text);
          }}
          className="border-t px-4 py-3"
          style={{ borderColor: "#1e2b36" }}
        >
          <div className="flex items-end gap-2">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(text);
                }
              }}
              rows={1}
              placeholder={`Ask the ${ident.name.toLowerCase()}…`}
              className="max-h-24 min-h-[38px] flex-1 resize-none rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-[12px] text-slate-200 outline-none placeholder:text-slate-600 focus:border-sig-500/50"
            />
            <button
              type="submit"
              disabled={busy || !text.trim()}
              className="h-[38px] rounded-lg bg-sig-500 px-3.5 text-[12px] font-semibold text-ink-1000 disabled:opacity-40"
            >
              Ask
            </button>
          </div>
        </form>
      </aside>
    </div>,
    document.body,
  );
}
