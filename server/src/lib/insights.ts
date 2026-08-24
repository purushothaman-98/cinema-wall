import type {
  CatalogFilm,
  ChannelEvaluationRow,
  CommentRow,
  FilmInsight,
  TopChannelCoverageRow,
  VideoSnapshotRow,
} from "./types.js";
import {
  getChannelEvaluation,
  getComments,
  getMetadata,
  getTopChannelCoverage,
  getVideoSnapshots,
} from "./store.js";

// ---------- small utilities ----------

function groupBy<T, K>(items: T[], key: (item: T) => K): Map<K, T[]> {
  const map = new Map<K, T[]>();
  for (const item of items) {
    const k = key(item);
    const bucket = map.get(k);
    if (bucket) bucket.push(item);
    else map.set(k, [item]);
  }
  return map;
}

function sum(values: number[]): number {
  return values.reduce((a, b) => a + b, 0);
}

function share(part: number, whole: number): number {
  return whole > 0 ? part / whole : 0;
}

function topOfCounts(counts: Map<string, number>): string | null {
  let best: string | null = null;
  let bestCount = -1;
  for (const [key, count] of counts) {
    if (count > bestCount) {
      best = key;
      bestCount = count;
    }
  }
  return best;
}

function countBy(values: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const value of values) {
    out[value] = (out[value] ?? 0) + 1;
  }
  return out;
}

// ---------- catalog ----------

export interface CatalogEntry extends CatalogFilm {
  onRadar: boolean;
}

/** Merges the active TMDB catalog with the historical one; active entries win. */
export function catalogIndex(): Map<string, CatalogEntry> {
  const meta = getMetadata();
  const index = new Map<string, CatalogEntry>();
  if (!meta) return index;
  for (const film of meta.movie_catalog_history ?? []) {
    index.set(film.title, { ...film, onRadar: false });
  }
  for (const film of meta.movie_catalog ?? []) {
    index.set(film.title, { ...film, onRadar: true });
  }
  return index;
}

// ---------- momentum / timeseries ----------

interface ScanRound {
  scannedAt: string;
  epochMs: number;
  views: number;
  likes: number;
  comments: number;
  standardViews: number;
  shortViews: number;
  videoCount: number;
}

/** Collapses a film's per-video snapshots into per-scan-round totals (all videos share one scanned_at per run). */
function scanRounds(rows: VideoSnapshotRow[]): ScanRound[] {
  const byTime = groupBy(rows, (r) => r.scanned_at);
  const rounds: ScanRound[] = [];
  for (const [scannedAt, group] of byTime) {
    const epochMs = Date.parse(scannedAt);
    if (Number.isNaN(epochMs)) continue;
    rounds.push({
      scannedAt,
      epochMs,
      views: sum(group.map((g) => g.views)),
      likes: sum(group.map((g) => g.likes)),
      comments: sum(group.map((g) => g.comments)),
      standardViews: sum(group.filter((g) => g.content_format === "Video").map((g) => g.views)),
      shortViews: sum(group.filter((g) => g.content_format === "Short").map((g) => g.views)),
      videoCount: group.length,
    });
  }
  return rounds.sort((a, b) => a.epochMs - b.epochMs);
}

export type Trend = "rising" | "cooling" | "flat" | "insufficient-data";

export interface Momentum {
  viewsPerHour: number;
  commentsPerHour: number;
  windowMinutes: number;
  trend: Trend;
  asOf: string | null;
  /** true when the most recent reliable gap is old enough that this film is no longer on the 30-minute cadence. */
  stale: boolean;
}

const RELIABLE_WINDOW_MIN = 20;
const RELIABLE_WINDOW_MAX = 70;
const STALE_AFTER_MS = 3 * 60 * 60 * 1000; // films that dropped off the active monitor read as stale, not "rising now"

/**
 * "Now", for freshness purposes, is the newest scan the dataset itself has ever recorded —
 * not the wall clock. The collector can go quiet for a while (quota, a paused workflow) without
 * every film in the dashboard suddenly reading as stale relative to a clock the data can't see.
 */
