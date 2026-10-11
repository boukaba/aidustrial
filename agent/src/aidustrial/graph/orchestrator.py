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

from ..agents.domains import ALL_DOMAIN_AGENTS
from ..agents.reasoning import apply_jev, apply_reasoning, request_jev, request_reasoning
from ..agents.specialists import ALL_AGENTS
from ..tools import sensors
from ..tools.actions import Action, Decision
from ..tools.jev import JEVS as _JEVS
from ..tools.llm import BRAIN as _BRAIN
from ..tools.sensors import CURRENT_AGENT
from ..twin import constants as C
from .state import FarmState, trace_event

ALL = list(ALL_AGENTS) + list(ALL_DOMAIN_AGENTS)
AGENT_BY_NAME = {a.name: a for a in ALL}
#: The agronomist owns irrigation; the crop specialist owns forage production.
#: Both wake on soil or water signals, so the router consults both.
DOMAIN_TRIGGERS: dict[str, str] = {
    "crop": "crop", "irrigation": "agronomist", "soil": "agronomist",
    "forage": "crop", "water": "agronomist",
    "livestock": "calving", "youngstock": "calving", "reproduction": "calving",
    "herd_health": "veterinarian", "heat": "veterinarian", "cooling": "veterinarian",
    "milk": "milking", "parlour": "milking", "quality": "milking",
    "cooling_chain": "milking", "powder": "milking",
    "assets": "maintenance", "maintenance": "maintenance",
    "feed": "logistics", "transport": "logistics", "airlift": "logistics",
}

