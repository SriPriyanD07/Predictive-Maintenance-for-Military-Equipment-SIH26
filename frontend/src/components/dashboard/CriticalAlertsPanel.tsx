// 21st.dev layer: alert/notification list panel.
// React Bits layer: a restrained pulse ring on the critical dot — draws the
// eye without turning the panel into a strobe. Only critical items pulse.
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import type { MaintenanceAlert } from "../../types";
import { SeverityBadge } from "../ui/Badge";
import { Button } from "../ui/Button";

export function CriticalAlertsPanel({
  alerts,
  onAcknowledge,
  onOpenVehicle,
}: {
  alerts: MaintenanceAlert[];
  onAcknowledge: (id: string) => void;
  onOpenVehicle: (vehicleId: string) => void;
}) {
  const sorted = [...alerts].sort((a, b) => (a.severity === "critical" ? -1 : b.severity === "critical" ? 1 : 0));

  return (
    <div className="rounded-xl border border-base-800 bg-base-900 shadow-panel">
      <div className="flex items-center justify-between border-b border-base-800 px-4 py-3">
        <h3 className="text-sm font-semibold text-ink-100">Critical Vehicles — Action Required</h3>
        <span className="text-xs text-ink-500">{sorted.length} active</span>
      </div>
      <ul className="max-h-80 divide-y divide-base-850 overflow-y-auto">
        {sorted.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-ink-500">No active alerts. Fleet nominal.</li>
        )}
        {sorted.map((alert) => (
          <li key={alert.id} className="flex items-start gap-3 px-4 py-3">
            <span className="relative mt-1.5 flex h-2 w-2 shrink-0">
              {alert.severity === "critical" && (
                <motion.span
                  className="absolute inline-flex h-full w-full rounded-full bg-status-critical"
                  animate={{ opacity: [0.6, 0, 0.6], scale: [1, 2.4, 1] }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
                />
              )}
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${
                  alert.severity === "critical" ? "bg-status-critical" : "bg-status-warning"
                }`}
              />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onOpenVehicle(alert.vehicleId)}
                  className="truncate text-sm font-medium text-ink-100 hover:text-status-info"
                >
                  {alert.vehicleName}
                </button>
                <SeverityBadge severity={alert.severity} />
              </div>
              <p className="mt-0.5 text-xs text-ink-500">{alert.message}</p>
              <p className="mt-1 text-xs text-ink-300">→ {alert.recommendation}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1.5">
              {alert.status === "new" ? (
                <Button size="sm" variant="subtle" onClick={() => onAcknowledge(alert.id)}>
                  Acknowledge
                </Button>
              ) : (
                <span className="text-[11px] text-ink-500">Acknowledged</span>
              )}
              <button
                onClick={() => onOpenVehicle(alert.vehicleId)}
                className="flex items-center gap-1 text-[11px] text-ink-500 hover:text-status-info"
              >
                Details <ArrowRight size={11} />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
