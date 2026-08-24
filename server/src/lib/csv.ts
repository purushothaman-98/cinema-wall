import { readFileSync, statSync } from "node:fs";
import { parse } from "csv-parse/sync";

const BOOL_TRUE = new Set(["true", "1", "yes"]);
const NUMERIC_HINT = /^-?\d+(\.\d+)?$/;

/**
 * Turns whatever csv-parse handed back into something JS-shaped:
 * "True"/"False" -> boolean, numeric-looking strings -> number,
 * empty string -> "" (kept, callers decide their own defaults).
 */
function coerceValue(raw: string): string | number | boolean {
  if (raw === "") return "";
  const lower = raw.toLowerCase();
  if (lower === "true" || lower === "false") return BOOL_TRUE.has(lower);
  if (NUMERIC_HINT.test(raw)) {
    const n = Number(raw);
    if (Number.isFinite(n)) return n;
  }
  return raw;
}

function coerceRow<T>(row: Record<string, string>): T {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(row)) {
    out[key] = coerceValue(value);
  }
  return out as T;
}

interface CacheEntry<T> {
  mtimeMs: number;
  rows: T[];
}

const cache = new Map<string, CacheEntry<unknown>>();

/**
 * Loads a CSV file into typed rows, re-parsing only when the file's mtime
 * changes. Pass `omit` for columns nothing downstream reads — e.g. a raw
 * YouTube video `description` repeated across every 30-minute snapshot of
 * the same video for weeks. csv-parse drops those columns while parsing
 * (via a per-column `undefined` definition), so the unwanted text is never
 * materialized into a retained string at all, not even transiently — this
 * is what keeps a many-year retained-history CSV parseable in a few
 * hundred MB of heap instead of ballooning to gigabytes.
 */
export function loadCsv<T>(filePath: string, options: { omit?: string[] } = {}): T[] {
  let mtimeMs: number;
  try {
    mtimeMs = statSync(filePath).mtimeMs;
  } catch {
    return [];
  }
  const hit = cache.get(filePath) as CacheEntry<T> | undefined;
  if (hit && hit.mtimeMs === mtimeMs) return hit.rows;

  const omit = options.omit;
  const text = readFileSync(filePath, "utf-8");
  const records = parse(text, {
    columns: omit && omit.length > 0 ? (header: string[]) => header.map((h) => (omit.includes(h) ? undefined : h)) : true,
    skip_empty_lines: true,
    relax_column_count: true,
    bom: true,
  }) as Record<string, string>[];
  const rows = records.map((record) => coerceRow<T>(record));
  cache.set(filePath, { mtimeMs, rows });
  return rows;
}

export function loadJson<T>(filePath: string): T | null {
  let mtimeMs: number;
  try {
    mtimeMs = statSync(filePath).mtimeMs;
  } catch {
    return null;
  }
  const cacheKey = `json:${filePath}`;
  const hit = cache.get(cacheKey) as CacheEntry<T> | undefined;
  if (hit && hit.mtimeMs === mtimeMs) return hit.rows[0] ?? null;

  const text = readFileSync(filePath, "utf-8");
  const data = JSON.parse(text) as T;
  cache.set(cacheKey, { mtimeMs, rows: [data] });
  return data;
}
