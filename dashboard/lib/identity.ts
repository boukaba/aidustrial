/**
 * Visual identity for the seven specialists.
 *
 * The complaint this file answers: every agent used to render as the same dark
 * card with a different name, so a viewer could not tell at a glance WHO was
 * working or HOW. Each agent now owns one colour, one monogram, and one glyph.
 *
 * The colours are the load-bearing part. They are spaced around the hue wheel
 * and all chosen to sit bright on a near-black ground, so seven simultaneous
 * agents read as seven distinct live signals rather than one grey mass.
 */

export interface AgentIdentity {
  id: string;
  /** the human name shown to a non-technical viewer */
  name: string;
  /** two-letter monogram for the avatar badge */
  mono: string;
  /** one line, what this agent does all day */
  role: string;
  /** hex, used for the colour rail, avatar, glow and status ring */
  hex: string;
  /** tailwind text class matching hex, for inline text colour */
  text: string;
  /** svg path data on a 24x24 grid, stroked */
  glyph: string;
}

const A = (
  id: string,
  name: string,
  mono: string,
  role: string,
  hex: string,
  text: string,
  glyph: string,
): AgentIdentity => ({ id, name, mono, role, hex, text, glyph });

export const AGENTS: Record<string, AgentIdentity> = {
  crop: A(
    "crop",
    "Field agent",
    "FL",
    "watches the fields and what is growing",
    "#a3e635",
    "text-lime-300",
    "M12 21V11 M12 11c0-3-2-5-6-5 0 4 2 5 6 5z M12 13c0-3 2-5 6-5 0 4-2 5-6 5z",
  ),
  agronomist: A(
    "agronomist",
    "Water specialist",
    "WS",
    "decides how much water the farm can afford",
    "#22d3ee",
    "text-cyan-300",
    "M12 3s-6 7-6 11a6 6 0 0 0 12 0c0-4-6-11-6-11z M9 14a3 3 0 0 0 3 3",
  ),
  veterinarian: A(
    "veterinarian",
    "Cow doctor",
    "VD",
    "watches cow health, heat and rumination",
    "#34d399",
    "text-emerald-300",
    "M12 20s-7-4.4-7-9a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 4.6-7 9-7 9z",
  ),
  calving: A(
    "calving",
    "Calving agent",
    "CV",
    "keeps the next generation of cows coming",
    "#c084fc",
    "text-purple-300",
    "M12 3v3 M5.6 9.6l2.1 2.1 M18.4 9.6l-2.1 2.1 M3 18h18 M6.5 18a5.5 5.5 0 0 1 11 0",
  ),
  milking: A(
    "milking",
    "Milking agent",
    "MK",
    "runs the milking parlour and milk quality",
    "#38bdf8",
    "text-sky-300",
    "M8 3h8v2.5A4.5 4.5 0 0 1 12 10 4.5 4.5 0 0 1 8 5.5V3z M12 10v11 M8.5 21h7",
  ),
  maintenance: A(
    "maintenance",
    "Machine engineer",
    "MT",
    "keeps pivots, chillers and pumps alive",
    "#fbbf24",
    "text-amber-300",
    "M20.4 6.6a3.6 3.6 0 0 1-4.6 4.6L6.8 20.2a2.2 2.2 0 0 1-3.1-3.1l9-9a3.6 3.6 0 0 1 4.6-4.6l-2.5 2.5 2.2 2.2 2.4-1.6z",
  ),
  logistics: A(
    "logistics",
    "Supply agent",
    "LG",
    "brings in feed, animals and parts",
    "#fb7185",
    "text-rose-300",
    "M3 7h11v10H3z M14 10h4l3 3v4h-7z M7.5 18.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z M17.5 18.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  ),
  orchestrator: A(
    "orchestrator",
    "Coordinator",
    "OR",
    "collects every specialist's input and decides what you see",
    "#e2e8f0",
    "text-slate-200",
    "M12 12m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M12 4v5.5 M12 14.5V20 M5 8l4.2 2.4 M14.8 13.6L19 16 M5 16l4.2-2.4 M14.8 10.4L19 8",
  ),
};

/** Falls back to a sensible identity rather than breaking on an unknown id. */
export const agent = (id: string): AgentIdentity =>
  AGENTS[id] ?? {
    id,
    name: id,
    mono: id.slice(0, 2).toUpperCase(),
    role: "",
    hex: "#94a3b8",
    text: "text-slate-400",
    glyph: "M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0",
  };

export const agentName = (id: string) => agent(id).name;
export const agentRole = (id: string) => agent(id).role;
export const agentHex = (id: string) => agent(id).hex;

/** The seven working specialists, in reading order. */
export const SPECIALISTS = [
  "crop",
  "agronomist",
  "veterinarian",
  "calving",
  "milking",
  "maintenance",
  "logistics",
] as const;
