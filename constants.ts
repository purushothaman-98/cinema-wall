// Explicit access is required for Next.js to replace variables at build time.
// Dynamic access (process.env[key]) returns undefined in the browser.

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

export const DEFAULT_POSTER = "https://picsum.photos/300/450?grayscale&blur=2";

export const SCORE_COLORS = {
  high: "text-green-500",
  medium: "text-yellow-500",
  low: "text-red-500",
};

export const TMDB_BASE_URL = "https://image.tmdb.org/t/p/w500";