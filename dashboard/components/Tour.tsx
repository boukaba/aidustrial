"use client";

import { useCallback, useEffect, useState } from "react";
import type { Packet } from "@/lib/types";
import { AGENT_NAME, NavId } from "@/lib/language";

/**
 * The 60-second tour, as a modal.
 *
 * Two decisions worth recording. First, it is a modal rather than an inline
 * card: the inline version expanded inside the page and pushed the actual farm
 * content around, so a visitor who opened it lost sight of the thing it was
 * describing. Second, every stop carries LIVE numbers drawn from the same
 * packet the dashboard renders. A tour that explains "this is live" while
 * showing a screenshot of it would be proving nothing.
 */

interface Live {
  label: string;
  value: string;
  tone?: "ok" | "act" | "stop";
}

interface Stop {
  area: NavId | null;
  title: string;
  body: string;
  look: string;
  live: (p: Packet) => Live[];
}

const n = (v: number, dp = 0) =>
  v.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp });

const STOPS: Stop[] = [
  {
    area: null,
    title: "This is a farm in the Sahara",
    body:
      "A 3.5 billion dollar dairy project in Adrar, Algeria. Growing its own feed, on groundwater that does not refill. The system watches all of it and asks you for a decision when something needs a human.",
    look: "The three cards behind this dialog are the whole farm in one view: food, cows, milk.",
    live: (p) => [
      { label: "Animals on the farm", value: n(p.livestock.total_head) },
      { label: "Milk made today", value: `${n(p.milk_production.daily_milk_kg / 1000, 1)} t` },
      { label: "Water used this year", value: `${n(p.environment.aquifer_budget_used_pct, 1)}%` },
    ],
  },
  {
    area: "crop",
    title: "The farm grows its own feed",
    body:
      "Six fields, irrigated by centre pivots. Everything the cows eat is grown here. If a field's soil water runs out the crop stops entirely — that is a permanent loss for the season, not a delay.",
    look: "Every number here has a plain-English explanation behind it.",
    live: (p) => {
      const driest = Math.min(...p.crop_production.fields.map((f) => f.soil_moisture_pct));
      return [
        { label: "Food growing right now", value: `${n(p.crop_production.standing_t)} t` },
        { label: "Driest field", value: `${n(driest, 1)}% soil water`, tone: driest <= 9 ? "stop" : driest < 22 ? "act" : "ok" },
        { label: "Fields short of water", value: `${p.crop_production.water_stressed_ha} ha`, tone: p.crop_production.water_stressed_ha ? "act" : "ok" },
      ];
    },
  },
  {
    area: "livestock",
    title: "Most of the herd does not pay for itself yet",
    body:
      "This is the single most important fact about the project. The animals arriving by air from the United States are mostly heifers — they will not give milk for roughly 18 months. Until then they eat feed and water and return nothing.",
    look: "The heifer bars show how close each group is to breeding weight.",
    live: (p) => {
      const pct = (p.livestock.non_productive_head / p.livestock.total_head) * 100;
      return [
        { label: "Total animals", value: n(p.livestock.total_head) },
        { label: "Eating, not yet producing", value: `${n(pct, 1)}%`, tone: pct > 30 ? "act" : "ok" },
        { label: "Calves lost this week", value: n(p.livestock.calf_mortality_7d), tone: p.livestock.calf_mortality_7d > 20 ? "act" : "ok" },
      ];
    },
  },
  {
    area: "milk",
    title: "Volume and quality are different problems",
    body:
      "The parlour can run flat out while the milk still fails its quality test. High cell counts come from infection in the cows, not from the plant — so the problem is reported by the milk specialist and fixed by the herd specialist.",
    look: "Watch the cold chain and the cell count separately.",
    live: (p) => {
      const m = p.milk_production;
      const over = m.bulk_scc_k > m.scc_limit_k;
      return [
        { label: "Milk made today", value: `${n(m.daily_milk_kg / 1000, 1)} t` },
        { label: "Cows milked per hour", value: n(m.throughput_cows_per_hour) },
        { label: "Cell count", value: `${n(m.bulk_scc_k)}k (limit ${n(m.scc_limit_k)}k)`, tone: over ? "act" : "ok" },
      ];
    },
  },
  {
    area: "infrastructure",
    title: "The real constraint is hardware, not water",
    body:
      "It is tempting to think cooling competes with irrigation for the aquifer. The arithmetic does not support it: four misting banks draw 53 cubic metres an hour against 27,000 for the pivots. Cooling was only installed in half the barns — that is the genuine bottleneck.",
    look: "Compare the water budget against the cooling hardware.",
    live: (p) => {
      const stopped = p.environment.pivots.filter((x) => !x.running).length;
      const sick = p.environment.pivots.filter((x) => x.health !== "nominal").length;
      return [
        { label: "Pivots running", value: `${p.environment.pivots.length - stopped} of ${p.environment.pivots.length}`, tone: stopped ? "act" : "ok" },
        { label: "Machines need work", value: n(sick), tone: sick ? "act" : "ok" },
        { label: "Feed in store", value: `${n(p.logistics.feed_hours_of_cover)} h`, tone: p.logistics.feed_hours_of_cover < 24 ? "stop" : p.logistics.feed_hours_of_cover < 72 ? "act" : "ok" },
      ];
    },
  },
  {
    area: "agents",
    title: "Seven specialists, arguing with each other",
    body:
      "Seven agents share one board. In the first round they each look at the site and post what they see. In the second round, only the agents that were actually asked something wake up and answer. That is why one decision never gets made on a single point of view.",
    look: "Read the messages top to bottom — question, then answer.",
    live: (p) => {
      const answered = new Set(p.board.map((m) => m.in_reply_to).filter(Boolean));
      const open = p.board.filter((m) => m.expects_reply && !answered.has(m.message_id));
      const senders = [...new Set(p.board.map((m) => m.sender))];
      return [
        { label: "Messages on the board", value: n(p.board.length) },
        { label: "Still unanswered", value: n(open.length), tone: open.length ? "act" : "ok" },
        { label: "Specialists talking", value: senders.length ? senders.map((s) => AGENT_NAME[s] ?? s).join(", ") : "first round starting" },
      ];
    },
  },
  {
    area: "decisions",
    title: "Now the part that needs you",
    body:
      "When the agents agree something is consequential, the whole system stops and waits. You get the reasoning, what breaks if it is wrong, what happens if you do nothing, and the numbers behind it. Nothing above the risk line ever runs on its own.",
    look: "Approve or reject. Both are recorded.",
    live: () => [],
  },
];

