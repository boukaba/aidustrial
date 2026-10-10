"""Layer 1 - Sensory Cortex: the tool surface.

These are the ONLY way agents perceive the facility. An agent never touches the
twin internals; it calls a tool and gets a dictionary back. That boundary is
what makes the eventual swap from digital twin to real vendor APIs a one-file
change rather than a rewrite.

The split mirrors the four sensory domains named in the architecture:
    telemetry  -> water pH, soil moisture, Adrar temperatures
    veterinary -> smart-collar vitals, rumination, milk yield
    assets     -> pivot/motor telemetry, well yield
    logistics  -> silo levels, tanker GPS, airlift schedule
"""

from __future__ import annotations

import contextvars
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from ..twin import constants as C
from ..twin.world import World

#: Which agent is currently running. Agents call tools synchronously, so a
#: context variable is the least invasive way to attribute every call to the
#: agent that made it -- and it means the log is real telemetry rather than a
#: narrative written after the fact.
CURRENT_AGENT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_agent", default="orchestrator"
)


@dataclass
class ToolCall:
    seq: int
    agent: str
    tool: str
    args: str
    tick: int
    ms: float
    ok: bool
    summary: str


class SensorGateway:
    """Read-only facade over the twin. Shared by every tool below."""

    def __init__(self, world: World) -> None:
        self.world = world
        #: Bounded ring of tool calls. Bounded because an unbounded log in a
        #: long-running stream is a memory leak dressed as a feature.
        self.calls: deque[ToolCall] = deque(maxlen=400)
        self._seq = 0
        self.by_agent: dict[str, int] = {}
        self.active: dict[str, str] = {}
        self.last_result: dict[str, Any] = {}

    def packet(self) -> dict:
        return self.world.observe()

    # -- call instrumentation --------------------------------------------

    def record(self, tool: str, args: str, fn, *a, **kw):
        agent = CURRENT_AGENT.get()
        self._seq += 1
        t0 = time.perf_counter()
        try:
            out = fn(*a, **kw)
            ok = True
        except Exception as exc:  # noqa: BLE001
            out = {"error": str(exc)}
            ok = False
        ms = (time.perf_counter() - t0) * 1000
        self.calls.append(
            ToolCall(
                seq=self._seq,
                agent=agent,
                tool=tool,
                args=args,
                tick=self.world.env.clock.tick,
                ms=ms,
                ok=ok,
                summary=summarise(tool, out),
            )
        )
        self.by_agent[agent] = self.by_agent.get(agent, 0) + 1
        self.active[agent] = tool
        self.last_result[f"{agent}:{tool}"] = out
        return out

    def activity(self) -> dict:
        """Per-agent live state for the control panel.

        `state` reflects what the agent is doing *right now*, not what it did
        once. A call older than the last tick means the agent has gone quiet, so
        it reads as idle rather than permanently busy.
        """
        now_tick = self.world.env.clock.tick
        agents: dict[str, dict] = {}
        for c in reversed(self.calls):
            a = agents.setdefault(
                c.agent,
                {
                    "agent": c.agent,
                    "calls": 0,
                    "last_tool": c.tool,
                    "last_args": c.args,
                    "last_ms": round(c.ms, 2),
                    "last_ok": c.ok,
                    "last_summary": c.summary,
                    "last_tick": c.tick,
                    "state": "idle",
                    "recent": [],
                },
            )
            a["calls"] += 1
            if c.tool not in a["recent"] and len(a["recent"]) < 6:
                a["recent"].append(c.tool)
            # newest call comes first because we iterate reversed
            a["last_tool"] = c.tool
            a["last_summary"] = c.summary
            a["last_ms"] = round(c.ms, 2)
            a["last_ok"] = c.ok
            a["last_tick"] = c.tick
        # a tool call from this tick or the last one still counts as "at work"
        for a in agents.values():
            a["state"] = "reading" if now_tick - a["last_tick"] <= 1 else "idle"
        for name, total in self.by_agent.items():
            if name in agents:
                agents[name]["total_calls"] = total
        return {
            "agents": list(agents.values()),
            "recent_calls": [
                {
                    "seq": c.seq,
                    "agent": c.agent,
                    "tool": c.tool,
                    "args": c.args,
                    "tick": c.tick,
                    "ms": round(c.ms, 2),
                    "ok": c.ok,
                    "summary": c.summary,
                }
                for c in list(self.calls)[-40:]
            ],
        }

    def step(self) -> dict:
        """Advance the simulation. Only the graph's `sense` node may call this."""
        self.world.step()
        return self.world.observe()

    # -- telemetry -------------------------------------------------------

    def environment(self) -> dict:
        return self.packet()["environment"]

    def pivot_telemetry(self) -> list[dict]:
        return self.packet()["environment"]["pivots"]

    def water_status(self) -> dict:
        e = self.environment()
        return {
            "aquifer_status": e["aquifer_status"],
            "budget_used_pct": e["aquifer_budget_used_pct"],
            "projected_annual_m3h": e["aquifer_projected_annual_m3h"],
            "annual_budget_m3": C.WATER_M3_FULL_ANNUAL,
            "water_use_m3h": e["water_use_m3h"],
            "misters_on": e["misters_on"],
            "aquifer_kind": C.AQUIFER_KIND,
        }

    # -- veterinary ------------------------------------------------------

    def herd(self) -> dict:
        return self.packet()["herd"]

    def group(self, name: str) -> dict | None:
        return next((g for g in self.herd()["groups"] if g["name"] == name), None)

    def barns_without_cooling(self) -> list[str]:
        return [g["name"] for g in self.herd()["groups"] if not g["misters_available"]]

    # -- assets ----------------------------------------------------------

    def asset_health(self) -> list[dict]:
        return self.pivot_telemetry()

    def degraded_assets(self) -> list[dict]:
        return [p for p in self.pivot_telemetry() if p["health"] != "nominal"]

    # -- logistics -------------------------------------------------------

    def logistics(self) -> dict:
        return self.packet()["logistics"]

    def critical_silos(self) -> list[dict]:
        return [s for s in self.logistics()["silos"] if s["status"] == "critical"]

    def airlift(self) -> dict:
        return self.logistics()["airlift"]


