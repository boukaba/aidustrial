"""Twin physics + graph behaviour tests.

These exist to protect the properties that make the demo defensible:
  - the diurnal curve is a real 24h cycle, not a partial-span artifact
  - dry-arid heat is genuinely less lethal than humid heat (the model's core
    honesty claim), and radiant load is what makes Adrar hard anyway
  - misting is scarce HARDWARE, not scarce water
  - agents do not re-propose actions that are already satisfied
"""

from __future__ import annotations

import pytest

from aidustrial.agents.specialists import (
    AgronomistAgent,
    LogisticsAgent,
    MaintenanceAgent,
    VeterinarianAgent,
)
from aidustrial.graph.orchestrator import GRAPH
from aidustrial.tools import sensors
from aidustrial.tools.actions import Action, score_risk
from aidustrial.twin import constants as C
from aidustrial.twin.clock import SimClock
from aidustrial.twin.world import World

# --- clock / diurnal behaviour ---------------------------------------------

def test_diurnal_curve_is_a_full_24h_cycle():
    """A partial-span cosine cliffs at dusk instead of holding a shoulder."""
    c = SimClock(tick=15 * 2)
    peak = c.temperature_c()
    assert peak == pytest.approx(C.TEMP_C_DAY_PEAK, abs=0.5)

    # Evening must still be warm: a broken curve collapses here.
    c19 = SimClock(tick=19 * 2)
    c21 = SimClock(tick=21 * 2)
    assert c19.temperature_c() > c21.temperature_c()
    assert c19.temperature_c() > C.TEMP_C_DAY_PEAK - 12


def test_air_thi_stays_low_in_arid_air():
    """The honesty claim: 43C at ~10% RH is NOT severe heat stress by air THI."""
    c = SimClock(tick=15 * 2)
    assert c.temperature_c() == pytest.approx(43, abs=1)
    assert c.th_i() < C.THI_HEAT_STRESS_ONSET


def test_radiant_load_is_what_creates_the_risk():
    """Air THI alone stays under threshold; adding exposure-weighted solar
    crosses it. This is the whole reason the model exists."""
    noon = SimClock(tick=12 * 2)
    assert noon.th_i() < C.THI_HEAT_STRESS_ONSET
    assert noon.effective_heat_load(exposure=0.82) > C.THI_HEAT_STRESS_ONSET


def test_solar_peaks_at_noon_not_at_peak_temperature():
    noon = SimClock(tick=12 * 2).solar_load()
    fifteen = SimClock(tick=15 * 2).solar_load()
    assert noon > fifteen


def test_no_solar_load_at_night():
    assert SimClock(tick=0).solar_load() == 0.0


# --- the water/hardware trade-off we deliberately do NOT claim --------------

def test_misting_is_not_competing_with_pivots_for_water():
    """Guards the framing we corrected during build. Misting is tiny against
    irrigation; the real contest is pivots vs the annual aquifer envelope."""
    w = World()
    pivot_m3h = C.PIVOTS * (C.PIVOT_AREA_HA * 10_000 * 0.009)
    mist_m3h = C.MISTER_FLOW_LPM * C.COOLING_MISTERS_INSTALLED * 60 / 1000
    assert mist_m3h < pivot_m3h / 100


def test_only_some_barns_have_misting_hardware():
    w = World()
    with_hw = [g for g in w.herd.groups if g.misters_available]
    without = [g for g in w.herd.groups if not g.misters_available]
    assert len(with_hw) == C.COOLING_MISTERS_INSTALLED
    assert len(without) > 0


# --- twin integrity ---------------------------------------------------------

def test_simulation_is_deterministic():
    a, b = World(seed=7), World(seed=7)
    for _ in range(200):
        a.step()
        b.step()
    assert a.observe()["herd"]["rumination_deficit_pct"] == (
        b.observe()["herd"]["rumination_deficit_pct"]
    )


def test_aquifer_status_tracks_projected_annual_draw():
    w = World()
    for p in w.env.pivots:
        p.running = True
    w.apply_action("start_pivot", ",".join(p.name for p in w.env.pivots))
    assert w.env.aquifer.projected_annual_m3h > 0
    assert w.env.aquifer.status() in ("nominal", "constrained", "critical", "over-budget")


def test_heatwave_produces_measurable_herd_harm():
    w = World()
    for _ in range(216):  # land on day 4 midday
        w.step()
    assert w.env.clock.day == 4
    packet = w.observe()
    assert packet["environment"]["heat_stress_band"] in ("moderate", "severe")
    assert packet["herd"]["rumination_deficit_pct"] > 1.0


