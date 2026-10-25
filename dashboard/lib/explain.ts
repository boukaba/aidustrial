/**
 * The plain-language layer.
 *
 * Judges are not all technical. A raw reading like "EHL 69.8 (mild)" or
 * "SCC 150k / limit 200" tells a dairy person nothing useful and tells a
 * non-specialist nothing at all. Every figure in the product is paired with a
 * sentence someone outside the industry can act on.
 *
 * Rules used throughout:
 *   - lead with the consequence, not the measurement
 *   - name the unit only when it changes the decision
 *   - never invent a severity the data does not support
 */

export type Level = "ok" | "watch" | "act" | "stop";

export interface Plain {
  /** One sentence a non-specialist can read at a glance. */
  line: string;
  /** Why it matters, one more sentence. */
  because?: string;
  level: Level;
}

export const LEVEL_STYLE: Record<Level, string> = {
  ok: "border-sig-500/30 bg-sig-500/10 text-sig-400",
  watch: "border-warn-500/40 bg-warn-500/10 text-warn-400",
  act: "border-warn-500/50 bg-warn-500/15 text-warn-400",
  stop: "border-crit-500/50 bg-crit-500/15 text-crit-400",
};

export const LEVEL_LABEL: Record<Level, string> = {
  ok: "Healthy",
  watch: "Watch",
  act: "Needs action",
  stop: "Act now",
};

/* ------------------------------------------------------------------ HEAT */

export function explainHeatLoad(ehl: number, band: string): Plain {
  if (band === "severe") {
    return {
      line: "The heat is dangerous for the cows right now.",
      because:
        "Cows cannot shed heat fast enough in dry desert air when it is this hot. Milk drops and, in the worst cases, animals go down.",
      level: "stop",
    };
  }
  if (band === "moderate") {
    return {
      line: "The cows are getting hot and losing milk.",
      because:
        "Above about 68 on this scale, cows start eating less and producing less milk. Catching it now prevents the loss compounding.",
      level: "act",
    };
  }
  if (band === "mild") {
    return {
      line: "Warm, but the herd is coping.",
      because:
        "The air is dry enough that the cows shed heat reasonably well. Worth watching, not worth intervening yet.",
      level: "watch",
    };
  }
  return {
    line: "The herd is comfortable.",
    because: "Night-time cooling is doing its job. This is the good case.",
    level: "ok",
  };
}

export function explainSoilMoisture(pct: number): Plain {
  if (pct <= 9) {
    return {
      line: "This field has run out of water. The crop is not growing at all.",
      because:
        "Below this point crops stop accumulating mass entirely. It is not a delay, whatever this crop was going to yield is already lost.",
      level: "stop",
    };
  }
  if (pct < 22) {
    return {
      line: "This field is drying out and needs water soon.",
      because: "Still growing, but every day without irrigation costs yield.",
      level: "act",
    };
  }
  return {
    line: "This field has enough water.",
    because: "Growth is at full rate.",
    level: "ok",
  };
}

export function explainRumination(deficitPct: number): Plain {
  if (deficitPct >= 15) {
    return {
      line: "The cows are barely chewing. This is the classic sign of heat stress.",
      because:
        "Cows stop chewing 12 to 18 hours before their temperature rises. By the time you can see them panting, the milk is already gone.",
      level: "stop",
    };
  }
  if (deficitPct >= 10) {
    return {
      line: "Chew activity has dropped. The herd is under heat pressure.",
      because: "This is the early warning. It is still cheap to fix today.",
      level: "act",
    };
  }
  if (deficitPct >= 5) {
    return {
      line: "Chew activity is slightly down.",
      because: "Worth watching. Normal variation at this level.",
      level: "watch",
    };
  }
  return { line: "The herd is chewing normally.", level: "ok" };
}

export function explainAquifer(pct: number): Plain {
  if (pct >= 100) {
    return {
      line: "Water use is above what the underground supply can sustain in a year.",
      because:
        "This water is fossil, it does not refill. Whatever is drawn now is gone permanently.",
      level: "stop",
    };
  }
  if (pct >= 85) {
    return {
      line: "Water use is close to the sustainable yearly limit.",
      because: "Fine for now, but the current rate cannot run for twelve months.",
      level: "act",
    };
  }
  if (pct >= 60) {
    return {
      line: "Water use is substantial but inside the limit.",
      because: "Worth planning around before the next dry season.",
      level: "watch",
    };
  }
  return { line: "Water use is well inside the sustainable limit.", level: "ok" };
}

