import { MovieMetadata } from '../types';

const getApiKey = () => {
  try {
    if (typeof process !== 'undefined' && process.env) {
      return process.env.TMDB_API_KEY;
    }
  } catch (e) {}
  return undefined;
};

const API_KEY = getApiKey();

export async function fetchMovieMetadata(query: string): Promise<MovieMetadata | undefined> {
  if (!API_KEY) return undefined;

  try {
    const searchRes = await fetch(
      `https://api.themoviedb.org/3/search/movie?api_key=${API_KEY}&query=${encodeURIComponent(query)}&language=en-US&page=1`
    );
    
    if (!searchRes.ok) return undefined;
    
    const searchData = await searchRes.json();
    const firstResult = searchData.results?.[0];

    if (!firstResult) return undefined;

    // Fetch details for runtime/genres
    const detailRes = await fetch(
        `https://api.themoviedb.org/3/movie/${firstResult.id}?api_key=${API_KEY}`
    );
    
    if(!detailRes.ok) {
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
    console.error("TMDB Fetch Error:", error);
    return undefined;
  }
}