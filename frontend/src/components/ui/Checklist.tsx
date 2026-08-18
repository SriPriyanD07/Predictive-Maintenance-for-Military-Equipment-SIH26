// OriginKit layer: inspection/prep checklist used on the vehicle details page.
import { useState } from "react";
import { Check } from "lucide-react";
import type { InspectionStep } from "../../types";

export function Checklist({ steps }: { steps: InspectionStep[] }) {
  const [checked, setChecked] = useState<Record<number, boolean>>(
    Object.fromEntries(steps.map((s, i) => [i, s.done])),
  );

  return (
    <ul className="space-y-2">
      {steps.map((step, i) => (
        <li key={i}>
          <button
            onClick={() => setChecked((prev) => ({ ...prev, [i]: !prev[i] }))}
            className="flex w-full items-center gap-2.5 rounded-md border border-base-800 bg-base-850 px-3 py-2 text-left text-sm transition-colors hover:border-base-700"
          >
            <span
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                checked[i] ? "border-status-healthy bg-status-healthy/20 text-status-healthy" : "border-base-600 text-transparent"
              }`}
            >
              <Check size={12} strokeWidth={3} />
            </span>
            <span className={checked[i] ? "text-ink-500 line-through" : "text-ink-100"}>{step.label}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