export function datasetReferenceMs(): number {
  let max = 0;
  for (const row of getVideoSnapshots()) {
    const ms = Date.parse(row.scanned_at);
    if (Number.isFinite(ms) && ms > max) max = ms;
  }
  return max || Date.now();
}

/** View/comment velocity from the last reliable ~30-minute gap between scan rounds, plus a rising/cooling read. */
export function momentum(rows: VideoSnapshotRow[], nowMs: number = datasetReferenceMs()): Momentum {
  const rounds = scanRounds(rows);
  const gaps: { views: number; comments: number; perHour: number; commentsPerHour: number; at: string }[] = [];
  for (let i = 1; i < rounds.length; i++) {
    const prev = rounds[i - 1];
    const cur = rounds[i];
    const minutes = (cur.epochMs - prev.epochMs) / 60000;
    if (minutes < RELIABLE_WINDOW_MIN || minutes > RELIABLE_WINDOW_MAX) continue;
    const viewsGained = Math.max(0, cur.views - prev.views);
    const commentsGained = Math.max(0, cur.comments - prev.comments);
    gaps.push({
      views: viewsGained,
      comments: commentsGained,
      perHour: (viewsGained * 60) / minutes,
      commentsPerHour: (commentsGained * 60) / minutes,
      at: cur.scannedAt,
    });
  }
  if (gaps.length === 0) {
    return { viewsPerHour: 0, commentsPerHour: 0, windowMinutes: 0, trend: "insufficient-data", asOf: null, stale: true };
  }
  const latest = gaps[gaps.length - 1];
  const stale = nowMs - Date.parse(latest.at) > STALE_AFTER_MS;
  let trend: Trend = "flat";
  if (stale) {
    trend = "insufficient-data";
  } else if (gaps.length >= 2) {
    const prior = gaps[gaps.length - 2];
    if (latest.perHour > prior.perHour * 1.15) trend = "rising";
    else if (latest.perHour < prior.perHour * 0.85) trend = "cooling";
  } else {
    trend = "insufficient-data";
  }
  return {
    viewsPerHour: stale ? 0 : Math.round(latest.perHour),
    commentsPerHour: stale ? 0 : Math.round(latest.commentsPerHour * 10) / 10,
    windowMinutes: RELIABLE_WINDOW_MIN,
    trend,
    asOf: latest.at,
    stale,
  };
}

export interface TimeseriesPoint {
  t: string;
  views: number;
  likes: number;
  comments: number;
  standardViews: number;
  shortViews: number;
}

export function timeseries(rows: VideoSnapshotRow[]): TimeseriesPoint[] {
  return scanRounds(rows).map((r) => ({
    t: r.scannedAt,
    views: r.views,
    likes: r.likes,
    comments: r.comments,
    standardViews: r.standardViews,
    shortViews: r.shortViews,
  }));
}

// ---------- comment composition ----------

export interface MixEntry {
  label: string;
  count: number;
  pct: number;
}

function mix(values: string[]): MixEntry[] {
  const counts = countBy(values);
  const total = values.length;
  return Object.entries(counts)
    .map(([label, count]) => ({ label, count, pct: share(count, total) }))
    .sort((a, b) => b.count - a.count);
}

export interface ReactionTone {
  appreciative: number;
  critical: number;
  mixed: number;
  sampleSize: number;
}

export interface CommentComposition {
  totalComments: number;
  usefulComments: number;
  languageMix: MixEntry[];
  topicMix: MixEntry[];
  commentKindMix: MixEntry[];
  reactionTone: ReactionTone;
  discussionDepthPct: number; // "Detailed discussion" + "Question" share of useful comments
  historicalComparisonPct: number;
  contemporaryReferencePct: number;
  sarcasmPct: number;
  promotionalFiltered: number;
  scamFlags: number;
}

