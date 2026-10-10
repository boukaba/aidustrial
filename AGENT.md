# AGENT.md

Working notes for anyone (human or AI) picking this up: **why aidustrial
exists**, **what has actually been built**, **where everything lives**, and
**which mistakes were made along the way** so they don't get repeated.

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
          Mission-control shell · Agents at work · Farm Director
          approves/rejects · 60s tour
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

## Where things live

Backend (`agent/src/aidustrial/`, ~6.3k lines Python, 33 tests):

```
twin/           Digital twin of the Adrar site. constants.py tags every
                number with provenance (SOURCED/DERIVED/ASSUMPTION/...).
tools/sensors.py  The ONLY module that talks to the twin. Every agent call
                goes through here. Swap in real telemetry = edit this file.
tools/llm.py    ★ The reasoning brain. Thread-safe queue, async drain,
                escalation-only validation, JSON repair, action filtering.
tools/actions.py  Action/Finding dataclasses + score_risk/score_urgency.
                Risk scoring is deterministic and NEVER touched by the LLM.
agents/specialists.py  Vet, agronomist, maintenance, logistics. Each has a
                run() that decides, and a watch() that reports live readings.
agents/domains.py     Crop, calving, milking. Same shape.
agents/reasoning.py   ★ Prompt construction + the escalation-only merge of
                an LLM verdict into rule output. READERS per agent, OWNED
                action vocabulary, _trim byte budgets.
agents/narrator.py    ★ The hidden eighth agent. Plain-language observations.
                Proposes nothing, gates nothing.
agents/mesh.py   Blackboard + digest() (now actually used, for prompts).
graph/orchestrator.py LangGraph state machine. ALL = 7 agents combined.
                wake_specialists requests reasoning and merges verdicts.
server/app.py   FastAPI + WebSocket. Starts the brain + narrator tasks.
                snapshot() exposes llm + narration + per-agent rationale.
tests/          59 cases. test_llm.py guards the safety invariants (no
                network in the suite).
```

Frontend (`dashboard/`, ~5.6k lines TS/TSX):

```
app/page.tsx        The shell. Nav routing, status header, DecisionStrip,
                    and the view switch. Start here.
app/globals.css     Design primitives: .card, .rail, .hot, .readout,
                    drifting grid + scan line + vignette background,
                    prefers-reduced-motion guard.
tailwind.config.ts  Palette (ink.*), per-agent colors (colors.agent.*),
                    animations (pulse/flash/scan/flow/sweep), glow shadows.
lib/identity.ts     ★ Canonical agent registry: id, name, monogram, role,
                    color hex, SVG glyph. One import, one source of truth.
lib/language.ts     Every user-facing string. NAV, glossary, status text.
                    Re-exports agentName/agentRole from identity.
lib/explain.ts      Plain-language explanations of every technical reading.
lib/types.ts        StreamMessage (incl. `mesh`, `llm`, `narration`),
                    AGENT_COLOR.
components/Icons.tsx    ★ All SVG glyphs: AgentGlyph, AgentBadge, NavGlyph,
                    UI gear/triangle. Replaces every emoji.
components/Live.tsx     ★ Liveness primitives: LiveNumber (flashes its own
                    color on change), StatusChip, SevChip, ReadingRow.
components/Agents.tsx   The money shot. SignalFlow diagram (7 agents → bus →
                    OR), hero stats with REASONED, AgentCard grid showing
                    each model's rationale + attribution, MessageFeed.
components/Control.tsx  useFarmStream hook, DecisionStrip (slim, sticky),
                    DecisionGate (full, on Decisions screen).
components/Home.tsx     Identity-colored status cards with flashing numbers.
components/Sidebar.tsx  Glyph nav, lit active rail, LIVE indicator, sim clock.
components/AreaDetail.tsx  Detail views. Wraps each area in its specialist's
                    --agent CSS var for a lit hairline accent.
components/Tour.tsx     60s modal tour, 7 stops, live numbers per stop.
components/ControlPanel.tsx  Right-side technical panel (trace, findings,
                    events, speed). The "details" disclosure.
components/Panels.tsx   EventsPanel, FindingsPanel, TraceFeed used on System.
components/Mesh.tsx     MeshBoard — the raw 7×N mesh grid on System.
components/AreaNav.tsx  PlainNote, Term — plain-language helper widgets.
components/Areas.tsx    ★ DEAD CODE — 310 lines, zero imports. The old
                    crop/livestock/milk views, superseded by AreaDetail.
                    Safe to delete.
```

