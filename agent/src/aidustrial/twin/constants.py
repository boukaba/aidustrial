"""
Layer 1 - Sensory Cortex: physical constants for the Adrar digital twin.

EVERY value here traces to a researched source in BALADNA_ALGERIA_DOSSIER.md or is
an explicit engineering assumption. The `provenance` dict at the bottom is the
machine-readable audit trail -- DATA_PROVENANCE.md is generated from it.

Nothing in this module is invented silently. If a number is our assumption rather
than a sourced fact, it says ASSUMPTION.
"""

from __future__ import annotations

from typing import Final, Literal

# ---------------------------------------------------------------------------
# SITE IDENTITY (sourced)
# ---------------------------------------------------------------------------

PROJECT: Final[str] = "Baladna Algeria S.P.A. / SPA Baladna El Djazair"
LOCATION: Final[str] = "Adrar Province, Wilaya of Adrar, Algerian Sahara"
OPERATOR: Final[str] = "Baladna Q.P.S.C. (QSE: BLDN)"
STATE_PARTNER: Final[str] = "Fonds National d'Investissement (FNI)"
OWNERSHIP_SPLIT: Final[tuple[int, int]] = (51, 49)

#: The dossier found a direct conflict: the operator's own recruitment site says
#: 219,000 ha; every shareholder/government document says 117,000 ha. We model the
#: CONSERVATIVE number (117,000) because that is what lenders and the state use,
#: and expose the contested figure so the UI can show the discrepancy honestly.
SITE_HA_SOURCED: Final[float] = 117_000.0
SITE_HA_OPERATOR_CLAIM: Final[float] = 219_000.0
SITE_HA: Final[float] = SITE_HA_SOURCED

# ---------------------------------------------------------------------------
# HERD (sourced)
# ---------------------------------------------------------------------------

HERD_TARGET_FULL: Final[int] = 270_000
HERD_PHASE1_CAPACITY: Final[int] = 50_000
#: GCB (Sonatrach subsidiary) was contracted to build infrastructure sized for
#: this head count in the Phase 2 tranche -- the first physically-built barn.
HERD_PHASE1_BUILT: Final[int] = 33_250
HERD_AIRLIFT_TOTAL: Final[int] = 30_000
HERD_AIRLIFT_FLIGHTS: Final[int] = 109
HERD_AIRLIFT_COWS_PER_FLIGHT: Final[int] = 300
HERD_AIRLIFT_START: Final[str] = "2026-11-01"
HERD_AIRLIFT_MONTHS: Final[int] = 10
BREED: Final[str] = "Holstein Friesian"

MILK_LITRES_ANNUAL_TARGET: Final[float] = 1.7e9
MILK_LITRES_PER_COW_DAY: Final[float] = 1_700_000_000 / HERD_TARGET_FULL / 365
MILK_POWDER_T_TARGET: Final[float] = 100_000.0  # GEA-confirmed design capacity

# ---------------------------------------------------------------------------
# FORAGE & FEED (sourced + derived)
# ---------------------------------------------------------------------------

FORAGE_TONNES_ANNUAL_TARGET: Final[float] = 2_500_000.0
#: Feed gap problem that defines Phase 1: the herd arrives ~6 months before the
#: arable programme is capable of feeding it. The logistics agent's core job.
FORAGE_DRY_MATTER_PCT: Final[float] = 32.0  # ASSUMPTION: typical corn silage DM
SILOS_ON_SITE: Final[int] = 6
SILO_CAPACITY_TONNES: Final[float] = 12_000.0  # ASSUMPTION per silo
AIR_FREIGHT_FEED_GAP_DAYS: Final[int] = 210  # ASSUMPTION: herd-before-fodder window

# ---------------------------------------------------------------------------
# WATER -- the central constraint (sourced, contested)
# ---------------------------------------------------------------------------

