import React from 'react';
import { MovieAggregate } from '../types';
import { formatDate, getScoreColor } from '../lib/utils';

interface MovieCardProps {
  movie: MovieAggregate;
}

const MovieCard: React.FC<MovieCardProps> = ({ movie }) => {
  // Extract unique reviewer avatars (thumbnails) for the footer
  const reviewerAvatars = movie.scans
    .filter(s => s.thumbnail && s.thumbnail.startsWith('http'))
    .slice(0, 4) // Show max 4 faces
    .map(s => s.thumbnail);

  return (
    <a href={`#/movie/${movie.slug}`} className="group relative block bg-surface rounded-xl overflow-hidden border border-slate-700/50 hover:border-primary/50 transition-all duration-300 hover:-translate-y-2 hover:shadow-2xl shadow-black/50">
      
      {/* 1. Image Area with Gradient Overlay */}
      <div className="relative aspect-[2/3] overflow-hidden bg-slate-900">
        <img 
          src={movie.poster_url} 
          alt={movie.subject_name} 
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110 group-hover:opacity-80"
          loading="lazy"
        />
        
        {/* Dark Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent opacity-90"></div>
        
        {/* Top Badges: Scores */}
        <div className="absolute top-3 right-3 flex flex-col gap-2">
           {/* Critics Score */}
           <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-lg backdrop-blur-md bg-black/40 border ${getScoreColor(movie.critics_score)} shadow-lg`}>
              <span className="text-sm font-bold text-white">{movie.critics_score}</span>
              <span className="text-[8px] uppercase tracking-wider text-gray-300">Critic</span>
           </div>
           
           {/* Audience Score */}
           <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-lg backdrop-blur-md bg-black/40 border border-blue-500/50 shadow-lg`}>
              <span className={`text-sm font-bold ${movie.audience_score > 0 ? 'text-blue-400' : 'text-gray-500'}`}>
                {movie.audience_score > 0 ? movie.audience_score : 'N/A'}
              </span>
              <span className="text-[8px] uppercase tracking-wider text-gray-300">Fans</span>
           </div>
        </div>
      </div>
      
      {/* 2. Content Area (Floating Glass Effect) */}
      <div className="absolute bottom-0 left-0 right-0 p-4">
         <div className="bg-surface/90 backdrop-blur-md border border-slate-600/30 rounded-lg p-3 shadow-xl transform translate-y-2 group-hover:translate-y-0 transition-transform duration-300">
            
            <h3 className="text-lg font-bold text-white truncate mb-1 leading-tight" title={movie.subject_name}>
              {movie.subject_name}
            </h3>
            
            <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] text-primary uppercase tracking-widest font-semibold truncate max-w-[60%]">
                    {movie.consensus_line}
                </span>
                <span className="text-[10px] text-gray-400">
                    {movie.metadata?.release_date ? new Date(movie.metadata.release_date).getFullYear() : 'Unknown'}
                </span>
            </div>

            {/* Reviewer Avatars / Footer */}
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-700/50">
                <div className="flex -space-x-1">
                    {reviewerAvatars.map((thumb, i) => (
                        <div key={i} className="w-6 h-6 rounded-md border border-slate-800 overflow-hidden bg-slate-800 z-10 hover:z-20 transition-all hover:scale-125">
                            <img src={thumb} alt="Reviewer" className="w-full h-full object-cover opacity-90" />
                        </div>
                    ))}
                    {reviewerAvatars.length === 0 && (
                        <span className="text-[10px] text-gray-500 italic">No previews</span>
                    )}
                </div>
                <div className="text-[10px] text-gray-400 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                    {movie.reviewers_count}
                </div>
            </div>

         </div>
      </div>
    </a>
  );
};

export default MovieCard;