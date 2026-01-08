
'use client';

import React, { useState, useEffect, useRef } from 'react';
import Navbar from './components/Navbar';
import { supabase } from './lib/supabase';
import { aggregateScans } from './lib/aggregate';
import { MovieAggregate, Scan, NewsItem, VaultItem } from './types';
import MovieCard from './components/MovieCard';
import ReviewerCard from './components/ReviewerCard';
import { DEFAULT_POSTER, TMDB_BASE_URL } from './constants';
import { unslugify, getScoreColor, formatDate } from './lib/utils';

// --- PAGE COMPONENTS ---

// 1. HOME PAGE
const HomePage = () => {
  const [movies, setMovies] = useState<MovieAggregate[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [filter, setFilter] = useState('trending');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setErrorMsg(null);
      try {
          // Fetch last 1000 scans to aggregate
          const { data, error } = await supabase
            .from('scans')
            .select('*')
            .order('created_at', { ascending: false })
            .limit(1000); 

          if (error) {
            console.error("Supabase Error:", error);
            throw error;
          }

          if (data) {
            // Client-side aggregation
            const agg = await aggregateScans(data as Scan[], false);
            setMovies(agg);
          }
      } catch (err: any) {
          setErrorMsg(err.message || "Failed to load data. Please check connection.");
      } finally {
          setLoading(false);
      }
    };
    loadData();
  }, []);

  const filteredMovies = movies
    .filter(m => m.subject_name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
        if (filter === 'latest') return new Date(b.last_scanned).getTime() - new Date(a.last_scanned).getTime();
        if (filter === 'az') return a.subject_name.localeCompare(b.subject_name);
        return b.reviewers_count - a.reviewers_count;
    });

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Controls */}
      <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
        <h1 className="text-3xl font-bold text-white border-l-4 border-primary pl-4">The Wall</h1>
        
        <div className="flex gap-2 w-full md:w-auto">
            <input 
                type="text"
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="bg-surface border border-slate-700 rounded px-3 py-2 text-white w-full md:w-64 focus:border-primary focus:outline-none"
            />
            <select 
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-surface border border-slate-700 rounded px-3 py-2 text-white focus:border-primary focus:outline-none"
            >
                <option value="trending">Trending</option>
                <option value="latest">Latest</option>
                <option value="az">A-Z</option>
            </select>
        </div>
      </div>

      {loading ? (
         <div className="flex justify-center py-20">
             <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
         </div>
      ) : errorMsg ? (
        <div className="text-center py-20 bg-red-900/20 border border-red-500/50 rounded-lg p-6">
            <h3 className="text-xl text-red-400 font-bold mb-2">Connection Error</h3>
            <p className="text-gray-300">{errorMsg}</p>
            <p className="text-sm text-gray-500 mt-4">Note: If this is a new deployment, ensure Environment Variables are set in Vercel.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {filteredMovies.map(movie => (
                <MovieCard key={movie.subject_name} movie={movie} />
            ))}
            {filteredMovies.length === 0 && (
                <div className="col-span-full text-center text-gray-500 py-20">
                    No movies found.
                </div>
            )}
        </div>
      )}
    </div>
  );
};

// 2. DETAIL PAGE
interface AnalysisReport {
    tagline?: string;
    summary?: string;
    critics_vs_audience?: string;
    conflict_points?: string;
    comment_vibe?: string;
}