export function explainFeed(coverHours: number): Plain {
  const days = coverHours / 24;
  if (coverHours < 24) {
    return {
      line: "There is less than a day of feed left on site.",
      because: "You need purchased feed on the next truck.",
      level: "stop",
    };
  }
  if (coverHours < 72) {
    return {
      line: `About ${days.toFixed(1)} days of feed in store.`,
      because: "Enough for the week, but nothing spare.",
      level: "act",
    };
  }
  return {
    line: `${days.toFixed(0)} days of feed in store.`,
    because: "Comfortable. The herd is not the constraint right now.",
    level: "ok",
  };
}

export function explainScc(scc: number, limit: number): Plain {
  if (scc > 300) {
    return {
      line: "The milk is failing a quality test.",
      because:
        "Mastitis in the cows is showing up in the bulk tank. This costs money on every litre until the affected cows are treated or culled.",
      level: "stop",
    };
  }
  if (scc > limit) {
    return {
      line: "Milk quality is drifting outside the legal limit.",
      because: "Still saleable, but it attracts a penalty and the trend is worsening.",
      level: "act",
    };
  }
  return {
    line: "Milk quality is inside the legal limit.",
    because: "The herd is clean enough on a bulk basis.",
    level: "ok",
  };
}

export function explainBulkTemp(c: number): Plain {
  if (c > 8) {
    return {
      line: "Milk in the tank is too warm and will be rejected.",
      because: "Above this temperature the plant refuses the load. That milk is a total loss.",
      level: "stop",
    };
  }
  if (c > 6.5) {
    return {
      line: "Milk in the tank is warmer than it should be.",
      because: "Still shippable, but quality is dropping while it sits.",
      level: "act",
    };
  }
  return { line: "Milk is properly chilled.", level: "ok" };
}

export function explainCropHealth(health: string, stressDays: number): Plain {
  if (health === "critical") {
    return {
      line: "Growth has stopped on this field.",
      because: `${stressDays} consecutive day${stressDays === 1 ? "" : "s"} without enough water.`,
      level: "stop",
    };
  }
  if (health === "degraded") {
    return { line: "This field is struggling.", because: "Growth has slowed and quality is dropping.", level: "act" };
  }
  return { line: "Growing normally.", level: "ok" };
}

export function explainHeiferWeight(pct: number): Plain {
  if (pct < 80) {
    return {
      line: "These heifers are too light to breed on schedule.",
      because:
        "A heifer that breeds late calves late, and that delay repeats every cycle after. She is eating feed without producing milk.",
      level: "stop",
    };
  }
  if (pct < 88) {
    return {
      line: "These heifers are a little under target breeding weight.",
      because: "A small ration adjustment now saves a cycle later.",
      level: "act",
    };
  }
  return { line: "On target for breeding.", because: "Will calve close to the 23-month target.", level: "ok" };
}

export function explainScours(ratePct: number): Plain {
  if (ratePct > 6) {
    return {
      line: "Calves have diarrhoea and some are dying.",
      because:
        "Calf scours in the first weeks is the biggest survival loss on any dairy. It shows up as a heifer that never reaches breeding weight 18 months later.",
      level: "stop",
    };
  }
  return { line: "Calves are healthy.", level: "ok" };
}

export function explainParlour(downtimeMin: number): Plain {
  if (downtimeMin > 180) {
    return {
      line: "Cows are waiting hours to be milked.",
      because:
        "Not just a throughput problem, cows standing in an unshaded desert yard is the worst heat exposure on the site.",
      level: "stop",
    };
  }
  if (downtimeMin > 60) {
    return {
      line: "The milking equipment has lost time today.",
      because: "Every minute is a cow milked late, which costs yield for that lactation.",
      level: "act",
    };
  }
  return { line: "Milking is running normally.", level: "ok" };
}

export function explainMisting(on: boolean, covered: number, total: number): Plain {
  if (on) {
    return {
      line: `Cooling is running for ${covered} of ${total} barns.`,
      because: "Only these barns are protected from the heat.",
      level: "watch",
    };
  }
  return {
    line: `No barns are being actively cooled. ${total - covered} of ${total} have no cooling equipment at all.`,
    because:
      "This is the site's real constraint: cooling water is cheap, but cooling hardware was only installed in half the barns.",
    level: "act",
  };
}

