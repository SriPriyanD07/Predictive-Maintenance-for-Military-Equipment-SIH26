// Single source of fleet data for the whole UI: one poll, one tick, so every
// page renders the same moment in the simulation.
//
// `live` is deliberately exposed. If the backend is unreachable the UI falls
// back to the mock fixtures, and a dashboard that silently swapped to random
// numbers would be worse than one that says so. LiveBadge surfaces this.

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type {
  FleetMetrics,
  MaintenanceAlert,
  ModelMetrics,
  Vehicle,
} from "../types";
import {
  FLEET as MOCK_FLEET,
  FLEET_METRICS as MOCK_FLEET_METRICS,
  MODEL_METRICS as MOCK_MODEL_METRICS,
  ALERTS as MOCK_ALERTS,
} from "../data/mockFleet";
import {
  buildAlerts,
  deriveFleetMetrics,
  fetchFleet,
  fetchMetrics,
  toModelMetrics,
} from "../data/api";

export interface FleetState {
  vehicles: Vehicle[];
  fleetMetrics: FleetMetrics;
  modelMetrics: ModelMetrics;
  alerts: MaintenanceAlert[];
  live: boolean;
  tick: number;
  running: boolean;
  error: string | null;
}

const FALLBACK: FleetState = {
  vehicles: MOCK_FLEET,
  fleetMetrics: MOCK_FLEET_METRICS,
  modelMetrics: MOCK_MODEL_METRICS,
  alerts: MOCK_ALERTS,
  live: false,
  tick: -1,
  running: false,
  error: null,
};

const Ctx = createContext<FleetState>(FALLBACK);

const POLL_MS = 2000;

export function FleetProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<FleetState>(FALLBACK);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [fleet, rawMetrics] = await Promise.all([fetchFleet(), fetchMetrics()]);
        if (cancelled) return;
        const modelMetrics = toModelMetrics(rawMetrics);
        setState({
          vehicles: fleet.vehicles,
          fleetMetrics: deriveFleetMetrics(fleet.vehicles, modelMetrics),
          modelMetrics,
          alerts: buildAlerts(fleet.vehicles),
          live: true,
          tick: fleet.tick,
          running: fleet.running,
          error: null,
        });
      } catch (e) {
        if (cancelled) return;
        setState({
          ...FALLBACK,
          error: e instanceof Error ? e.message : String(e),
        });
      }
    }

    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export function useFleet() {
  return useContext(Ctx);
}