export function commentComposition(rows: CommentRow[]): CommentComposition {
  const total = rows.length;
  const useful = rows.filter((r) => !r.low_information);
  const usefulTexts = useful.length;
  const reactionRows = useful.filter((r) => r.reaction_signal !== "Mixed / unclear");
  const appreciative = reactionRows.filter((r) => r.reaction_signal === "Appreciative").length;
  const critical = reactionRows.filter((r) => r.reaction_signal === "Critical").length;

  const depthRows = useful.filter((r) => r.comment_kind === "Detailed discussion" || r.comment_kind === "Question");
  const historical = rows.filter((r) => r.context_signals.includes("Older-film")).length;
  const contemporary = rows.filter((r) => r.context_signals.includes("Contemporary social")).length;
  const sarcasm = rows.filter((r) => r.possible_sarcasm).length;
  const promo = rows.filter((r) => r.promotional_flag).length;
  const scam = rows.filter((r) => r.scam_risk && r.scam_risk !== "Low").length;

  return {
    totalComments: total,
    usefulComments: usefulTexts,
    languageMix: mix(useful.map((r) => r.language)),
    topicMix: mix(useful.map((r) => r.topic)),
    commentKindMix: mix(useful.map((r) => r.comment_kind)),
    reactionTone: {
      appreciative,
      critical,
      mixed: reactionRows.length - appreciative - critical,
      sampleSize: reactionRows.length,
    },
    discussionDepthPct: share(depthRows.length, usefulTexts),
    historicalComparisonPct: share(historical, total),
    contemporaryReferencePct: share(contemporary, total),
    sarcasmPct: share(sarcasm, total),
    promotionalFiltered: promo,
    scamFlags: scam,
  };
}

export interface CommentSample {
  text: string;
  author: string;
  channel: string;
  url: string;
  likes: number;
  topic: string;
  commentKind: string;
  reactionSignal: string;
  language: string;
  createdAt: string;
}

function toSample(row: CommentRow): CommentSample {
  return {
    text: row.text,
    author: row.author,
    channel: row.channel,
    url: row.url,
    likes: row.likes,
    topic: row.topic,
    commentKind: row.comment_kind,
    reactionSignal: row.reaction_signal,
    language: row.language,
    createdAt: row.created_at,
  };
}

/** A small, deliberately varied evidence sample: most-liked, a question, a critical take, a detailed one. */
export function evidenceSample(rows: CommentRow[], limit = 6): CommentSample[] {
  const useful = rows.filter((r) => !r.low_information && !r.promotional_flag && r.text && r.text.length > 0);
  const picked = new Map<string, CommentRow>();
  const byLikes = [...useful].sort((a, b) => b.likes - a.likes);
  for (const row of byLikes) {
    if (picked.size >= 2) break;
    picked.set(row.source_id, row);
  }
  const critical = useful.find((r) => r.reaction_signal === "Critical" && !picked.has(r.source_id));
  if (critical) picked.set(critical.source_id, critical);
  const question = useful.find((r) => r.is_question && !picked.has(r.source_id));
  if (question) picked.set(question.source_id, question);
  const detailed = useful.find((r) => r.comment_kind === "Detailed discussion" && !picked.has(r.source_id));
  if (detailed) picked.set(detailed.source_id, detailed);
  for (const row of byLikes) {
    if (picked.size >= limit) break;
    picked.set(row.source_id, row);
  }
  return [...picked.values()].slice(0, limit).map(toSample);
}

// ---------- evidence / coverage grading ----------

export type EvidenceLabel = "Strong evidence" | "Useful evidence" | "Thin evidence" | "Awaiting evidence";

export function evidenceGrade(score: number): EvidenceLabel {
  if (score >= 72) return "Strong evidence";
  if (score >= 48) return "Useful evidence";
  if (score >= 24) return "Thin evidence";
  return "Awaiting evidence";
}

export interface EvidenceScore {
  score: number;
  label: EvidenceLabel;
}

const clip = (v: number, max: number) => Math.min(v, max);

export function evidenceScore(opts: {
  storedComments: number;
  reviewerChannels: number;
  sourceLayers: number;
  usefulShare: number;
  reviewItems: number;
  questions: number;
}): EvidenceScore {
  const score =
    (clip(opts.storedComments, 300) / 300) * 32 +
    (clip(opts.reviewerChannels, 6) / 6) * 18 +
    (clip(opts.sourceLayers, 4) / 4) * 12 +
    clip(opts.usefulShare, 1) * 18 +
    (clip(opts.reviewItems, 6) / 6) * 15 +
    (clip(opts.questions, 30) / 30) * 5;
  return { score: Math.round(score), label: evidenceGrade(score) };
}

