"""Layer 2 - Crop, Calving/Youngstock, and Milking specialists.

These three join the original Agronomist, Veterinarian, Maintenance and Logistics
agents, giving coverage of the three production areas the site actually has:

    CROP PRODUCTION   irrigation, soil, forage growth, harvest, ensiling
    LIVESTOCK         lactating herd, heifers, calves, dry cows, reproduction
    MILK PRODUCTION   parlour, cooling, cold chain, powder plant, milk quality

Unlike the original fan-out, each of these both broadcasts findings to the board
and answers what the others asked of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..tools import sensors
from ..tools.actions import Action, Finding, score_risk, score_urgency
from ..twin import constants as C
from ..twin.livestock import (
    SCC_LIMIT_K,
)
from .mesh import Blackboard, Kind, Message
from .specialists import AgentMemory

# ---------------------------------------------------------------------------
# CROP PRODUCTION
# ---------------------------------------------------------------------------

CROP_SYSTEM = """\
You are the CROP PRODUCTION specialist for an irrigated forage programme in Adrar,
Algerian Sahara: 6 centre pivots, 6 forage fields, aiming at 2.5 million tonnes
of forage a year against roughly 1.17 million m3 of water.

MANDATE
  1. Stand dry matter per hectare, and cut the fields at the right moment.
  2. Keep the water-per-kilogram-of-dry-matter ratio inside the project budget.
  3. Route harvested material to ensiling without losing the crop in the field.

WHAT YOU SEE THAT OTHERS DO NOT
  A field below the wilting point accrues ZERO biomass -- growth stops, it does
  not merely slow. So a missed irrigation is not a delay, it is a permanent loss
  for that growing season. Standing DM is the number, soil moisture is the cause.

