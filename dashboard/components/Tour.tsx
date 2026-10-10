"use client";

import { useEffect, useState } from "react";
import type { Packet } from "@/lib/types";
import { AreaId } from "@/lib/explain";

interface Stop {
  area: AreaId | null;
  title: string;
  body: string;
  look: string;
}

const STOPS: Stop[] = [
  {
    area: null,
    title: "This is a farm in the Sahara",
    body:
      "A 3.5 billion dollar dairy project in Adrar, Algeria. 33,000 head of cows, growing its own feed, on groundwater that does not refill. The system below watches all of it and asks you for a decision when something needs a human.",
    look: "Start at the top: the six tiles are the site's vital signs.",
  },
  {
    area: "crop",
    title: "The farm grows its own feed",
    body:
      "Six fields, irrigated by centre pivots. Everything the cows eat is grown here. Notice the soil-water bars — if one hits zero the crop stops growing entirely, and that is a permanent loss for the season, not a delay.",
    look: "Click any metric for a plain-English explanation of what it means.",
  },
  {
    area: "livestock",
    title: "Most of the herd does not pay for itself yet",
    body:
      "This is the single most important fact about the project. The 30,000 animals arriving by air from the United States are mostly heifers — they will not give milk for roughly 18 months. Until then they consume feed and water without returning anything.",
    look: "The heifer bars show how close each group is to breeding weight.",
  },
  {
    area: "milk",
    title: "Volume and quality are different problems",
    body:
      "The parlour can run at full speed while the milk still fails its quality test. High cell counts come from infection in the cows, not from the plant — so the problem is reported by the milk specialist and fixed by the herd specialist.",
    look: "Watch the cold chain and the cell count separately.",
  },
  {
    area: "infrastructure",
    title: "The real constraint is hardware, not water",
    body:
      "It is tempting to think cooling competes with irrigation for the aquifer. The arithmetic does not support it: four misting banks draw 53 cubic metres an hour against 27,000 for the pivots. Cooling was only installed in half the barns — that is the genuine bottleneck.",
    look: "Compare the water budget against the cooling hardware panel.",
  },
  {
    area: "mesh",
    title: "The specialists argue with each other",
    body:
      "Seven agents share one board. In the first round they all look at the site and post what they see. In the second round, only the agents that were actually asked something wake up and answer. That is why one decision never gets made on a single point of view.",
    look: "Read the messages top to bottom — question, then answer.",
  },
  {
    area: null,
    title: "Now the part that needs you",
    body:
      "When the agents agree something is consequential, the whole system stops and waits. You get the reasoning, what breaks if it is wrong, what happens if you do nothing, and the numbers behind it. Nothing above the risk line ever runs on its own.",
    look: "Approve or reject. Both are recorded.",
  },
];

export function GuidedTour({
  p,
  onSelectArea,
  hasPending,
}: {
  p: Packet;
  onSelectArea: (a: AreaId | null) => void;
  hasPending: boolean;
}) {
  const [step, setStep] = useState<number | null>(null);

  useEffect(() => {
    if (step === null) return;
    const s = STOPS[step];
    onSelectArea(s.area);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  useEffect(() => {
    if (step === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setStep(null);
      if (e.key === "ArrowRight") setStep((s) => (s === null ? null : Math.min(STOPS.length - 1, s + 1)));
      if (e.key === "ArrowLeft") setStep((s) => (s === null ? null : Math.max(0, s - 1)));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step]);

  if (step === null) {
    return (
      <button
        onClick={() => setStep(0)}
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
    );
  }

  const s = STOPS[step];
  const last = step === STOPS.length - 1;

  return (
    <div className="card border-sig-500/40 p-4">
      <div className="mb-3 flex items-center gap-3">
        <span className="rounded bg-sig-500/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-sig-400">
          TOUR {step + 1} / {STOPS.length}
        </span>
        <h3 className="text-sm font-semibold text-slate-100">{s.title}</h3>
        <button
          onClick={() => setStep(null)}
          className="ml-auto text-[10px] text-slate-500 hover:text-slate-300"
        >
          Exit tour (esc)
        </button>
      </div>

      <p className="text-sm leading-relaxed text-slate-300">{s.body}</p>
      <p className="mt-2 text-xs text-sig-400">↳ {s.look}</p>

      {last && hasPending && (
        <p className="mt-3 rounded border border-fuchsia-500/30 bg-fuchsia-500/10 p-2.5 text-xs text-fuchsia-300">
          A decision is waiting for you right now — scroll down to the decision panel.
        </p>
      )}

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={() => setStep((v) => Math.max(0, (v ?? 0) - 1))}
          disabled={step === 0}
          className="rounded border border-ink-600 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-ink-800 disabled:opacity-30"
        >
          ← Back
        </button>
        {last ? (
          <button
            onClick={() => setStep(null)}
            className="rounded bg-sig-600 px-4 py-1.5 text-xs font-semibold text-ink-950 transition hover:bg-sig-500"
          >
            Explore on my own
          </button>
        ) : (
          <button
            onClick={() => setStep((v) => Math.min(STOPS.length - 1, (v ?? 0) + 1))}
            className="rounded bg-sig-600 px-4 py-1.5 text-xs font-semibold text-ink-950 transition hover:bg-sig-500"
          >
            Next →
          </button>
        )}
        <div className="ml-auto flex gap-1">
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
      </div>
    </div>
  );
}