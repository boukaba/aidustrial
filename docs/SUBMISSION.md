# Thirduni Cohort 1, submission pack

Copy the answers below into the delivery platform. Items marked `[ADD ...]` are
the only things that need a URL or a full legal name from you.

> **Solo team:** confirmed permitted for this cohort (programme staff, by direct
> message). Team members and roles lists **Mohammed Boukaba** as the sole human
> member, with AI tools disclosed separately.

---

## 1. Project name and one-line summary (max 20 words)

**Project name:** Aidustrial

**One-line summary:** An agentic operations layer for large industrial farms:
seven specialist AI Agents working 24/7, escalating consequential decisions to
humans.

*(19 words.)*

## 2. Project description (max 150 words)

A large industrial farm produces more telemetry than any team can turn into
timely decisions. Feed, water, herd health, milk, machinery and supply run at
once, and a decision in one lands in another: a bearing fails, a pivot stops, a
field dries, the herd loses feed.

Aidustrial puts seven specialist AI Agents on it, each owning one domain and
working around the clock. They read a live digital twin fed by telemetry from
pivots, silos, the parlour, weather stations and laboratories, and share findings
in real time. Most decisions they take alone in under a second. Anything carrying
real risk goes to a human specialist, with the evidence, the blast radius and the
cost of doing nothing. Risk is scored by our rules, never by the model.

It is built around Baladna's dairy project in Adrar, and adapts to any industry
run by specialists.

*(145 words.)*

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

## 5. Demo video (2-4 minutes)

`[ADD UNLISTED YOUTUBE OR GOOGLE DRIVE URL]`

Record from the script in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). Set it to
**unlisted**, not private. Check that a logged-out browser can open it.

## 6. Team members and roles

**Solo submission (team of one).**

- **Mohammed Boukaba**, product concept, domain research, data
  provenance, architecture, backend, frontend, tests, demo.
- **AI tools**, a coding assistant was used for code implementation and test
  scaffolding. All design decisions, domain assumptions and verification are
  mine. The criteria explicitly expect AI tools to be
  disclosed; hiding them costs points.
- **No other team members.**

**Prior-work disclosure (required if applicable):** if any code or design
predates the programme, add one sentence here: “Earlier work used as a starting
point: …”. The product history in this repository begins in October 2026; do
not claim otherwise.

## 7. Tech stack

- **Backend:** Python 3.11+, LangGraph, FastAPI, Uvicorn, Pydantic, HTTPX,
  WebSocket, pytest, ruff, uv
- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS, pnpm
- **AI:** Jev 1.13 via OpenCode Zen (typed decisions), DeepSeek V4.1 Flash via
  OpenCode Go (prose), a coding assistant for implementation
- **Data:** deterministic digital twin seeded from published figures and domain
  literature, plus SQLite (stdlib `sqlite3`) for the decision ledger, work
  orders, chat history and an FTS5 full-text index
- **Retrieval (RAG):** SQLite FTS5 / BM25 over an eight-document domain corpus;
  no vector database, no embedding service, no model download
- **Deployment:** Docker, single image; static Next.js build served by FastAPI
- **Tooling:** Playwright (UI verification), GitHub

## 8. What happens next (max 100 words)

Three months: take Aidustrial off the twin and onto one real barn group, live
telemetry, lab feeds, four weeks in shadow mode with every AI Agent decision
logged beside the human's. Behind it, production hardening: PostgreSQL replacing
SQLite, row-level multi-tenant isolation, structured logging with audit
retention, and Neo4j for the cross-domain knowledge graph, everything a serious
industrial deployment expects. The core is already built; this is the last mile.
Then we would like an introduction to Baladna. The same architecture fits any
specialist industry: energy, manufacturing, logistics.

*(89 words.)*

---

## Optional pitch deck (max 8 slides)

1. **Title**, Aidustrial; one-line summary; solo builder; Thirduni Cohort 1.
2. **Problem**, Adrar: 270,000 head, fossil aquifer, cooling in 4 of 8 barns,
   herd before fodder; coordination is the failure mode.
3. **Insight**, the agents should do the watching and reasoning; the human
   keeps authority. Risk must be deterministic and visible.
4. **Product**, screenshot of the decision gate; approve/reject; evidence,
   blast radius, cost of inaction.
5. **How it works**, seven specialists, blackboard, LangGraph gate, tool
   boundary; models may escalate but never set risk.
6. **What is real / simulated**, published figures vs twin; no Baladna
   relationship; provenance register.
7. **Impact and viability**, Algerian operators, shadow-mode pilot, open tool
   boundary, next three months.
8. **Ask / links**, demo URL, repo, video, contact; what you want from the
   programme.

## Rubric check

| Criterion | What the submission shows | Gap to be honest about |
|---|---|---|
| Problem and insight | A specific site, a specific constraint, a coordination problem | No operator interviews yet; say so and describe the validation plan |
| Working product | The human gate works end to end; reject does not mutate the world | The farm is simulated; the reasoning backend is optional |
| Technical execution | README, architecture, 104 tests, provenance, tool boundary | Known gaps are documented in the README |
| Impact and viability | A narrow user, a pilot plan, a reason to continue | No signed pilot yet; the next step is one operator |
| Story and demo | Three-minute script opens with the product and shows a real decision | Record it, keep it unlisted, check it logged out |

## Before you submit

- [ ] Repository is **public**; README opens without errors.
- [ ] `uv run pytest tests/ -q` passes (104 tests).
- [ ] Dashboard runs from a fresh clone with the two commands in the README.
- [ ] Live URL works in a private window, logged out, on 30 October.
- [ ] Video is **unlisted** (not private), 2-4 minutes, audio audible, screen
      readable.
- [ ] Team members and roles are filled in, including “solo” if that is the
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

---

© 2026 Mohammed Boukaba. All rights reserved. · [mohammed@pullrun.dev](mailto:mohammed@pullrun.dev)
