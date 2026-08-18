// OriginKit layer: single-purpose banner that states the one thing an
// officer needs to do next. Deliberately loud for critical, quiet for healthy.
import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import type { RiskLevel } from "../../types";

const STYLES: Record<RiskLevel, string> = {
  critical: "border-status-critical/40 bg-status-criticalBg text-status-critical",
  warning: "border-status-warning/40 bg-status-warningBg text-status-warning",
  healthy: "border-status-healthy/40 bg-status-healthyBg text-status-healthy",
};

const ICON: Record<RiskLevel, typeof AlertTriangle> = {
  critical: AlertTriangle,
  warning: Clock,
  healthy: CheckCircle2,
};

export function ActionBanner({ risk, text }: { risk: RiskLevel; text: string }) {
  const Icon = ICON[risk];
  return (
    <div className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${STYLES[risk]}`}>
      <Icon size={20} className="shrink-0" />
      <div>
        <div className="text-xs font-medium uppercase tracking-wide opacity-80">Recommended action</div>
        <div className="text-sm font-semibold">{text}</div>
      </div>
    </div>
  );
}
