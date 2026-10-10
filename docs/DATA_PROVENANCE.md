# Data Provenance

Every number in the digital twin is classified. Nothing is invented silently.

| Class | Meaning |
|---|---|
| **SOURCED** | Appears in a public Baladna, Algerian government, GEA or supplier document. Source given. |
| **DERIVED** | Arithmetic on sourced values. Formula given. |
| **INDUSTRY** | Standard dairy/veterinary literature (NRC thresholds, rumination baselines). |
| **ASSUMPTION** | Our engineering estimate where no public figure exists. This is the class to challenge. |
| **DESIGN** | A deliberate product decision (risk policy, batching). Not physics. |
| **MODELLED** | Physics we wrote rather than took from literature, because no single published model fits. |

## The honest headline

**The Baladna Algeria site has no operational herd and no operating telemetry.**
45 wells are drilled, one barley crop has been harvested, 30,000 cows land in
November 2026, and first milk powder is targeted for late 2027. Every number on
the dashboard is produced by a simulator we wrote, seeded with the sourced
parameters below.

What is real: the site's physics, the constraints it operates under, the supply
chain, the supplier list, and the fact that a scarce resource must be allocated
under pressure by a human being. What is not real: the telemetry itself.

## Why this framing rather than "we connected to live sensors"

Anyone who has run a dairy will ask where the data comes from. An honest answer
that the Adrar site is pre-operational is stronger than a fake integration,
because it reframes the product: **the highest-value time to deploy agentic
operations is before the first animal arrives.** Right now the site has civil
works done, 186 drilling permits and no herd. In that window the agents plan
water, feed and capacity rather than react to incidents. That is a real job with
real money attached, and it is exactly the window Baladna is in.

## Land area: an unresolved conflict in the source documents

