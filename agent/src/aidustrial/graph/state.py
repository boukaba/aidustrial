"""Layer 3 - Orchestrator state.

The shared blackboard every node reads and writes. Reducers matter: findings and
memory entries ACCUMULATE across the swarm within a tick rather than overwriting,
because several agents can independently notice the same fault and the
orchestrator needs to see that convergence -- one agent noticing a hot bearing is
an anecdote, three noticing it is a pattern.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from ..tools.actions import Action, Decision, Finding


def _merge_findings(a: list, b: list) -> list:
    """Deduplicate. Three agents reporting the same pivot is signal, not noise."""
    seen: dict[str, Finding] = {}
    for f in list(a) + list(b):
        key = f"{f.agent}|{f.summary[:60]}"
        prev = seen.get(key)
        if prev is None or f.confidence > prev.confidence:
            seen[key] = f
    return list(seen.values())


def _append(a: list, b: list) -> list:
    return list(a) + list(b)


class FarmState(TypedDict, total=False):
    # --- clock ---
    tick: int
    sim_time: str
    day: int
    phase: str

    # NOTE: the World is deliberately NOT in this state. It is live process
    # state owned by the session and reached through the sensor gateway, because
    # the checkpointer serialises every channel through msgpack.

    # --- agents ---
    agents_awake: list[str]
    findings: Annotated[list[Finding], _merge_findings]
    proposals: Annotated[list[Action], _append]
    trace: Annotated[list[dict], _append]

    # --- routing ---
    focus: list[str]
    escalation: Literal["none", "watch", "urgent"]
    dispatched: list[str]
    dispatch_reasons: list[str]
    orchestration: dict

    # --- HITL ---
    gate_queue: list[Action]
    pending: Action | None
    decision: Decision | None
    # These accumulate: the queue drains across several human_gate visits in a
    # single turn, so a plain overwrite would silently discard every decision
    # after the first.
    executed: Annotated[list[dict], _append]
    rejected: Annotated[list[dict], _append]
    #: Human verdicts, appended as they happen so the audit trail survives a
    #: resume and shows up in the control panel.
    decision_log: Annotated[list[dict], _append]

    # --- loop control ---
    turn: int
    max_turns: int
    halt_reason: str


def trace_event(agent: str, phase: str, message: str, **extra: Any) -> dict:
    return {"agent": agent, "phase": phase, "message": message, **extra}


__all__ = ["FarmState", "_append", "_merge_findings", "trace_event"]