#: Which specialist owns which implication. This mapping IS the routing policy.
IMPLICATION_ROUTES: dict[str, str] = {
    "start_pivot": "agronomist",
    "shed_pivot": "agronomist",
    "repair_pivot": "maintenance",
    "harvest_field": "crop",
    "boost_heifer_rations": "calving",
    "isolate_calves": "calving",
    "service_parlour": "milking",
    "clean_condenser": "milking",
    "cull_chronic_mastitis": "milking",
    "halt_intake": "milking",
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

#: The LLM is only allowed to propose actions the system already knows how to
#: route and execute. Anything else it invents is dropped in `tools/llm.py`.
#: Jev gets the same set, but as a closed `choice` vocabulary it must pick from
#: rather than a post-hoc filter -- see `agents/reasoning.build_jev_questions`.
_BRAIN.allowed = frozenset(IMPLICATION_ROUTES)
_JEVS.allowed = frozenset(IMPLICATION_ROUTES)


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

    crop = sensors.crops()
    livestock = sensors.youngstock()
    milk = sensors.milk()

    wilting = sum(1 for f in crop["fields"] if f["soil_moisture_pct"] <= C.SOIL_MOISTURE_WILTING_PCT)
    if wilting or env["aquifer_budget_used_pct"] >= 85 or crop["water_stressed_ha"] > 0:
        focus.append("agronomist")
        if crop["water_stressed_ha"] > 0:
            focus.append("crop")
        reasons.append(
            f"{wilting} field(s) at wilting point; aquifer "
            f"{env['aquifer_budget_used_pct']:.0f}% of annual envelope"
        )
        if env["aquifer_budget_used_pct"] >= 100:
            urgency.append("aquifer over annual envelope")

    ready = [f for f in crop["fields"] if f["ready_for_cut"]]
    if ready or any(f["health"] != "nominal" for f in crop["fields"]):
        if "crop" not in focus:
            focus.append("crop")
        reasons.append(f"{len(ready)} forage field(s) cut-ready; programme status {crop['status']}")

    deficient = [g for g in livestock["groups_heifer"] if g["weight_pct_of_target"] < 88.0]
    sick_calves = [g for g in livestock["groups_calf"] if g["scours_rate_pct"] > 6.0]
    if deficient or sick_calves or livestock["status"] != "nominal":
        focus.append("calving")
        reasons.append(
            f"{sum(g['head'] for g in deficient):,} heifers under breeding weight; "
            f"{livestock['non_productive_head']:,} non-productive head"
        )
        if sick_calves:
            urgency.append("calf morbidity above threshold")

    if (
        milk["downtime_min_24h"] > 60
        or milk["bulk_scc_k"] > 200
        or milk["bulk_temp_c"] > 6.5
        or milk["silo_fill_pct"] > 92
        or milk["status"] != "nominal"
    ):
        focus.append("milking")
        reasons.append(
            f"SCC {milk['bulk_scc_k']:.0f}k, bulk {milk['bulk_temp_c']:.1f}C, "
            f"downtime {milk['downtime_min_24h']:.0f}min"
        )
        if milk["bulk_temp_c"] > 8.0:
            urgency.append("bulk milk above rejection temperature")

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
        "dispatched": focus,
        "dispatch_reasons": reasons,
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
    """ROUND 1 -- survey. Each focused agent reads the site and broadcasts what
    it sees onto the shared blackboard, alongside its own proposals.

    Two reasoning tracks run on top of the rules, and they divide the work by
    what each is good at:

      Jev (SystemOne) DECIDES. Typed questions, ~0.85s, lands nearly on the
          same tick as the readings that caused it.
      flash (Token Harbor) WRITES. The plain-language summary a judge reads,
          12-66s, and that is fine -- nothing blocks on it.

    The threshold rules still run first and always produce output: they are
    the floor that keeps the demo alive when the network is slow or a free
    tier is rate-limiting. Both verdicts, when they have landed, are merged on
    top under the escalation-only safety rules in `agents/reasoning.py`.
    """
    focus = state.get("agents_awake") or []
    world = sensors.current().world
    board = world.board
    board.messages.clear()

    findings, proposals, trace = [], [], []
    for name in focus:
        agent = AGENT_BY_NAME.get(name)
        if agent is None:
            continue
        CURRENT_AGENT.set(name)

        # 1. rules -- synchronous, deterministic, always succeeds
        f, a = agent.survey(board)

        # 2. ask both tracks to reason about the same slice. Neither blocks:
        #    they stash work for the server's event loop and return at once.
        request_jev(name, board)
        request_reasoning(name, board, getattr(agent, "system_prompt", ""))

        # 3. merge any verdict that has already landed (from a prior tick).
        #    Jev first: its verdict is the one that may *propose an action*,
        #    and the prose track then narrates whatever is in front of it.
        f, a = apply_jev(name, f, a)
        f, a = apply_reasoning(name, f, a)
        r = _BRAIN.get(name)

        findings.extend(f)
        proposals.extend(a)
        trace.append(
            trace_event(
                name, "survey",
                (f"{len(f)} finding(s), {len(a)} proposal(s). "
                 + (f"Top: {f[0].summary}" if f else "Nothing actionable.")),
                domains=list(getattr(agent, "domains", ())),
                reasoned=bool(r and r.valid),
                thinking=_BRAIN.in_flight(name) or _JEVS.in_flight(name),
            ),
        )
    return {"findings": findings, "proposals": proposals, "trace": trace}


def consult(state: FarmState) -> dict:
    """ROUND 2 -- respond. Only agents actually addressed by an open thread are
    woken. This is what makes it a mesh rather than a fan-out: each agent is
    answering a specific question from a specific peer."""
    world = sensors.current().world
    board = world.board
    open_threads = board.open_threads()
    if not open_threads:
        return {"trace": [trace_event("orchestrator", "mesh",
                                      "No open questions on the board. Round 2 skipped.")]}

    responders: dict[str, list] = {}
    for m in open_threads:
        responders.setdefault(m.recipient, []).append(m)

    trace = [
        trace_event(
            "orchestrator", "mesh",
            f"{len(open_threads)} open thread(s); routing to "
            + ", ".join(f"{k} ({len(v)})" for k, v in responders.items()),
        )
    ]
    for name, inbox in responders.items():
        agent = AGENT_BY_NAME.get(name)
        if agent is None:
            continue
        CURRENT_AGENT.set(name)
        _f, _a = agent.respond(board, inbox)
        trace.append(
            trace_event(
                name, "respond",
                f"Answered {len(inbox)} message(s) from "
                + ", ".join(sorted({m.sender for m in inbox})),
            )
        )
    return {"trace": trace}


def deliberate(state: FarmState) -> dict:
    """The orchestrator's only judgement: did the swarm converge, and what is
    still contested? It routes and summarises -- it does not resolve technical
    disagreements between specialists."""
    board = sensors.current().world.board
    answered = {m.in_reply_to for m in board.messages if m.in_reply_to}
    unresolved = [m for m in board.messages if m.message_id not in answered and m.expects_reply]
    contested = board.contested()

    if not board.messages:
        state_line = "Board empty."
    elif unresolved:
        state_line = (
            f"{len(board.messages)} messages, {len(unresolved)} still unanswered "
            f"({', '.join(f'{m.sender}->{m.recipient}' for m in unresolved)})."
        )
    elif contested:
        state_line = f"{len(board.messages)} messages, {len(contested)} contested thread(s)."
    else:
        state_line = (
            f"{len(board.messages)} messages, all threads resolved -- swarm converged."
        )

    return {
        "orchestration": {
            "converged": not unresolved and not contested,
            "messages": len(board.messages),
            "unresolved": len(unresolved),
            "contested": len(contested),
            "unresolved_detail": [
                {"from": m.sender, "to": m.recipient, "kind": m.kind, "content": m.content}
                for m in unresolved
            ],
        },
        "trace": [
            trace_event("orchestrator", "deliberate", state_line,
                        converged=not unresolved and not contested,
                        messages=len(board.messages),
                        unresolved=len(unresolved),
                        contested=len(contested))
        ]
    }


def _batch(actions: list[Action]) -> list[Action]:
    """Merge same-action proposals into ONE compound decision.

    Six pivots at wilting point is one decision, not six. Asking the same
    question six times trains the director to approve reflexively, which
    defeats the whole point of human-in-the-loop.
    """
    out: list[Action] = []
    by_action: dict[str, list[Action]] = {}
    for a in actions:
        by_action.setdefault(a.action, []).append(a)

    for action, group in by_action.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        targets = sorted({t for a in group for t in a.target.split(",") if t})
        head = group[0]
        total_head = max(a.evidence.get("headcount_affected", 0) for a in group)
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
        "decision_log": [
            {
                **record,
                "action": top.action,
                "target": top.target,
                "approved": approved,
                "note": note,
                "sim_time": state.get("sim_time", ""),
                "risk": top.risk_score,
                "urgency": top.urgency_band(),
                "requested_by": top.requested_by,
            }
        ],
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
    g.add_node("deliberate", deliberate)
    g.add_node("gate", gate)
    g.add_node("execute", execute)
    g.add_node("human_gate", human_gate)
    g.add_node("done", done)

    g.add_edge(START, "sense")
    g.add_edge("sense", "triage")
    g.add_edge("triage", "wake")
    g.add_edge("wake", "consult")
    g.add_edge("consult", "deliberate")
    g.add_edge("deliberate", "gate")

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
    "ALL",
    "DOMAIN_TRIGGERS",
    "GRAPH",
    "IMPLICATION_ROUTES",
    "Action",
    "Command",
    "build_graph",
]