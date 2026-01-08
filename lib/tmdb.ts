import { MovieMetadata } from '../types';

export async function fetchMovieMetadata(query: string): Promise<MovieMetadata | undefined> {
  try {
    // We now fetch from our own internal API route (/api/metadata)
    // This keeps the TMDB_API_KEY hidden on the server side.
    // Relative URL works automatically in the browser.
    const searchRes = await fetch(`/api/metadata?query=${encodeURIComponent(query)}`);
    
    if (!searchRes.ok) return undefined;
    
    const searchData = await searchRes.json();
    const firstResult = searchData.results?.[0];

    if (!firstResult) return undefined;

    // Fetch details for runtime/genres via internal proxy
    const detailRes = await fetch(`/api/metadata?id=${firstResult.id}`);
    
    if(!detailRes.ok) {
        // Fallback to basic info if detail fetch fails
        return {
            poster_path: firstResult.poster_path,
            release_date: firstResult.release_date,
            overview: firstResult.overview,
            backdrop_path: firstResult.backdrop_path,
            vote_average: firstResult.vote_average
        }
    }

    const details = await detailRes.json();
    return {
      poster_path: details.poster_path,
      release_date: details.release_date,
      overview: details.overview,
      backdrop_path: details.backdrop_path,
      vote_average: details.vote_average,
      genres: details.genres,
      runtime: details.runtime
    };

  } catch (error) {
    console.warn("Metadata Fetch Warning:", error);
    return undefined;
  }
}