★ = files you will touch most. `lib/identity.ts` and `components/Live.tsx`
are the load-bearing pieces of the mission-control look.

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
| 10 | `fbe0537` | This document |
| 11 | `cd35380` | **Mission-control rebuild** — per-agent identity, SVG glyphs everywhere, flash-on-change numbers, signal-flow diagram, slim decision strip |
| 12 | `6c6b1d6` | This document as a session-handoff (file map, exact commands, loose ends) |
| 13 | `8521ba6` | **The agents actually reason** — free-LLM decision path, hidden narrator agent, escalation-only safety rules |

---

## The reasoning layer (commit 13)

The seven agents used to be pure threshold machines: `if soil_moisture <=
wilting: propose start_pivot`. Defensible, testable, and not intelligence. A
judge watching for thirty seconds could tell.

Now each agent's `survey()` still runs its rules first (the floor that keeps
the demo alive), then a **real language model** reasons about the same slice of
readings and produces the finding's plain-language summary, its rationale, and
optionally an action. The verdict lands a few ticks late and is merged in from
then on.

### Which backend, and why not OpenCode Zen

`TOKENHARBOR_API_KEY` is already in the environment. Token Harbor is plain
OpenAI-compatible at `https://tokenharbor.ai/v1/chat/completions`, and your
`opencode.jsonc` lists several free models on it (`mimo-v2.6-flash:free`,
`deepseek-v4-flash:free`, `claude-haiku-5.5:free`, …).

**OpenCode Zen is not usable from here.** Its free tier answers programmatic
calls with `FreeTierError: OpenCode's free tier can only be used from within
OpenCode` (HTTP 403). The key in `~/.local/share/opencode/auth.json`
(`opencode-go`) gets the same refusal. Do not waste time on it. Do not try to
route around that restriction either — it is an access control, and this
project's honesty constraint applies to how we obtain compute, not only to what
we display.

### The three constraints

**1. Latency.** A trivial call measures ~4.7s; a real reasoning call measures
6–24s. The world ticks 12×/second. So the brain **never blocks a tick**:

- `Brain.request()` is thread-safe and non-blocking (the graph runs in a worker
  thread via `asyncio.to_thread`); it only stashes a payload.
- A background `asyncio` task started on server startup drains a queue, at most
  **3 concurrent** calls, each capped at **24s**.
- Ticks keep running on rules while calls are in flight; the verdict is used
  from a later pass.
- A **22s per-agent cooldown** dedups. The twin changes every tick, so a
  content-hash cache can never hit — the cooldown is what stops hammering the
  free tier. Measured: 11 calls, 1 failure, 35 cache hits.

**2. Trust.** A flash model is a fallible narrator, not an oracle.

- It may choose *whether* an action is warranted and *how urgent*.
- It may **never set the risk score**. Risk is what routes a proposal to the
  human gate; a model that could lower its own risk could slip something past
  the gate. Risk stays with the deterministic `score_risk()`.
- It may **not de-escalate**. Severity and urgency may only *rise* from what
  the rules found.
- An action the model invents that the rules did not find is accepted only if
  it is in the known 14-action vocabulary, and is always scored **above** the
  human-gate ceiling — we have no evidence to verify it, so it faces a person.
- A rule-mandated action the model *omits* is kept anyway. Omission is the one
  failure we refuse to inherit.

**3. Degradation.** No key, or `AIDUSTRIAL_LLM=off`, and the system is
byte-for-byte the pre-LLM one. A timeout, a rate limit or a malformed response
falls back to the rules. A circuit breaker opens after 3 consecutive failures
for 45s. The original 33 tests pass unchanged.

