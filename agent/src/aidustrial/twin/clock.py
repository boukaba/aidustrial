"""Deterministic simulated clock.

The twin advances in discrete ticks rather than wall-clock time. Every run is
reproducible from a seed, which matters when you are demonstrating an audit
trail: a judge can ask "why did the vet agent escalate on tick 41?" and you can
replay tick 41 exactly.

Tick = 30 simulated minutes by default, so one 24h day = 48 ticks. Diurnal
temperature drives the THI curve, which is what makes heat stress appear at the
same hour every day -- exactly like Adrar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import constants as C


@dataclass(frozen=True)
class SimClock:
    """Immutable clock state. Advancing returns a new clock (never mutates)."""

    tick: int = 0
    minutes_per_tick: int = 30

    # --- derived -------------------------------------------------------

    @property
    def ticks_per_day(self) -> int:
        return (24 * 60) // self.minutes_per_tick

    @property
    def day(self) -> int:
        return self.tick // self.ticks_per_day

    @property
    def hour(self) -> float:
        return (self.tick % self.ticks_per_day) * self.minutes_per_tick / 60.0

    @property
    def phase(self) -> str:
        h = self.hour
        if 5 <= h < 8:
            return "dawn"
        if 8 <= h < 17:
            return "day"
        if 17 <= h < 20:
            return "dusk"
        return "night"

    @property
    def iso(self) -> str:
        return f"D{self.day:03d} {int(self.hour):02d}:{int((self.hour % 1) * 60):02d}"

    # --- transitions ---------------------------------------------------

    def advance(self, n: int = 1) -> SimClock:
        return SimClock(self.tick + n, self.minutes_per_tick)

    def seconds_into_day(self) -> float:
        return self.hour * 3600.0

    # --- weather -------------------------------------------------------

    def temperature_c(self, day_weather: float = 1.0) -> float:
        """True 24-hour sinusoidal diurnal curve, peaking ~15:00.

        Max and min are 12h apart on a sinusoid, which puts the minimum at
        03:00 -- close enough to the observed Saharan pre-dawn minimum. Using a
        partial span here is a trap: it makes the curve fall back into the
        evening like a sunset rather than holding a shoulder, which is what
        real desert temperatures do.

        `day_weather` in [0.7, 1.3] scales the daily amplitude for heatwave events.
        """
        mean = (C.TEMP_C_DAY_PEAK + C.TEMP_C_NIGHT_MEAN) / 2.0
        amplitude = (C.TEMP_C_DAY_PEAK - C.TEMP_C_NIGHT_MEAN) / 2.0
        phase = 2 * math.pi * (self.hour - 15.0) / 24.0
        return mean + amplitude * day_weather * math.cos(phase)

    def relative_humidity(self, day_weather: float = 1.0) -> float:
        """Inverse of temperature -- arid air dries as it heats."""
        t = self.temperature_c(day_weather)
        base = C.REL_HUMIDITY_MEAN_PCT
        # Dewpoint roughly constant in arid climates.
        dewpoint = 4.0
        rh = 100.0 * (math.exp((17.625 * dewpoint) / (243.04 + dewpoint)) /
                      math.exp((17.625 * t) / (243.04 + t)))
        return max(3.0, min(95.0, min(base * 2.0, rh)))

    def wind_kmh(self, gust: float = 0.0) -> float:
        base = C.WIND_MEAN_KMH
        diurnal = 1.0 + 0.25 * math.sin(2 * math.pi * (self.hour - 8) / 24)
        return max(0.0, base * diurnal + gust)

    def th_i(self, day_weather: float = 1.0) -> float:
        """Air Temperature-Humidity Index (NRC / Tucker formulation).

        THI = (1.8 x Tdb) + (RH - (0.55 - 0.0011 x Tdb) x 27.9) - 29.9

        In a hot ARID climate this stays surprisingly low -- 43C at 18% RH gives
        THI ~51, well under the 68 dairy threshold. Dry heat is far less
        dangerous to a cow than humid heat. That is a real property of Adrar and
        the system should model it honestly rather than inventing humidity.
        """
        t = self.temperature_c(day_weather)
        rh = self.relative_humidity(day_weather)
        return (1.8 * t) + (rh - (0.55 - 0.0011 * t) * 27.9) - 29.9

    def solar_load(self, day_weather: float = 1.0, exposure: float = 0.55) -> float:
        """Radiant load on an animal in direct desert sun, weighted by exposure.

        WHY THIS TERM EXISTS. Air THI is built on wet-bulb depression and badly
        underestimates risk in hot-ARID, high-insolation climates. A Holstein's
        black patches in direct Saharan sun sit 15-20C above ambient, and Adrar
        is near-permanent clear sky. This is the standard argument against using
        air THI alone in desert dairies, and without it the model would report
        that a 46C day is harmless -- which is wrong, and would make the whole
        demonstration look naive to anyone who has run a desert dairy.

        Solar geometry peaks at solar NOON (12:00), correctly lagging the
        temperature peak at 15:00. That lag is real and is why peak heat load
        lands mid-afternoon rather than at the hottest instant.

        `exposure` is the fraction of the animal's day spent unshaded (parlour
        approach, holding area, water trough). Even fully-housed animals carry a
        SHADED_FLOOR of radiant exposure via open sides and transit, so the
        term never scales to zero -- it scales between a floor and full sun.

        MODELLED, not sourced. See DATA_PROVENANCE.md.
        """
        if not 6.0 <= self.hour <= 18.0:
            return 0.0
        geometry = math.sin(math.pi * (self.hour - 6.0) / 12.0)
        shaded_floor = 0.35
        weight = shaded_floor + (1.0 - shaded_floor) * min(1.0, max(0.0, exposure))
        full_sun_equivalent_c = 42.0
        return full_sun_equivalent_c * geometry * (0.94 + 0.06 * day_weather) * weight

    def effective_heat_load(self, day_weather: float = 1.0, exposure: float = 0.55) -> float:
        """EHL = air THI + exposure-weighted radiant load. Drives physiology."""
        return self.th_i(day_weather) + self.solar_load(day_weather, exposure)