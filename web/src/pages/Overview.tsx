import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi } from "../hooks/useApi";
import { StatTile } from "../components/StatTile";
import { Section, LoadingBlock, ErrorBlock } from "../components/Section";
import { MixBars } from "../components/MixBars";
import { ReactionTone } from "../components/ReactionTone";
import { ArrivalHeatmap } from "../components/Heatmap";
import { TrendBadge } from "../components/Badges";
import { compactNumber, pct, timeAgo } from "../lib/format";

export function Overview() {
  const { data, loading, error } = useApi(() => api.overview(), []);

  if (loading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock message={error ?? "Unknown error"} />;

  const { totals } = data;

  return (
    <div className="space-y-12">
      <div>
        <div className="mb-1 flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${totals.status === "healthy" ? "bg-signal-400" : "bg-bloom-400"}`}
          />
          <span className="kicker">{totals.status === "healthy" ? "Collector healthy" : "Collector attention needed"}</span>
          <span className="text-xs text-ink-500">· data as of {timeAgo(totals.lastScan)}</span>
        </div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink-100 sm:text-4xl">
          What Tamil cinema audiences are actually saying on YouTube
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-400">
          Public review videos and comments, tracked every 30 minutes. Evidence and discussion patterns — deliberately
          no film-quality or sentiment score.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Films on radar" value={totals.filmsOnRadar} accent="ember" hint={`${totals.filmsAnalyzed} analyzed lifetime`} />
        <StatTile label="Comments tracked" value={compactNumber(totals.storedComments)} accent="bloom" />
        <StatTile label="Videos monitored" value={compactNumber(totals.videosMonitored)} accent="violet" />
        <StatTile label="Channels covered" value={totals.channelsTracked} accent="signal" />
      </div>

      <Section title="Trending now" subtitle="View & comment velocity from the last reliable ~30-minute window, on-radar films only">
        <div className="scrollbar-none -mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-2">
          {data.trending.map((t) => (
            <Link
              key={t.film}
              to={`/films/${encodeURIComponent(t.film)}`}
              className="panel panel-hover flex w-52 shrink-0 snap-start flex-col gap-3 p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-display text-sm font-semibold leading-snug text-ink-100 line-clamp-2">{t.film}</h3>
                <TrendBadge trend={t.trend} />
              </div>
              <div className="mt-auto space-y-1 text-xs text-ink-400">
                <p>
                  <span className="font-mono text-ink-100">+{compactNumber(t.viewsPerHour)}</span> views/hr
                </p>
                <p>
                  <span className="font-mono text-ink-100">+{t.commentsPerHour}</span> comments/hr
                </p>
              </div>
            </Link>
          ))}
          {data.trending.length === 0 && <p className="text-sm text-ink-400">Not enough live velocity data yet.</p>}
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="panel p-5 lg:col-span-1">
          <Section title="Language mix" subtitle="Across all tracked comments">
            <MixBars entries={data.languageMix} />
          </Section>
        </div>
        <div className="panel p-5 lg:col-span-1">
          <Section title="What's discussed" subtitle="Beyond general reactions">
            <MixBars entries={data.topicMix.filter((t) => t.label !== "General reaction")} />
          </Section>
        </div>
        <div className="panel p-5 lg:col-span-1">
          <Section title="Reaction tone" subtitle="Sitewide, from comment wording">
            <ReactionTone tone={data.reactionTone} />
          </Section>
        </div>
      </div>

      <div className="panel p-5">
        <Section title="When the audience shows up" subtitle="Comment arrival heatmap, all films combined">
          <ArrivalHeatmap cells={data.arrivalHeatmap} />
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="panel p-5">
          <Section title="Deepest discussions" subtitle="Highest share of detailed comments & questions, not just reactions">
            <ol className="space-y-2.5">
              {data.discussionDepthLeaders.map((f, i) => (
                <li key={f.film}>
                  <Link to={`/films/${encodeURIComponent(f.film)}`} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 hover:bg-ink-800">
                    <span className="flex items-center gap-2.5 text-sm text-ink-200">
                      <span className="w-4 text-right font-mono text-xs text-ink-500">{i + 1}</span>
                      {f.film}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-ink-400">{pct(f.depthPct)} depth</span>
                  </Link>
                </li>
              ))}
              {data.discussionDepthLeaders.length === 0 && <p className="text-sm text-ink-400">Not enough data yet.</p>}
            </ol>
          </Section>
        </div>

        <div className="panel p-5">
          <Section title="Strongest evidence" subtitle="Best-covered samples — reviewer breadth, not praise">
            <ol className="space-y-2.5">
              {data.strongestEvidence.map((f, i) => (
                <li key={f.film}>
                  <Link to={`/films/${encodeURIComponent(f.film)}`} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 hover:bg-ink-800">
                    <span className="flex items-center gap-2.5 text-sm text-ink-200">
                      <span className="w-4 text-right font-mono text-xs text-ink-500">{i + 1}</span>
                      {f.film}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-ink-400">{f.score}/100</span>
                  </Link>
                </li>
              ))}
            </ol>
          </Section>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <SpotlightCard
          title="Compared to older films"
          subtitle="Unusually high rate of nostalgia / remake comparisons"
          rows={data.historicalComparisonSpotlight}
        />
        <SpotlightCard
          title="Pulled into current events"
          subtitle="Unusually high rate of politics, memes & social commentary"
          rows={data.contemporaryReferenceSpotlight}
        />
      </div>

      <div className="panel p-5">
        <Section
          title="Top channels"
          subtitle="Ranked by tracker value — coverage breadth × comment yield × usefulness"
          action={
            <Link to="/channels" className="text-xs font-semibold text-ember-400 hover:text-ember-300">
              View all →
            </Link>
          }
        >
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {data.topChannels.map((c) => (
              <div key={c.channel} className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
                <p className="truncate text-sm font-medium text-ink-100">{c.channel}</p>
                <p className="mt-0.5 text-xs text-ink-400">
                  {c.films_covered} films · {compactNumber(c.stored_comments)} comments
                </p>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

function SpotlightCard({
  title,
  subtitle,
  rows,
}: {
  title: string;
  subtitle: string;
  rows: { film: string; pct: number; sampleSize: number }[];
}) {
  return (
    <div className="panel p-5">
      <Section title={title} subtitle={subtitle}>
        <ol className="space-y-2.5">
          {rows.map((r, i) => (
            <li key={r.film}>
              <Link
                to={`/films/${encodeURIComponent(r.film)}`}
                className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 hover:bg-ink-800"
              >
                <span className="flex items-center gap-2.5 text-sm text-ink-200">
                  <span className="w-4 text-right font-mono text-xs text-ink-500">{i + 1}</span>
                  {r.film}
                </span>
                <span className="shrink-0 font-mono text-xs text-ink-400">{pct(r.pct)}</span>
              </Link>
            </li>
          ))}
          {rows.length === 0 && <p className="text-sm text-ink-400">No standout films yet.</p>}
        </ol>
      </Section>
    </div>
  );
}
