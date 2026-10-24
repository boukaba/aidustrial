"""Layer 3.5 - FastAPI + WebSocket bridge.

One session per thread. The graph runs against a live twin held by the session,
not by LangGraph state, so the checkpointer only ever sees plain data.

Two channels to the dashboard:
  WS  /ws/stream   -- continuous telemetry + agent trace, pushed as it happens
  POST /decide     -- the Farm Director's verdict, which resumes the thread
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from ..agents.narrator import NARRATOR
from ..graph.orchestrator import ALL as ALL_MESH
from ..graph.orchestrator import GRAPH
from ..tools import ledger, sensors
from ..tools.jev import JEVS
from ..tools.llm import BRAIN
from ..twin import constants as C
from ..twin import policy
from ..twin.world import World

app = FastAPI(title="aidustrial", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_compiled = GRAPH.compile(checkpointer=MemorySaver())
_brain_task: asyncio.Task | None = None
_jev_task: asyncio.Task | None = None
_narrator_task: asyncio.Task | None = None


@app.on_event("startup")
async def _start_brain() -> None:
    """Run both reasoning drain loops and the narrator on the event loop.

    Reasoning never blocks a graph tick: the graph stashes payloads, these
    loops drain them concurrently, and ticks pick up verdicts on later passes.
    The decision track (Jev) polls faster than the prose track because it is
    ~15x cheaper per call and is the one that decides what to *do*. The
    narrator runs on its own slower cadence and is purely decorative prose.
    """
    global _brain_task, _jev_task, _narrator_task
    # The audit trail must outlive the process, so it is opened before anything
    # can record into it.
    ledger.configure()
    loop = asyncio.get_running_loop()
    BRAIN.bind_loop(loop)
    JEVS.bind_loop(loop)
    _brain_task = asyncio.create_task(BRAIN.run())
    _jev_task = asyncio.create_task(JEVS.run())
    _narrator_task = asyncio.create_task(NARRATOR.run())


@app.on_event("shutdown")
async def _stop_brain() -> None:
    BRAIN.stop()
    JEVS.stop()
    NARRATOR.stop()
    for task in (_brain_task, _jev_task, _narrator_task):
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

@dataclass
class Session:
    """One farm run: twin + graph thread + pending decision."""

    thread_id: str
    world: World
    speed: float = 12.0  # ticks per second
    running: bool = True
    trace: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    pending: dict | None = None
    findings: list[dict] = field(default_factory=list)
    subscribers: set[WebSocket] = field(default_factory=set)
    last_push: float = 0.0
    awaiting_decision: bool = False
    orchestration: dict = field(default_factory=dict)
    decision_log: list[dict] = field(default_factory=list)
    #: The graph returns its whole append-only decision log on every resume.
    #: Track how much of it the session has already copied so the audit trail
    #: does not show the same verdict three times.
    decision_log_seen: int = 0
    auto_executed: list[dict] = field(default_factory=list)
    auto_executed_seen: int = 0
    dispatch_log: list[dict] = field(default_factory=list)

    def snapshot(self) -> dict:
        p = self.world.observe()
        return {
            "type": "telemetry",
            "thread": self.thread_id,
            "packet": p,
            "summary": self._summary(p),
            "pending": self.pending,
            "findings": self.findings[-14:],
            "trace": self.trace[-60:],
            "awaiting_decision": self.awaiting_decision,
            "activity": sensors.GW.activity(),
            "mesh": self._mesh(p),
            # A session that has not run a graph tick yet must still emit a
            # well-formed payload -- the panel reads these keys unconditionally.
            "orchestration": self.orchestration
            or {
                "converged": True,
                "messages": 0,
                "unresolved": 0,
                "contested": 0,
                "unresolved_detail": [],
            },
            "decision_log": self.decision_log[-25:],
            "auto_executed": self.auto_executed[-15:],
            # Proof the agents are reasoning rather than only applying
            # thresholds: model, call counts, latency, and which agents have a
            # live verdict. Empty when the brain is disabled.
            "llm": BRAIN.stats(),
            # The decision track. Separate from `llm` because it is a different
            # model answering a different kind of question: typed decisions with
            # probabilities, rather than prose. ~0.85s vs 12-66s.
            "decision": JEVS.stats(),
            # The hidden eighth agent: plain-language narration of the site.
            "narration": {"stats": NARRATOR.stats(), "recent": NARRATOR.recent(6)},
            "project": {
                "name": C.PROJECT,
                "location": C.LOCATION,
                "operator": C.OPERATOR,
                "state_partner": C.STATE_PARTNER,
                "ownership": f"{C.OWNERSHIP_SPLIT[0]}/{C.OWNERSHIP_SPLIT[1]}",
                "aquifer": C.AQUIFER_KIND,
            },
        }

    def _mesh(self, p: dict) -> dict:
        """Per-agent live state: what it reads, what it is doing, what it decided.

        This is the answer to "is anything actually thinking?". Each agent
        reports its own live readings straight from the sensors, its latest
        finding, and where its proposal currently sits in the mesh. Nothing
        here is precomputed -- it is rebuilt on every push.
        """
        act = {a["agent"]: a for a in sensors.GW.activity()["agents"]}
        findings: dict[str, dict] = {}
        for f in self.findings:
            findings[f.get("agent", "")] = f
        msgs = p.get("board") or []
        answered = {m.get("in_reply_to") for m in msgs if m.get("in_reply_to")}

        agents: list[dict] = []
        for a in ALL_MESH:
            name = a.name
            live = act.get(name, {})
            rows = a.watch()
            worst = "stop" if any(r["status"] == "stop" for r in rows) else (
                "act" if any(r["status"] == "act" for r in rows) else "ok"
            )
            f = findings.get(name, {})
            # A proposal is "live" once raised and not yet answered on the board.
            mine = [m for m in msgs if m.get("sender") == name]
            open_q = [m for m in mine if m.get("expects_reply") and m.get("message_id") not in answered]
            r = BRAIN.get(name)
            j = JEVS.get(name)
            agents.append({
                "agent": name,
                "readings": rows,
                "worst": worst,
                "state": live.get("state", "idle"),
                "calls": live.get("calls", 0),
                "last_tool": live.get("last_tool", ""),
                "last_summary": live.get("last_summary", ""),
                "last_ms": live.get("last_ms", 0),
                "finding": f.get("summary", ""),
                "severity": f.get("severity", "info"),
                "confidence": f.get("confidence", 0),
                "implies": f.get("implies", ""),
                "messages": len(mine),
                "open_questions": len(open_q),
                "awaiting_reply": bool(open_q),
                # Live reasoning state. `thinking` drives the spinner;
                # `rationale` is the model's own plain-language explanation.
                "thinking": BRAIN.in_flight(name) or JEVS.in_flight(name),
                "reasoned": bool(r and r.valid),
                "reasoned_ms": round(r.ms, 1) if r else 0,
                "rationale": (r.rationale if r and r.valid else ""),
                "reasoned_by": (r.model if r and r.valid else ""),
                # The decision track: did this agent decide anything, how sure
                # was it, and how fast. Jev is the one that may propose actions.
                "decided": bool(j and j.valid),
                "decided_ms": round(j.ms, 1) if j else 0,
                "decided_by": (j.model if j and j.valid else ""),
                "warranted": bool(j and j.valid and j.warranted),
                "action_p": round(j.action_p, 2) if j else 0.0,
            })

        return {
            "agents": agents,
            "messages": len(msgs),
            "unresolved": len([m for m in msgs if m.get("expects_reply") and m.get("message_id") not in answered]),
            "feed": msgs[-14:],
            "converged": self.orchestration.get("converged", True) if self.orchestration else True,
            "summary": self.orchestration.get("summary", "") if self.orchestration else "",
        }

    @staticmethod
    def _summary(p: dict) -> dict:
        e, h, l = p["environment"], p["herd"], p["logistics"]
        return {
            "sim_time": p["time"],
            "day": p["day"],
            "hour": p["hour"],
            "phase": p["phase"],
            "temperature_c": e["temperature_c"],
            "thi_air": e["thi_air"],
            "effective_heat_load": e["effective_heat_load"],
            "heat_stress_band": e["heat_stress_band"],
            "aquifer_pct": e["aquifer_budget_used_pct"],
            "aquifer_status": e["aquifer_status"],
            "herd_head": h["head"],
            "rumination_deficit": h["rumination_deficit_pct"],
            "milk_loss_kg": h["milk_loss_today_kg"],
            "feed_hours": l["feed_hours_of_cover"],
            "airlift_delivered": l["airlift"]["delivered"],
            "airlift_target": l["airlift"]["target"],
            "crop_standing_t": p["crop_production"]["standing_t"],
            "crop_fields_wilting": sum(
                1 for f in p["crop_production"]["fields"]
                if f["soil_moisture_pct"] <= 9
            ),
            "non_productive_head": p["livestock"]["non_productive_head"],
            "total_head": p["livestock"]["total_head"],
            "milk_t_day": p["milk_production"]["daily_milk_kg"] / 1000,
            "bulk_scc_k": p["milk_production"]["bulk_scc_k"],
            "mesh_messages": len(p.get("board") or []),
        }

    def push_trace(self, events: list[dict]) -> None:
        for e in events:
            self.trace.append({**e, "wall": time.time()})


SESSIONS: dict[str, Session] = {}


#: Open the demo three days in. Days 0-2 are a quiet baseline; the pump failure
#: lands on day 3 and the heatwave on days 4-6. A judge watching five minutes
#: should land inside the scenario, not spend it watching nothing happen.
DEMO_WARMUP_TICKS = (3 * 48) + 24


def get_session(thread_id: str, speed: float = 12.0) -> Session:
    if thread_id not in SESSIONS:
        world = World()
        for _ in range(DEMO_WARMUP_TICKS):
            world.step()
        sensors.bind(world)
        SESSIONS[thread_id] = Session(thread_id=thread_id, world=world, speed=speed)
    return SESSIONS[thread_id]


# ---------------------------------------------------------------------------
# Graph driver
# ---------------------------------------------------------------------------




async def drive(session: Session, approved: dict | None = None) -> None:
    """Advance the graph one tick (or resume it after a decision)."""
    cfg = {"configurable": {"thread_id": session.thread_id}}

    try:
        if approved is not None:
            out = await asyncio.to_thread(
                _compiled.invoke,
                Command(resume=approved),
                cfg,
            )
        else:
            out = await asyncio.to_thread(
                _compiled.invoke, {"max_turns": 1, "turn": 0}, cfg
            )
    except Exception as exc:  # noqa: BLE001
        session.trace.append(
            {"agent": "system", "phase": "error", "message": f"Graph error: {exc}"}
        )
        session.awaiting_decision = False
        return

    session.push_trace(out.get("trace") or [])
    if out.get("orchestration"):
        session.orchestration = out["orchestration"]
    if out.get("dispatched"):
        session.dispatch_log.append(
            {
                "tick": out.get("tick", 0),
                "dispatched": out["dispatched"],
                "reasons": out.get("dispatch_reasons", []),
                "escalation": out.get("escalation", "none"),
            }
        )
    session.findings = [
        f.to_dict() for f in (out.get("findings") or [])
    ][-14:]
    auto_log = [
        e for e in (out.get("executed") or [])
        if e.get("approved_by") == "auto-policy"
    ]
    if len(auto_log) < session.auto_executed_seen:
        session.auto_executed_seen = 0
    session.auto_executed.extend(auto_log[session.auto_executed_seen:])
    session.auto_executed_seen = len(auto_log)
    session.auto_executed = session.auto_executed[-15:]

    graph_log = out.get("decision_log") or []
    if len(graph_log) < session.decision_log_seen:
        # The checkpoint was reset; start copying from the beginning again.
        session.decision_log_seen = 0
    for entry in graph_log[session.decision_log_seen:]:
        session.decision_log.append(entry)
    session.decision_log_seen = len(graph_log)

    it = out.get("__interrupt__")
    payload = it[0].value if it else None
    if payload:
        session.pending = payload
        session.awaiting_decision = True
    else:
        session.pending = None
        session.awaiting_decision = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "agents": [a.name for a in ALL_MESH],
        "sessions": len(SESSIONS),
        "provenance": C.provenance,
    }


@app.get("/api/site/{thread_id}")
async def site(thread_id: str, speed: float = 12.0) -> dict:
    s = get_session(thread_id, speed)
    return s.snapshot()


@app.post("/api/session/{thread_id}/speed")
async def set_speed(thread_id: str, body: dict) -> dict:
    s = get_session(thread_id)
    s.speed = max(1.0, min(60.0, float(body.get("speed", 12.0))))
    return {"speed": s.speed}


@app.post("/api/session/{thread_id}/pause")
async def pause(thread_id: str) -> dict:
    s = get_session(thread_id)
    s.running = not s.running
    return {"running": s.running}


@app.post("/api/decide/{thread_id}")
async def decide(thread_id: str, body: dict) -> dict:
    """The Farm Director's verdict. Resumes the suspended graph."""
    s = get_session(thread_id)
    if not s.awaiting_decision:
        return {"error": "no decision pending"}

    pending = s.pending or {}
    action = pending.get("action") or {}
    approved = bool(body.get("approved"))
    note = str(body.get("note", ""))

    gate_reason = "human gate"
    try:
        from ..tools.actions import Action

        fields = {k: v for k, v in action.items() if k in Action.__dataclass_fields__}
        gate_reason = Action(**fields).gate_reason()
    except Exception:  # noqa: BLE001, S110 -- the ledger must never block a verdict
        pass

    # Write the verdict BEFORE resuming, so a crash mid-resume still leaves the
    # decision on record. An audit log that can lose the entry it was created
    # to keep is not an audit log.
    ledger.record_decision(
        agent=str(action.get("requested_by", "")),
        action=str(action.get("action", "")),
        target=str(action.get("target", "")),
        risk_score=float(action.get("risk_score", 0) or 0),
        urgency_score=float(action.get("urgency_score", 0) or 0),
        severity=str(action.get("severity", "")),
        required_human=True,
        gate_reason=gate_reason,
        approved_by="human" if approved else "rejected",
        note=note,
        rationale=str(action.get("rationale", "")),
        sim_time=str(pending.get("sim_time", "")),
    )

    await drive(
        s,
        approved={
            "approved": approved,
            "note": note,
        },
    )
    await broadcast(s)
    return {"ok": True, "awaiting_decision": s.awaiting_decision, "pending": s.pending}