### The hidden eighth agent

`agents/narrator.py`. It watches the same simulated physics and writes short
plain-language observations for a reader who has never run a dairy. It proposes
nothing, gates nothing, and never appears in the human decision queue — the only
kind of agent worth giving a free-form model. Runs on its own 12s cadence,
entirely off the graph tick. It even writes its own honesty disclaimer.

### Configuration

| Env var | Default | Meaning |
|---|---|---|
| `TOKENHARBOR_API_KEY` | — | Required. Absent = brain disabled, rules only. |
| `AIDUSTRIAL_LLM` | on | `off` / `0` / `false` / `no` disables everything. |
| `AIDUSTRIAL_LLM_MODEL` | `mimo-v2.6-flash:free` | Any Token Harbor free model. |
| `AIDUSTRIAL_LLM_BASE` | `https://tokenharbor.ai/v1` | OpenAI-compatible base URL. |

### What is exposed to the UI

- `snapshot.llm` — `{enabled, model, calls, failures, cache_hits, dropped_actions, last_ms, last_error, agents_reasoned, …}`.
- `snapshot.narration` — narrator stats + recent observations.
- `mesh.agents[i].thinking` / `.reasoned` / `.rationale` / `.reasoned_by` / `.reasoned_ms` — per-agent live reasoning state.

### Two bugs found and fixed here (don't repeat)

- **`request()` used `dict.get()` to mean "in flight."** `get()` returns `None`
  for both an absent key *and* a `None` value, so the guard "if already in
  flight, return" matched everything and **nothing was ever queued**. In-flight
  is now an explicit `set`. If you track two states, use two structures.
- **`_repair_truncated` only handled a cut inside a VALUE.** A cut inside a KEY
  (`..."confid`) returned `None` and discarded the whole verdict. It now walks
  the string back to the last well-formed prefix. Free models stop mid-key as
  often as mid-value.

---

## The design system, and why

The first five UI commits produced a competent but not astonishing dashboard:
a grid of identical dark cards with emoji icons, where genuinely live data
looked like a static screenshot. A judge saw fixed numbers and reasonably
concluded it was a mock. The agents are the product; the interface was failing
to show them working.

The rebuild (`cd35380`) fixed four things, in order of damage:

1. **The decision gate rendered at the top of EVERY view**, pushing ~500px of
   repeated card above whatever you had navigated to see. Now it is a slim
   sticky `DecisionStrip`; the full gate lives on the Decisions screen only.
2. **All seven agents looked identical.** No colour, no glyph, no identity.
   Now each owns a hue from `colors.agent.*`, a monogram badge, and a
   stroked SVG glyph. Seven simultaneous agents read as seven distinct signals.
3. **Nothing signalled change.** Numbers updated silently over the socket, so
   a live feed read as a screenshot. Now `LiveNumber` flashes in its own
   colour the instant the value changes. This was the single most important
   fix — "watching an agent work" was invisible before it.
4. **Emoji icons** read as a 2015 emoji picker on top of a serious interface.
   All replaced with a consistent stroked SVG system in `components/Icons.tsx`.

The ambient motion (drifting field grid, scan line, vignette) exists so the
page reads as an *instrumented room* rather than a flat sheet. It is subtle on
purpose and respects `prefers-reduced-motion`.

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
  touch it, fix the model properly and update the tests. The relabelled row is
  "Where the water comes from / fossil, not rain".
- **The tour used to hijack the background nav.** Inline, advancing a stop
  silently switched the page behind it. As a modal that became invisible, so we
  added an explicit **"Take me there →"** button instead.
- **A regex text-surgery attempt to insert methods landed in the wrong place**
  (inside a docstring) and broke the parser. Use AST line numbers
  (`ast.parse` → `ClassDef`/`FunctionDef.end_lineno`) for any structural edit to
  a Python file in this repo. Don't regex-hack source files.
