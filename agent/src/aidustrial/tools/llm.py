"""Layer 1.5 -- the reasoning brain.

An HTTP client that lets the seven agents actually *think* instead of only
applying thresholds, using a local `opencode serve` and the OpenCode Go
subscription (deepseek-v4.1-flash by default).

Two hard constraints shaped every decision in this file:

  1. LATENCY. A trivial call measured ~2-4s and a realistic agronomist
     reasoning call measured ~4s. The world ticks 12x/second. So the brain
     NEVER blocks a tick. `request()` is thread-safe and non-blocking: it
     stashes a payload, and a background asyncio task on the server's event
     loop drains it concurrently. The tick keeps running on rules meanwhile,
     and picks up the model's answer on a later pass.

  2. TRUST. A flash model is a fallible narrator, not an oracle. It is allowed
     to choose *whether* an action is warranted and *how urgent* it is. It is
     NEVER allowed to set the risk score -- risk is what decides whether a
     human is required, so it is always computed by our own deterministic
     `score_risk`. A model that could raise its own risk score could also
     lower it to slip past the gate. The model proposes; our scorer decides.

Anything the model returns is validated against the known action vocabulary.
An unrecognised action is dropped rather than passed through: a hallucinated
`dispatch_helicopter` must not reach the executor.

Disable the whole thing with `AIDUSTRIAL_LLM=off`. Either way the agents fall
back to their threshold rules and the demo is byte-for-byte the pre-LLM system.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

#: At most this many reasoning calls in flight at once. The model still
#: throttles, and 7 concurrent calls will trip it.
MAX_CONCURRENT = 3

#: How long a verdict stays fresh enough to reuse. The twin advances every tick
#: so the readings never repeat, which makes a content-hash cache useless -- the
#: key always differs. A cooldown is the honest answer: re-reason on this cadence
#: and treat the answer as current until then. At 14 ticks/s this is ~110 ticks
#: between calls per agent, which is what keeps us off the free tier's limits.
COOLDOWN_S = 22.0

#: Hard ceiling per call. Measured latency on the free tier runs 6-13s for a
#: real reasoning payload, so 14s was shedding a third of calls as ReadTimeout.
#: 24s rides out the slow tail while still well under anything that would stall
#: the dashboard -- the tick never blocks on this anyway.
CALL_TIMEOUT_S = 24.0

#: How many consecutive failures before we stop trying for a while.
BREAK_AFTER = 3
BREAK_COOLDOWN_S = 45.0

SEVERITIES = ("info", "low", "medium", "high", "critical")

#: Prose comes from a local `opencode serve`, on the OpenCode Go subscription.
#: Every previous provider here was an anonymous free tier, and all of them
#: eventually ration the same rolling 7-day pool to zero -- which left the
#: agents unable to explain themselves mid-demo. Routing through OpenCode instead
#: buys a real allowance, and because OpenCode's API is only reachable from an
#: OpenCode client, this local server *is* that client rather than a workaround.
ZEN_BASE = os.getenv("AIDUSTRIAL_ZEN_BASE", "http://127.0.0.1:4814")
ZEN_PORT = int(ZEN_BASE.rsplit(":", 1)[-1]) if ":" in ZEN_BASE else 4814
ZEN_PROVIDER = os.getenv("AIDUSTRIAL_ZEN_PROVIDER", "opencode-go")
ZEN_MODEL = os.getenv("AIDUSTRIAL_ZEN_MODEL", "deepseek-v4.1-flash")
#: A prose session that never touches files. The agents are reasoning about a
#: twin, not building software, so the coding tools must stay out of the way.
ZEN_SYSTEM = (
    "You are one specialist agent on an industrial control team. Reply with the "
    "answer only. Do not use tools. Do not read, write or list files. Do not plan "
    "or explain what you would do next."
)


def _enabled() -> bool:
    if os.getenv("AIDUSTRIAL_LLM", "").strip().lower() in {"off", "0", "false", "no"}:
        return False
    return bool(os.getenv("AIDUSTRIAL_ZEN_BASE", ZEN_BASE).strip())


class _Zen:
    """Client for a local `opencode serve`, used only when Token Harbor is dry.

    Each call gets its own session and deletes it afterwards. Reusing one would
    accumulate every prior turn into the prompt, so the ~8k token floor would
    grow without bound across a demo; a throwaway session keeps each call flat
    and stops one agent's context bleeding into another's answer.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    async def _ensure(self) -> None:
        if await self._healthy():
            return
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return
            try:
                self._proc = subprocess.Popen(
                    ["opencode", "serve", "--port", str(ZEN_PORT)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                raise RuntimeError("opencode CLI not found") from None
        for _ in range(40):
            await asyncio.sleep(0.5)
            if await self._healthy():
                return
        raise RuntimeError("opencode serve did not become healthy")

    async def _healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                return (await c.get(f"{ZEN_BASE}/health")).status_code == 200
        except Exception:  # noqa: BLE001 -- not up is the common case
            return False

    async def complete(self, system: str, user: str) -> str:
        await self._ensure()
        async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as c:
            created = await c.post(f"{ZEN_BASE}/session", json={"title": "prose"})
            created.raise_for_status()
            sid = created.json().get("id", "")
            try:
                resp = await c.post(
                    f"{ZEN_BASE}/session/{sid}/message",
                    json={
                        "model": {"providerID": ZEN_PROVIDER, "modelID": ZEN_MODEL},
                        "system": system,
                        "parts": [{"type": "text", "text": user}],
                    },
                )
                resp.raise_for_status()
                parts = resp.json().get("parts", [])
            finally:
                await c.delete(f"{ZEN_BASE}/session/{sid}", timeout=10.0)
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


_ZEN_CLIENT = _Zen()


@dataclass
class Reasoning:
    """One validated model verdict about an agent's slice of the site."""

    agent: str
    summary: str = ""
    severity: str = "info"
    confidence: float = 0.5
    implies: str = ""
    rationale: str = ""
    #: Action the model wants, already validated against the vocabulary.
    action: str = ""
    target: str = ""
    urgency: float = 50.0
    reversible: bool = True
    #: Content hash of the readings that produced this. Lets us skip re-calls.
    hash: str = ""
    ms: float = 0.0
    at_tick: int = 0
    model: str = ""

    @property
    def valid(self) -> bool:
        return bool(self.summary.strip())


@dataclass
class _Pending:
    payload: dict
    hash: str


class Brain:
    """Shared, thread-safe reasoning cache + async call loop.

    Callers in the graph (which runs in a worker thread via `asyncio.to_thread`)
    only ever touch `request()` and `get()`. Neither blocks. The event loop's
    `run()` owns all network I/O.
    """

    def __init__(self, allowed_actions: frozenset[str] | set[str] = frozenset()) -> None:
        self.allowed = frozenset(allowed_actions)
        self._pending: dict[str, _Pending] = {}
        self._results: dict[str, Reasoning] = {}
        #: Agents with a call currently on the wire. Kept separate from
        #: `_pending` on purpose: conflating "queued" with "in flight" (via a
        #: None sentinel) made `request()` refuse to queue anything that was
        #: not already running, so nothing was ever queued.
        self._inflight: set[str] = set()
        #: Wall-clock of each agent's most recent queued call, for cooldowns.
        self._last_call: dict[str, float] = {}
        self._lock = threading.Lock()
        self._sem: asyncio.Semaphore | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping = False
        self.calls = 0
        self.failures = 0
        self.cache_hits = 0
        self.dropped = 0
        self.last_ms = 0.0
        self.last_error = ""
        self.last_at = 0.0
        self._trip_at = 0.0
        self._consecutive = 0
        self.model = ZEN_MODEL
        #: Which model actually served the most recent verdict. Differs from
        #: `self.model` when `AIDUSTRIAL_ZEN_MODEL` is overridden.
        self.provider = ""

    # -- public, callable from the graph thread --------------------------

    @property
    def enabled(self) -> bool:
        return _enabled()

    def request(self, agent: str, payload: dict, state_hash: str) -> None:
        """Stash a reasoning request. Non-blocking, thread-safe, idempotent.

        Deduped two ways: never while a call is already queued or on the wire,
        and never within `COOLDOWN_S` of the last successful verdict. The
        cooldown is what does the real work -- the twin changes every tick, so
        a content hash alone would re-call once per tick per agent forever.
        """
        if not self.enabled:
            return
        with self._lock:
            if agent in self._inflight or agent in self._pending:
                return  # already queued or on the wire for this agent
            cached = self._results.get(agent)
            if cached and cached.valid:
                if cached.hash == state_hash:
                    self.cache_hits += 1
                    return
                if time.time() - self._last_call.get(agent, 0.0) < COOLDOWN_S:
                    self.cache_hits += 1
                    return  # recent enough; the verdict still stands
            self._pending[agent] = _Pending(payload=payload, hash=state_hash)
            self._last_call[agent] = time.time()

    def get(self, agent: str) -> Reasoning | None:
        """Latest validated verdict, or None if we have none / it is stale."""
        with self._lock:
            return self._results.get(agent)

    def in_flight(self, agent: str) -> bool:
        with self._lock:
            return agent in self._inflight

    def stats(self) -> dict:
        """Exposed on the snapshot so the UI can show the reasoning is real."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "model": self.model if self.enabled else "",
                "in_flight": len(self._inflight),
                "queued": len(self._pending),
                "calls": self.calls,
                "failures": self.failures,
                "cache_hits": self.cache_hits,
                "dropped_actions": self.dropped,
                "last_ms": round(self.last_ms, 1),
                "last_error": self.last_error,
                "last_at": self.last_at,
                "provider": self.provider,
                "agents_reasoned": sorted(k for k, v in self._results.items() if v.valid),
            }

    def reset(self) -> None:
        with self._lock:
            self._pending.clear()
            self._results.clear()
            self._inflight.clear()
            self._last_call.clear()

    # -- event loop side -------------------------------------------------

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def run(self) -> None:
        """Background drain. Lives for the life of the server."""
        self._stopping = False
        while not self._stopping:
            await asyncio.sleep(0.25)
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
                raw = await self._complete(pend.payload)
                r = self._parse(agent, raw, pend.hash)
                ms = (time.perf_counter() - t0) * 1000
                r.ms = ms
                with self._lock:
                    if r.valid:
                        self._results[agent] = r
                        self._consecutive = 0
                    self.last_ms = ms
                    self.last_at = time.time()
                    self.last_error = "" if r.valid else "empty verdict"
            except Exception as exc:  # noqa: BLE001 -- any failure must degrade
                self.failures += 1
                self._consecutive += 1
                self.last_error = f"{type(exc).__name__}: {exc}"[:180]
                if self._consecutive >= BREAK_AFTER:
                    self._trip_at = time.time() + BREAK_COOLDOWN_S
            finally:
                with self._lock:
                    self._inflight.discard(agent)

    async def _complete(self, payload: dict) -> str:
        if time.time() < self._trip_at:
            raise RuntimeError("circuit open after repeated failures")
        self.provider = ZEN_MODEL
        return await _ZEN_CLIENT.complete(ZEN_SYSTEM, payload["user"])

    # -- validation ------------------------------------------------------

    def _parse(self, agent: str, raw: str, state_hash: str) -> Reasoning:
        obj = _extract_json(raw)
        r = Reasoning(agent=agent, hash=state_hash, model=self.provider or self.model)
        if not isinstance(obj, dict):
            return r

        r.summary = str(obj.get("summary", ""))[:300]
        r.rationale = str(obj.get("rationale", ""))[:600]
        sev = str(obj.get("severity", "info")).strip().lower()
        r.severity = sev if sev in SEVERITIES else "info"
        r.confidence = _clamp(obj.get("confidence", 0.5), 0.0, 1.0)
        r.urgency = _clamp(obj.get("urgency", 50.0), 0.0, 100.0)
        r.reversible = bool(obj.get("reversible", True))

        # `implies` from a flash model is often prose. Only an exact vocabulary
        # hit counts; anything else is treated as "no action".
        cand = str(obj.get("action") or obj.get("implies") or "").strip().lower()
        cand = re.sub(r"[^a-z_]+", "_", cand).strip("_")
        if cand in self.allowed:
            r.action = cand
            r.implies = cand
            r.target = str(obj.get("target", ""))[:120]
        else:
            self.dropped += 1
            r.implies = ""
        return r


# --------------------------------------------------------------------------
# JSON extraction -- free models fence, ramble, and sometimes truncate.
# --------------------------------------------------------------------------


def _extract_json(text: str) -> Any:
    """Best-effort JSON pull, with a repair pass for truncated output."""
    if not text:
        return None
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Grab the outermost braces and retry.
    brace = re.search(r"\{.*\}", s, re.DOTALL)
    if brace:
        candidate = brace.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _repair_truncated(candidate)
            if repaired is not None:
                return repaired
    return None


def _repair_truncated(s: str) -> Any | None:
    """Close an object that ran out of tokens mid-string or mid-key.

    Free models routinely stop mid-word, and they stop just as often inside a
    KEY (`..."confid`) as inside a VALUE (`..."the pivot is degra`). The naive
    fix -- close an odd quote and strip a trailing comma-pair -- only handles
    the value case, so a truncated key returned None and the whole verdict was
    discarded.

    Instead, walk the string back one character at a time, closing the object
    each try, and return the longest prefix that parses. That recovers every
    complete key/value pair before the cut, which is exactly what we want: keep
    what the model finished, drop what it did not.
    """
    cut = s.rstrip()
    if cut.endswith("}"):
        try:
            return json.loads(cut)
        except json.JSONDecodeError:
            cut = cut[:-1].rstrip()

    # Try the full string first, with an unclosed string closed off.
    for candidate in (_close(cut), ):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Walk back to the last point where the object was still well-formed.
    for i in range(len(cut), max(0, len(cut) - 400), -1):
        prefix = cut[:i].rstrip().rstrip(",")
        if not prefix:
            break
        try:
            return json.loads(_close(prefix))
        except json.JSONDecodeError:
            continue
    return None


def _close(s: str) -> str:
    """Close an unterminated string, then any open object, then the root."""
    out = s.rstrip()
    if out.count('"') % 2 == 1:
        out += '"'
    # A trailing `:` with no value is not a valid pair; drop it.
    out = re.sub(r":\s*$", "", out)
    # A dangling `"key` with no colon is not a valid pair; drop it.
    out = re.sub(r',\s*"[^"]*$', "", out)
    depth = out.count("{") - out.count("}")
    return out + "}" * max(0, depth)


def _clamp(v: Any, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return lo


def hash_state(payload: dict) -> str:
    """Stable hash of a reasoning payload, for call-dedup."""
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


#: Module-level singleton. The orchestrator, the agents and the server all
#: reach the same instance.
BRAIN = Brain()


__all__ = [
    "BRAIN",
    "Brain",
    "Reasoning",
    "hash_state",
]
