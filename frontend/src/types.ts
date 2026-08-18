export type RiskLevel = "healthy" | "warning" | "critical";

export interface TelemetryPoint {
  cycle: number;
  vibration: number; // mm/s
  temperature: number; // deg C
  current: number; // amps
}

export interface RulPoint {
  cycle: number;
  actualRul: number | null;
  predictedRul: number;
  confidenceLow: number;
  confidenceHigh: number;
}

export interface InspectionStep {
  label: string;
  done: boolean;
}

export interface Vehicle {
  id: string;
  name: string;
  fleetGroup: string;
  risk: RiskLevel;
  riskPercent: number; // 0-100, likelihood of failure in forecast window
  rulCycles: number;
  rulDays: number;
  healthScore: number; // 0-100
  likelyFailingPart: string;
  actionRecommendation: string; // e.g. "Service within 48 hours"
  serviceWindow: string; // e.g. "Within 48h"
  inspectionChecklist: InspectionStep[];
  lastUpdated: string;
  cyclesRun: number;
  telemetry: TelemetryPoint[];
  rulHistory: RulPoint[];
}

export type AlertSeverity = "critical" | "warning" | "info";
export type AlertStatus = "new" | "acknowledged" | "resolved";

export interface MaintenanceAlert {
  id: string;
  vehicleId: string;
  vehicleName: string;
  severity: AlertSeverity;
  part: string;
  message: string;
  recommendation: string;
  raisedAt: string;
  status: AlertStatus;
}

export interface FleetMetrics {
  totalVehicles: number;
  healthyCount: number;
  warningCount: number;
  criticalCount: number;
  avgRulAccuracy: number; // %
  avgLeadTimeGainedCycles: number;
  failuresPrevented: number;
}

export type StockStatus = "sufficient" | "low" | "shortage";

export interface SparePartForecast {
  part: string;
  predictedDemand: number; // units needed in forecast window
  currentStock: number;
  status: StockStatus;
  shortageCount: number; // predictedDemand - currentStock, if positive
  affectedVehicleIds: string[];
  forecastWindowDays: number;
}

export interface ModelMetrics {
  rulAccuracyPct: number;
  rmse: number;
  mae: number;
  f1FaultDetection: number;
  avgLeadTimeCycles: number;
  downtimeReductionPct: number;
  sparePartsForecastErrorPct: number;
}
