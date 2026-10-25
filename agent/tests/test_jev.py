"""Tests for the Jev / SystemOne decision track.

Same two invariants as the prose track in `test_llm.py`, plus the one that
matters more here:

  1. A model may escalate. It may never de-escalate past what the rules found.
  2. A model may never set the risk score. Risk decides whether a human is
     consulted; a model that could lower it could slip past the gate.
  3. An action the model proposes that the rules did not find always faces a
     human. We have no sensor figure to score it, so it cannot auto-approve.

The third is what makes Jev safe to put on the *deciding* track rather than
only the *narrating* one.

No network in the test suite -- every decision is a hand-written payload.
"""

from __future__ import annotations

import json

from aidustrial.agents.reasoning import (
    ACTION_LABELS,
    OWNED,
    apply_jev,
    build_jev_payload,
    build_jev_questions,
)
from aidustrial.tools.actions import Action, Finding, score_urgency
from aidustrial.tools.jev import (
    ACTION_FLOOR,
    JEVS,
    NO_ACTION,
    WARRANT_FLOOR,
    Decision,
    JevBrain,
    parse_decision,
)
from aidustrial.twin import constants as C

#: Mirrors IMPLICATION_ROUTES in graph/orchestrator.py. Duplicated here (as
#: test_llm.py does) rather than imported, so this file tests the parse layer
#: without pulling the LangGraph orchestrator into the import chain.
ALLOWED = frozenset({
    "start_pivot", "shed_pivot", "repair_pivot", "harvest_field",
    "boost_heifer_rations", "isolate_calves", "service_parlour",
    "clean_condenser", "cull_chronic_mastitis", "halt_intake",
    "enable_misters", "shed_load", "restart_inlet", "reroute_convoy",
})


def _payload(choice="enable_misters", p=0.92, warrant=0.85, urg=2, sev=3, probs=None):
    """A hand-written SystemOne response, as the endpoint returns it."""
    return {
        "model": "jev-1.13-free",
        "answers": {
            "warranted": {"type": "noul", "noul": warrant},
            "action": {
                "type": "choice",
                "choice": choice,
                "confidence": p,
                "probabilities": probs if probs is not None else {choice: p},
            },
            "urgency": {"type": "score", "score": urg},
            "severity": {"type": "score", "score": sev},
        },
        "usage": {"input_tokens": 400, "output_tokens": 60},
    }


def _decision(**kw) -> Decision:
    base = {
        "agent": "veterinarian",
        "warranted": True,
        "action": "enable_misters",
        "action_p": 0.92,
        "urgency": 90.0,
        "severity": "high",
        "confidence": 0.92,
        "answered": True,
        "ms": 850.0,
        "model": "jev-1.13-free",
    }
    base.update(kw)
    return Decision(**base)


def _inject(agent: str, d: Decision) -> None:
    JEVS._results[agent] = d


# --- parsing: the typed contract -------------------------------------------


def test_parse_full_decision():
    d = parse_decision("veterinarian", _payload(), allowed=ALLOWED)
    assert d.warranted is True
    assert d.action == "enable_misters"
    assert d.action_p == 0.92
    assert d.urgency == 90.0
    assert d.severity == "high"  # rubric index 3, 0-indexed
    assert d.valid is True


def test_parse_no_action_is_a_valid_answer():
    d = parse_decision("veterinarian", _payload(choice=NO_ACTION, p=0.6), allowed=ALLOWED)
    assert d.valid is True
    assert d.action == ""
    assert d.actionable is False


def test_parse_unreadable_payload_is_invalid():
    for raw in ({}, {"answers": None}, {"answers": "nope"}, {"answers": {"action": {}}}):
        d = parse_decision("veterinarian", raw, allowed=ALLOWED)
        assert d.valid is False
        assert d.actionable is False


def test_parse_low_probability_is_not_actionable():
    d = parse_decision("veterinarian", _payload(p=ACTION_FLOOR - 0.01), allowed=ALLOWED)
    assert d.action == "enable_misters"  # we still record the pick
    assert d.actionable is False  # but refuse to act on it


def test_parse_missing_probability_fails_safe():
    """No odds at all must read as no confidence, never as full confidence."""
    d = parse_decision("veterinarian", _payload(probs={}), allowed=ALLOWED)
    assert d.action_p == 0.0
    assert d.actionable is False


