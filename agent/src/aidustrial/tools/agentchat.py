"""Talk to one specialist about its own domain.

The agent answers from three places, in this order of trust:

  1. what it is reading *now* (the live domain slice),
  2. what it knows (retrieved corpus passages, with citations),
  3. what happened (its own events and decisions from the ledger).

When a prose model is available the three are composed into an answer. When it
is not -- the public demo runs with the reasoning tracks off -- the same three
are composed deterministically into a shorter answer. That matters: a chat that
only works with the author's API key would be the exact "works on my machine"
failure the brief warns about, so the fallback is a first-class path, not an
apology.
"""

from __future__ import annotations

import re
from typing import Any

from . import ledger, rag

#: How each specialist's live slice is read out of the site packet.
_SLICES: dict[str, tuple[str, ...]] = {
    "agronomist": ("environment", "crop_production"),
    "crop": ("environment", "crop_production"),
    "veterinarian": ("environment", "herd"),
    "maintenance": ("environment", "assets"),
    "logistics": ("logistics",),
    "milking": ("milk_production",),
    "calving": ("herd",),
}

_MANDATE: dict[str, str] = {
    "agronomist": "water allocation and irrigation across the site",
    "crop": "fodder crops, soil moisture and harvest timing",
    "veterinarian": "herd health, heat stress and animal welfare",
    "maintenance": "pivots, pumps, bearings and work orders",
    "logistics": "feed inventory, silos and the tanker cycle",
    "milking": "parlour throughput, bulk tank and milk quality",
    "calving": "calving, heifers and calf health",
}

_STOP = {
    "the", "and", "for", "was", "were", "what", "when", "why", "how", "did",
    "does", "you", "your", "are", "is", "it", "on", "in", "of", "to", "a",
    "an", "this", "that", "with", "about", "tell", "me", "there", "have",
}


def readings(agent: str, packet: dict | None = None) -> dict[str, Any]:
    """The agent's live slice, trimmed to something a prompt can hold."""
    if not packet:
        return {}
    keys = _SLICES.get(agent, ("environment",))
    out: dict[str, Any] = {}
    for k in keys:
        v = packet.get(k)
        if isinstance(v, dict):
            out[k] = {kk: vv for kk, vv in list(v.items())[:18]}
        elif isinstance(v, list):
            out[k] = v[:6]
    return out


def _terms(question: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9]+", question.lower()) if len(t) > 3 and t not in _STOP]


def gather(agent: str, question: str, packet: dict | None = None) -> dict[str, Any]:
    """Everything the answer will be built from, gathered in one place."""
    passages = rag.retrieve(agent, question, k=3)
    events = ledger.search_events(agent, _terms(question), limit=5)
    decisions = ledger.recent_decisions(limit=5, agent=agent)
    return {
        "agent": agent,
        "mandate": _MANDATE.get(agent, "site operations"),
        "question": question,
        "readings": readings(agent, packet),
        "passages": passages,
        "events": events,
        "decisions": decisions,
    }


def _cite(passages: list[dict]) -> list[str]:
    seen: list[str] = []
    for p in passages:
        if p["cite"] not in seen:
            seen.append(p["cite"])
    return seen


def deterministic(ctx: dict[str, Any]) -> str:
    """Compose an answer without a model. Terse, but grounded and correct."""
    lines: list[str] = []
    ev = ctx["events"]
    ps = ctx["passages"]

    if ev:
        e = ev[0]
        lines.append(f"Most recent on record: {e['summary']} ({e.get('sim_time') or 'recent'}).")
        if len(ev) > 1:
            lines.append(f"{len(ev) - 1} earlier event(s) for this domain are in the ledger.")
    else:
        lines.append("Nothing on this topic is in my event history yet.")

    if ps:
        p = ps[0]
        lines.append(f"{p['cite']}: {p['text']}")
    else:
        lines.append("I have no reference document matching that question.")

    auto = [d for d in ctx["decisions"] if d.get("approved_by") == "auto-policy"]
    if auto:
        d = auto[0]
        lines.append(
            f"I last acted without a human on {d['action']} ({d.get('target') or 'site-wide'}), "
            f"risk {d.get('risk_score', 0):.0f}."
        )
    return " ".join(lines)


def build_prompt(ctx: dict[str, Any]) -> tuple[str, str]:
    """The system and user messages handed to the prose model."""
    system = (
        f"You are the {ctx['agent']} agent on a dairy site in Adrar, Algeria. "
        f"Your mandate is {ctx['mandate']}. Answer the operator's question in at "
        "most four sentences, in the first person, using only the readings, the "
        "reference passages and the event history given below. If the evidence "
        "does not settle the question, say what you would need to know. Never "
        "invent a number. Never claim authority you do not have: anything that "
        "commits water, welfare or money goes to a human."
    )
    user = (
        f"CURRENT READINGS:\n{ctx['readings']}\n\n"
        f"REFERENCE PASSAGES:\n"
        + "\n".join(f"- [{p['cite']}] {p['text']}" for p in ctx["passages"])
        + "\n\nRECENT EVENTS:\n"
        + ("\n".join(f"- {e['summary']}" for e in ctx["events"]) or "- none")
        + f"\n\nOPERATOR QUESTION: {ctx['question']}"
    )
    return system, user


async def answer(agent: str, question: str, packet: dict | None = None) -> dict[str, Any]:
    """Answer a question, using the model when it is available."""
    from .llm import _ZEN_CLIENT, _enabled

    ctx = gather(agent, question, packet)
    used_model = False
    text = ""

    if _enabled():
        try:
            system, user = build_prompt(ctx)
            text = (await _ZEN_CLIENT.complete(system, user)).strip()
            used_model = bool(text)
        except Exception:  # noqa: BLE001 -- fall back, never fail the request
            used_model = False

    if not text:
        text = deterministic(ctx)

    sources = _cite(ctx["passages"])
    ledger.record_chat(agent=agent, role="user", text=question)
    ledger.record_chat(agent=agent, role="assistant", text=text, sources=sources)

    return {
        "agent": agent,
        "answer": text,
        "sources": sources,
        "grounded": {
            "events": len(ctx["events"]),
            "passages": len(ctx["passages"]),
            "readings": bool(ctx["readings"]),
        },
        "model": used_model,
    }


__all__ = ["answer", "build_prompt", "deterministic", "gather", "readings"]
