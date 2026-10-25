# Three-minute demo script

**Target:** 3:00 (acceptable range 2:00-4:00). **Upload:** unlisted YouTube or
Google Drive, openable without requesting access. **Format:** 16:9, 1080p,
screen recording with voice-over. No music, no title sequence, no slides before
the product.

The criteria reward a video that opens with the product, explains the problem in
under 30 seconds, and shows real usage. This script follows that order. The
money shot is the **reject/approve contrast** at 1:45, record it carefully.

---

## Before you record

1. **Fix and verify the gate.** `uv run pytest tests/ -q` must pass. In a browser,
   reject one proposal and confirm the world does not change; approve another and
   confirm it does. This is the core claim of the video.
2. Start the backend and dashboard with the README commands. Use a fresh `demo`
   session so the first gate is waiting at Day 3, 12:30.
3. **Warm up the reasoning layer** if you are recording with it on. Open the
   dashboard once, wait for the “deciding via …” and “writing via …” lines to
   show a decided/reasoned count, then reload for the take. If the model is not
   available, record the rules-only version and use the offline line, do not
   fake it. The gate is the product either way.
4. Record at 1920×1080 or 1440×900, browser zoom 110-125%. Close other tabs,
   hide bookmarks, silence notifications. Check the microphone level.
5. Do a 20-second test recording and watch it back. If the screen text is not
   readable at normal size, zoom in and re-record.
6. Have a second take ready. It is fine to cut between a reject take and an
   approve take; the criteria do not require a single unbroken session.

---

## Shot list and narration

### 0:00-0:15, Open on the product

**On screen:** the dashboard, already paused at the first decision. The
“PAUSED” strip and the **SIMULATED** badge are visible.

**Say:**

> “This is Aidustrial. It watches a large dairy farm, and it stops before it does
> anything consequential. Every number on this screen is simulated, the farm is
> a digital twin of a real project in Adrar, Algeria. The decision layer is the
> part that is real.”

Do not open with a logo or a slide. The first frame is the working product.

### 0:15-0:40, The problem, in one sentence

**On screen:** click **What’s happening**. Point at the food, herd and water
cards. Keep the cursor still.

**Say:**

> “A 270,000-head dairy in the Sahara is a coordination problem, not a sensing
> problem. Cooling hardware exists in only half the barns. The aquifer does not
> refill. The herd arrives before its feed does. The hard question is never ‘is
> there a reading?’ It is ‘which trade-off do we make, and who owns it?’”

### 0:40-1:05, What the system is

**On screen:** click **Agents at work**. Let the seven specialist cards and the
signal-flow diagram breathe for a second. If the reasoning lines are live, point
at the decision/prose attribution. If offline, point at the explicit offline
line.

**Say:**

> “Seven specialists watch one domain each, crop, water, herd health, calving,
> milk, machinery, supply. They share findings on a blackboard. They can propose
> actions. They cannot execute them. That is the design: the agents do the
> watching and reasoning; the human keeps the authority.”

### 1:05-1:45, The gate

**On screen:** click **Decisions**. Show the proposal, the plain-language
rationale, “If you approve,” “If you do nothing,” then expand **Show technical
detail and evidence**. Point at the risk score, the urgency score and the
evidence values. Scroll slowly; do not rush.

**Say:**

> “When a proposal crosses the risk ceiling, the whole graph suspends. The
> director sees what the agent wants, why, what breaks if it is wrong, and what
> happens if we do nothing. Risk is a deterministic function of severity,
> headcount, water and reversibility. A model may escalate a finding. It may
> never lower the risk to slip past this gate.”

### 1:45-2:20, The money shot: reject, then approve

**On screen:** click **Reject**. Let the next state load. Open **Decisions** and
show the rejected entry in the audit log. Then go to **Water & machines** (or
the relevant area) and show that the fault is still there: the pivot is still
hot, the misters are still off, the world did not move.

If your first gate is a different action, say what it is and show its unchanged
reading. The principle is the same; do not pretend the screen says something it
does not.

Then take the next decision, or cut to a second take, and click **Approve**.
Show the changed reading or the approved entry in the audit log.

**Say:**

> “Watch what rejection does. The decision is recorded, the agent enters a
> cooldown so it does not nag, and the farm does not move. The pivot is still
> hot. Nothing happened, because I said no.
>
> Now I approve the next one. The action is applied, the reading changes, and the
> audit trail says who approved it. That contrast is the product: autonomy where
> it is safe, a hard gate where it is not.”

If the next decision is not ready, record the approve as a second take and cut.
Do not stage a fake click or narrate a change that did not happen.

### 2:20-2:45, Provenance and honesty

**On screen:** return to **What’s happening**. Point at the **SIMULATED** badge,
then open **How it works** or the provenance panel. If you have the repository
open, show `docs/DATA_PROVENANCE.md` for two seconds, just enough to show that
the assumptions are classified, not hidden.

**Say:**

> “The farm is a simulation, and the system says so above the fold. Every
> constant is either sourced, derived or labelled an assumption. There is no
> relationship with Baladna and no live telemetry. I would rather be argued with
> than believed.”

### 2:45-3:00, Close on the next step

**On screen:** back to the decision gate or the home screen. End card with the
repository and demo URL.

**Say:**

> “I built this solo. In the next three months I want to connect one real site’s
> telemetry and run a two-week shadow-mode pilot with an Algerian operator. The
> goal is not a fully autonomous farm. It is a system an operations director
> trusts enough to use on a real shift.”

---

## Editing notes

- Cut loading, dead air, cursor hunting and repeated clicks. Keep the gate
  explanation and the reject/approve contrast intact.
- Add captions if your accent may be hard for an international panel; do not
  cover the evidence with captions.
- Keep the screen readable: zoom on the decision card, not on the whole desktop.
- No music. No animated intro. No four minutes of context.
- End with a static card: project name, one-line summary, repo URL, live demo
  URL, “Built solo for Thirduni Cohort 1.”
- Watch the export once at 100% volume and once muted, on a phone-sized window.
  If the text is unreadable there, re-record the zoomed sections.

## Upload checklist

- [ ] Length is between 2:00 and 4:00.
- [ ] The first 15 seconds show the working product, not a slide.
- [ ] The problem is explained in under 30 seconds.
- [ ] Reject and approve are both shown, with the world changing only on approve.
- [ ] The word “simulated” is said and the badge is visible.
- [ ] The video is **unlisted**, not private.
- [ ] A logged-out browser can open it without requesting access.
- [ ] The audio is audible on laptop speakers; the screen text is readable.
- [ ] The end card has the repo and demo URLs.
