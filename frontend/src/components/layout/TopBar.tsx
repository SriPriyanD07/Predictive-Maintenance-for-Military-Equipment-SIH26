// 21st.dev layer: top bar — page title + global search/context, kept minimal
// so the eye moves straight to the KPI row below it.
import { Search } from "lucide-react";

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="flex items-center justify-between border-b border-base-800 bg-base-900/60 px-6 py-4">
      <div>
        <h1 className="text-lg font-semibold text-ink-100">{title}</h1>
        {subtitle && <p className="text-sm text-ink-500">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-md border border-base-700 bg-base-850 px-3 py-1.5 text-sm text-ink-500">
          <Search size={14} />
          <span className="hidden sm:inline">Search vehicle ID…</span>
        </div>
        <div className="h-8 w-8 rounded-full bg-base-700" />
      </div>
    </header>
  );
}
