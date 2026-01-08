// Helper to safely access env vars in various environments
const getEnv = (key: string) => {
  try {
    if (typeof process !== 'undefined' && process.env) {
      return process.env[key];
    }
  } catch (e) {
    // Ignore reference errors
  }
  // Fallback for some client-side bundlers
  try {
    // @ts-ignore
    if (typeof import.meta !== 'undefined' && import.meta.env) {
      // @ts-ignore
      return import.meta.env[key];
    }
  } catch (e) {}
  return undefined;
};

export const SUPABASE_URL = getEnv('NEXT_PUBLIC_SUPABASE_URL') || 'https://placeholder.supabase.co';
export const SUPABASE_ANON_KEY = getEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY') || 'placeholder';

export const DEFAULT_POSTER = "https://picsum.photos/300/450?grayscale&blur=2";

export const SCORE_COLORS = {
  high: "text-green-500",
  medium: "text-yellow-500",
  low: "text-red-500",
};

export const TMDB_BASE_URL = "https://image.tmdb.org/t/p/w500";