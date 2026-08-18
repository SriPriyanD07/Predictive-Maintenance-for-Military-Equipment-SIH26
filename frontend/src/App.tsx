import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { VehiclesPage } from "./pages/VehiclesPage";
import { VehicleDetailsPage } from "./pages/VehicleDetailsPage";
import { TelemetryIndexPage } from "./pages/TelemetryIndexPage";
import { TelemetryPage } from "./pages/TelemetryPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { MaintenanceSchedulePage } from "./pages/MaintenanceSchedulePage";
import { SparePartsPage } from "./pages/SparePartsPage";
import { AlertsProvider } from "./hooks/useAlerts";
import { FLEET_METRICS } from "./data/mockFleet";

function titleFor(pathname: string): { title: string; subtitle: string } {
  if (pathname === "/") return { title: "Fleet Dashboard", subtitle: "Live predictive maintenance overview" };
  if (pathname.startsWith("/vehicles/")) return { title: "Vehicle Details", subtitle: "Unit investigation view" };
  if (pathname === "/vehicles") return { title: "Vehicles", subtitle: "Full fleet roster" };
  if (pathname.startsWith("/telemetry/")) return { title: "Live Telemetry", subtitle: "Real-time sensor readings" };
  if (pathname === "/telemetry") return { title: "Telemetry", subtitle: "Select a unit to view live sensors" };
  if (pathname === "/analytics") return { title: "Analytics", subtitle: "Model performance & prediction accuracy" };
  if (pathname === "/alerts") return { title: "Alerts", subtitle: "All maintenance alerts" };
  if (pathname === "/maintenance") return { title: "Maintenance Schedule", subtitle: "Ranked by urgency — who to service first" };
  if (pathname === "/spare-parts") return { title: "Spare Parts Forecast", subtitle: "Predicted demand vs. current stock" };
  return { title: "PrediX RUL", subtitle: "" };
}

function Shell() {
  const location = useLocation();
  const { title, subtitle } = titleFor(location.pathname);

  return (
    <DashboardLayout criticalCount={FLEET_METRICS.criticalCount} title={title} subtitle={subtitle}>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/vehicles" element={<VehiclesPage />} />
        <Route path="/vehicles/:id" element={<VehicleDetailsPage />} />
        <Route path="/telemetry" element={<TelemetryIndexPage />} />
        <Route path="/telemetry/:id" element={<TelemetryPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/maintenance" element={<MaintenanceSchedulePage />} />
        <Route path="/spare-parts" element={<SparePartsPage />} />
      </Routes>
    </DashboardLayout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AlertsProvider>
        <Shell />
      </AlertsProvider>
    </BrowserRouter>
  );
}
