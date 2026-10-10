# AGENT.md

Working notes for anyone (human or AI) picking this up: **why aidustrial
exists**, **what has actually been built**, and **which mistakes were made along
the way** so they don't get repeated.

This is not the architecture doc — that is [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
This is the *intent* and the *history*. Read `docs/DATA_PROVENANCE.md` before
quoting any number to an outside party.

---

## Why this exists

`aidustrial` is an **agentic operations layer for industrial agro-complexes** —
software where specialist agents watch a facility, each holding a narrow
mandate, hand findings to a coordinator, and stop to ask a human before anything
consequential happens.

The live demonstration is **Baladna Algeria S.P.A.**, the USD 3.5 bn integrated
dairy and milk-powder project in Adrar Province, Algerian Sahara.

The demo exists to make one idea undeniable to judges and investors:

> A farm is not run by one omniscient system. It is run by specialists who each
> see a sliver, disagree with each other, and still need to reach one safe
> decision — and that decision is ultimately a human's.

Everything in the codebase serves that argument. When a feature could either
show the idea more clearly or look more impressive, clarity wins.

**Non-negotiable honesty constraint.** Adrar has **no operating herd and no live
telemetry.** 45 wells are drilled, one barley crop harvested, ~30,000 cows land
late 2026, first milk powder late 2027. Every dashboard number is simulated and
labelled as such. The reframe: the highest-value time to deploy agentic ops is
*before* the first animal arrives — which is exactly the window Baladna is in.
We never fake "live" telemetry, and we never let a judge believe the numbers
are real.

---

## Architecture in one diagram

```
LAYER 4   HITL Command Center — Next.js           (:3010)
          Agents at work · Farm Director approves/rejects · 60s tour
LAYER 3   Orchestrator — LangGraph state machine   (:8781)
          Routes context, owns the gate, does no work itself.
          sense → triage → wake → consult → gate → ┬→ execute
                                                    └→ human_gate ⏸
LAYER 2   Seven agents — 4 specialists + 3 domain
          Crop · Agronomist · Veterinarian · Calving · Milking ·
          Maintenance · Logistics. Narrow mandate, explicit rule.
LAYER 1   Sensory Cortex — tools/sensors.py
          The ONLY boundary between agents and the world.
LAYER 0   Digital twin — Adrar site simulation
          Seeded with researched Baladna parameters.
```

---

## What we built, in order (this is also the git history)

| # | Commit | What it added |
|---|--------|---------------|
| 1 | `0f3526a` | Core: twin, sensor gateway, 4 specialist agents, LangGraph orchestrator, HITL gate, first dashboard |
| 2 | `247e428` | Ignore tool caches / build artefacts |
| 3 | `722c29e` | Tanker-dispatch realism; dropped zero-headcount evidence |
| 4 | `398f548` | Three production areas + the **seven-agent mesh** |
| 5 | `3aad954` | Plain-language layer, clickable areas, guided tour |
| 6 | `a05ee94` | Control panel with live agent telemetry, orchestration, HITL |
| 7 | `51956ac` | **Left sidebar** + a rewrite of every user-facing string for non-industrial readers |
| 8 | `36104e8` | **Made the agents visible** — `watch()` on all 7, live readings, mesh feed; fixed a calls-count bug |
| 9 | `a276f11` | 60-second tour as a **modal** with a close button, live numbers per stop |

---

## The five judgements that shaped the product

Most of the build was getting things wrong first and then being honest about it.
These are the ones worth knowing before reading the code.

**1. Cooling is scarce hardware, not scarce water.** The obvious framing —
cooling competes with irrigation for the aquifer — is false by a factor of ~500:

```
4 misting banks       =     53 m³/h
6 centre pivots       = 27,143 m³/h
33,250 cows drinking  =    ~111 m³/h
```

Phase 1 installed misting in only 4 of 8 barns. So the real decision is *which
barns get it* — a genuine allocation under scarcity. That is both the more
honest and the better demo.

**2. Risk and urgency are different axes.** Sorting the human queue by risk
buried live animal emergencies under irrigation. The queue is ordered by
**urgency** (how soon harm becomes irreversible) first, then risk.

**3. Air THI says Adrar is fine, and it is right.** At 43 °C / ~10 % RH the NRC
index sits near 41, well under the 68 that starts heat stress. Pretending
otherwise would be the fastest way for anyone who has run a dairy to dismiss the
whole thing. The real stress is radiant load, so the twin computes
`Effective Heat Load = air THI + exposure-weighted solar load`.

**4. The agents must not nag.** The first working build re-proposed
`repair_pivot PIVOT-3` every tick. Systems that nag train operators to approve
reflexively, defeating HITL. Fixed with idempotence guards, request batching,
and a re-proposal cooldown.

**5. The world is not graph state.** LangGraph checkpoints every channel via
msgpack. The `World` is live process state owned by the session and reached
through the sensor gateway — putting it in graph state is wrong and physically
impossible.

---

## Corrections we made along the way (don't repeat these)

These are real bugs/decisions we hit and fixed. Each is here so the next person
knows it was considered, not stumbled into.

- **`activity()` never counted tool calls.** It built each agent with
  `setdefault(calls=0)` and never incremented, so the "watching an agent work"
  signal read `0 reads` forever. The whole "agents are thinking" story was dead
  on arrival until this was fixed (`sensors.py`, `activity()`).
- **Agent `state` had to be time-aware.** Deriving "reading" from *any*
  historical call made every agent look permanently busy. Now an agent counts
  as `reading` only if it queried this tick or the previous one, else `idle`.
- **`projected_annual_m3h` is a genuine modelling bug** (left unfixed on
  purpose). It stuffs an instantaneous per-hour rate into an annual-budget
  comparison. Fixing it changes scenario thresholds and the test suite, so we
  relabelled the reading honestly instead of quietly changing the model. If you
  touch it, fix the model properly and update the tests.
- **The tour used to hijack the background nav.** Inline, advancing a stop
  silently switched the page behind it. As a modal that became invisible, so we
  added an explicit **"Take me there →"** button instead.
- **A regex text-surgery attempt to insert methods landed in the wrong place**
  (inside a docstring) and broke the parser. Use AST line numbers
  (`ast.parse` → `ClassDef`/`FunctionDef.end_lineno`) for any structural edit to
  a Python file in this repo. Don't regex-hack source files.

---

## How to run it

```bash
# 1. agent core — LangGraph + FastAPI on :8781
cd agent
uv run uvicorn aidustrial.server.app:app --app-dir src --port 8781

# 2. dashboard — Next.js on :3010
cd dashboard
pnpm install && pnpm exec next dev -p 3010
```

Open <http://localhost:3010>. The session opens at **Day 3, midday** — the pump
failure has just happened and the heatwave starts tomorrow, so a five-minute
judge watch lands inside the scenario.

The backend needs `langgraph`, `langchain-core`, `fastapi`, `uvicorn`. Run it
with `uv run --with ... uvicorn ...` if they are not in your environment.

## How to verify it

```bash
cd agent
uv run pytest tests/ -q      # 33 tests
uv run ruff check src/       # lint
cd ../dashboard && pnpm exec next build   # typecheck + prod build
```

The 33 tests guard the properties that make the demo defensible rather than
decorative — that the diurnal curve is a real 24 h cycle, that dry-arid heat is
genuinely *less* lethal than humid heat, that agents never re-propose a
satisfied action, and that risk and urgency stay independent axes.

---

## Conventions to follow

- **Sensors are the only boundary.** Agents never touch the world directly; they
  call `tools/sensors.py`, which is the single module that knows it is talking
  to a simulation. Swapping the twin for real telemetry means editing that file
  and nothing else.
- **Every user-facing string goes in `dashboard/lib/language.ts`.** No jargon
  in the UI. Name things by what they *do* ("Cow food", not "Crop production").
  Technical terms live behind a "details" disclosure.
- **Every constant in `twin/constants.py` carries a provenance tag**
  (SOURCED / DERIVED / ASSUMPTION / INDUSTRY / DESIGN). Do not add an untagged
  number.
- **Agents report live readings via `watch()`.** If you add an agent, give it a
  `watch()` returning `[{label, value, unit, status}]` so the Agents-at-work
  view has something true to show.
- **Don't fake "live".** If a number isn't streaming from the twin, label it.

---

## Honest status / what's next

- The demo is **judge-ready** for the pitch: left sidebar, simplified
  home, visible agents, modal tour, working HITL gate, screenshot-friendly.
- Still worth doing: surface **per-agent "thinking" traces** on the Agents view
  (the tool name is shown; a short natural-language rationale per call would
  strengthen "thinking"); possibly a real photo/thumbnail per agent for warmth.
- **The Adrar twin is simulated.** The moment real telemetry exists, point
  `sensors.py` at it and the rest of the stack is unchanged.