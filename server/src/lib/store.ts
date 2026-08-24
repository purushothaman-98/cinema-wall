import { statSync } from "node:fs";
import { loadCsv, loadJson } from "./csv.js";
import { FILES } from "./paths.js";
import type {
  ChannelEvaluationRow,
  CommentRow,
  ScanMetadata,
  TopChannelCoverageRow,
  VideoSnapshotRow,
} from "./types.js";

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : value == null ? fallback : String(value);
}
function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
function bool(value: unknown): boolean {
  return value === true;
}

/**
 * Every getX() below maps loadCsv()'s raw rows into a typed shape. loadCsv
 * already caches the raw parse by mtime, but without this, each *call* to
 * getX() still re-ran that .map() over the full file — and insights.ts
 * calls these several times while building one response, multiplying an
 * already-large in-memory copy of ~83K/18K rows each time. Memoize the
 * mapped result per file too, so it's built once per data version.
 */
function cachedByMtime<T>(file: string, build: () => T): () => T {
  let mtimeMs = -1;
  let value: T | undefined;
  return () => {
    let current: number;
    try {
      current = statSync(file).mtimeMs;
    } catch {
      current = -1;
    }
    if (value === undefined || current !== mtimeMs) {
      value = build();
      mtimeMs = current;
    }
    return value;
  };
}

export const getComments = cachedByMtime(FILES.comments, () =>
  loadCsv<Record<string, unknown>>(FILES.comments).map(
    (row): CommentRow => ({
      film: str(row.film, "Unknown"),
      platform: str(row.platform),
      source: str(row.source),
      text: str(row.text),
      created_at: str(row.created_at),
      likes: num(row.likes),
      author: str(row.author),
      url: str(row.url),
      source_id: str(row.source_id),
      content_type: str(row.content_type),
      parent_id: str(row.parent_id),
      scanned_at: str(row.scanned_at),
      language: str(row.language, "English / other"),
      low_information: bool(row.low_information),
      channel: str(row.channel, "Unknown"),
      video_id: str(row.video_id),
      video_title: str(row.video_title),
      updated_at: str(row.updated_at),
      reply_count: num(row.reply_count),
      word_count: num(row.word_count),
      topic: str(row.topic, "General reaction"),
      comment_kind: str(row.comment_kind, "Quick reaction"),
      is_question: bool(row.is_question),
      analysis_status: str(row.analysis_status),
      content_format: str(row.content_format, "Video"),
      reaction_signal: str(row.reaction_signal, "Mixed / unclear"),
      promotional_flag: bool(row.promotional_flag),
      scam_risk: str(row.scam_risk, "Low"),
      context_signals: str(row.context_signals),
      possible_sarcasm: bool(row.possible_sarcasm),
      sarcasm_cues: str(row.sarcasm_cues),
      audience_value: str(row.audience_value),
      source_category: str(row.source_category, "open_youtube"),
      video_intent: str(row.video_intent),
    }),
  ),
);

export const getVideoSnapshots = cachedByMtime(FILES.videoSnapshots, () =>
  // description/duration are parsed by scanner.py but nothing here reads them — they're also the
  // single biggest columns in this file by far (a full video description repeated across every
  // 30-minute snapshot of that video). Omitting them at parse time is what keeps a
  // long-retained-history CSV from blowing well past a free-tier heap ceiling just to load.
  loadCsv<Record<string, unknown>>(FILES.videoSnapshots, { omit: ["description", "duration"] }).map(
    (row): VideoSnapshotRow => ({
      video_id: str(row.video_id),
      channel: str(row.channel, "Unknown"),
      title: str(row.title),
      published_at: str(row.published_at),
      views: num(row.views),
      likes: num(row.likes),
      comments: num(row.comments),
      signal_score: num(row.signal_score),
      trusted_channel: bool(row.trusted_channel),
      promotional: bool(row.promotional),
      film: str(row.film, "Unknown"),
      scanned_at: str(row.scanned_at),
      channel_id: str(row.channel_id),
      thumbnail_url: str(row.thumbnail_url),
      content_format: str(row.content_format, "Video") === "Short" ? "Short" : "Video",
      source_category: str(row.source_category, "open_youtube"),
      source_profile: str(row.source_profile, "Open YouTube"),
      video_intent: str(row.video_intent),
      review_evidence: bool(row.review_evidence),
    }),
  ),
);

export const getChannelEvaluation = cachedByMtime(FILES.channelEvaluation, () =>
  loadCsv<Record<string, unknown>>(FILES.channelEvaluation).map(
    (row): ChannelEvaluationRow => ({
      channel: str(row.channel, "Unknown"),
      source_profile: str(row.source_profile),
      source_category: str(row.source_category, "open_youtube"),
      films_covered: num(row.films_covered),
      items_tracked: num(row.items_tracked),
      full_videos: num(row.full_videos),
      shorts: num(row.shorts),
      review_discussion_items: num(row.review_discussion_items),
      context_items: num(row.context_items),
      review_share_pct: num(row.review_share_pct),
      stored_comments: num(row.stored_comments),
      useful_comments: num(row.useful_comments),
      useful_share_pct: num(row.useful_share_pct),
      questions: num(row.questions),
      public_comments: num(row.public_comments),
      views: num(row.views),
      comments_per_item: num(row.comments_per_item),
      tracker_value: num(row.tracker_value),
    }),
  ),
);

export const getTopChannelCoverage = cachedByMtime(FILES.topChannelCoverage, () =>
  loadCsv<Record<string, unknown>>(FILES.topChannelCoverage).map(
    (row): TopChannelCoverageRow => ({
      film: str(row.film, "Unknown"),
      channel: str(row.channel, "Unknown"),
      channel_rank: num(row.channel_rank),
      channel_id: str(row.channel_id),
      source_category: str(row.source_category),
      status: str(row.status, "missing"),
      top_channels_present_for_film: num(row.top_channels_present_for_film),
      top_channels_total: num(row.top_channels_total),
      tracked_review_videos: num(row.tracked_review_videos),
      stored_comments: num(row.stored_comments),
      latest_published_at: str(row.latest_published_at),
      latest_scanned_at: str(row.latest_scanned_at),
      retry_priority: str(row.retry_priority),
      note: str(row.note),
    }),
  ),
);

export const getMetadata = cachedByMtime(FILES.metadata, () => loadJson<ScanMetadata>(FILES.metadata));
