import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { AlertStatus, MaintenanceAlert } from "../types";
import { useFleet } from "./useFleet";

interface AlertsContextValue {
  alerts: MaintenanceAlert[];
  acknowledgeAlert: (id: string) => void;
  resolveAlert: (id: string) => void;
}

const AlertsContext = createContext<AlertsContextValue | null>(null);

// Alerts are DERIVED from live fleet state on every poll, so they cannot drift
// out of sync with the model. Acknowledge/resolve is the one piece of genuinely
// local state: it is a user action the backend has no endpoint for, so it is
// held as an id -> status override map and re-applied over each fresh poll.
// Without that, the 2s refresh would wipe every acknowledgement.
export function AlertsProvider({ children }: { children: ReactNode }) {
  const { alerts: liveAlerts } = useFleet();
  const [overrides, setOverrides] = useState<Record<string, AlertStatus>>({});

  const value = useMemo<AlertsContextValue>(() => {
    const alerts = liveAlerts.map((a) =>
      overrides[a.id] ? { ...a, status: overrides[a.id] } : a,
    );
    return {
      alerts,
      acknowledgeAlert: (id) =>
        setOverrides((prev) => ({ ...prev, [id]: "acknowledged" })),
      resolveAlert: (id) => setOverrides((prev) => ({ ...prev, [id]: "resolved" })),
    };
  }, [liveAlerts, overrides]);

  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}

export function useAlerts() {
  const ctx = useContext(AlertsContext);
  if (!ctx) throw new Error("useAlerts must be used within AlertsProvider");
  return ctx;
}
