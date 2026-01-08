import React from 'react';
import { Scan } from '../types';
import { formatDate } from '../lib/utils';

const ReviewerCard: React.FC<{ scan: Scan }> = ({ scan }) => {
  const result = scan.result || {};
  
  // Display Logic
  const displaySummary = result.overallSummary || result.summary || "Summary pending.";
  const sentiment = result.sentiment || 'Neutral';
  
  // Extract refined audience perception from style analysis
  const rawPerception = result.reviewerStyleAnalysis || 
                       (result.highQualityInsights?.[0]?.analysis ? `Comments highlight: ${result.highQualityInsights[0].analysis}` : null) ||
                       "No significant audience data.";
                       
  // Truncate perception for neatness if too long
  const perception = rawPerception.length > 150 ? rawPerception.substring(0, 147) + "..." : rawPerception;

  return (
    <div className="bg-surface border border-slate-700/60 rounded-lg p-5 hover:border-slate-500 transition-colors">
      <div className="flex justify-between items-center mb-3">
        <div>
           <h4 className="font-bold text-white text-lg leading-none">{scan.reviewer_name}</h4>
           <div className="flex items-center gap-2 mt-2">
             <span className="text-xs text-secondary">{formatDate(scan.created_at)}</span>
             {scan.mode === 'COMMENTS' && <span className="text-[10px] bg-slate-800 text-gray-400 px-1.5 py-0.5 rounded border border-slate-700 tracking-wide uppercase">Community Aggregate</span>}
           </div>
        </div>
        <div className={`px-3 py-1 rounded text-xs font-bold border uppercase tracking-wider ${
             sentiment.includes('Positive') ? 'bg-green-900/10 text-green-400 border-green-800' :
             sentiment.includes('Negative') ? 'bg-red-900/10 text-red-400 border-red-800' :
             'bg-slate-800 text-gray-400 border-slate-600'
        }`}>
            {sentiment}
        </div>
      </div>

      {/* The Verdict */}
      <div className="mb-4">
          <p className="text-gray-300 text-sm leading-relaxed border-l-2 border-primary/30 pl-3">
             {displaySummary}
          </p>
      </div>

      {/* The Meta-Analysis (Perception) */}
      {scan.mode !== 'COMMENTS' && (
        <div className="bg-slate-900/50 rounded p-3 mt-3 border border-slate-800">
            <div className="flex items-center gap-2 mb-1">
                <svg className="w-3 h-3 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                <p className="text-[10px] uppercase tracking-widest text-secondary font-bold">
                    Audience Response
                </p>
            </div>
            <p className="text-sm text-gray-400 italic">
                "{perception}"
            </p>
        </div>
      )}

      <div className="mt-3 flex justify-end">
         <a 
            href={scan.video_url || `https://www.youtube.com/results?search_query=${encodeURIComponent(scan.title)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary/70 hover:text-primary flex items-center gap-1 transition-colors group"
        >
            Source Analysis
            <svg className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
        </a>
      </div>
    </div>
  );
};

export default ReviewerCard;