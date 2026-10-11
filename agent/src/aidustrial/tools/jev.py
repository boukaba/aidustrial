"""Layer 1.6 -- the decision track.

`tools/llm.py` asks a free flash model to *write* what an agent sees. That is
good prose and bad plumbing: writing takes 12-66s, so a verdict lands a dozen
ticks after the readings that caused it.

Zen's Jev (SystemOne) answers a different kind of question. You give it typed
questions -- `noul` (yes/no), `choice` (pick from a list you supply) and `score`
(rate against a rubric) -- and it returns values *with probabilities*. Measured
against the free model above:

  Token Harbor flash   12-66s, 8,400 input tokens, prose -> JSON parse
  Jev free              ~0.85s,   400 input tokens, typed  -> no parsing

So the two tracks divide the work on their strengths:

  Jev   DECIDES.  Is this warranted? Which action? How urgent? How severe?
                  Fast enough to land on the same tick as the readings.
  flash WRITES.   The plain-language summary and rationale a judge reads.
                  Slow, and that is fine -- the tick never blocks on it.

Three properties make Jev safer than free-form text for a decision:

  - It cannot invent an action. We hand it `choice` criteria; it returns one of
    those strings or nothing. There is no post-hoc vocabulary filter to get
    wrong, because the set was closed before it answered.
  - It cannot write an action to risk. Risk still comes from `score_risk`.
  - Low confidence is visible. `probabilities` means we can refuse a 0.53 call
    instead of guessing whether 0.53 was meant confidently.

Disable with `AIDUSTRIAL_JEV=off`, or by removing `OPENCODE_API_KEY` and the
OpenCode auth file. Degradation is identical to the flash track: the rules run
regardless, and they are the floor.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

#: Zen's structured-decision endpoint. Documented on opencode.ai/docs/zen.
DEFAULT_URL = "https://opencode.ai/zen/v1/systemone"
DEFAULT_MODEL = "jev-1.13-free"

#: At most this many Jev calls in flight. Jev is cheap and fast, so this can be
#: higher than the flash track's cap without tripping anything.
MAX_CONCURRENT = 4

#: Re-reason on this cadence. Measured at ~0.85s and ~400 tokens per call, so a
#: short cooldown keeps decisions roughly in step with the world rather than
#: a full minute behind it. Deliberately shorter than llm.COOLDOWN_S.
COOLDOWN_S = 9.0

#: A measured 0.85s call; 8s rides out a bad tail without ever stalling a tick.
CALL_TIMEOUT_S = 8.0

BREAK_AFTER = 3
BREAK_COOLDOWN_S = 45.0

#: A `choice` is only believed above this probability. 0.65 is a real majority
#: over the alternatives without demanding certainty from a small model.
ACTION_FLOOR = 0.65

#: A `noul` (warranted?) must clear this to trigger anything at all.
WARRANT_FLOOR = 0.55

#: The score rubrics, in order. Jev returns the *index* the model picked, so
#: these are both the prompt and the decode table.
URGENCY_RUBRIC = ("routine", "soon", "now")
URGENCY_LEVELS = (20.0, 55.0, 90.0)
SEVERITY_RUBRIC = ("informational", "minor", "moderate", "serious", "critical")
SEVERITY_LEVELS = ("info", "low", "medium", "high", "critical")

#: The choice a caller always gets, so "do nothing" is an explicit option the
#: model must actively select rather than an absence we infer.
NO_ACTION = "no_action"


def _enabled() -> bool:
    if os.getenv("AIDUSTRIAL_JEV", "").strip().lower() in {"off", "0", "false", "no"}:
        return False
    return bool(_api_key())


def _api_key() -> str:
    """Zen key: explicit env var wins, else the OpenCode auth store.

    OpenCode's free tier refuses calls that are not made *from OpenCode*, which
    is why this is not a bare Token Harbor-style HTTP call. Routing through the
    user's own stored credential is the supported path.
    """
    key = os.getenv("OPENCODE_API_KEY", "").strip()
    if key:
        return key
    raw = os.getenv("OPENCODE_AUTH_PATH", "").strip()
    path = Path(raw) if raw else Path.home() / ".local" / "share" / "opencode" / "auth.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return ""
    if isinstance(data, dict) and isinstance(data.get("auth"), dict):
        data = data["auth"]
    for name in ("opencode-go", "opencode"):
        entry = data.get(name) if isinstance(data, dict) else None
        if isinstance(entry, dict) and entry.get("key"):
            return str(entry["key"]).strip()
    return ""


@dataclass
class Decision:
    """What Jev decided about one agent's slice, with the odds attached."""

    agent: str = ""
    #: Did the model say anything is warranted in the next ~15 minutes?
    warranted: bool = False
    #: Action name, already one of the `choice` criteria we offered.
    action: str = ""
    #: Probability the model attached to the action it picked.
    action_p: float = 0.0
    urgency: float = 20.0
    severity: str = "info"
    #: Overall confidence: how sure the model was about the action.
    confidence: float = 0.0
    #: Did the response contain at least one *informative* answer? A payload
    #: with `answers: {}` or an empty `action: {}` teaches us nothing, and
    #: treating it as a real verdict would let a malformed reply look like a
    #: confident "nothing to do".
    answered: bool = False
    ms: float = 0.0
    model: str = ""
    at_tick: int = 0

    @property
    def valid(self) -> bool:
        """True once a real, load-bearing answer has landed.

        A call that came back and said "not warranted, no action" is still a
        valid answer -- it is the model doing its job. A call that came back
        with an empty or unreadable body is not.
        """
        return bool(self.model) and self.answered

    @property
    def actionable(self) -> bool:
        """A decision worth merging into the agent's proposals."""
        return (
            self.valid
            and self.warranted
            and bool(self.action)
            and self.action != NO_ACTION
            and self.action_p >= ACTION_FLOOR
        )


