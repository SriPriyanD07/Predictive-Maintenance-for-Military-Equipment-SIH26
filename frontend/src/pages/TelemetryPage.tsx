// Surfaces the "physical degradation → sensor change → RUL drop" moment for demos.
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowDown, ArrowUp, Minus } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useFleet } from "../hooks/useFleet";
import { RiskBadge } from "../components/ui/Badge";

function pctChange(curr: number, prev: number) {
  if (prev === 0) return 0;
  return ((curr - prev) / prev) * 100;
}

function ChangeIndicator({ pct }: { pct: number }) {
  const rounded = pct.toFixed(1);
  if (Math.abs(pct) < 0.5) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-ink-500">
        <Minus size={11} /> {rounded}%
      </span>
    );
  }
  const isUp = pct > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${isUp ? "text-status-critical" : "text-status-healthy"}`}>
      {isUp ? <ArrowUp size={11} /> : <ArrowDown size={11} />} {isUp ? "+" : ""}
      {rounded}%
    </span>
  );
}

function SensorPanel({
  label,
  unit,
  dataKey,
  color,
  data,
}: {
  label: string;
  unit: string;
  dataKey: "vibration" | "temperature" | "current";
  color: string;
  data: { cycle: number; vibration: number; temperature: number; current: number }[];
}) {
  const latest = data[data.length - 1];
  const prev = data[data.length - 2] ?? latest;
  const change = pctChange(latest[dataKey], prev[dataKey]);

  return (
    <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</span>
        <ChangeIndicator pct={change} />
      </div>
      <div className="mb-2 text-2xl font-semibold text-ink-100">
        {latest[dataKey]}
        <span className="ml-1 text-sm font-normal text-ink-500">{unit}</span>
      </div>
      <div className="h-24 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -30 }}>
            <CartesianGrid stroke="#1c2532" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="cycle" hide />
            <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} />
            <Tooltip
              contentStyle={{ background: "#131a24", border: "1px solid #243040", borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: "#eef2f7" }}
            />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} isAnimationActive animationDuration={500} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function TelemetryPage() {
  const { vehicles: FLEET } = useFleet();
  const { id } = useParams();
  const navigate = useNavigate();
  const vehicle = FLEET.find((v) => v.id === id);

  if (!vehicle) {
    return (
      <div className="rounded-xl border border-dashed border-base-800 p-8 text-center text-sm text-ink-500">
        Vehicle {id} not found.{" "}
        <Link to="/telemetry" className="text-status-info hover:underline">
          Back to telemetry
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-xs text-ink-500 hover:text-ink-300">
        <ArrowLeft size={13} /> Back
      </button>

      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-ink-100">Live Telemetry — {vehicle.name}</h2>
        <RiskBadge risk={vehicle.risk} pulse />
        <span className="text-xs text-ink-500">{vehicle.id} · cycle {vehicle.telemetry[vehicle.telemetry.length - 1].cycle}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SensorPanel label="Vibration" unit="mm/s" dataKey="vibration" color="#38bdf8" data={vehicle.telemetry} />
        <SensorPanel label="Temperature" unit="°C" dataKey="temperature" color="#f5a524" data={vehicle.telemetry} />
        <SensorPanel label="Current Draw" unit="A" dataKey="current" color="#a78bfa" data={vehicle.telemetry} />
      </div>

      <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
        <div className="text-xs font-medium uppercase tracking-wide text-ink-500">Cycles Run</div>
        <div className="mt-1 text-xl font-semibold text-ink-100">{vehicle.cyclesRun} cycles</div>
      </div>
    </div>
  );
}
