import { Router } from "express";
import { getComments, getMetadata, getTopChannelCoverage, getVideoSnapshots } from "../lib/store.js";
import {
  buildFilmSummaries,
  catalogIndex,
  commentComposition,
  coverageGrade,
  evidenceSample,
  evidenceScoreForFilm,
  momentum,
  timeseries,
} from "../lib/insights.js";

export const filmsRouter = Router();

filmsRouter.get("/films", (req, res) => {
  const radarOnly = req.query.radar === "true";
  const summaries = buildFilmSummaries();
  const filtered = radarOnly ? summaries.filter((s) => s.catalog?.onRadar) : summaries;
  res.json(
    filtered.map((s) => ({
      film: s.film,
      onRadar: s.catalog?.onRadar ?? false,
      poster: s.catalog?.poster_url ?? null,
      releaseDate: s.catalog?.release_date ?? null,
      genres: s.catalog?.genres ?? [],
      director: s.catalog?.director ?? null,
      latestViews: s.latestViews,
      latestLikes: s.latestLikes,
      latestComments: s.latestComments,
      videoCount: s.videoCount,
      reviewerChannels: s.reviewerChannels,
      storedComments: s.storedComments,
      usefulComments: s.usefulComments,
      momentum: s.momentum,
      evidence: s.evidence,
      reactionTone: s.reactionTone,
      leadTopic: s.leadTopic,
      summary: s.insight?.summary ?? null,
    })),
  );
});

filmsRouter.get("/films/:film", (req, res) => {
  const film = req.params.film;
  const catalog = catalogIndex().get(film) ?? null;
  const videos = getVideoSnapshots().filter((v) => v.film === film);
  const comments = getComments().filter((c) => c.film === film);
  const coverage = getTopChannelCoverage().filter((c) => c.film === film);

  if (videos.length === 0 && comments.length === 0 && !catalog) {
    res.status(404).json({ error: "Unknown film" });
    return;
  }

  const composition = commentComposition(comments);
  const latestByVideoId = new Map<string, (typeof videos)[number]>();
  for (const v of [...videos].sort((a, b) => Date.parse(a.scanned_at) - Date.parse(b.scanned_at))) {
    latestByVideoId.set(v.video_id, v);
  }

  res.json({
    film,
    catalog,
    insight: getMetadata()?.film_insights?.[film] ?? null,
    momentum: momentum(videos),
    evidence: evidenceScoreForFilm([...latestByVideoId.values()], comments),
    timeseries: timeseries(videos),
    composition,
    coverage: coverageGrade(coverage),
    evidenceSample: evidenceSample(comments),
    videos: [...latestByVideoId.values()]
      .sort((a, b) => b.views - a.views)
      .map((v) => ({
        videoId: v.video_id,
        channel: v.channel,
        title: v.title,
        publishedAt: v.published_at,
        views: v.views,
        likes: v.likes,
        comments: v.comments,
        contentFormat: v.content_format,
        sourceCategory: v.source_category,
        sourceProfile: v.source_profile,
        videoIntent: v.video_intent,
        thumbnailUrl: v.thumbnail_url,
      })),
  });
});
