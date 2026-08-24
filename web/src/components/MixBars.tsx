import type { MixEntry } from "../lib/api";
import { pct, compactNumber } from "../lib/format";

const PALETTE = ["#ff5f2e", "#ff2e88", "#8b5cf6", "#1fd1ac", "#ffb020", "#5b8cff", "#e879f9", "#64748b"];

export function MixBars({ entries, limit = 6 }: { entries: MixEntry[]; limit?: number }) {
  const rows = entries.slice(0, limit);
  const max = Math.max(...rows.map((r) => r.pct), 0.0001);
  return (
    <div className="space-y-2.5">
      {rows.map((row, i) => (
        <div key={row.label} className="group">
          <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
            <span className="truncate text-ink-200">{row.label}</span>
            <span className="shrink-0 font-mono text-ink-400">
              {pct(row.pct)} · {compactNumber(row.count)}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-800">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${(row.pct / max) * 100}%`, backgroundColor: PALETTE[i % PALETTE.length] }}
            />
          </div>
        </div>
      ))}
      {rows.length === 0 && <p className="text-xs text-ink-400">Not enough data yet.</p>}
    </div>
  );
}
