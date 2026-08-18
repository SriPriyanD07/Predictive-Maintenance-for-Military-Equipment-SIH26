// Parts planner view: what to stock, and where the shortages will bite.
import { PackageCheck, PackageX, AlertTriangle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { SPARE_PARTS_FORECAST } from "../data/mockFleet";
import type { StockStatus } from "../types";

const STATUS_META: Record<StockStatus, { label: string; icon: typeof PackageCheck; classes: string }> = {
  sufficient: { label: "Sufficient", icon: PackageCheck, classes: "bg-status-healthyBg text-status-healthy border-status-healthy/30" },
  low: { label: "Low Stock", icon: AlertTriangle, classes: "bg-status-warningBg text-status-warning border-status-warning/30" },
  shortage: { label: "Shortage", icon: PackageX, classes: "bg-status-criticalBg text-status-critical border-status-critical/30" },
};

export function SparePartsPage() {
  const navigate = useNavigate();
  const shortageCount = SPARE_PARTS_FORECAST.filter((p) => p.status === "shortage").length;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <SummaryTile label="Parts Tracked" value={SPARE_PARTS_FORECAST.length} accent="text-ink-100" />
        <SummaryTile
          label="Sufficient Stock"
          value={SPARE_PARTS_FORECAST.filter((p) => p.status === "sufficient").length}
          accent="text-status-healthy"
        />
        <SummaryTile label="Low Stock" value={SPARE_PARTS_FORECAST.filter((p) => p.status === "low").length} accent="text-status-warning" />
        <SummaryTile label="Shortages" value={shortageCount} accent="text-status-critical" />
      </div>

      <div className="rounded-xl border border-base-800 bg-base-900 shadow-panel">
        <div className="flex items-center justify-between border-b border-base-800 px-4 py-3">
          <h3 className="text-sm font-semibold text-ink-100">Spare Parts Demand Forecast</h3>
          <span className="text-xs text-ink-500">Next 30 days, based on predicted failures fleet-wide</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-base-800 text-xs uppercase tracking-wide text-ink-500">
                <th className="px-4 py-2.5 font-medium">Part</th>
                <th className="px-4 py-2.5 font-medium">Predicted Demand</th>
                <th className="px-4 py-2.5 font-medium">Current Stock</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Shortage</th>
                <th className="px-4 py-2.5 font-medium">Affected Vehicles</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-base-850">
              {SPARE_PARTS_FORECAST.map((p) => {
                const meta = STATUS_META[p.status];
                const Icon = meta.icon;
                return (
                  <tr key={p.part} className="hover:bg-base-850">
                    <td className="px-4 py-2.5 font-medium text-ink-100">{p.part}</td>
                    <td className="px-4 py-2.5 text-ink-100">{p.predictedDemand} units</td>
                    <td className="px-4 py-2.5 text-ink-300">{p.currentStock} units</td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta.classes}`}>
                        <Icon size={12} />
                        {meta.label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {p.shortageCount > 0 ? (
                        <span className="font-semibold text-status-critical">-{p.shortageCount}</span>
                      ) : (
                        <span className="text-ink-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {p.affectedVehicleIds.length === 0 && <span className="text-xs text-ink-500">None</span>}
                        {p.affectedVehicleIds.map((id) => (
                          <button
                            key={id}
                            onClick={() => navigate(`/vehicles/${id}`)}
                            className="rounded border border-base-700 bg-base-850 px-1.5 py-0.5 text-xs text-ink-300 hover:border-status-info hover:text-status-info"
                          >
                            {id}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SummaryTile({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="rounded-xl border border-base-800 bg-base-900 p-4 shadow-panel">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${accent}`}>{value}</div>
    </div>
  );
}
