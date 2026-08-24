import path from "node:path";
import { fileURLToPath } from "node:url";

// server/src/lib/paths.ts -> repo/data/live
// (dist/lib/paths.js sits one level deeper than src/lib, but both are two
// directories under server/, so the relative path up to the repo root is the same)
const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(HERE, "../../../");
export const DATA_DIR = path.join(REPO_ROOT, "data", "live");

export const FILES = {
  comments: path.join(DATA_DIR, "comments.csv"),
  videoSnapshots: path.join(DATA_DIR, "video_snapshots.csv"),
  channelEvaluation: path.join(DATA_DIR, "channel_evaluation.csv"),
  topChannelCoverage: path.join(DATA_DIR, "top_channel_coverage.csv"),
  metadata: path.join(DATA_DIR, "scan_metadata.json"),
} as const;
