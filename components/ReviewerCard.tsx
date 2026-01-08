import React from 'react';
import { Scan } from '../types';
import { formatDate } from '../lib/utils';

const ReviewerCard: React.FC<{ scan: Scan }> = ({ scan }) => {
  const result = scan.result || {};
  
  // Display Logic
  const displaySummary = result.overallSummary || result.summary || "Summary pending.";
  const sentiment = result.sentiment || 'Neutral';
  const botThreat = result.botDetection?.overallThreatLevel;

  // Key Feature: Audience Perception of the Reviewer
  // If 'reviewerStyleAnalysis' exists, use it. Otherwise, look at highQualityInsights for context.
  const audiencePerception = result.reviewerStyleAnalysis || 
                             (result.highQualityInsights?.[0]?.analysis ? `Fans note: ${result.highQualityInsights[0].analysis}` : null) ||
                             "No specific audience consensus on this review yet.";

  return (
    <div className="bg-surface border border-slate-700/60 rounded-lg p-5 hover:border-slate-500 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <div>
           <h4 className="font-bold text-white text-lg">{scan.reviewer_name}</h4>
           <div className="flex items-center gap-2 mt-1">
             <span className="text-xs text-secondary">{formatDate(scan.created_at)}</span>
             {scan.mode === 'COMMENTS' && <span className="text-[10px] bg-slate-800 text-gray-400 px-1.5 py-0.5 rounded border border-slate-700">AUDIENCE AGGREGATE</span>}
           </div>
        </div>
        <div className={`px-3 py-1 rounded text-sm font-bold border ${
             sentiment.includes('Positive') ? 'bg-green-900/20 text-green-400 border-green-800' :
             sentiment.includes('Negative') ? 'bg-red-900/20 text-red-400 border-red-800' :
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
      <div className="bg-black/20 rounded p-3 mt-3">
          <p className="text-[10px] uppercase tracking-widest text-secondary font-bold mb-1">
              Analyst Perception (Comments Vibe)
          </p>
          <p className="text-sm text-gray-400 italic">
              "{audiencePerception}"
          </p>
      </div>

      <div className="mt-3 flex justify-end">
         <a 
            href={scan.video_url || `https://www.youtube.com/results?search_query=${encodeURIComponent(scan.title)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary/70 hover:text-primary flex items-center gap-1 transition-colors"
        >
            Source
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
        </a>
      </div>
    </div>
  );
};

export default ReviewerCard;