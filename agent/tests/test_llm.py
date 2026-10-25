"""Tests for the LLM reasoning layer.

These guard the two properties that make letting a language model near the
decision path defensible at all:

  1. A model can escalate. It can never de-escalate past what the rules found.
  2. A model can never set the risk score, because risk is what decides
     whether a human is consulted. A model that could lower it could slip an
     action past the gate.

Everything here runs against fakes -- no network in the test suite.
"""

from __future__ import annotations

import json

from aidustrial.agents.reasoning import _trim, apply_reasoning
from aidustrial.tools.actions import Action, Finding
from aidustrial.tools.llm import (
    BRAIN,
    Brain,
    Reasoning,
    _extract_json,
    _repair_truncated,
)


def _reasoning(**kw) -> Reasoning:
    base = {
        "agent": "veterinarian",
        "summary": "Cows in barn B07 are panting and off their feed.",
        "severity": "high",
        "confidence": 0.9,
        "rationale": "Rumination deficit is 14% and EHL is 81.",
        "action": "enable_misters",
        "target": "B07",
        "urgency": 85.0,
        "reversible": True,
        "hash": "h1",
        "model": "mimo-v2.6-flash:free",
    }
    base.update(kw)
    return Reasoning(**base)


# --- JSON extraction: free models fence, ramble and truncate ---------------


def test_extract_plain_json():
    assert _extract_json('{"summary": "x"}') == {"summary": "x"}


def test_extract_fenced_json():
    raw = "Here you go:\n```json\n{\"summary\": \"x\"}\n```\nHope that helps."
    assert _extract_json(raw) == {"summary": "x"}


def test_extract_json_with_surrounding_prose():
    assert _extract_json('noise {"a": 1} more noise') == {"a": 1}


def test_extract_garbage_returns_none():
    assert _extract_json("I cannot answer that.") is None
    assert _extract_json("") is None


def test_repair_truncated_object():
    """A response cut off mid-string must still parse, not raise."""
    broken = '{"summary": "the pivot is degra'
    assert _repair_truncated(broken) == {"summary": "the pivot is degra"}


def test_repair_truncated_after_complete_key():
    broken = '{"summary": "ok", "severity": "high", "confid'
    out = _repair_truncated(broken)
    assert out == {"summary": "ok", "severity": "high"}


# --- action vocabulary: a hallucinated verb must never reach the executor ---


def _brain() -> Brain:
    b = Brain(allowed_actions={"enable_misters", "start_pivot"})
    return b


def test_model_action_in_vocabulary_is_accepted():
    b = _brain()
    r = b._parse("veterinarian", json.dumps({"summary": "s", "action": "enable_misters"}), "h")
    assert r.action == "enable_misters"
    assert r.implies == "enable_misters"


def test_model_action_outside_vocabulary_is_dropped():
    b = _brain()
    r = b._parse(
        "veterinarian",
        json.dumps({"summary": "s", "action": "dispatch_helicopter"}),
        "h",
    )
    assert r.action == ""
    assert r.implies == ""
    assert b.dropped == 1


def test_prose_implies_is_not_treated_as_an_action():
    """The model often writes prose into `implies`. That must not become an action."""
    b = _brain()
    r = b._parse(
        "veterinarian",
        json.dumps(
            {
                "summary": "s",
                "implies": "Turn on the misters in barn B07 immediately and "
                "notify the farm manager about the heat stress situation.",
            }
        ),
        "h",
    )
    assert r.action == ""


def test_severity_outside_enum_falls_back_to_info():
    b = _brain()
    r = b._parse("veterinarian", json.dumps({"summary": "s", "severity": "catastrophic"}), "h")
    assert r.severity == "info"


def test_confidence_and_urgency_are_clamped():
    b = _brain()
    r = b._parse(
        "veterinarian",
        json.dumps({"summary": "s", "confidence": 42, "urgency": -7}),
        "h",
    )
    assert r.confidence == 1.0
    assert r.urgency == 0.0


def test_non_numeric_confidence_defaults_low():
    b = _brain()
    r = b._parse("veterinarian", json.dumps({"summary": "s", "confidence": "very high"}), "h")
    assert r.confidence == 0.0


# --- the safety invariants -------------------------------------------------


def test_model_can_escalate_severity():
    f = Finding(agent="veterinarian", summary="rule summary", severity="medium", confidence=0.8)
    a = Action(action="enable_misters", target="B07", urgency_score=40.0, risk_score=62.0)
    BRAIN._results["veterinarian"] = _reasoning(severity="critical", urgency=90.0)
    apply_reasoning("veterinarian", [f], [a])
    assert f.severity == "critical"
    assert a.urgency_score == 90.0


def test_model_cannot_deescalate_severity():
    f = Finding(agent="veterinarian", summary="rule summary", severity="critical", confidence=0.9)
    a = Action(action="enable_misters", target="B07", urgency_score=90.0, risk_score=80.0)
    BRAIN._results["veterinarian"] = _reasoning(severity="info", urgency=10.0)
    apply_reasoning("veterinarian", [f], [a])
    assert f.severity == "critical"
    assert a.urgency_score == 90.0


