// 21st.dev layer: KPI card row (dashboard overview / stats cards).
// React Bits layer: AnimatedCounter gives each number a purposeful pop
// when it updates, instead of a static text swap.
import { AlertTriangle, CheckCircle2, Gauge, TrendingUp } from "lucide-react";
import type { FleetMetrics } from "../../types";
import { AnimatedCounter } from "../ui/AnimatedCounter";

function StatTile({
  icon: Icon,
  label,
  value,
  accent,
  suffix,
  decimals,
}: {
  icon: typeof Gauge;
  label: string;
  value: number;
  accent: string;
  suffix?: string;
  decimals?: number;
}) {
  return (
    <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</span>
        <Icon size={16} className={accent} />
      </div>
      <div className={`mt-2 text-2xl font-semibold ${accent}`}>
        <AnimatedCounter value={value} suffix={suffix} decimals={decimals} />
      </div>
    </div>
  );
}

export function FleetHealthSummary({ metrics }: { metrics: FleetMetrics }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
      <StatTile icon={Gauge} label="Total Fleet" value={metrics.totalVehicles} accent="text-ink-100" />
      <StatTile icon={CheckCircle2} label="Healthy" value={metrics.healthyCount} accent="text-status-healthy" />
      <StatTile icon={AlertTriangle} label="Watch" value={metrics.warningCount} accent="text-status-warning" />
      <StatTile icon={AlertTriangle} label="Critical" value={metrics.criticalCount} accent="text-status-critical" />
      <StatTile
        icon={TrendingUp}
        label="RUL Accuracy"
        value={metrics.avgRulAccuracy}
        accent="text-status-info"
        suffix="%"
        decimals={1}
      />
      <StatTile
        icon={TrendingUp}
        label="Lead Time Gained"
        value={metrics.avgLeadTimeGainedCycles}
        accent="text-status-info"
        suffix=" cyc"
      />
    </div>
  );
}