def test_parse_choice_outside_offered_set_is_ignored():
    """The choice set is closed by construction; guard it anyway."""
    d = parse_decision("veterinarian", _payload(choice="dispatch_helicopter"), allowed=ALLOWED)
    assert d.action == ""
    assert d.actionable is False


def test_parse_low_warrant_is_not_actionable():
    d = parse_decision("veterinarian", _payload(warrant=WARRANT_FLOOR - 0.01), allowed=ALLOWED)
    assert d.warranted is False
    assert d.actionable is False


def test_urgency_rubric_decodes_to_levels():
    assert parse_decision("x", _payload(urg=0), allowed=ALLOWED).urgency == 20.0
    assert parse_decision("x", _payload(urg=1), allowed=ALLOWED).urgency == 55.0
    assert parse_decision("x", _payload(urg=2), allowed=ALLOWED).urgency == 90.0


def test_out_of_range_rubric_index_clamps():
    assert parse_decision("x", _payload(urg=9), allowed=ALLOWED).urgency == 90.0
    assert parse_decision("x", _payload(sev=-3), allowed=ALLOWED).severity == "info"


def test_every_owned_action_has_a_readable_label():
    """A bare verb makes a small model guess; a sentence does not."""
    for agent, actions in OWNED.items():
        for name in actions:
            assert name in ACTION_LABELS, f"{agent}/{name} has no label"
            assert ACTION_LABELS[name] != name.replace("_", " ")


# --- questions: the choice set is closed ------------------------------------


def test_questions_offer_only_own_actions_plus_no_action():
    # The invariant is that the choice set is CLOSED: exactly the agent's own
    # actions plus "no action", never a neighbour's. Deriving it from OWNED
    # means adding an action to an agent updates this test instead of breaking
    # it -- the thing being protected is the boundary, not a frozen list.
    for agent, owned in OWNED.items():
        q = build_jev_questions(agent)
        assert set(q["action"]["criteria"]) == set(owned) | {NO_ACTION}, agent

    # No cross-agent leakage.
    q2 = build_jev_questions("milking")
    assert NO_ACTION in q2["action"]["criteria"]
    assert "enable_misters" not in q2["action"]["criteria"]


def test_questions_ask_the_four_types():
    q = build_jev_questions("crop")
    assert q["warranted"]["type"] == "noul"
    assert q["action"]["type"] == "choice"
    assert q["urgency"]["type"] == "score"
    assert q["severity"]["type"] == "score"


def test_payload_carries_model_and_state():
    p = build_jev_payload("crop", None)
    assert p["model"] == JEVS.model
    assert isinstance(p["state"], str)
    assert p["state"]


# --- the safety invariants --------------------------------------------------


def test_model_action_always_faces_a_human():
    _inject("veterinarian", _decision())
    actions: list[Action] = []
    _, actions = apply_jev("veterinarian", [], actions)
    assert len(actions) == 1
    assert actions[0].action == "enable_misters"
    # The whole point: no evidence we can score, therefore no auto-approval.
    assert actions[0].risk_score >= C.RISK_AUTO_APPROVE_CEILING
    assert actions[0].evidence["origin"] == "jev"


def test_low_confidence_decision_is_not_merged():
    _inject("veterinarian", _decision(action_p=ACTION_FLOOR - 0.01))
    _, actions = apply_jev("veterinarian", [], [])
    assert actions == []


def test_warranted_decision_is_not_merged_when_not_warranted():
    _inject("veterinarian", _decision(warranted=False))
    _, actions = apply_jev("veterinarian", [], [])
    assert actions == []


def test_severity_may_escalate_but_never_deescalate():
    f = Finding(agent="veterinarian", summary="s", severity="medium", confidence=0.5)
    _inject("veterinarian", _decision(severity="critical"))
    apply_jev("veterinarian", [f], [])
    assert f.severity == "critical"

    f2 = Finding(agent="veterinarian", summary="s", severity="critical", confidence=0.5)
    _inject("veterinarian", _decision(severity="low"))
    apply_jev("veterinarian", [f2], [])
    assert f2.severity == "critical"  # the rule stands