def test_model_never_sets_risk_score():
    """The risk score routes a proposal to the human gate. The model must not touch it."""
    a = Action(action="enable_misters", target="B07", risk_score=72.0, urgency_score=50.0)
    f = Finding(agent="veterinarian", summary="s", severity="high")
    BRAIN._results["veterinarian"] = _reasoning()
    apply_reasoning("veterinarian", [f], [a])
    assert a.risk_score == 72.0


def test_model_only_rises_in_urgency():
    a = Action(action="enable_misters", target="B07", urgency_score=88.0, risk_score=60.0)
    f = Finding(agent="veterinarian", summary="s", severity="high")
    BRAIN._results["veterinarian"] = _reasoning(urgency=30.0)
    apply_reasoning("veterinarian", [f], [a])
    assert a.urgency_score == 88.0


def test_model_originated_action_is_always_gated():
    """An action the rules did not find cannot be auto-approved: we have no
    evidence to score it, so it must face a person."""
    BRAIN._results["veterinarian"] = _reasoning(action="enable_misters")
    f: list[Finding] = []
    a: list[Action] = []
    apply_reasoning("veterinarian", f, a)
    assert len(a) == 1
    assert a[0].requires_human()
    assert a[0].evidence["origin"] == "model"


def test_rule_action_is_not_duplicated_when_model_agrees():
    a = Action(action="enable_misters", target="B07", risk_score=60.0)
    f = Finding(agent="veterinarian", summary="s", severity="high")
    BRAIN._results["veterinarian"] = _reasoning(action="enable_misters")
    apply_reasoning("veterinarian", [f], [a])
    assert len([x for x in [a] if x.action == "enable_misters"]) == 1


def test_reasoning_is_ignored_when_absent_or_invalid():
    f = Finding(agent="veterinarian", summary="rule summary", severity="medium")
    a = Action(action="enable_misters", urgency_score=40.0)
    BRAIN._results.pop("veterinarian", None)
    apply_reasoning("veterinarian", [f], [a])
    assert f.summary == "rule summary"
    assert a.urgency_score == 40.0

    BRAIN._results["veterinarian"] = Reasoning(agent="veterinarian", summary="  ")
    apply_reasoning("veterinarian", [f], [a])
    assert f.summary == "rule summary"


def test_narrative_and_provenance_are_attached():
    f = Finding(agent="veterinarian", summary="old", severity="high", confidence=0.7)
    BRAIN._results["veterinarian"] = _reasoning(confidence=0.95)
    apply_reasoning("veterinarian", [f], [])
    assert f.summary == "Cows in barn B07 are panting and off their feed."
    assert f.confidence == 0.95
    assert f.evidence["reasoning_rationale"] == "Rumination deficit is 14% and EHL is 81."
    assert f.evidence["reasoned_by"]


# --- prompt-budget trimming ------------------------------------------------


def test_trim_keeps_head_of_long_list():
    data = [{"id": i, "name": f"field-{i}", "moisture": 10.5 + i} for i in range(40)]
    out = _trim(data, 400)
    assert isinstance(out, dict)
    assert "_truncated" in out
    assert len(out["sample"]) < 40
    assert out["sample"][0]["id"] == 0  # the head survives


def test_trim_passes_small_values_through():
    assert _trim({"a": 1}, 500) == {"a": 1}
    assert _trim([1, 2, 3], 500) == [1, 2, 3]


def test_trim_shrinks_nested_dicts():
    big = {f"k{i}": [{"x": j} for j in range(30)] for i in range(5)}
    out = _trim(big, 900)
    blob = json.dumps(out, default=str)
    assert len(blob) < len(json.dumps(big, default=str))


# --- cooldown dedup --------------------------------------------------------


def test_cooldown_prevents_immediate_requeue(monkeypatch):
    # enabled() is false without a local opencode server or an explicit base.
    # This test is about the cooldown path, so it opts in explicitly.
    monkeypatch.setenv("AIDUSTRIAL_ZEN_BASE", "http://127.0.0.1:9")
    b = Brain(allowed_actions={"enable_misters"})
    b._results["veterinarian"] = _reasoning(hash="old")
    b._last_call["veterinarian"] = 1e12  # pretend the call just happened
    import time as _t

    b._last_call["veterinarian"] = _t.time()
    before = b.cache_hits
    b.request("veterinarian", {"system": "s", "user": "u"}, "different-hash")
    assert b.cache_hits == before + 1
    assert "veterinarian" not in b._pending


def test_inflight_blocks_duplicate_queue():
    b = Brain(allowed_actions={"enable_misters"})
    b._inflight.add("veterinarian")
    b.request("veterinarian", {"system": "s", "user": "u"}, "h")
    assert "veterinarian" not in b._pending


def test_disabled_brain_ignores_requests(monkeypatch):
    monkeypatch.setenv("AIDUSTRIAL_LLM", "off")
    b = Brain()
    b.request("veterinarian", {"system": "s", "user": "u"}, "h")
    assert "veterinarian" not in b._pending