const TONE: Record<string, string> = {
  ok: "text-slate-100",
  act: "text-warn-300",
  stop: "text-crit-300",
};

export function GuidedTour({
  p,
  hasPending,
  onSelectArea,
}: {
  p: Packet;
  hasPending: boolean;
  onSelectArea: (a: NavId) => void;
}) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  const close = useCallback(() => {
    setOpen(false);
    setStep(0);
  }, []);

  const next = useCallback(() => setStep((s) => Math.min(STOPS.length - 1, s + 1)), []);
  const prev = useCallback(() => setStep((s) => Math.max(0, s - 1)), []);

  // Close the dialog and hand the visitor over to the screen this stop is about.
  const goThere = useCallback(() => {
    const target = STOPS[step].area;
    close();
    if (target) onSelectArea(target);
  }, [step, close, onSelectArea]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    // stop the page behind from scrolling while the dialog is up
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, close, next, prev]);

  const s = STOPS[step];
  const last = step === STOPS.length - 1;
  const rows = s.live(p);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="group flex items-center gap-2.5 rounded-lg border border-sig-500/40 bg-sig-500/10 px-4 py-2.5 text-left transition hover:bg-sig-500/20"
      >
        <span className="text-lg" aria-hidden>
          👋
        </span>
        <span>
          <span className="block text-xs font-semibold text-sig-400">
            New here? Take the 60-second tour
          </span>
          <span className="block text-[10px] text-slate-400">
            Seven short stops, no technical background needed
          </span>
        </span>
        <span className="ml-1 text-sig-400 transition-transform group-hover:translate-x-0.5">→</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="60-second tour"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) close();
          }}
        >
          <div className="card w-full max-w-lg border-sig-500/40 p-5 shadow-2xl">
            <header className="mb-4 flex items-start gap-3">
              <span className="mt-0.5 shrink-0 rounded bg-sig-500/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-sig-400">
                {step + 1} / {STOPS.length}
              </span>
              <h3 className="flex-1 text-base font-semibold leading-snug text-slate-100">
                {s.title}
              </h3>
              <button
                onClick={close}
                aria-label="Close tour"
                className="-mr-1 -mt-1 shrink-0 rounded p-1 text-lg leading-none text-slate-500 transition hover:bg-slate-800 hover:text-slate-200"
              >
                ✕
              </button>
            </header>

            <p className="text-sm leading-relaxed text-slate-300">{s.body}</p>

            {rows.length > 0 && (
              <section className="mt-4 rounded-md bg-slate-900/60 p-3" aria-label="live numbers">
                <p className="mb-1.5 text-[9px] font-semibold uppercase tracking-wider text-slate-600">
                  live right now
                </p>
                {rows.map((r) => (
                  <div
                    key={r.label}
                    className="flex items-baseline gap-2 border-t border-slate-800/70 py-1.5 first:border-t-0"
                  >
                    <span className="flex-1 text-[11px] leading-tight text-slate-400">
                      {r.label}
                    </span>
                    <span
                      className={`shrink-0 font-mono text-[11px] font-semibold ${TONE[r.tone ?? "ok"]}`}
                    >
                      {r.value}
                    </span>
                  </div>
                ))}
              </section>
            )}

            <p className="mt-3 text-xs text-sig-400">↳ {s.look}</p>

            {last && hasPending && (
              <p className="mt-3 rounded border border-fuchsia-500/30 bg-fuchsia-500/10 p-2.5 text-xs text-fuchsia-300">
                A decision is waiting for you right now — close this and it is on the Decisions
                screen.
              </p>
            )}

            <footer className="mt-5 flex items-center gap-2">
              <button
                onClick={prev}
                disabled={step === 0}
                className="rounded border border-ink-600 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-ink-800 disabled:opacity-30"
              >
                ← Back
              </button>
              {last ? (
                <button
                  onClick={close}
                  className="rounded bg-sig-600 px-4 py-1.5 text-xs font-semibold text-ink-950 transition hover:bg-sig-500"
                >
                  Explore on my own
                </button>
              ) : (
                <button
                  onClick={next}
                  className="rounded bg-sig-600 px-4 py-1.5 text-xs font-semibold text-ink-950 transition hover:bg-sig-500"
                >
                  Next →
                </button>
              )}

              {s.area && (
                <button
                  onClick={goThere}
                  className="rounded border border-ink-600 px-3 py-1.5 text-xs text-slate-300 transition hover:border-sig-500/50 hover:text-sig-400"
                >
                  Take me there →
                </button>
              )}

              <div className="ml-auto flex items-center gap-2">
                <div className="flex gap-1">
                  {STOPS.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => setStep(i)}
                      aria-label={`Go to stop ${i + 1}`}
                      className={`h-1.5 w-1.5 rounded-full transition ${
                        i === step ? "bg-sig-500" : "bg-ink-600 hover:bg-ink-500"
                      }`}
                    />
                  ))}
                </div>
                <button
                  onClick={close}
                  className="text-[10px] text-slate-500 transition hover:text-slate-300"
                >
                  Close
                </button>
              </div>
            </footer>
          </div>
        </div>
      )}
    </>
  );
}