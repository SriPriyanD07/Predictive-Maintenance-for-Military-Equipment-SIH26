import type {
  AlertSeverity,
  FleetMetrics,
  InspectionStep,
  MaintenanceAlert,
  ModelMetrics,
  RiskLevel,
  RulPoint,
  SparePartForecast,
  StockStatus,
  TelemetryPoint,
  Vehicle,
} from "../types";

// Deterministic pseudo-random so the demo looks the same every run.
function seededRandom(seed: number) {
  let value = seed;
  return () => {
    value = (value * 9301 + 49297) % 233280;
    return value / 233280;
  };
}

function buildRulHistory(rand: () => number, startCycle: number, finalRul: number): RulPoint[] {
  const points: RulPoint[] = [];
  const totalPoints = 24;
  for (let i = 0; i < totalPoints; i++) {
    const cycle = startCycle + i * 8;
    const progress = i / (totalPoints - 1);
    const decay = 260 * (1 - progress) + finalRul * progress;
    const noise = (rand() - 0.5) * 10;
    const predicted = Math.max(finalRul * 0.6, decay + noise);
    const band = 8 + progress * 18;
    points.push({
      cycle,
      actualRul: i < totalPoints - 4 ? Math.max(0, Math.round(predicted + (rand() - 0.5) * 6)) : null,
      predictedRul: Math.round(predicted),
      confidenceLow: Math.max(0, Math.round(predicted - band)),
      confidenceHigh: Math.round(predicted + band),
    });
  }
  return points;
}

function buildTelemetry(rand: () => number, risk: RiskLevel): TelemetryPoint[] {
  const points: TelemetryPoint[] = [];
  const baseVibration = risk === "critical" ? 6.2 : risk === "warning" ? 3.8 : 2.1;
  const baseTemp = risk === "critical" ? 92 : risk === "warning" ? 78 : 65;
  const baseCurrent = risk === "critical" ? 18.5 : risk === "warning" ? 14.2 : 11.0;
  for (let i = 0; i < 20; i++) {
    const drift = risk === "critical" ? i * 0.18 : risk === "warning" ? i * 0.06 : i * 0.01;
    points.push({
      cycle: i * 10,
      vibration: +(baseVibration + drift + (rand() - 0.5) * 0.4).toFixed(2),
      temperature: +(baseTemp + drift * 2 + (rand() - 0.5) * 2).toFixed(1),
      current: +(baseCurrent + drift * 0.5 + (rand() - 0.5) * 0.6).toFixed(2),
    });
  }
  return points;
}

const PART_POOL = [
  "Turbine Bearing",
  "Fuel Injector",
  "Compressor Blade",
  "Hydraulic Pump",
  "Cooling Fan Motor",
  "Exhaust Valve",
  "Drive Shaft Coupling",
];

const NAME_POOL = [
  "Freight Unit",
  "Transit Coach",
  "Haul Truck",
  "Gen-Set",
  "Pump Skid",
  "Compressor Rig",
];

function riskFromRul(rulCycles: number): RiskLevel {
  if (rulCycles <= 40) return "critical";
  if (rulCycles <= 100) return "warning";
  return "healthy";
}

function actionRecommendationFor(risk: RiskLevel, rulDays: number, part: string): string {
  if (risk === "critical") return `Service within 48 hours — ${part} replacement required`;
  if (risk === "warning") return `Schedule ${part.toLowerCase()} inspection within ${rulDays} days`;
  return "No action required — continue routine monitoring";
}

function serviceWindowFor(risk: RiskLevel, rulDays: number): string {
  if (risk === "critical") return "Within 48h";
  if (risk === "warning") return `Within ${rulDays}d`;
  return "Routine";
}

function inspectionChecklistFor(risk: RiskLevel, part: string): InspectionStep[] {
  const base: InspectionStep[] = [
    { label: `Inspect ${part.toLowerCase()}`, done: risk === "healthy" },
    { label: `Prepare replacement ${part.toLowerCase()}`, done: false },
    { label: "Verify sensor calibration", done: risk !== "critical" },
    { label: "Log pre-service telemetry snapshot", done: false },
  ];
  if (risk === "critical") {
    base.push({ label: "Notify depot supervisor", done: false });
    base.push({ label: "Reserve replacement unit from stock", done: false });
  }
  return base;
}