@dataclass
class _Pending:
    payload: dict
    hash: str


class JevBrain:
    """Thread-safe decision queue with an async drain.

    Same shape as `llm.Brain`, deliberately separate: different endpoint,
    different payload, different timeouts, different trust rules. Sharing a
    class here would have meant two flags on one object and two ways for a
    call to be "not in flight".
    """

    def __init__(self, allowed_actions: frozenset[str] | set[str] = frozenset()) -> None:
        self.allowed = frozenset(allowed_actions)
        self._pending: dict[str, _Pending] = {}
        self._results: dict[str, Decision] = {}
        self._inflight: set[str] = set()
        self._last_call: dict[str, float] = {}
        self._lock = threading.Lock()
        self._sem: asyncio.Semaphore | None = None
        self._stopping = False
        self.calls = 0
        self.failures = 0
        self.cache_hits = 0
        self.rejected_low_confidence = 0
        self.last_ms = 0.0
        self.last_error = ""
        self._trip_at = 0.0
        self._consecutive = 0
        self.model = os.getenv("AIDUSTRIAL_JEV_MODEL", "").strip() or DEFAULT_MODEL
        self.base = os.getenv("AIDUSTRIAL_JEV_BASE", "").strip() or DEFAULT_URL

    # -- graph-thread side (never blocks) --------------------------------

    @property
    def enabled(self) -> bool:
        return _enabled()

    def request(self, agent: str, payload: dict, state_hash: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            if agent in self._inflight or agent in self._pending:
                return
            cached = self._results.get(agent)
            if cached and cached.valid and time.time() - self._last_call.get(agent, 0.0) < COOLDOWN_S:
                self.cache_hits += 1
                return
            self._pending[agent] = _Pending(payload=payload, hash=state_hash)
            self._last_call[agent] = time.time()

    def get(self, agent: str) -> Decision | None:
        with self._lock:
            return self._results.get(agent)

    def in_flight(self, agent: str) -> bool:
        with self._lock:
            return agent in self._inflight

    def stats(self) -> dict:
        with self._lock:
            decided = sorted(k for k, v in self._results.items() if v.valid)
            return {
                "enabled": self.enabled,
                "model": self.model if self.enabled else "",
                "endpoint": "zen/systemone" if self.enabled else "",
                "in_flight": len(self._inflight),
                "queued": len(self._pending),
                "calls": self.calls,
                "failures": self.failures,
                "cache_hits": self.cache_hits,
                "rejected_low_confidence": self.rejected_low_confidence,
                "last_ms": round(self.last_ms, 1),
                "last_error": self.last_error,
                "agents_decided": decided,
            }

    def reset(self) -> None:
        with self._lock:
            self._pending.clear()
            self._results.clear()
            self._inflight.clear()
            self._last_call.clear()

    # -- event-loop side -------------------------------------------------

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        del loop  # only used to keep the signature parallel with llm.Brain
        self._sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def run(self) -> None:
        self._stopping = False
        while not self._stopping:
            await asyncio.sleep(0.15)  # faster poll than the flash track
            with self._lock:
                batch = dict(self._pending)
                self._pending.clear()
                self._inflight.update(batch)
            if not batch:
                continue
            await asyncio.gather(
                *(self._one(name, pend) for name, pend in batch.items()),
                return_exceptions=True,
            )

    def stop(self) -> None:
        self._stopping = True

    async def _one(self, agent: str, pend: _Pending) -> None:
        assert self._sem is not None
        async with self._sem:
            t0 = time.perf_counter()
            self.calls += 1
            try:
                raw = await self._post(pend.payload)
                d = parse_decision(agent, raw, allowed=self.allowed, model=self.model)
                # A pick we refuse to act on is worth counting: it is the model
                # guessing, and hiding that would make the demo dishonest.
                if d.action and d.action_p < ACTION_FLOOR:
                    self.rejected_low_confidence += 1
                ms = (time.perf_counter() - t0) * 1000
                d.ms = ms
                with self._lock:
                    self._results[agent] = d
                    self._consecutive = 0
                    self.last_ms = ms
                    self.last_error = ""
            except Exception as exc:  # noqa: BLE001 -- degrade to rules
                self.failures += 1
                self._consecutive += 1
                self.last_error = f"{type(exc).__name__}: {exc}"[:180]
                if self._consecutive >= BREAK_AFTER:
                    self._trip_at = time.time() + BREAK_COOLDOWN_S
            finally:
                with self._lock:
                    self._inflight.discard(agent)

    async def _post(self, payload: dict) -> dict:
        if time.time() < self._trip_at:
            raise RuntimeError("circuit open after repeated failures")
        key = _api_key()
        if not key:
            raise RuntimeError("no OpenCode credential available")
        async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as client:
            resp = await client.post(
                self.base,
                json=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()


#: How long we ask the model to look ahead when judging urgency.
LOOKAHEAD = "the next 15 minutes"


def parse_decision(
    agent: str,
    raw: dict,
    allowed: frozenset[str] | set[str] = frozenset(),
    model: str = DEFAULT_MODEL,
) -> Decision:
    """Decode a SystemOne response into a `Decision`.

    Kept as a module-level function (not a method) so tests can drive it with a
    hand-written payload and never touch the network. `allowed` is passed in
    rather than read off the singleton for the same reason.
    """
    vocab = frozenset(allowed)
    d = Decision(agent=agent, model=model)
    answers = raw.get("answers") if isinstance(raw, dict) else None
    if not isinstance(answers, dict):
        return d

    warrant = answers.get("warranted")
    if isinstance(warrant, dict) and "noul" in warrant:
        d.answered = True
        d.warranted = _num(warrant.get("noul")) >= WARRANT_FLOOR

    action = answers.get("action")
    if isinstance(action, dict) and "choice" in action:
        d.answered = True
        choice = str(action.get("choice") or "").strip().lower()
        probs = action.get("probabilities")
        probs = probs if isinstance(probs, dict) else {}
        if choice in vocab:
            # Closed set: this string came from the criteria WE supplied, so
            # there is nothing to filter or normalise after the fact.
            d.action = choice
            d.action_p = _num(probs.get(choice))
            d.confidence = d.action_p
        # `no_action` (or anything unrecognised, which cannot happen) leaves
        # d.action empty: the model chose to do nothing.

    urg = answers.get("urgency")
    if isinstance(urg, dict) and "score" in urg:
        d.answered = True
        idx = int(_num(urg.get("score")))
        idx = max(0, min(idx, len(URGENCY_LEVELS) - 1))
        d.urgency = URGENCY_LEVELS[idx]

    sev = answers.get("severity")
    if isinstance(sev, dict) and "score" in sev:
        d.answered = True
        idx = int(_num(sev.get("score")))
        idx = max(0, min(idx, len(SEVERITY_LEVELS) - 1))
        d.severity = SEVERITY_LEVELS[idx]

    return d


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


#: Module-level singleton, matching `llm.BRAIN`.
JEVS = JevBrain()


__all__ = [
    "ACTION_FLOOR",
    "JEVS",
    "NO_ACTION",
    "Decision",
    "JevBrain",
    "parse_decision",
]