ESCALATE when: any field hits wilting point, OR standing DM drops after a cut
and does not recover, OR a field is over-mature past its cut interval, OR the
forage programme cannot cover projected herd demand.
"""


@dataclass
class CropAgent:
    name: str = "crop"
    system_prompt: str = CROP_SYSTEM
    domains: tuple[str, ...] = ("crop", "irrigation", "soil", "forage")
    memory: AgentMemory = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = AgentMemory(self.name)

    # -- round 1 --------------------------------------------------------

    def survey(self, board: Blackboard) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []
        p = sensors.crops()
        water = sensors.get_water_budget()

        wilted = [f for f in p["fields"] if f["soil_moisture_pct"] <= C.SOIL_MOISTURE_WILTING_PCT]
        dry = [
            f for f in p["fields"]
            if C.SOIL_MOISTURE_WILTING_PCT < f["soil_moisture_pct"] < C.SOIL_MOISTURE_OPTIMAL_PCT
        ]
        ready = [f for f in p["fields"] if f["ready_for_cut"]]
        overmature = [f for f in p["fields"] if f["ready_for_cut"] and f["biomass_t_ha"] > 16.0]

        # --- the headline number, and who else needs to hear it ---
        if wilted or ready:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"{len(wilted)} of {len(p['fields'])} forage fields are at wilting point "
                        f"({', '.join(f['field_id'] for f in wilted)}). Biomass accrual is at "
                        f"zero there -- this is a permanent loss for the season, not a delay. "
                        f"Site standing DM {p['standing_t']:.0f} t."
                    ),
                    severity="high",
                    confidence=0.95,
                    evidence={"wilted": [f["field_id"] for f in wilted], "standing_t": p["standing_t"]},
                    implies="start_pivot",
                )
            )
            # Crop's gain is the herd's cost, and the herd's cooling is the
            # water the crop was going to use. Both belong on the board.
            board.post(
                self.name,
                Kind.QUESTION,
                (
                    f"{len(wilted)} forage field(s) at wilting point, growth stopped. Irrigation "
                    "for them comes out of the same aquifer envelope the herd drinks from. "
                    "Do the animal domains have a claim on that water this cycle?"
                ),
                to="calving",
                severity="high",
                domains=("water", "forage"),
                evidence={"wilted": [f["field_id"] for f in wilted]},
            )
            board.post(
                self.name,
                Kind.ALERT,
                (
                    "Forage standing DM is falling. Anything that increases feed demand this "
                    "cycle has to be paid for with purchased feed, which has lead time."
                ),
                to="logistics",
                domains=("forage", "feed"),
            )

            for f in wilted:
                actions.append(
                    Action(
                        action="start_pivot",
                        # Target by pivot NAME, not id. The agronomist targets by
                        # name, and using two vocabularies for the same asset made
                        # batching merge "1,2,3" with "PIVOT-1,PIVOT-2,PIVOT-3".
                        target=f"PIVOT-{f['pivot_id']}",
                        rationale=(
                            f"{f['field_id']} ({f['crop']}, {f['area_ha']:.0f} ha) is at "
                            f"{f['soil_moisture_pct']:.1f}% soil moisture. Crop growth has stopped. "
                            "The forage it would have carried is the ration the herd eats."
                        ),
                        requested_by=self.name,
                        risk_score=score_risk(
                            severity="high",
                            water_m3h=f["area_ha"] * 10_000 * 0.009,
                            resource_class="non_renewable_aquifer",
                        ),
                        severity="high",
                        urgency_score=score_urgency(decays_per_day=True),
                        evidence={"water_m3h": f["area_ha"] * 10_000 * 0.009, "field": f["field_id"]},
                        blast_radius=f"{f['area_ha']:.0f} ha of forage production",
                        cost_of_inaction="Zero biomass accrual for the remainder of the season.",
                    )
                )

        if overmature:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"{', '.join(f['field_id'] for f in overmature)} are past their cut interval "
                        f"at {max(f['biomass_t_ha'] for f in overmature):.0f} t DM/ha. Past peak, "
                        "every day standing costs quality and digestibility."
                    ),
                    severity="medium",
                    confidence=0.85,
                    evidence={"fields": [f["field_id"] for f in overmature]},
                    implies="harvest_field",
                )
            )
            actions.append(
                Action(
                    action="harvest_field",
                    target=",".join(f["field_id"] for f in overmature),
                    rationale=(
                        "Fields are past their cut interval. Standing DM is at or near peak; "
                        "leaving it drops crude protein and raises lignification, which the "
                        "lactating herd cannot efficiently use."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity="medium"),
                    severity="medium",
                    urgency_score=score_urgency(hours_to_irreversible_harm=36.0),
                    evidence={"fields": [f["field_id"] for f in overmature]},
                    blast_radius="Forage quality for the whole milking herd.",
                    cost_of_inaction="Digestible energy lost every day the crop stands.",
                )
            )

        if water["budget_used_pct"] >= 85:
            board.post(
                self.name,
                Kind.OBJECTION,
                (
                    f"Irrigating the full pivot set projects {water['budget_used_pct']:.0f}% of the "
                    "annual aquifer envelope, against a non-renewable stock. Any new water claim "
                    "must displace existing water, not add to it."
                ),
                to="veterinarian",
                severity="high",
                domains=("water",),
                evidence=water,
            )

        if not actions:
            self.memory.note(
                f"standing {p['standing_t']:.0f} t, {len(dry)} field(s) drying, aquifer "
                f"{water['budget_used_pct']:.0f}%"
            )
        return findings, actions

    def watch(self) -> list[dict]:
        """The live readings this agent is looking at right now.

        Rendered in the dashboard so a viewer can SEE telemetry arriving at
        each agent. Values are read live from the sensors, never cached.
        """
        c = sensors.crops()
        driest = min((f["soil_moisture_pct"] for f in c["fields"]), default=0.0)
        ready = sum(1 for f in c["fields"] if f["ready_for_cut"])
        return [
            {"label": "Food growing right now", "value": round(c["standing_t"]), "unit": "t in the field",
             "status": "ok"},
            {"label": "Fields too dry", "value": c["water_stressed_ha"], "unit": "ha",
             "status": "act" if c["water_stressed_ha"] else "ok"},
            {"label": "Driest field", "value": round(driest, 1), "unit": "% soil water",
             "status": "stop" if driest <= 9 else "act" if driest < 22 else "ok"},
            {"label": "Fields ready to cut", "value": ready, "unit": "of " + str(len(c["fields"])),
             "status": "ok"},
        ]

    # -- round 2 --------------------------------------------------------

    def respond(self, board: Blackboard, inbox: list[Message]) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []
        water = sensors.get_water_budget()

        for m in inbox:
            if "forage" in m.domains or "feed" in m.domains or m.sender in ("logistics", "calving"):
                board.post(
                    self.name,
                    Kind.ANSWER,
                    (
                        f"Acknowledged. Standing DM is {sensors.crops()['standing_t']:.0f} t across "
                        f"6 fields. I can hold the programme at current output only by drawing "
                        f"about {water['water_use_m3h']:.0f} m3/h, which is "
                        f"{water['budget_used_pct']:.0f}% of the annual envelope. Beyond that, "
                        "every extra tonne of forage has to be bought, not grown."
                    ),
                    to=m.sender,
                    in_reply_to=m.message_id,
                    domains=("forage", "water"),
                    evidence=water,
                )
            if m.sender == "veterinarian" and "cooling" in m.domains:
                board.post(
                    self.name,
                    Kind.ANSWER,
                    (
                        "Cooling is not competing with me for water -- four misting banks draw "
                        "about 53 m3/h against roughly 27,000 m3/h for the pivot set. The real "
                        "constraint on cooling is hardware: 4 of 8 barns have it. If you need more "
                        "barns cooled, the fix is capital, not irrigation."
                    ),
                    to=m.sender,
                    in_reply_to=m.message_id,
                    domains=("cooling", "water"),
                )
        return findings, actions


# ---------------------------------------------------------------------------
# LIVESTOCK - calving, youngstock, reproduction
# ---------------------------------------------------------------------------

CALVING_SYSTEM = """\
You are the CALVING AND YOUNGSTOCK specialist for the Baladna Adrar site.