function buildVehicle(index: number): Vehicle {
  const rand = seededRandom(index * 97 + 13);
  const rulCycles = Math.round(20 + rand() * 220);
  const risk = riskFromRul(rulCycles);
  const rulDays = Math.round(rulCycles / 3.2);
  const healthScore =
    risk === "critical" ? Math.round(10 + rand() * 20) : risk === "warning" ? Math.round(35 + rand() * 25) : Math.round(70 + rand() * 30);
  const id = `FLT-${String(index + 1).padStart(3, "0")}`;
  const cyclesRun = Math.round(150 + rand() * 400);
  const part = PART_POOL[index % PART_POOL.length];
  const riskPercent =
    risk === "critical" ? Math.round(75 + rand() * 24) : risk === "warning" ? Math.round(35 + rand() * 35) : Math.round(2 + rand() * 20);

  return {
    id,
    name: `${NAME_POOL[index % NAME_POOL.length]} ${index + 1}`,
    fleetGroup: index % 3 === 0 ? "North Depot" : index % 3 === 1 ? "South Depot" : "Central Depot",
    risk,
    riskPercent,
    rulCycles,
    rulDays,
    healthScore,
    likelyFailingPart: part,
    actionRecommendation: actionRecommendationFor(risk, rulDays, part),
    serviceWindow: serviceWindowFor(risk, rulDays),
    inspectionChecklist: inspectionChecklistFor(risk, part),
    lastUpdated: new Date(Date.now() - Math.round(rand() * 1000 * 60 * 40)).toISOString(),
    cyclesRun,
    telemetry: buildTelemetry(rand, risk),
    rulHistory: buildRulHistory(rand, Math.max(0, cyclesRun - 190), rulCycles),
  };
}

export const FLEET: Vehicle[] = Array.from({ length: 18 }, (_, i) => buildVehicle(i));

function severityFor(risk: RiskLevel): AlertSeverity {
  if (risk === "critical") return "critical";
  if (risk === "warning") return "warning";
  return "info";
}

export const ALERTS: MaintenanceAlert[] = FLEET.filter((v) => v.risk !== "healthy")
  .map((v, i) => ({
    id: `ALT-${String(i + 1).padStart(3, "0")}`,
    vehicleId: v.id,
    vehicleName: v.name,
    severity: severityFor(v.risk),
    part: v.likelyFailingPart,
    message:
      v.risk === "critical"
        ? `Predicted failure within ${v.rulCycles} cycles (~${v.rulDays} days). Immediate inspection required.`
        : `Degradation trend detected in ${v.likelyFailingPart.toLowerCase()}. Monitor closely.`,
    recommendation:
      v.risk === "critical"
        ? `Schedule emergency maintenance for ${v.likelyFailingPart} before next deployment.`
        : `Add ${v.likelyFailingPart} inspection to next scheduled service window.`,
    raisedAt: v.lastUpdated,
    status: i % 4 === 0 ? "acknowledged" : "new",
  }));

export const FLEET_METRICS: FleetMetrics = {
  totalVehicles: FLEET.length,
  healthyCount: FLEET.filter((v) => v.risk === "healthy").length,
  warningCount: FLEET.filter((v) => v.risk === "warning").length,
  criticalCount: FLEET.filter((v) => v.risk === "critical").length,
  avgRulAccuracy: 91.4,
  avgLeadTimeGainedCycles: 34,
  failuresPrevented: 7,
};

function stockStatusFor(predictedDemand: number, currentStock: number): StockStatus {
  if (currentStock >= predictedDemand) return "sufficient";
  if (currentStock >= predictedDemand * 0.5) return "low";
  return "shortage";
}

export const SPARE_PARTS_FORECAST: SparePartForecast[] = PART_POOL.map((part, i) => {
  const rand = seededRandom(i * 53 + 7);
  const affected = FLEET.filter((v) => v.likelyFailingPart === part && v.risk !== "healthy");
  const predictedDemand = Math.max(affected.length, Math.round(1 + rand() * 5));
  const currentStock = Math.round(rand() * predictedDemand * 1.6);
  const status = stockStatusFor(predictedDemand, currentStock);
  return {
    part,
    predictedDemand,
    currentStock,
    status,
    shortageCount: Math.max(0, predictedDemand - currentStock),
    affectedVehicleIds: affected.map((v) => v.id),
    forecastWindowDays: 30,
  };
}).sort((a, b) => b.shortageCount - a.shortageCount);

export const MODEL_METRICS: ModelMetrics = {
  rulAccuracyPct: 91.4,
  rmse: 12.8,
  mae: 9.3,
  f1FaultDetection: 0.88,
  avgLeadTimeCycles: 34,
  downtimeReductionPct: 27,
  sparePartsForecastErrorPct: 8.6,
};
