"""The ledger: the audit trail has to survive the process that wrote it.

The point of these tests is persistence and read-back, not SQL trivia. If the
log evaporates on restart then the product's central claim -- that every
decision is written down where it can be read -- is false.
"""

from __future__ import annotations

from aidustrial.tools import ledger


def test_decisions_persist_across_reconnect(tmp_path):
    ledger.configure(tmp_path / "a.db")
    row_id = ledger.record_decision(
        agent="veterinarian",
        action="enable_misters",
        target="GRP-B01,GRP-B02",
        risk_score=62.0,
        severity="high",
        required_human=True,
        gate_reason="risk 62 is at or above this action's ceiling (25)",
        approved_by="human",
        note="approved",
        rationale="heat load on the two uncooled barns",
        sources=["HEAT-STRESS §2.1"],
        sim_time="D004 14:30",
    )
    assert row_id > 0

    # Re-point at the same file: this is what a restart looks like.
    ledger.configure(tmp_path / "a.db")
    rows = ledger.recent_decisions()
    assert len(rows) == 1
    r = rows[0]
    assert r["action"] == "enable_misters"
    assert r["approved_by"] == "human"
    assert r["sim_time"] == "D004 14:30"
    assert r["sources"] == ["HEAT-STRESS §2.1"]


def test_events_search_by_keyword_and_agent(tmp_path):
    ledger.configure(tmp_path / "b.db")
    ledger.record_event(agent="maintenance", kind="finding", summary="PIVOT-3 vibration 8.0 mm/s over warning", severity="high")
    ledger.record_event(agent="maintenance", kind="finding", summary="PIVOT-1 nominal")
    ledger.record_event(agent="veterinarian", kind="finding", summary="PIVOT-3 is not my domain")

    hits = ledger.search_events("maintenance", ["vibration"])
    assert len(hits) == 1
    assert "vibration" in hits[0]["summary"]

    # Agent scoping must hold: another agent's event never surfaces.
    assert all(h["agent"] == "maintenance" for h in hits)

    # No terms degrades to "recent", never to "everything".
    assert len(ledger.search_events("maintenance", [])) == 2


def test_work_orders_and_chat_are_recorded(tmp_path):
    ledger.configure(tmp_path / "c.db")
    ledger.open_work_order(who="PIVOT-3 bearing", note="vibration over warning", sim_time="D005 06:00")
    ledger.record_chat(agent="maintenance", role="user", text="why PIVOT-3?")
    ledger.record_chat(agent="maintenance", role="assistant", text="vibration crossed 7.1 mm/s", sources=["PIVOT-MAINT §4.2"])

    s = ledger.stats()
    assert s["work_orders"] == 1
    assert s["chat_messages"] == 2
    assert s["decisions"] == 0


def test_stats_reports_a_real_file(tmp_path):
    p = ledger.configure(tmp_path / "d.db")
    assert p.exists()
    assert ledger.stats()["path"].endswith("d.db")
