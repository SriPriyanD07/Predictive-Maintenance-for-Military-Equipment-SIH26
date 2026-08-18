// Investigation view: the officer drills down here to understand one unit.
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Activity } from "lucide-react";
import { FLEET } from "../data/mockFleet";
import { RiskBadge } from "../components/ui/Badge";
import { ActionBanner } from "../components/ui/ActionBanner";
import { Checklist } from "../components/ui/Checklist";
import { Tabs } from "../components/ui/Tabs";
import { Button } from "../components/ui/Button";
import { RULTrendChart } from "../components/dashboard/RULTrendChart";

export function VehicleDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const vehicle = FLEET.find((v) => v.id === id);

  if (!vehicle) {
    return (
      <div className="rounded-xl border border-dashed border-base-800 p-8 text-center text-sm text-ink-500">
        Vehicle {id} not found.{" "}
        <Link to="/vehicles" className="text-status-info hover:underline">
          Back to vehicles
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-xs text-ink-500 hover:text-ink-300"
      >
        <ArrowLeft size={13} /> Back
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold text-ink-100">{vehicle.name}</h2>
            <RiskBadge risk={vehicle.risk} pulse />
          </div>
          <p className="mt-1 text-sm text-ink-500">
            {vehicle.id} · {vehicle.fleetGroup} · {vehicle.cyclesRun} cycles run
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => navigate(`/telemetry/${vehicle.id}`)}>
          <Activity size={14} /> View live telemetry
        </Button>
      </div>

      <ActionBanner risk={vehicle.risk} text={vehicle.actionRecommendation} />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard label="Failure Risk" value={`${vehicle.riskPercent}%`} accent={riskAccent(vehicle.risk)} />
        <MetricCard label="RUL Remaining" value={`${vehicle.rulCycles} cyc`} sub={`~${vehicle.rulDays} days`} />
        <MetricCard label="Health Score" value={`${vehicle.healthScore}%`} />
        <MetricCard label="Likely Failing Part" value={vehicle.likelyFailingPart} small />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel lg:col-span-2">
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
                label: "Telemetry Snapshot",
                content: (() => {
                  const latest = vehicle.telemetry[vehicle.telemetry.length - 1];
                  return (
                    <div className="grid grid-cols-3 gap-3 text-sm">
                      <SnapshotStat label="Vibration" value={`${latest.vibration} mm/s`} />
                      <SnapshotStat label="Temperature" value={`${latest.temperature} °C`} />
                      <SnapshotStat label="Current" value={`${latest.current} A`} />
                    </div>
                  );
                })(),
              },
            ]}
          />
        </div>

        <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
          <h3 className="mb-3 text-sm font-semibold text-ink-100">Inspection Checklist</h3>
          <Checklist steps={vehicle.inspectionChecklist} />
        </div>
      </div>
    </div>
  );
}

function riskAccent(risk: "healthy" | "warning" | "critical") {
  return risk === "critical" ? "text-status-critical" : risk === "warning" ? "text-status-warning" : "text-status-healthy";
}

function MetricCard({ label, value, sub, accent, small }: { label: string; value: string; sub?: string; accent?: string; small?: boolean }) {
  return (
    <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className={`mt-1 font-semibold ${accent ?? "text-ink-100"} ${small ? "text-base" : "text-xl"}`}>{value}</div>
      {sub && <div className="text-xs text-ink-500">{sub}</div>}
    </div>
  );
}

function SnapshotStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-base-800 bg-base-850 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div className="text-base font-semibold text-ink-100">{value}</div>
    </div>
  );
}