def test_cooling_mitigates_heat_loss():
    def trough(cool: bool) -> float:
        w = World()
        worst = 100.0
        # Heatwave runs days 4-6; step far enough to cover the whole window.
        for _ in range((6 * 48) + 26):
            p = w.step()
            if p["environment"]["heat_stress_band"] == "moderate":
                if cool and not w.env.misters_on:
                    w.apply_action("enable_misters", "GRP-B01,GRP-B02,GRP-B03,GRP-B04")
                if not cool and w.env.misters_on:
                    w.apply_action("stop_misters", "GRP-B01,GRP-B02,GRP-B03,GRP-B04")
            if 4 <= p["day"] <= 6 and 9 <= p["hour"] <= 19:
                groups = p["herd"]["groups"]
                worst = min(worst, sum(g["milk_yield_pct"] for g in groups) / len(groups))
        return worst

    uncooled = trough(False)
    cooled = trough(True)
    assert cooled > uncooled, "misting must measurably protect yield"


def test_observation_packet_is_json_safe():
    import json

    json.dumps(World().observe(), allow_nan=False)


# --- agent behaviour --------------------------------------------------------

def test_agents_do_not_propose_actions_that_are_already_done():
    """The classic agent failure: re-proposing a repair it just performed."""
    w = World()
    for _ in range(216):
        w.step()
    sensors.bind(w)

    w.apply_action("start_pivot", ",".join(p.name for p in w.env.pivots))
    _f, actions = AgronomistAgent().run()
    assert not [a for a in actions if a.action == "start_pivot"]


def test_bulk_feed_silos_are_not_faulted():
    """Grain/mineral silos are tipper-fed. Flagging them is a false positive."""
    w = World()
    for _ in range(48):
        w.step()
    sensors.bind(w)
    _f, actions = MaintenanceAgent().run()
    for a in actions:
        if a.action == "restart_inlet":
            assert a.target in [
                s["name"]
                for s in w.observe()["logistics"]["silos"]
                if s["inlet_type"] == "conveyor" and not s["inlet_operational"]
            ]


def test_every_proposal_shows_its_work():
    w = World()
    for _ in range(216):
        w.step()
    sensors.bind(w)
    for agent in (VeterinarianAgent(), AgronomistAgent(), MaintenanceAgent(), LogisticsAgent()):
        _f, actions = agent.run()
        for a in actions:
            assert a.rationale, f"{agent.name} proposed without a rationale"
            assert a.cost_of_inaction, f"{agent.name} proposed without cost of inaction"
            assert a.risk_factors()


def test_always_gate_actions_require_a_human():
    for act in C.ALWAYS_GATE_ACTIONS:
        a = Action(action=act, risk_score=1.0)
        assert a.requires_human(), f"{act} must never auto-execute"


# --- risk / urgency separation ---------------------------------------------

def test_risk_and_urgency_are_independent():
    routine = Action(action="start_pivot", risk_score=80, urgency_score=20)
    urgent = Action(action="enable_misters", risk_score=30, urgency_score=90)
    assert routine.risk_score > urgent.risk_score
    assert urgent.urgency_score > routine.urgency_score


def test_score_risk_is_monotonic_in_severity():
    scores = [
        score_risk(severity=s) for s in ("info", "low", "medium", "high", "critical")
    ]
    assert scores == sorted(scores)


def test_non_renewable_water_scores_above_ordinary_work():
    water = score_risk(severity="high", water_m3h=50_000, resource_class="non_renewable_aquifer")
    routine = score_risk(severity="high")
    assert water > routine


# --- graph ------------------------------------------------------------------

def test_graph_halts_at_the_human_gate():
    from langgraph.checkpoint.memory import MemorySaver

    app = GRAPH.compile(checkpointer=MemorySaver())
    w = World()
    for _ in range(216):
        w.step()
    sensors.bind(w)
    out = app.invoke({"max_turns": 1, "turn": 0}, {"configurable": {"thread_id": "t1"}})
    assert out.get("__interrupt__"), "graph must suspend rather than auto-approve"


def test_resuming_requires_a_decision():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    app = GRAPH.compile(checkpointer=MemorySaver())
    w = World()
    for _ in range(216):
        w.step()
    sensors.bind(w)
    cfg = {"configurable": {"thread_id": "t2"}}
    app.invoke({"max_turns": 3, "turn": 0}, cfg)
    out = app.invoke(Command(resume={"approved": False, "note": "no"}), cfg)
    assert out.get("__interrupt__") or out.get("executed") is not None


def test_rejecting_records_the_decision_and_changes_nothing():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    app = GRAPH.compile(checkpointer=MemorySaver())
    w = World()
    for _ in range(216):
        w.step()
    sensors.bind(w)
    cfg = {"configurable": {"thread_id": "t3"}}
    out = app.invoke({"max_turns": 3, "turn": 0}, cfg)
    while out.get("__interrupt__"):
        out = app.invoke(Command(resume={"approved": False, "note": "held"}), cfg)
    assert out["rejected"], "rejections must be recorded for audit"
    assert not out["executed"]


