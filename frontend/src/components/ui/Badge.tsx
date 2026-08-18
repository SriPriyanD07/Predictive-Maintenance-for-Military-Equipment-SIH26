// OriginKit layer: small, consistent status primitive reused across
// the table, alert list, and detail modal so risk states always read the same way.
import type { RiskLevel, AlertSeverity } from "../../types";

const RISK_STYLES: Record<RiskLevel, string> = {
  healthy: "bg-status-healthyBg text-status-healthy border-status-healthy/30",
  warning: "bg-status-warningBg text-status-warning border-status-warning/30",
  critical: "bg-status-criticalBg text-status-critical border-status-critical/30",
};

const RISK_LABEL: Record<RiskLevel, string> = {
  healthy: "Healthy",
  warning: "Watch",
  critical: "Critical",
};

export function RiskBadge({ risk, pulse = false }: { risk: RiskLevel; pulse?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${RISK_STYLES[risk]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          risk === "healthy" ? "bg-status-healthy" : risk === "warning" ? "bg-status-warning" : "bg-status-critical"
        } ${pulse && risk === "critical" ? "animate-pulse-ring" : ""}`}
      />
      {RISK_LABEL[risk]}
    </span>
  );
}

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  critical: "bg-status-criticalBg text-status-critical border-status-critical/30",
  warning: "bg-status-warningBg text-status-warning border-status-warning/30",
  info: "bg-status-info/10 text-status-info border-status-info/30",
};

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide ${SEVERITY_STYLES[severity]}`}>
      {severity}
    </span>
  );
}
