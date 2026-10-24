"""The persistent ledger.

The product's headline promise is that nothing consequential happens without a
person, and that every decision is written down where it can be read. Until now
that log was a Python list, trimmed to 25 entries for the UI and destroyed on
restart -- which is the difference between "auditable" and "auditable until the
process exits".

One SQLite file, no server, no dependencies. The same file will hold the
retrieval corpus and the agent chat history, so a single volume is all a
deployment needs.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_DEFAULT = Path(os.getenv("AIDUSTRIAL_DB", "data/aidustrial.db"))

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS decisions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            REAL NOT NULL,
    sim_time      TEXT,
    agent         TEXT,
    action        TEXT,
    target        TEXT,
    risk_score    REAL,
    urgency_score REAL,
    severity      TEXT,
    required_human INTEGER,
    gate_reason   TEXT,
    approved_by   TEXT,
    note          TEXT,
    rationale     TEXT,
    model         TEXT,
    sources       TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    sim_time  TEXT,
    agent     TEXT,
    kind      TEXT,
    severity  TEXT,
    summary   TEXT
);

CREATE TABLE IF NOT EXISTS work_orders (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL NOT NULL,
    sim_time TEXT,
    who      TEXT,
    status   TEXT,
    note     TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    agent   TEXT,
    role    TEXT,
    text    TEXT,
    sources TEXT
);

CREATE INDEX IF NOT EXISTS idx_decisions_agent ON decisions(agent, ts);
CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent, ts);
CREATE INDEX IF NOT EXISTS idx_chat_agent ON chat_messages(agent, ts);
"""

_lock = threading.Lock()
_path: Path = _DEFAULT


def configure(path: str | Path | None = None) -> Path:
    """Point the ledger at a file. Called once at startup."""
    global _path
    if path:
        _path = Path(path)
    _path.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.executescript(_SCHEMA)
    return _path


def path() -> Path:
    """The file the ledger, the corpus and the chat history share."""
    return _path


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_path), timeout=5.0, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _now() -> float:
    return time.time()


def record_decision(
    *,
    agent: str,
    action: str,
    target: str = "",
    risk_score: float = 0.0,
    urgency_score: float = 0.0,
    severity: str = "",
    required_human: bool = True,
    gate_reason: str = "",
    approved_by: str = "",
    note: str = "",
    rationale: str = "",
    model: str = "",
    sources: list[str] | None = None,
    sim_time: str = "",
) -> int:
    """Append one decision to the audit trail. Returns its row id."""
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO decisions
               (ts, sim_time, agent, action, target, risk_score, urgency_score,
                severity, required_human, gate_reason, approved_by, note,
                rationale, model, sources)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _now(), sim_time, agent, action, target, risk_score, urgency_score,
                severity, int(required_human), gate_reason, approved_by, note,
                rationale, model, json.dumps(sources or []),
            ),
        )
        return int(cur.lastrowid or 0)


def record_event(
    *,
    agent: str,
    kind: str,
    summary: str,
    severity: str = "info",
    sim_time: str = "",
) -> int:
    """Append a notable event -- a finding, an alarm, a lab result."""
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO events (ts, sim_time, agent, kind, severity, summary) VALUES (?,?,?,?,?,?)",
            (_now(), sim_time, agent, kind, severity, summary),
        )
        return int(cur.lastrowid or 0)


def open_work_order(*, who: str, note: str = "", sim_time: str = "") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO work_orders (ts, sim_time, who, status, note) VALUES (?,?,?,?,?)",
            (_now(), sim_time, who, "open", note),
        )
        return int(cur.lastrowid or 0)


def record_chat(*, agent: str, role: str, text: str, sources: list[str] | None = None) -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO chat_messages (ts, agent, role, text, sources) VALUES (?,?,?,?,?)",
            (_now(), agent, role, text, json.dumps(sources or [])),
        )
        return int(cur.lastrowid or 0)


def _rows(sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def recent_decisions(limit: int = 50, agent: str | None = None) -> list[dict[str, Any]]:
    if agent:
        rows = _rows("SELECT * FROM decisions WHERE agent=? ORDER BY id DESC LIMIT ?", (agent, limit))
    else:
        rows = _rows("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        try:
            r["sources"] = json.loads(r.get("sources") or "[]")
        except json.JSONDecodeError:
            r["sources"] = []
    return rows


def recent_events(limit: int = 50, agent: str | None = None) -> list[dict[str, Any]]:
    if agent:
        return _rows("SELECT * FROM events WHERE agent=? ORDER BY id DESC LIMIT ?", (agent, limit))
    return _rows("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))


def search_events(agent: str, terms: list[str], limit: int = 8) -> list[dict[str, Any]]:
    """Cheap keyword recall over one agent's history, for chat grounding."""
    if not terms:
        return recent_events(limit=limit, agent=agent)
    clause = " OR ".join("summary LIKE ?" for _ in terms)
    args = tuple(f"%{t}%" for t in terms) + (agent, limit)
    return _rows(
        f"SELECT * FROM events WHERE ({clause}) AND agent=? ORDER BY id DESC LIMIT ?", args
    )


def stats() -> dict[str, Any]:
    with _lock, _conn() as c:
        def n(table: str) -> int:
            return int(c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

        return {
            "path": str(_path),
            "decisions": n("decisions"),
            "events": n("events"),
            "work_orders": n("work_orders"),
            "chat_messages": n("chat_messages"),
        }


__all__ = [
    "configure",
    "open_work_order",
    "path",
    "recent_decisions",
    "recent_events",
    "record_chat",
    "record_decision",
    "record_event",
    "search_events",
    "stats",
]
