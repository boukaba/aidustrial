# aidustrial

An agentic operations layer for industrial agro-complexes.

**Built around:** Baladna Algeria — the USD 3.5 billion integrated dairy and
milk powder project in Adrar Province, Wilaya of Adrar, Algerian Sahara.
Every parameter in the twin comes from that project's published figures.

We have no relationship with Baladna and are not in contact with them. The site
was chosen for its constraints, not its connections: 270,000 head on a
non-renewable fossil aquifer, misting hardware in only 4 of 8 barns, and a herd
arriving by air before its fodder programme has grown. The tool boundary
(`tools/sensors.py`) is the seam — the system could be integrated there in full
if a partnership ever becomes real.

---

## What this is

Four specialist agents observe a facility through a tool layer, an orchestrator
routes between them, and anything consequential stops and asks a human.

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 4   HITL Command Center — Next.js                              │
│          Farm Director approves / rejects. Shows the agent's        │
│          evidence, risk score, blast radius, cost of inaction.       │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 3   Orchestrator — LangGraph state machine                     │
│          Routes context. Owns the gate. Does no work itself.        │
│          sense → triage → wake → consult → gate → ┬→ execute         │
│                                                  └→ human_gate ⏸     │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 2   Agronomist · Veterinarian · Maintenance · Logistics        │
│          Narrow mandate, explicit decision rule, bounded memory.     │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 1   Sensory Cortex — tools                                     │
│          Telemetry · veterinary · assets · logistics.                │
│          The ONLY boundary between agents and the world.             │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 0   Digital twin — Adrar site simulation                       │
│          Seeded with researched Baladna parameters.                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Run it

Two runtimes.

```bash
# 1. agent core — LangGraph + FastAPI on :8781
cd agent
uv run uvicorn aidustrial.server.app:app --app-dir src --port 8781

# 2. dashboard — Next.js on :3010
cd dashboard
pnpm install && pnpm exec next dev -p 3010
```

Open <http://localhost:3010>. The session opens at **Day 3, midday** — the pump
failure has just happened, and the heatwave starts tomorrow.

Point the dashboard at a different backend with `NEXT_PUBLIC_AGENT_API`.

## Test it

```bash
cd agent
uv run pytest tests/ -q      # 23 tests
```

The suite guards the properties that make the demo defensible rather than
decorative — that the diurnal curve is a real 24 h cycle, that dry-arid heat is
genuinely *less* lethal than humid heat and radiant load is what makes Adrar hard
anyway, that agents never re-propose an action already satisfied, and that
risk and urgency stay independent axes.

## The decisions that matter

Most of the build was getting four things wrong first and then being honest about
it. These are the ones worth knowing before you read the code.

**Risk and urgency are different axes.** Sorting the human queue by risk buried
live animal emergencies under irrigation. A routine pivot restart can be riskier
than a well-scoped cooling call; the queue is now ordered by urgency (how soon
harm becomes irreversible) and only then by risk (how dangerous the action is).

**Cooling is scarce hardware, not scarce water.** The obvious framing — cooling
water competes with irrigation for the aquifer — is false by a factor of 500:

```
4 misting banks       =     53 m³/h
6 centre pivots       = 27,143 m³/h
33,250 cows drinking  =    ~111 m³/h
```

Phase 1 installed misting in 4 of 8 barns. So the real decision is not "turn
cooling on" but **which barns get it** — a genuine allocation under scarcity.
That is both the more honest demo and the better one.

**Air THI says Adrar is fine, and it is right.** At 43 °C and ~10 % RH the NRC
index sits near 41, well under the 68 that starts dairy heat stress. Pretending
otherwise would be the fastest way for anyone who has run a dairy to dismiss the
whole thing. The risk is radiant load, so the twin computes
`Effective Heat Load = air THI + exposure-weighted solar load`.

**The agents must not nag.** The first working build re-proposed
`repair_pivot PIVOT-3` every single tick. Six pivots at wilting point also
produced six identical prompts. Real systems that do this train their operator
to approve reflexively, which defeats human-in-the-loop entirely. Fixed by
idempotence guards, request batching, and a re-proposal cooldown.

**The world is not graph state.** LangGraph checkpoints every channel through
msgpack. The `World` is live process state owned by the session and reached
through the sensor gateway — putting it in the graph state is both wrong and
physically impossible.

## Layout

```
agent/src/aidustrial/
  twin/          Layer 0 — clock, environment, herd, logistics, world
    constants.py   every parameter + machine-readable provenance dict
  tools/         Layer 1 — sensors.py (the boundary), actions.py (risk model)
  agents/        Layer 2 — specialists.py, four agents with real prompts
  graph/         Layer 3 — orchestrator.py (LangGraph), state.py
  server/        FastAPI + WebSocket bridge
dashboard/       Layer 4 — Next.js App Router, Tailwind
docs/
  ARCHITECTURE.md    layer-by-layer detail
  DATA_PROVENANCE.md sourced / derived / modelled split — read this first
  PITCH.md           the investor and judge narrative
```

## Honesty

The Adrar site **has no operating herd and no live telemetry.** 45 wells are
drilled, one barley crop harvested, 30,000 cows land November 2026, first milk
powder late 2027. Every dashboard number is simulated and labelled as such.

The reframe: the highest-value time to deploy agentic operations is *before* the
first animal arrives — and that is precisely the window Baladna is in now.
[`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md) classifies every constant and
names the assumptions worth arguing with.

## Swapping the twin for real

`sensors.py` is the only module that knows it is talking to a simulation.
Reimplement it against Valmont/AFKO pivot telemetry, herd smart collars, parlour
yield systems, silo load cells, GPS telematics and well meters — and nothing
above the tool layer changes.