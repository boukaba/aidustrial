# Aidustrial

### The agentic operations layer for industrial agro-complexes

Aidustrial is built around a **simulated** dairy complex dimensioned from the
**Baladna Algeria** mega-dairy in
Adrar, Algerian Sahara, USD 3.5 billion, 270,000 head of Holstein across
117,000 hectares, targeting roughly half of Algeria's national powdered-milk
demand. Every parameter is either taken from published figures or explicitly
labelled as an assumption; the full register is in
[`DATA_PROVENANCE.md`](DATA_PROVENANCE.md). This is an independent case study:
I have no relationship with Baladna and no access to their telemetry. Baladna is
the target: the aim is to integrate Aidustrial with them, and the tool boundary
is built for exactly that. The site was chosen because its constraints are the
clearest demonstration of the problem this solves.

---

## Project description

**Aidustrial is an agentic operations layer for a large industrial operation, 
and it makes every AI Agent stop and ask a person before anything consequential
happens.**

It is not a dashboard, and it is not a chatbot bolted onto telemetry. It is
seven specialist AI Agents, each owning one domain of the operation, feed, water,
herd health, calving, milking, machinery, supply, reading a **simulated**
digital twin of the site. They read continuously, and when the reasoning backend
is configured they explain what they see in plain language. Every consequential
proposal is held at a gate until a person says yes or no.

The simulated twin behind it is dimensioned from published data: 270,000 head,
51,548 animals modelled at granular state, an irrigation programme drawing from
the Albien fossil aquifer that never refills, misting hardware in 4 of 8 barns,
a fodder programme that needs a full growing season before the herd arrives.

---

## The problem

**A 270,000-cow operation in the Sahara will produce more telemetry than any
human team can watch, and the failures that matter are not sensor failures,
they are coordination failures.**

Consider what is actually running at once. Feed stocks and fodder growth. An
aquifer that does not refill, at 2.5 to 4 billion cubic metres a year at full
build-out. Herd health across 51,000 animals. A milking line where every minute
of delay costs milk for an entire lactation. Six irrigation pivots, blocked
nozzles, bearings running hot. A supply chain bringing animals in by air.

Each of those is somebody's entire job. The moment two of them interact, a
drying field is a feed problem, a herd problem *and* a milk problem, nobody
holds the whole picture.

The obvious answer is AI. But the obvious AI answer is unacceptable here, for
three reasons:

1. **It is opaque.** If a model quietly decides that Barn 6 goes without cooling
   today, you cannot audit that decision, and you cannot reverse it.
2. **It is sycophantic.** A model that is free to set its own risk score is free
   to lower it and slip past any gate you build.
3. **It invents provenance.** A number without a source is a rumour. In an
   operation where water comes from fossil aquifers rather than rainfall, the
   *difference* matters more than the number.

---

## The solution

**Aidustrial gives the operation autonomy where it is safe and a hard human gate
where it is not, and it makes both auditable.**

### Seven specialists, two reasoning tracks

Each agent owns a domain and reads it continuously through a tool layer, not a
static dashboard. They are not threshold alarms. When the reasoning backend is
configured, two models run the work in parallel, on different jobs:

- **One decides.** It asks typed questions, is this warranted, which action from
  a closed vocabulary, how urgent, and answers in **about a second**, with the
  odds it was working from attached to the verdict. ~0.9s measured on the
  development machine.
- **One writes.** It produces the plain-language explanation a manager can read
  aloud and argue with, sourced from the same readings.

Without credentials, both tracks fall back to the deterministic rules. The rules
are the floor, and the human gate works either way.

### The model never sets the risk

This is the core of the design. **Risk is computed by deterministic scoring
written for this system, never by a model.** A model may escalate a finding's
severity or urgency. It may never de-escalate past a rule. A model that could
raise its own risk score could lower it to slip past the gate, so it never gets
the number. The model proposes; the scorer decides.

Every consequential proposal carries a deterministic risk score. Anything above
the ceiling for automatic approval, 40, is *guaranteed* to face a human.

### Nothing consequential happens without a person

Every such action suspends the system and waits. The director sees the evidence,
the blast radius of saying yes, and the cost of doing nothing. Then approves or
rejects. The action vocabulary is closed: an unrecognised action is dropped, not
passed through. A hallucinated `dispatch_helicopter` never reaches an executor.

### Every number is sourced or labelled

Readings carry their provenance, water drawn from a fossil aquifer, not
rainfall, is labelled as non-renewable. The telemetry is simulated, and the
dashboard says so above the fold. I would rather be argued with than believed.

### Built to be pointed at the real thing

The twin is disposable. The tool boundary is the asset. Point Aidustrial at real
site telemetry and nothing else in the stack has to change.

---

## Why Algeria, why now

Adrar is the sharpest version of a national problem: Algeria is investing in
food security on water that does not refill. The operators who will run these
sites are being hired now, before the telemetry exists. Aidustrial is designed
for that window. It makes the water cost visible, forces the trade-off to a
person, and leaves an audit trail. The same pattern applies to any large
irrigated agri-industrial site in North Africa.

## Who it is for

**Operations directors and plant managers running large industrial sites who
want autonomous agents but cannot accept an opaque system making irreversible
calls.**

Specifically:

- **Large agri-industrial operations**, mega-dairies, feedlots, integrated crop
  and livestock complexes, where several specialist domains run at once and the
  coordination cost between them is the real failure mode.
- **Teams that already tried dashboards** and found that a wall of numbers is not
  a decision, and the decision is still a person's whole job.
- **Regulated or high-consequence environments** where an action must be
  attributable, reversible and auditable, cooling sheds, water allocation,
  animal welfare, machinery dispatch.
- **Operators standing up a new site** where telemetry does not exist yet. Aidustrial
  runs on a simulated twin dimensioned from published parameters, so the agents
  and the governance layer are proven before the collars and load cells arrive.

The promise is narrow and deliberate: **the agents do the watching and the
reasoning. The human keeps the authority.** That is not a limitation the design
works around, it is the product.

---

*Aidustrial, seven specialists, one human gate.*

---

© 2026 Mohammed Boukaba. All rights reserved. · [mohammed@pullrun.dev](mailto:mohammed@pullrun.dev)
