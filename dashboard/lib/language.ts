/**
 * Single source of truth for user-facing language.
 *
 * The complaint that drove this file: the UI was readable only by someone who
 * already runs a dairy. Every label here is written for a curious adult who
 * does not know the domain. Technical terms are not banned, they are hidden
 * behind a "details" disclosure and kept available for operators.
 *
 * Rule followed throughout: name the thing by what it DOES, not by what it is
 * called in the industry.
 */

export const NAV = [
  { id: "home", icon: "🏠", label: "What's happening", sub: "One screen" },
  { id: "agents", icon: "🤖", label: "Agents at work", sub: "Watch them think" },
  { id: "orchestrator", icon: "🎛", label: "The orchestrator", sub: "Who wakes, and when" },
  { id: "crop", icon: "🌾", label: "Cow food", sub: "Fields and water" },
  { id: "livestock", icon: "🐄", label: "The herd", sub: "Cows and calves" },
  { id: "milk", icon: "🥛", label: "The milk", sub: "Milking and quality" },
  { id: "infrastructure", icon: "💧", label: "Water & machines", sub: "Pumps, pivots, feed" },
  { id: "decisions", icon: "🖐", label: "Decisions", sub: "What you've approved" },
  { id: "system", icon: "🧠", label: "How it works", sub: "The rules they follow" },
] as const;

export type NavId = (typeof NAV)[number]["id"];

// Agent names/roles now live in lib/identity.ts alongside each agent's colour,
// monogram and glyph. Re-exported here so existing imports keep resolving.
export { agentName as AGENT_NAME, agentRole as AGENT_ROLE } from "./identity";

/** Industry term -> what it actually means, for the "details" disclosures. */
export const TERM: Record<string, string> = {
  "Effective heat load":
    "How hard the heat is on the cows. Combines air temperature, humidity and direct sunshine. Ordinary temperature alone understates it in a sunny desert.",
  "THI": "Temperature-Humidity Index, the standard heat measure for farm animals.",
  "Rumination":
    "How long the cows spend chewing each day. Collapses before their temperature does, so it is the earliest warning of heat stress.",
  "Somatic cell count":
    "A measure of infection in the milk. High numbers mean dirty milk and a price penalty. The legal limit is 200 thousand cells per millilitre.",
  "Aquifer": "An underground water store. The one under Adrar is fossil water, it formed thousands of years ago and does not refill.",
  "Fossil aquifer": "Groundwater that took millennia to accumulate and is now being removed far faster than it can form.",
  "Pivot": "A centre-pivot irrigation machine, a long pipe on wheels that rotates slowly around a field, spraying water.",
  "Standing DM": "How much crop is growing in the field right now, measured without the water in it.",
  "DM": "Dry Matter, the part of the feed the cow can actually use.",
  "Fodder": "Feed grown on the farm for the cows.",
  "Forage": "Grass, corn and other feed crops grown for animals.",
  "Ensiling": "Storing cut grass or corn in an airtight silo so it ferments and keeps.",
  "Silo": "A sealed store for animal feed.",
  "Parlour": "The milking shed where cows are milked.",
  "Heifer": "A young cow that has not had a calf yet.",
  "Dry cow": "A cow that is not pregnant and not being milked, resting before her next calf.",
  "SCC": "Somatic Cell Count, see above.",
  "Misting":
    "Spraying fine water at the cows. In dry desert air the water evaporates and pulls heat off the animal, which is why it works so well here.",
  "Holstein": "The black-and-white dairy breed used here.",
  "Breeding weight":
    "The weight a young cow has to reach before she can safely get pregnant. Below it, she calves late, and that delay repeats every cycle.",
  "Calving": "A cow giving birth.",
  "Bulk tank": "The refrigerated tank where milk is held before it goes to the powder plant.",
  "Spray dryer": "The machine that turns milk into powdered milk.",
  "Projected annual draw":
    "If the site keeps using water at today's rate for a whole year, how much of its yearly allowance that would use.",
  "Concession": "A long lease of government land granted to the project.",
};

/** Headline sentences. One clear verdict, never a wall of numbers. */
export type Status = "good" | "watch" | "act" | "stop";

export const STATUS_WORD: Record<Status, string> = {
  good: "All good",
  watch: "Keep an eye on it",
  act: "Needs attention",
  stop: "Act now",
};

export function statusColour(s: Status): string {
  return s === "good"
    ? "border-sig-500/30 bg-sig-500/10 text-sig-400"
    : s === "watch"
      ? "border-warn-500/40 bg-warn-500/10 text-warn-400"
      : s === "act"
        ? "border-warn-500/50 bg-warn-500/15 text-warn-400"
        : "border-crit-500/50 bg-crit-500/15 text-crit-400";
}

export const STATUS_RING: Record<Status, string> = {
  good: "stroke-sig-500",
  watch: "stroke-warn-400",
  act: "stroke-warn-500",
  stop: "stroke-crit-500",
};

/** Short labels for the simplified home cards. */
export const SHORT = {
  airTemp: "Air temperature",
  heatCows: "Heat on the cows",
  water: "Water used",
  herdSize: "Animals on the farm",
  cowFood: "Cow food in store",
  milkDay: "Milk per day",
  milkQuality: "Milk quality",
  milkSaved: "Milk actually collected",
  chewing: "How much the cows are chewing",
  youngCows: "Young cows ready to breed",
  fieldsDry: "Fields short of water",
  cropReady: "Food growing now",
  machines: "Machines running",
  paused: "Waiting for you",
};