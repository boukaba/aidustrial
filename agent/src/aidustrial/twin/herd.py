"""Layer 1 - Sensory Cortex: herd simulation.

Cows are aggregated into groups, not modelled individually. At 270,000 head,
per-cow fidelity is a fiction; what matters for operations is group-level
signal, and that is what the veterinarian actually reasons about.

The physiology model is deliberately simple but *causally correct*:
  THI -> heat load -> rumination suppression -> milk yield decline, mediated
  by cooling availability. The early-warning value comes from rumination moving
  BEFORE THI crosses the threshold, which is the real-world finding.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import constants as C
from .clock import SimClock

#: Rumination below this % of baseline = the veterinarian escalates. Declared
#: before HerdGroup because `HerdGroup.status()` reads it at call time.
BASELINE_RUMINATION_CRITICAL_PCT = 78.0


@dataclass
class HerdGroup:
    """A barn or pen as the veterinarian sees it."""

    gid: str
    head: int
    barn_id: str
    misters_available: int = 0
    fans_available: int = 0

    # --- physiology ---
    rumination_min: float = C.RUMINATION_BASELINE_MIN
    body_temp_c: float = 38.6
    resp_rate: int = 28
    milk_kg_day: float = 34.0  # baseline peak yield, avoids startup transient
    feed_intake_kg: float = 0.0
    water_intake_l: float = 0.0

    # --- health ---
    mastitis_cases: int = 0
    lameness_cases: int = 0
    mortality_24h: int = 0
    mortality_baseline_24h: int = 0
    heat_abatement_active: bool = False
    misting_enabled: bool = False
    cooling_effective: float = 0.0

    @property
    def name(self) -> str:
        return f"GRP-{self.gid}"

    @property
    def rumination_pct(self) -> float:
        return 100.0 * self.rumination_min / C.RUMINATION_BASELINE_MIN

    @property
    def heat_stress_severity(self) -> str:
        if self.body_temp_c >= 39.6:
            return "severe"
        if self.body_temp_c >= 39.1:
            return "moderate"
        if self.body_temp_c >= 38.9:
            return "mild"
        return "none"

    @property
    def milk_yield_pct(self) -> float:
        return 100.0 * self.milk_kg_day / max(self._baseline_yield, 1e-6)

    _baseline_yield: float = 34.0  # kg/day Holstein at peak, lactating

    def status(self) -> str:
        if self.mortality_24h > self.mortality_baseline_24h * 2.5 + 1:
            return "critical"
        if self.heat_stress_severity in ("severe",):
            return "critical"
        if self.rumination_pct < BASELINE_RUMINATION_CRITICAL_PCT:
            return "degraded"
        if self.heat_stress_severity == "moderate":
            return "degraded"
        return "nominal"


@dataclass
class HerdState:
    """Herd size ramps with the airlift schedule; groups appear as barns fill."""

    clock: SimClock = field(default_factory=SimClock)
    groups: list[HerdGroup] = field(default_factory=list)
    head_current: int = 0
    head_arrived_total: int = 0
    tick_in_service: int = 0

    @classmethod
    def initial(cls, seed: int = 20260911) -> HerdState:
        rng = random.Random(seed)
        herd = cls()
        # Phase 1: GCB built infrastructure for 33,250 head. Model 8 operational
        # barns of roughly that size, arriving as the airlift progresses.
        barn_sizes = [4200, 4200, 4150, 4150, 4150, 4150, 4200, 4050]
        for i, size in enumerate(barn_sizes):
            herd.groups.append(
                HerdGroup(
                    gid=f"B{i + 1:02d}",
                    head=size,
                    barn_id=f"BARN-{i + 1:02d}",
                    misters_available=4 if i < C.COOLING_MISTERS_INSTALLED else 0,
                    fans_available=24 if i < C.FAN_INSTALLED // 24 else 0,
                    rumination_min=C.RUMINATION_BASELINE_MIN + rng.uniform(-6, 6),
                    mortality_baseline_24h=1,
                )
            )
        return herd

    # --- perception ----------------------------------------------------

    def thi(self, day_weather: float = 1.0) -> float:
        return self.clock.th_i(day_weather)

    def herd_total_head(self) -> int:
        return sum(g.head for g in self.groups)

    def rumination_deficit_pct(self) -> float:
        """Population-weighted rumination shortfall vs baseline."""
        total = self.herd_total_head() or 1
        shortfall = sum(
            max(0.0, 100.0 - g.rumination_pct) * g.head for g in self.groups
        )
        return shortfall / total

    def milk_loss_today_kg(self) -> float:
        return sum(
            max(0.0, g._baseline_yield - g.milk_kg_day) * g.head for g in self.groups
        )

    # --- physics -------------------------------------------------------

    def tick(self, rng: random.Random, ehl: float, day_weather: float = 1.0) -> None:
        """Advance herd physiology given the site Effective Heat Load.

        `ehl` is air THI plus clear-sky solar load -- see SimClock.effective_heat_load.
        """
        self.tick_in_service += 1
        heat_index = max(0.0, ehl - C.THI_HEAT_STRESS_ONSET)

        for g in self.groups:
            # --- cooling availability ---
            has_cooling = bool(g.misters_available) and g.misting_enabled
            if has_cooling:
                # Evaporative cooling is near-adiabatic in DRY air. At ~10-18% RH
                # in Adrar, misting removes a large fraction of the cow's heat
                # load -- aridity is what makes the misters viable here, and the
                # same aridity that keeps air THI low is why the herd needs them.
                target_effect = 0.82
            elif g.fans_available:
                # Fans work by air speed alone; they help but cannot replace
                # evaporative cooling at these temperatures.
                target_effect = 0.34
            else:
                target_effect = 0.08
            g.cooling_effective += (target_effect - g.cooling_effective) * 0.30
            g.heat_abatement_active = g.cooling_effective > 0.35

            # --- heat accumulation ---
            heat_target = 38.6 + heat_index * 0.062 * (1.0 - g.cooling_effective)
            g.body_temp_c += (heat_target - g.body_temp_c) * 0.14
            g.body_temp_c += rng.uniform(-0.03, 0.05)

            # --- rumination: earliest observable signal ---
            rum_target = C.RUMINATION_BASELINE_MIN * (
                1.0 - heat_index * 0.022 * (1.0 - g.cooling_effective)
            )
            g.rumination_min += (rum_target - g.rumination_min) * 0.12
            g.rumination_min += rng.uniform(-2.5, 2.5)
            g.rumination_min = max(40.0, min(C.RUMINATION_BASELINE_MIN * 1.12, g.rumination_min))

            # --- milk yield ---
            loss_coef = C.THI_MILK_YIELD_LOSS_MILD
            if heat_index > C.THI_HEAT_STRESS_MODERATE - C.THI_HEAT_STRESS_ONSET:
                loss_coef = C.THI_MILK_YIELD_LOSS_SEVERE
            yield_target = g._baseline_yield * (
                1.0 - heat_index * loss_coef / 100.0 * (1.0 - g.cooling_effective * 0.75)
            )
            g.milk_kg_day += (yield_target - g.milk_kg_day) * 0.10
            g.milk_kg_day += rng.uniform(-0.3, 0.3)
            g.milk_kg_day = max(4.0, min(g._baseline_yield * 1.05, g.milk_kg_day))

            # --- intake & water ---
            g.feed_intake_kg = max(8.0, 24.0 - heat_index * 0.28 * (1 - g.cooling_effective))
            g.water_intake_l = 55.0 + 6.5 * max(0.0, ehl - 25.0)

            # --- morbidity ---
            if g.heat_stress_severity in ("moderate", "severe"):
                g.mastitis_cases = min(
                    g.head // 50,
                    g.mastitis_cases + int(rng.random() < 0.12),
                )
                g.lameness_cases = min(
                    g.head // 80,
                    g.lameness_cases + int(rng.random() < 0.05),
                )
                g.mortality_24h = g.mortality_baseline_24h + int(rng.random() < 0.18)
            else:
                g.mastitis_cases = max(0, g.mastitis_cases - int(rng.random() < 0.08))
                g.lameness_cases = max(0, g.lameness_cases - int(rng.random() < 0.05))
                g.mortality_24h = max(
                    g.mortality_baseline_24h - 1, g.mortality_baseline_24h - int(rng.random() < 0.2)
                )

        self.clock = self.clock.advance()

    def health_summary(self) -> str:
        statuses = {g.status() for g in self.groups}
        if "critical" in statuses:
            return "critical"
        if "degraded" in statuses:
            return "degraded"
        return "nominal"


__all__ = ["BASELINE_RUMINATION_CRITICAL_PCT", "HerdGroup", "HerdState"]