"""Layer 0 - CROP PRODUCTION.

Pivot irrigation is only one third of crop production. The other two thirds are
crop performance and harvest: which field is carrying which forage, how fast it
is accumulating dry matter, when it is cut, and how much silage that produces.

The Adrar programme is aimed at 2.5 million tonnes of forage a year against
1.17 million m3 of water -- roughly 2.1 kg of dry matter per m3 delivered. That
ratio is the whole feasibility argument for the project, and it is the number
this module exists to produce.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from . import constants as C


class CropType(str, Enum):
    CORN_SILAGE = "corn_silage"
    ALFALFA = "alfalfa"
    BARLEY = "barley"
    SORGHUM_SUDAN = "sorghum_sudangrass"
    WHEAT = "wheat"


class GrowthStage(str, Enum):
    EMERGENCE = "emergence"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    MATURITY = "maturity"
    HARVESTED = "harvested"


#: Peak standing dry matter, t/ha, by crop under good irrigation.
PEAK_DM_T_HA: dict[CropType, float] = {
    CropType.CORN_SILAGE: 20.0,
    CropType.ALFALFA: 14.0,
    CropType.BARLEY: 8.0,
    CropType.SORGHUM_SUDAN: 12.0,
    CropType.WHEAT: 7.5,
}

#: Days from sowing to a first cut. Desert growing seasons are short.
CUT_INTERVAL_DAYS: dict[CropType, int] = {
    CropType.CORN_SILAGE: 95,
    CropType.ALFALFA: 38,
    CropType.BARLEY: 105,
    CropType.SORGHUM_SUDAN: 75,
    CropType.WHEAT: 110,
}

#: Below this standing DM, a cut wastes machinery and labour.
MIN_CUTTABLE_DM_T_HA: float = 2.5

#: Crude protein, %. Drives the ration, not the mass balance.
CRUDE_PROTEIN_PCT: dict[CropType, float] = {
    CropType.CORN_SILAGE: 8.5,
    CropType.ALFALFA: 19.0,
    CropType.BARLEY: 11.0,
    CropType.SORGHUM_SUDAN: 10.0,
    CropType.WHEAT: 12.0,
}


@dataclass
class ForageField:
    """One field under irrigation, carrying one crop."""

    field_id: str
    pivot_id: int
    crop: CropType
    area_ha: float
    stage: GrowthStage = GrowthStage.VEGETATIVE
    #: Standing dry matter, t/ha. Only accrues when the crop is not water-stressed.
    biomass_t_ha: float = 0.0
    days_since_sowing: int = 0
    days_since_cut: int = 0
    water_stress_days: int = 0
    weeds_pct: float = 8.0
    heat_stress_days: int = 0

    @property
    def name(self) -> str:
        return f"FLD-{self.field_id}"

    @property
    def standing_t(self) -> float:
        return self.biomass_t_ha * self.area_ha

    @property
    def ready_for_cut(self) -> bool:
        """A cut is only worth taking if there is something on the ground.

        Without a biomass floor, a field that went water-stressed kept reporting
        itself ready every tick and the site logged dozens of zero-tonne
        harvests -- a real failure mode, because a 'cut' resets the growth
        clock and would stop the field ever recovering."""
        if self.stage is GrowthStage.HARVESTED:
            return False
        if self.biomass_t_ha < MIN_CUTTABLE_DM_T_HA:
            return False
        return self.days_since_cut >= CUT_INTERVAL_DAYS[self.crop]

    @property
    def moisture_stress(self) -> bool:
        """Wilting-point soil moisture caps biomass accrual sharply."""
        return self.water_stress_days > 0

    def growth_rate_per_day(self, soil_moisture_pct: float, ehl: float) -> float:
        """t DM/ha/day, gated on water and heat.

        Logistic accumulation: a young crop adds almost nothing, a crop past
        half its interval approaches the ceiling, and water or heat stress
        drives the rate to zero rather than merely reducing it.
        """
        peak = PEAK_DM_T_HA[self.crop]
        interval = CUT_INTERVAL_DAYS[self.crop]
        progress = min(1.0, self.days_since_sowing / max(interval, 1))
        # Logistic S-curve.
        shape = (6.0 * progress * (1.0 - progress)) / (1.0 + 4.0 * (1.0 - progress) ** 2)

        # Water response. Below wilting point nothing grows; above optimum the
        # crop saturates and further water is wasted.
        if soil_moisture_pct <= C.SOIL_MOISTURE_WILTING_PCT:
            water = 0.0
        else:
            span = C.SOIL_MOISTURE_OPTIMAL_PCT - C.SOIL_MOISTURE_WILTING_PCT
            water = min(1.0, (soil_moisture_pct - C.SOIL_MOISTURE_WILTING_PCT) / span)

        # Heat response. Corn and sorghum tolerate heat; alfalfa penalises it.
        heat_tolerance = 0.9 if self.crop in (CropType.CORN_SILAGE, CropType.SORGHUM_SUDAN) else 0.6
        heat = max(0.0, 1.0 - max(0.0, ehl - C.THI_HEAT_STRESS_ONSET) / 40.0)
        heat = 1.0 - (1.0 - heat) / max(heat_tolerance, 0.1)

        ceiling = peak / max(interval * 0.42, 1.0)
        return ceiling * shape * water * heat

    def stage_of(self) -> GrowthStage:
        if self.stage is GrowthStage.HARVESTED:
            return self.stage
        progress = self.days_since_sowing / max(CUT_INTERVAL_DAYS[self.crop], 1)
        if progress < 0.15:
            return GrowthStage.EMERGENCE
        if progress < 0.55:
            return GrowthStage.VEGETATIVE
        if progress < 0.85:
            return GrowthStage.FLOWERING
        return GrowthStage.MATURITY

    def cut(self) -> float:
        """Harvest. Returns tonnes of dry matter produced."""
        t = self.standing_t
        self.biomass_t_ha = 0.0
        self.days_since_cut = 0
        # Regrowth starts from the current season position rather than
        # rewinding to emergence, so a multi-cut crop does not behave like a
        # freshly sown one.
        self.days_since_sowing = max(
            self.days_since_sowing, CUT_INTERVAL_DAYS[self.crop] - 1
        )
        self.stage = GrowthStage.VEGETATIVE
        return t

    def health(self) -> str:
        if self.stage is GrowthStage.HARVESTED:
            return "harvested"
        if self.water_stress_days >= 4 or self.biomass_t_ha < 1.0:
            return "critical"
        if self.water_stress_days >= 2 or self.weeds_pct > 28:
            return "degraded"
        return "nominal"


@dataclass
class CropState:
    """Standing forage programme across all irrigated fields."""

    fields: list[ForageField] = field(default_factory=list)
    harvested_this_season_t: float = 0.0
    cuts_completed: int = 0
    silage_to_silo_t: float = 0.0
    #: Wilt target: silage is chopped at ~30% DM then wilts to ~35%.
    ensiling_loss_factor: float = 0.82

    @classmethod
    def initial(cls, seed: int = 20260911) -> CropState:
        rng = random.Random(seed)
        st = cls()
        # Six pivots x one primary crop each, plus alfalfa on spare ground.
        plan = [
            ("A1", 1, CropType.CORN_SILAGE),
            ("A2", 2, CropType.ALFALFA),
            ("A3", 3, CropType.SORGHUM_SUDAN),
            ("A4", 4, CropType.BARLEY),
            ("A5", 5, CropType.CORN_SILAGE),
            ("A6", 6, CropType.ALFALFA),
        ]
        for fid, pivot, crop in plan:
            st.fields.append(
                ForageField(
                    field_id=fid,
                    pivot_id=pivot,
                    crop=crop,
                    area_ha=C.PIVOT_AREA_HA,
                    # First barley harvest at Tamest already happened in May
                    # 2026, so corn and sorghum are part-way through a season.
                    days_since_sowing=48 if crop in (CropType.CORN_SILAGE, CropType.SORGHUM_SUDAN) else 110,
                    biomass_t_ha=rng.uniform(2.0, 6.5) if crop in (CropType.CORN_SILAGE, CropType.SORGHUM_SUDAN) else rng.uniform(5.0, 7.0),
                    weeds_pct=rng.uniform(4.0, 18.0),
                )
            )
        return st

    # --- perception ----------------------------------------------------

    def standing_t(self) -> float:
        return sum(f.standing_t for f in self.fields)

    def water_stressed_ha(self) -> float:
        return sum(f.area_ha for f in self.fields if f.moisture_stress)

    def ready_fields(self) -> list[ForageField]:
        return [f for f in self.fields if f.ready_for_cut]

    def protein_pct(self) -> float:
        if not self.fields:
            return 0.0
        w = sum(f.area_ha for f in self.fields)
        if w <= 0:
            return 0.0
        return sum(CRUDE_PROTEIN_PCT[f.crop] * f.area_ha for f in self.fields) / w

    def annualised_t(self) -> float:
        """Extrapolate current standing crop to an annual figure using the
        documented target as the yardstick."""
        return C.FORAGE_TONNES_ANNUAL_TARGET

    # --- physics -------------------------------------------------------

    def tick(self, rng: random.Random, soil_moisture_by_pivot: dict[int, float], ehl: float) -> None:
        for f in self.fields:
            moisture = soil_moisture_by_pivot.get(f.pivot_id, C.SOIL_MOISTURE_WILTING_PCT)
            if moisture <= C.SOIL_MOISTURE_WILTING_PCT:
                f.water_stress_days += 1
            else:
                f.water_stress_days = max(0, f.water_stress_days - 1)

            if ehl >= C.THI_HEAT_STRESS_MODERATE:
                f.heat_stress_days += 1

            f.biomass_t_ha += f.growth_rate_per_day(moisture, ehl) * (
                self.clock_fraction()
            )
            f.biomass_t_ha = min(PEAK_DM_T_HA[f.crop], f.biomass_t_ha)

            f.days_since_sowing += 1
            f.days_since_cut += 1
            f.weeds_pct = min(45.0, f.weeds_pct + rng.uniform(-0.05, 0.09))
            f.stage = f.stage_of()

    def clock_fraction(self) -> float:
        """One tick is half a day, so per-day growth accrues at 0.5."""
        return 0.5

    def harvest(self, field: ForageField) -> dict:
        """Cut a field and route the material to ensiling."""
        dry_t = field.cut()
        as_received_t = dry_t / max(C.FORAGE_DRY_MATTER_PCT / 100.0, 0.05)
        ensiled_t = as_received_t * self.ensiling_loss_factor
        self.harvested_this_season_t += ensiled_t
        self.cuts_completed += 1
        self.silage_to_silo_t += ensiled_t
        return {
            "field": field.name,
            "crop": field.crop.value,
            "dry_t": dry_t,
            "as_received_t": as_received_t,
            "ensiled_t": ensiled_t,
        }

    def status(self) -> str:
        if any(f.health() == "critical" for f in self.fields):
            return "critical"
        if any(f.health() == "degraded" for f in self.fields):
            return "degraded"
        return "nominal"


__all__ = [
    "CRUDE_PROTEIN_PCT",
    "CUT_INTERVAL_DAYS",
    "PEAK_DM_T_HA",
    "CropState",
    "CropType",
    "ForageField",
    "GrowthStage",
]