- **A repeated decision gate was eating 500px of every view.** It was rendered
  unconditionally at the top of the shell, so navigating to a detail view
  pushed the content you wanted below the fold. Now `DecisionStrip` is slim,
  sticky, and only rendered when `pending` and `nav !== "decisions"`; the
  status banner is also dropped while pending so the same fact isn't stated
  twice. If you add a new view, check it doesn't reintroduce this.
- **The agronomist's water row mixed instantaneous and annual units.** Rather
  than silently change the model, we relabelled it. See the modelling-bug note
  above — same principle: honest label beats quiet fix.

---

## How to run it

Backend on `:8781` (needs `langgraph`, `langchain-core`, `fastapi`, `uvicorn`,
`websockets`, `httpx`; use `--no-project --with ...` if they are not in your env):

```bash
cd agent
uv run --no-project --with "langgraph>=0.2" --with "langchain-core>=0.3" \
  --with fastapi --with uvicorn --with websockets --with httpx \
  python -m uvicorn aidustrial.server.app:app --app-dir src --port 8781
```

For the agents to actually reason, `TOKENHARBOR_API_KEY` must be set in the
environment (it already is on this machine). Without it the system still runs,
just on rules only — check `GET /api/site/demo` → `llm.enabled`.

Frontend on `:3010` (production start; `pnpm install` first if needed):

```bash
cd dashboard
pnpm exec next start -p 3010
# or, while editing:
pnpm exec next dev -p 3010
```

Open <http://localhost:3010>. The session opens at **Day 3, midday** — the pump
failure has just happened and the heatwave starts tomorrow, so a five-minute
judge watch lands inside the scenario.

Useful knobs on the page: **Speed** (4× / 14× / 40×) and the **Panel** button
(right-side technical disclosure). The **Agents at work** screen is the money
shot — the signal-flow diagram lights a line only when that agent actually
spoke this round, and each card shows the model's own rationale under the
finding.

## How to verify it

```bash
cd agent
uv run --no-project --with "langgraph>=0.2" --with "langchain-core>=0.3" \
  --with fastapi --with uvicorn --with websockets --with httpx --with pytest \
  python -m pytest tests/ -q                    # expect 59 passed
uv run --no-project --with ruff ruff check src/ tests/   # expect clean
cd ../dashboard
pnpm exec next build                            # expect "Compiled successfully"
```

Both services up:

```bash
curl -s -o /dev/null -w "frontend %{http_code}\n" http://localhost:3010
curl -s -o /dev/null -w "backend %{http_code}\n"  http://localhost:8781/api/health
```

To confirm reasoning is live (not just rules):

```bash
curl -s http://localhost:8781/api/site/demo | python3 -c "
import json,sys; d=json.load(sys.stdin); l=d.get('llm',{})
print('enabled', l.get('enabled'), '| calls', l.get('calls'),
      '| reasoned', l.get('agents_reasoned'), '| err', l.get('last_error') or '-')"
```

Expect `enabled True`, a growing `calls`, and a non-empty `agents_reasoned`
within ~30s of a tick running. The 33 original tests guard the properties that
make the demo defensible rather than decorative — that the diurnal curve is a
real 24 h cycle, that dry-arid heat is genuinely *less* lethal than humid heat,
that agents never re-propose a satisfied action, and that risk and urgency stay
independent axes. The 26 new tests in `test_llm.py` guard the safety invariants
of the reasoning layer.

---

## Conventions to follow

- **Sensors are the only boundary.** Agents never touch the world directly; they
  call `tools/sensors.py`, which is the single module that knows it is talking
  to a simulation. Swapping the twin for real telemetry means editing that file
  and nothing else.
- **The LLM never sets a risk score.** `score_risk()` is deterministic and
  decides whether a human is consulted. A model that could lower its own risk
  could slip an action past the gate. If you add a model-driven score anywhere,
  you have broken the HITL argument.
- **A model may escalate, never de-escalate.** Severity and urgency may only
  rise from what the rules found. The rules are the floor, not a suggestion.
- **A model-proposed action is always gated.** No evidence to verify it means it
  faces a person. Never let a model-originated action auto-approve.
