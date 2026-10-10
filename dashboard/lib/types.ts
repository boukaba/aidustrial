export type Severity = "info" | "low" | "medium" | "high" | "critical";

export interface Pivot {
  name: string;
  field_ha: number;
  running: boolean;
  soil_moisture_pct: number;
  bearing_temp_c: number;
  vibration_mm_s: number;
  motor_hours: number;
  nozzles_blocked: number;
  health: string;
}

export interface BarnGroup {
  name: string;
  barn: string;
  head: number;
  rumination_min: number;
  rumination_pct: number;
  body_temp_c: number;
  milk_kg_day: number;
  milk_yield_pct: number;
  heat_stress: string;
  heat_abatement_active: boolean;
  cooling_effective_pct: number;
  misters_available: number;
  misting_enabled: boolean;
  mastitis_cases: number;
  lameness_cases: number;
  mortality_24h: number;
  status: string;
}

export interface Silo {
  name: string;
  feed_type: string;
  fill_t: number;
  fill_pct: number;
  hours_of_cover: number;
  inlet_operational: boolean;
  inlet_type: string;
  status: string;
}

export interface Tanker {
  name: string;
  lat: number;
  lon: number;
  load_kg: number;
  fill_pct: number;
  coolant_temp_c: number;
  leg: string;
  status: string;
}

export interface Packet {
  tick: number;
  time: string;
  day: number;
  hour: number;
  phase: string;
  environment: {
    temperature_c: number;
    relative_humidity_pct: number;
    thi_air: number;
    solar_load: number;
    solar_exposure: number;
    effective_heat_load: number;
    heat_stress_band: string;
    wind_kmh: number;
    soil_moisture_pct: number[];
    soil_ph: number;
    soil_salinity_ds_m: number;
    aquifer_budget_used_pct: number;
    aquifer_status: string;
    aquifer_kind?: string;
    water_use_m3h: number;
    misters_on: boolean;
    pivots: Pivot[];
  };
  herd: {
    head: number;
    rumination_mean_min: number;
    rumination_deficit_pct: number;
    milk_loss_today_kg: number;
    groups: BarnGroup[];
  };
  logistics: {
    feed_total_t: number;
    feed_hours_of_cover: number;
    daily_demand_t: number;
    purchased_feed_t: number;
    airlift: {
      state: string;
      delivered: number;
      target: number;
      progress_pct: number;
      flights_completed: number;
    };
    silos: Silo[];
    tankers: Tanker[];
  };
  crop_production: {
    standing_t: number; harvested_t: number; cuts_completed: number;
    protein_pct: number; water_stressed_ha: number; annual_target_t: number; status: string;
    fields: {
      field_id: string; pivot_id: number; crop: string; area_ha: number;
      biomass_t_ha: number; standing_t: number; stage: string;
      soil_moisture_pct: number; ready_for_cut: boolean; water_stress_days: number; health: string;
    }[];
  };
  livestock: {
    total_head: number; lactating_head: number; non_productive_head: number;
    by_class: Record<string, number>; airlift_head: number; airlift_mix: Record<string, number>;
    calf_mortality_7d: number; status: string;
    calvings: { group_id: string; calvings: number; difficult_births: number; stillbirths: number }[];
    heifers: {
      group_id: string; head: number; age_months: number; avg_weight_kg: number;
      target_weight_kg: number; weight_pct_of_target: number; daily_gain_kg: number;
      pregnant: boolean; days_open: number; status: string;
    }[];
    calves: {
      group_id: string; head: number; age_days: number; avg_weight_kg: number;
      scours_rate_pct: number; mortality_7d: number; status: string;
    }[];
    dry_cows: { group_id: string; head: number; days_to_calving: number; bcs: number; status: string }[];
  };
  milk_production: {
    daily_milk_kg: number; daily_shipped_kg: number; daily_loss_kg: number; capture_ratio: number;
    lactating_head: number; milkings_per_day: number; units: number;
    throughput_cows_per_hour: number; downtime_min_24h: number;
    bulk_temp_c: number; bulk_tank_kg: number; bulk_fill_pct: number;
    condenser_fouling_pct: number; bulk_scc_k: number; scc_limit_k: number;
    quality_status: string; silo_fill_pct: number; powder_live: boolean; status: string;
  };
  board: {
    message_id: string; kind: string; sender: string; recipient: string;
    content: string; in_reply_to: string | null; severity: string;
    domains: string[]; expects_reply: boolean;
  }[];
  events: { tick: number; time: string; kind: string; message: string; severity: string }[];
}

