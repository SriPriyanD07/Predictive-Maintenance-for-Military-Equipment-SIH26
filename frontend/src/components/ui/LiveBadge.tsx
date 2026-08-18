// States, unambiguously, whether the screen is showing model output or mock
// fixtures. Without this a dead backend looks identical to a working one.
import { useFleet } from "../../hooks/useFleet";

export function LiveBadge() {
  const { live, tick, running, error, modelMetrics } = useFleet();

  if (!live) {
    return (
      <span
        className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-400"
        title={error ? "backend unreachable: " + error : undefined}
      >
        <span className="h-2 w-2 rounded-full bg-amber-400" />
        MOCK DATA — backend offline, numbers are placeholders
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
      <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
      LIVE — XGBoost · MAE {modelMetrics.mae} · tick {tick} ·{" "}
      {running ? "running" : "paused"}
    </span>
  );
}