| Source | Area |
|---|---|
| **baladna-algeria.dz** (operator's own project site) | **219,000 ha** |
| Baladna Q.P.S.C. Annual Report 2025 | 117,000 ha |
| Baladna framework agreement press release (Apr 2024) | 117,000 ha |
| GEA Group press release (Jul 2025) | 117,000 ha |
| Gulf Times, TSA-Algérie, FPT Industrial, Twala, GRAIN | 117,000 ha |

We model **117,000 ha** because that is the number lenders and the Algerian state
work with. We flag it because Algerian job applicants are being recruited
against 219,000 ha. Unexplained as of this build.

## Employment: three published figures

| Figure | Source | Date |
|---|---|---|
| 5,000 direct jobs | Algerian government / APS | Apr 2024 |
| 15,000+ jobs | Baladna Q.P.S.C. | Apr 2026 |
| **1,000 posts by 2027** | baladna-algeria.dz recruitment campaign | Sep 2026 |

We surface the 1,000 figure because the recruitment is live now. This makes
capital-per-job *worse* than the headline claim, not better.

## The heat model, and why it is not simply "it's 45 degrees"

Air THI in Adrar is genuinely **low**. At 43 °C and ~10 % relative humidity the
NRC index sits around 41, well under the 68 that starts dairy heat stress. Dry
heat is much less dangerous to a cow than humid heat, and pretending otherwise
would be the easiest way for a knowledgeable judge to dismiss this whole build.

The risk in Adrar comes from **radiant load instead**: Holstein black patches in
direct sun run well above ambient, and the site is near-permanent clear sky. So
the twin computes

    Effective Heat Load  =  air THI  +  exposure-weighted solar load

with solar geometry peaking at solar noon (12:00), correctly lagging the
temperature peak (15:00), and an exposure term for how much of the animal's day
is spent unshaded (parlour approach, holding area, water trough). Under the
simulated heatwave that pushes the load into the moderate band and produces the
rumination collapse the veterinarian exists to catch.

The radiant term is **MODELLED**, not sourced. It is the assumption most worth
arguing with.

## A framing we explicitly do not make

It is tempting to say cooling water competes with irrigation for the aquifer.
The arithmetic does not support it, and we say so in the code:

    4 misting banks      =     53 m3/h
    6 centre pivots      = 27,143 m3/h
    33,250 cows drinking =    ~111 m3/h

Misting is 0.2 % of pivot draw. The genuine contests are herd drinking water
against the annual aquifer envelope, and pivot allocation across fields to keep
projected annual draw inside budget. **Misting is constrained by hardware, not
water** — Phase 1 installed it in only 4 of 8 barns. That turns the interesting
decision from a switch into an allocation, which is the better demo and the more
honest one.

## Constant register

| Constant | Class | Provenance |
|---|---|---|
| `HERD_TARGET_FULL` | **SOURCED** | SOURCED - Baladna AR2025 / GEA PR / APS. Competing figures: 240k-280k. |
| `HERD_PHASE1_CAPACITY` | **SOURCED** | SOURCED - APS via Djazagro, Phase 1 targets 50,000 head. |
| `HERD_PHASE1_BUILT` | **SOURCED** | SOURCED - GCB (Sonatrach sub) contracted for infrastructure sized 33,250 head. |
| `HERD_AIRLIFT_TOTAL` | **SOURCED** | SOURCED - Baladna PR 23 Apr 2026; 109 flights, 9 US states. |
| `MILK_LITRES_ANNUAL_TARGET` | **SOURCED** | SOURCED - Baladna PR. 1.7bn L/yr. |
| `MILK_LITRES_PER_COW_DAY` | **DERIVED** | DERIVED - 1.7e9 / 270,000 / 365. |
| `WELLS_COMPLETED` | **SOURCED** | SOURCED - Baladna FY2025 disclosure, 45 wells / 186 permits. |
| `WATER_M3_FULL_ANNUAL` | **SOURCED** | SOURCED (Tafelwit Jun 2026, high end of 2.5-4bn range). GRAIN: 1,700bn L total demand. |
| `WATER_L_PER_L_MILK` | **SOURCED** | SOURCED - GRAIN derivation, 1,020 L water per L milk. |
| `WATER_M3_PHASE1_ANNUAL` | **SOURCED** | SOURCED - Tafelwit, Phase 1 draw 500-700M m3/yr. |
| `PIVOTS` | **ASSUMPTION** | ASSUMPTION - 6 Phase 1 pivots. Valmont/AFKO confirmed as suppliers; count not published. |
| `PIVOT_RADIUS_M` | **ASSUMPTION** | ASSUMPTION - 400m radius mid-size centre pivot. |
| `TEMP_C_DAY_PEAK` | **ASSUMPTION** | ASSUMPTION - Adrar BWh climatology, July mean daily max ~43C. |
| `TEMP_C_NIGHT_MEAN` | **ASSUMPTION** | ASSUMPTION - desert night minimum ~24C (low diurnal recovery). |
| `REL_HUMIDITY_MEAN_PCT` | **ASSUMPTION** | ASSUMPTION - arid interior ~18% RH. |
| `THI_HEAT_STRESS_ONSET` | **INDUSTRY** | INDUSTRY - NRC 1971 dairy heat-stress thresholds. |
| `THI_MILK_YIELD_LOSS_MILD` | **INDUSTRY** | INDUSTRY - NRC: 1.9% yield loss per THI unit above threshold. |
| `RUMINATION_BASELINE_MIN` | **INDUSTRY** | INDUSTRY - 150-200 min/day baseline for lactating Holstein. |
| `RUMINATION_HEAT_DROP_PCT` | **INDUSTRY** | INDUSTRY - 20-25% rumination decline precedes overt heat stress. |
| `SOIL_MOISTURE_*` | **ASSUMPTION** | ASSUMPTION - sandy Saharan soil wilting/optimal/saturation points. |
| `RISK_AUTO_APPROVE_CEILING` | **DESIGN** | DESIGN - our governance policy, configurable per deployment. |
| `ALWAYS_GATE_ACTIONS` | **DESIGN** | DESIGN - actions touching the contested aquifer or animal welfare are never auto-run. |

## Constants not individually registered

| Name | Class | Note |
|---|---|---|
| `SILOS_ON_SITE`, `SILO_CAPACITY_TONNES` | ASSUMPTION | 6 silos × 12,000 t. No public figure. |
| `PIVOTS`, `PIVOT_RADIUS_M` | ASSUMPTION | 6 Phase 1 pivots. Valmont/AFKO confirmed as suppliers; unit count and size are not published. |
| `COOLING_MISTERS_INSTALLED`, `MISTER_FLOW_LPM`, `FAN_INSTALLED` | ASSUMPTION | 4 banks × 220 L/min; 180 fans. |
| `SOIL_MOISTURE_*` | ASSUMPTION | Sandy Saharan profile wilting/optimal/saturation. |
| `MOTOR_BEARING_*`, `PIVOT_VIBRATION_WARN_MM_S` | ASSUMPTION | Vendor alarm setpoints are proprietary and site-specific. |
| `FORAGE_DRY_MATTER_PCT`, `AIR_FREIGHT_FEED_GAP_DAYS` | ASSUMPTION | 32 % DM; 210-day herd-before-fodder window. |
| `LATITUDE`, `LONGITUDE`, `ELEVATION_M` | SOURCED | Adrar, 27.8743 N, -0.2939 E, ~264 m. |
| `TEMPERATURE_HUMIDITY_INDEX` formula | INDUSTRY | NRC / Tucker: `(1.8·T) + (RH − (0.55 − 0.0011·T)·27.9) − 29.9`. |
| `RISK_AUTO_APPROVE_CEILING`, `RISK_GATE_*` | DESIGN | 40 / 55 / 80. Ours to tune per deployment. |
| `ALWAYS_GATE_ACTIONS` | DESIGN | Never auto-execute; touches the aquifer or animal welfare. |
| `score_risk`, `score_urgency` | DESIGN | Deterministic, inspectable functions of their inputs. |

## What would make this real

The tool layer in `agent/src/aidustrial/tools/sensors.py` is the only boundary
between agents and the world. Replacing the twin with live vendor APIs means
reimplementing that module against:

- **Valmont / AFKO** pivot telemetry (soil moisture, bearing temp, vibration, GPS)
- **Herd smart collars** (rumination, activity, core temperature, location)
- **Parlour systems** (milk yield per cow, conductivity, SCC)
- **Silo weighing** (load cells or load-cell belts)
- **GPS/telematics** on milk tankers and feed trucks
- **Well meters** on the 45 completed boreholes

Nothing above the tool layer changes. That is the point of the boundary.
