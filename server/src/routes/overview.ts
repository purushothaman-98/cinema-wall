import { Router } from "express";
import { getComments, getVideoSnapshots } from "../lib/store.js";
import { cached } from "../lib/cache.js";
import {
  arrivalHeatmap,
  buildFilmSummaries,
  channelLeaderboard,
  commentComposition,
  contextSpotlight,
  discussionDepthLeaders,
  overviewTotals,
} from "../lib/insights.js";

export const overviewRouter = Router();

overviewRouter.get("/overview", (_req, res) => {
  res.json(cached("overviewPayload", buildOverviewPayload));
});

function buildOverviewPayload() {
  const summaries = buildFilmSummaries();
  const comments = getComments();

  const onRadar = summaries.filter((s) => s.catalog?.onRadar);
  const trending = [...onRadar]
    .filter((s) => s.momentum.trend !== "insufficient-data")
    .sort((a, b) => b.momentum.viewsPerHour + b.momentum.commentsPerHour * 50 - (a.momentum.viewsPerHour + a.momentum.commentsPerHour * 50))
    .slice(0, 8)
    .map((s) => ({
      film: s.film,
      poster: s.catalog?.poster_url ?? null,
      viewsPerHour: s.momentum.viewsPerHour,
      commentsPerHour: s.momentum.commentsPerHour,
      trend: s.momentum.trend,
      latestViews: s.latestViews,
      evidence: s.evidence,
    }));

  const strongestEvidence = [...summaries]
    .sort((a, b) => b.evidence.score - a.evidence.score)
    .slice(0, 8)
    .map((s) => ({ film: s.film, score: s.evidence.score, label: s.evidence.label, storedComments: s.storedComments }));

  const composition = commentComposition(comments);

  return {
    totals: overviewTotals(),
    trending,
    strongestEvidence,
    languageMix: composition.languageMix,
    topicMix: composition.topicMix,
    commentKindMix: composition.commentKindMix,
    reactionTone: composition.reactionTone,
    arrivalHeatmap: arrivalHeatmap(comments),
    historicalComparisonSpotlight: contextSpotlight(comments, "historical"),
    contemporaryReferenceSpotlight: contextSpotlight(comments, "contemporary"),
    discussionDepthLeaders: discussionDepthLeaders(comments),
    topChannels: channelLeaderboard().slice(0, 6),
  };
}

// Kept for callers that only need the raw counts (used by the "as of" freshness badge).
overviewRouter.get("/health", (_req, res) => {
  const videos = getVideoSnapshots();
  res.json({ ok: true, videoSnapshotRows: videos.length });
});
