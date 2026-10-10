"""Layer 2 - The Specialist Agents.

Four agents, each with a narrow mandate, an explicit decision rule, and a bounded
memory. They do NOT talk to each other. The orchestrator (Layer 3) routes between
them, which is what keeps the graph inspectable.

Each agent returns zero or more `Action` proposals and zero or more `Finding`s.
They never mutate the world directly -- only the approved executor does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..tools import sensors
from ..tools.actions import Action, Finding, score_risk, score_urgency
from ..twin import constants as C
from .mesh import Blackboard, Kind, Message


@dataclass
class AgentMemory:
    """Bounded scratchpad.

    Bounded on purpose: an agent with unbounded memory will eventually narrate
    its own history back to itself instead of reading the site. Cap at 8.
    """

    agent: str
    entries: list[str] = field(default_factory=list)
    cap: int = 8

    def remember(self, line: str) -> None:
        if line in self.entries:
            return
        self.entries.append(line)
        if len(self.entries) > self.cap:
            self.entries.pop(0)

    def note(self, line: str) -> None:
        self.remember(line)

    def digest(self) -> str:
        if not self.entries:
            return "no prior observations"
        return " | ".join(self.entries[-3:])


# ---------------------------------------------------------------------------
# AGRONOMIST -- water and soil
# ---------------------------------------------------------------------------

AGRONOMIST_SYSTEM = """\
You are the AGRONOMIST for a 33,250-head dairy and fodder complex in Adrar,
Algerian Sahara. You own soil moisture and the pivot irrigation fleet.

MANDATE
  1. Keep soil moisture above the wilting point on every field.
  2. Keep projected annual groundwater draw inside the site's envelope.
  3. Diagnose pivot faults from bearing temperature, vibration and nozzle loss.

CONSTRAINTS YOU MUST RESPECT
  - The aquifer is NON-RENEWABLE fossil groundwater. A single wet year you cannot
    get back. Judge every irrigation proposal against projected ANNUAL draw, not
    against today's moisture reading.
  - Pivots are Valmont/AFKO hardware. Running a degraded pivot risks a cascade
    failure across the span; hand those to the maintenance agent.
  - You may propose water actions. You may not decide that the herd goes without.

