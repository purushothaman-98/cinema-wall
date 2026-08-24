const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export type Trend = "rising" | "cooling" | "flat" | "insufficient-data";

export interface Momentum {
  viewsPerHour: number;
  commentsPerHour: number;
  windowMinutes: number;
  trend: Trend;
  asOf: string | null;
  stale: boolean;
}

export interface EvidenceScore {
  score: number;
  label: "Strong evidence" | "Useful evidence" | "Thin evidence" | "Awaiting evidence";
}

export interface ReactionTone {
  appreciative: number;
  critical: number;
  mixed: number;
  sampleSize: number;
}

export interface MixEntry {
  label: string;
  count: number;
  pct: number;
}

export interface FilmListItem {
  film: string;
  onRadar: boolean;
  poster: string | null;
  releaseDate: string | null;
  genres: string[];
  director: string | null;
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
  summary: string | null;
}

export interface TimeseriesPoint {
  t: string;
  views: number;
  likes: number;
  comments: number;
  standardViews: number;
  shortViews: number;
}

export interface CommentComposition {
  totalComments: number;
  usefulComments: number;
  languageMix: MixEntry[];
  topicMix: MixEntry[];
  commentKindMix: MixEntry[];
  reactionTone: ReactionTone;
  discussionDepthPct: number;
  historicalComparisonPct: number;
  contemporaryReferencePct: number;
  sarcasmPct: number;
  promotionalFiltered: number;
  scamFlags: number;
}

export interface CoverageGrade {
  present: number;
  total: number;
  pct: number;
  channels: { channel: string; status: string; rank: number }[];
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

export interface FilmInsight {
  summary: string;
  useful_comments: number;
  explicit_reaction_comments: number;
  appreciative_signals: number;
  critical_signals: number;
  substantive_share: number;
  top_aspects: { name: string; comments: number }[];
  reviewers: { channel: string; useful_comments: number; appreciative_signals: number; critical_signals: number }[];
}

export interface CatalogEntry {
  title: string;
  original_title?: string;
  release_date?: string;
  poster_url?: string;
  backdrop_url?: string;
  overview?: string;
  runtime?: number;
  genres?: string[];
  director?: string;
  cast?: string[];
  onRadar: boolean;
}

export interface VideoRow {
  videoId: string;
  channel: string;
  title: string;
  publishedAt: string;
  views: number;
  likes: number;
  comments: number;
  contentFormat: "Video" | "Short";
  sourceCategory: string;
  sourceProfile: string;
  videoIntent: string;
  thumbnailUrl: string;
}

export interface FilmDetail {
  film: string;
  catalog: CatalogEntry | null;
  insight: FilmInsight | null;
  momentum: Momentum;
  evidence: EvidenceScore;
  timeseries: TimeseriesPoint[];
  composition: CommentComposition;
  coverage: CoverageGrade;
  evidenceSample: CommentSample[];
  videos: VideoRow[];
}

export interface ChannelRow {
  channel: string;
  source_profile: string;
  source_category: string;
  films_covered: number;
  items_tracked: number;
  full_videos: number;
  shorts: number;
  review_discussion_items: number;
  context_items: number;
  review_share_pct: number;
  stored_comments: number;
  useful_comments: number;
  useful_share_pct: number;
  questions: number;
  public_comments: number;
  views: number;
  comments_per_item: number;
  tracker_value: number;
}

export interface OverviewTotals {
  status: string;
  lastScan: string | null;
  lastVideoDiscovery: string | null;
  filmsAnalyzed: number;
  filmsOnRadar: number;
  videosMonitored: number;
  channelsTracked: number;
  storedComments: number;
  keepHistoryDays: number | null;
}

export interface TrendingFilm {
  film: string;
  poster: string | null;
  viewsPerHour: number;
  commentsPerHour: number;
  trend: Trend;
  latestViews: number;
  evidence: EvidenceScore;
}

export interface HeatmapCell {
  day: number;
  hour: number;
  count: number;
}

export interface Overview {
  totals: OverviewTotals;
  trending: TrendingFilm[];
  strongestEvidence: { film: string; score: number; label: string; storedComments: number }[];
  languageMix: MixEntry[];
  topicMix: MixEntry[];
  commentKindMix: MixEntry[];
  reactionTone: ReactionTone;
  arrivalHeatmap: HeatmapCell[];
  historicalComparisonSpotlight: { film: string; pct: number; sampleSize: number }[];
  contemporaryReferenceSpotlight: { film: string; pct: number; sampleSize: number }[];
  discussionDepthLeaders: { film: string; depthPct: number; usefulComments: number }[];
  topChannels: ChannelRow[];
}

export const api = {
  overview: () => get<Overview>("/overview"),
  films: (radarOnly = false) => get<FilmListItem[]>(`/films${radarOnly ? "?radar=true" : ""}`),
  film: (name: string) => get<FilmDetail>(`/films/${encodeURIComponent(name)}`),
  channels: () => get<ChannelRow[]>("/channels"),
};