MANDATE
  1. Reproduction: heifers hitting breeding weight, conception, calving.
  2. Calf survival and welfare through weaning.
  3. Dry-cow transition management ahead of calving.

THE ECONOMIC FACT YOU ARE RESPONSIBLE FOR
The 30,000 head arriving by air from the United States are overwhelmingly
HEIFERS -- roughly 72% -- plus about 22% dry cows. A Holstein heifer does not
milk until roughly 18 months after landing. So the herd build-out consumes feed
and water for well over a year before it produces any saleable milk.

That is the project economics in one sentence, and it is invisible if you only
model mature lactating cows. It is also why heifer growth rate is a capital
question, not a husbandry detail: a heifer that misses breeding weight calves
late, and the delay compounds every cycle after.

ESCALATE when: a heifer group drops below 88% of target breeding weight, OR calf
mortality rises, OR calving interval stretches, OR an airlift cohort arrives into
inadequate housing.
"""


@dataclass
class CalvingAgent:
    name: str = "calving"
    system_prompt: str = CALVING_SYSTEM
    domains: tuple[str, ...] = ("livestock", "youngstock", "reproduction")
    memory: AgentMemory = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = AgentMemory(self.name)

    def survey(self, board: Blackboard) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []
        ys = sensors.youngstock()

        heifers = ys["groups_heifer"]
        deficient = [g for g in heifers if g["weight_pct_of_target"] < 88.0]
        calves = ys["groups_calf"]
        sick_calves = [g for g in calves if g["scours_rate_pct"] > 6.0]

        if deficient:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"{sum(g['head'] for g in deficient):,} heifers below 88% of target "
                        f"breeding weight (worst: "
                        + ", ".join(f"{g['group_id']} {g['weight_pct_of_target']:.0f}%" for g in deficient)
                        + f"). Non-productive head site-wide: {ys['non_productive_head']:,}."
                    ),
                    severity="high",
                    confidence=0.9,
                    evidence={"groups": [g["group_id"] for g in deficient]},
                    implies="boost_heifer_rations",
                )
            )
            # Heifers are eating and not milking. That is a feed-budget claim the
            # logistics agent has to price, so it goes on the board.
            board.post(
                self.name,
                Kind.QUESTION,
                (
                    f"{sum(g['head'] for g in deficient):,} heifers are under breeding weight and "
                    "therefore eating feed without producing milk. Bridging that gap means more "
                    "ration or more imported protein. Which is available this cycle?"
                ),
                to="logistics",
                severity="high",
                domains=("feed", "youngstock"),
                evidence={"head": sum(g["head"] for g in deficient)},
            )

        if sick_calves:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Calf scours at {max(g['scours_rate_pct'] for g in sick_calves):.1f}% of "
                        f"head in {', '.join(g['group_id'] for g in sick_calves)} "
                        f"(7-day mortality {ys['calf_mortality_7d']})."
                    ),
                    severity="high",
                    confidence=0.85,
                    evidence={"groups": [g["group_id"] for g in sick_calves]},
                    implies="isolate_calves",
                )
            )
            actions.append(
                Action(
                    action="isolate_calves",
                    target=",".join(g["group_id"] for g in sick_calves),
                    rationale=(
                        "Calf scours above 6% of head with elevated 7-day mortality. Scours in the "
                        "first weeks of life is the single biggest survival loss on a dairy, and it "
                        "compounds into a heifer that never reaches breeding weight."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity="high", headcount_affected=sum(g["head"] for g in sick_calves)),
                    severity="high",
                    urgency_score=score_urgency(animal_welfare=True, hours_to_irreversible_harm=48.0),
                    evidence={"head": sum(g["head"] for g in sick_calves)},
                    blast_radius=f"{sum(g['head'] for g in sick_calves):,} calves; separates the affected pens.",
                    cost_of_inaction="Pre-weaning mortality becomes a heifer shortfall 18 months later.",
                )
            )

        if ys["airlift_head"] > 0:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Airlift cohort in residence: {ys['airlift_head']:,} head "
                        f"({ys['airlift_mix']}). Only lactating head produces milk -- this cohort "
                        "earns nothing for about 18 months from landing."
                    ),
                    severity="info",
                    confidence=0.95,
                    evidence=ys["airlift_mix"],
                    implies="monitor",
                )
            )

        if not actions:
            self.memory.note(
                f"heifers {len(deficient)} under target, non-productive {ys['non_productive_head']:,}"
            )
        return findings, actions

    def watch(self) -> list[dict]:
        """The live readings this agent is looking at right now.

        Rendered in the dashboard so a viewer can SEE telemetry arriving at
        each agent. Values are read live from the sensors, never cached.
        """
        ys = sensors.youngstock()
        cow_ratio = round(ys["airlift_head"] / ys["total_head"] * 100, 1) if ys["total_head"] else 0.0
        return [
            {"label": "Heifers to calve soon", "value": ys["by_class"].get("heifer", 0), "unit": "head", "status": "ok"},
            {"label": "Need replacement cows", "value": cow_ratio, "unit": "% of herd",
             "status": "act" if cow_ratio > 10 else "ok"},
            {"label": "Calves lost this week", "value": ys["calf_mortality_7d"], "unit": "calves",
             "status": "act" if ys["calf_mortality_7d"] > 20 else "ok"},
            {"label": "Total animals", "value": ys["total_head"], "unit": "head", "status": "ok"},
        ]

    def respond(self, board: Blackboard, inbox: list[Message]) -> tuple[list[Finding], list[Action]]:
        for m in inbox:
            if "forage" in m.domains or m.sender == "crop":
                ys = sensors.youngstock()
                board.post(
                    self.name,
                    Kind.ANSWER,
                    (
                        f"{ys['non_productive_head']:,} head are eating without milking -- heifers, "
                        f"calves and dry cows. So the forage programme is carrying a growing "
                        "non-productive population, and every shortfall hits that first before it "
                        "hits the lactating herd."
                    ),
                    to=m.sender,
                    in_reply_to=m.message_id,
                    domains=("youngstock", "feed"),
                )
            if m.sender == "milking" and "milk" in m.domains:
                ys = sensors.youngstock()
                board.post(
                    self.name,
                    Kind.COUNTER,
                    (
                        f"Worth being explicit: of {ys['total_head']:,} head on site, only the "
                        f"{ys['lactating_head']:,} lactating animals generate parlour throughput. "
                        "Parlour capacity sized on total head would be badly oversized for the "
                        "next 18 months, and the empty parlour time is where heat load builds."
                    ),
                    to=m.sender,
                    in_reply_to=m.message_id,
                    domains=("milk", "livestock"),
                    evidence={"lactating_head": ys["lactating_head"]},
                )
        return [], []


# ---------------------------------------------------------------------------
# MILK PRODUCTION
# ---------------------------------------------------------------------------

MILKING_SYSTEM = """\
You are the MILK PRODUCTION specialist for the Baladna Adrar site: parlour,
bulk tank cooling, tanker dispatch and the GEA powder plant.

