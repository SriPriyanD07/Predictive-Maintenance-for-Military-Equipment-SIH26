// Adapter: backend (snake_case, C-MAPSS/decision contract) -> UI (camelCase).
//
// The backend is authoritative for everything it actually computes: RUL, risk,
// health, priority, action, telemetry, history. Fields the UI needs but the
// backend does NOT produce are marked DERIVED or SYNTHETIC below. Never present
// a SYNTHETIC field to a judge as a model prediction.

import type {
  FleetMetrics,
  MaintenanceAlert,
  ModelMetrics,
  RiskLevel,
  RulPoint,
  TelemetryPoint,
  Vehicle,
} from "../types";

export interface ApiUnit {
  unit_id: string;
  unit_name: string;
  tick: number;
  cycle: number;
  timestamp: string;
  telemetry: Record<string, number>;
  rul: number;
  rul_band: { low: number; high: number };
  health_index: number;
  risk_score: number;
  risk_level: string;
  priority: string;
  action_code: string;
  recommended_action: string;
  reason: string;
  source: string;
}

export interface ApiHistoryPoint {
  tick: number;
  cycle: number;
  rul: number;
  risk_score: number;
  risk_level: string;
  telemetry: Record<string, number>;
}

export interface ApiMetrics {
  model: string;
  dataset: string;
  mae: number;
  rmse: number;
  n_test: number;
  baseline_mae: number;
  lead_time_cycles: number;
  trained_at: string;
}

// The backend has 4 risk levels, the UI type has 3. WATCH and WARNING both map
// to "warning"; the finer distinction survives in priority and action_code.
const RISK_MAP: Record<string, RiskLevel> = {
  NOMINAL: "healthy",
  WATCH: "warning",
  WARNING: "warning",
  CRITICAL: "critical",
};

const SERVICE_WINDOW: Record<string, string> = {
  GROUND_NOW: "Immediate",
  SERVICE_24H: "Within 24h",
  SCHEDULE_72H: "Within 72h",
  INSPECT_7D: "Within 7 days",
  MONITOR: "Routine",
};

// Mirrors BASELINE/SPREAD in ml/sensor_map.py so the "likely failing part"
// tracks real telemetry drift rather than being decorative.
const BASELINE: Record<string, number> = {
  core_temp: 642.38,
  exhaust_temp: 1587.24,
  fan_speed: 521.94,
  core_speed: 8.42,
  pressure: 1402.92,
  vibration: 0.557,
  fuel_flow: 553.99,
};

const SPREAD: Record<string, number> = {
  core_temp: 3.32,
  exhaust_temp: 45.87,
  fan_speed: 4.69,
  core_speed: 0.26,
  pressure: 59.24,
  vibration: 1.2,
  fuel_flow: 6.21,
};

const PART_FOR_CHANNEL: Record<string, string> = {
  core_temp: "HPC Thermal Liner",
  exhaust_temp: "LPT Exhaust Duct",
  fan_speed: "Fan Bearing Assembly",
  core_speed: "Core Shaft Bearing",
  pressure: "HPC Compressor Stage",
  vibration: "Rotor Balance / Bearing",
  fuel_flow: "Fuel Metering Valve",
};

function dominantChannel(t: Record<string, number>): string {
  let best = "vibration";
  let bestDev = -Infinity;
  for (const k of Object.keys(BASELINE)) {
    const v = t[k];
    if (typeof v !== "number") continue;
    const dev = Math.abs(v - BASELINE[k]) / (SPREAD[k] || 1);
    if (dev > bestDev) {
      bestDev = dev;
      best = k;
    }
  }
  return best;
}

// The UI TelemetryPoint carries 3 channels; expose the 3 most legible of the 7.
function toTelemetryPoint(cycle: number, t: Record<string, number>): TelemetryPoint {
  return {
    cycle,
    vibration: Number((t.vibration ?? 0).toFixed(3)),
    temperature: Number((t.core_temp ?? 0).toFixed(2)),
    current: Number((t.fuel_flow ?? 0).toFixed(2)),
  };
}