const MovieDetail = ({ slug }: { slug: string }) => {
  const subjectName = unslugify(slug);
  const [movie, setMovie] = useState<MovieAggregate | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiSummary, setAiSummary] = useState<AnalysisReport | null>(null);
  const [generating, setGenerating] = useState(false);
  const attemptRef = useRef(false);

  // 1. Load Movie Data
  useEffect(() => {
    const loadDetail = async () => {
        setLoading(true);
        const { data } = await supabase
            .from('scans')
            .select('*')
            .ilike('subject_name', subjectName);

        if (data && data.length > 0) {
            const aggs = await aggregateScans(data as Scan[], true);
            if (aggs.length > 0) setMovie(aggs[0]);
        }
        setLoading(false);
    };
    loadDetail();
  }, [subjectName]);

  // 2. Auto-Check Vault & Auto-Generate
  useEffect(() => {
    if (!movie || attemptRef.current) return;
    
    const checkVault = async () => {
        attemptRef.current = true; // Prevent double firing
        
        // Try to find in vault
        const { data: vaultData } = await supabase
            .from('memory_vault')
            .select('*')
            .eq('movie_name', movie.subject_name)
            .maybeSingle();

        if (vaultData) {
            // Found existing analysis
            try {
                let report = typeof vaultData.summary_report === 'string' 
                    ? JSON.parse(vaultData.summary_report) 
                    : vaultData.summary_report;
                
                // Validate report content (basic check)
                if (!report || typeof report !== 'object' || !report.summary) {
                   generateConsensus(movie);
                } else {
                   setAiSummary(report);
                }
            } catch (e) {
                console.error("Failed to parse vault report, regenerating...", e);
                generateConsensus(movie);
            }
        } else {
            // Not found, trigger auto-analysis
            generateConsensus(movie);
        }
    };
    checkVault();
  }, [movie]);

  const generateConsensus = async (targetMovie: MovieAggregate) => {
    setGenerating(true);
    setAiSummary(null);
    
    // OPTIMIZATION: Reduce payload to save tokens
    const body = {
        movie: targetMovie.subject_name,
        topics: targetMovie.top_topics,
        sentiments: {
            critics: targetMovie.critics_score,
            audience: targetMovie.audience_score
        },
        reviews: targetMovie.scans
            .slice(0, 8) // Limit to 8 relevant reviews
            .map(s => ({ 
                title: s.reviewer_name, 
                // Truncate snippet to 300 chars to save tokens
                snippet: (s.result?.summary || s.result?.sentimentDescription || s.title).substring(0, 300) 
            }))
    };

    try {
        const res = await fetch('/api/summarize', {
            method: 'POST',
            body: JSON.stringify(body),
        });
        
        if (res.ok) {
            const data = await res.json();
            setAiSummary(data);
            
            // Auto Save to Vault ONLY on success
            await supabase.from('memory_vault').upsert({
                movie_name: targetMovie.subject_name,
                summary_report: JSON.stringify(data)
            }, { onConflict: 'movie_name' });
        } else {
             console.warn("AI Generation failed");
             setAiSummary({ tagline: "Analysis Delayed", summary: "The system is currently maximizing resource usage. Please retry shortly." });
        }
    } catch (e) {
        console.error("Generation Error", e);
        setAiSummary({ tagline: "Network Error", summary: "Could not reach the analysis engine." });
    } finally {
        setGenerating(false);
    }
  };

  if (loading) return <div className="text-center py-20 text-primary">Loading Movie Details...</div>;
  if (!movie) return <div className="text-center py-20 text-red-500">Movie not found.</div>;

  const isPending = aiSummary?.tagline === "Analysis Delayed" || aiSummary?.tagline === "Network Error" || !aiSummary;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
        <a href="#/" className="text-secondary hover:text-white mb-6 inline-block">&larr; Back to Wall</a>
        <div className="grid md:grid-cols-3 gap-8">
            <div className="md:col-span-1 space-y-6">
                <div className="rounded-lg overflow-hidden border border-slate-700 shadow-2xl relative group bg-slate-800">
                    <img src={movie.poster_url} alt={movie.subject_name} className="w-full" />
                </div>
                <div className="bg-surface p-4 rounded-lg border border-slate-700">
                    <h3 className="text-gray-400 text-sm uppercase tracking-widest font-bold mb-4">Scores</h3>
                    <div className="flex justify-around text-center">
                        <div>
                            <div className={`text-4xl font-bold ${getScoreColor(movie.critics_score)}`}>{movie.critics_score}</div>
                            <div className="text-xs text-gray-500 mt-1">Critics</div>
                        </div>
                        <div className="w-px bg-slate-700"></div>
                        <div>
                            <div className={`text-4xl font-bold ${getScoreColor(movie.audience_score)}`}>
                                {movie.audience_score > 0 ? `${movie.audience_score}%` : 'N/A'}
                            </div>
                            <div className="text-xs text-gray-500 mt-1">Audience</div>
                        </div>
                    </div>
                </div>
                <div className="bg-surface p-4 rounded-lg border border-slate-700">
                     <h3 className="text-gray-400 text-sm uppercase tracking-widest font-bold mb-2">Details</h3>
                     <p className="text-sm text-gray-300"><span className="text-gray-500">Released:</span> {movie.metadata?.release_date || 'Unknown'}</p>
                     <div className="flex flex-wrap gap-2 mt-3">
                        {movie.metadata?.genres?.map(g => (
                            <span key={g.id} className="text-xs bg-slate-800 text-gray-300 px-2 py-1 rounded">{g.name}</span>
                        ))}
                     </div>
                </div>
            </div>
            <div className="md:col-span-2 space-y-8">
                <div>
                    <h1 className="text-4xl font-bold text-white mb-2">{movie.subject_name}</h1>
                </div>
                
                {/* AI Consensus Block */}
                <div className="bg-gradient-to-br from-slate-900 to-slate-800 border border-primary/30 p-6 rounded-xl relative overflow-hidden shadow-lg shadow-primary/5">
                     <div className="absolute top-0 right-0 p-4 opacity-10">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-24 w-24 text-primary" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
                        </svg>
                    </div>
                    
                    <div className="flex justify-between items-start">
                        <h2 className="text-xl font-bold text-primary mb-4 flex items-center gap-2">
                            AI Consensus Protocol
                            {generating && <span className="text-xs text-gray-400 animate-pulse font-normal">(Analyzing Data...)</span>}
                        </h2>
                        {!generating && (
                             <button onClick={() => generateConsensus(movie)} className="text-xs border border-primary text-primary px-3 py-1 rounded hover:bg-primary hover:text-black">
                                {isPending ? 'Retry Analysis' : 'Refresh'}
                             </button>
                        )}
                    </div>
                    
                    {!aiSummary && !generating ? (
                        <div className="text-center py-8">
                           <p className="text-gray-500 italic">Initializing automated analysis...</p>
                        </div>
                    ) : aiSummary ? (
                        <div className="animate-in fade-in duration-500 relative z-10 space-y-6">
                            
                            {/* Header */}
                            <div>
                                <p className="text-2xl font-serif text-white italic mb-2 leading-relaxed">"{aiSummary.tagline || 'Pending...'}"</p>
                                <p className="text-gray-300 leading-relaxed text-lg">{aiSummary.summary || 'Summary unavailable.'}</p>
                            </div>

                            {/* Deep Analysis Grid */}
                            {!isPending && (
                                <div className="grid md:grid-cols-2 gap-4 pt-4 border-t border-slate-700/50">
                                    <div className="bg-black/20 p-3 rounded">
                                        <h4 className="text-xs font-bold text-secondary uppercase mb-1">Critics vs Audience</h4>
                                        <p className="text-sm text-gray-300">{aiSummary.critics_vs_audience || "Consensus aligned."}</p>
                                    </div>
                                    <div className="bg-black/20 p-3 rounded">
                                        <h4 className="text-xs font-bold text-secondary uppercase mb-1">Conflict Matrix</h4>
                                        <p className="text-sm text-gray-300">{aiSummary.conflict_points || "No major disagreements."}</p>
                                    </div>
                                    <div className="md:col-span-2 bg-black/20 p-3 rounded flex items-center justify-between">
                                        <span className="text-xs font-bold text-secondary uppercase">Comment Section Vibe:</span>
                                        <span className="text-sm font-mono text-primary">{aiSummary.comment_vibe || "Neutral"}</span>
                                    </div>
                                </div>
                            )}

                            {!isPending && (
                                <div className="flex items-center gap-2 mt-2">
                                    <span className="text-[10px] text-green-400 font-mono tracking-widest border border-green-900 bg-green-900/20 px-2 py-0.5 rounded">● ARCHIVED IN VAULT</span>
                                </div>
                            )}
                        </div>
                    ) : (
                         <div className="py-8 space-y-3">
                             <div className="h-4 bg-slate-700/50 rounded w-3/4 animate-pulse"></div>
                             <div className="h-4 bg-slate-700/50 rounded w-full animate-pulse"></div>
                             <div className="h-4 bg-slate-700/50 rounded w-5/6 animate-pulse"></div>
                         </div>
                    )}
                </div>

                <div>
                    <h3 className="text-xl font-bold text-white mb-4 border-b border-slate-700 pb-2">Analyst Breakdown</h3>
                    <div className="space-y-4">
                        {movie.scans.map(scan => <ReviewerCard key={scan.id} scan={scan} />)}
                    </div>
                </div>
            </div>
        </div>
    </div>
  );
};

