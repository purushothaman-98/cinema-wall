import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../hooks/useApi";
import { LoadingBlock, ErrorBlock } from "../components/Section";
import { FilmCard } from "../components/FilmCard";

type SortKey = "views" | "evidence" | "momentum" | "comments";

const SORTERS: Record<SortKey, string> = {
  views: "Most viewed",
  evidence: "Strongest evidence",
  momentum: "Fastest moving",
  comments: "Most discussed",
};

export function Films() {
  const { data, loading, error } = useApi(() => api.films(), []);
  const [query, setQuery] = useState("");
  const [radarOnly, setRadarOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>("views");

  const filtered = useMemo(() => {
    if (!data) return [];
    let rows = data;
    if (radarOnly) rows = rows.filter((f) => f.onRadar);
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      rows = rows.filter((f) => f.film.toLowerCase().includes(q));
    }
    const sorted = [...rows];
    switch (sort) {
      case "views":
        sorted.sort((a, b) => b.latestViews - a.latestViews);
        break;
      case "evidence":
        sorted.sort((a, b) => b.evidence.score - a.evidence.score);
        break;
      case "momentum":
        sorted.sort((a, b) => b.momentum.viewsPerHour - a.momentum.viewsPerHour);
        break;
      case "comments":
        sorted.sort((a, b) => b.storedComments - a.storedComments);
        break;
    }
    return sorted;
  }, [data, query, radarOnly, sort]);

  if (loading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock message={error ?? "Unknown error"} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink-100">Films</h1>
        <p className="mt-1 text-sm text-ink-400">{filtered.length} of {data.length} tracked</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search films…"
          className="w-56 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-ember-500 focus:outline-none"
        />
        <button
          onClick={() => setRadarOnly((v) => !v)}
          className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
            radarOnly ? "border-ember-500 bg-ember-500/10 text-ember-400" : "border-ink-700 text-ink-300 hover:text-ink-100"
          }`}
        >
          On radar only
        </button>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 focus:border-ember-500 focus:outline-none"
        >
          {Object.entries(SORTERS).map(([key, label]) => (
            <option key={key} value={key}>
              Sort: {label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {filtered.map((film) => (
          <FilmCard key={film.film} film={film} />
        ))}
        {filtered.length === 0 && <p className="col-span-full text-sm text-ink-400">No films match.</p>}
      </div>
    </div>
  );
}
