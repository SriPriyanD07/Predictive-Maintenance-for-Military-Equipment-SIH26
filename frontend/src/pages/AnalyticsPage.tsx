// Model performance view — does NOT duplicate dashboard/alerts content.
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MODEL_METRICS, FLEET } from "../data/mockFleet";

function MetricTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink-100">{value}</div>
      {sub && <div className="text-xs text-ink-500">{sub}</div>}
    </div>
  );
}

export function AnalyticsPage() {
  // Aggregate predicted-vs-actual RUL across a representative unit for the comparison chart.
  const sample = FLEET.find((v) => v.risk === "critical") ?? FLEET[0];
  const comparisonData = sample.rulHistory.filter((p) => p.actualRul !== null);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricTile label="RUL Prediction Accuracy" value={`${MODEL_METRICS.rulAccuracyPct}%`} />
        <MetricTile label="RMSE" value={MODEL_METRICS.rmse.toFixed(1)} sub="cycles" />
        <MetricTile label="MAE" value={MODEL_METRICS.mae.toFixed(1)} sub="cycles" />
        <MetricTile label="F1 — Fault Detection" value={MODEL_METRICS.f1FaultDetection.toFixed(2)} />
        <MetricTile label="Avg. Lead Time" value={`${MODEL_METRICS.avgLeadTimeCycles} cyc`} sub="advance notice before failure" />
        <MetricTile label="Downtime Reduction" value={`${MODEL_METRICS.downtimeReductionPct}%`} />
        <MetricTile label="Spare Parts Forecast Error" value={`${MODEL_METRICS.sparePartsForecastErrorPct}%`} />
      </div>

      <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-ink-100">Predicted vs. Actual RUL</h3>
          <p className="text-xs text-ink-500">Sample unit {sample.id} — model prediction against observed remaining life</p>
        </div>
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={comparisonData} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid stroke="#1c2532" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="cycle" stroke="#4a5b72" tick={{ fill: "#8b98ab", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#243040" }} />
              <YAxis stroke="#4a5b72" tick={{ fill: "#8b98ab", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#243040" }} width={40} />
              <Tooltip contentStyle={{ background: "#131a24", border: "1px solid #243040", borderRadius: 6, fontSize: 12 }} labelStyle={{ color: "#eef2f7" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="predictedRul" name="Predicted RUL" stroke="#38bdf8" strokeWidth={2.5} dot={false} isAnimationActive animationDuration={700} />
              <Line type="monotone" dataKey="actualRul" name="Actual RUL" stroke="#8b98ab" strokeWidth={1.5} strokeDasharray="4 3" dot={{ r: 2 }} isAnimationActive animationDuration={700} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