ESCALATE when: any field hits wilting point, OR projected annual draw exceeds
85% of envelope, OR a pivot shows a fault signature.
"""


class AgronomistAgent:
    name = "agronomist"
    system_prompt = AGRONOMIST_SYSTEM
    memory = AgentMemory("agronomist")

    def run(self) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []

        water = sensors.get_water_budget()
        pivots = sensors.get_pivot_telemetry()

        # Only act on pivots whose current state makes the action meaningful.
        # Re-proposing "start PIVOT-1" after approving it is the classic agent
        # failure mode: it fills the human gate with noise and trains the
        # director to approve reflexively.
        wilted = [
            (p["name"], p["soil_moisture_pct"])
            for p in pivots
            if p["soil_moisture_pct"] <= C.SOIL_MOISTURE_WILTING_PCT and not p["running"]
        ]
        dry = [
            (p["name"], p["soil_moisture_pct"])
            for p in pivots
            if C.SOIL_MOISTURE_WILTING_PCT < p["soil_moisture_pct"] < C.SOIL_MOISTURE_OPTIMAL_PCT
        ]
        broken = [
            p for p in pivots
            if (p["nozzles_blocked"] > 8 or p["vibration_mm_s"] >= C.PIVOT_VIBRATION_WARN_MM_S)
            and p["nozzles_blocked"] > 0
        ]

        # Fields drying but not yet at wilting point are the leading indicator.
        # Surfacing them as information is what stops the agronomist only ever
        # reacting once the damage is done.
        if dry and not wilted:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"{len(dry)} field(s) trending toward wilting point "
                        f"({', '.join(f'{n} {p:.1f}%' for n, p in dry)}); "
                        f"threshold is {C.SOIL_MOISTURE_WILTING_PCT}%."
                    ),
                    severity="medium",
                    confidence=0.8,
                    evidence={"fields": [n for n, _ in dry]},
                    implies="monitor",
                )
            )

        # --- soil moisture ---
        for name, pct in wilted:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=f"{name} at wilting point ({pct:.1f}% moisture, threshold {C.SOIL_MOISTURE_WILTING_PCT}%).",
                    severity="high",
                    confidence=0.95,
                    evidence={"pivot": name, "soil_moisture_pct": pct},
                    implies="start_pivot",
                )
            )
            area = next(p["field_ha"] for p in pivots if p["name"] == name)
            actions.append(
                Action(
                    action="start_pivot",
                    target=name,
                    rationale=(
                        f"{name} has reached wilting point. Standing crop on "
                        f"{area:.0f} ha will lose yield this cycle if not irrigated."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(
                        severity="high",
                        water_m3h=area * 10_000 * 0.009,
                        resource_class="non_renewable_aquifer",
                    ),
                    severity="high",
                    urgency_score=score_urgency(decays_per_day=True),
                    evidence={"water_m3h": area * 10_000 * 0.009, "field_ha": area},
                    blast_radius=f"{area:.0f} ha of fodder production",
                    cost_of_inaction="Fodder yield loss compounding daily at this moisture deficit.",
                    reversible=True,
                )
            )
            self.memory.note(f"{name} hit wilting point at {pct:.1f}%")

        # --- aquifer envelope ---
        if water["budget_used_pct"] >= 85:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Projected annual draw is {water['budget_used_pct']:.0f}% of the "
                        f"{water['aquifer_kind']} envelope. Current allocation "
                        f"{water['water_use_m3h']:.0f} m3/h sustained for a year breaches the budget."
                    ),
                    severity="critical" if water["budget_used_pct"] >= 100 else "high",
                    confidence=0.9,
                    evidence=water,
                    implies="shed_pivot",
                )
            )
            actions.append(
                Action(
                    action="shed_pivot",
                    target=",".join(p["name"] for p in pivots if p["running"]) or "none",
                    rationale=(
                        f"At current allocation the site draws "
                        f"{water['projected_annual_m3h']:.0f} m3/h = "
                        f"{water['budget_used_pct']:.0f}% of the annual aquifer envelope. "
                        "Holding this for twelve months is not a sustainable plan."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(
                        severity="critical" if water["budget_used_pct"] >= 100 else "high",
                        water_m3h=water["water_use_m3h"],
                        resource_class="non_renewable_aquifer",
                    ),
                    severity="critical" if water["budget_used_pct"] >= 100 else "high",
                    urgency_score=score_urgency(window_closes=True),
                    evidence=water,
                    blast_radius="Fodder production programme; rotating irrigation affects every field.",
                    cost_of_inaction="Unrecoverable draw from a non-renewable aquifer.",
                    reversible=True,
                )
            )
            self.memory.note(f"aquifer at {water['budget_used_pct']:.0f}% of envelope")

        # --- fault handoff ---
        for p in broken:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"{p['name']} fault signature: {p['nozzles_blocked']} blocked nozzles, "
                        f"vibration {p['vibration_mm_s']:.1f} mm/s, bearing {p['bearing_temp_c']:.0f}C."
                    ),
                    severity="high",
                    confidence=0.85,
                    evidence=p,
                    implies="repair_pivot",
                )
            )
            actions.append(
                Action(
                    action="repair_pivot",
                    target=p["name"],
                    rationale=(
                        f"{p['name']} is distributing water unevenly ({p['nozzles_blocked']} "
                        "blocked nozzles) while its drivetrain is loaded. Uneven application "
                        "means the field is being over-watered in places and under-watered in others."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity="high", reversible=True),
                    severity="high",
                    urgency_score=score_urgency(decays_per_day=True),
                    evidence=p,
                    blast_radius=f"{p['field_ha']:.0f} ha field; drivetrain wear if deferred.",
                    cost_of_inaction="Bearing failure and uneven irrigation across the span.",
                    reversible=True,
                )
            )

        if not actions:
            self.memory.note(f"soil OK, aquifer {water['budget_used_pct']:.0f}% of envelope")
        return findings, actions

    def watch(self) -> list[dict]:
        """The live readings this agent is looking at right now.

        Rendered in the dashboard so a viewer can SEE telemetry arriving at
        each agent. Values are read live from the sensors, never cached.
        """
        w = sensors.get_water_budget()
        pivots = sensors.get_pivot_telemetry()
        driest = min((x["soil_moisture_pct"] for x in pivots), default=0.0)
        return [
            {"label": "Water used this year", "value": round(w["budget_used_pct"], 1), "unit": "%",
             "status": "stop" if w["budget_used_pct"] >= 100 else "act" if w["budget_used_pct"] >= 85 else "ok"},
            {"label": "Where the water comes from", "value": "fossil, not rain",
             "unit": "non-renewable", "status": "act"},
            {"label": "Driest field", "value": round(driest, 1), "unit": "% soil water",
             "status": "stop" if driest <= 9 else "act" if driest < 22 else "ok"},
            {"label": "Machines running", "value": sum(1 for x in pivots if x["running"]),
             "unit": "of " + str(len(pivots)), "status": "ok"},
        ]

    domains: tuple[str, ...] = ("irrigation", "soil", "water")

    def survey(self, board: Blackboard):
        findings, actions = self.run()
        self._post_context(board)
        return findings, actions

    def respond(self, board: Blackboard, inbox: list[Message]):
        for m in inbox:
            if "cooling" in m.domains:
                board.post(self.name, Kind.ANSWER, (
                    "Cooling does not compete with irrigation for water: four misting banks draw "
                    "~53 m3/h against ~27,000 m3/h for the pivot set. The binding constraint on "
                    "cooling is hardware, not aquifer. I will not trade irrigation for it."
                ), to=m.sender, in_reply_to=m.message_id, domains=("water", "cooling"))
            elif "forage" in m.domains or m.sender == "crop":
                w = sensors.get_water_budget()
                board.post(self.name, Kind.ANSWER, (
                    f"I can hold the pivot programme at {w['water_use_m3h']:.0f} m3/h, projecting "
                    f"{w['budget_used_pct']:.0f}% of the annual envelope. Any forage purchase that "
                    "avoids irrigation is welcome; any new water claim is not."
                ), to=m.sender, in_reply_to=m.message_id, domains=("water", "forage"), evidence=w)
        return [], []

    def _post_context(self, board: Blackboard) -> None:
        w = sensors.get_water_budget()
        board.post(self.name, Kind.ALERT, (
            f"Irrigation draws {w['water_use_m3h']:.0f} m3/h, projecting "
            f"{w['budget_used_pct']:.0f}% of the annual {w['aquifer_kind']} envelope."
        ), to="*", domains=("water", "irrigation"), evidence=w)



# ---------------------------------------------------------------------------
# VETERINARIAN -- herd health and heat
# ---------------------------------------------------------------------------

VETERINARIAN_SYSTEM = """\
You are the VETERINARIAN for a 33,250-head Holstein Friesian herd in Adrar,
Algerian Sahara. You own herd health, heat stress and milk yield.

