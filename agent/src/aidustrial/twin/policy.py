"""Autonomy policy: which actions may run without a human.

Risk scoring answers "how dangerous is this act?". This module answers a
different question: "for *this class* of act, how much risk is acceptable
without a person?" Those are not the same question. A barn light and a transfer
of fossil water are not equivalent decisions even when they score the same, and
collapsing both into one global number makes the "autonomy where it is safe"
claim weaker than it sounds.

Three tiers, hardest first:

  ALWAYS_GATE   never runs without a human, whatever the score. Declared in
                `twin.constants` because they encode the governance contract.
  BOUNDED       runs alone below the action's own ceiling. A per-action ceiling
                may only ever be *stricter* than the global one -- it can never
                be used to widen autonomy past `RISK_AUTO_APPROVE_CEILING`.
  AUTONOMOUS    changes nothing physical, or is undone by the next tick. These
                run at any score, which is safe precisely because they carry no
                physical consequence.

The ordering matters for the safety argument: a model may raise a risk score,
never lower one, and the policy is read-only configuration that no model
touches. Nothing here can be influenced by a proposal.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import constants as C


@dataclass(frozen=True)
class Rule:
    """How one action class is governed."""

    tier: str  # "autonomous" | "bounded" | "always_gate"
    auto_below: float | None
    why: str


#: Acts with no physical consequence. Safe to run at any risk score: the worst
#: outcome of a wrong call is a message somebody reads.
AUTONOMOUS: Rule = Rule("autonomous", None, "no physical change; reversible by definition")

#: Acts that do touch the world but recover within a tick or two. The ceiling is
#: deliberately low -- these are comfort and airflow, not resource allocation.
_BOUNDED_CEILING = 25.0

#: Per-action governance. Anything absent falls back to the global ceiling.
POLICY: dict[str, Rule] = {
    "set_lighting": Rule("autonomous", None, "illumination only; no welfare or resource effect"),
    "notify_technician": Rule("autonomous", None, "opens a work order; changes nothing physical"),
    "set_ventilation": Rule("bounded", _BOUNDED_CEILING, "fans and airflow; recovers within minutes"),
    "enable_misters": Rule("bounded", _BOUNDED_CEILING, "misting draws water; capped well below the gate"),
}


def rule_for(action: str) -> Rule:
    """The rule governing an action, defaulting to the global gate."""
    if action in C.ALWAYS_GATE_ACTIONS:
        return Rule("always_gate", None, "irreversible or resource-committing; never auto")
    found = POLICY.get(action)
    if found is not None:
        return found
    return Rule("bounded", C.RISK_AUTO_APPROVE_CEILING, "default: auto only below the global ceiling")


def ceiling_for(action: str) -> float | None:
    """Risk below which this action may run alone. None means never."""
    r = rule_for(action)
    if r.tier == "always_gate":
        return None
    if r.tier == "autonomous":
        return float("inf")
    # A bounded ceiling can tighten the global one, never loosen it.
    assert r.auto_below is not None
    return min(r.auto_below, C.RISK_AUTO_APPROVE_CEILING)


def requires_human(action: str, risk_score: float) -> tuple[bool, str]:
    """Decide whether an action needs a person, and say why in one phrase."""
    r = rule_for(action)
    if r.tier == "always_gate":
        return True, r.why
    ceiling = ceiling_for(action)
    assert ceiling is not None
    if risk_score >= ceiling:
        return True, f"risk {risk_score:.0f} is at or above this action's ceiling ({ceiling:.0f})"
    if r.tier == "autonomous":
        return False, r.why
    return False, f"risk {risk_score:.0f} is below this action's ceiling ({ceiling:.0f})"


def describe() -> list[dict]:
    """The policy as data, for the UI and the README."""
    rows: list[dict] = []
    for action, r in sorted(POLICY.items()):
        rows.append(
            {
                "action": action,
                "tier": r.tier,
                "auto_below": None if r.auto_below is None else r.auto_below,
                "why": r.why,
            }
        )
    for action in sorted(C.ALWAYS_GATE_ACTIONS):
        rows.append({"action": action, "tier": "always_gate", "auto_below": None,
                     "why": "irreversible or resource-committing; never auto"})
    return rows