export interface CoverageGrade {
  present: number;
  total: number;
  pct: number;
  channels: { channel: string; status: string; rank: number }[];
}

const COVERED_STATUSES = new Set(["fetched_with_comments", "tracked_no_comments"]);

export function coverageGrade(rows: TopChannelCoverageRow[]): CoverageGrade {
  if (rows.length === 0) return { present: 0, total: 0, pct: 0, channels: [] };
  const present = rows.filter((r) => COVERED_STATUSES.has(r.status)).length;
  const total = rows[0]?.top_channels_total || rows.length;
  return {
    present,
    total,
    pct: share(present, total),
    channels: rows
      .sort((a, b) => a.channel_rank - b.channel_rank)
      .map((r) => ({ channel: r.channel, status: r.status, rank: r.channel_rank })),
  };
}

// ---------- global insights ----------

const REVIEW_INTENTS = new Set([
  "review",
  "short_review",
  "public_review",
  "deep_analysis",
  "roast_commentary",
  "film_discussion",
]);
/** The evidence score for one film's already-deduped latest video rows + its comments. */
export function evidenceScoreForFilm(latestVideos: VideoSnapshotRow[], filmComments: CommentRow[]): EvidenceScore {
  const composition = commentComposition(filmComments);
  const sourceLayers = new Set(latestVideos.map((v) => v.source_category)).size;
  const reviewerChannels = new Set(latestVideos.map((v) => v.channel)).size;
  const reviewItems = latestVideos.filter((v) => REVIEW_INTENTS.has(v.video_intent)).length;
  return evidenceScore({
    storedComments: composition.totalComments,
    reviewerChannels,
    sourceLayers,
    usefulShare: share(composition.usefulComments, composition.totalComments),
    reviewItems,
    questions: filmComments.filter((c) => c.is_question).length,
  });
}

export interface FilmSummary {
  film: string;
  catalog: CatalogEntry | null;
  insight: FilmInsight | null;
  latestViews: number;
  latestLikes: number;
  latestComments: number;
  videoCount: number;
  reviewerChannels: number;
  storedComments: number;
  usefulComments: number;
  momentum: Momentum;
  evidence: EvidenceScore;
  reactionTone: ReactionTone;
  leadTopic: string | null;
}

/** One row per film: the summary card used by the films grid and the homepage. */
export function buildFilmSummaries(): FilmSummary[] {
  const videos = getVideoSnapshots();
  const comments = getComments();
  const catalog = catalogIndex();
  const meta = getMetadata();

  const filmNames = new Set<string>([
    ...videos.map((v) => v.film),
    ...comments.map((c) => c.film),
    ...(meta?.all_films_analyzed ?? []),
  ]);

  const videosByFilm = groupBy(videos, (v) => v.film);
  const commentsByFilm = groupBy(comments, (c) => c.film);

  const summaries: FilmSummary[] = [];
  for (const film of filmNames) {
    const filmVideos = videosByFilm.get(film) ?? [];
    const filmComments = commentsByFilm.get(film) ?? [];
    const latestByVideoId = new Map<string, VideoSnapshotRow>();
    for (const v of [...filmVideos].sort((a, b) => Date.parse(a.scanned_at) - Date.parse(b.scanned_at))) {
      latestByVideoId.set(v.video_id, v);
    }
    const latest = [...latestByVideoId.values()];
    const composition = commentComposition(filmComments);
    const reviewerChannels = new Set(latest.map((v) => v.channel)).size;

    summaries.push({
      film,
      catalog: catalog.get(film) ?? null,
      insight: meta?.film_insights?.[film] ?? null,
      latestViews: sum(latest.map((v) => v.views)),
      latestLikes: sum(latest.map((v) => v.likes)),
      latestComments: sum(latest.map((v) => v.comments)),
      videoCount: latest.length,
      reviewerChannels,
      storedComments: composition.totalComments,
      usefulComments: composition.usefulComments,
      momentum: momentum(filmVideos),
      evidence: evidenceScoreForFilm(latest, filmComments),
      reactionTone: composition.reactionTone,
      leadTopic: composition.topicMix[0]?.label ?? null,
    });
  }

  return summaries.sort((a, b) => b.latestViews - a.latestViews);
}