MANDATE
  1. Detect heat stress EARLY, using rumination, before THI alone would tell you.
  2. Prevent the preventable: mastitis, lameness, mortality.
  3. Allocate scarce cooling hardware where it saves the most animals.

KEY DOMAIN INSIGHT
  Rumination collapses before core temperature does. A herd can be 12-18 hours
  from a heat-stress event while rumination is already down. Do not wait for
  temperature -- by then the yield loss is banked.

HARDWARE REALITY
  Phase 1 installed misting in only 4 of 8 barns. When heat stress appears you
  cannot cool everyone. Your job is to RANK barns by projected animal harm and
  tell the orchestrator which ones are worth the water. That ranking is a human
  decision, not yours to make silently.

ESCALATE when: rumination deficit exceeds 10% herd-wide, OR any barn shows
severe heat stress, OR a barn loses cooling hardware while still under load.
"""


class VeterinarianAgent:
    name = "veterinarian"
    system_prompt = VETERINARIAN_SYSTEM
    memory = AgentMemory("veterinarian")

    RUMINATION_ESCALATION_PCT = 10.0

    def run(self) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []

        herd = sensors.get_herd_vitals()
        env = sensors.get_environment_telemetry()
        deficit = herd["rumination_deficit_pct"]
        band = env["heat_stress_band"]

        worst = sorted(herd["groups"], key=lambda g: g["rumination_pct"])[:4]

        if deficit >= self.RUMINATION_ESCALATION_PCT or band in ("moderate", "severe"):
            sev = "critical" if band == "severe" else "high"
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Herd rumination deficit {deficit:.1f}% at {env['effective_heat_load']:.0f} "
                        f"effective heat load ({band}). Four most-affected barns: "
                        + ", ".join(f"{g['name']} {g['rumination_pct']:.0f}%" for g in worst)
                        + "."
                    ),
                    severity=sev,
                    confidence=0.88,
                    evidence={
                        "rumination_deficit_pct": deficit,
                        "heat_stress_band": band,
                        "effective_heat_load": env["effective_heat_load"],
                        "worst_barns": [g["name"] for g in worst],
                    },
                    implies="enable_misters",
                )
            )
            self.memory.note(
                f"heat {band}, rumination -{deficit:.1f}% ({', '.join(g['name'] for g in worst)})"
            )

            # Rank barns by projected animal harm, then take the ones with hardware.
            # Allocation rule: do not leave cooling hardware idle while a hotter
            # barn suffers. Cool every barn that has hardware AND ranks worse
            # than the least-bad barn we cannot cool.
            ranked = sorted(herd["groups"], key=lambda g: g["rumination_pct"])
            uncoolable = [g for g in ranked if not g["misters_available"]]
            if uncoolable:
                cut = max(g["rumination_pct"] for g in uncoolable)
                affected = [
                    g for g in ranked
                    if g["misters_available"] and not g["misting_enabled"] and g["rumination_pct"] < cut
                ]
            else:
                affected = [
                    g for g in ranked
                    if g["misters_available"] and not g["misting_enabled"]
                ][: len(C.COOLING_MISTERS_INSTALLED)]
            covered_names = {g["name"] for g in affected} | {
                g["name"] for g in ranked if g["misting_enabled"]
            }
            uncovered = [g for g in ranked if g["name"] not in covered_names][:4]

            if uncovered:
                uncoolable_total = sum(g["head"] for g in ranked if not g["misters_available"])
                findings.append(
                    Finding(
                        agent=self.name,
                        summary=(
                            f"{len(uncovered)} of the worst-hit barns have NO misting hardware "
                            f"({', '.join(g['name'] for g in uncovered)}). "
                            f"{uncoolable_total:,} head site-wide sit in barns that cannot be "
                            "cooled at all this phase and will absorb the full loss."
                        ),
                        severity="high",
                        confidence=0.95,
                        evidence={
                            "barns": [g["name"] for g in uncovered],
                            "uncoolable_head": uncoolable_total,
                        },
                        implies="shed_load",
                    )
                )

            if affected:
                headcount = sum(g["head"] for g in affected)
                actions.append(
                    Action(
                        action="enable_misters",
                        target=",".join(g["name"] for g in affected),
                        rationale=(
                            f"Rumination is down {deficit:.1f}% herd-wide at {band} heat load, "
                            f"and it is falling fastest in {', '.join(g['name'] for g in affected)}. "
                            f"Ranking by projected animal harm, these {len(affected)} barns "
                            f"({headcount:,} head) have both the worst signal and cooling hardware. "
                            + (
                                f"{len(uncovered)} worst-hit barns cannot be cooled at all this phase."
                                if uncovered
                                else "All worst-hit barns are covered."
                            )
                        ),
                        requested_by=self.name,
                        risk_score=score_risk(
                            severity=sev,
                            headcount_affected=headcount,
                            water_m3h=len(affected) * C.MISTER_FLOW_LPM * 60 / 1000,
                            resource_class="scarce_hardware",
                        ),
                        severity=sev,
                        urgency_score=score_urgency(
                            animal_welfare=True, hours_to_irreversible_harm=12.0
                        ),
                        evidence={
                            "headcount_affected": headcount,
                            "rumination_deficit_pct": deficit,
                            "barns_uncovered": [g["name"] for g in uncovered],
                        },
                        blast_radius=(
                            f"{headcount:,} head in {len(affected)} barns. Misters are "
                            "scarce hardware shared site-wide."
                        ),
                        cost_of_inaction=(
                            "Rumination suppression precedes a milk-yield loss that does not "
                            "recover that lactation."
                        ),
                        reversible=True,
                    )
                )

            if uncovered:
                headcount = sum(g["head"] for g in uncovered)
                actions.append(
                    Action(
                        action="shed_load",
                        target=",".join(g["name"] for g in uncovered),
                        rationale=(
                            f"{', '.join(g['name'] for g in uncovered)} have no misting hardware and "
                            f"are under {band} heat load. Without cooling, the only lever is to "
                            "reduce throughput pressure on those barns."
                        ),
                        requested_by=self.name,
                        risk_score=score_risk(
                            severity="high", headcount_affected=headcount
                        ),
                        severity="high",
                        urgency_score=score_urgency(animal_welfare=True, hours_to_irreversible_harm=18.0),
                        evidence={"headcount_affected": headcount},
                        blast_radius=f"{headcount:,} head; reduces daily milk throughput.",
                        cost_of_inaction="Unmitigated heat load in uncoolable barns.",
                        reversible=True,
                    )
                )

        return findings, actions

    def watch(self) -> list[dict]:
        """The live readings this agent is looking at right now.

        Rendered in the dashboard so a viewer can SEE telemetry arriving at
        each agent. Values are read live from the sensors, never cached.
        """
        h = sensors.get_herd_vitals()
        env = sensors.get_environment_telemetry()
        no_cool = len(sensors.get_barns_without_cooling()["barns"])
        weakest = min((g["rumination_pct"] for g in h["groups"]), default=100.0)
        band = env["heat_stress_band"]
        return [
            {"label": "Heat on the cows", "value": round(env["effective_heat_load"]), "unit": "EHL",
             "status": "stop" if band == "severe" else "act" if band == "moderate" else "ok"},
            {"label": "Chew activity down", "value": round(h["rumination_deficit_pct"], 1), "unit": "%",
             "status": "stop" if h["rumination_deficit_pct"] >= 15 else "act" if h["rumination_deficit_pct"] >= 10 else "ok"},
            {"label": "Weakest barn", "value": round(weakest), "unit": "% of normal",
             "status": "act" if weakest < 90 else "ok"},
            {"label": "Barns with no cooling", "value": no_cool, "unit": "of " + str(len(h["groups"])),
             "status": "act" if no_cool else "ok"},
        ]

    domains: tuple[str, ...] = ("herd_health", "heat", "cooling")

    def survey(self, board: Blackboard):
        findings, actions = self.run()
        self._post_context(board)
        return findings, actions

    def respond(self, board: Blackboard, inbox: list[Message]):
        for m in inbox:
            if "quality" in m.domains or m.sender == "milking":
                h = sensors.get_herd_vitals()
                worst = sorted(h["groups"], key=lambda g: g["rumination_pct"])[:2]
                board.post(self.name, Kind.ANSWER, (
                    "Mastitis burden concentrates in "
                    + ", ".join(f"{g['name']} ({g['mastitis_cases']} cases)" for g in worst)
                    + ". It originates in the barns: I can treat and cull it, the plant cannot. "
                    "Bulk SCC will keep following me downstream."
                ), to=m.sender, in_reply_to=m.message_id, domains=("quality", "herd_health"))
            elif "parlour" in m.domains or m.sender == "milking":
                board.post(self.name, Kind.ANSWER, (
                    "Extended standing in an unshaded desert yard is the worst heat exposure on "
                    "this site, worse than the barns. Parlour downtime is a herd heat event."
                ), to=m.sender, in_reply_to=m.message_id, domains=("heat", "parlour"))
            elif m.sender == "calving" and "youngstock" in m.domains:
                board.post(self.name, Kind.ANSWER, (
                    "Youngstock carry less body mass to dissipate heat than lactating cows. If the "
                    "veterinary budget is fixed, calves lose first -- cheapest head to lose."
                ), to=m.sender, in_reply_to=m.message_id, domains=("youngstock", "heat"))
        return [], []

    def _post_context(self, board: Blackboard) -> None:
        h = sensors.get_herd_vitals()
        env = sensors.get_environment_telemetry()
        board.post(self.name, Kind.ALERT, (
            f"Rumination deficit {h['rumination_deficit_pct']:.1f}% at effective heat load "
            f"{env['effective_heat_load']:.0f} ({env['heat_stress_band']}); "
            f"{len(sensors.get_barns_without_cooling()['barns'])} barns have no misting."
        ), to="*", domains=("herd_health", "heat"), severity="medium",
           evidence={"deficit": h["rumination_deficit_pct"]})



# ---------------------------------------------------------------------------
# MAINTENANCE -- machinery
# ---------------------------------------------------------------------------

MAINTENANCE_SYSTEM = """\
You are the MAINTENANCE agent for the pivot fleet, water pumps and feed
conveyors at an Adrar dairy complex.