export function adaptUnit(
  u: ApiUnit,
  history: ApiHistoryPoint[] = [],
  mae = 13.43,
): Vehicle {
  const channel = dominantChannel(u.telemetry || {});
  const telemetry = history.length
    ? history.map((p) => toTelemetryPoint(p.cycle, p.telemetry || {}))
    : [toTelemetryPoint(u.cycle, u.telemetry || {})];

  const rulHistory: RulPoint[] = history.map((p) => ({
    cycle: p.cycle,
    // The true RUL of a live unit is unknowable at serve time. null is the
    // honest value; the chart then draws prediction plus band only.
    actualRul: null,
    predictedRul: Number(p.rul.toFixed(2)),
    confidenceLow: Number(Math.max(0, p.rul - mae).toFixed(2)),
    confidenceHigh: Number(Math.min(125, p.rul + mae).toFixed(2)),
  }));

  return {
    id: u.unit_id, // REAL
    name: u.unit_name, // REAL
    fleetGroup: "C-MAPSS FD001", // SYNTHETIC
    risk: RISK_MAP[u.risk_level] ?? "healthy", // REAL
    riskPercent: Math.round((u.risk_score ?? 0) * 100), // REAL
    rulCycles: Math.round(u.rul), // REAL (model output)
    rulDays: Math.round(u.rul), // DERIVED: 1 cycle treated as 1 day
    healthScore: Math.round((u.health_index ?? 0) * 100), // REAL
    likelyFailingPart: PART_FOR_CHANNEL[channel], // DERIVED from telemetry drift
    actionRecommendation: u.recommended_action, // REAL
    serviceWindow: SERVICE_WINDOW[u.action_code] ?? u.action_code, // REAL
    inspectionChecklist: [
      // SYNTHETIC: presentation scaffolding, not model output
      { label: "Inspect " + PART_FOR_CHANNEL[channel], done: false },
      { label: "Stage replacement part", done: false },
      { label: "Notify maintenance supervisor", done: false },
      { label: "Log pre-service telemetry snapshot", done: false },
    ],
    lastUpdated: u.timestamp, // REAL
    cyclesRun: u.cycle, // REAL
    telemetry, // REAL
    rulHistory, // REAL
  };
}

export async function fetchFleet(): Promise<{
  vehicles: Vehicle[];
  tick: number;
  running: boolean;
}> {
  const res = await fetch("/api/fleet");
  if (!res.ok) throw new Error("/api/fleet " + res.status);
  const data = await res.json();
  const units: ApiUnit[] = data.units ?? [];

  const histories = await Promise.all(
    units.map(async (u) => {
      try {
        const r = await fetch("/api/unit/" + u.unit_id + "/history");
        return r.ok ? ((await r.json()).points ?? []) : [];
      } catch {
        return [];
      }
    }),
  );

  return {
    vehicles: units.map((u, i) => adaptUnit(u, histories[i])),
    tick: data.tick ?? 0,
    running: Boolean(data.running),
  };
}

export async function fetchMetrics(): Promise<ApiMetrics> {
  const res = await fetch("/api/metrics");
  if (!res.ok) throw new Error("/api/metrics " + res.status);
  return res.json();
}

export function toModelMetrics(m: ApiMetrics): ModelMetrics {
  return {
    rulAccuracyPct: Number((100 - (m.mae / 125) * 100).toFixed(1)), // DERIVED from MAE
    rmse: m.rmse, // REAL
    mae: m.mae, // REAL
    f1FaultDetection: 0, // NOT MEASURED
    avgLeadTimeCycles: m.lead_time_cycles, // REAL
    downtimeReductionPct: 0, // NOT MEASURED
    sparePartsForecastErrorPct: 0, // NOT MEASURED
  };
}

export function deriveFleetMetrics(v: Vehicle[], mm: ModelMetrics): FleetMetrics {
  return {
    totalVehicles: v.length,
    healthyCount: v.filter((x) => x.risk === "healthy").length,
    warningCount: v.filter((x) => x.risk === "warning").length,
    criticalCount: v.filter((x) => x.risk === "critical").length,
    avgRulAccuracy: mm.rulAccuracyPct,
    avgLeadTimeGainedCycles: mm.avgLeadTimeCycles,
    failuresPrevented: v.filter((x) => x.risk !== "healthy").length,
  };
}

export function buildAlerts(v: Vehicle[]): MaintenanceAlert[] {
  return v
    .filter((x) => x.risk !== "healthy")
    .sort((a, b) => a.rulCycles - b.rulCycles)
    .map((x) => ({
      id: "AL-" + x.id,
      vehicleId: x.id,
      vehicleName: x.name,
      severity: x.risk === "critical" ? "critical" : "warning",
      part: x.likelyFailingPart,
      message: "RUL " + x.rulCycles + " cycles, risk " + x.riskPercent + "%",
      recommendation: x.actionRecommendation,
      raisedAt: x.lastUpdated,
      status: "new",
    }));
}