MANDATE
  1. Capture the milk the herd produces. Milk not captured is production lost.
  2. Protect bulk tank somatic cell count. Above 200k cells/mL it is outside the
     EU limit and the load is penalised.
  3. Hold the cold chain from the parlour to the powder silo.

THE DISTINCTION THAT MATTERS
Tonnage alone will mislead you. Milk volume and milk quality are separate
failures: a herd can be in full lactation, the parlour can be running at full
throughput, and the load can still be rejected on SCC. Bulk SCC rises with
mastitis burden in the barns and falls with treatment and culling -- so quality
is a herd-health signal arriving downstream, and you should say so rather than
treat it as a plant problem.

ESCALATE when: parlour downtime exceeds an hour, bulk temperature rises above
6.5C, SCC exceeds 200k, or the powder silo passes 92% and risks blocking intake.
"""


@dataclass
class MilkingAgent:
    name: str = "milking"
    system_prompt: str = MILKING_SYSTEM
    domains: tuple[str, ...] = ("milk", "parlour", "quality", "cooling_chain", "powder")
    memory: AgentMemory = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = AgentMemory(self.name)

    def survey(self, board: Blackboard) -> tuple[list[Finding], list[Action]]:
        findings: list[Finding] = []
        actions: list[Action] = []
        m = sensors.milk()

        if m["downtime_min_24h"] > 60:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Parlour downtime {m['downtime_min_24h']:.0f} min in 24h across "
                        f"{m['units']} units. At {m['throughput_cows_per_hour']:.0f} cows/h that is "
                        "milk that exists and is not collected."
                    ),
                    severity="high" if m["downtime_min_24h"] > 180 else "medium",
                    confidence=0.9,
                    evidence=m,
                    implies="service_parlour",
                )
            )
            actions.append(
                Action(
                    action="service_parlour",
                    target="all_units",
                    rationale=(
                        f"{m['downtime_min_24h']:.0f} minutes of downtime against "
                        f"{m['milkings_per_day']} milkings a day. Every minute is a cow milked "
                        "late, and late-milked cows drop yield permanently for that lactation."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity="medium"),
                    severity="medium",
                    urgency_score=score_urgency(hours_to_irreversible_harm=24.0),
                    evidence=m,
                    blast_radius=f"Milking throughput for {m['lactating_head']:,} lactating head.",
                    cost_of_inaction="Cumulative yield loss across every lactation in progress.",
                )
            )
            # A parlour problem is also a heat problem: cows standing in the
            # holding area are the hottest animals on site.
            board.post(
                self.name,
                Kind.ALERT,
                (
                    f"Parlour downtime is putting cows in the holding area longer "
                    f"({m['holding_area_ehl']:.0f} effective heat load there). Extended holding in "
                    "a desert is where heat stress actually kills -- not in the barns."
                ),
                to="veterinarian",
                severity="medium",
                domains=("heat", "parlour"),
                evidence={"holding_area_ehl": m["holding_area_ehl"]},
            )

        if m["bulk_scc_k"] > SCC_LIMIT_K:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Bulk SCC {m['bulk_scc_k']:.0f}k cells/mL, above the {SCC_LIMIT_K:.0f}k "
                        "EU limit. The load attracts a penalty and the trend compounds."
                    ),
                    severity="high" if m["bulk_scc_k"] > 300 else "medium",
                    confidence=0.9,
                    evidence=m,
                    implies="cull_chronic_mastitis",
                )
            )
            # This is a herd problem arriving downstream, and the veterinarian
            # is the only agent who can fix it.
            board.post(
                self.name,
                Kind.QUESTION,
                (
                    f"Bulk SCC is {m['bulk_scc_k']:.0f}k, outside the {SCC_LIMIT_K:.0f}k limit. "
                    "This originates in the barns, not the plant. Which groups are carrying the "
                    "mastitis burden, and what is the culling plan?"
                ),
                to="veterinarian",
                severity="high",
                domains=("quality", "herd_health"),
                evidence={"bulk_scc_k": m["bulk_scc_k"]},
            )
            actions.append(
                Action(
                    action="cull_chronic_mastitis",
                    target="high_scc_groups",
                    rationale=(
                        f"Bulk SCC {m['bulk_scc_k']:.0f}k is outside the regulatory limit. Every "
                        "litre produced carries the penalty until the chronic-mastitis cows are "
                        "culled or treated out."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity="high", headcount_affected=m["mastitis_head_estimate"]),
                    severity="high",
                    urgency_score=score_urgency(hours_to_irreversible_harm=96.0),
                    evidence={"bulk_scc_k": m["bulk_scc_k"]},
                    blast_radius="Milk price across the whole site, not one load.",
                    cost_of_inaction="Regulatory penalty and a declining cull value as cases chronic.",
                )
            )

        if m["bulk_temp_c"] > 6.5:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Bulk tank at {m['bulk_temp_c']:.1f}C, above the 6.5C quality limit. "
                        f"Condenser fouling {m['condenser_fouling_pct']:.0f}%."
                    ),
                    severity="high",
                    confidence=0.95,
                    evidence=m,
                    implies="clean_condenser",
                )
            )
            board.post(
                self.name,
                Kind.QUESTION,
                (
                    f"Bulk tank holding at {m['bulk_temp_c']:.1f}C with the condenser "
                    f"{m['condenser_fouling_pct']:.0f}% fouled. Is the refrigerant duty adequate or "
                    "is this a maintenance backlog?"
                ),
                to="maintenance",
                severity="high",
                domains=("cooling_chain",),
                evidence={"bulk_temp_c": m["bulk_temp_c"]},
            )
            actions.append(
                Action(
                    action="clean_condenser",
                    target="bulk_tank",
                    rationale=(
                        f"Bulk milk at {m['bulk_temp_c']:.1f}C. Above 8C the load is rejected at "
                        "the powder plant and the milk is written off entirely."
                    ),
                    requested_by=self.name,
                    risk_score=score_risk(severity="high"),
                    severity="high",
                    urgency_score=score_urgency(hours_to_irreversible_harm=8.0),
                    evidence={"bulk_temp_c": m["bulk_temp_c"]},
                    blast_radius=f"Up to {m['bulk_tank_kg'] / 1000:.0f} t of milk in the tank.",
                    cost_of_inaction="Rejected load; total loss of that milk.",
                )
            )

        if m["silo_fill_pct"] > 92:
            findings.append(
                Finding(
                    agent=self.name,
                    summary=(
                        f"Powder silo {m['silo_fill_pct']:.0f}% full. Intake must stop or the "
                        "spray dryer will block."
                    ),
                    severity="critical",
                    confidence=0.95,
                    evidence=m,
                    implies="halt_intake",
                )
            )

        if not actions:
            self.memory.note(
                f"SCC {m['bulk_scc_k']:.0f}k, tank {m['bulk_temp_c']:.1f}C, capture {m['capture_ratio']:.0f}%"
            )
        return findings, actions

    def watch(self) -> list[dict]:
        """The live readings this agent is looking at right now.

        Rendered in the dashboard so a viewer can SEE telemetry arriving at
        each agent. Values are read live from the sensors, never cached.
        """
        m = sensors.milk()
        return [
            {"label": "Milk made today", "value": round(m["daily_milk_kg"] / 1000, 1), "unit": "tonnes",
             "status": "ok"},
            {"label": "Milk stored", "value": round(m["bulk_tank_kg"] / 1000, 1), "unit": "t in tank",
             "status": "ok"},
            {"label": "How fast cows are milked", "value": round(m["throughput_cows_per_hour"]), "unit": "cows/hour",
             "status": "ok"},
            {"label": "How warm the cows are", "value": round(m["holding_area_ehl"]), "unit": "EHL",
             "status": "act" if m["holding_area_ehl"] >= 68 else "ok"},
        ]

    def respond(self, board: Blackboard, inbox: list[Message]) -> tuple[list[Finding], list[Action]]:
        for m in inbox:
            if m.sender == "veterinarian" and "quality" in m.domains:
                mv = sensors.milk()
                board.post(
                    self.name,
                    Kind.ANSWER,
                    (
                        f"Confirmed from the plant side: bulk SCC is {mv['bulk_scc_k']:.0f}k. "
                        f"Capture ratio {mv['capture_ratio']:.0f}%, parlour running "
                        f"{mv['milkings_per_day']}x daily. The quality problem is upstream -- I can "
                        "hold the cold chain but I cannot fix a mastitis burden."
                    ),
                    to=m.sender,
                    in_reply_to=m.message_id,
                    domains=("quality", "milk"),
                )
            if m.sender == "logistics" and "transport" in m.domains:
                board.post(
                    self.name,
                    Kind.ANSWER,
                    (
                        "Dispatch capacity is fine -- the bottleneck is never trucks. Watch the bulk "
                        "tank level and the cold chain instead; a tanker held at the plant while "
                        "product sits above 6.5C costs more than the haulage."
                    ),
                    to=m.sender,
                    in_reply_to=m.message_id,
                    domains=("transport", "cooling_chain"),
                )
        return [], []


ALL_DOMAIN_AGENTS = [CropAgent(), CalvingAgent(), MilkingAgent()]

__all__ = ["ALL_DOMAIN_AGENTS", "CalvingAgent", "CropAgent", "MilkingAgent"]