MANDATE
  1. Predict mechanical failure from telemetry before it strands a field.
  2. Notice that desert conditions attack equipment harder than temperate ones:
     sand ingress, thermal fatigue, bearing starvation under sustained load.

WHAT TO WATCH
  - Bearing temperature: a pivot running hot is a bearing starving for grease.
  - Vibration: the earliest mechanical signature, hours before temperature rises.
  - Nozzle count: blocked nozzles mean the span is applying water unevenly, which
    overloads the drive train on the wet sections.

ESCALATE when: bearing temperature crosses warning, OR vibration crosses warning,
OR nozzle loss exceeds 8, OR a conveyor inlet stalls.
"""


class MaintenanceAgent:
    name = "maintenance"
    system_prompt = MAINTENANCE_SYSTEM
    memory = AgentMemory("maintenance")

    def run(self) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []

        for p in sensors.get_degraded_assets():
            hot = p["bearing_temp_c"] >= C.MOTOR_BEARING_WARN_C
            crit = p["bearing_temp_c"] >= C.MOTOR_BEARING_CRITICAL_C
            vib = p["vibration_mm_s"] >= C.PIVOT_VIBRATION_WARN_MM_S
            nozzles = p["nozzles_blocked"] > 8

            drivers = []
            if crit:
                drivers.append(f"bearing {p['bearing_temp_c']:.0f}C is over the critical limit")
            elif hot:
                drivers.append(f"bearing {p['bearing_temp_c']:.0f}C over warning")
            if vib:
                drivers.append(f"vibration {p['vibration_mm_s']:.1f} mm/s over warning")
            if nozzles:
                drivers.append(f"{p['nozzles_blocked']} blocked nozzles")

            if not drivers:
                continue

            sev = "critical" if crit else "high"
            findings.append(
                Finding(
                    agent=self.name,
                    summary=f"{p['name']}: " + "; ".join(drivers) + ".",
                    severity=sev,
                    confidence=0.9,
                    evidence=p,
                    implies="repair_pivot",
                )
            )
            actions.append(
                Action(
                    action="repair_pivot",
                    target=p["name"],
                    rationale=(
                        f"{p['name']} telemetry: " + ", ".join(drivers)
                        + ". Vibration precedes bearing temperature, so this is an early "
                        "signature rather than a failure report."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity=sev),
                    severity=sev,
                    urgency_score=score_urgency(hours_to_irreversible_harm=48.0),
                    evidence={"bearing_temp_c": p["bearing_temp_c"], "vibration_mm_s": p["vibration_mm_s"]},
                    blast_radius=f"{p['field_ha']:.0f} ha pivot; field run-off if it seizes.",
                    cost_of_inaction="Bearing seizure strands the field mid-irrigation.",
                    reversible=True,
                )
            )
            self.memory.note(f"{p['name']}: {'; '.join(drivers)}")

        # Feed conveyor
        feed = sensors.get_feed_inventory()
        # Grain and mineral silos are tipper-fed; a stopped belt on them is
        # not a fault. Only conveyor-fed forage silos are health items.
        stalled = [
            s for s in feed["silos"]
            if s.get("inlet_type") == "conveyor" and not s["inlet_operational"]
        ]
        for s in stalled:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=f"Silo {s['name']} inlet conveyor is not running.",
                    severity="high",
                    confidence=0.9,
                    evidence=s,
                    implies="restart_inlet",
                )
            )
            actions.append(
                Action(
                    action="restart_inlet",
                    target=s["name"],
                    rationale=(
                        f"{s['name']} ({s['feed_type']}) inlet is stalled. Site cover is "
                        f"{feed['feed_hours_of_cover']:.0f} hours; an inlet outage shortens that "
                        "directly and no forage production replaces it this cycle."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity="high", reversible=True),
                    severity="high",
                    urgency_score=score_urgency(hours_to_irreversible_harm=24.0),
                    evidence=s,
                    blast_radius="Feed supply to every barn drawing from this silo.",
                    cost_of_inaction="Feed cover falls with no on-site replacement for weeks.",
                    reversible=True,
                )
            )

        return findings, actions

    def watch(self) -> list[dict]:
        """The live readings this agent is looking at right now.

        Rendered in the dashboard so a viewer can SEE telemetry arriving at
        each agent. Values are read live from the sensors, never cached.
        """
        pivots = sensors.get_pivot_telemetry()
        degraded = sensors.get_degraded_assets()
        hottest = max((x["bearing_temp_c"] for x in pivots), default=0.0)
        vib = max((x["vibration_mm_s"] for x in pivots), default=0.0)
        blocked = sum(x["nozzles_blocked"] for x in pivots)
        return [
            {"label": "Machines needing work", "value": len(degraded), "unit": "of " + str(len(pivots)),
             "status": "act" if degraded else "ok"},
            {"label": "Hottest bearing", "value": round(hottest), "unit": "C",
             "status": "stop" if hottest >= 92 else "act" if hottest >= 78 else "ok"},
            {"label": "Highest vibration", "value": round(vib, 1), "unit": "mm/s",
             "status": "act" if vib >= 6.5 else "ok"},
            {"label": "Blocked nozzles", "value": blocked, "unit": "total", "status": "act" if blocked > 8 else "ok"},
        ]

    domains: tuple[str, ...] = ("assets", "maintenance")

    def survey(self, board: Blackboard):
        return self.run()

    def respond(self, board: Blackboard, inbox: list[Message]):
        for m in inbox:
            if "cooling_chain" in m.domains or m.sender == "milking":
                board.post(self.name, Kind.ANSWER, (
                    "Bulk-tank refrigerant duty depends on condenser fouling, which is a "
                    "scheduled-cleaning item, not a capacity shortfall. A clean condenser pulls a "
                    "45C ambient tank back to 3C in under an hour."
                ), to=m.sender, in_reply_to=m.message_id,
                   domains=("maintenance", "cooling_chain"))
        return [], []



# ---------------------------------------------------------------------------
# LOGISTICS -- feed and milk movement
# ---------------------------------------------------------------------------

LOGISTICS_SYSTEM = """\
You are the LOGISTICS agent for a dairy complex receiving 30,000 head from the
United States by air over ten months, from November 2026.