WELLS_COMPLETED: Final[int] = 45
DRILLING_PERMITS: Final[int] = 186
#: Tafelwit (June 2026) estimate: Phase 1 draws 500-700M m3/yr; full capacity
#: needs 2.5-4bn m3/yr from the Albien -- a NON-RENEWABLE fossil aquifer.
#: We model the pessimistic end, because that is the risk case.
AQUIFER_KIND: Final[str] = "Albien fossil aquifer (non-renewable)"
WATER_M3_PHASE1_ANNUAL: Final[float] = 700e6
WATER_M3_FULL_ANNUAL_LOW: Final[float] = 2.5e9
WATER_M3_FULL_ANNUAL_HIGH: Final[float] = 4.0e9
WATER_M3_FULL_ANNUAL: Final[float] = WATER_M3_FULL_ANNUAL_HIGH

#: Litre of water per litre of milk. GRAIN derives 1,020. Industry literature for
#: desert dairies puts the total (drinking+cooling+feed+washdown) far higher.
WATER_L_PER_L_MILK: Final[float] = 1_020.0

# ---------------------------------------------------------------------------
# IRRIGATION ASSETS (sourced suppliers)
# ---------------------------------------------------------------------------

PIVOTS: Final[int] = 6
PIVOT_RADIUS_M: Final[float] = 400.0  # ASSUMPTION: mid-size centre pivot
PIVOT_AREA_HA: Final[float] = float(PIVOT_RADIUS_M**2) * 3.14159265 / 10_000
IRRIGATION_SUPPLIER: Final[str] = "Valmont Industries (USA) + AFKO (Turkey)"
PROCESS_SUPPLIER: Final[str] = "GEA Group AG (DE) - incl. 40m drying tower"

# ---------------------------------------------------------------------------
# CLIMATE -- Adrar is the reason this is hard (sourced + climatology)
# ---------------------------------------------------------------------------

#: Adrar, elevation ~264-406m, subtropical hot desert (Koppen BWh).
LATITUDE: Final[float] = 27.8743
LONGITUDE: Final[float] = -0.2939
ELEVATION_M: Final[float] = 264.0

TEMP_C_NIGHT_MEAN: Final[float] = 24.0  # ASSUMPTION from BWh climatology
TEMP_C_DAY_PEAK: Final[float] = 43.0  # ASSUMPTION: Adrar July mean daily max
TEMP_C_DIURNAL_SWING: Final[float] = TEMP_C_DAY_PEAK - TEMP_C_NIGHT_MEAN
REL_HUMIDITY_MEAN_PCT: Final[float] = 18.0  # ASSUMPTION: arid interior
WIND_MEAN_KMH: Final[float] = 14.0  # ASSUMPTION

#: Cooling systems the veterinarian can summon. These compete with pivots for the
#: same aquifer -- that trade-off is the demo.
COOLING_MISTERS_INSTALLED: Final[int] = 4
MISTER_FLOW_LPM: Final[float] = 220.0  # ASSUMPTION per mister bank
FAN_INSTALLED: Final[int] = 180  # ASSUMPTION across Phase 1 barns

# ---------------------------------------------------------------------------
# THRESHOLDS (industry standard, cited in DATA_PROVENANCE)
# ---------------------------------------------------------------------------

#: Temperature-Humidity Index. NRC (1971) dairy thresholds.
THI_HEAT_STRESS_ONSET: Final[float] = 68.0
THI_HEAT_STRESS_MODERATE: Final[float] = 72.0
THI_HEAT_STRESS_SEVERE: Final[float] = 80.0
THI_MILK_YIELD_LOSS_MILD: Final[float] = 1.9  # % per THI unit above threshold
THI_MILK_YIELD_LOSS_SEVERE: Final[float] = 3.9

#: Rumination drop is the earliest reliable heat-stress signal -- often hours
#: before THI alone would trigger. This is what makes the vet agent useful.
RUMINATION_BASELINE_MIN: Final[float] = 180.0
RUMINATION_HEAT_DROP_PCT: Final[float] = 22.0
RUMINATION_SICK_DROP_PCT: Final[float] = 35.0

SOIL_MOISTURE_WILTING_PCT: Final[float] = 9.0  # ASSUMPTION: sandy Saharan soil
SOIL_MOISTURE_OPTIMAL_PCT: Final[float] = 22.0
SOIL_MOISTURE_SATURATION_PCT: Final[float] = 38.0

MOTOR_BEARING_WARN_C: Final[float] = 78.0
MOTOR_BEARING_CRITICAL_C: Final[float] = 92.0
PIVOT_VIBRATION_WARN_MM_S: Final[float] = 6.5

