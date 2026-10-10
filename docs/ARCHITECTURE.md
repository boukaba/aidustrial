# Architecture

Layer by layer, with the reasoning behind each boundary.

---

## Layer 0 — Digital twin (`twin/`)

A simulation of the Adrar site, seeded with researched parameters. It exists
because the real thing has no telemetry yet — see
[`DATA_PROVENANCE.md`](DATA_PROVENANCE.md) for the honest framing.

| Module | Responsibility |
|---|---|
| `constants.py` | Every physical parameter, plus a `provenance` dict that classifies each as sourced / derived / industry / assumption / design / modelled. The dict is machine-readable and surfaced at `GET /api/health`. |
| `clock.py` | Deterministic simulated time. One tick = 30 simulated minutes, so a day is 48 ticks and the diurnal cycle is reproducible from a seed. |
| `environment.py` | Soil water balance, aquifer stock, pivot telemetry. |
| `herd.py` | Per-barn physiology: heat load → rumination → milk yield, mediated by cooling. |
| `logistics.py` | Silo inventory, tanker dispatch cycle, US cattle airlift. |
| `world.py` | Binds the three, runs the scenario, exposes `observe()` and `apply_action()`. |

### Physics worth knowing about

**The diurnal curve is a true 24 h sinusoid.** The first attempt used a
partial-span cosine anchored at 15:00/05:00, which made temperature *cliff* in
the evening like a sunset instead of holding a shoulder. Real desert nights
linger. A full-period sinusoid puts the maximum at 15:00 and the minimum at 03:00,
which is close to the observed pre-dawn minimum.