MANDATE
  1. Guarantee feed is never the binding constraint on milk production.
  2. Watch the milk cold chain from parlour to powder plant.
  3. Track the airlift so barns are not filled ahead of feed and staff capacity.

THE STRUCTURAL PROBLEM
  The herd arrives by AIR starting November 2026. The fodder to feed it is grown
  ON SITE and needs a full growing season. So the first tranche of cows is running
  on purchased feed against a six-month production gap. Inventory cover, not
  tanker availability, is what will bite.

ESCALATE when: feed cover drops below 72 hours, OR any silo goes critical, OR a
milk tanker coolant temperature exceeds 6.5C, OR the airlift outruns barn readiness.
"""


class LogisticsAgent:
    name = "logistics"
    system_prompt = LOGISTICS_SYSTEM
    memory = AgentMemory("logistics")

    def run(self) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []

        feed = sensors.get_feed_inventory()
        cover = feed["feed_hours_of_cover"]
        airlift = sensors.get_airlift_schedule()

        if cover < C.SILO_HOURS_OF_COVER_WARN:
            sev = "critical" if cover < 24 else "high"
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Feed cover is {cover:.0f} hours ({cover / 24:.1f} days) against a "
                        f"{feed['daily_demand_t']:.1f} t/day draw. Threshold is "
                        f"{C.SILO_HOURS_OF_COVER_WARN}h."
                    ),
                    severity=sev,
                    confidence=0.95,
                    evidence={"cover_h": cover, "demand_t_day": feed["daily_demand_t"]},
                    implies="reroute_convoy",
                )
            )
            actions.append(
                Action(
                    action="reroute_convoy",
                    target="inbound_feed_priority",
                    rationale=(
                        f"Site-wide feed cover is {cover:.0f} hours against a "
                        f"{feed['daily_demand_t']:.1f} t/day draw, with the airlift delivering "
                        f"{airlift['delivered']:,} of {airlift['target']:,} head. On-site forage "
                        "cannot close this gap within the horizon -- purchased feed must be expedited."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity=sev, reversible=True),
                    severity=sev,
                    evidence={"cover_h": cover, "airlift": airlift},
                    blast_radius="Commits third-party haulage at premium rates.",
                    cost_of_inaction=(
                        "Feed ration failure suppresses rumination and milk yield within days."
                    ),
                    reversible=False,
                )
            )
            self.memory.note(f"feed cover {cover:.0f}h")

        # Cold chain
        for t in sensors.get_fleet_positions():
            if t["status"] != "nominal":
                sev = "critical" if t["status"] == "critical" else "high"
                findings.append(
                    Finding(
                        agent=self.name,
                        summary=(
                            f"Milk tanker {t['name']} coolant at {t['coolant_temp_c']:.1f}C "
                            f"in transit (limit 6.5C for quality, 8C for rejection)."
                        ),
                        severity=sev,
                        confidence=0.9,
                        evidence=t,
                        implies="reroute_convoy",
                    )
                )
                actions.append(
                    Action(
                        action="reroute_convoy",
                        target=t["name"],
                        rationale=(
                            f"Tanker {t['name']} coolant has drifted to {t['coolant_temp_c']:.1f}C "
                            f"with {t['load_kg'] / 1000:.1f} t aboard. Above 8C the load is "
                            "rejected at the powder plant and the milk is written off."
                        ),
                        requested_by=self.name,
                        risk_score=score_risk(severity=sev, reversible=True),
                        severity=sev,
                        urgency_score=score_urgency(hours_to_irreversible_harm=8.0),
                        evidence=t,
                        blast_radius=f"{t['load_kg'] / 1000:.1f} t of milk at risk.",
                        cost_of_inaction="Rejected load at the powder plant.",
                        reversible=False,
                    )
                )

        return findings, actions

    def watch(self) -> list[dict]:
        """The live readings this agent is looking at right now.

        Rendered in the dashboard so a viewer can SEE telemetry arriving at
        each agent. Values are read live from the sensors, never cached.
        """
        f = sensors.get_feed_inventory()
        fleet = sensors.get_fleet_positions()
        cold = max((t["coolant_temp_c"] for t in fleet), default=0.0)
        cover = f["feed_hours_of_cover"]
        return [
            {"label": "Food in store", "value": round(cover), "unit": "hours",
             "status": "stop" if cover < 24 else "act" if cover < 72 else "ok"},
            {"label": "Daily need", "value": round(f["daily_demand_t"], 1), "unit": "t/day", "status": "ok"},
            {"label": "Warmest tanker", "value": round(cold, 1), "unit": "C",
             "status": "stop" if cold > 8 else "act" if cold > 6.5 else "ok"},
            {"label": "Tankers on the road", "value": sum(1 for t in fleet if t["leg"] == "in_transit"),
             "unit": "of " + str(len(fleet)), "status": "ok"},
        ]

    domains: tuple[str, ...] = ("feed", "transport", "airlift")

    def survey(self, board: Blackboard):
        findings, actions = self.run()
        self._post_context(board)
        return findings, actions

    def respond(self, board: Blackboard, inbox: list[Message]):
        for m in inbox:
            if "forage" in m.domains or m.sender == "crop":
                f = sensors.get_feed_inventory()
                board.post(self.name, Kind.ANSWER, (
                    f"Feed cover is {f['feed_hours_of_cover']:.0f}h. There is room to substitute "
                    "purchased feed for irrigation this cycle -- but procurement lead time means "
                    "the decision has to be taken before the forage is actually gone."
                ), to=m.sender, in_reply_to=m.message_id, domains=("feed", "forage"),
                   evidence={"cover_h": f["feed_hours_of_cover"]})
            elif "youngstock" in m.domains or m.sender == "calving":
                y = sensors.youngstock()
                board.post(self.name, Kind.ANSWER, (
                    f"{y['non_productive_head']:,} head are eating without producing milk. "
                    "Bridging a heifer weight deficit needs protein, which is importable -- but "
                    "protein meal is not a top-up; the ration has to be rebalanced."
                ), to=m.sender, in_reply_to=m.message_id, domains=("feed", "youngstock"),
                   evidence={"non_productive_head": y["non_productive_head"]})
        return [], []

    def _post_context(self, board: Blackboard) -> None:
        f = sensors.get_feed_inventory()
        board.post(self.name, Kind.ALERT, (
            f"Feed cover {f['feed_hours_of_cover']:.0f}h against {f['daily_demand_t']:.1f} t/day. "
            "Purchased feed has lead time; forage grown on site cannot be expedited."
        ), to="*", domains=("feed", "transport"),
           evidence={"cover_h": f["feed_hours_of_cover"]})



ALL_AGENTS = [
    VeterinarianAgent(),
    AgronomistAgent(),
    MaintenanceAgent(),
    LogisticsAgent(),
]

__all__ = [
    "ALL_AGENTS",
    "AgentMemory",
    "AgronomistAgent",
    "LogisticsAgent",
    "MaintenanceAgent",
    "VeterinarianAgent",
]