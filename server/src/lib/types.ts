// Raw row shapes, as they exist in the CSVs written by scanner.py.
// Every field arrives from csv-parse as a string; numeric/boolean/date
// coercion happens in store.ts.

export interface CommentRow {
  film: string;
  platform: string;
  source: string;
  text: string;
  created_at: string;
  likes: number;
  author: string;
  url: string;
  source_id: string;
  content_type: string;
  parent_id: string;
  scanned_at: string;
  language: string;
  low_information: boolean;
  channel: string;
  video_id: string;
  video_title: string;
  updated_at: string;
  reply_count: number;
  word_count: number;
  topic: string;
  comment_kind: string;
  is_question: boolean;
  analysis_status: string;
  content_format: string;
  reaction_signal: string;
  promotional_flag: boolean;
  scam_risk: string;
  context_signals: string;
  possible_sarcasm: boolean;
  sarcasm_cues: string;
  audience_value: string;
  source_category: string;
  video_intent: string;
}

export interface VideoSnapshotRow {
  video_id: string;
  channel: string;
  title: string;
  published_at: string;
  views: number;
  likes: number;
  comments: number;
  signal_score: number;
  trusted_channel: boolean;
  promotional: boolean;
  film: string;
  scanned_at: string;
  channel_id: string;
  thumbnail_url: string;
  content_format: string;
  source_category: string;
  source_profile: string;
  video_intent: string;
  review_evidence: boolean;
}

export interface ChannelEvaluationRow {
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

export interface TopChannelCoverageRow {
  film: string;
  channel: string;
  channel_rank: number;
  channel_id: string;
  source_category: string;
  status: string;
  top_channels_present_for_film: number;
  top_channels_total: number;
  tracked_review_videos: number;
  stored_comments: number;
  latest_published_at: string;
  latest_scanned_at: string;
  retry_priority: string;
  note: string;
}

export interface CatalogFilm {
  title: string;
  original_title?: string;
  release_date?: string;
  poster_url?: string;
  backdrop_url?: string;
  tmdb_id?: number;
  overview?: string;
  runtime?: number;
  genres?: string[];
  director?: string;
  cast?: string[];
}

export interface FilmInsightAspect {
  name: string;
  comments: number;
}

export interface FilmInsightReviewer {
  channel: string;
  useful_comments: number;
  appreciative_signals: number;
  critical_signals: number;
}

export interface FilmInsight {
  summary: string;
  useful_comments: number;
  explicit_reaction_comments: number;
  appreciative_signals: number;
  critical_signals: number;
  substantive_share: number;
  top_aspects: FilmInsightAspect[];
  reviewers: FilmInsightReviewer[];
}

export interface ScanMetadata {
  status: string;
  last_scan: string;
  last_video_discovery: string;
  scan_interval_minutes: number;
  keep_history_days: number;
  films: string[];
  movie_catalog: CatalogFilm[];
  movie_catalog_history: CatalogFilm[];
  all_films_analyzed: string[];
  film_insights: Record<string, FilmInsight>;
  stored_comments: number;
  videos_monitored: number;
  standard_videos_monitored: number;
  shorts_monitored: number;
  [key: string]: unknown;
}