def test_urgency_may_rise_but_never_fall():
    a = Action(action="enable_misters", urgency_score=90.0)
    _inject("veterinarian", _decision(urgency=55.0))
    apply_jev("veterinarian", [], [a])
    assert a.urgency_score == 90.0  # not lowered
    assert "urgency_from_jev" not in a.evidence

    a2 = Action(action="enable_misters", urgency_score=40.0)
    _inject("veterinarian", _decision(urgency=90.0))
    apply_jev("veterinarian", [], [a2])
    assert a2.urgency_score == 90.0
    assert a2.evidence["urgency_from_jev"] is True


def test_rule_proposal_is_not_duplicated_by_the_model():
    a = Action(action="enable_misters", urgency_score=50.0)
    _inject("veterinarian", _decision(action="enable_misters"))
    _, actions = apply_jev("veterinarian", [], [a])
    assert len(actions) == 1


def test_model_proposed_urgency_is_at_least_the_floor():
    """A model that says 'now' for a 24h-harm action must not look lazy."""
    _inject("veterinarian", _decision(urgency=20.0))
    _, actions = apply_jev("veterinarian", [], [])
    floor = score_urgency(hours_to_irreversible_harm=24.0)
    assert actions[0].urgency_score >= floor


def test_decision_is_recorded_on_the_finding_for_the_ui():
    f = Finding(agent="veterinarian", summary="s", severity="medium", confidence=0.5)
    _inject("veterinarian", _decision())
    apply_jev("veterinarian", [f], [])
    jev = f.evidence["jev"]
    assert jev["warranted"] is True
    assert jev["probability"] == 0.92
    assert jev["model"] == "jev-1.13-free"
    assert jev["ms"] == 850.0


def test_quiet_decision_produces_no_findings_and_no_actions():
    """A valid 'nothing to do' answer must stay quiet, not invent work."""
    _inject("veterinarian", _decision(warranted=False, action="", action_p=0.0))
    findings, actions = apply_jev("veterinarian", [], [])
    assert findings == []
    assert actions == []


# --- the brain's plumbing ---------------------------------------------------


def test_request_is_non_blocking_and_dedupes(monkeypatch):
    # enabled() needs a credential. This test is about the cache path, so it
    # supplies one rather than depending on the developer's ~/.local store.
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    b = JevBrain(allowed_actions={"enable_misters"})
    b._results["veterinarian"] = _decision()
    b._last_call["veterinarian"] = __import__("time").time()
    before = b.cache_hits
    b.request("veterinarian", {"model": "m", "state": "s", "questions": {}}, "other-hash")
    assert b.cache_hits == before + 1
    assert "veterinarian" not in b._pending


def test_inflight_blocks_duplicate_queue():
    b = JevBrain(allowed_actions={"enable_misters"})
    b._inflight.add("veterinarian")
    b.request("veterinarian", {"model": "m", "state": "s", "questions": {}}, "h")
    assert "veterinarian" not in b._pending


def test_disabled_brain_ignores_requests(monkeypatch):
    monkeypatch.setenv("AIDUSTRIAL_JEV", "off")
    b = JevBrain()
    b.request("veterinarian", {"model": "m", "state": "s", "questions": {}}, "h")
    assert "veterinarian" not in b._pending


def test_stats_expose_rejected_low_confidence():
    b = JevBrain()
    stats = b.stats()
    assert "rejected_low_confidence" in stats
    assert stats["agents_decided"] == []


# --- credential resolution --------------------------------------------------


def test_key_env_var_wins(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-from-env")
    from aidustrial.tools.jev import _api_key

    assert _api_key() == "sk-from-env"


def test_key_falls_back_to_opencode_auth_store(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    store = tmp_path / "auth.json"
    store.write_text(json.dumps({"auth": {"opencode-go": {"type": "api", "key": "sk-stored"}}}))
    monkeypatch.setenv("OPENCODE_AUTH_PATH", str(store))
    from aidustrial.tools.jev import _api_key

    assert _api_key() == "sk-stored"


def test_key_absent_everywhere_is_empty(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.setenv("OPENCODE_AUTH_PATH", str(tmp_path / "missing.json"))
    from aidustrial.tools.jev import _api_key

    assert _api_key() == ""
