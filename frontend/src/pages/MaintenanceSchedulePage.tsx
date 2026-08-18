// Dispatch view: "who do I service first?" — ranked by urgency (lowest RUL first).
import { useNavigate } from "react-router-dom";
import { FLEET } from "../data/mockFleet";
import { RiskBadge } from "../components/ui/Badge";

export function MaintenanceSchedulePage() {
  const navigate = useNavigate();
  const ranked = [...FLEET]
    .filter((v) => v.risk !== "healthy")
    .sort((a, b) => a.rulCycles - b.rulCycles);

  return (
    <div className="rounded-xl border border-base-800 bg-base-900 shadow-panel">
      <div className="flex items-center justify-between border-b border-base-800 px-4 py-3">
        <h3 className="text-sm font-semibold text-ink-100">Maintenance Schedule</h3>
        <span className="text-xs text-ink-500">{ranked.length} units require service, ranked by urgency</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-base-800 text-xs uppercase tracking-wide text-ink-500">
              <th className="px-4 py-2.5 font-medium">Rank</th>
              <th className="px-4 py-2.5 font-medium">Vehicle</th>
              <th className="px-4 py-2.5 font-medium">RUL Remaining</th>
              <th className="px-4 py-2.5 font-medium">Likely Failing Part</th>
              <th className="px-4 py-2.5 font-medium">Service Window</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-base-850">
            {ranked.map((v, i) => (
              <tr key={v.id} onClick={() => navigate(`/vehicles/${v.id}`)} className="cursor-pointer transition-colors hover:bg-base-850">
                <td className="px-4 py-2.5">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                      i === 0 ? "bg-status-critical/20 text-status-critical" : "bg-base-800 text-ink-300"
                    }`}
                  >
                    {i + 1}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <div className="font-medium text-ink-100">{v.name}</div>
                  <div className="text-xs text-ink-500">{v.id} · {v.fleetGroup}</div>
                </td>
                <td className="px-4 py-2.5 text-ink-100">
                  {v.rulCycles} cyc <span className="text-xs text-ink-500">(~{v.rulDays}d)</span>
                </td>
                <td className="px-4 py-2.5 text-ink-300">{v.likelyFailingPart}</td>
                <td className="px-4 py-2.5 font-medium text-ink-100">{v.serviceWindow}</td>
                <td className="px-4 py-2.5">
                  <RiskBadge risk={v.risk} pulse />
                </td>
              </tr>
            ))}
            {ranked.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-ink-500">
                  No units currently require maintenance.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
