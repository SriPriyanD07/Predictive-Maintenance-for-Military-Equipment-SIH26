// 21st.dev layer: primary chart/data-visualization panel.
// React Bits layer: line/area transitions animate smoothly when the
// underlying vehicle selection changes (recharts' built-in animation,
// tuned to feel deliberate rather than bouncy).
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RiskLevel, RulPoint } from "../../types";

const RISK_COLOR: Record<RiskLevel, string> = {
  healthy: "#22c55e",
  warning: "#f5a524",
  critical: "#ef4444",
};

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const point: RulPoint = payload[0].payload;
  return (
    <div className="rounded-md border border-base-700 bg-base-850 px-3 py-2 text-xs shadow-panel">
      <div className="mb-1 font-medium text-ink-100">Cycle {label}</div>
      <div className="text-ink-300">Predicted RUL: {point.predictedRul} cycles</div>
      {point.actualRul !== null && <div className="text-ink-500">Actual: {point.actualRul} cycles</div>}
      <div className="text-ink-500">
        Band: {point.confidenceLow}–{point.confidenceHigh}
      </div>
    </div>
  );
}

export function RULTrendChart({ data, risk }: { data: RulPoint[]; risk: RiskLevel }) {
  const color = RISK_COLOR[risk];
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
          <defs>
            <linearGradient id="rulBand" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.18} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1c2532" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="cycle"
            stroke="#4a5b72"
            tick={{ fill: "#8b98ab", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#243040" }}
          />
          <YAxis
            stroke="#4a5b72"
            tick={{ fill: "#8b98ab", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#243040" }}
            width={40}
          />
          <Tooltip content={<ChartTooltip />} />
          <Area
            type="monotone"
            dataKey="confidenceHigh"
            stroke="none"
            fill="url(#rulBand)"
            isAnimationActive
            animationDuration={600}
          />
          <Line
            type="monotone"
            dataKey="predictedRul"
            stroke={color}
            strokeWidth={2.5}
            dot={false}
            isAnimationActive
            animationDuration={700}
            animationEasing="ease-out"
          />
          <Line
            type="monotone"
            dataKey="actualRul"
            stroke="#8b98ab"
            strokeWidth={1.5}
            strokeDasharray="4 3"
            dot={{ r: 2, fill: "#8b98ab", strokeWidth: 0 }}
            connectNulls
            isAnimationActive
            animationDuration={700}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