// 3. VAULT PAGE
const VaultPage = () => {
  const [items, setItems] = useState<VaultItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVault = async () => {
        const {data, error} = await supabase.from('memory_vault').select('*').order('created_at', { ascending: false });
        if(data) setItems(data as unknown as VaultItem[]);
        setLoading(false);
    }
    fetchVault();
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-white mb-8 border-l-4 border-primary pl-4">Memory Vault</h1>
        
        {loading ? (
             <div className="text-center text-gray-500 py-10">Accessing archives...</div>
        ) : (
            <div className="grid gap-4">
                {items.map(item => {
                    let report: any = null;
                    try {
                        if (!item.summary_report) {
                            report = null;
                        } else if (typeof item.summary_report === 'string') {
                            report = JSON.parse(item.summary_report);
                        } else {
                            report = item.summary_report;
                        }
                    } catch(e) { 
                        report = { tagline: "Error parsing report", summary: "Data corruption detected." }; 
                    }
                    
                    const safeReport = report || { tagline: "Processing...", summary: "Analysis is queued or unavailable." };
                    const isError = safeReport.tagline === "Analysis Delayed" || safeReport.tagline === "Network Error";

                    if (isError) return null; // Don't show failed attempts in Vault

                    return (
                        <div key={item.id} className="bg-surface p-6 rounded-lg border border-slate-700 hover:border-slate-500 transition-colors">
                            <div className="flex justify-between items-start mb-2">
                                <h2 className="text-xl font-bold text-white">{item.movie_name}</h2>
                                <span className="text-xs text-gray-500">{formatDate(item.created_at)}</span>
                            </div>
                            <p className="text-primary italic text-lg font-serif mb-3">"{safeReport.tagline || 'Pending...'}"</p>
                            <p className="text-gray-400 text-sm line-clamp-2">{safeReport.summary || 'Summary unavailable.'}</p>
                            
                            {safeReport.critics_vs_audience && (
                                <div className="mt-3 text-xs text-gray-500 bg-black/20 p-2 rounded">
                                   <span className="font-bold">Consensus Gap:</span> {safeReport.critics_vs_audience}
                                </div>
                            )}

                            <div className="mt-4 pt-4 border-t border-slate-800 text-right">
                                <a href={`#/movie/${item.movie_name.toLowerCase().replace(/\s+/g, '-')}`} className="text-xs text-white bg-slate-700 px-3 py-1 rounded hover:bg-slate-600">
                                    View Full Analysis
                                </a>
                            </div>
                        </div>
                    );
                })}
                {items.length === 0 && <div className="text-gray-500 text-center py-20 bg-surface rounded">Vault is empty. Visit a movie page to generate analysis.</div>}
            </div>
        )}
    </div>
  );
};

