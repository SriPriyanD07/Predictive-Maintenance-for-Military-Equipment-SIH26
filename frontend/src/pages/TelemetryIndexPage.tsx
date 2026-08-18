import { useNavigate } from "react-router-dom";
import { useFleet } from "../hooks/useFleet";
import { RiskBadge } from "../components/ui/Badge";

export function TelemetryIndexPage() {
  const { vehicles: FLEET } = useFleet();
  const navigate = useNavigate();
  return (
    <div className="rounded-xl border border-base-800 bg-base-900 shadow-panel">
      <div className="border-b border-base-800 px-4 py-3">
        <h3 className="text-sm font-semibold text-ink-100">Select a vehicle for live telemetry</h3>
      </div>
      <ul className="divide-y divide-base-850">
        {FLEET.map((v) => (
          <li key={v.id}>
            <button
              onClick={() => navigate(`/telemetry/${v.id}`)}
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-base-850"
            >
              <div>
                <div className="text-sm font-medium text-ink-100">{v.name}</div>
                <div className="text-xs text-ink-500">{v.id} · {v.fleetGroup}</div>
              </div>
              <RiskBadge risk={v.risk} pulse />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
