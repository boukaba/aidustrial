"""Retrieval and the specialist chat.

Two things are being protected here: that an agent can only cite its own
domain, and that the chat still answers when no model is available. The second
matters most -- the public demo runs with the reasoning tracks off, so if the
chat needed a model it would be dead on the judged URL.
"""

from __future__ import annotations

import asyncio

from aidustrial.tools import agentchat, ledger, rag


def _setup(tmp_path):
    ledger.configure(tmp_path / "k.db")
    n = rag.configure()
    assert n > 0, "corpus must index"
    return n


def test_corpus_indexes_and_cites(tmp_path):
    _setup(tmp_path)
    s = rag.stats()
    assert s["documents"] >= 8
    assert s["chunks"] >= 20

    hits = rag.retrieve("maintenance", "bearing vibration warning", k=2)
    assert hits
    assert hits[0]["doc"] == "pivot-maintenance"
    assert hits[0]["cite"].startswith("PIVOT-MAINTENANCE §")


def test_retrieval_is_scoped_to_the_agent(tmp_path):
    _setup(tmp_path)
    # The milk lab lives in the milking doc; the maintenance agent must not see it.
    vet = rag.retrieve("veterinarian", "somatic cell count bulk tank", k=5)
    assert all(h["doc"] in ("heat-stress", "governance-policy") for h in vet)

    milk = rag.retrieve("milking", "somatic cell count bulk tank", k=3)
    assert milk and milk[0]["doc"] == "milking-quality"


def test_empty_query_does_not_throw(tmp_path):
    _setup(tmp_path)
    assert rag.retrieve("milking", "", k=3) == []
    assert rag.retrieve("milking", "!!! ???", k=3) == []


def test_chat_falls_back_when_no_model(tmp_path, monkeypatch):
    _setup(tmp_path)
    ledger.record_event(
        agent="maintenance", kind="finding",
        summary="PIVOT-3 vibration 8.0 mm/s over warning", severity="high",
        sim_time="D004 14:30",
    )
    monkeypatch.setattr("aidustrial.tools.llm._enabled", lambda: False)

    out = asyncio.run(agentchat.answer("maintenance", "what happened with pivot vibration?", {}))
    assert out["model"] is False
    assert "PIVOT-3" in out["answer"]
    assert out["sources"], "a grounded answer must cite something"
    assert out["grounded"]["events"] >= 1

    # The exchange is recorded, so the chat itself is part of the audit trail.
    assert ledger.stats()["chat_messages"] == 2


def test_chat_is_agent_scoped(tmp_path, monkeypatch):
    _setup(tmp_path)
    ledger.record_event(agent="milking", kind="finding", summary="bulk SCC above 400k")
    monkeypatch.setattr("aidustrial.tools.llm._enabled", lambda: False)

    other = asyncio.run(agentchat.answer("maintenance", "what about the bulk tank?", {}))
    assert "SCC" not in other["answer"] or "bulk SCC above 400k" not in other["answer"]
