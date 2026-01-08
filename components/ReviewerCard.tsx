import React from 'react';
import { Scan } from '../types';
import { formatDate } from '../lib/utils';

const ReviewerCard: React.FC<{ scan: Scan }> = ({ scan }) => {
  const result = scan.result || {};
  
  // 1. Determine Display Text
  // DeepAnalysisResult uses 'overallSummary' or 'sentimentDescription'. 
  // Standard result uses 'summary'.
  const displaySummary = result.overallSummary || result.summary || result.sentimentDescription || "No detailed summary available.";
  
  // 2. Determine Sentiment Label
  let sentiment = result.sentiment || 'Neutral';
  // If neutral but we have text, try to derive a label for display
  if (sentiment === 'Neutral' && displaySummary) {
      const lower = displaySummary.toLowerCase();
      if (lower.includes('excellent') || lower.includes('positive') || lower.includes('great')) sentiment = 'Positive';
      else if (lower.includes('terrible') || lower.includes('negative') || lower.includes('bad')) sentiment = 'Negative';
      else if (lower.includes('mixed')) sentiment = 'Mixed';
  }

  // 3. Bot Detection Logic
  const botThreat = result.botDetection?.overallThreatLevel;
  const isHighThreat = botThreat === 'CRITICAL' || botThreat === 'ELEVATED';

  // 4. Topics / Insights
  const topics = result.topics?.slice(0, 3).join(', ') || '';
  const insights = result.highQualityInsights?.slice(0, 1) || [];

  return (
    <div className={`bg-surface p-4 rounded-lg border border-slate-700 flex flex-col gap-2 ${isHighThreat ? 'border-red-500/50 bg-red-900/10' : ''}`}>
      <div className="flex justify-between items-start">
        <div className="flex flex-col">
            <h4 className="font-bold text-gray-200">{scan.reviewer_name}</h4>
            <span className="text-xs text-gray-500">{formatDate(scan.created_at)}</span>
        </div>
        <div className="flex gap-2">
            {botThreat && botThreat !== 'NOMINAL' && (
                <span className="text-[10px] px-2 py-1 rounded bg-red-900 text-red-200 border border-red-700 font-bold">
                    BOT THREAT: {botThreat}
                </span>
            )}
            <span className={`text-xs px-2 py-1 rounded bg-slate-900 border ${
                sentiment.toLowerCase().includes('positive') ? 'border-green-500 text-green-500' :
                sentiment.toLowerCase().includes('negative') ? 'border-red-500 text-red-500' :
                'border-gray-500 text-gray-500'
            }`}>
                {sentiment}
            </span>
        </div>
      </div>
      
      <p className="text-sm text-gray-300 font-medium line-clamp-1 border-b border-slate-800 pb-2 mb-1">{scan.title}</p>
      
      <p className="text-sm text-gray-400 leading-relaxed">
        {displaySummary}
      </p>

      {/* Show High Quality Insight if available */}
      {insights.length > 0 && (
          <div className="mt-3 bg-slate-800/50 p-3 rounded border-l-2 border-primary">
              <p className="text-xs text-primary font-bold mb-1">Top Insight ({insights[0].username}):</p>
              <p className="text-xs text-gray-300 italic">"{insights[0].analysis}"</p>
          </div>
      )}

      {/* Show Reviewer Style if available */}
      {result.reviewerStyleAnalysis && (
           <div className="mt-2 text-xs text-gray-500">
             <span className="font-bold text-gray-400">Audience Perception:</span> {result.reviewerStyleAnalysis}
           </div>
      )}
      
      <div className="mt-auto pt-3 flex justify-between items-center">
         {topics && <div className="text-xs text-secondary">Tags: {topics}</div>}
         
         <a 
            href={scan.video_url || `https://www.youtube.com/results?search_query=${encodeURIComponent(scan.title)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary hover:underline flex items-center gap-1 ml-auto"
        >
            View Source 
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
        </a>
      </div>
    </div>
  );
};

export default ReviewerCard;
