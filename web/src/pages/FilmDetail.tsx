import { useParams, Link } from "react-router-dom";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../lib/api";
import { useApi } from "../hooks/useApi";
import { LoadingBlock, ErrorBlock, Section } from "../components/Section";
import { StatTile } from "../components/StatTile";
import { EvidenceBadge, RadarBadge, TrendBadge } from "../components/Badges";
import { MixBars } from "../components/MixBars";
import { ReactionTone } from "../components/ReactionTone";
import { CommentCard } from "../components/CommentCard";
import { compactNumber, pct, shortDate, chartTime } from "../lib/format";

export function FilmDetail() {
  const { film } = useParams<{ film: string }>();
  const { data, loading, error } = useApi(() => api.film(film ?? ""), [film]);

  if (loading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock message={error ?? "Unknown error"} />;

  const { catalog, composition } = data;
  const chartData = data.timeseries.map((p) => ({
    ...p,
    label: chartTime(p.t),
  }));

  return (
    <div className="space-y-10">
      <Link to="/films" className="text-xs font-medium text-ink-400 hover:text-ink-200">
        ← All films
      </Link>

      <div className="grid gap-6 md:grid-cols-[180px_1fr]">
        {catalog?.poster_url && (
          <img src={catalog.poster_url} alt={data.film} className="h-full max-h-64 w-full rounded-2xl object-cover shadow-glow" />
        )}
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <RadarBadge onRadar={catalog?.onRadar ?? false} />
            <EvidenceBadge evidence={data.evidence} />
          </div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink-100">{data.film}</h1>
          {catalog?.original_title && <p className="text-sm text-ink-400">{catalog.original_title}</p>}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-300">
            {catalog?.release_date && <span>Released {shortDate(catalog.release_date)}</span>}
            {catalog?.director && <span>Dir. {catalog.director}</span>}
            {!!catalog?.genres?.length && <span>{catalog.genres.join(", ")}</span>}
          </div>
          {catalog?.overview && <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-400">{catalog.overview}</p>}
          {!!catalog?.cast?.length && (
            <p className="mt-2 text-xs text-ink-500">Cast: {catalog.cast.slice(0, 6).join(", ")}</p>
          )}
          <div className="mt-4 flex items-center gap-3">
            <TrendBadge trend={data.momentum.trend} />
            {!data.momentum.stale && (
              <span className="text-xs text-ink-400">
                +{compactNumber(data.momentum.viewsPerHour)} views/hr · +{data.momentum.commentsPerHour} comments/hr
              </span>
            )}
          </div>
        </div>
      </div>

      {data.insight?.summary && (
        <div className="panel border-ember-500/20 bg-gradient-to-br from-ember-500/5 to-bloom-500/5 p-5">
          <p className="kicker mb-2">Auto-generated read of the sample</p>
          <p className="text-sm leading-relaxed text-ink-200">{data.insight.summary}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Views tracked" value={compactNumber(sumViews(data.videos))} accent="ember" />
        <StatTile label="Comments tracked" value={compactNumber(composition.totalComments)} accent="bloom" />
        <StatTile label="Videos monitored" value={data.videos.length} accent="violet" />
        <StatTile label="Reviewer channels" value={new Set(data.videos.map((v) => v.channel)).size} accent="signal" />
      </div>

      {chartData.length > 1 && (
        <div className="panel p-5">
          <Section title="Attention over time" subtitle="Total tracked views across all monitored videos for this film">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="viewsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ff5f2e" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#ff5f2e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1f232f" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: "#8b8fa3", fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={40} />
                  <YAxis
                    tick={{ fill: "#8b8fa3", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => compactNumber(v)}
                    width={44}
                  />
                  <Tooltip
                    contentStyle={{ background: "#161922", border: "1px solid #2a2f3d", borderRadius: 10, fontSize: 12 }}
                    labelStyle={{ color: "#c4c7d4" }}
                    formatter={(value: number) => compactNumber(value)}
                  />
                  <Area type="monotone" dataKey="views" stroke="#ff5f2e" strokeWidth={2} fill="url(#viewsFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Section>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="panel p-5">
          <Section title="Language mix">
            <MixBars entries={composition.languageMix} />
          </Section>
        </div>
        <div className="panel p-5">
          <Section title="Discussion topics">
            <MixBars entries={composition.topicMix.filter((t) => t.label !== "General reaction")} />
          </Section>
        </div>
        <div className="panel p-5">
          <Section title="Reaction tone">
            <ReactionTone tone={composition.reactionTone} />
          </Section>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <SignalChip label="Discussion depth" value={pct(composition.discussionDepthPct)} note="detailed comments & questions" />
        <SignalChip label="Older-film comparisons" value={pct(composition.historicalComparisonPct)} note="nostalgia / remake talk" />
        <SignalChip label="Current-events pull" value={pct(composition.contemporaryReferencePct)} note="politics, memes, social refs" />
      </div>

      {data.coverage.total > 0 && (
        <div className="panel p-5">
          <Section
            title="Major-channel coverage"
            subtitle={`${data.coverage.present} of ${data.coverage.total} tracked major channels have covered this film`}
          >
            <div className="h-2 w-full overflow-hidden rounded-full bg-ink-800">
              <div
                className="h-full rounded-full bg-gradient-to-r from-signal-500 to-ember-500"
                style={{ width: `${data.coverage.pct * 100}%` }}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {data.coverage.channels.map((c) => (
                <span
                  key={c.channel}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                    c.status === "fetched_with_comments" || c.status === "tracked_no_comments"
                      ? "bg-signal-500/15 text-signal-400"
                      : "bg-ink-800 text-ink-500"
                  }`}
                >
                  {c.channel}
                </span>
              ))}
            </div>
          </Section>
        </div>
      )}

      {data.insight?.reviewers && data.insight.reviewers.length > 0 && (
        <div className="panel p-5">
          <Section title="Who's reviewing it" subtitle="Useful-comment yield by channel, from the auto-generated read">
            <div className="grid gap-2 sm:grid-cols-2">
              {data.insight.reviewers.slice(0, 8).map((r) => (
                <div key={r.channel} className="flex items-center justify-between rounded-lg border border-ink-700/70 bg-ink-800/40 px-3 py-2 text-sm">
                  <span className="text-ink-200">{r.channel}</span>
                  <span className="font-mono text-xs text-ink-400">{r.useful_comments} useful</span>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {data.evidenceSample.length > 0 && (
        <div>
          <Section title="Evidence wall" subtitle="A varied sample of raw public comments, with source links">
            <div className="grid gap-4 sm:grid-cols-2">
              {data.evidenceSample.map((c, i) => (
                <CommentCard key={`${c.author}-${i}`} comment={c} />
              ))}
            </div>
          </Section>
        </div>
      )}

      {data.videos.length > 0 && (
        <div className="panel overflow-hidden">
          <Section title="Monitored videos">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-ink-700/70 text-left text-xs uppercase tracking-wide text-ink-400">
                    <th className="px-4 py-3 font-medium">Video</th>
                    <th className="px-4 py-3 font-medium">Channel</th>
                    <th className="px-4 py-3 font-medium text-right">Views</th>
                    <th className="px-4 py-3 font-medium text-right">Comments</th>
                  </tr>
                </thead>
                <tbody>
                  {data.videos.slice(0, 20).map((v) => (
                    <tr key={v.videoId} className="border-b border-ink-800/60 last:border-0 hover:bg-ink-800/40">
                      <td className="max-w-xs truncate px-4 py-3 text-ink-200">
                        <a
                          href={`https://youtube.com/watch?v=${v.videoId}`}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:text-ember-400"
                        >
                          {v.title || v.videoId}
                        </a>
                      </td>
                      <td className="px-4 py-3 text-ink-400">{v.channel}</td>
                      <td className="px-4 py-3 text-right font-mono text-ink-300">{compactNumber(v.views)}</td>
                      <td className="px-4 py-3 text-right font-mono text-ink-300">{compactNumber(v.comments)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>
      )}
    </div>
  );
}

function sumViews(videos: { views: number }[]): number {
  return videos.reduce((a, v) => a + v.views, 0);
}

function SignalChip({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="panel p-4">
      <p className="kicker">{label}</p>
      <p className="mt-1 font-display text-2xl font-bold text-ink-100">{value}</p>
      <p className="mt-0.5 text-xs text-ink-400">{note}</p>
    </div>
  );
}