// 4. NEWS PAGE
const NewsPage = () => {
    const [news, setNews] = useState<NewsItem[]>([]);
    useEffect(() => {
        supabase.from('cinema_news').select('*').order('created_at', { ascending: false }).limit(20).then(({data}) => {
            if(data) setNews(data as NewsItem[]);
        });
    }, []);
    return (
        <div className="max-w-4xl mx-auto px-4 py-8">
            <h1 className="text-3xl font-bold text-white mb-8 border-l-4 border-primary pl-4">Cinema News</h1>
            <div className="space-y-6">
                {news.map(item => (
                    <div key={item.id} className="bg-surface p-6 rounded-lg border border-slate-700">
                        <h2 className="text-xl font-bold text-white mb-2">{item.title}</h2>
                        <p className="text-gray-400 mb-4">{item.content}</p>
                        {item.url && <a href={item.url} target="_blank" className="text-primary text-sm hover:underline">Read Source &rarr;</a>}
                    </div>
                ))}
                {news.length === 0 && <div className="text-center py-20 bg-surface rounded-lg border border-slate-700">No News Yet</div>}
            </div>
        </div>
    );
};

// MAIN ROUTER
const App = () => {
  const [route, setRoute] = useState('#/');

  useEffect(() => {
    setRoute(window.location.hash || '#/');
    const handleHashChange = () => setRoute(window.location.hash || '#/');
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  let Component: React.ElementType = HomePage;
  let params: any = {};

  if (route.startsWith('#/movie/')) {
    Component = MovieDetail;
    params = { slug: route.replace('#/movie/', '') };
  } else if (route === '#/vault') {
    Component = VaultPage;
  } else if (route === '#/news') {
    Component = NewsPage;
  }

  return (
    <div className="min-h-screen bg-background text-white font-sans selection:bg-primary selection:text-black">
      <Navbar />
      <main>
        <Component {...params} />
      </main>
      <footer className="border-t border-slate-800 mt-20 py-8 text-center text-gray-600 text-sm">
        <p>&copy; {new Date().getFullYear()} Cinema Wall.</p>
      </footer>
    </div>
  );
};

export default App;
