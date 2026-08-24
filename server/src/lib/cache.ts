import { statSync } from "node:fs";
import { FILES } from "./paths.js";

/**
 * A cheap fingerprint of every data file's mtime+size. On a real deploy the
 * CSVs are static for the life of the process (data.yaml disables
 * auto-deploy; a fresh copy only ever arrives via a new build), so this
 * fingerprint never changes and everything keyed on it computes exactly
 * once. In local dev, where the scanner can update these files while the
 * server is running, a changed fingerprint correctly invalidates the cache.
 */
function dataFingerprint(): string {
  return Object.values(FILES)
    .map((file) => {
      try {
        const stat = statSync(file);
        return `${file}:${stat.mtimeMs}:${stat.size}`;
      } catch {
        return `${file}:missing`;
      }
    })
    .join("|");
}

const store = new Map<string, { fingerprint: string; value: unknown }>();

/**
 * Memoizes an expensive derived computation (grouping/scoring across every
 * film) against the current data fingerprint, so repeat requests — health
 * checks, page reloads, multiple visitors — hit a cache instead of
 * re-deriving everything from the raw CSV rows every single time.
 */
export function cached<T>(key: string, compute: () => T): T {
  const fingerprint = dataFingerprint();
  const hit = store.get(key);
  if (hit && hit.fingerprint === fingerprint) return hit.value as T;
  const value = compute();
  store.set(key, { fingerprint, value });
  return value;
}
