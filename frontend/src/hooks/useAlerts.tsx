import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { ALERTS } from "../data/mockFleet";
import type { MaintenanceAlert } from "../types";

interface AlertsContextValue {
  alerts: MaintenanceAlert[];
  acknowledgeAlert: (id: string) => void;
  resolveAlert: (id: string) => void;
}

const AlertsContext = createContext<AlertsContextValue | null>(null);

export function AlertsProvider({ children }: { children: ReactNode }) {
  const [alerts, setAlerts] = useState<MaintenanceAlert[]>(ALERTS);

  const value = useMemo<AlertsContextValue>(
    () => ({
      alerts,
      acknowledgeAlert: (id) => setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, status: "acknowledged" } : a))),
      resolveAlert: (id) => setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, status: "resolved" } : a))),
    }),
    [alerts],
  );

  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}

export function useAlerts() {
  const ctx = useContext(AlertsContext);
  if (!ctx) throw new Error("useAlerts must be used within AlertsProvider");
  return ctx;
}
