"""Layer 3 - The Orchestrator (LangGraph state machine).

The orchestrator does not do the work. It routes context between specialists and
decides what needs a human. Its only real judgement is a two-part question:

    does anything need a human, and if so what is the single most consequential
    thing we are asking permission for?

Graph shape:

    sense -> triage -> wake specialists -> collect -> gate -> _route_after_gate
      ^                                                             |
      |                                                             |
      +--------------- execute (approved only) ------------------ human_gate
                                                          (interrupt / resume)

`human_gate` uses LangGraph's interrupt(), so the graph genuinely suspends: no
polling loop, no fake "waiting" state, and the thread can be resumed from any
process via a checkpoint.
"""

from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ..agents.specialists import ALL_AGENTS
from ..tools import sensors
from ..tools.actions import Action, Decision
from ..twin import constants as C
from .state import FarmState, trace_event

AGENT_BY_NAME = {a.name: a for a in ALL_AGENTS}

#: Which specialist owns which implication. This mapping IS the routing policy.
IMPLICATION_ROUTES: dict[str, str] = {
    "start_pivot": "agronomist",
    "shed_pivot": "agronomist",
    "repair_pivot": "maintenance",
    "enable_misters": "veterinarian",
    "shed_load": "veterinarian",
    "restart_inlet": "maintenance",
    "reroute_convoy": "logistics",
}

#: If any agent raises a finding implying one of these, pull in a second opinion.
CROSS_CONSULT: dict[str, list[str]] = {
    "veterinarian": ["agronomist"],
    "agronomist": ["maintenance"],
    "maintenance": ["logistics"],
    "logistics": [],
}


# ---------------------------------------------------------------------------
# NODES
# ---------------------------------------------------------------------------

def sense(state: FarmState) -> dict:
    """Advance the world one tick through the bound sensor gateway."""
    packet = sensors.current().step()
    return {
        "tick": packet["tick"],
        "sim_time": packet["time"],
        "day": packet["day"],
        "phase": packet["phase"],
        "turn": state.get("turn", 0) + 1,
        "trace": [
            trace_event(
                "orchestrator",
                "sense",
                f"Sensed {packet['time']} ({packet['phase']}). "
                f"THI {packet['environment']['thi_air']:.1f} / EHL "
                f"{packet['environment']['effective_heat_load']:.1f} ({packet['environment']['heat_stress_band']}).",
                tick=packet["tick"],
            )
        ],
    }


def triage(state: FarmState) -> dict:
    """Decide who wakes this turn, before any agent burns tokens."""
    packet = sensors.current().packet()
    env, herd, log = packet["environment"], packet["herd"], packet["logistics"]

    focus: list[str] = []
    reasons: list[str] = []
    urgency: list[str] = []

    if env["heat_stress_band"] in ("moderate", "severe") or herd["rumination_deficit_pct"] >= 8:
        focus.append("veterinarian")
        reasons.append(
            f"heat load {env['effective_heat_load']:.0f} ({env['heat_stress_band']}), "
            f"rumination -{herd['rumination_deficit_pct']:.1f}%"
        )
        if env["heat_stress_band"] == "severe":
            urgency.append("severe heat load")

    wilting = sum(
        1 for m in env["soil_moisture_pct"] if m <= C.SOIL_MOISTURE_WILTING_PCT
    )
    if wilting or env["aquifer_budget_used_pct"] >= 85:
        focus.append("agronomist")
        reasons.append(
            f"{wilting} field(s) at wilting point; aquifer "
            f"{env['aquifer_budget_used_pct']:.0f}% of annual envelope"
        )
        if env["aquifer_budget_used_pct"] >= 100:
            urgency.append("aquifer over annual envelope")

    if any(p["health"] != "nominal" for p in env["pivots"]) or any(
        not s["inlet_operational"] for s in log["silos"]
    ):
        focus.append("maintenance")
        reasons.append("asset degradation present")

    if log["feed_hours_of_cover"] < C.SILO_HOURS_OF_COVER_WARN or any(
        t["status"] != "nominal" for t in log["tankers"]
    ):
        focus.append("logistics")
        reasons.append(f"feed cover {log['feed_hours_of_cover']:.0f}h")
        if log["feed_hours_of_cover"] < 24:
            urgency.append("sub-24h feed cover")

    escalation = "urgent" if urgency else ("watch" if focus else "none")

    return {
        "agents_awake": focus,
        "escalation": escalation,
        "trace": [
            trace_event(
                "orchestrator",
                "triage",
                (
                    f"Waking {', '.join(focus)} — " + "; ".join(reasons)
                    if focus
                    else "All systems nominal. No specialist required."
                ),
                escalation=escalation,
            )
        ],
    }


