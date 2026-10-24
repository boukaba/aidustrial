"""Layer 2.5 -- turning a model verdict into something the graph can trust.

`tools/llm.py` gives us a validated `Reasoning`. This module decides what that
verdict is *allowed* to change, and builds the prompt that produced it.

The safety rule, stated once and enforced everywhere below:

  THE MODEL MAY ESCALATE. IT MAY NEVER DE-ESCALATE PAST A RULE.

The threshold rules were written by hand and tested. A flash model agreeing
with them is a bonus; a flash model talking them out of an animal-welfare
action is a liability. So:

  - Narrative (summary / rationale) -> the model's wins. It is strictly better
    at plain language than an f-string, and that is the whole point.
  - Urgency -> the model may RAISE it. It may not lower it below the rule's.
  - Risk -> never touched. `score_risk` decides, always, because risk is what
    routes a proposal to the human gate.
  - An action the model invents that the rules did not find -> accepted only if
    it is in the known vocabulary, and always scored at or above the human
    gate ceiling. We cannot verify its evidence, so it must face a person.
  - A rule-mandated action the model omits -> kept anyway. Omission is the one
    failure mode we refuse to inherit.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ..tools import sensors
from ..tools.actions import Action, Finding, score_risk, score_urgency
from ..tools.jev import (
    JEVS,
    NO_ACTION,
    SEVERITY_RUBRIC,
    URGENCY_RUBRIC,
    Decision,
)
from ..tools.llm import BRAIN, Reasoning, hash_state
from ..twin import constants as C
from .mesh import digest

#: Which sensor tools each agent is allowed to see. Mirrors what the agents
#: already call in their own `survey()` -- we do not widen any agent's view.
READERS: dict[str, tuple[str, ...]] = {
    "agronomist": ("get_water_budget", "get_pivot_telemetry"),
    "veterinarian": ("get_herd_vitals", "get_environment_telemetry"),
    "maintenance": ("get_degraded_assets", "get_feed_inventory"),
    "logistics": ("get_feed_inventory", "get_airlift_schedule", "get_fleet_positions"),
    "crop": ("crops", "get_water_budget"),
    "calving": ("youngstock",),
    "milking": ("milk",),
}

#: Per-tool byte budget. One flat cap meant a single large payload (herd vitals
#: with 8 groups) blew the whole budget and the agent received the string
#: "readings truncated" instead of its readings -- so it reasoned about nothing.
#: Cap each tool independently so one big read cannot starve the others.
MAX_BYTES_PER_TOOL = 1800

#: Total prompt ceiling after per-tool trimming.
MAX_TOTAL_BYTES = 6000

#: Which actions each agent owns. Mirrors IMPLICATION_ROUTES but is defined
#: here to avoid an import cycle (orchestrator imports this module). Showing an
#: agent only its own verbs measurably cut hallucinated actions.
OWNED: dict[str, tuple[str, ...]] = {
    "agronomist": ("start_pivot", "shed_pivot"),
    "maintenance": ("repair_pivot", "restart_inlet", "notify_technician"),
    "logistics": ("reroute_convoy",),
    "veterinarian": ("enable_misters", "shed_load", "set_ventilation", "set_lighting"),
    "crop": ("harvest_field", "start_pivot"),
    "calving": ("boost_heifer_rations", "isolate_calves"),
    "milking": ("service_parlour", "clean_condenser", "cull_chronic_mastitis", "halt_intake"),
}

#: Human-readable criteria for the Jev `choice` question. A bare verb string
#: makes a small model guess at intent; a sentence describing the consequence
#: does not. Unknown verbs fall back to their raw name rather than being
#: dropped -- the choice set must stay closed and complete.
ACTION_LABELS: dict[str, str] = {
    "start_pivot": "Start irrigating with the centre pivot",
    "shed_pivot": "Shut a pivot down to protect it or the field",
    "repair_pivot": "Send maintenance to repair a broken pivot",
    "restart_inlet": "Restart a tripped water inlet valve",
    "reroute_convoy": "Reroute the feed convoy to a different silo",
    "enable_misters": "Turn on barn misters / cooling for the herd",
    "shed_load": "Shed electrical load to protect the milking parlour",
    "harvest_field": "Harvest the field now",
    "boost_heifer_rations": "Increase heifer and calf feed rations",
    "isolate_calves": "Separate sick or at-risk calves from the group",
    "service_parlour": "Service the milking parlour",
    "clean_condenser": "Clean the milk condenser / chiller",
    "cull_chronic_mastitis": "Cull cows with chronic mastitis",
    "halt_intake": "Halt milk intake and hold the tanker",
    # Autonomous by policy: reversible, or no physical change at all.
    "set_lighting": "Set barn lighting for the current period",
    "set_ventilation": "Raise or lower barn ventilation fans",
    "notify_technician": "Open a work order and send a technician to the site",
}

#: Ceiling on the compact state text handed to Jev. ~400 input tokens measured
#: at roughly 1,500 characters, so this keeps a decision call in the same
#: weight class whether or not the agent's sensors are busy.
MAX_JEV_STATE_BYTES = 2400


def _trim(value: Any, budget: int) -> Any:
    """Shrink a JSON-ish value to fit a byte budget, keeping structure.

    Lists are the usual offender (8 herd groups, 6 pivots). Keep the head and
    the tail and say how many were dropped, rather than discarding the whole
    read.
    """
    blob = json.dumps(value, default=str)
    if len(blob) <= budget:
        return value
    if isinstance(value, list) and value:
        keep = max(2, min(len(value), budget // 120))
        head = value[:keep]
        tail = value[-1:] if len(value) > keep else []
        dropped = len(value) - len(head) - len(tail)
        return {
            "_truncated": f"{dropped} of {len(value)} entries omitted to fit the prompt",
            "sample": head + tail,
        }
    if isinstance(value, dict):
        out = {}
        share = max(200, budget // max(1, len(value)))
        for k, v in value.items():
            out[k] = _trim(v, share)
        return out
    return str(value)[:budget]


def build_context(agent: str, board: Any, system_prompt: str) -> dict:
    """Assemble the prompt payload for one agent's reasoning call.

    Returns the system/user strings plus `readings`, a stable view of the
    sensor data used for call-dedup. The clock is deliberately kept OUT of
    `readings`: hashing it meant every tick looked like new information and the
    cache never hit, so the free tier was hammered once per tick per agent.
    """
    tools: list[dict] = []
    per_tool = max(400, MAX_BYTES_PER_TOOL // max(1, len(READERS.get(agent, ()))))
    for name in READERS.get(agent, ()):
        fn: Callable[..., Any] | None = getattr(sensors, name, None)
        if fn is None:
            continue
        try:
            tools.append({"tool": name, "data": _trim(fn(), per_tool)})
        except Exception as exc:  # noqa: BLE001 -- never let a read kill the tick
            tools.append({"tool": name, "error": str(exc)[:120]})

    blob = json.dumps(tools, default=str)
    if len(blob) > MAX_TOTAL_BYTES:
        tools = _trim(tools, MAX_TOTAL_BYTES)

    snapshot = sensors.current().packet() if sensors.GW else {}
    board_view = digest(board) if board is not None else "(no board)"
    mine = OWNED.get(agent, tuple(sorted(BRAIN.allowed)))

    system = (
        "You are one specialist agent inside an agentic operations system for a "
        "33,250-head dairy complex in Adrar, Algerian Sahara.\n\n"
        "You will be given your mandate, your live sensor readings, and what the "
        "other agents have said on the shared blackboard.\n\n"
        "Respond with ONLY a single JSON object. No prose, no markdown fences.\n"
        "Schema:\n"
        "{\n"
        '  "summary": "<one plain-language sentence: what you see and what it means>",\n'
        '  "rationale": "<2-3 sentences: which readings drove your conclusion>",\n'
        '  "severity": "info" | "low" | "medium" | "high" | "critical",\n'
        '  "confidence": <0.0-1.0>,\n'
        '  "action": "<one of YOUR actions below, or empty string>",\n'
        '  "target": "<equipment/group id, or empty>",\n'
        '  "urgency": <0-100, how soon this must happen>,\n'
        '  "reversible": <true|false>\n'
        "}\n\n"
        "Rules:\n"
        f"- YOUR actions (you may propose only these): {', '.join(mine) or '(none)'}. \n"
        "- If no action is warranted, set action to an empty string. Do not invent actions.\n"
        "- The risk score is computed by the system, not by you. Do not output it.\n"
        "- Numbers in your summary must come from the readings you were given.\n"
        "- If a reading is marked _truncated, reason from the sample you can see.\n"
        "- This is a SIMULATION. Never claim the telemetry is real-world data.\n"
    )

    user = (
        f"YOUR MANDATE:\n{system_prompt.strip()}\n\n"
        f"YOUR SENSOR READINGS:\n{json.dumps(tools, indent=1, default=str)}\n\n"
        f"WHAT OTHER AGENTS SAID (blackboard):\n{board_view}\n\n"
        f"CURRENT SITE CLOCK: {snapshot.get('time', '?')} "
        f"(day {snapshot.get('day', '?')}, {snapshot.get('phase', '?')})\n\n"
        "Produce your verdict as one JSON object."
    )

    # `readings` deliberately excludes the clock AND the blackboard. Hashing
    # either meant every tick looked like new information -- the clock advances
    # 30 simulated minutes per tick and the board is cleared in
    # `wake_specialists` -- so the cache never hit and the free tier was hit
    # once per tick per agent for unchanged sensor data. Only the sensor
    # readings belong in the dedup key.
    readings = json.dumps(tools, sort_keys=True, default=str)

    return {"system": system, "user": user, "agent": agent, "readings": readings}


def request_reasoning(agent: str, board: Any, system_prompt: str) -> str:
    """Fire a non-blocking reasoning request. Returns the state hash.

    Safe to call from the graph thread: it only stashes work for the event
    loop to pick up. Returns "" if the brain is disabled.
    """
    if not BRAIN.enabled:
        return ""
    try:
        payload = build_context(agent, board, system_prompt)
    except Exception:  # noqa: BLE001
        return ""
    h = hash_state({"a": agent, "r": payload["readings"]})
    BRAIN.request(agent, payload, h)
    return h


# --------------------------------------------------------------------------
# The decision track (Jev / SystemOne)
# --------------------------------------------------------------------------


def build_jev_state(agent: str, board: Any) -> str:
    """A compact, plain text view of one agent's slice, for a decision model.

    Reuses the same `READERS` and `_trim` budgets as the prose track so the two
    tracks never disagree about what an agent can see. The clock and the
    blackboard are excluded for the same reason they are excluded from the
    prose hash: neither belongs in a call-dedup key, and the clock would make
    the model reason about the time instead of the readings.
    """
    parts: list[str] = []
    per_tool = max(300, MAX_JEV_STATE_BYTES // max(1, len(READERS.get(agent, ()))))
    for name in READERS.get(agent, ()):
        fn: Callable[..., Any] | None = getattr(sensors, name, None)
        if fn is None:
            continue
        try:
            parts.append(f"{name}: {json.dumps(_trim(fn(), per_tool), default=str)}")
        except Exception as exc:  # noqa: BLE001 -- a failed read must not kill the tick
            parts.append(f"{name}: unavailable ({str(exc)[:80]})")
    state = " | ".join(parts)
    if len(state) > MAX_JEV_STATE_BYTES:
        state = state[:MAX_JEV_STATE_BYTES] + " [state truncated]"
    if board is not None:
        try:
            board_view = digest(board)
        except Exception:  # noqa: BLE001
            board_view = ""
        if board_view and board_view != "(no board)":
            state += f" | peers_say: {board_view[:400]}"
    return state


def build_jev_questions(agent: str) -> dict:
    """The four typed questions Jev answers, per agent.

    The `choice` criteria are the agent's OWNED actions plus an explicit
    `no_action`. Because Jev can only return a key from this dict, an agent
    physically cannot be handed an action it does not own -- which is a
    stronger guarantee than filtering a free-form string after the fact.
    """
    owned = OWNED.get(agent, ())
    criteria = {name: ACTION_LABELS.get(name, name.replace("_", " ")) for name in owned}
    criteria[NO_ACTION] = "Continue monitoring; nothing needs to happen yet"
    return {
        "warranted": {
            "type": "noul",
            "instructions": (
                "Given these readings, does anything require action in the next "
                "15 minutes? Note this is a SIMULATION of a dairy complex in Adrar, Algeria."
            ),
        },
        "action": {
            "type": "choice",
            "instructions": "Which single action, if any, is warranted right now?",
            "criteria": criteria,
        },
        "urgency": {
            "type": "score",
            "instructions": "How soon must this happen?",
            "criteria": list(URGENCY_RUBRIC),
        },
        "severity": {
            "type": "score",
            "instructions": "How severe is the situation if nothing is done?",
            "criteria": list(SEVERITY_RUBRIC),
        },
    }


def build_jev_payload(agent: str, board: Any) -> dict:
    """Full SystemOne request body for one agent."""
    return {
        "model": JEVS.model,
        "state": build_jev_state(agent, board),
        "questions": build_jev_questions(agent),
    }


def request_jev(agent: str, board: Any) -> str:
    """Fire a non-blocking decision request. Returns the state hash, or "".

    Thread-safe and non-blocking for the same reason as `request_reasoning`:
    the graph runs in a worker thread, and only the server's event loop is
    allowed to touch the network.
    """
    if not JEVS.enabled:
        return ""
    try:
        payload = build_jev_payload(agent, board)
    except Exception:  # noqa: BLE001
        return ""
    h = hash_state({"a": agent, "r": payload["state"]})
    JEVS.request(agent, payload, h)
    return h


def apply_jev(
    agent: str,
    findings: list[Finding],
    actions: list[Action],
) -> tuple[list[Finding], list[Action]]:
    """Merge Jev's decision into the rule output, under the same safety rules.

    The prose track (`apply_reasoning`) and this one both obey one invariant:

        THE MODEL MAY ESCALATE. IT MAY NEVER DE-ESCALATE PAST A RULE.

    Plus one that matters more here, because Jev is the track that decides
    *what to do* rather than *what to say*: an action Jev proposes always
    carries a risk score above the human-gate ceiling. We have no sensor figure
    to feed `score_risk` for a model-originated call, so it must face a person.
    """
    d: Decision | None = JEVS.get(agent)
    if d is None or not d.valid:
        return findings, actions

    # --- severity: may only escalate -----------------------------------
    if findings:
        findings[0].evidence["jev"] = {
            "warranted": d.warranted,
            "action": d.action,
            "probability": round(d.action_p, 2),
            "ms": round(d.ms, 1),
            "model": d.model,
        }
        if _sev_rank(d.severity) > _sev_rank(findings[0].severity):
            findings[0].severity = d.severity
            findings[0].evidence["severity_from_jev"] = True
    elif d.warranted:
        # A finding the rules did not raise. Worth surfacing: an early, quiet
        # warning is exactly what a decision model is for.
        findings.append(
            Finding(
                agent=agent,
                summary=f"{agent} flags a developing condition requiring attention.",
                severity=d.severity,
                confidence=round(d.confidence, 2),
                evidence={
                    "origin": "jev",
                    "reasoned_by": d.model,
                    "jev_ms": round(d.ms, 1),
                    "warranted_probability": d.warranted,
                },
                implies=d.action,
            )
        )

    # --- urgency: may rise, never fall ---------------------------------
    for a in actions:
        a.evidence.setdefault("jev_model", d.model)
        if d.urgency > a.urgency_score:
            a.urgency_score = round(d.urgency, 1)
            a.evidence["urgency_from_jev"] = True

    # --- an action the rules did not find, with real confidence --------
    if d.actionable and not any(a.action == d.action for a in actions):
        actions.append(_jev_action(agent, d))

    return findings, actions


def _jev_action(agent: str, d: Decision) -> Action:
    """An Action from a decision we did not independently verify.

    Same risk floor as the prose track's model actions, and for the same
    reason: no evidence we can score, therefore no auto-approval.
    """
    risk = max(
        score_risk(severity=d.severity, reversible=True),
        C.RISK_AUTO_APPROVE_CEILING + 15.0,
    )
    urgency = max(d.urgency, score_urgency(hours_to_irreversible_harm=24.0))
    label = ACTION_LABELS.get(d.action, d.action.replace("_", " "))
    return Action(
        action=d.action,
        target="",
        rationale=f"{label} (proposed by {d.model} at {d.action_p:.0%} confidence).",
        requested_by=agent,
        risk_score=round(min(risk, 100.0), 1),
        urgency_score=round(min(urgency, 100.0), 1),
        severity=d.severity,
        evidence={
            "origin": "jev",
            "reasoned_by": d.model,
            "action_probability": round(d.action_p, 2),
            "confidence": round(d.confidence, 2),
        },
        reversible=True,
    )


def apply_reasoning(
    agent: str,
    findings: list[Finding],
    actions: list[Action],
) -> tuple[list[Finding], list[Action]]:
    """Merge the model's verdict into the rule output, under the safety rules.

    Called after `survey()` returns. Mutates in place and returns the same
    lists so existing call sites keep working.
    """
    r: Reasoning | None = BRAIN.get(agent)
    if r is None or not r.valid:
        return findings, actions

    # --- narrative: the model's plain language wins -------------------
    if findings:
        findings[0].summary = r.summary or findings[0].summary
        findings[0].evidence["reasoning_rationale"] = r.rationale
        findings[0].evidence["reasoned_by"] = r.model
        findings[0].evidence["reasoning_ms"] = round(r.ms, 1)
        findings[0].evidence["reasoning_at_tick"] = r.at_tick
        if r.confidence > findings[0].confidence:
            findings[0].confidence = round(r.confidence, 2)
        # Severity may only escalate.
        if _sev_rank(r.severity) > _sev_rank(findings[0].severity):
            findings[0].severity = r.severity
    elif r.summary:
        findings.append(
            Finding(
                agent=agent,
                summary=r.summary,
                severity=r.severity,
                confidence=r.confidence,
                evidence={
                    "reasoning_rationale": r.rationale,
                    "reasoned_by": r.model,
                    "reasoning_ms": round(r.ms, 1),
                },
                implies=r.action,
            )
        )

    # --- urgency: may rise, never fall --------------------------------
    for a in actions:
        a.evidence["reasoned_by"] = r.model
        if r.rationale:
            a.rationale = r.rationale
        if r.urgency > a.urgency_score:
            a.urgency_score = round(r.urgency, 1)
            a.evidence["urgency_from_model"] = True

    # --- an action the rules did not find -----------------------------
    if r.action and not any(a.action == r.action for a in actions):
        actions.append(_model_action(agent, r))

    return findings, actions


def _model_action(agent: str, r: Reasoning) -> Action:
    """Build an Action from a model verdict we cannot independently verify.

    Because we have no headcount or water figure to feed `score_risk`, we
    refuse to let this auto-approve: the risk floor sits above the human-gate
    ceiling, so every model-originated action faces a person.
    """
    risk = max(
        score_risk(severity=r.severity, reversible=r.reversible),
        C.RISK_AUTO_APPROVE_CEILING + 15.0,
    )
    urgency = max(r.urgency, score_urgency(hours_to_irreversible_harm=24.0))
    return Action(
        action=r.action,
        target=r.target,
        rationale=r.rationale or r.summary,
        requested_by=agent,
        risk_score=round(min(risk, 100.0), 1),
        urgency_score=round(min(urgency, 100.0), 1),
        severity=r.severity,
        evidence={
            "origin": "model",
            "reasoned_by": r.model,
            "reasoning_rationale": r.rationale,
            "confidence": r.confidence,
        },
        reversible=r.reversible,
    )


_SEV_ORDER = {s: i for i, s in enumerate(("info", "low", "medium", "high", "critical"))}


def _sev_rank(s: str) -> int:
    return _SEV_ORDER.get(s, 0)


__all__ = [
    "ACTION_LABELS",
    "OWNED",
    "READERS",
    "apply_jev",
    "apply_reasoning",
    "build_context",
    "build_jev_payload",
    "build_jev_questions",
    "build_jev_state",
    "request_jev",
    "request_reasoning",
]
