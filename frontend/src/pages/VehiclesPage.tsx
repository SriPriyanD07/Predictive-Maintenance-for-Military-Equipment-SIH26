import { useNavigate } from "react-router-dom";
import { VehicleTable } from "../components/dashboard/VehicleTable";
import { FLEET } from "../data/mockFleet";

export function VehiclesPage() {
  const navigate = useNavigate();
  return <VehicleTable vehicles={FLEET} onSelect={(v) => navigate(`/vehicles/${v.id}`)} />;
}