# ---------------------------------------------------------------------------
# Tool functions. Thin on purpose -- the value is in the contract, not the body.
# ---------------------------------------------------------------------------

def summarise(tool: str, out: Any) -> str:
    """One-line digest of a tool result, for the live activity feed."""
    try:
        if isinstance(out, list):
            return f"{len(out)} row(s)"
        if not isinstance(out, dict):
            return str(out)[:70]
        if "standing_t" in out:
            return f"{out['standing_t']:.0f} t standing, {len(out.get('fields', []))} fields"
        if "non_productive_head" in out:
            return f"{out['total_head']:,} head, {out['non_productive_head']:,} non-productive"
        if "daily_milk_kg" in out:
            return f"{out['daily_milk_kg'] / 1000:.0f} t/d, SCC {out.get('bulk_scc_k', 0):.0f}k"
        if "budget_used_pct" in out:
            return f"aquifer {out['budget_used_pct']:.0f}% of envelope"
        if "effective_heat_load" in out:
            return f"EHL {out['effective_heat_load']:.0f} ({out.get('heat_stress_band')})"
        if "rumination_deficit_pct" in out:
            return f"rumination -{out['rumination_deficit_pct']:.1f}%"
        if "feed_hours_of_cover" in out:
            return f"feed cover {out['feed_hours_of_cover']:.0f}h"
        if "pivots" in out:
            return f"{len(out['pivots'])} pivots, {sum(1 for p in out['pivots'] if p['running'])} running"
        if "airlift" in out:
            return f"airlift {out['airlift']['delivered']:,}/{out['airlift']['target']:,}"
        return ", ".join(f"{k}={v}" for k, v in list(out.items())[:3])[:70]
    except Exception:  # noqa: BLE001
        return ""


GW: SensorGateway | None = None


def current() -> SensorGateway:
    """The gateway bound to the live twin. Nodes use this instead of passing
    the world through graph state."""
    return _gw()


def bind(world: World) -> SensorGateway:
    """Attach the live gateway the agents will query."""
    global GW
    GW = SensorGateway(world)
    return GW


def _gw() -> SensorGateway:
    if GW is None:
        raise RuntimeError("SensorGateway not bound -- call tools.bind(world) first")
    return GW


# --- telemetry tools -------------------------------------------------------

def get_environment_telemetry() -> dict:
    """Air and surface conditions at site. Agronomist + veterinarian."""
    return _gw().record("get_environment_telemetry", "", lambda: _environment_packet())