/* --------------------------------------------------------- AREA SUMMARIES */

export type AreaId = "crop" | "livestock" | "milk" | "infrastructure" | "mesh";

export function cropSummary(c: {
  standing_t: number;
  water_stressed_ha: number;
  status: string;
  harvested_t: number;
}): Plain {
  if (c.water_stressed_ha > 0) {
    return {
      line: "The fields have run dry and the crop has stopped growing.",
      because: `${Math.round(c.water_stressed_ha)} hectares are affected. Harvest so far is ${Math.round(c.harvested_t)} tonnes.`,
      level: "stop",
    };
  }
  return {
    line: "The crop programme is on track.",
    because: `${Math.round(c.standing_t)} tonnes of forage standing, ready for cutting.`,
    level: "ok",
  };
}

export function livestockSummary(l: {
  non_productive_head: number;
  total_head: number;
  calf_mortality_7d: number;
  status: string;
}): Plain {
  const pct = (l.non_productive_head / Math.max(l.total_head, 1)) * 100;
  if (l.calf_mortality_7d > 4) {
    return {
      line: "Calves are dying at a rate that needs attention.",
      because: `${l.calf_mortality_7d} deaths in the last week.`,
      level: "stop",
    };
  }
  return {
    line: `${pct.toFixed(0)}% of the herd produces no milk yet.`,
    because:
      "Most of the site is heifers and calves. They eat feed and water now, and start paying that back about 18 months after they arrive.",
    level: "watch",
  };
}

export function milkSummary(m: {
  bulk_scc_k: number;
  scc_limit_k: number;
  bulk_temp_c: number;
  downtime_min_24h: number;
  capture_ratio: number;
}): Plain {
  if (m.bulk_temp_c > 8) return { line: "Milk in the tank is too warm and will be rejected.", level: "stop" };
  if (m.bulk_scc_k > m.scc_limit_k)
    return {
      line: "Milk quality is outside the legal limit.",
      because: "The cause is in the cows, not the plant.",
      level: "act",
    };
  if (m.downtime_min_24h > 60)
    return { line: "Milking has lost time today.", because: "Cows are waiting to be milked.", level: "act" };
  return {
    line: "Milk is flowing, chilled and within spec.",
    because: `${m.capture_ratio.toFixed(0)}% of what the herd produced has been collected.`,
    level: "ok",
  };
}

/* -------------------------------------------------------------- GLOSSARY */

export const GLOSSARY: Record<string, string> = {
  EHL: "Effective Heat Load. How hard the heat is on a cow, combining air temperature, humidity and direct sun. Ordinary temperature alone understates it in a sunny desert.",
  THI: "Temperature-Humidity Index. The standard heat measure, based on air and humidity. In dry desert air this reads surprisingly low, which is why we also use EHL.",
  "Rumination": "How long cows spend chewing each day, measured by a collar. It collapses before their body temperature does, which makes it the earliest heat warning.",
  SCC: "Somatic Cell Count. A measure of infection in the milk. High numbers mean dirty milk and a price penalty. The legal limit is 200 thousand cells per millilitre.",
  "Aquifer": "An underground water store. The one under Adrar is fossil water, it formed thousands of years ago and does not refill.",
  DM: "Dry Matter. Crop mass without the water in it. This is what the herd actually eats, so it is what gets measured.",
  Ensiling: "Storing grass or corn siloed and fermented, the way hay is stored. Preserves it for winter.",
  Misting: "Spraying fine water at cows. In dry air the water evaporates and pulls heat off the animal, which is why it works so well in a desert.",
  Holstein: "The black-and-white dairy breed. High volume but relatively heat-sensitive.",
  "Water-stress days": "Consecutive days a field went without enough water.",
  CC: "Counting cells per millilitre, the raw number behind SCC.",
  Fodder: "Feed grown on the farm, mainly for the cows.",
  "Non-renewable": "Cannot be replaced on any human timescale.",
  "Standing DM": "Crop that is growing in the field right now, measured without water.",
  "Bulk tank": "The refrigerated tank milk is held in before it goes to the powder plant.",
};

export const ARIA_LABEL: Record<AreaId, string> = {
  crop: "Crop production",
  livestock: "Livestock",
  milk: "Milk production",
  infrastructure: "Water, pivots and feed",
  mesh: "The agents talking",
};