@app.get("/api/ledger")
async def ledger_view(limit: int = 50, agent: str | None = None) -> dict:
    """The audit trail, readable and persistent.

    This is the endpoint that makes the product's promise checkable: every
    decision that ever reached a human, who answered it, and why it was gated.
    """
    return {
        "stats": ledger.stats(),
        "decisions": ledger.recent_decisions(limit=limit, agent=agent),
        "events": ledger.recent_events(limit=limit, agent=agent),
        "policy": policy.describe(),
    }


async def broadcast(session: Session) -> None:
    if not session.subscribers:
        return
    msg = json.dumps(session.snapshot(), default=str)
    dead: list[WebSocket] = []
    for ws in list(session.subscribers):
        try:
            await ws.send_text(msg)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        session.subscribers.discard(ws)


@app.websocket("/ws/stream")
async def stream(ws: WebSocket, thread_id: str = "demo", speed: float = 12.0) -> None:
    await ws.accept()
    session = get_session(thread_id, speed)
    session.subscribers.add(ws)

    await ws.send_text(json.dumps(session.snapshot(), default=str))
    last_graph = 0.0

    try:
        while True:
            if not session.running:
                await asyncio.sleep(0.2)
                continue

            interval = 1.0 / session.speed
            now = time.time()

            # Only drive the graph when the previous turn cleared its gate.
            # If a human decision is outstanding the world pauses at the gate --
            # the correct behaviour for an agentic ops system.
            if not session.awaiting_decision and now - last_graph > interval:
                last_graph = now
                await drive(session)
                if not session.subscribers:
                    await asyncio.sleep(interval)
                    continue

            await asyncio.sleep(interval)
            if now - session.last_push > 0.45:
                session.last_push = now
                with contextlib.suppress(Exception):
                    await broadcast(session)
    except WebSocketDisconnect:
        pass
    finally:
        session.subscribers.discard(ws)


# ---------------------------------------------------------------------------
# Static dashboard (single-container deployment)
# ---------------------------------------------------------------------------

#: The Docker image builds the Next.js dashboard into `/app/static`. Locally
#: this directory does not exist, so the API runs on its own and the dashboard
#: is served by `next dev` on :3010. Mounting after the API/WebSocket routes
#: means it never shadows them.
_STATIC_DIR = Path(
    os.getenv(
        "AIDUSTRIAL_STATIC_DIR",
        str(Path(__file__).resolve().parents[3] / "static"),
    )
)
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="dashboard")