def _environment_packet() -> dict:
    e = _gw().environment()
    return {
        "time": _gw().packet()["time"],
        "temperature_c": e["temperature_c"],
        "relative_humidity_pct": e["relative_humidity_pct"],
        "thi_air": e["thi_air"],
        "solar_load_c": e["solar_load"],
        "effective_heat_load": e["effective_heat_load"],
        "heat_stress_band": e["heat_stress_band"],
        "wind_kmh": e["wind_kmh"],
        "soil_moisture_pct": e["soil_moisture_pct"],
        "soil_ph": e["soil_ph"],
        "soil_salinity_ds_m": e["soil_salinity_ds_m"],
    }


def get_water_budget() -> dict:
    """Aquifer status and projected annual draw. This is the scarce resource."""
    return _gw().record("get_water_budget", "", _gw().water_status)


def get_pivot_telemetry() -> list[dict]:
    return _gw().record("get_pivot_telemetry", "", _gw().pivot_telemetry)


# --- veterinary tools ------------------------------------------------------

def get_herd_vitals() -> dict:
    """Smart-collar roll-up. Aggregated per barn, not per cow -- at 270k head
    per-cow telemetry is a fiction and operations reason at barn level."""
    return _gw().record("get_herd_vitals", "", _gw().herd)


def get_group_health(name: str) -> dict | None:
    return _gw().group(name)


def get_barns_without_cooling() -> dict:
    return _gw().record("get_barns_without_cooling", "", _barns_without_cooling)


def _barns_without_cooling() -> dict:
    return {
        "barns": _gw().barns_without_cooling(),
        "note": (
            "Phase 1 installs misting hardware in only 4 of 8 barns. Cooling "
            "allocation is a scarcity decision, not a switch."
        ),
    }


# --- asset tools -----------------------------------------------------------

def get_asset_health() -> list[dict]:
    return _gw().asset_health()


def get_degraded_assets() -> list[dict]:
    return _gw().record("get_degraded_assets", "", _gw().degraded_assets)


# --- crop tools ------------------------------------------------------------

def crops() -> dict:
    """Standing forage programme: growth, cut readiness, harvest history."""
    return _gw().record("crops", "", _crops_packet)


def _crops_packet() -> dict:
    w = _gw().world
    c = w.crops
    return {
        "standing_t": c.standing_t(),
        "harvested_t": c.harvested_this_season_t,
        "cuts_completed": c.cuts_completed,
        "protein_pct": c.protein_pct(),
        "water_stressed_ha": c.water_stressed_ha(),
        "annual_target_t": C.FORAGE_TONNES_ANNUAL_TARGET,
        "status": c.status(),
        "fields": [
            {
                "field_id": f.name,
                "pivot_id": f.pivot_id,
                "crop": f.crop.value,
                "area_ha": round(f.area_ha, 1),
                "biomass_t_ha": round(f.biomass_t_ha, 2),
                "standing_t": round(f.standing_t, 1),
                "stage": f.stage.value,
                "soil_moisture_pct": round(
                    next(
                        (p.soil_moisture_pct for p in w.env.pivots if p.pid == f.pivot_id), 0.0
                    ), 2,
                ),
                "ready_for_cut": f.ready_for_cut,
                "water_stress_days": f.water_stress_days,
                "health": f.health(),
            }
            for f in c.fields
        ],
    }


# --- livestock tools -------------------------------------------------------

def youngstock() -> dict:
    """Herd structure by class, reproduction and calf welfare.

    Surfaces the fact that most of the herd is non-productive: the airlifted
    animals are heifers and will not milk for roughly 18 months.
    """
    return _gw().record("youngstock", "", _youngstock_packet)