export interface HeatmapCell {
  day: number; // 0 = Sunday .. 6 = Saturday (UTC)
  hour: number; // 0-23 UTC
  count: number;
}

/** Comment arrival pattern across the week — when the audience actually shows up, in UTC. */
export function arrivalHeatmap(comments: CommentRow[]): HeatmapCell[] {
  const grid = new Map<string, number>();
  for (const row of comments) {
    const ms = Date.parse(row.created_at);
    if (Number.isNaN(ms)) continue;
    const d = new Date(ms);
    const key = `${d.getUTCDay()}:${d.getUTCHours()}`;
    grid.set(key, (grid.get(key) ?? 0) + 1);
  }
  const cells: HeatmapCell[] = [];
  for (let day = 0; day < 7; day++) {
    for (let hour = 0; hour < 24; hour++) {
      cells.push({ day, hour, count: grid.get(`${day}:${hour}`) ?? 0 });
    }
  }
  return cells;
}

export interface ChannelLeaderboardRow extends ChannelEvaluationRow {}

export function channelLeaderboard(): ChannelLeaderboardRow[] {
  return getChannelEvaluation().sort((a, b) => b.tracker_value - a.tracker_value);
}

export interface ContextSpotlightFilm {
  film: string;
  pct: number;
  sampleSize: number;
}

/** Films where the audience is unusually busy comparing to older films / pulling in current events. */
export function contextSpotlight(comments: CommentRow[], kind: "historical" | "contemporary", minSample = 15, limit = 5): ContextSpotlightFilm[] {
  const byFilm = groupBy(comments, (c) => c.film);
  const needle = kind === "historical" ? "Older-film" : "Contemporary social";
  const rows: ContextSpotlightFilm[] = [];
  for (const [film, rowsForFilm] of byFilm) {
    if (rowsForFilm.length < minSample) continue;
    const hits = rowsForFilm.filter((r) => r.context_signals.includes(needle)).length;
    if (hits === 0) continue;
    rows.push({ film, pct: share(hits, rowsForFilm.length), sampleSize: rowsForFilm.length });
  }
  return rows.sort((a, b) => b.pct - a.pct).slice(0, limit);
}

export interface DiscussionDepthFilm {
  film: string;
  depthPct: number;
  usefulComments: number;
}

/** Films whose comment section is genuinely discussing the film, not just dropping quick reactions. */
export function discussionDepthLeaders(comments: CommentRow[], minSample = 25, limit = 5): DiscussionDepthFilm[] {
  const byFilm = groupBy(comments, (c) => c.film);
  const rows: DiscussionDepthFilm[] = [];
  for (const [film, rowsForFilm] of byFilm) {
    const useful = rowsForFilm.filter((r) => !r.low_information);
    if (useful.length < minSample) continue;
    const depth = useful.filter((r) => r.comment_kind === "Detailed discussion" || r.comment_kind === "Question").length;
    rows.push({ film, depthPct: share(depth, useful.length), usefulComments: useful.length });
  }
  return rows.sort((a, b) => b.depthPct - a.depthPct).slice(0, limit);
}

export function overviewTotals() {
  const meta = getMetadata();
  const videos = getVideoSnapshots();
  const comments = getComments();
  const uniqueVideos = new Set(videos.map((v) => v.video_id)).size;
  const channels = new Set(videos.map((v) => v.channel)).size;
  return {
    status: meta?.status ?? "unknown",
    lastScan: meta?.last_scan ?? null,
    lastVideoDiscovery: meta?.last_video_discovery ?? null,
    filmsAnalyzed: meta?.all_films_analyzed?.length ?? 0,
    filmsOnRadar: meta?.movie_catalog?.length ?? 0,
    videosMonitored: uniqueVideos,
    channelsTracked: channels,
    storedComments: comments.length,
    keepHistoryDays: meta?.keep_history_days ?? null,
  };
}
