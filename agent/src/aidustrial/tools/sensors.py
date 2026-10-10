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

from typing import Any

from ..twin import constants as C
from ..twin.world import World


class SensorGateway:
    """Read-only facade over the twin. Shared by every tool below."""

    def __init__(self, world: World) -> None:
        self.world = world

    def packet(self) -> dict:
        return self.world.observe()

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
    return _gw().water_status()


def get_pivot_telemetry() -> list[dict]:
    return _gw().pivot_telemetry()


# --- veterinary tools ------------------------------------------------------

def get_herd_vitals() -> dict:
    """Smart-collar roll-up. Aggregated per barn, not per cow -- at 270k head
    per-cow telemetry is a fiction and operations reason at barn level."""
    return _gw().herd()


def get_group_health(name: str) -> dict | None:
    return _gw().group(name)


def get_barns_without_cooling() -> dict:
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
    return _gw().degraded_assets()


# --- logistics tools -------------------------------------------------------

def get_feed_inventory() -> dict:
    l = _gw().logistics()
    return {
        "feed_total_t": l["feed_total_t"],
        "feed_hours_of_cover": l["feed_hours_of_cover"],
        "daily_demand_t": l["daily_demand_t"],
        "silos": l["silos"],
        "critical": l["silos"] and _gw().critical_silos(),
    }


def get_fleet_positions() -> list[dict]:
    return _gw().logistics()["tankers"]


def get_airlift_schedule() -> dict:
    return _gw().airlift()


ALL_TOOLS: list[Any] = [
    get_environment_telemetry,
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
]