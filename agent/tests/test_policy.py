"""Autonomy policy: the rules that decide when a person is required.

The point of these tests is the safety ordering, not the numbers. A future
change may retune a ceiling; it may never let a model-reachable path widen
autonomy past the global gate, and it may never make an always-gate action
automatic.
"""

from aidustrial.tools.actions import Action
from aidustrial.twin import constants as C
from aidustrial.twin import policy


def test_autonomous_actions_never_need_a_human():
    for act in ("set_lighting", "notify_technician"):
        for risk in (0, 40, 80, 100):
            assert policy.requires_human(act, risk)[0] is False, f"{act} at {risk}"


def test_bounded_action_gates_at_its_own_ceiling():
    ceiling = policy.ceiling_for("set_ventilation")
    assert ceiling is not None and ceiling < C.RISK_AUTO_APPROVE_CEILING
    assert policy.requires_human("set_ventilation", ceiling - 1)[0] is False
    assert policy.requires_human("set_ventilation", ceiling)[0] is True


def test_always_gate_actions_never_auto_execute():
    for act in C.ALWAYS_GATE_ACTIONS:
        for risk in (0, 10, 39, 100):
            needs, why = policy.requires_human(act, risk)
            assert needs is True, f"{act} must never auto-execute (risk {risk})"
            assert why


def test_bounded_ceiling_cannot_exceed_the_global_gate():
    """A per-action rule exists to tighten autonomy, never to widen it."""
    for act in ("set_ventilation", "enable_misters", "some_unlisted_action"):
        ceiling = policy.ceiling_for(act)
        assert ceiling is not None
        assert ceiling <= C.RISK_AUTO_APPROVE_CEILING


def test_unknown_action_falls_back_to_the_global_gate():
    assert policy.ceiling_for("invented_action") == C.RISK_AUTO_APPROVE_CEILING
    assert policy.requires_human("invented_action", 39)[0] is False
    assert policy.requires_human("invented_action", 40)[0] is True


def test_action_model_delegates_to_policy():
    lighting = Action(action="set_lighting", risk_score=95.0)
    assert lighting.requires_human() is False
    assert "runs without a human" in lighting.risk_factors()[0]

    water = Action(action="transfer_water", risk_score=1.0)
    assert water.requires_human() is True
    assert "always gated" in water.risk_factors()[0]

    pivot = Action(action="repair_pivot", risk_score=10.0)
    assert pivot.requires_human() is False
    assert "auto below" in pivot.risk_factors()[0]


def test_describe_covers_every_governed_action():
    rows = {r["action"] for r in policy.describe()}
    assert set(policy.POLICY) <= rows
    assert set(C.ALWAYS_GATE_ACTIONS) <= rows
    for r in policy.describe():
        assert r["tier"] in {"autonomous", "bounded", "always_gate"}
        assert r["why"]
