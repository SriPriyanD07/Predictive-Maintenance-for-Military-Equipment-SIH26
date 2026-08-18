// Combines 21st.dev structure (modal body layout) + OriginKit Tabs/Modal +
// the RUL chart into the per-unit drill-down view.
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import type { Vehicle } from "../../types";
import { Modal } from "../ui/Modal";
import { Tabs } from "../ui/Tabs";
import { RiskBadge } from "../ui/Badge";
import { RULTrendChart } from "./RULTrendChart";

function TelemetryChart({ dataKey, color, unit, data }: { dataKey: string; color: string; unit: string; data: Vehicle["telemetry"] }) {
  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid stroke="#1c2532" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="cycle" stroke="#4a5b72" tick={{ fill: "#8b98ab", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#243040" }} />
          <YAxis stroke="#4a5b72" tick={{ fill: "#8b98ab", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#243040" }} width={36} unit={unit} />
          <Tooltip
            contentStyle={{ background: "#131a24", border: "1px solid #243040", borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: "#eef2f7" }}
          />
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} isAnimationActive animationDuration={600} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function VehicleDetailModal({ vehicle, onClose }: { vehicle: Vehicle | null; onClose: () => void }) {
  return (
    <Modal open={!!vehicle} onClose={onClose} title={vehicle?.name ?? ""} subtitle={vehicle ? `${vehicle.id} · ${vehicle.fleetGroup}` : undefined}>
      {vehicle && (
        <div>
          <div className="mb-5 flex flex-wrap items-center gap-4">
            <RiskBadge risk={vehicle.risk} pulse />
            <div className="text-sm text-ink-300">
              RUL: <span className="font-medium text-ink-100">{vehicle.rulCycles} cycles</span> (~{vehicle.rulDays} days)
            </div>
            <div className="text-sm text-ink-300">
              Health Score: <span className="font-medium text-ink-100">{vehicle.healthScore}%</span>
            </div>
            <div className="text-sm text-ink-300">
              Likely Part: <span className="font-medium text-ink-100">{vehicle.likelyFailingPart}</span>
            </div>
          </div>

          <Tabs
            defaultKey="rul"
            tabs={[
              {
                key: "rul",
                label: "RUL Trend",
                content: <RULTrendChart data={vehicle.rulHistory} risk={vehicle.risk} />,
              },
              {
                key: "telemetry",
                label: "Telemetry",
                content: (
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div>
                      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-500">Vibration (mm/s)</div>
                      <TelemetryChart dataKey="vibration" color="#38bdf8" unit="" data={vehicle.telemetry} />
                    </div>
                    <div>
                      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-500">Temperature (°C)</div>
                      <TelemetryChart dataKey="temperature" color="#f5a524" unit="" data={vehicle.telemetry} />
                    </div>
                    <div>
                      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-500">Current (A)</div>
                      <TelemetryChart dataKey="current" color="#a78bfa" unit="" data={vehicle.telemetry} />
                    </div>
                  </div>
                ),
              },
              {
                key: "recommendation",
                label: "Recommendation",
                content: (
                  <div className="rounded-lg border border-base-800 bg-base-850 p-4 text-sm text-ink-300">
                    {vehicle.risk === "critical"
                      ? `Schedule emergency maintenance for the ${vehicle.likelyFailingPart} before next deployment. Predicted failure window: ${vehicle.rulCycles} cycles (~${vehicle.rulDays} days).`
                      : vehicle.risk === "warning"
                        ? `Add a ${vehicle.likelyFailingPart} inspection to the next scheduled service window. Degradation trend is measurable but not yet urgent.`
                        : "No action required. Unit is operating within nominal parameters."}
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}
    </Modal>
  );
}
