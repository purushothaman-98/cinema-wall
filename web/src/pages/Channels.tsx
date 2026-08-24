import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../hooks/useApi";
import { LoadingBlock, ErrorBlock } from "../components/Section";
import { compactNumber, pct } from "../lib/format";

const CATEGORY_LABEL: Record<string, string> = {
  critic_review: "Critic",
  general_review: "General review",
  deep_analysis: "Deep analysis",
  roast_commentary: "Roast / commentary",
  mixed_media: "Mixed media",
  open_youtube: "Open YouTube",
};

export function Channels() {
  const { data, loading, error } = useApi(() => api.channels(), []);
  const [query, setQuery] = useState("");

  if (loading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock message={error ?? "Unknown error"} />;

  const rows = data.filter((c) => c.channel.toLowerCase().includes(query.trim().toLowerCase()));
  const maxTracker = Math.max(...data.map((c) => c.tracker_value), 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink-100">Channel leaderboard</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-400">
          Ranked by tracker value — a blend of how many films a channel covers, how many comments its videos generate,
          and how useful those comments turn out to be. Not a subscriber count or influence score.
        </p>
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search channels…"
        className="w-64 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-ember-500 focus:outline-none"
      />

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-ink-700/70 text-left text-xs uppercase tracking-wide text-ink-400">
                <th className="px-4 py-3 font-medium">#</th>
                <th className="px-4 py-3 font-medium">Channel</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium text-right">Films</th>
                <th className="px-4 py-3 font-medium text-right">Comments</th>
                <th className="px-4 py-3 font-medium text-right">Useful</th>
                <th className="px-4 py-3 font-medium">Tracker value</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c, i) => (
                <tr key={c.channel} className="border-b border-ink-800/60 last:border-0 hover:bg-ink-800/40">
                  <td className="px-4 py-3 text-ink-500">{i + 1}</td>
                  <td className="px-4 py-3 font-medium text-ink-100">{c.channel}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-ink-800 px-2 py-0.5 text-[11px] text-ink-300">
                      {CATEGORY_LABEL[c.source_category] ?? c.source_category}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-300">{c.films_covered}</td>
                  <td className="px-4 py-3 text-right font-mono text-ink-300">{compactNumber(c.stored_comments)}</td>
                  <td className="px-4 py-3 text-right font-mono text-ink-300">{pct(c.useful_share_pct / 100)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-ink-800">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-ember-500 to-bloom-500"
                          style={{ width: `${(c.tracker_value / maxTracker) * 100}%` }}
                        />
                      </div>
                      <span className="font-mono text-xs text-ink-400">{c.tracker_value.toFixed(1)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
