"""Layer 2 - THE MESH.

Agents do not merely fan out in parallel and get merged. They put claims on a
shared blackboard, challenge each other's claims, answer, and sometimes concede.
The orchestrator mediates but does not decide the technical argument -- it
routes messages and detects whether the swarm converged.

Why this matters for the demo: the interesting decisions in a facility like this
are not single-domain. "Turn on the misters" is a veterinarian's proposal, but
whether it is affordable is a logistics question, and whether the forage
programme can absorb the water cost is an agronomist's. Fan-out architecture
cannot express that; a message board can.

Message kinds, and what each obliges the recipient to do:
    QUESTION    -> answer with facts from your own domain
    OBJECTION   -> concede, defend with evidence, or counter-propose
    COUNTER     -> recipient must explicitly accept or reject
    ALERT       -> no reply required, but it seeds the recipient's next survey
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import asdict, dataclass

MsgKind = str


class Kind:
    QUESTION = "question"
    ANSWER = "answer"
    OBJECTION = "objection"
    CONCESSION = "concession"
    COUNTER = "counter"
    ALERT = "alert"
    ACCEPT = "accept"
    REJECT = "reject"


#: Kinds that oblige the recipient to respond this round.
REQUIRES_REPLY: frozenset[str] = frozenset(
    {Kind.QUESTION, Kind.OBJECTION, Kind.COUNTER}
)

#: Which agent owns which production area. The orchestrator uses this to route
#: a message to the only party that can actually answer it.
DOMAIN_OWNERS: dict[str, str] = {
    "crop": "crop",
    "irrigation": "crop",
    "soil": "crop",
    "forage": "crop",
    "livestock": "calving",
    "herd_health": "veterinarian",
    "heat": "veterinarian",
    "cooling": "veterinarian",
    "youngstock": "calving",
    "reproduction": "calving",
    "milk": "milking",
    "parlour": "milking",
    "quality": "milking",
    "cooling_chain": "milking",
    "powder": "milking",
    "assets": "maintenance",
    "maintenance": "maintenance",
    "feed": "logistics",
    "transport": "logistics",
    "airlift": "logistics",
    "water": "crop",
    "orchestrator": "orchestrator",
}


class Blackboard:
    """Shared board for one deliberation round."""

    def __init__(self) -> None:
        self.messages: list[Message] = []
        self._ids = itertools.count(1)

    def post(
        self,
        sender: str,
        kind: MsgKind,
        content: str,
        *,
        to: str | None = None,
        in_reply_to: str | None = None,
        severity: str = "info",
        evidence: dict | None = None,
        domains: Iterable[str] = (),
        expects_reply: bool | None = None,
    ) -> Message:
        mid = f"m{next(self._ids):03d}"
        if expects_reply is None:
            expects_reply = kind in REQUIRES_REPLY
        msg = Message(
            message_id=mid,
            kind=kind,
            sender=sender,
            recipient=to or "*",
            content=content,
            in_reply_to=in_reply_to,
            severity=severity,
            evidence=evidence or {},
            domains=list(domains),
            expects_reply=expects_reply,
        )
        self.messages.append(msg)
        return msg

    def inbox(self, agent: str) -> list[Message]:
        """Unanswered messages addressed to this agent."""
        answered = {m.in_reply_to for m in self.messages if m.in_reply_to}
        return [
            m
            for m in self.messages
            if m.recipient == agent and m.message_id not in answered and m.expects_reply
        ]

    def open_threads(self) -> list[Message]:
        answered = {m.in_reply_to for m in self.messages if m.in_reply_to}
        return [
            m for m in self.messages
            if m.message_id not in answered and m.expects_reply
        ]

    def thread(self, message_id: str) -> list[Message]:
        """The root plus every reply, in order."""
        out = [m for m in self.messages if m.message_id == message_id]
        frontier = [message_id]
        while True:
            children = [m for m in self.messages if m.in_reply_to in frontier]
            if not children:
                break
            out.extend(children)
            frontier = [c.message_id for c in children]
        return out

    def by_agent(self, agent: str) -> list[Message]:
        return [m for m in self.messages if m.sender == agent]

    def contested(self) -> list[list[Message]]:
        """Threads containing an objection or counter that has not been closed."""
        out = []
        for root in [m for m in self.messages if m.in_reply_to is None and m.expects_reply]:
            thread = self.thread(root.message_id)
            if (
                any(m.kind in (Kind.OBJECTION, Kind.COUNTER) for m in thread)
                and not any(m.kind in (Kind.ACCEPT, Kind.REJECT) for m in thread)
            ):
                out.append(thread)
        return out

    def to_dict(self) -> dict:
        return {"messages": [asdict(m) for m in self.messages]}


@dataclass
class Message:
    message_id: str
    kind: MsgKind
    sender: str
    recipient: str
    content: str
    in_reply_to: str | None
    severity: str
    evidence: dict
    domains: list[str]
    expects_reply: bool

    def label(self) -> str:
        arrow = "→" if self.recipient != "*" else "→*"
        return f"[{self.kind}] {self.sender} {arrow} {self.recipient}"

    def to_dict(self) -> dict:
        return asdict(self)


def route_to_agent(domains: Iterable[str]) -> list[str]:
    """Map the domains a message touches onto the agents that own them."""
    owners: list[str] = []
    for d in domains:
        owner = DOMAIN_OWNERS.get(d)
        if owner and owner not in owners:
            owners.append(owner)
    return owners


def digest(blackboard: Blackboard, limit: int = 6) -> str:
    """Compact view of the board, for injecting into an agent's prompt."""
    lines = [f"{m.sender} → {m.recipient}: {m.content}" for m in blackboard.messages[-limit:]]
    return " | ".join(lines) if lines else "(board empty)"


__all__ = [
    "DOMAIN_OWNERS",
    "REQUIRES_REPLY",
    "Blackboard",
    "Kind",
    "Message",
    "digest",
    "route_to_agent",
]