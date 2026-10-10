"""Layer 0 - LIVESTOCK.

Herd structure, reproduction, and youngstock. `herd.py` owns the physiology of
a lactating animal under heat load; this module owns who is in which class, how
the herd reproduces, and what happens to the animals that are not yet milking.

THE POINT THAT MATTERS MOST FOR ADRAR: the 30,000 head arriving from the United
States by air are overwhelmingly HEIFERS, not mature lactating cows. A Holstein
heifer does not calve until 22-24 months and does not enter the milking parlour
until roughly 18 months after landing. So the herd build-out consumes feed and
water for well over a year before it produces a single litre of saleable milk.

That is the real economics of this project, and it is invisible if you only
model lactating cows. It is encoded here as AIRLIFT_ARRIVAL_CLASS.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from . import constants as C


class HerdClass(str, Enum):
    LACTATING = "lactating"
    DRY = "dry"
    HEIFER = "heifer"       # post-weaning, pre-calving
    CALF = "calf"           # pre-weaning
    BULL = "bull"


#: What actually arrives in the airlift. Livestock exporters sell breeding
#: animals: predominantly pregnant heifers, plus some dry cows.
AIRLIFT_ARRIVAL_CLASS: dict[str, float] = {
    HerdClass.HEIFER: 0.72,
    HerdClass.DRY: 0.22,
    HerdClass.BULL: 0.06,
}

#: Months from landing to first calving for an arriving heifer.
HEIFER_AGE_AT_FIRST_CALVING_M = 23
#: A heifer arriving already pregnant carries most of that interval already.
HEIFER_PREGNANCY_DAYS_ON_ARRIVAL = 150
#: From calving to first milk entering the parlour.
CALVING_TO_FIRST_MILK_D = 4

#: Days in milk when a lactation begins.
DRY_PERIOD_D = 60

#: Biological norms used as escalation baselines.
AGE_FIRST_CALVING_TARGET_M = 23
CALVING_INTERVAL_TARGET_D = 365
CALF_PREWEANING_MORTALITY_PCT = 4.5
SCC_LIMIT_K = 200.0          # EU bulk milk somatic cell count limit
SCC_MASTITIS_RISK_K = 250.0


@dataclass
class HerdClassGroup:
    """A group of animals in a non-lactating class."""

    group_id: str
    group_class: HerdClass
    head: int
    barn_id: str

    # --- growth / age ---
    age_days: float = 0.0
    avg_weight_kg: float = 0.0
    daily_gain_kg: float = 0.0
    target_weight_kg: float = 0.0

    # --- health ---
    mortality_7d: int = 0
    scours_cases: int = 0
    respiratory_cases: int = 0
    treatment_cases: int = 0
    treatment_success_pct: float = 88.0
    body_condition_score: float = 3.0

    # --- reproduction (heifers and dry cows) ---
    days_to_first_calving: float = 0.0
    pregnancy_confirmed: bool = False
    days_open: float = 0.0
    conception_rate_pct: float = 92.0

    # --- calves ---
    age_at_weaning_d: int = 60
    weaning_age_d: float = 0.0

    @property
    def name(self) -> str:
        return f"YNG-{self.group_id}"

    @property
    def is_productive(self) -> bool:
        """Only lactating animals produce saleable milk."""
        return self.group_class is HerdClass.LACTATING

    def status(self) -> str:
        if self.group_class is HerdClass.CALF:
            if self.mortality_7d > max(2, self.head * 0.004):
                return "critical"
            if self.scours_cases > self.head * 0.06:
                return "degraded"
        if self.group_class in (HerdClass.HEIFER, HerdClass.DRY):
            if self.body_condition_score < 2.5:
                return "degraded"
            if self.body_condition_score < 2.0:
                return "critical"
            # Heifers drifting past the age-at-first-calving target is a
            # compounding cost: they eat for a year and calve late.
            if (
                self.group_class is HerdClass.HEIFER
                and self.age_days / 30.4 > AGE_FIRST_CALVING_TARGET_M + 2
            ):
                return "degraded"
        if self.mortality_7d > max(1, self.head * 0.002):
            return "degraded"
        return "nominal"


@dataclass
class CalvingRecord:
    group_id: str
    calvings: int
    difficult_births: int
    stillbirths: int
    last_calving_tick: int


@dataclass
class LivestockState:
    """Whole-herd structure: lactating barns plus youngstock classes."""

    youngstock: list[HerdClassGroup] = field(default_factory=list)
    calvings: list[CalvingRecord] = field(default_factory=list)
    #: Head delivered by the airlift, broken out by arrival class.
    airlift_mix: dict[str, int] = field(default_factory=dict)
    open_heifers_not_calving_90d: int = 0
    total_conception_failures: int = 0

    @classmethod
    def initial(cls, seed: int = 20260911) -> LivestockState:
        # `seed` is accepted for interface parity with the other subsystems; the
        # opening herd structure is deliberately fixed so the demo always starts
        # from the same documented position.
        del seed
        st = cls()

        st.youngstock = [
            HerdClassGroup(
                group_id="H1", group_class=HerdClass.HEIFER, head=6_400,
                barn_id="BARN-H1", age_days=470, avg_weight_kg=445,
                daily_gain_kg=0.62, target_weight_kg=570,
                days_to_first_calving=HEIFER_AGE_AT_FIRST_CALVING_M * 30.4,
                pregnancy_confirmed=True,
            ),
            HerdClassGroup(
                group_id="H2", group_class=HerdClass.HEIFER, head=6_100,
                barn_id="BARN-H2", age_days=300, avg_weight_kg=340,
                daily_gain_kg=0.78, target_weight_kg=570,
                days_to_first_calving=HEIFER_AGE_AT_FIRST_CALVING_M * 30.4 + 170,
                pregnancy_confirmed=False,
            ),
            HerdClassGroup(
                group_id="C1", group_class=HerdClass.CALF, head=3_800,
                barn_id="BARN-C1", age_days=22, avg_weight_kg=61,
                daily_gain_kg=0.91, target_weight_kg=200,
                weaning_age_d=22,
            ),
            HerdClassGroup(
                group_id="D1", group_class=HerdClass.DRY, head=1_950,
                barn_id="BARN-D1", age_days=1_100, avg_weight_kg=635,
                body_condition_score=3.1, days_to_first_calving=DRY_PERIOD_D,
                pregnancy_confirmed=True,
            ),
            HerdClassGroup(
                group_id="B1", group_class=HerdClass.BULL, head=48,
                barn_id="BARN-B1", age_days=900, avg_weight_kg=1_050,
                target_weight_kg=1_150, body_condition_score=3.4,
            ),
        ]
        st.airlift_mix = {
            "heifer": 4_600,
            "dry": 1_400,
            "bull": 20,
        }
        return st

    # --- perception ----------------------------------------------------

    def head_by_class(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for g in self.youngstock:
            out[g.group_class.value] = out.get(g.group_class.value, 0) + g.head
        return out

    def total_youngstock(self) -> int:
        return sum(g.head for g in self.youngstock)

    def non_productive_head(self) -> int:
        """Head that consumes feed but produces no milk."""
        return sum(g.head for g in self.youngstock)

    def heifer_growth_deficit(self) -> list[HerdClassGroup]:
        """Heifers missing target breeding weight."""
        return [g for g in self.youngstock
                if g.group_class is HerdClass.HEIFER and g.avg_weight_kg < g.target_weight_kg * 0.88]

    def critical_youngstock(self) -> list[HerdClassGroup]:
        return [g for g in self.youngstock if g.status() in ("critical",)]

    def dry_cows(self) -> list[HerdClassGroup]:
        return [g for g in self.youngstock if g.group_class is HerdClass.DRY]

    # --- physics -------------------------------------------------------

    def tick(self, rng: random.Random, ehl: float, feed_available: bool) -> None:
        for g in self.youngstock:
            # Growth stalls without feed, and heat load depresses ADG in
            # replacement stock as surely as in lactating cows.
            if not feed_available:
                g.daily_gain_kg = 0.0
                g.body_condition_score = max(1.0, g.body_condition_score - 0.01)
            else:
                heat_penalty = max(0.0, 1.0 - max(0.0, ehl - C.THI_HEAT_STRESS_ONSET) / 60.0)
                base_gain = {
                    HerdClass.CALF: 0.95,
                    HerdClass.HEIFER: 0.78,
                    HerdClass.DRY: 0.0,
                    HerdClass.BULL: 0.55,
                }.get(g.group_class, 0.6)
                g.daily_gain_kg = max(0.0, base_gain * heat_penalty + rng.uniform(-0.03, 0.03))

            g.avg_weight_kg += g.daily_gain_kg * 0.5  # half-day tick
            g.age_days += 0.5

            # Youngstock disease pressure.
            if g.group_class is HerdClass.CALF:
                g.scours_cases = max(
                    0,
                    g.scours_cases + int(rng.random() < 0.05 * (1.4 if ehl > 70 else 1.0)),
                )
                g.respiratory_cases = max(
                    0, g.respiratory_cases + int(rng.random() < 0.03)
                )
                g.mortality_7d = max(0, g.mortality_7d + int(rng.random() < 0.012))
                g.weaning_age_d = min(g.age_at_weaning_d, g.age_days)
                if g.age_days >= g.age_at_weaning_d and g.group_class is HerdClass.CALF:
                    g.group_class = HerdClass.HEIFER  # transitions onward
            else:
                g.mortality_7d = max(0, g.mortality_7d + int(rng.random() < 0.003))

            g.treatment_success_pct = min(
                99.0, max(60.0, g.treatment_success_pct + rng.uniform(-1.2, 1.2))
            )

            # Body condition drifts with feed and heat.
            if not feed_available:
                g.body_condition_score = max(1.0, g.body_condition_score - 0.008)
            else:
                g.body_condition_score = min(
                    5.0, g.body_condition_score + rng.uniform(-0.004, 0.006)
                )

            # Reproduction.
            if g.group_class in (HerdClass.HEIFER, HerdClass.DRY):
                if g.pregnancy_confirmed:
                    if g.group_class is HerdClass.HEIFER:
                        g.days_to_first_calving = max(0.0, g.days_to_first_calving - 0.5)
                else:
                    g.days_open += 0.5
                    # Heifers under target breeding weight conceive later.
                    if (
                        g.group_class is HerdClass.HEIFER
                        and g.avg_weight_kg > g.target_weight_kg * 0.82
                        and rng.random() < 0.004
                    ):
                        g.pregnancy_confirmed = True
                        self.total_conception_failures += 1

        # Calving outcomes for dry cows coming to term.
        for g in self.dry_cows():
            if g.days_to_first_calving <= 0.0 and g.pregnancy_confirmed:
                rec = next((c for c in self.calvings if c.group_id == g.group_id), None)
                if rec is None:
                    self.calvings.append(
                        CalvingRecord(g.group_id, 0, 0, 0, 0)
                    )
                    rec = self.calvings[-1]
                rec.calvings += 1
                if rng.random() < 0.09:
                    rec.difficult_births += 1
                if rng.random() < 0.03:
                    rec.stillbirths += 1
                g.pregnancy_confirmed = False
                g.group_class = HerdClass.LACTATING
                g.days_open = 0.0

    def status(self) -> str:
        if any(g.status() == "critical" for g in self.youngstock):
            return "critical"
        if any(g.status() == "degraded" for g in self.youngstock):
            return "degraded"
        return "nominal"


__all__ = [
    "AGE_FIRST_CALVING_TARGET_M",
    "AIRLIFT_ARRIVAL_CLASS",
    "CALF_PREWEANING_MORTALITY_PCT",
    "CALVING_INTERVAL_TARGET_D",
    "SCC_LIMIT_K",
    "SCC_MASTITIS_RISK_K",
    "CalvingRecord",
    "HerdClass",
    "HerdClassGroup",
    "LivestockState",
]