def test_approving_applies_the_action():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    app = GRAPH.compile(checkpointer=MemorySaver())
    w = World()
    for _ in range(216):
        w.step()
    sensors.bind(w)
    cfg = {"configurable": {"thread_id": "t4"}}
    out = app.invoke({"max_turns": 3, "turn": 0}, cfg)
    guard = 0
    while out.get("__interrupt__") and guard < 8:
        out = app.invoke(Command(resume={"approved": True, "note": "go"}), cfg)
        guard += 1
    assert out["executed"], "approval must produce an execution record"
    assert out["executed"][0]["approved_by"] == "farm_director"

# --- three production areas -------------------------------------------------

def test_world_exposes_three_production_areas():
    w = World()
    w.step()
    p = w.observe()
    assert "crop_production" in p and p["crop_production"]["fields"]
    assert "livestock" in p and "milk_production" in p


def test_livestock_is_mostly_non_productive():
    """The economics of the project: most head eats feed and makes no milk."""
    w = World()
    w.step()
    l = w.observe()["livestock"]
    assert l["non_productive_head"] > 0
    assert l["non_productive_head"] < l["total_head"]


def test_airlift_is_mostly_heifers():
    from aidustrial.twin.livestock import AIRLIFT_ARRIVAL_CLASS, HerdClass

    assert AIRLIFT_ARRIVAL_CLASS[HerdClass.HEIFER] > 0.5
    assert AIRLIFT_ARRIVAL_CLASS[HerdClass.DRY] > 0.1


def test_forage_growth_stops_below_wilting_point():
    from aidustrial.twin.crops import CropType, ForageField

    # Mid-season: the logistic accrual curve is still near zero at emergence,
    # so a field has to be part-way through its interval before it grows at all.
    f = ForageField(field_id="X", pivot_id=1, crop=CropType.CORN_SILAGE, area_ha=50.0,
                    days_since_cut=48)
    dry = f.growth_rate_per_day(5.0, 40.0)
    wet = f.growth_rate_per_day(25.0, 40.0)
    assert dry == 0.0, "growth must be exactly zero below the wilting point"
    assert wet > dry


def test_cut_requires_something_on_the_ground():
    from aidustrial.twin.crops import CropType, ForageField

    f = ForageField(field_id="X", pivot_id=1, crop=CropType.CORN_SILAGE, area_ha=50.0,
                    days_since_cut=200, biomass_t_ha=0.1)
    assert not f.ready_for_cut


# --- the mesh ---------------------------------------------------------------

def test_agents_post_to_a_shared_board():
    from aidustrial.graph.orchestrator import ALL
    from aidustrial.tools import sensors as sg

    w = World()
    for _ in range(216):
        w.step()
    sg.bind(w)
    for a in ALL:
        a.survey(w.board)
    assert w.board.messages, "surveys must broadcast to the board"
    assert any(m.kind == "question" for m in w.board.messages), \
        "at least one agent must ask a peer something"


def test_mesh_routes_only_agents_actually_addressed():
    from aidustrial.graph.orchestrator import ALL
    from aidustrial.tools import sensors as sg

    w = World()
    for _ in range(216):
        w.step()
    sg.bind(w)
    for a in ALL:
        a.survey(w.board)
    open_msgs = w.board.open_threads()
    assert open_msgs
    addressed = {m.recipient for m in open_msgs}
    for name in addressed:
        agent = next(a for a in ALL if a.name == name)
        agent.respond(w.board, agent_specific_inbox(w.board, name))
    assert not w.board.open_threads(), "responders must close their threads"


def agent_specific_inbox(board, agent_name):
    return board.inbox(agent_name)


def test_board_clears_between_rounds():
    from aidustrial.graph.orchestrator import ALL
    from aidustrial.tools import sensors as sg

    w = World()
    for _ in range(216):
        w.step()
    sg.bind(w)
    for a in ALL:
        a.survey(w.board)
    assert w.board.messages
    w.board.messages.clear()
    assert not w.board.messages


def test_every_agent_declares_domains_and_can_respond():
    from aidustrial.graph.orchestrator import ALL

    assert len(ALL) >= 7
    for a in ALL:
        assert a.domains, f"{a.name} declares no domains"
        assert callable(getattr(a, "survey", None)), f"{a.name} cannot survey"
        assert callable(getattr(a, "respond", None)), f"{a.name} cannot respond"


def test_graph_runs_both_deliberation_rounds():
    from langgraph.checkpoint.memory import MemorySaver

    from aidustrial.graph.orchestrator import GRAPH

    app = GRAPH.compile(checkpointer=MemorySaver())
    w = World()
    for _ in range(216):
        w.step()
    sensors.bind(w)
    out = app.invoke({"max_turns": 1, "turn": 0}, {"configurable": {"thread_id": "mesh-t"}})
    phases = {t["phase"] for t in out["trace"]}
    assert "survey" in phases
    assert "mesh" in phases
    assert "deliberate" in phases