def wake_specialists(state: FarmState) -> dict:
    """Run each focused agent. Parallel in intent; sequential in practice so the
    trace reads cleanly on the dashboard."""
    focus = state.get("agents_awake") or []
    findings, proposals, trace = [], [], []

    for name in focus:
        agent = AGENT_BY_NAME.get(name)
        if agent is None:
            continue
        f, a = agent.run()
        findings.extend(f)
        proposals.extend(a)
        if f or a:
            trace.append(
                trace_event(
                    name,
                    "reason",
                    (
                        f"{len(f)} finding(s), {len(a)} proposal(s). "
                        + (f"Top: {f[0].summary}" if f else "No actionable finding.")
                    ),
                    findings=[x.summary for x in f],
                    proposals=[x.action for x in a],
                )
            )
        else:
            trace.append(trace_event(name, "reason", "Surveyed site. Nothing actionable."))

    return {"findings": findings, "proposals": proposals, "trace": trace}


def consult(state: FarmState) -> dict:
    """Cross-consult. A veterinarian finding does not by itself move irrigation;
    the agronomist has to say whether water can be reallocated to help the herd.

    This is the node that makes the swarm a swarm rather than four dashboards.
    """
    focus = set(state.get("agents_awake") or [])
    extra: list[str] = []
    for name in list(focus):
        for peer in CROSS_CONSULT.get(name, []):
            if peer not in focus and peer not in extra:
                extra.append(peer)
    if not extra:
        return {"trace": [trace_event("orchestrator", "consult", "No cross-consult needed.")]}

    findings, proposals, trace = [], [], []
    for name in extra:
        agent = AGENT_BY_NAME[name]
        f, a = agent.run()
        findings.extend(f)
        proposals.extend(a)
        trace.append(
            trace_event(
                name,
                "consult",
                f"Consulted by {', '.join(sorted(focus))}: "
                + (f[0].summary if f else "no additional findings"),
            )
        )
    return {"findings": findings, "proposals": proposals, "trace": trace}


def _batch(actions: list[Action]) -> list[Action]:
    """Merge same-action proposals into one compound decision."""
    out: list[Action] = []
    by_action: dict[str, list[Action]] = {}
    for a in actions:
        by_action.setdefault(a.action, []).append(a)

    for action, group in by_action.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        group.sort(key=lambda a: a.target)
        head = group[0]
        targets = [a.target for a in group]
        heads = sorted({a.evidence.get("headcount_affected", 0) for a in group})
        total_head = max(heads)
        water = sum(a.evidence.get("water_m3h", 0.0) for a in group)
        out.append(
            Action(
                action=action,
                target=",".join(targets),
                rationale=(
                    f"{len(group)} {action} proposals consolidated into one decision "
                    f"({', '.join(targets)}). " + head.rationale
                ),
                requested_by=head.requested_by,
                risk_score=min(100.0, max(a.risk_score for a in group) + 6.0),
                urgency_score=max(a.urgency_score for a in group),
                severity=head.severity,
                evidence={
                    "headcount_affected": total_head,
                    "water_m3h": water,
                    "batched_count": len(group),
                    "routed_to": head.evidence.get("routed_to", ""),
                },
                blast_radius=head.blast_radius,
                cost_of_inaction=head.cost_of_inaction,
                reversible=all(a.reversible for a in group),
            )
        )
    return sorted(out, key=lambda a: (a.urgency_score, a.risk_score), reverse=True)


def gate(state: FarmState) -> dict:
    """Split proposals into auto-executable and human-gated."""
    proposals = state.get("proposals") or []
    # Cross-consult can re-run an agent that already contributed. Dedupe on
    # (action, target) and keep the highest-risk instance.
    best: dict[tuple[str, str], Action] = {}
    snapshot = sensors.current().packet()
    running_pivots = {p["name"] for p in snapshot["environment"]["pivots"] if p["running"]}
    misting_barns = {
        g["name"] for g in snapshot["herd"]["groups"] if g["misting_enabled"]
    }
    active_inlets = {
        s["name"] for s in snapshot["logistics"]["silos"] if s["inlet_operational"]
    }

    def already_satisfied(a: Action) -> bool:
        targets = [t for t in a.target.split(",") if t]
        if a.action == "start_pivot" and targets and all(t in running_pivots for t in targets):
            return True
        if a.action == "enable_misters" and targets and all(t in misting_barns for t in targets):
            return True
        return bool(
            a.action == "restart_inlet"
            and targets
            and all(t in active_inlets for t in targets)
        )

    world = sensors.current().world
    for p in proposals:
        if not IMPLICATION_ROUTES.get(p.action) or already_satisfied(p):
            continue
        # Cooldown: a repair or restart that has just been carried out is not
        # re-escalated. Without this the human gate becomes noise and the
        # director starts approving reflexively, which defeats the whole point.
        if world.acted_recently(p.action, p.target):
            continue
        k = (p.action, p.target)
        if k not in best or p.risk_score > best[k].risk_score:
            best[k] = p
    routable = list(best.values())

    for p in routable:
        routed = IMPLICATION_ROUTES[p.action]
        p.evidence["routed_to"] = routed
        p.evidence["routed_because"] = (
            f"a {p.action} proposal belongs to the {routed} domain"
        )

    auto = [p for p in routable if not p.requires_human()]
    gated = sorted(
        (p for p in routable if p.requires_human()),
        key=lambda p: (p.urgency_score, p.risk_score),
        reverse=True,
    )

    # Six pivots at wilting point is ONE decision, not six. Batch same-action
    # proposals into a single compound action so the Farm Director is asked
    # once. Asking the same question six times is how you train people to
    # approve reflexively.
    gated = _batch(gated)

    return {
        "proposals": [],
        "gate_queue": gated,
        "trace": [
            trace_event(
                "orchestrator",
                "gate",
                (
                    f"{len(auto)} action(s) below the risk ceiling execute automatically; "
                    f"{len(gated)} require the Farm Director. Most urgent: "
                    + (
                        f"{gated[0].action} ({gated[0].urgency_band()}, "
                        f"risk {gated[0].risk_score:.0f}/100)"
                        if gated
                        else "none"
                    )
                ),
                auto=[a.action for a in auto],
                gated=[a.action for a in gated],
            )
        ],
    }


