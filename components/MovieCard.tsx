import React from 'react';
import { MovieAggregate } from '../types';
import { formatDate, getScoreColor } from '../lib/utils';
import { DEFAULT_POSTER, TMDB_BASE_URL } from '../constants';

interface MovieCardProps {
  movie: MovieAggregate;
}

const MovieCard: React.FC<MovieCardProps> = ({ movie }) => {
  const posterUrl = movie.metadata?.poster_path 
    ? `${TMDB_BASE_URL}${movie.metadata.poster_path}` 
    : DEFAULT_POSTER;

  return (
    <a href={`#/movie/${movie.slug}`} className="group block bg-surface rounded-lg overflow-hidden border border-slate-700 hover:border-primary/50 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl shadow-black/50">
      <div className="relative aspect-[2/3] overflow-hidden">
        <img 
          src={posterUrl} 
          alt={movie.subject_name} 
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          loading="lazy"
        />
        <div className="absolute top-2 right-2 flex flex-col gap-1">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center bg-black/80 backdrop-blur-sm border-2 font-bold text-xs ${getScoreColor(movie.critics_score)}`}>
            {movie.critics_score}
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black/80 to-transparent p-4 translate-y-2 group-hover:translate-y-0 transition-transform">
          <p className="text-xs text-gray-300 line-clamp-2 italic">"{movie.consensus_line}"</p>
        </div>
      </div>
      
      <div className="p-4">
        <h3 className="text-lg font-bold text-white truncate mb-1" title={movie.subject_name}>
          {movie.subject_name}
        </h3>
        <div className="flex items-center text-xs text-gray-400 mb-3 space-x-2">
           <span>{movie.metadata?.release_date ? movie.metadata.release_date.split('-')[0] : 'Unknown Year'}</span>
           <span>•</span>
           <span>{movie.reviewers_count} Reviewers</span>
        </div>
        
        <div className="flex justify-between items-center text-xs text-gray-500 border-t border-slate-700 pt-3">
          <span>Audience: <span className={getScoreColor(movie.audience_score).split(' ')[0]}>{movie.audience_score}%</span></span>
          <span>{formatDate(movie.last_scanned)}</span>
        </div>
      </div>
    </a>
  );
};

export default MovieCard;