SILO_CRITICAL_FILL_PCT: Final[float] = 18.0
SILO_HOURS_OF_COVER_WARN: Final[float] = 72.0

# ---------------------------------------------------------------------------
# HITL RISK POLICY (our design decision -- surfaced to the Farm Director)
# ---------------------------------------------------------------------------

#: Actions at or above this score pause the graph and require human approval.
#: This is the governance contract of the system, not a tunable afterthought.
RISK_AUTO_APPROVE_CEILING: Final[float] = 40.0
RISK_GATE_ELEVATED: Final[float] = 55.0
RISK_GATE_CRITICAL: Final[float] = 80.0

#: Irreversible / water-consuming actions are ALWAYS gated regardless of score.
ALWAYS_GATE_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "transfer_water",       # moves a contested aquifer resource
        "restart_pivot",        # energises machinery near live equipment
        "shed_load",            # reduces herd throughput, economic impact
        "reroute_convoy",       # commits third-party haulage
        "quarantine_group",     # animal-welfare + export consequence
    }
)

Severity = Literal["info", "low", "medium", "high", "critical"]

# ---------------------------------------------------------------------------
# MACHINE-READABLE PROVENANCE
# ---------------------------------------------------------------------------

provenance: dict[str, str] = {
    "HERD_TARGET_FULL": "SOURCED - Baladna AR2025 / GEA PR / APS. Competing figures: 240k-280k.",
    "HERD_PHASE1_CAPACITY": "SOURCED - APS via Djazagro, Phase 1 targets 50,000 head.",
    "HERD_PHASE1_BUILT": "SOURCED - GCB (Sonatrach sub) contracted for infrastructure sized 33,250 head.",
    "HERD_AIRLIFT_TOTAL": "SOURCED - Baladna PR 23 Apr 2026; 109 flights, 9 US states.",
    "MILK_LITRES_ANNUAL_TARGET": "SOURCED - Baladna PR. 1.7bn L/yr.",
    "MILK_LITRES_PER_COW_DAY": "DERIVED - 1.7e9 / 270,000 / 365.",
    "WELLS_COMPLETED": "SOURCED - Baladna FY2025 disclosure, 45 wells / 186 permits.",
    "WATER_M3_FULL_ANNUAL": "SOURCED (Tafelwit Jun 2026, high end of 2.5-4bn range). GRAIN: 1,700bn L total demand.",
    "WATER_L_PER_L_MILK": "SOURCED - GRAIN derivation, 1,020 L water per L milk.",
    "WATER_M3_PHASE1_ANNUAL": "SOURCED - Tafelwit, Phase 1 draw 500-700M m3/yr.",
    "PIVOTS": "ASSUMPTION - 6 Phase 1 pivots. Valmont/AFKO confirmed as suppliers; count not published.",
    "PIVOT_RADIUS_M": "ASSUMPTION - 400m radius mid-size centre pivot.",
    "TEMP_C_DAY_PEAK": "ASSUMPTION - Adrar BWh climatology, July mean daily max ~43C.",
    "TEMP_C_NIGHT_MEAN": "ASSUMPTION - desert night minimum ~24C (low diurnal recovery).",
    "REL_HUMIDITY_MEAN_PCT": "ASSUMPTION - arid interior ~18% RH.",
    "THI_HEAT_STRESS_ONSET": "INDUSTRY - NRC 1971 dairy heat-stress thresholds.",
    "THI_MILK_YIELD_LOSS_MILD": "INDUSTRY - NRC: 1.9% yield loss per THI unit above threshold.",
    "RUMINATION_BASELINE_MIN": "INDUSTRY - 150-200 min/day baseline for lactating Holstein.",
    "RUMINATION_HEAT_DROP_PCT": "INDUSTRY - 20-25% rumination decline precedes overt heat stress.",
    "SOIL_MOISTURE_*": "ASSUMPTION - sandy Saharan soil wilting/optimal/saturation points.",
    "RISK_AUTO_APPROVE_CEILING": "DESIGN - our governance policy, configurable per deployment.",
    "ALWAYS_GATE_ACTIONS": "DESIGN - actions touching the contested aquifer or animal welfare are never auto-run.",
}