- **Every user-facing string goes in `dashboard/lib/language.ts`.** No jargon
  in the UI. Name things by what they *do* ("Cow food", not "Crop production").
  Technical terms live behind a "details" disclosure.
- **Every constant in `twin/constants.py` carries a provenance tag**
  (SOURCED / DERIVED / ASSUMPTION / INDUSTRY / DESIGN). Do not add an untagged
  number.
- **Agents report live readings via `watch()`.** If you add an agent, give it a
  `watch()` returning `[{label, value, unit, status}]` so the Agents-at-work
  view has something true to show.
- **Agent identity is centralised in `lib/identity.ts`.** Never hardcode a
  name, colour, monogram or glyph elsewhere. Add the agent there, import
  `agent(id)` / `agentName(id)` / `agentHex(id)`. `lib/language.ts` re-exports
  the name helpers for convenience.
- **No emoji in the UI.** Use the stroked SVG glyphs in `components/Icons.tsx`
  (`AgentGlyph`, `NavGlyph`, `UiGlyph`). If you need a new symbol, add a path
  to that file so the stroke weight stays consistent.
- **Live values use `LiveNumber`** from `components/Live.tsx`, not raw text.
  If a number changes and doesn't flash, it looks static to a judge.
- **Thread identity through a CSS variable.** Views set `--agent` to the
  specialist's hex and use the `.rail` / `.hot` / `.readout` classes from
  `globals.css`, so accents follow automatically.
- **Respect `prefers-reduced-motion`.** All ambient motion is already guarded
  in `globals.css`; keep new animations inside that guard.
- **Don't fake "live".** If a number isn't streaming from the twin, label it.
  The same applies to reasoning: if the brain is off, say so rather than
  implying the agents are thinking.

---

## Honest status / what's left

**Judge-ready** for the pitch: mission-control shell, seven visibly distinct
agents with live flashing readings, **agents that genuinely reason via a free
LLM with a hidden narrator**, signal-flow diagram, working HITL gate, modal
tour, plain-language layer throughout, screenshot-friendly.

Known loose ends, in rough priority order:

1. **`components/Areas.tsx` is dead code** (310 lines, zero imports). The old
   crop/livestock/milk views were superseded by `AreaDetail.tsx`. Delete it.
2. **The detail views (Cow food / The herd / The milk / Water & machines) are
   still list-shaped.** They inherit the identity hairline but don't have the
   live flashing treatment the Agents view has. Giving each a per-field live
   panel with `LiveNumber` + `StatusChip` is the obvious next step.
3. **The README is stale** — it still says "four specialist agents" and "23
   tests". Actual: seven agents, 59 tests. Rewrite it to match this file.
4. **Only the agents triage wakes get a reasoning call.** That is correct (an
   agent with nothing to look at should not burn the free tier) but it means a
   quiet scenario shows 2–3 agents reasoning, not 7. If you want more visible
   reasoning, either widen `triage`'s wake rules or add a low-priority "every
   agent reasons every N seconds" sweep.
5. **Reasoning latency is 6–24s** on the free tier. The tick never blocks, so
   the dashboard stays live, but a verdict arrives a few ticks late. A paid
   model would cut this to ~1s. `AIDUSTRIAL_LLM_MODEL` is the only knob.
6. **No real photo/thumbnail per agent** — optional warmth, low priority.
7. **The Adrar twin is simulated.** The moment real telemetry exists, point
   `sensors.py` at it and the rest of the stack is unchanged.

---

## If you are resuming in a fresh session

1. Read this file top to bottom (~10 min). It is the whole history.
2. Start both services with the commands above and open
   <http://localhost:3010>. Click through every nav item.
3. The most useful screens to understand the current state: **Agents at work**
   (the design system at full strength) and **Cow food** (the weakest view —
   that's the gap to close).
4. Check the loose ends list above and pick one. Item 1 (delete dead
   `Areas.tsx`) is a two-minute win. Item 2 is the main remaining work.
5. Before you finish, run the three verification commands and commit with a
   message that says *why*, not just *what*.
