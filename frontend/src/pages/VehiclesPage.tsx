import { useNavigate } from "react-router-dom";
import { VehicleTable } from "../components/dashboard/VehicleTable";
import { useFleet } from "../hooks/useFleet";

export function VehiclesPage() {
  const { vehicles: FLEET } = useFleet();
  const navigate = useNavigate();
  return <VehicleTable vehicles={FLEET} onSelect={(v) => navigate(`/vehicles/${v.id}`)} />;
}
