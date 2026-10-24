# Thirduni Cohort 1 — submission pack

Copy the answers below into the delivery platform. Items marked `[ADD ...]` are
the only things that need a URL or a full legal name from you.

> **Solo team:** the published criteria describe a team project. This pack assumes
> a **team of one**. Confirm in the group chat that a solo team is eligible, and
> list yourself under team members and roles. Do not leave that field blank.

---

## 1. Project name and one-line summary (max 20 words)

**Aidustrial** — An agentic operations layer for large farms: seven specialists
reason, one human decides.

## 2. Project description (max 150 words)

Aidustrial is an agentic operations layer for large industrial farms. Seven
specialist agents read a simulated digital twin of a dairy complex in Adrar,
Algeria, and propose actions on feed, water, herd health, calving, milking,
machinery and logistics. The problem is coordination, not sensing: a
270,000-head operation on a non-renewable aquifer produces more signals than any
team can watch, and the hard decisions are trade-offs between domains.
Aidustrial makes the agents do the watching and reasoning, but never gives them
authority. Every consequential proposal carries a deterministic risk score and
stops at a human gate showing the evidence, blast radius and cost of inaction.
The farm is simulated from published Baladna Algeria figures; this project is
independent and has no access to live telemetry. Built solo for Thirduni
Cohort 1.

*(131 words.)*

If the app is **not hosted** by the deadline, add this sentence and let the video
carry the demo: “The app is a two-process system and is not hosted; the demo
video shows the full workflow end to end.”

## 3. Live demo link

`[ADD PUBLIC URL]`

The app ships as one container; see [`DEPLOY.md`](DEPLOY.md). A judge must be
able to open it without installing anything. Test it in a private browser window,
logged out, on 30 October.

If you cannot deploy, say so in the description (above) and make sure the video
is excellent. Do not submit a dead link.

## 4. Code repository

`[ADD PUBLIC GITHUB URL]`

The repository is public and the README covers:

- what the project is and what is simulated
- how to run it locally (two commands, no keys required)
- who built which part (solo, with AI tools disclosed)
- tests, architecture, data provenance and known gaps

## 5. Demo video (2–4 minutes)

`[ADD UNLISTED YOUTUBE OR GOOGLE DRIVE URL]`

Record from the script in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). Set it to
**unlisted**, not private. Check that a logged-out browser can open it.

## 6. Team members and roles

**Solo submission (team of one).**

- **Yacine `[ADD FAMILY NAME]`** — product concept, domain research, data
  provenance, architecture, backend, frontend, tests, demo.
- **AI tools** — OpenCode / DeepSeek were used heavily for implementation, test
  scaffolding and documentation drafts. All design decisions, domain assumptions
  and verification are mine. The criteria explicitly expect AI tools to be
  disclosed; hiding them costs points.
- **No other team members.**

**Prior-work disclosure (required if applicable):** if any code or design
predates the programme, add one sentence here: “Earlier work used as a starting
point: …”. The product history in this repository begins in October 2026; do
not claim otherwise.

## 7. Tech stack

- **Backend:** Python 3.11+, LangGraph, FastAPI, WebSocket, Pydantic, pytest,
  ruff, uv
- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS, pnpm
- **AI:** OpenCode Zen / Jev (typed decisions), OpenCode Go / DeepSeek V4.1 Flash
  (prose), OpenCode coding agents (implementation assistance)
- **Data:** deterministic digital twin seeded from published figures and domain
  literature; no database required
- **Deployment:** single Docker image; static Next.js build served by FastAPI

## 8. What happens next (max 100 words)

In the next three months I would replace the simulated sensor gateway with one
real site’s telemetry — pivot, collar, silo and tanker feeds — and run a
two-week shadow-mode pilot with an Algerian operator. I would publish the
risk-scoring and provenance method so decisions can be audited, add a
French/Arabic operator view, and keep the tool boundary open for other
integrators. The goal is not a fully autonomous farm. It is a system an
operations director trusts enough to use on a real shift.

*(84 words.)*

---

## Optional pitch deck (max 8 slides)

1. **Title** — Aidustrial; one-line summary; solo builder; Thirduni Cohort 1.
2. **Problem** — Adrar: 270,000 head, fossil aquifer, cooling in 4 of 8 barns,
   herd before fodder; coordination is the failure mode.
3. **Insight** — the agents should do the watching and reasoning; the human
   keeps authority. Risk must be deterministic and visible.
4. **Product** — screenshot of the decision gate; approve/reject; evidence,
   blast radius, cost of inaction.
5. **How it works** — seven specialists, blackboard, LangGraph gate, tool
   boundary; models may escalate but never set risk.
6. **What is real / simulated** — published figures vs twin; no Baladna
   relationship; provenance register.
7. **Impact and viability** — Algerian operators, shadow-mode pilot, open tool
   boundary, next three months.
8. **Ask / links** — demo URL, repo, video, contact; what you want from the
   programme.

## Rubric check

| Criterion | What the submission shows | Gap to be honest about |
|---|---|---|
| Problem and insight | A specific site, a specific constraint, a coordination problem | No operator interviews yet; say so and describe the validation plan |
| Working product | The human gate works end to end; reject does not mutate the world | The farm is simulated; the reasoning backend is optional |
| Technical execution | README, architecture, 88 tests, provenance, tool boundary | Known gaps are documented in the README |
| Impact and viability | A narrow user, a pilot plan, a reason to continue | No signed pilot yet; the next step is one operator |
| Story and demo | Three-minute script opens with the product and shows a real decision | Record it, keep it unlisted, check it logged out |

## Before you submit

- [ ] Repository is **public**; README opens without errors.
- [ ] `uv run pytest tests/ -q` passes (88 tests).
- [ ] Dashboard runs from a fresh clone with the two commands in the README.
- [ ] Live URL works in a private window, logged out, on 30 October.
- [ ] Video is **unlisted** (not private), 2–4 minutes, audio audible, screen
      readable.
- [ ] Team members and roles are filled in — including “solo” if that is the
      case.
- [ ] Tech stack lists the AI tools you actually used.
- [ ] What happens next is under 100 words.
- [ ] Description is under 150 words and says what the product does, not only
      how it is built.
- [ ] If any code or design predates the programme, disclose it in the
      description. The product history in this repository begins in October
      2026; do not claim otherwise.
- [ ] Submit before **31 October, 23:59 Algiers time**. Do not leave the upload
      to the final evening.
