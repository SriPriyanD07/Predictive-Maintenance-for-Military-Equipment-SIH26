// 21st.dev layer: dashboard skeleton — fixed sidebar with primary nav.
// Structure only; visual polish of each item comes from the OriginKit-style
// button/badge primitives, not from this component.
import { NavLink } from "react-router-dom";
import { LayoutDashboard, Truck, BarChart3, Bell, Wrench, Radio, Package, Activity } from "lucide-react";

const NAV_ITEMS: { to: string; label: string; icon: typeof LayoutDashboard; badgeKey?: "critical" }[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/vehicles", label: "Vehicles", icon: Truck },
  { to: "/telemetry", label: "Telemetry", icon: Activity },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/alerts", label: "Alerts", icon: Bell, badgeKey: "critical" },
  { to: "/maintenance", label: "Maintenance", icon: Wrench },
  { to: "/spare-parts", label: "Spare Parts", icon: Package },
];

export function Sidebar({ criticalCount }: { criticalCount: number }) {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-base-800 bg-base-900">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-status-info/15 text-status-info">
          <Radio size={18} />
        </div>
        <div>
          <div className="text-sm font-semibold text-ink-100">PrediX RUL</div>
          <div className="text-xs text-ink-500">Ops Center</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, badgeKey }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? "bg-base-800 text-ink-100" : "text-ink-500 hover:bg-base-850 hover:text-ink-300"
              }`
            }
          >
            <span className="flex items-center gap-2.5">
              <Icon size={16} />
              {label}
            </span>
            {badgeKey === "critical" && criticalCount > 0 && (
              <span className="rounded-full bg-status-critical/20 px-1.5 py-0.5 text-[11px] font-semibold text-status-critical">
                {criticalCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mx-3 mb-4 rounded-lg border border-base-800 bg-base-850 px-3 py-3">
        <div className="flex items-center gap-2 text-xs text-ink-500">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-status-healthy" />
          Live telemetry connected
        </div>
      </div>
    </aside>
  );
}
