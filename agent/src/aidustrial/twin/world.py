"""Layer 1 - Sensory Cortex: the world container.

Binds environment + herd + logistics into one coherent simulation. This is the
single object the tool layer reads from. It also owns the SCENARIO driver -- the
demo needs a designed narrative arc, not random noise, so that a judge watching
five minutes sees the agents escalate on something real.

Scenario arc (`heatwave` -- the default):
  day 0-2    baseline. EHL touches 'mild' around solar noon. Agents observe.
  day 3      pump 7 at well-field 2 fails -> pivot 3 loses pressure, bearing temp
             climbs. Maintenance agent territory.
  day 4      heatwave: EHL sustained 'moderate' at solar noon. Only 4 of 8 Phase 1
             barns have misting hardware, so the veterinarian's job is NOT
             "turn cooling on" but "CHOOSE which barns get water" -- a scarcity
             decision that only a human should make.
  day 5-6    rumination deficit and milk yield loss compound. If the director
             allocates misting to the worst-hit barns, the loss is contained to
             the four barns with no hardware. If he declines, it spreads herd-wide.
  day 7+     recovery or escalation depending on recorded decisions.

NOTE ON WHAT THE REAL SCARCITY IS. It is tempting to frame this as "cooling
water competes with irrigation water for the aquifer". The arithmetic does not
support that framing and we should not pretend otherwise:
    4 misting banks   = 53 m3/h
    6 centre pivots   = 27,143 m3/h
    33,250 cows drinking = ~111 m3/h
So misting is 0.2% of pivot draw and ~48% of Phase 1 herd drinking water. It is
material against *drinking* demand at Phase 1 scale, and negligible against
irrigation. The genuine contests are (a) herd drinking water vs the annual
aquifer envelope, and (b) pivot allocation across fields to keep the projected
annual draw inside budget. Misting is constrained by HARDWARE, not water.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..agents.mesh import Blackboard
from . import constants as C
from .clock import SimClock
from .crops import CropState
from .environment import EnvironmentState
from .herd import HerdState
from .livestock import LivestockState
from .logistics import LogisticsState
from .milk import MilkState

Scenario = str


@dataclass
class World:
    """The whole simulated facility."""

    seed: int = 20260911
    scenario: Scenario = "heatwave"
    env: EnvironmentState = field(init=False)
    crops: CropState = field(init=False)
    herd: HerdState = field(init=False)
    livestock: LivestockState = field(init=False)
    milk: MilkState = field(init=False)
    log: LogisticsState = field(init=False)
    #: The powder plant is not commissioned until the real timeline's first
    #: production in late 2027, so it is opt-in during the demo.
    powder_live: bool = False
    _rng: random.Random = field(init=False, repr=False)
    event_log: list[dict] = field(default_factory=list)
    #: The agent blackboard. Held on the world because it is session-scoped
    #: live state, not graph state -- the checkpointer serialises every channel
    #: and a running thread would be meaningless to deserialise.
    board: Blackboard = field(default_factory=Blackboard)
    #: (action, target) -> tick, so the orchestrator can suppress an immediate
    #: re-proposal of something it just did. A repair that is working does not
    #: need asking about again five minutes later.
    recent_actions: dict[tuple[str, str], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self.env = EnvironmentState.initial(self.seed)
        self.crops = CropState.initial(self.seed)
        self.herd = HerdState.initial(self.seed)
        self.livestock = LivestockState.initial(self.seed)
        self.milk = MilkState()
        self.log = LogisticsState.initial(self.seed)
        # Keep all three clocks in lockstep.
        self.log.clock = self.env.clock
        self.herd.clock = self.env.clock

    # --- clock ---------------------------------------------------------

    @property
    def clock(self) -> SimClock:
        return self.env.clock

    @property
    def day(self) -> int:
        return self.env.clock.day

    @property
    def thi(self) -> float:
        """Air THI only -- kept for display so judges see dry-air advantage."""
        return self.env.th_i()

    def acted_recently(self, action: str, target: str, within_ticks: int = 24) -> bool:
        """True if this exact action was performed on this target recently."""
        last = self.recent_actions.get((action, target))
        return last is not None and (self.env.clock.tick - last) < within_ticks

    @property
    def solar_exposure(self) -> float:
        """Fraction of the cow's day spent unshaded.

        Barns shade the herd; the parlour approach, holding area and water trough
        do not. Under a heatwave cows move more slowly and linger, so cumulative
        radiant exposure rises -- this is the mechanism by which dry-desert heat
        still causes dairy heat stress despite a low air THI.
        """
        if 4 <= self.day <= 6:
            return 0.82
        return 0.55

    @property
    def ehl(self) -> float:
        """Effective Heat Load (air THI + exposure-weighted radiant load)."""
        return self.env.clock.effective_heat_load(self.env.day_weather, self.solar_exposure)

    # --- scenario injection --------------------------------------------

    def _apply_scenario(self) -> None:
        if self.scenario != "heatwave":
            return
        d = self.day

        # Day 3: irrigation pump failure at well-field 2.
        if d == 3 and self.env.clock.hour == 9:
            p3 = next(p for p in self.env.pivots if p.pid == 3)
            p3.nozzles_blocked = 14
            p3.bearing_temp_c += 12.0
            p3.vibration_mm_s += 4.2
            self._emit(
                "asset_fault",
                f"{p3.name}: pump cavitation at well-field 2, nozzles blocked",
                severity="high",
            )

        # Day 4: sustained heatwave. Days 4-6 run ~4C above normal peak.
        if 4 <= d <= 6:
            self.env.day_weather = 1.16
            if d == 4 and self.env.clock.hour == 8:
                self._emit(
                    "weather",
                    "Regional heatwave: forecast peak +4.8C above seasonal mean for 72h",
                    severity="high",
                )
        else:
            self.env.day_weather = 1.0

        # Day 6: siltation in the feed conveyor if not maintained.
        if d == 6 and self.env.clock.hour == 13:
            s = self.log.silos[0]
            s.inlet_operational = False
            self._emit(
                "conveyor",
                f"Silo {s.sid}: inlet conveyor stalled, siltation suspected",
                severity="medium",
            )

    def _emit(self, kind: str, message: str, severity: str = "info") -> None:
        self.event_log.append(
            {
                "tick": self.env.clock.tick,
                "time": self.env.clock.iso,
                "kind": kind,
                "message": message,
                "severity": severity,
            }
        )

    # --- simulation ----------------------------------------------------

    def step(self) -> dict:
        """Advance one tick. Returns the observation packet agents will read."""
        self._apply_scenario()

        ehl_before = self.ehl
        headcount = self.herd.herd_total_head()

        # Environment first -- it determines heat load which the herd responds to.
        self.env.tick(self._rng)

        # CROP PRODUCTION: growth is gated on the soil moisture the pivots
        # actually delivered this tick.
        soil_by_pivot = {p.pid: p.soil_moisture_pct for p in self.env.pivots}
        self.crops.tick(self._rng, soil_by_pivot, ehl_before)

        # LIVESTOCK
        feed_available = self.log.feed_hours_of_cover() >= 24.0
        self.herd.tick(self._rng, ehl_before, self.env.day_weather)
        self.livestock.tick(self._rng, ehl_before, feed_available)

        # MILK PRODUCTION: capture what the lactating herd produced.
        herd_scc = self._herd_scc()
        self.milk.tick(self._rng, headcount, herd_scc, self.powder_live)

        self.log.tick(self._rng, headcount, herd_alive=headcount > 0)

        # Route harvested forage into the silos when a field reaches its cut
        # interval and a machine is available to take it off.
        if self._harvest_available:
            for f in self.crops.ready_fields():
                res = self.crops.harvest(f)
                self.log.silage_to_silo_t += res["ensiled_t"]
                self._emit(
                    "harvest",
                    f"{res['field']} cut: {res['dry_t']:.1f} t DM ({res['crop']}) -> "
                    f"{res['ensiled_t']:.1f} t ensiled",
                    severity="info",
                )

        return self.observe()

    def _herd_scc(self) -> float:
        """Herd somatic cell count, driven by the mastitis burden in the barns."""
        groups = self.herd.groups or []
        if not groups:
            return 120.0
        burden = sum(g.mastitis_cases for g in groups) / max(
            sum(g.head for g in groups) / 100.0, 1.0
        )
        return max(90.0, 150.0 + burden * 2.2)

    @property
    def _harvest_available(self) -> bool:
        """Forage equipment is shared with the maintenance crew. A degraded
        fleet means cutting waits, which is a real forage-loss mechanism."""
        return sum(1 for p in self.env.pivots if p.health() != "critical") >= 4

    def observe(self) -> dict:
        """The sensory packet. This is exactly what Layer 1 tools expose."""
        head = self.herd.herd_total_head()
        return {
            "tick": self.env.clock.tick,
            "time": self.env.clock.iso,
            "day": self.day,
            "hour": round(self.env.clock.hour, 2),
            "phase": self.env.clock.phase,
            "environment": {
                "temperature_c": round(self.env.temperature_c(), 2),
                "relative_humidity_pct": round(self.env.relative_humidity(), 1),
                "thi_air": round(self.thi, 2),
                "solar_load": round(self.env.clock.solar_load(self.env.day_weather, self.solar_exposure), 2),
                "solar_exposure": self.solar_exposure,
                "effective_heat_load": round(self.ehl, 2),
                "heat_stress_band": heat_stress_band(self.ehl),
                "wind_kmh": round(self.env.clock.wind_kmh(), 1),
                "soil_moisture_pct": [round(p.soil_moisture_pct, 2) for p in self.env.pivots],
                "soil_ph": round(self.env.soil_ph, 2),
                "soil_salinity_ds_m": round(self.env.soil_salinity_ds_m, 3),
                "aquifer_budget_used_pct": round(100 * self.env.aquifer.budget_utilisation, 1),
                "aquifer_projected_annual_m3h": round(self.env.aquifer.projected_annual_m3h, 1),
                "aquifer_remaining_pct": round(100 * self.env.aquifer.remaining_fraction, 3),
                "aquifer_status": self.env.aquifer.status(),
                "water_use_m3h": round(self.env.water_use_m3h(), 1),
                "misters_on": self.env.misters_on,
                "pivots": [
                    {
                        "name": p.name,
                        "field_ha": round(p.field_ha, 1),
                        "running": p.running,
                        "soil_moisture_pct": round(p.soil_moisture_pct, 2),
                        "bearing_temp_c": round(p.bearing_temp_c, 1),
                        "vibration_mm_s": round(p.vibration_mm_s, 2),
                        "motor_hours": round(p.motor_hours, 1),
                        "nozzles_blocked": p.nozzles_blocked,
                        "health": p.health(),
                    }
                    for p in self.env.pivots
                ],
            },
            "herd": {
                "head": head,
                "herd_targets_met": head >= C.HERD_PHASE1_BUILT,
                "rumination_mean_min": round(
                    sum(g.rumination_min for g in self.herd.groups) / max(len(self.herd.groups), 1), 1
                ),
                "rumination_deficit_pct": round(self.herd.rumination_deficit_pct(), 2),
                "milk_loss_today_kg": round(self.herd.milk_loss_today_kg(), 1),
                "groups": [
                    {
                        "name": g.name,
                        "barn": g.barn_id,
                        "head": g.head,
                        "rumination_min": round(g.rumination_min, 1),
                        "rumination_pct": round(g.rumination_pct, 1),
                        "body_temp_c": round(g.body_temp_c, 2),
                        "resp_rate": g.resp_rate,
                        "milk_kg_day": round(g.milk_kg_day, 2),
                        "milk_yield_pct": round(g.milk_yield_pct, 1),
                        "heat_stress": g.heat_stress_severity,
                        "heat_abatement_active": g.heat_abatement_active,
                        "cooling_effective_pct": round(100 * g.cooling_effective, 1),
                        "misters_available": g.misters_available,
                        "misting_enabled": g.misting_enabled,
                        "mastitis_cases": g.mastitis_cases,
                        "lameness_cases": g.lameness_cases,
                        "mortality_24h": g.mortality_24h,
                        "status": g.status(),
                    }
                    for g in self.herd.groups
                ],
            },
            "logistics": {
                "feed_total_t": round(self.log.total_feed_t(), 1),
                "feed_hours_of_cover": round(self.log.feed_hours_of_cover(), 1),
                "daily_demand_t": round(self.log.daily_feed_demand_t, 2),
                "purchased_feed_t": round(self.log.purchased_feed_t, 1),
                "airlift": {
                    "state": self.log.airlift.state,
                    "delivered": int(self.log.airlift.delivered),
                    "target": self.log.airlift.total_cows,
                    "progress_pct": round(self.log.airlift.progress_pct, 2),
                    "flights_completed": self.log.airlift.flights_completed,
                },
                "silos": [
                    {
                        "name": s.sid,
                        "feed_type": s.feed_type,
                        "fill_t": round(s.fill_t, 1),
                        "fill_pct": round(s.fill_pct, 1),
                        "hours_of_cover": round(s.hours_of_cover(self.log.daily_feed_demand_t), 1),
                        "inlet_operational": s.inlet_operational,
                        "inlet_type": s.inlet_type,
                        "status": s.status(self.log.daily_feed_demand_t),
                    }
                    for s in self.log.silos
                ],
                "tankers": [
                    {
                        "name": t.tid,
                        "lat": round(t.lat, 5),
                        "lon": round(t.lon, 5),
                        "load_kg": round(t.load_kg, 1),
                        "fill_pct": round(t.fill_pct, 1),
                        "coolant_temp_c": round(t.coolant_temp_c, 2),
                        "leg": t.status_,
                        "status": t.status(),
                    }
                    for t in self.log.tankers
                ],
            },
            "crop_production": {
                "standing_t": self.crops.standing_t(),
                "harvested_t": self.crops.harvested_this_season_t,
                "cuts_completed": self.crops.cuts_completed,
                "protein_pct": self.crops.protein_pct(),
                "water_stressed_ha": self.crops.water_stressed_ha(),
                "annual_target_t": C.FORAGE_TONNES_ANNUAL_TARGET,
                "status": self.crops.status(),
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
                                (p.soil_moisture_pct for p in self.env.pivots if p.pid == f.pivot_id),
                                0.0,
                            ),
                            2,
                        ),
                        "ready_for_cut": f.ready_for_cut,
                        "water_stress_days": f.water_stress_days,
                        "health": f.health(),
                    }
                    for f in self.crops.fields
                ],
            },
            "livestock": {
                "total_head": head + self.livestock.total_youngstock(),
                "lactating_head": head,
                "non_productive_head": self.livestock.total_youngstock(),
                "by_class": self.livestock.head_by_class(),
                "airlift_head": sum(self.livestock.airlift_mix.values()),
                "airlift_mix": self.livestock.airlift_mix,
                "calf_mortality_7d": sum(
                    g.mortality_7d
                    for g in self.livestock.youngstock
                    if g.group_class.value == "calf"
                ),
                "status": self.livestock.status(),
                "calvings": [
                    {
                        "group_id": c.group_id,
                        "calvings": c.calvings,
                        "difficult_births": c.difficult_births,
                        "stillbirths": c.stillbirths,
                    }
                    for c in self.livestock.calvings
                ],
                "heifers": [
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
                    for g in self.livestock.youngstock
                    if g.group_class.value == "heifer"
                ],
                "calves": [
                    {
                        "group_id": g.group_id,
                        "head": g.head,
                        "age_days": round(g.age_days, 1),
                        "avg_weight_kg": round(g.avg_weight_kg, 1),
                        "scours_rate_pct": round(100 * g.scours_cases / max(g.head, 1), 2),
                        "mortality_7d": g.mortality_7d,
                        "status": g.status(),
                    }
                    for g in self.livestock.youngstock
                    if g.group_class.value == "calf"
                ],
                "dry_cows": [
                    {
                        "group_id": g.group_id,
                        "head": g.head,
                        "days_to_calving": round(g.days_to_first_calving, 1),
                        "bcs": g.body_condition_score,
                        "status": g.status(),
                    }
                    for g in self.livestock.dry_cows()
                ],
            },
            "milk_production": {
                "daily_milk_kg": self.milk.daily_milk_kg,
                "daily_shipped_kg": self.milk.daily_shipped_kg,
                "daily_loss_kg": self.milk.daily_loss_kg,
                "capture_ratio": self.milk.capture_ratio(),
                "lactating_head": head,
                "milkings_per_day": self.milk.parlour.milkings_per_day,
                "units": self.milk.parlour.units,
                "throughput_cows_per_hour": self.milk.parlour.throughput_cows_per_hour,
                "downtime_min_24h": self.milk.parlour.downtime_min_24h,
                "bulk_temp_c": self.milk.tank.milk_temp_c,
                "bulk_tank_kg": self.milk.tank.level_kg,
                "bulk_fill_pct": self.milk.tank.fill_pct,
                "condenser_fouling_pct": self.milk.tank.condenser_fouling_pct,
                "bulk_scc_k": self.milk.bulk_scc_k,
                "scc_limit_k": 200.0,
                "quality_status": self.milk.quality_status(),
                "silo_fill_pct": self.milk.plant.silo_fill_pct,
                "powder_live": self.milk.plant.running,
                "status": self.milk.status(),
            },
            "board": [
                {
                    "message_id": m.message_id,
                    "kind": m.kind,
                    "sender": m.sender,
                    "recipient": m.recipient,
                    "content": m.content,
                    "in_reply_to": m.in_reply_to,
                    "severity": m.severity,
                    "domains": m.domains,
                    "expects_reply": m.expects_reply,
                }
                for m in self.board.messages
            ],
            "events": self.event_log[-14:],
        }

    # --- actuation (only the gate-approved ones) -----------------------

    def apply_action(self, action: str, target: str = "") -> str:
        """Mutate the world. Called ONLY after human approval."""
        self.recent_actions[(action, target)] = self.env.clock.tick
        if action in ("enable_misters", "stop_misters"):
            want = action == "enable_misters"
            targets = [t.strip() for t in target.split(",") if t.strip()]
            hit, blocked = [], []
            for g in self.herd.groups:
                if targets and g.name not in targets:
                    continue
                if not g.misters_available:
                    blocked.append(g.name)
                    continue
                g.misting_enabled = want
                hit.append(g.name)
            active = sum(1 for g in self.herd.groups if g.misting_enabled)
            self.env.mist_flow_lpm = C.MISTER_FLOW_LPM * active
            self.env.misters_on = active > 0
            self.env.aquifer.projected_annual_m3h = self.env.water_use_m3h()
            msg = f"Misting {'ON' if want else 'OFF'} for {len(hit)} barn(s): {', '.join(hit) or '-'}"
            if blocked:
                msg += f" | NO HARDWARE in {', '.join(blocked)}"
            return msg

        if action in ("start_pivot", "stop_pivot", "repair_pivot"):
            names = [t.strip() for t in target.split(",") if t.strip()]
            hit = []
            for p in self.env.pivots:
                if names and p.name not in names:
                    continue
                hit.append(p.name)
                if action == "start_pivot":
                    p.running = True
                elif action == "stop_pivot":
                    p.running = False
                else:
                    # Return the unit to a genuinely healthy state: grease
                    # restored, nozzles cleared, alignment re-trued. Scaling the
                    # old readings down leaves a hot bearing still over the
                    # warning limit, so the same fault re-fires next tick.
                    p.nozzles_blocked = 0
                    p.bearing_temp_c = self.env._ambient_bearing_target() * 0.52
                    p.vibration_mm_s = 2.1
            if action == "repair_pivot":
                return (
                    f"Repaired {len(hit)} pivot(s) ({', '.join(hit)}): nozzles cleared, "
                    "bearings cooled, vibration reset."
                )
            self.env.aquifer.projected_annual_m3h = self.env.water_use_m3h()
            verb = "started" if action == "start_pivot" else "stopped"
            return (
                f"{verb.capitalize()} {len(hit)} pivot(s): {', '.join(hit)}. "
                f"Projected annual draw now {self.env.aquifer.projected_annual_m3h:.0f} m3/h "
                f"({self.env.aquifer.budget_utilisation * 100:.0f}% of envelope)."
            )

        if action == "transfer_water":
            src, dst = (target.split(">") + ["", ""])[:2]
            for p in self.env.pivots:
                if p.name == src:
                    p.running = False
                if p.name == dst:
                    p.running = True
            return f"Water diverted {src} -> {dst}"

        if action == "shed_pivot":
            names = [t.strip() for t in target.split(",") if t.strip()]
            stopped = []
            for p in self.env.pivots:
                if not p.running:
                    continue
                if not names or p.name in names:
                    p.running = False
                    stopped.append(p.name)
            self.env.mist_flow_lpm = sum(
                C.MISTER_FLOW_LPM for g in self.herd.groups if g.misting_enabled
            )
            return (
                f"Shed rotation: stopped {len(stopped)} pivot(s) "
                f"({', '.join(stopped) or 'none running'}). Projected annual draw now "
                f"{self.env.aquifer.projected_annual_m3h:.0f} m3/h."
            )

        if action == "repair_pivot":
            for p in self.env.pivots:
                if p.name == target:
                    p.nozzles_blocked = 0
                    p.bearing_temp_c *= 0.72
                    p.vibration_mm_s *= 0.55
                    return f"{p.name} repaired: nozzles cleared, bearing cooled"

        # --- CROP PRODUCTION ---
        if action == "harvest_field":
            ids = [t.strip() for t in target.split(",") if t.strip()]
            out = []
            for f in self.crops.fields:
                if ids and f.name not in ids and f.field_id not in ids:
                    continue
                if f.biomass_t_ha < 2.5:
                    out.append(f"{f.name}: nothing worth cutting ({f.biomass_t_ha:.1f} t/ha)")
                    continue
                res = self.crops.harvest(f)
                self.log.silage_to_silo_t += res["ensiled_t"]
                out.append(f"{res['field']} {res['dry_t']:.0f} t DM -> {res['ensiled_t']:.0f} t ensiled")
                self._emit("harvest", f"{res['field']} cut: {res['dry_t']:.1f} t DM ({res['crop']})", "info")
            return "; ".join(out) or "no fields matched"

        # --- MILK PRODUCTION ---
        if action == "service_parlour":
            self.milk.parlour.downtime_min_24h = max(
                0.0, self.milk.parlour.downtime_min_24h - 25.0
            )
            return f"Parlour serviced; downtime now {self.milk.parlour.downtime_min_24h:.0f} min/24h"

        if action == "clean_condenser":
            self.milk.tank.condenser_fouling_pct = 6.0
            self.milk.tank.milk_temp_c = min(self.milk.tank.milk_temp_c, 3.8)
            return f"Condenser cleaned; bulk tank now {self.milk.tank.milk_temp_c:.1f}C"

        if action == "cull_chronic_mastitis":
            removed = 0
            for g in self.herd.groups:
                if g.mastitis_cases > 0:
                    removed += min(g.mastitis_cases, max(1, g.head // 500))
                    g.mastitis_cases = max(0, g.mastitis_cases - max(1, g.head // 500))
                    g.head = max(0, g.head - max(1, g.head // 500))
            self.milk.bulk_scc_k = max(120.0, self.milk.bulk_scc_k - 40.0)
            return f"Culled {removed} chronic mastitis case(s); bulk SCC now {self.milk.bulk_scc_k:.0f}k"

        if action == "halt_intake":
            self.milk.plant.running = False
            return "Powder intake halted to protect the silo from overfill"

        # --- LIVESTOCK ---
        if action == "isolate_calves":
            ids = [t.strip() for t in target.split(",") if t.strip()]
            out = []
            for g in self.livestock.youngstock:
                if ids and g.group_id not in ids:
                    continue
                if g.scours_cases == 0 and g.group_class.value != "calf":
                    continue
                g.scours_cases = max(0, g.scours_cases - max(1, g.scours_cases // 2))
                g.mortality_7d = max(0, g.mortality_7d - 1)
                g.treatment_success_pct = min(99.0, g.treatment_success_pct + 3.0)
                out.append(f"{g.group_id} isolated ({g.head:,} hd)")
            return "; ".join(out) or "no calf groups matched"

        if action == "boost_heifer_rations":
            for g in self.livestock.youngstock:
                if g.group_class.value == "heifer":
                    g.daily_gain_kg = min(g.daily_gain_kg + 0.25, 1.3)
                    g.body_condition_score = min(5.0, g.body_condition_score + 0.15)
            return "Heifer rations boosted; growth rate and body condition lifted across heifer groups"

        if action == "restart_inlet":
            for s in self.log.silos:
                if s.sid == target:
                    s.inlet_operational = True
                    return f"Silo {s.sid} inlet restarted"

        if action == "reroute_convoy":
            return f"Convoy rerouted: {target}"

        if action == "shed_load":
            return f"Shed load on {target}: shedding 8% of throughput to protect herd"

        if action == "quarantine_group":
            return f"{target} flagged for veterinary quarantine protocol"

        return f"no-op: unknown action {action}"


def heat_stress_band(thi: float) -> str:
    if thi >= C.THI_HEAT_STRESS_SEVERE:
        return "severe"
    if thi >= C.THI_HEAT_STRESS_MODERATE:
        return "moderate"
    if thi >= C.THI_HEAT_STRESS_ONSET:
        return "mild"
    return "none"


__all__ = ["Scenario", "World", "heat_stress_band"]