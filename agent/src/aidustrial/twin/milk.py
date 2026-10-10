"""Layer 0 - MILK PRODUCTION.

From teat to powder silo. The crop and livestock systems decide how much milk
exists; this module decides whether the site actually captures it.

Three stages, each of which loses milk if it fails:
  parlour  -> milking yield per cow per milking, throughput, downtime
  cooling  -> bulk tank, milk temperature, the cold chain handover
  plant    -> powder plant intake, spray dryer availability, silo inventory

The dairy-quality signal that matters here is somatic cell count (SCC). It rises
with mastitis and falls with treatment and culling. It is the one number a
dairy buyer looks at, and it is invisible in tonnage -- so the milking agent
needs it separately or it will optimise the wrong thing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import constants as C


@dataclass
class MilkingEvent:
    """One milking of one group."""

    group: str
    milking_number: int  # 1 or 2 (or 3 on a high-frequency system)
    yield_kg: float
    conductivity: float  # mS/cm; rises with mastitis
    refusals: int  # cows that kicked off or were missed
    downtime_min: float

    @property
    def per_cow_kg(self) -> float:
        return self.yield_kg


@dataclass
class ParlourState:
    """Milking platform. Robotic or parallel parlour for a herd this size."""

    #: Parallel parlour with two milkings a day is the norm at this scale.
    milkings_per_day: int = 2
    units: int = 2
    throughput_cows_per_hour: float = 180.0
    cows_milked_today: int = 0
    last_milking_complete: bool = True
    downtime_min_24h: float = 0.0
    milk_temp_c: float = 3.8
    #: Bedding and holding area heat load -- where cows stand before milking.
    holding_area_ehl: float = 0.0

    @property
    def capacity_cows_per_day(self) -> float:
        return self.units * self.throughput_cows_per_hour * (24.0 / self.units)

    @property
    def utilisation_pct(self) -> float:
        if self.cows_milked_today <= 0:
            return 0.0
        return 100.0 * self.cows_milked_today / max(self.capacity_cows_per_day, 1.0)

    def status(self) -> str:
        if self.downtime_min_24h > 180:
            return "critical"
        if self.downtime_min_24h > 60 or self.milk_temp_c > 6.5:
            return "degraded"
        return "nominal"


@dataclass
class BulkTank:
    """Storage before dispatch. Cold chain begins here."""

    capacity_kg: float = 60_000.0
    level_kg: float = 0.0
    milk_temp_c: float = 3.4
    condenser_fouling_pct: float = 8.0
    cleaned_today: bool = False

    @property
    def fill_pct(self) -> float:
        return 100.0 * self.level_kg / self.capacity_kg

    def status(self) -> str:
        if self.milk_temp_c > 8.0:
            return "critical"
        if self.milk_temp_c > 6.5:
            return "degraded"
        if self.condenser_fouling_pct > 70:
            return "degraded"
        return "nominal"


@dataclass
class PowderPlant:
    """GEA spray-drying installation."""

    #: ~100,000 t/yr design capacity at full build-out.
    design_t_year: float = C.MILK_POWDER_T_TARGET
    silo_t: float = 0.0
    silo_capacity_t: float = 3_500.0
    running: bool = False
    throughput_t_day: float = 0.0
    downtime_min_24h: float = 0.0
    first_production: bool = False

    @property
    def silo_fill_pct(self) -> float:
        return 100.0 * self.silo_t / self.silo_capacity_t

    def status(self) -> str:
        if self.silo_fill_pct > 92:
            return "critical"  # silo full, must stop intake
        if self.downtime_min_24h > 120:
            return "degraded"
        return "nominal"


@dataclass
class MilkState:
    parlour: ParlourState = field(default_factory=ParlourState)
    tank: BulkTank = field(default_factory=BulkTank)
    plant: PowderPlant = field(default_factory=PowderPlant)

    daily_milk_kg: float = 0.0
    bulk_scc_k: float = 180.0  # thousand cells/mL. 200k is the EU limit.
    daily_shipped_kg: float = 0.0
    #: Milk lost to quality rejection, heat, or spillage.
    daily_loss_kg: float = 0.0
    last_events: list[dict] = field(default_factory=list)

    # --- perception ----------------------------------------------------

    def projected_kg_day(self) -> float:
        return self.daily_milk_kg

    def quality_status(self) -> str:
        if self.bulk_scc_k > 400:
            return "critical"
        if self.bulk_scc_k > 200:
            return "degraded"
        return "nominal"

    def capture_ratio(self) -> float:
        """Share of biological production actually captured and dispatched."""
        if self.daily_milk_kg <= 0:
            return 0.0
        return 100.0 * self.daily_shipped_kg / self.daily_milk_kg

    # --- physics -------------------------------------------------------

    def tick(self, rng: random.Random, lactating_head: int, herd_scc_k: float, powder_live: bool) -> None:
        """One half-day tick."""
        p = self.parlour

        # Biological production from the lactating herd.
        produced = lactating_head * C.MILK_LITRES_PER_COW_DAY * 0.5
        self.daily_milk_kg = produced * 2.0  # two milkings a day

        # Bulk SCC follows the herd, with a lag from the parlour.
        self.bulk_scc_k += (herd_scc_k - self.bulk_scc_k) * 0.18

        # Cooling: condenser fouling degrades pull-down.
        if not p.cleaned_today if hasattr(p, "cleaned_today") else True:
            self.tank.condenser_fouling_pct = min(
                100.0, self.tank.condenser_fouling_pct + rng.uniform(0.1, 0.4)
            )
        self.tank.milk_temp_c += (3.2 - self.tank.milk_temp_c) * 0.3
        self.tank.milk_temp_c += rng.uniform(-0.05, 0.12)

        # Milk enters the bulk tank, minus any that spoils in transit.
        spoiled = 0.0
        if self.tank.milk_temp_c > 6.5:
            spoiled = produced * (self.tank.milk_temp_c - 6.5) / 100.0
        self.daily_loss_kg += spoiled * 2.0
        self.tank.level_kg = min(self.tank.capacity_kg, self.tank.level_kg + produced - spoiled)

        # Randomised parlour downtime.
        if rng.random() < 0.02:
            p.downtime_min_24h += rng.uniform(5.0, 45.0)
        p.cows_milked_today = int(
            min(
                lactating_head * p.milkings_per_day,
                p.cows_milked_today + p.throughput_cows_per_hour * 0.5,
            )
        )

        # Powder plant. Not yet commissioned on the real timeline, so this runs
        # only once the twin is told the site is operational.
        if powder_live:
            self.plant.running = True
            intake = self.tank.level_kg
            self.plant.throughput_t_day = intake / 1000.0
            # ~8.5:1 concentration ratio from milk to skim milk powder.
            powder_t = intake / 1000.0 / 8.5
            self.plant.silo_t = min(self.plant.silo_capacity_t, self.plant.silo_t + powder_t)
            self.tank.level_kg = 0.0
            self.daily_shipped_kg = intake
            if powder_t > 0:
                self.plant.first_production = True
        else:
            # Pre-commissioning: milk accumulates and ships as liquid product.
            self.daily_shipped_kg = min(self.tank.level_kg, 20_000.0)
            self.tank.level_kg = max(0.0, self.tank.level_kg - self.daily_shipped_kg)

        if rng.random() < 0.01:
            self.plant.downtime_min_24h += rng.uniform(10.0, 60.0)

    def status(self) -> str:
        s = {self.parlour.status(), self.tank.status(), self.plant.status()}
        if "critical" in s:
            return "critical"
        if "degraded" in s:
            return "degraded"
        return "nominal"


__all__ = ["BulkTank", "MilkState", "MilkingEvent", "ParlourState", "PowderPlant"]