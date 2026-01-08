import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const query = searchParams.get('query');
  const id = searchParams.get('id');
  const apiKey = process.env.TMDB_API_KEY;

  if (!apiKey) {
    // If no key, return empty to prevent errors, client handles fallback
    return NextResponse.json({ error: 'TMDB_API_KEY not configured' }, { status: 500 });
  }

  try {
    // Scenario 1: Search by query
    if (query) {
      const searchRes = await fetch(
        `https://api.themoviedb.org/3/search/movie?api_key=${apiKey}&query=${encodeURIComponent(query)}&language=en-US&page=1`
      );
      const data = await searchRes.json();
      return NextResponse.json(data);
    }
    
    // Scenario 2: Get details by ID
    if (id) {
       const detailRes = await fetch(
        `https://api.themoviedb.org/3/movie/${id}?api_key=${apiKey}`
       );
       const data = await detailRes.json();
       return NextResponse.json(data);
    }

    return NextResponse.json({ error: 'Invalid parameters' }, { status: 400 });

  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch metadata' }, { status: 500 });
  }
}