import React from 'react';
import { Scan } from '../types';
import { formatDate } from '../lib/utils';

const ReviewerCard: React.FC<{ scan: Scan }> = ({ scan }) => {
  const result = scan.result || {};
  
  // Try to find a meaningful snippet or sentiment
  const sentiment = result.sentiment || 'Neutral';
  const topics = result.topics?.slice(0, 3).join(', ') || '';
  const isBot = result.is_bot || (result.bot_probability && result.bot_probability > 0.7);

  return (
    <div className={`bg-surface p-4 rounded-lg border border-slate-700 flex flex-col gap-2 ${isBot ? 'opacity-60 border-red-900/50' : ''}`}>
      <div className="flex justify-between items-start">
        <div className="flex flex-col">
            <h4 className="font-bold text-gray-200">{scan.reviewer_name}</h4>
            <span className="text-xs text-gray-500">{formatDate(scan.created_at)}</span>
        </div>
        <span className={`text-xs px-2 py-1 rounded bg-slate-900 border ${
            sentiment.toLowerCase() === 'positive' ? 'border-green-500 text-green-500' :
            sentiment.toLowerCase() === 'negative' ? 'border-red-500 text-red-500' :
            'border-gray-500 text-gray-500'
        }`}>
            {sentiment}
        </span>
      </div>
      
      <p className="text-sm text-gray-300 font-medium line-clamp-1">{scan.title}</p>
      
      {result.summary && (
        <p className="text-xs text-gray-400 mt-1 line-clamp-3">"{result.summary}"</p>
      )}

      {topics && (
        <div className="mt-2 text-xs text-secondary">
          Topics: {topics}
        </div>
      )}
      
      {isBot && (
        <div className="mt-2 text-[10px] text-red-400 uppercase tracking-wider font-bold">
            ⚠️ Potentially Automated Content
        </div>
      )}
      
      <div className="mt-auto pt-3">
        <a 
            href={`https://www.youtube.com/results?search_query=${encodeURIComponent(scan.title + ' ' + scan.reviewer_name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary hover:underline flex items-center gap-1"
        >
            Find Source 
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
        </a>
      </div>
    </div>
  );
};

export default ReviewerCard;
