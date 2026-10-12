# aidustrial — pitch

**One line:** An agentic operations layer for industrial agro-complexes.
Built around the published parameters of the Baladna Algeria mega-dairy in Adrar.

> **Relationship:** we have none. Not a partner, not engaged, no contact with
> Baladna. The project was entirely imagined around that site's real, public
> data and numbers, because its constraints are the clearest demonstration of
> the problem. The architecture is built to be integrated there in full if a
> partnership ever becomes real — the tool boundary is the seam.

---

## The problem

The Baladna Algeria project is the largest integrated dairy development anywhere:
USD 3.5 billion, 270,000 head of Holstein across 117,000 hectares of Algerian
Sahara, target of ~50% of Algeria's national powdered-milk demand.

It is also, right now, a construction site with an impossible operating problem
sitting on top of it.

**270,000 cows in a desert.** Air temperature reaches 43 °C. The herd depends on
irrigation that draws from the **Albien, a non-renewable fossil aquifer**, at a
volume the published analysis puts between 2.5 and 4 billion m³ a year at full
build-out. Phase 1 has misting hardware in only **4 of 8 barns** — so when heat
arrives, nobody can cool everybody, and someone has to decide who goes without.

Meanwhile the first 30,000 cows arrive **by air** from nine US states starting
November 2026, to be fed by a fodder programme that needs a full growing season.
The herd lands before its feed does.

This is not a problem that scales linearly with headcount. It is a coordination
problem, and coordination problems are exactly what agentic systems are for.

## Why the existing answer does not work

Operations software assumes telemetry exists. In Adrar it does not — no collars,
no parlour data, no silo load cells, no pivot telemetry. And by the time it does,
270,000 animals across three hubs on a contested aquifer will not fit on one
operator's screen.

Three things follow, and they are the product:

1. **The highest-value deployment window is before the first animal arrives.**
   Civil works are done, 186 drilling permits are issued, and there is no herd
   operations to disturb. In that window agents do not just react — they plan
   water allocation, feed inventory and capacity.
2. **The scarce resource must be allocated by a human.** When cooling exists for
   four barns and demand is eight, that is a judgement about animal welfare and
   commercial exposure. An agent can rank barns by projected harm and show its
   reasoning; it should not make the call silently.
3. **Everything consequential must be explainable.** A director who cannot see
   *why* will start clicking Approve without reading, and the entire
   human-in-the-loop premise collapses.

## What we built

Four layers, and the seams between them are the point.

**Layer 1 — Sensory Cortex.** A tool boundary. Agents never touch the simulation
internals; they call telemetry, veterinary, asset and logistics tools. This is
the only module that changes when the twin is replaced by real Valmont pivot
telemetry, smart collars, parlour yield systems, silo load cells and well meters.

**Layer 2 — The swarm.** An agronomist who judges irrigation against projected
*annual* aquifer draw rather than today's soil moisture. A veterinarian who acts
on rumination, because rumination collapses hours before core temperature does.
A maintenance agent that reads vibration as an early warning. A logistics agent
that owns the airlift-versus-fodder gap. Narrow mandates, explicit escalation
rules, bounded memory.

**Layer 3 — The orchestrator.** A LangGraph state machine that routes between
them and owns the gate. It does no work itself. A veterinary finding does not
move irrigation by itself — the agronomist has to say whether water can be
reallocated. That cross-consult is what makes the swarm a swarm rather than four
dashboards.

**Layer 4 — The Command Center.** When the swarm wants something consequential
the graph **suspends** — LangGraph's `interrupt()`, a real checkpoint, not a
polling loop — and the Farm Director gets the rationale, the blast radius, the
cost of inaction, the itemised risk factors, the evidence values, and risk and
urgency as separate scored axes. Approve or reject, with a note. Both recorded.

## The demo, in five minutes

The session opens at **Day 3, midday**. A pump has cavitated at well-field 2 and
PIVOT-3 is running with 14 blocked nozzles and climbing bearing temperature.

| Beat | What happens |
|---|---|
| Day 3 | The agronomist wakes on six fields at wilting point. Six identical prompts would be absurd, so they are batched into **one** decision. |
| Day 4 | A heatwave lands. Effective heat load crosses into the moderate band. The veterinarian wakes, ranks all eight barns by rumination deficit, and finds only four have misting hardware. |
| Day 4 | The gate asks the director to allocate cooling to the two worst-hit barns *that can be cooled* — and separately flags the three worst barns that cannot, with a load-shedding option. |
| Every tick | The maintenance agent reads PIVOT-1's vibration as an early failure signature, hours before its bearing temperature would justify an alarm. |

The point of the demo is not the alerts. It is that **the alerts are arguable** —
you can see the evidence, the reasoning and the tradeoff, and disagree.

## Two things we had to be honest about

**The data is simulated, and we say so on the dashboard footer.** The Adrar site
has no herd and no telemetry. Every parameter is classified as sourced, derived,
industry-standard, assumption or modelled, with the source named. The
assumption most worth arguing with — the exposure-weighted radiant-load term —
is called out explicitly.

**We removed a claim that would not survive scrutiny.** The intuitive story is
"cooling water competes with irrigation for the aquifer." The arithmetic does not
support it: four misting banks draw 53 m³/h against 27,143 m³/h for six pivots.
The real constraint on cooling is hardware, not water. Correcting this turned a
switch into an allocation — a harder problem, and a far better one.

## Where it goes

aidustrial is not a dairy product. The pattern — contested resource, scarce
hardware, specialist agents, human owns the irreversible call — generalises to
any large industrial agro-complex: irrigation districts, grain handling, cold
chain, mining water, chemical processing.

The twin is disposable. The tool boundary, the specialist/arbitrator split, and
the gate policy are the asset.

---

## Proof

```bash
cd agent && uv run pytest tests/ -q     # 23 passing
```

The suite guards the properties that make this defensible rather than
decorative:

- the diurnal curve is a real 24-hour cycle, not a partial-span artifact
- dry-arid heat is genuinely **less** lethal than humid heat, and radiant load is
  what makes Adrar hard anyway
- misting is scarce hardware, not scarce water
- agents never re-propose an action already satisfied
- risk and urgency remain independent axes
- the graph halts rather than auto-approving
- rejections are recorded and change nothing