**Evaporation integrates as a daily rate.** ET₀ is mm/**day**. The first
implementation treated it as a per-tick quantity and halved it, overstating
evaporation 24-fold and crashing every field to wilting point within two days.

**Heat load is not air temperature.** See `clock.effective_heat_load`. Air THI
plus exposure-weighted radiant load, with solar peaking at noon and temperature
peaking at 15:00.

**The aquifer is judged on projected annual draw**, not on stock. A seven-day
demo cannot deplete a fossil aquifer, but it can immediately show whether the
current allocation, held for a year, would breach the 2.5–4 bn m³ envelope. That
is the number the orchestrator needs in order to arbitrate.

**Milk tankers cycle.** load → transit → unload → dwell → load. The first version
discharged on every tick regardless of state and emptied the entire fleet on day 0.

### Determinism

Every run is reproducible from a seed, so an audit question — "why did the vet
escalate on tick 216?" — has an exact replay.

---

## Layer 1 — Sensory cortex (`tools/`)

### `sensors.py` — the boundary

Agents never touch twin internals. They call a tool and get a dict. This is the
only module that would be rewritten to go live: reimplement it against Valmont
pivot telemetry, smart collars, parlour yield systems, silo load cells, GPS
telematics and well meters, and nothing above it changes.

The gateway holds the live `World` as a module-level binding rather than
threading it through graph state, because LangGraph checkpoints every channel
through msgpack and the simulation cannot be serialised.

### `actions.py` — the risk model

Risk scoring is an explicit deterministic function of its inputs. No model, no
randomness, no hidden weights. If the score shown to a human cannot be
reconstructed, the human-in-the-loop step is theatre.

**Risk** — how dangerous is this action?
- base severity (5 → 85)
- headcount affected
- water moved, especially from a non-renewable source
- resource class (routine / scarce hardware / shared budget / non-renewable aquifer)
- reversibility

**Urgency** — how soon must it happen?
- animal welfare involved
- hours until irreversible harm
- does the window close, does the damage compound daily

These are **independent axes** and the gate queue sorts by urgency first. An early
build sorted by risk alone and buried a live heat emergency for 33,250 head
behind irrigation for standing crop.

`ALWAYS_GATE_ACTIONS` — anything touching the contested aquifer or animal
welfare — is never auto-executed regardless of score.

---

## Layer 2 — Specialists (`agents/specialists.py`)

Four agents. Each has a narrow mandate, an explicit escalation rule, bounded
memory (capped at 8 entries — an agent with unbounded memory eventually narrates
its own history back to itself instead of reading the site), and returns findings
and proposals. None of them mutate the world.

**Agronomist** — soil moisture and the pivot fleet. Judges irrigation proposals
against projected *annual* draw, not today's moisture reading. A single wet year
you cannot get back.

**Veterinarian** — herd health and heat. Knows that rumination collapses before
core temperature does, so it acts on rumination rather than waiting for THI. When
only some barns have cooling hardware, it ranks barns by projected animal harm
and reports the uncovered ones explicitly rather than silently cooling what it
can.

**Maintenance** — machinery. Vibration precedes bearing temperature; both precede
failure. Ignores bulk-feed silos, which are tipper-fed and have no conveyor to
stall.

**Logistics** — feed and cold chain. Owns the structural problem that the herd
arrives by air in November 2026 while the fodder to feed it needs a full growing
season.

---

## Layer 3 — Orchestrator (`graph/orchestrator.py`)

The orchestrator does no work. It routes, it gates, and it logs.

```
START → sense → triage → wake → consult → gate ─┬─→ execute → done → END
                                                └─→ human_gate ⏸
                                                        ↓ resume
                                                   human_gate ⟲ (drain queue)
                                                        ↓
                                                      done
```

**`sense`** advances one tick through the sensor gateway and records the tick's
environmental context in the trace.

**`triage`** decides who wakes, before any agent burns tokens. Severity thresholds
plus compound conditions — the veterinarian wakes on heat band *or* rumination
deficit, the agronomist on wilting fields *or* aquifer pressure.

**`wake`** runs each focused specialist.

**`consult`** cross-consults. A veterinary finding does not move irrigation by
itself; the agronomist has to say whether water can be reallocated. This is what
makes the swarm a swarm rather than four dashboards.

**`gate`** does three things, in order:
1. **Deduplicate** on `(action, target)` — cross-consult legitimately re-runs a
   peer and would otherwise double-propose. Three agents independently noticing a
   hot bearing is a *finding* worth keeping; three identical *actions* are not.
2. **Filter satisfied actions** — never propose starting a pivot that is already
   running, enabling misting that is already on, or restarting an inlet already
   restarted. This is the classic agent failure and it fills the human gate with
   noise.
3. **Batch** same-action proposals into one decision. Six pivots at wilting point
   is one decision, not six. Asking the same question six times trains people to
   approve reflexively.

Then it splits survivors into auto-executable (below the risk ceiling) and
human-gated (at or above, or on the always-gate list), ordered by urgency.

**`human_gate`** calls LangGraph's `interrupt()`. The graph genuinely suspends —
no polling loop, no fake waiting state — and resumes from any process given the
thread id and a `Command(resume=...)`. Requires a checkpointer; `MemorySaver` in
development, `SqliteSaver` to survive restarts.

**`execute`** applies auto-cleared actions only. It never touches anything in the
gate queue.

---

## Layer 3.5 — Transport (`server/app.py`)

One session per thread, holding the twin and the graph thread id.

- `WS /ws/stream` — continuous telemetry and agent trace
- `POST /api/decide/{thread}` — the Farm Director's verdict, resumes the thread
- `GET /api/health` — agents plus the full provenance register

When a decision is outstanding the world **pauses**. That is the correct
behaviour for an agentic operations system: the swarm does not steamroll ahead
while a person is deciding. The demo opens at Day 3 midday so a viewer lands
inside the scenario rather than watching two quiet days of baseline.

---

## Layer 4 — HITL Command Center (`dashboard/`)

Next.js App Router, Tailwind, one WebSocket.

The gate is the centrepiece and shows what a human needs in order to decide
rather than rubber-stamp:

- what the agent wants, and on what target
- **rationale** in plain language
- **blast radius** — what breaks if this is wrong
- **cost of inaction** — what happens if we do nothing
- **why it was escalated** — the risk factors, itemised
- **risk and urgency** as separate scored axes
- **reversibility**
- the underlying **evidence** values
- how many further decisions are queued

Nothing auto-executes above the ceiling. The director can approve or reject with
a note, and both are recorded in the audit trail.