def _youngstock_packet() -> dict:
    w = _gw().world
    ls = w.livestock
    lact = w.herd.herd_total_head()
    return {
        "total_head": lact + ls.total_youngstock(),
        "lactating_head": lact,
        "non_productive_head": ls.total_youngstock(),
        "by_class": ls.head_by_class(),
        "airlift_head": sum(ls.airlift_mix.values()),
        "airlift_mix": ls.airlift_mix,
        "calf_mortality_7d": sum(g.mortality_7d for g in ls.youngstock if g.group_class.value == "calf"),
        "status": ls.status(),
        "groups_heifer": [
            {
                "group_id": g.group_id,
                "head": g.head,
                "age_months": round(g.age_days / 30.4, 1),
                "avg_weight_kg": round(g.avg_weight_kg, 1),
                "target_weight_kg": g.target_weight_kg,
                "weight_pct_of_target": round(100 * g.avg_weight_kg / g.target_weight_kg, 1),
                "daily_gain_kg": round(g.daily_gain_kg, 2),
                "pregnant": g.pregnancy_confirmed,
                "days_open": round(g.days_open, 1),
                "status": g.status(),
            }
            for g in ls.youngstock
            if g.group_class.value == "heifer"
        ],
        "groups_calf": [
            {
                "group_id": g.group_id,
                "head": g.head,
                "age_days": round(g.age_days, 1),
                "avg_weight_kg": round(g.avg_weight_kg, 1),
                "scours_rate_pct": round(100 * g.scours_cases / max(g.head, 1), 2),
                "mortality_7d": g.mortality_7d,
                "status": g.status(),
            }
            for g in ls.youngstock
            if g.group_class.value == "calf"
        ],
        "groups_dry": [
            {
                "group_id": g.group_id,
                "head": g.head,
                "days_to_calving": round(g.days_to_first_calving, 1),
                "bcs": g.body_condition_score,
                "status": g.status(),
            }
            for g in ls.dry_cows()
        ],
    }


# --- milk tools ------------------------------------------------------------

def milk() -> dict:
    """Parlour, cold chain, quality and powder plant."""
    return _gw().record("milk", "", _milk_packet)


def _milk_packet() -> dict:
    w = _gw().world
    m = w.milk
    lact = w.herd.herd_total_head()
    return {
        "daily_milk_kg": m.daily_milk_kg,
        "daily_shipped_kg": m.daily_shipped_kg,
        "daily_loss_kg": m.daily_loss_kg,
        "capture_ratio": m.capture_ratio(),
        "lactating_head": lact,
        "milkings_per_day": m.parlour.milkings_per_day,
        "units": m.parlour.units,
        "throughput_cows_per_hour": m.parlour.throughput_cows_per_hour,
        "cows_milked_today": m.parlour.cows_milked_today,
        "downtime_min_24h": m.parlour.downtime_min_24h,
        "holding_area_ehl": w.env.clock.effective_heat_load(w.env.day_weather),
        "bulk_temp_c": m.tank.milk_temp_c,
        "bulk_tank_kg": m.tank.level_kg,
        "bulk_fill_pct": m.tank.fill_pct,
        "condenser_fouling_pct": m.tank.condenser_fouling_pct,
        "bulk_scc_k": m.bulk_scc_k,
        "quality_status": m.quality_status(),
        "silo_fill_pct": m.plant.silo_fill_pct,
        "silo_t": m.plant.silo_t,
        "powder_live": m.plant.running,
        "mastitis_head_estimate": sum(g.mastitis_cases for g in w.herd.groups),
        "status": m.status(),
    }


# --- logistics tools -------------------------------------------------------

def get_feed_inventory() -> dict:
    return _gw().record("get_feed_inventory", "", _feed_inventory)


def _feed_inventory() -> dict:
    l = _gw().logistics()
    return {
        "feed_total_t": l["feed_total_t"],
        "feed_hours_of_cover": l["feed_hours_of_cover"],
        "daily_demand_t": l["daily_demand_t"],
        "silos": l["silos"],
        "critical": l["silos"] and _gw().critical_silos(),
    }


def get_fleet_positions() -> list[dict]:
    return _gw().record("get_fleet_positions", "", lambda: _gw().logistics()["tankers"])


def get_airlift_schedule() -> dict:
    return _gw().record("get_airlift_schedule", "", _gw().airlift)


ALL_TOOLS: list[Any] = [
    get_environment_telemetry,
    crops,
    youngstock,
    milk,
    get_water_budget,
    get_pivot_telemetry,
    get_herd_vitals,
    get_group_health,
    get_barns_without_cooling,
    get_asset_health,
    get_degraded_assets,
    get_feed_inventory,
    get_fleet_positions,
    get_airlift_schedule,
]

__all__ = [
    "ALL_TOOLS",
    "SensorGateway",
    "bind",
    "crops",
    "current",
    "get_airlift_schedule",
    "get_asset_health",
    "get_barns_without_cooling",
    "get_degraded_assets",
    "get_environment_telemetry",
    "get_feed_inventory",
    "get_fleet_positions",
    "get_group_health",
    "get_herd_vitals",
    "get_pivot_telemetry",
    "get_water_budget",
    "milk",
    "youngstock",
]