"""Layer 1 - Sensory Cortex: logistics simulation.

Silos, milk tankers, feed inbound, and the US cattle airlift schedule.

The logistics agent has the most interesting job in this build because of a
structural tension that exists in the real project: the herd arrives by AIR
starting November 2026, but the fodder to feed it is produced by an arable
programme that needs a full growing season. So the first 30,000 head are
running on purchased feed against a six-month production gap. That is a real
inventory crisis, not a synthetic one, and it is exactly what the demo should
show.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from . import constants as C
from .clock import SimClock


@dataclass
class Silo:
    """Feed silo. Level is the whole game."""

    sid: str
    capacity_t: float = C.SILO_CAPACITY_TONNES
    fill_t: float = 0.0
    feed_type: str = "corn_silage"
    inlet_rate_t_per_day: float = 0.0
    inlet_operational: bool = False
    #: "conveyor" = fed from standing forage by belt; "bulk" = grain/mineral
    #: delivered by tipper. Only conveyor inlets are a mechanical health item.
    inlet_type: str = "conveyor"

    @property
    def fill_pct(self) -> float:
        return 100.0 * self.fill_t / self.capacity_t

    def hours_of_cover(self, daily_demand_t: float) -> float:
        """0.0 while the herd is not yet consuming, so the value stays JSON-safe."""
        if daily_demand_t <= 0:
            return 0.0
        return 24.0 * self.fill_t / daily_demand_t

    def status(self, daily_demand_t: float) -> str:
        cover = self.hours_of_cover(daily_demand_t)
        if self.fill_pct <= C.SILO_CRITICAL_FILL_PCT:
            return "critical"
        if daily_demand_t <= 0:
            return "nominal"  # not yet drawing; hours-of-cover is not meaningful
        if cover < 24:
            return "critical"
        if cover < C.SILO_HOURS_OF_COVER_WARN:
            return "degraded"
        return "nominal"


@dataclass
class Tanker:
    """Milk tanker in transit to the powder plant."""

    tid: str
    lat: float
    lon: float
    load_kg: float
    capacity_kg: float = 30_000.0
    destination: str = "powder-plant"
    coolant_temp_c: float = 4.0
    in_transit: bool = True
    #: "loading" | "in_transit" | "unloading" -- shown on the dashboard so the
    #: cold-chain risk is visibly attached to a leg of the journey.
    status_: str = "in_transit"
    dwell_ticks: int = 0

    @property
    def fill_pct(self) -> float:
        return 100.0 * self.load_kg / self.capacity_kg

    def status(self) -> str:
        if self.coolant_temp_c > 8.0:
            return "critical"
        if self.coolant_temp_c > 6.5:
            return "degraded"
        return "nominal"


@dataclass
class AirliftTracker:
    """109 flights from 9 US states, ~300 cows per flight, from Nov 2026."""

    start: date = date(2026, 11, 1)
    total_cows: int = C.HERD_AIRLIFT_TOTAL
    total_flights: int = C.HERD_AIRLIFT_FLIGHTS
    cows_per_flight: int = C.HERD_AIRLIFT_COWS_PER_FLIGHT
    months: int = C.HERD_AIRLIFT_MONTHS
    delivered: int = 0
    flights_completed: int = 0

    @property
    def progress_pct(self) -> float:
        return 100.0 * self.delivered / self.total_cows

    @property
    def state(self) -> str:
        if self.delivered == 0:
            return "pre-departure"
        if self.delivered >= self.total_cows:
            return "complete"
        if self.progress_pct < 25:
            return "ramping"
        if self.progress_pct < 75:
            return "in-campaign"
        return "tapering"


@dataclass
class LogisticsState:
    clock: SimClock = field(default_factory=SimClock)
    silos: list[Silo] = field(default_factory=list)
    tankers: list[Tanker] = field(default_factory=list)
    airlift: AirliftTracker = field(default_factory=AirliftTracker)
    daily_feed_demand_t: float = 0.0
    purchased_feed_t: float = 0.0
    inbound_shipments: int = 0

    @classmethod
    def initial(cls, seed: int = 20260911) -> LogisticsState:
        rng = random.Random(seed)
        log = cls()
        types = ["corn_silage", "corn_silage", "alfalfa", "barley_grain", "sorghum_sudangrass", "mineral_mix"]
        for i, t in enumerate(types):
            conveyor = t in ("corn_silage", "alfalfa", "sorghum_sudangrass")
            log.silos.append(
                Silo(
                    sid=f"S{i + 1:02d}",
                    fill_t=C.SILO_CAPACITY_TONNES * rng.uniform(0.55, 0.92),
                    feed_type=t,
                    inlet_type="conveyor" if conveyor else "bulk",
                    inlet_operational=conveyor,
                )
            )
        # A road milk tanker carries 20-30 t. Chilled to 2-4C on dispatch.
        log.tankers = [
            Tanker(
                tid=f"T{i + 1}",
                lat=27.87 + rng.uniform(-0.05, 0.05),
                lon=-0.29 + rng.uniform(-0.05, 0.05),
                load_kg=rng.uniform(16_000.0, 28_000.0),
                capacity_kg=30_000.0,
                coolant_temp_c=rng.uniform(2.5, 4.2),
            )
            for i in range(3)
        ]
        return log

    # --- perception ----------------------------------------------------

    def total_feed_t(self) -> float:
        return sum(s.fill_t for s in self.silos)

    def feed_hours_of_cover(self) -> float:
        """Hours of feed on hand. Returns 0.0 before the herd is in service so
        the value survives JSON round-tripping -- a bare inf() becomes null in
        JSON, which the dashboard would read as "no data"."""
        if self.daily_feed_demand_t <= 0:
            return 0.0
        return 24.0 * self.total_feed_t() / self.daily_feed_demand_t

    def critical_silos(self) -> list[Silo]:
        return [s for s in self.silos if s.status(self.daily_feed_demand_t) == "critical"]

    # --- physics -------------------------------------------------------

    def tick(self, rng: random.Random, headcount: int, herd_alive: bool) -> None:
        self.clock = self.clock.advance()

        milk_output_t_day = 0.0
        if herd_alive and headcount > 0:
            # A lactating Holstein eats ~4% of bodyweight in DM terms; 24kg DM
            # is the modelling figure from HerdGroup.feed_intake_kg.
            self.daily_feed_demand_t = headcount * 24.0 / 1000.0
            milk_output_t_day = headcount * 30.0 / 1000.0  # ~30 kg/cow/day
            for s in self.silos:
                draw = self.daily_feed_demand_t * self.clock.minutes_per_tick / 1440.0
                s.fill_t = max(0.0, s.fill_t - draw)
                if s.inlet_operational:
                    s.fill_t = min(s.capacity_t, s.fill_t + rng.uniform(2.0, 9.0))

            # Purchased feed covers the pre-harvest gap.
            deficit = max(0.0, self.daily_feed_demand_t - sum(s.inlet_rate_t_per_day for s in self.silos))
            self.purchased_feed_t += deficit * self.clock.minutes_per_tick / 1440.0
            self.inbound_shipments = int(self.purchased_feed_t / 900.0)

        # Airlift progresses ~10 flights per 30-day month.
        if self.airlift.state not in ("pre-departure", "complete"):
            per_tick = self.airlift.total_cows / (self.airlift.months * 30 * 48)
            self.airlift.delivered = min(
                self.airlift.total_cows, self.airlift.delivered + per_tick
            )
            self.airlift.flights_completed = int(
                self.airlift.delivered / self.airlift.cows_per_flight
            )

        # --- tanker dispatch cycle ---
        # A tanker is either filling at the parlour, in transit, or unloading.
        # It previously discharged every tick regardless of state, which drained
        # the whole fleet to zero on day 0.
        step_frac = self.clock.minutes_per_tick / 1440.0
        for t in self.tankers:
            if t.load_kg <= 0.0:
                # Dwell at the powder plant, then load and depart.
                t.dwell_ticks -= 1
                if t.dwell_ticks <= 0:
                    t.load_kg = min(t.capacity_kg, milk_output_t_day * step_frac * 240.0)
                    t.coolant_temp_c = rng.uniform(2.5, 4.2)
                    t.status_ = "loading"
                continue

            t.status_ = "in_transit"
            t.coolant_temp_c += (3.0 - t.coolant_temp_c) * 0.22
            t.coolant_temp_c += rng.uniform(-0.06, 0.10)
            if rng.random() < 0.004:
                t.coolant_temp_c += rng.uniform(1.5, 4.0)
            t.lat += rng.uniform(-0.004, 0.004)
            t.lon += rng.uniform(-0.004, 0.004)
            # Discharge over ~half a day of ticks.
            t.load_kg = max(0.0, t.load_kg - (t.capacity_kg / 24.0))
            if t.load_kg <= 0.0:
                t.dwell_ticks = 96
                t.status_ = "unloading"

    def status(self) -> str:
        if self.critical_silos():
            return "critical"
        if self.feed_hours_of_cover() < C.SILO_HOURS_OF_COVER_WARN:
            return "degraded"
        return "nominal"


__all__ = ["AirliftTracker", "LogisticsState", "Silo", "Tanker"]