import { Link } from "react-router-dom";
import type { FilmListItem } from "../lib/api";
import { compactNumber } from "../lib/format";
import { EvidenceBadge, RadarBadge, TrendBadge } from "./Badges";

export function FilmCard({ film }: { film: FilmListItem }) {
  return (
    <Link
      to={`/films/${encodeURIComponent(film.film)}`}
      className="panel panel-hover group flex flex-col overflow-hidden"
    >
      <div className="relative aspect-[2/3] w-full overflow-hidden bg-ink-800">
        {film.poster ? (
          <img
            src={film.poster}
            alt={film.film}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-ink-500">No poster</div>
        )}
        <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-ink-950 to-transparent" />
        <div className="absolute left-2 top-2">
          <RadarBadge onRadar={film.onRadar} />
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="font-display text-sm font-semibold leading-snug text-ink-100 line-clamp-2">{film.film}</h3>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-400">
          <span>{compactNumber(film.latestViews)} views</span>
          <span aria-hidden>·</span>
          <span>{compactNumber(film.storedComments)} comments tracked</span>
        </div>
        <div className="mt-auto flex items-center justify-between pt-1">
          <EvidenceBadge evidence={film.evidence} />
          {film.onRadar && <TrendBadge trend={film.momentum.trend} />}
        </div>
      </div>
    </Link>
  );
}
