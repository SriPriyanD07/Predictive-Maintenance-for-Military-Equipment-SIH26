import { useNavigate } from "react-router-dom";
import { CriticalAlertsPanel } from "../components/dashboard/CriticalAlertsPanel";
import { useAlerts } from "../hooks/useAlerts";

export function AlertsPage() {
  const navigate = useNavigate();
  const { alerts, acknowledgeAlert } = useAlerts();
  return <CriticalAlertsPanel alerts={alerts} onAcknowledge={acknowledgeAlert} onOpenVehicle={(id) => navigate(`/vehicles/${id}`)} />;
}
