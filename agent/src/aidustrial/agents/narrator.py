"""The narrator -- a hidden eighth agent.

The seven visible agents each hold a narrow mandate and propose actions. The
narrator does something different and quieter: it watches the same simulated
physics and writes down what is happening, in language a non-industrial reader
can follow.

Why it exists. The digital twin produces numbers: soil moisture 6.1%, rumination
deficit 12%, bearing 81C. Those are true and they are also unreadable to anyone
who has not run a dairy. A judge looking at the dashboard should be able to read
a sentence and understand the situation without a glossary. That is the gap this
agent fills.

It is deliberately NOT one of the seven. It proposes nothing, gates nothing, and
never appears in the human decision queue. If it is wrong, the worst outcome is
an awkward sentence. That is the only kind of agent worth giving a free-form
language model.

Cadence. It runs on its own timer, roughly every `INTERVAL_S` seconds, entirely
off the graph tick. It reads the live packet, asks the model for a handful of
short observations, and appends them to a bounded ring the server streams out.
If the brain is disabled or the call fails, it simply produces nothing -- the
dashboard is unchanged.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field

from ..tools import sensors
from ..tools.llm import _enabled

#: Seconds between narrations. Slow on purpose: this is ambient colour, not a
#: decision feed, and every call competes with the seven agents for the free
#: tier's rate limit.
INTERVAL_S = 12.0

#: Bounded. An unbounded prose log in a long-running stream is a memory leak.
MAX_OBSERVATIONS = 40

_SYSTEM = """\
You are the site narrator for a simulated dairy farm dashboard. You watch the
same sensor readings the farm's specialist agents see, and you write short,
plain-language observations for a reader who knows nothing about dairy farming.

You have exactly three jobs:
  1. Describe what is actually happening right now, in one or two sentences.
  2. Translate jargon. "Rumination deficit 12%" becomes "the cows are chewing
     their cud noticeably less than they should, which is an early sign of heat
     stress."
  3. Flag what matters most, if anything. If the site is quiet, say so plainly
     -- do not manufacture drama.

Hard rules:
  - Every number you mention must appear in the readings you were given. Never
    invent a figure.
  - Never claim the telemetry is real-world data. It is a simulation.
  - Never propose an action. You observe; you do not decide.
  - Max two sentences per observation. Plain words. No bullet points.
  - Two or three observations total, most important first.

Respond with ONLY a JSON object, no prose, no markdown fences:
{"observations": ["<sentence>", "<sentence>"]}
"""


@dataclass
class Narrator:
    """Holds the narration ring and the timer state."""

    observations: deque[dict] = field(default_factory=lambda: deque(maxlen=MAX_OBSERVATIONS))
    calls: int = 0
    failures: int = 0
    last_ms: float = 0.0
    last_error: str = ""
    last_at: float = 0.0
    _task: asyncio.Task | None = None
    _stopping: bool = False

    # -- public ---------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return _enabled()

    def stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "calls": self.calls,
            "failures": self.failures,
            "last_ms": round(self.last_ms, 1),
            "last_at": self.last_at,
            "last_error": self.last_error,
            "observations": len(self.observations),
        }

    def recent(self, n: int = 8) -> list[dict]:
        return list(self.observations)[-n:]

    async def run(self) -> None:
        """Background loop. Owns its own cadence, never touches the graph."""
        self._stopping = False
        while not self._stopping:
            await asyncio.sleep(INTERVAL_S)
            if not self.enabled:
                continue
            if sensors.GW is None:
                continue
            try:
                t0 = time.perf_counter()
                obs = await self._narrate()
                self.calls += 1
                self.last_ms = (time.perf_counter() - t0) * 1000
                self.last_at = time.time()
                self.last_error = ""
                for text in obs:
                    self.observations.append(
                        {"at": sensors.GW.packet().get("time", ""), "text": text}
                    )
            except Exception as exc:  # noqa: BLE001 -- narration must never kill the server
                self.failures += 1
                self.last_error = f"{type(exc).__name__}: {exc}"[:160]

    def stop(self) -> None:
        self._stopping = True

    # -- internals ------------------------------------------------------

    async def _narrate(self) -> list[str]:
        from ..tools.llm import _ZEN_CLIENT

        if not _enabled():
            return []
        p = sensors.GW.packet() if sensors.GW else {}
        prompt = _build_user_prompt(p)
        raw = await _ZEN_CLIENT.complete(_SYSTEM, prompt)
        return _parse_observations(raw)


def _build_user_prompt(p: dict) -> str:
    """Compact the live packet down to what a narrator can actually use."""
    env = p.get("environment", {})
    herd = p.get("herd", {})
    logistics = p.get("logistics", {})
    crop = p.get("crop_production", {})
    milk = p.get("milk_production", {})
    events = [e.get("text", "") for e in (p.get("events") or [])[-3:]]

    return json.dumps(
        {
            "clock": {"time": p.get("time"), "day": p.get("day"), "phase": p.get("phase")},
            "weather": {
                "temperature_c": env.get("temperature_c"),
                "humidity_pct": env.get("relative_humidity_pct"),
                "heat_stress_band": env.get("heat_stress_band"),
                "effective_heat_load": env.get("effective_heat_load"),
            },
            "water": {
                "aquifer_used_pct": env.get("aquifer_budget_used_pct"),
                "status": env.get("aquifer_status"),
            },
            "herd": {
                "head": herd.get("head"),
                "rumination_deficit_pct": herd.get("rumination_deficit_pct"),
                "milk_loss_today_kg": herd.get("milk_loss_today_kg"),
            },
            "crops": {
                "standing_t": crop.get("standing_t"),
                "fields_wilting": sum(
                    1
                    for f in (crop.get("fields") or [])
                    if (f.get("soil_moisture_pct") or 100) <= 9.0
                ),
            },
            "feed": {"hours_of_cover": logistics.get("feed_hours_of_cover")},
            "milk": {
                "bulk_temp_c": milk.get("bulk_temp_c"),
                "bulk_scc_k": milk.get("bulk_scc_k"),
                "quality_status": milk.get("quality_status"),
            },
            "recent_scenario_events": events,
            "note": "SIMULATED telemetry. Never present it as real.",
        },
        default=str,
    )


def _parse_observations(raw: str) -> list[str]:
    from ..tools.llm import _extract_json

    obj = _extract_json(raw)
    if not isinstance(obj, dict):
        return []
    obs = obj.get("observations")
    if isinstance(obs, str):
        obs = [obs]
    if not isinstance(obs, list):
        return []
    return [str(o)[:300] for o in obs[:3] if str(o).strip()]


#: Module singleton, matching the brain.
NARRATOR = Narrator()

__all__ = ["NARRATOR", "Narrator"]
