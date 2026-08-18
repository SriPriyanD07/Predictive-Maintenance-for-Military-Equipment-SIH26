// 21st.dev layer: data-table skeleton for the vehicle listing.
import { useMemo, useState } from "react";
import { ArrowUpDown, Search } from "lucide-react";
import type { RiskLevel, Vehicle } from "../../types";
import { RiskBadge } from "../ui/Badge";

type SortKey = "rulCycles" | "healthScore" | "name";

const RISK_ORDER: Record<RiskLevel, number> = { critical: 0, warning: 1, healthy: 2 };

export function VehicleTable({
  vehicles,
  onSelect,
}: {
  vehicles: Vehicle[];
  onSelect: (vehicle: Vehicle) => void;
}) {
  const [query, setQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "all">("all");
  const [sortKey, setSortKey] = useState<SortKey>("rulCycles");
  const [sortAsc, setSortAsc] = useState(true);

  const filtered = useMemo(() => {
    let rows = vehicles.filter((v) => v.name.toLowerCase().includes(query.toLowerCase()) || v.id.toLowerCase().includes(query.toLowerCase()));
    if (riskFilter !== "all") rows = rows.filter((v) => v.risk === riskFilter);
    rows = [...rows].sort((a, b) => {
      let diff = 0;
      if (sortKey === "name") diff = a.name.localeCompare(b.name);
      else diff = a[sortKey] - b[sortKey];
      return sortAsc ? diff : -diff;
    });
    return rows;
  }, [vehicles, query, riskFilter, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  return (
    <div className="rounded-xl border border-base-800 bg-base-900 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-base-800 px-4 py-3">
        <h3 className="text-sm font-semibold text-ink-100">Fleet Vehicles</h3>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-md border border-base-700 bg-base-850 px-2.5 py-1.5 text-xs">
            <Search size={13} className="text-ink-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search vehicle…"
              className="w-32 bg-transparent text-ink-100 placeholder:text-ink-500 focus:outline-none"
            />
          </div>
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value as RiskLevel | "all")}
            className="rounded-md border border-base-700 bg-base-850 px-2 py-1.5 text-xs text-ink-100 focus:outline-none"
          >
            <option value="all">All risk</option>
            <option value="critical">Critical</option>
            <option value="warning">Watch</option>
            <option value="healthy">Healthy</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-base-800 text-xs uppercase tracking-wide text-ink-500">
              <th className="px-4 py-2.5 font-medium">
                <button onClick={() => toggleSort("name")} className="flex items-center gap-1 hover:text-ink-300">
                  Vehicle <ArrowUpDown size={11} />
                </button>
              </th>
              <th className="px-4 py-2.5 font-medium">Depot</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">
                <button onClick={() => toggleSort("rulCycles")} className="flex items-center gap-1 hover:text-ink-300">
                  RUL <ArrowUpDown size={11} />
                </button>
              </th>
              <th className="px-4 py-2.5 font-medium">
                <button onClick={() => toggleSort("healthScore")} className="flex items-center gap-1 hover:text-ink-300">
                  Health <ArrowUpDown size={11} />
                </button>
              </th>
              <th className="px-4 py-2.5 font-medium">Likely Part</th>
              <th className="px-4 py-2.5 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-base-850">
            {filtered.map((v) => (
              <tr
                key={v.id}
                onClick={() => onSelect(v)}
                className="cursor-pointer transition-colors hover:bg-base-850"
              >
                <td className="px-4 py-2.5">
                  <div className="font-medium text-ink-100">{v.name}</div>
                  <div className="text-xs text-ink-500">{v.id}</div>
                </td>
                <td className="px-4 py-2.5 text-ink-300">{v.fleetGroup}</td>
                <td className="px-4 py-2.5">
                  <RiskBadge risk={v.risk} pulse />
                </td>
                <td className="px-4 py-2.5 text-ink-100">{v.rulCycles} cyc</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-base-800">
                      <div
                        className={`h-full rounded-full ${
                          v.risk === "critical" ? "bg-status-critical" : v.risk === "warning" ? "bg-status-warning" : "bg-status-healthy"
                        }`}
                        style={{ width: `${v.healthScore}%` }}
                      />
                    </div>
                    <span className="text-xs text-ink-500">{v.healthScore}%</span>
                  </div>
                </td>
                <td className="px-4 py-2.5 text-ink-300">{v.likelyFailingPart}</td>
                <td className="px-4 py-2.5 text-xs text-ink-500">
                  {new Date(v.lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm text-ink-500">
                  No vehicles match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
