"""Layer 1 - Sensory Cortex: environment simulation.

Soil water balance, aquifer depletion, and the THI curve that makes Adrar hard.

The aquifer is modelled as a NON-RENEWABLE stock. This is the single most
important modelling decision in the whole twin: it means the system cannot
sustain full herd scale forever, and the agents must discover that themselves
rather than being told.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import constants as C
from .clock import SimClock


@dataclass
class Aquifer:
    """Non-renewable Albien groundwater stock.

    Status is judged against the PROJECTED ANNUAL DRAW, not against the
    absolute stock. A 7-day demo cannot deplete a fossil aquifer, but it can
    immediately show that the current allocation, held for a year, would exceed
    the 2.5-4bn m3/yr envelope. That is the decision-relevant number and the one
    the orchestrator needs in order to arbitrate pivots against misters.
    """

    annual_budget_m3: float = C.WATER_M3_FULL_ANNUAL
    stock_m3: float = C.WATER_M3_FULL_ANNUAL * 25.0
    cumulative_draw_m3: float = 0.0
    projected_annual_m3h: float = 0.0
    base_yield_m3h: float = 42.0

    @property
    def remaining_fraction(self) -> float:
        return max(0.0, 1.0 - self.cumulative_draw_m3 / self.stock_m3)

    @property
    def budget_utilisation(self) -> float:
        """Projected annual draw / annual budget. >1.0 means unsustainable."""
        if self.projected_annual_m3h <= 0:
            return 0.0
        return self.projected_annual_m3h * 8760.0 / self.annual_budget_m3

    def well_yield_m3h(self) -> float:
        """Specific capacity declines roughly linearly with depletion."""
        return self.base_yield_m3h * (0.35 + 0.65 * self.remaining_fraction)

    def draw(self, m3: float, rate_m3h: float) -> None:
        self.cumulative_draw_m3 += max(0.0, m3)
        self.projected_annual_m3h = rate_m3h

    def status(self) -> str:
        u = self.budget_utilisation
        if u >= 1.0:
            return "over-budget"
        if u >= 0.85:
            return "critical"
        if u >= 0.60:
            return "constrained"
        return "nominal"


@dataclass
class Pivot:
    """Centre-pivot irrigation unit. Valmont/AFKO hardware."""

    pid: int
    field_ha: float
    soil_moisture_pct: float = C.SOIL_MOISTURE_OPTIMAL_PCT
    running: bool = False
    position_pct: float = 0.0
    bearing_temp_c: float = 42.0
    vibration_mm_s: float = 2.1
    motor_hours: float = 0.0
    nozzles_blocked: int = 0
    applied_m3_ha: float = 0.0

    @property
    def name(self) -> str:
        return f"PIVOT-{self.pid}"

    def health(self) -> str:
        if self.bearing_temp_c >= C.MOTOR_BEARING_CRITICAL_C:
            return "critical"
        if self.bearing_temp_c >= C.MOTOR_BEARING_WARN_C or self.vibration_mm_s >= C.PIVOT_VIBRATION_WARN_MM_S:
            return "degraded"
        if self.nozzles_blocked > 8:
            return "degraded"
        return "nominal"

    def needs_water(self) -> bool:
        return self.soil_moisture_pct < C.SOIL_MOISTURE_OPTIMAL_PCT


@dataclass
class EnvironmentState:
    """What the agronomist agent can perceive."""

    clock: SimClock = field(default_factory=SimClock)
    aquifer: Aquifer = field(default_factory=Aquifer)
    pivots: list[Pivot] = field(default_factory=list)
    day_weather: float = 1.0
    misters_on: bool = False
    mist_flow_lpm: float = 0.0
    water_allocated_m3h: float = 0.0
    soil_ph: float = 7.4
    soil_salinity_ds_m: float = 0.8
    #: Standing-crop cover 0..1. Established barley at Tamest from May 2026, so
    #: cover is non-zero at t0. Mulching/canopy cuts soil evaporation ~40%.
    crop_cover: float = 0.35

    @classmethod
    def initial(cls, seed: int = 20260911) -> EnvironmentState:
        rng = random.Random(seed)
        env = cls()
        # Assume the Phase 1 pivots are already installed over the first fields.
        env.pivots = [
            Pivot(
                pid=i + 1,
                field_ha=C.PIVOT_AREA_HA,
                soil_moisture_pct=rng.uniform(14.0, 27.0),
            )
            for i in range(C.PIVOTS)
        ]
        return env

    # --- perception ----------------------------------------------------

    def temperature_c(self) -> float:
        return self.clock.temperature_c(self.day_weather)

    def relative_humidity(self) -> float:
        return self.clock.relative_humidity(self.day_weather)

    def th_i(self) -> float:
        return self.clock.th_i(self.day_weather)

    def effective_heat_load(self) -> float:
        """Air THI + clear-sky solar load. This is what triggers heat stress."""
        return self.clock.effective_heat_load(self.day_weather)

    def water_use_m3h(self) -> float:
        pivots = sum(1 for p in self.pivots if p.running)
        # Pivot application rate for sandy soil ~ 9mm/h on a full circle.
        pivot_m3h = pivots * (C.PIVOT_AREA_HA * 10_000 * 0.009)
        mister_m3h = self.mist_flow_lpm * 60.0 / 1000.0 if self.misters_on else 0.0
        return pivot_m3h + mister_m3h

    # --- physics -------------------------------------------------------

    def tick(self, rng: random.Random) -> None:
        """Advance environment physics by one tick."""
        t = self.temperature_c()
        evap_mm_day = self._potential_et(t)
        # ET0 is a DAILY rate; integrate over the tick as a fraction of a day.
        evap_mm = evap_mm_day * self.clock.minutes_per_tick / 1440.0
        evap_mm *= (1.0 - 0.40 * self.crop_cover)

        for p in self.pivots:
            if p.running:
                applied_mm = 9.0 * (self.clock.minutes_per_tick / 60.0)
                soil_gain = applied_mm * 1.35  # sandy soil, low runoff
                # 1pp of soil moisture per mm of net infiltration, sandy profile.
                p.soil_moisture_pct += soil_gain * 0.62 - evap_mm * 1.0
                p.motor_hours += self.clock.minutes_per_tick / 60.0
                p.position_pct = (p.position_pct + 100.0 / 48.0) % 100.0
                p.applied_m3_ha += applied_mm
            else:
                p.soil_moisture_pct -= evap_mm * 1.0
            p.soil_moisture_pct = max(
                0.5, min(C.SOIL_MOISTURE_SATURATION_PCT, p.soil_moisture_pct)
            )

            # Thermal + mechanical wear on rotating equipment.
            load = 1.0 if p.running else 0.28
            p.bearing_temp_c += (self._ambient_bearing_target() - p.bearing_temp_c) * 0.22 * load
            p.bearing_temp_c += rng.uniform(-0.7, 1.5) * load
            p.vibration_mm_s += rng.uniform(-0.22, 0.28) * load
            p.vibration_mm_s = max(0.4, min(14.0, p.vibration_mm_s))
            if rng.random() < 0.004:
                p.nozzles_blocked += 1

        # Water draw against the aquifer, with the current rate for budgeting.
        rate = self.water_use_m3h()
        self.aquifer.draw(rate * self.clock.minutes_per_tick / 60.0, rate)
        self.water_allocated_m3h = rate

        # Evaporation concentrates salts in the root zone -- a slow-burn failure.
        self.soil_salinity_ds_m = min(
            6.0, self.soil_salinity_ds_m + 0.0016 * (evap_mm_day / 11.0)
            * (self.clock.minutes_per_tick / 1440.0)
        )
        self.clock = self.clock.advance()

    def _potential_et(self, temp_c: float) -> float:
        """Hargreaves-style ET0 proxy. mm/day."""
        return max(
            0.4,
            0.0023 * (temp_c + 17.8) * math.sqrt(max(temp_c - 2.0, 0.0)) * 12.0,
        )

    def _ambient_bearing_target(self) -> float:
        # Bearings sit well above ambient once running; solar load in the desert
        # is severe.
        return self.temperature_c() * 0.72 + 16.0

    # --- state quality -------------------------------------------------

    def health_summary(self) -> str:
        statuses = {p.health() for p in self.pivots}
        if "critical" in statuses or self.aquifer.status() == "critical":
            return "critical"
        if "degraded" in statuses or self.aquifer.status() in ("watch", "constrained"):
            return "degraded"
        return "nominal"


__all__ = [
    "Aquifer",
    "EnvironmentState",
    "Pivot",
]