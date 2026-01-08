
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

// Helper: Robust JSON Parsing for Vault items
const safeParseJSON = (input: any) => {
    if (!input) return null;
    if (typeof input === 'object') return input;
    try {
        const parsed = JSON.parse(input);
        if (typeof parsed === 'string') return JSON.parse(parsed);
        return parsed;
    } catch (e) {
        console.warn("JSON Parse Error:", e);
        return null;
    }
};

// --- PAGE COMPONENTS ---

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
          const { data, error } = await supabase
            .from('scans')
            .select('*')
            .order('created_at', { ascending: false })
            .limit(1000); 

          if (error) throw error;

          if (data) {
            const agg = await aggregateScans(data as Scan[], false);
            setMovies(agg);
          }
      } catch (err: any) {
          setErrorMsg(err.message || "Failed to load data.");
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
      {/* Hero Section */}
      <div className="relative mb-12 p-8 rounded-3xl bg-gradient-to-r from-slate-900 to-slate-800 border border-slate-700/50 overflow-hidden">
          <div className="absolute top-0 right-0 -mt-4 -mr-4 w-32 h-32 bg-primary/10 rounded-full blur-3xl"></div>
          <div className="absolute bottom-0 left-0 -mb-4 -ml-4 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl"></div>
          
          <div className="relative z-10 flex flex-col md:flex-row justify-between items-end gap-6">
              <div>
                  <h1 className="text-4xl md:text-5xl font-extrabold text-white tracking-tight mb-2">
                      <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-yellow-200">INTELLIGENT</span> CINEMA
                  </h1>
                  <p className="text-gray-400 max-w-lg text-lg">
                      AI-aggregated consensus from the web's most trusted critics and comment sections.
                  </p>
              </div>
              
              <div className="flex gap-3 w-full md:w-auto">
                  <div className="relative flex-grow md:flex-grow-0">
                    <input 
                        type="text"
                        placeholder="Find a movie..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full md:w-64 bg-black/30 border border-slate-600 rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none placeholder-gray-500"
                    />
                    <svg className="w-5 h-5 absolute right-3 top-3 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                  </div>
                  <select 
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                      className="bg-black/30 border border-slate-600 rounded-lg px-4 py-3 text-white focus:border-primary focus:outline-none cursor-pointer"
                  >
                      <option value="trending">Trending</option>
                      <option value="latest">Latest</option>
                      <option value="az">A-Z</option>
                  </select>
              </div>
          </div>
      </div>

      {loading ? (
         <div className="flex flex-col items-center justify-center py-32 space-y-4">
             <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
             <p className="text-gray-500 text-sm animate-pulse">Synchronizing Data Streams...</p>
         </div>
      ) : errorMsg ? (
        <div className="text-center py-20 bg-red-950/30 border border-red-500/20 rounded-xl">
            <h3 className="text-red-400 font-bold mb-2">System Offline</h3>
            <p className="text-gray-500 text-sm">{errorMsg}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {filteredMovies.map(movie => (
                <MovieCard key={movie.subject_name} movie={movie} />
            ))}
        </div>
      )}
    </div>
  );
};

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

  useEffect(() => {
    if (!movie || attemptRef.current) return;
    
    const checkVault = async () => {
        attemptRef.current = true;
        const { data: vaultData } = await supabase
            .from('memory_vault')
            .select('*')
            .eq('movie_name', movie.subject_name)
            .maybeSingle();

        if (vaultData) {
            const report = safeParseJSON(vaultData.summary_report);
            if (report && report.summary) {
                setAiSummary(report);
            } else {
                generateConsensus(movie);
            }
        } else {
            generateConsensus(movie);
        }
    };
    checkVault();
  }, [movie]);

  const generateConsensus = async (targetMovie: MovieAggregate) => {
    setGenerating(true);
    setAiSummary(null);
    
    const body = {
        movie: targetMovie.subject_name,
        topics: targetMovie.top_topics,
        sentiments: {
            critics: targetMovie.critics_score,
            audience: targetMovie.audience_score
        },
        reviews: targetMovie.scans.slice(0, 8).map(s => ({ 
            title: s.reviewer_name, 
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
            await supabase.from('memory_vault').upsert({
                movie_name: targetMovie.subject_name,
                summary_report: JSON.stringify(data)
            }, { onConflict: 'movie_name' });
        } else {
             setAiSummary({ tagline: "Analysis Delayed", summary: "Server is busy. Please refresh manually." });
        }
    } catch (e) {
        setAiSummary({ tagline: "Network Error", summary: "Could not connect to AI service." });
    } finally {
        setGenerating(false);
    }
  };

  if (loading) return <div className="text-center py-20 text-primary">Loading...</div>;
  if (!movie) return <div className="text-center py-20 text-red-500">Movie not found.</div>;

  const isPending = aiSummary?.tagline === "Analysis Delayed" || !aiSummary;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
        <a href="#/" className="text-secondary hover:text-white mb-6 inline-flex items-center gap-2 text-sm bg-surface px-3 py-1 rounded-full border border-slate-700">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path></svg>
            Back to Dashboard
        </a>
        
        <div className="grid md:grid-cols-12 gap-8">
            {/* Sidebar */}
            <div className="md:col-span-4 lg:col-span-3 space-y-6">
                <div className="rounded-xl overflow-hidden border border-slate-700 shadow-2xl relative group bg-slate-900">
                    <img src={movie.poster_url} alt={movie.subject_name} className="w-full h-auto object-cover opacity-90 group-hover:opacity-100 transition-opacity" />
                </div>
                
                <div className="bg-surface p-6 rounded-xl border border-slate-700/50 backdrop-blur-sm">
                    <h3 className="text-gray-400 text-[10px] uppercase tracking-widest font-bold mb-4">Metric Analysis</h3>
                    
                    {/* Critic Bar */}
                    <div className="mb-6">
                        <div className="flex justify-between text-sm mb-2">
                            <span className="text-gray-300 font-medium">Critics Aggregate</span>
                            <span className={`font-bold ${getScoreColor(movie.critics_score)}`}>{movie.critics_score}</span>
                        </div>
                        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full bg-gradient-to-r from-yellow-600 to-primary transition-all duration-1000" style={{width: `${movie.critics_score}%`}}></div>
                        </div>
                    </div>

                    {/* Audience Bar */}
                    <div>
                        <div className="flex justify-between text-sm mb-2">
                            <span className="text-gray-300 font-medium">Audience Sentiment</span>
                            <span className={`font-bold ${movie.audience_score > 0 ? 'text-blue-400' : 'text-gray-500'}`}>
                                {movie.audience_score > 0 ? movie.audience_score : 'N/A'}
                            </span>
                        </div>
                        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full bg-gradient-to-r from-blue-900 to-blue-500 transition-all duration-1000" style={{width: `${movie.audience_score}%`}}></div>
                        </div>
                    </div>
                </div>

                <div className="bg-surface p-6 rounded-xl border border-slate-700/50">
                     <h3 className="text-gray-400 text-[10px] uppercase tracking-widest font-bold mb-3">Metadata</h3>
                     <p className="text-sm text-gray-300 mb-2 flex justify-between">
                        <span className="text-gray-500">Released</span> 
                        <span>{movie.metadata?.release_date || 'Unknown'}</span>
                     </p>
                     <div className="flex flex-wrap gap-2 mt-4">
                        {movie.metadata?.genres?.map(g => (
                            <span key={g.id} className="text-[10px] bg-slate-800 text-gray-400 border border-slate-700 px-3 py-1 rounded-full">{g.name}</span>
                        ))}
                     </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="md:col-span-8 lg:col-span-9 space-y-8">
                <div>
                     <h1 className="text-4xl md:text-6xl font-black text-white tracking-tighter mb-2">{movie.subject_name}</h1>
                     <p className="text-primary font-mono text-sm tracking-widest uppercase">{movie.consensus_line}</p>
                </div>
                
                {/* AI Dashboard */}
                <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 border border-slate-700 rounded-2xl p-6 md:p-8 shadow-2xl relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-12 bg-primary/5 rounded-full blur-3xl -mr-10 -mt-10"></div>
                    
                    <div className="flex justify-between items-start mb-8 relative z-10">
                        <h2 className="text-white font-bold tracking-widest text-xs uppercase flex items-center gap-3">
                            <span className={`w-2 h-2 rounded-full ${generating ? 'bg-yellow-500 animate-ping' : 'bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]'}`}></span>
                            Gemini 3 Consensus Protocol
                        </h2>
                        {!generating && (
                            <button 
                                onClick={() => generateConsensus(movie)} 
                                className="text-xs text-slate-500 hover:text-white transition-colors border border-slate-700 hover:border-slate-500 px-3 py-1 rounded-full"
                            >
                                {isPending ? 'Initialize Analysis' : 'Refresh Data'}
                            </button>
                        )}
                    </div>

                    {!aiSummary && !generating ? (
                         <div className="animate-pulse space-y-4 opacity-50">
                             <div className="h-6 bg-slate-700 rounded w-1/2"></div>
                             <div className="h-4 bg-slate-700/50 rounded w-full"></div>
                             <div className="h-4 bg-slate-700/50 rounded w-3/4"></div>
                         </div>
                    ) : aiSummary ? (
                        <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 relative z-10">
                            <p className="text-2xl md:text-3xl font-serif italic text-white mb-6 leading-relaxed">
                                "{aiSummary.tagline || 'Processing Data...'}"
                            </p>
                            <p className="text-gray-300 leading-relaxed text-lg mb-8 max-w-3xl">
                                {aiSummary.summary}
                            </p>

                            {!isPending && (
                                <div className="grid md:grid-cols-3 gap-4 border-t border-white/10 pt-6">
                                    <div className="bg-black/30 p-5 rounded-xl border border-white/5">
                                        <h4 className="text-[10px] font-bold text-secondary uppercase mb-2 tracking-wider">Gap Analysis</h4>
                                        <p className="text-sm text-gray-300 leading-snug">{aiSummary.critics_vs_audience || "N/A"}</p>
                                    </div>
                                    <div className="bg-black/30 p-5 rounded-xl border border-white/5">
                                        <h4 className="text-[10px] font-bold text-secondary uppercase mb-2 tracking-wider">Major Conflict</h4>
                                        <p className="text-sm text-gray-300 leading-snug">{aiSummary.conflict_points || "N/A"}</p>
                                    </div>
                                    <div className="bg-black/30 p-5 rounded-xl border border-white/5">
                                        <h4 className="text-[10px] font-bold text-secondary uppercase mb-2 tracking-wider">Community Vibe</h4>
                                        <p className="text-sm font-mono text-primary">{aiSummary.comment_vibe || "Neutral"}</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : null}
                </div>

                {/* Reviewers List */}
                <div>
                    <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3 border-l-4 border-primary pl-4">
                        Analyst Breakdown 
                        <span className="text-sm font-normal text-gray-500 bg-slate-800 px-2 py-0.5 rounded-full">{movie.scans.length} Sources</span>
                    </h3>
                    <div className="grid gap-4">
                        {movie.scans.map(scan => <ReviewerCard key={scan.id} scan={scan} />)}
                    </div>
                </div>
            </div>
        </div>
    </div>
  );
};

const VaultPage = () => {
  const [items, setItems] = useState<VaultItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVault = async () => {
        const {data} = await supabase.from('memory_vault').select('*').order('created_at', { ascending: false });
        if(data) setItems(data as unknown as VaultItem[]);
        setLoading(false);
    }
    fetchVault();
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-white mb-8 border-l-4 border-primary pl-4">Memory Vault</h1>
        
        {loading ? (
             <div className="flex justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary"></div></div>
        ) : (
            <div className="grid gap-4">
                {items.map(item => {
                    const report = safeParseJSON(item.summary_report);
                    if (!report || report.tagline === "Analysis Delayed") return null;

                    return (
                        <div key={item.id} className="bg-surface p-6 rounded-lg border border-slate-700 hover:border-slate-500 transition-colors group">
                            <div className="flex justify-between items-start mb-2">
                                <h2 className="text-xl font-bold text-white group-hover:text-primary transition-colors">{item.movie_name}</h2>
                                <span className="text-xs text-gray-500">{formatDate(item.created_at)}</span>
                            </div>
                            <p className="text-gray-300 font-serif italic mb-2">"{report.tagline}"</p>
                            <p className="text-sm text-gray-500 line-clamp-2">{report.summary}</p>
                            <div className="mt-4 flex justify-end">
                                <a href={`#/movie/${item.movie_name.toLowerCase().replace(/\s+/g, '-')}`} className="text-xs text-white bg-slate-700 px-4 py-2 rounded hover:bg-slate-600 transition-colors">
                                    Full Analysis
                                </a>
                            </div>
                        </div>
                    );
                })}
                {items.length === 0 && <div className="text-gray-500 text-center py-20">Vault is empty.</div>}
            </div>
        )}
    </div>
  );
};

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
            </div>
        </div>
    );
};

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
        <p>&copy; {new Date().getFullYear()} Cinema Wall. Powered by AI.</p>
      </footer>
    </div>
  );
};

export default App;
