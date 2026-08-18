import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FleetHealthSummary } from "../components/dashboard/FleetHealthSummary";
import { RULTrendChart } from "../components/dashboard/RULTrendChart";
import { CriticalAlertsPanel } from "../components/dashboard/CriticalAlertsPanel";
import { VehicleTable } from "../components/dashboard/VehicleTable";
import { RiskBadge } from "../components/ui/Badge";
import { useFleet } from "../hooks/useFleet";
import { useAlerts } from "../hooks/useAlerts";

export function DashboardPage() {
  const { vehicles: FLEET, fleetMetrics: FLEET_METRICS } = useFleet();
  const navigate = useNavigate();
  const { alerts, acknowledgeAlert } = useAlerts();
  const criticalVehicles = useMemo(() => FLEET.filter((v) => v.risk === "critical"), [FLEET]);
  const [featuredId, setFeaturedId] = useState<string>("");
  const featuredVehicle =
    FLEET.find((v) => v.id === featuredId) ?? criticalVehicles[0] ?? FLEET[0];

  return (
    <div className="space-y-6">
      <FleetHealthSummary metrics={FLEET_METRICS} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ink-100">RUL Trend — {featuredVehicle.name}</h3>
              <p className="text-xs text-ink-500">{featuredVehicle.id} · predicted vs. actual, with confidence band</p>
            </div>
            <RiskBadge risk={featuredVehicle.risk} pulse />
          </div>
          <RULTrendChart data={featuredVehicle.rulHistory} risk={featuredVehicle.risk} />
        </div>

        <CriticalAlertsPanel
          alerts={alerts}
          onAcknowledge={acknowledgeAlert}
          onOpenVehicle={(id) => {
            setFeaturedId(id);
            navigate(`/vehicles/${id}`);
          }}
        />
      </div>

      <VehicleTable vehicles={FLEET} onSelect={(v) => navigate(`/vehicles/${v.id}`)} />
    </div>
  );
}
