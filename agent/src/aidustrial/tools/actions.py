"""Action model shared by Layer 2 (who proposes) and Layer 3 (who gates).

Risk scoring is explicit and inspectable because the whole credibility argument
for human-in-the-loop rests on being able to say WHY an action was gated. If the
score were opaque, the HITL step would be theatre.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Literal

from ..twin import constants as C
from ..twin import policy

Severity = Literal["info", "low", "medium", "high", "critical"]


@dataclass
class Action:
    """A concrete, executable change to the facility."""

    action: str
    target: str = ""
    rationale: str = ""
    requested_by: str = ""
    #: 0-100. >= RISK_AUTO_APPROVE_CEILING requires a human.
    risk_score: float = 50.0
    #: 0-100. How SOON this must happen. Independent of risk: a routine
    #: irrigation restart can be riskier than an urgent, well-scoped action.
    urgency_score: float = 50.0
    severity: Severity = "medium"
    #: The evidence that produced this. Agents must show their work.
    evidence: dict = field(default_factory=dict)
    #: What breaks if this is wrong.
    blast_radius: str = ""
    #: What the agent believes happens if we do nothing.
    cost_of_inaction: str = ""
    reversible: bool = True
    action_id: str = ""

    def __post_init__(self) -> None:
        # Normalise target order so that the same SET of barns always produces
        # the same key. Without this, a proposal for {B05,B06,B07} and one for
        # {B07,B05,B06} are different strings, so dedup and the cooldown both
        # miss them and the audit log fills with permutations of one decision.
        if self.target is not None and not isinstance(self.target, str):
            self.target = str(self.target)
        if self.target and "," in self.target:
            self.target = ",".join(sorted(t.strip() for t in self.target.split(",") if t.strip()))
        if not self.action_id:
            stamp = f"{self.action}|{self.target}|{self.requested_by}|{time.time_ns()}"
            self.action_id = hashlib.sha1(stamp.encode()).hexdigest()[:12]

    def risk_factors(self) -> list[str]:
        """Human-readable reasons this scored what it scored. Shown in the UI."""
        f: list[str] = []
        tier = policy.rule_for(self.action).tier
        if tier == "always_gate":
            f.append(f"policy: '{self.action}' is always gated -- no score makes it safe")
        elif tier == "autonomous":
            f.append(f"policy: '{self.action}' runs without a human ({policy.rule_for(self.action).why})")
        else:
            ceiling = policy.ceiling_for(self.action)
            f.append(f"policy: auto below a risk score of {ceiling:.0f}")
        if not self.reversible:
            f.append("irreversible -- cannot be undone by the system")
        if self.severity == "critical":
            f.append("severity: critical")
        elif self.severity == "high":
            f.append("severity: high")
        if self.evidence.get("water_m3h", 0) > 100:
            f.append(
                f"water: moves {self.evidence['water_m3h']:.0f} m3/h of a "
                "non-renewable aquifer"
            )
        if self.evidence.get("headcount_affected", 0) > 5000:
            f.append(
                f"herd: affects {self.evidence['headcount_affected']:,} head"
            )
        if self.risk_score >= C.RISK_GATE_CRITICAL:
            f.append("score in the critical band")
        return f or ["no elevated factors -- routine"]

    def requires_human(self) -> bool:
        """Whether this action must stop for a person, per the autonomy policy."""
        return policy.requires_human(self.action, self.risk_score)[0]

    def gate_reason(self) -> str:
        """One phrase explaining the governance call, for the audit log."""
        return policy.requires_human(self.action, self.risk_score)[1]

    def urgency_band(self) -> str:
        if self.urgency_score >= 80:
            return "immediate"
        if self.urgency_score >= 55:
            return "soon"
        return "whenever"

    def gate_band(self) -> str:
        if self.risk_score >= C.RISK_GATE_CRITICAL:
            return "critical"
        if self.risk_score >= C.RISK_GATE_ELEVATED:
            return "elevated"
        if self.risk_score >= C.RISK_AUTO_APPROVE_CEILING:
            return "standard"
        return "routine"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risk_factors"] = self.risk_factors()
        d["requires_human"] = self.requires_human()
        d["gate_band"] = self.gate_band()
        d["urgency_band"] = self.urgency_band()
        return d


@dataclass
class Finding:
    """An observation an agent wants the system to know about."""

    agent: str
    summary: str
    severity: Severity = "info"
    confidence: float = 0.7
    evidence: dict = field(default_factory=dict)
    #: What this finding suggests the orchestrator should consider doing.
    implies: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decision:
    """A human ruling, recorded for audit."""

    action_id: str
    approved: bool
    decided_by: str = "farm_director"
    note: str = ""
    decided_at_tick: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def score_risk(
    *,
    severity: Severity,
    headcount_affected: int = 0,
    water_m3h: float = 0.0,
    reversible: bool = True,
    resource_class: str = "routine",
) -> float:
    """Deterministic risk score.

    Kept as an explicit function of its inputs -- no model, no randomness -- so
    that the score shown to a human is auditable and reproducible.
    """
    base = {"info": 5.0, "low": 15.0, "medium": 35.0, "high": 60.0, "critical": 85.0}[severity]

    if headcount_affected > 10_000:
        base += 12
    elif headcount_affected > 3_000:
        base += 7
    elif headcount_affected > 500:
        base += 3

    if water_m3h > 10_000:
        base += 18
    elif water_m3h > 1_000:
        base += 11
    elif water_m3h > 100:
        base += 6

    if resource_class in ("non_renewable_aquifer", "shared_budget"):
        base += 9
    elif resource_class == "scarce_hardware":
        base += 4

    if not reversible:
        base += 15

    return max(0.0, min(100.0, base))


def score_urgency(
    *,
    animal_welfare: bool = False,
    hours_to_irreversible_harm: float | None = None,
    decays_per_day: bool = False,
    window_closes: bool = False,
) -> float:
    """How soon must this happen?

    `hours_to_irreversible_harm` is the strong signal: rumination suppression
    costs milk for the whole lactation, so it is effectively irreversible on the
    day it happens.
    """
    u = 20.0
    if animal_welfare:
        u += 30.0
    if hours_to_irreversible_harm is not None:
        u += max(0.0, 50.0 * (1.0 - min(hours_to_irreversible_harm, 24.0) / 24.0))
    if decays_per_day:
        u += 25.0
    if window_closes:
        u += 10.0
    return max(0.0, min(100.0, u))


__all__ = ["Action", "Decision", "Finding", "Severity", "score_risk", "score_urgency"]