export interface ActionPayload {
  action_id: string;
  action: string;
  target: string;
  rationale: string;
  requested_by: string;
  risk_score: number;
  urgency_score: number;
  urgency_band: string;
  severity: Severity;
  evidence: Record<string, unknown>;
  blast_radius: string;
  cost_of_inaction: string;
  reversible: boolean;
  risk_factors: string[];
  requires_human: boolean;
  gate_band: string;
}

export interface Summary {
  sim_time: string;
  day: number;
  hour: number;
  phase: string;
  temperature_c: number;
  thi_air: number;
  effective_heat_load: number;
  heat_stress_band: string;
  aquifer_pct: number;
  aquifer_status: string;
  herd_head: number;
  rumination_deficit: number;
  milk_loss_kg: number;
  feed_hours: number;
  airlift_delivered: number;
  airlift_target: number;
}

export interface TraceEvent {
  agent: string;
  phase: string;
  message: string;
  wall?: number;
  findings?: string[];
  proposals?: string[];
  approved?: boolean;
}

export interface StreamMessage {
  type: string;
  thread: string;
  packet: Packet;
  summary: Summary;
  pending: { action: ActionPayload; queued: ActionPayload[]; tick: number; sim_time: string } | null;
  findings: { agent: string; summary: string; severity: Severity; confidence: number; evidence: Record<string, unknown>; implies: string }[];
  trace: TraceEvent[];
  awaiting_decision: boolean;
  project: {
    name: string;
    location: string;
    operator: string;
    state_partner: string;
    ownership: string;
    aquifer: string;
  };
}

export const bandColor = (band: string) =>
  band === "severe"
    ? "text-crit-400 border-crit-500/40 bg-crit-500/10"
    : band === "moderate"
      ? "text-warn-400 border-warn-500/40 bg-warn-500/10"
      : band === "mild"
        ? "text-sky-400 border-sky-500/30 bg-sky-500/10"
        : "text-sig-500 border-sig-500/30 bg-sig-500/10";

export const sevColor = (s: string) =>
  s === "critical"
    ? "text-crit-400 bg-crit-500/10 border-crit-500/40"
    : s === "high"
      ? "text-warn-400 bg-warn-500/10 border-warn-500/40"
      : s === "medium"
        ? "text-sky-400 bg-sky-500/10 border-sky-500/30"
        : "text-slate-400 bg-slate-500/10 border-slate-600/40";

export const healthColor = (h: string) =>
  h === "nominal"
    ? "text-sig-500"
    : h === "degraded"
      ? "text-warn-400"
      : "text-crit-400";

export const AGENT_COLOR: Record<string, string> = {
  orchestrator: "text-sky-300",
  crop: "text-lime-300",
  crop_irrigation: "text-lime-300",
  agronomist: "text-teal-300",
  calving: "text-emerald-300",
  veterinarian: "text-emerald-400",
  maintenance: "text-amber-300",
  logistics: "text-violet-300",
  milking: "text-cyan-300",
  human: "text-fuchsia-300",
  system: "text-crit-400",
};

export const KIND_COLOR: Record<string, string> = {
  question: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  answer: "border-sig-500/40 bg-sig-500/10 text-sig-400",
  objection: "border-crit-500/40 bg-crit-500/10 text-crit-400",
  counter: "border-warn-500/40 bg-warn-500/10 text-warn-400",
  alert: "border-warn-500/30 bg-warn-500/5 text-warn-400",
  concession: "border-sig-500/30 bg-sig-500/5 text-sig-500",
};

export const AREA = {
  crop: "CROP PRODUCTION",
  livestock: "LIVESTOCK",
  milk: "MILK PRODUCTION",
} as const;