def execute(state: FarmState) -> dict:
    """Apply everything that cleared the risk ceiling. Gated actions are held."""
    world = sensors.current().world
    held = {a.action_id for a in state.get("gate_queue") or []}
    done, trace = [], []

    for p in state.get("proposals") or []:
        if p.action_id in held:
            continue
        if p.action in ("repair_pivot",):
            continue  # executed only after the gate resolves it
        result = world.apply_action(p.action, p.target)
        done.append({"action": p.action, "target": p.target, "result": result,
                     "approved_by": "auto-policy"})
        trace.append(
            trace_event(
                "orchestrator",
                "execute",
                f"AUTO: {p.action} ({p.target}) → {result}. Risk {p.risk_score:.0f} < ceiling "
                f"{C.RISK_AUTO_APPROVE_CEILING:.0f}.",
            )
        )
    return {"executed": done, "trace": trace}


def human_gate(state: FarmState) -> dict:
    """Suspend the graph and hand the decision to the Farm Director.

    LangGraph's interrupt() checkpoints the entire thread here. The caller
    resumes with Command(resume={"approved": bool, "note": str}).
    """
    queue = state.get("gate_queue") or []
    if not queue:
        return {"pending": None, "decision": None,
                "trace": [trace_event("orchestrator", "gate", "Nothing requires a human.")]}

    top = queue[0]
    payload = {
        "action": top.to_dict(),
        "queued": [a.to_dict() for a in queue[1:]],
        "tick": state.get("tick", 0),
        "sim_time": state.get("sim_time", ""),
        "asked_at": time.time(),
    }

    reply = interrupt(payload)

    approved = bool(reply.get("approved"))
    note = str(reply.get("note", ""))
    decision = Decision(
        action_id=top.action_id,
        approved=approved,
        note=note,
        decided_at_tick=int(state.get("tick", 0)),
    )

    result = sensors.current().world.apply_action(top.action, top.target)
    record = {"action": top.action, "target": top.target, "result": result,
              "approved_by": "farm_director", "note": note}

    verdict = "APPROVED" if approved else "REJECTED"
    trace = [
        trace_event(
            "human",
            "decision",
            f"{verdict} by Farm Director: {top.action} ({top.target}). {note}".strip(),
            approved=approved,
        ),
        trace_event("orchestrator", "execute", f"{verdict} → {result}"),
    ]

    return {
        "pending": None,
        "decision": decision,
        "gate_queue": queue[1:],
        "executed": [record] if approved else [],
        "rejected": [] if approved else [record],
        "trace": trace,
    }


def done(state: FarmState) -> dict:
    if state.get("turn", 0) >= state.get("max_turns", 1):
        return {
            "halt_reason": f"turn budget reached ({state.get('max_turns')})",
            "trace": [trace_event("orchestrator", "halt", "Turn budget reached.")],
        }
    return {}


# ---------------------------------------------------------------------------
# ASSEMBLY
# ---------------------------------------------------------------------------

def build_graph():
    g = StateGraph(FarmState)

    g.add_node("sense", sense)
    g.add_node("triage", triage)
    g.add_node("wake", wake_specialists)
    g.add_node("consult", consult)
    g.add_node("gate", gate)
    g.add_node("execute", execute)
    g.add_node("human_gate", human_gate)
    g.add_node("done", done)

    g.add_edge(START, "sense")
    g.add_edge("sense", "triage")
    g.add_edge("triage", "wake")
    g.add_edge("wake", "consult")
    g.add_edge("consult", "gate")

    # After gate: if anything needs a human, suspend there; otherwise execute.
    g.add_conditional_edges(
        "gate",
        lambda s: "human_gate" if s.get("gate_queue") else "execute",
        {"human_gate": "human_gate", "execute": "execute"},
    )

    # Drain the queue: a turn may hold several decisions. Keep asking until the
    # Farm Director has ruled on all of them, then move on.
    g.add_conditional_edges(
        "human_gate",
        lambda s: "human_gate" if s.get("gate_queue") else "done",
        {"human_gate": "human_gate", "done": "done"},
    )
    g.add_edge("execute", "done")
    g.add_edge("done", END)

    return g


GRAPH = build_graph()

__all__ = [
    "AGENT_BY_NAME",
    "CROSS_CONSULT",
    "GRAPH",
    "IMPLICATION_ROUTES",
    "Action",
    "Command",
    "build_graph",
]