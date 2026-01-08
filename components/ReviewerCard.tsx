import React from 'react';
import { Scan } from '../types';
import { formatDate } from '../lib/utils';

const ReviewerCard: React.FC<{ scan: Scan }> = ({ scan }) => {
  const result = scan.result || {};
  
  // Display Logic
  const displaySummary = result.overallSummary || result.summary || "Summary pending.";
  const sentiment = result.sentiment || 'Neutral';
  
  // Audience Perception Logic
  // Removed arbitrary substring limit (120 chars) to allow full insight display
  const perception = result.reviewerStyleAnalysis || 
                       (result.highQualityInsights?.[0]?.analysis ? `Comments highlight: ${result.highQualityInsights[0].analysis}` : null) ||
                       "No consensus data available.";

  // Use scan thumbnail as "Analyst Avatar". Fallback to a generic gradient if missing.
  const avatarUrl = scan.thumbnail;

  return (
    <div className="group bg-surface border border-slate-700/60 rounded-xl p-0 overflow-hidden hover:border-slate-500 transition-all duration-300 hover:shadow-lg">
      <div className="flex flex-col sm:flex-row h-full">
          
          {/* Left: Analyst Identity Column */}
          <div className="sm:w-32 bg-slate-900/50 flex flex-col items-center justify-center p-4 border-r border-slate-800">
              <div className="w-16 h-16 rounded-full overflow-hidden border-2 border-slate-700 shadow-md mb-2 group-hover:scale-105 transition-transform">
                  {avatarUrl ? (
                      <img src={avatarUrl} alt={scan.reviewer_name} className="w-full h-full object-cover" />
                  ) : (
                      <div className="w-full h-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center text-xs text-gray-500">
                          N/A
                      </div>
                  )}
              </div>
              <h4 className="font-bold text-white text-xs text-center leading-tight mb-1">{scan.reviewer_name}</h4>
              <span className="text-[10px] text-gray-500">{formatDate(scan.created_at)}</span>
          </div>

          {/* Right: Content Area */}
          <div className="flex-1 p-5 flex flex-col justify-between">
              <div>
                  <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-2">
                        {scan.mode === 'COMMENTS' && <span className="text-[9px] bg-blue-900/30 text-blue-400 border border-blue-800/50 px-1.5 py-0.5 rounded tracking-wide uppercase">Community</span>}
                        {scan.mode !== 'COMMENTS' && <span className="text-[9px] bg-slate-800 text-gray-400 border border-slate-700 px-1.5 py-0.5 rounded tracking-wide uppercase">Review</span>}
                      </div>
                      
                      <div className={`px-2 py-1 rounded text-[10px] font-bold border uppercase tracking-wider ${
                           sentiment.includes('Positive') ? 'bg-green-950 text-green-400 border-green-900' :
                           sentiment.includes('Negative') ? 'bg-red-950 text-red-400 border-red-900' :
                           'bg-slate-800 text-gray-400 border-slate-700'
                      }`}>
                          {sentiment}
                      </div>
                  </div>

                  <p className="text-gray-300 text-sm leading-relaxed mb-4">
                     "{displaySummary}"
                  </p>
              </div>

              {/* Footer: Meta Analysis */}
              <div className="bg-black/20 rounded-lg p-3 border border-white/5 flex items-start gap-3">
                    <div className="mt-0.5 min-w-[12px]">
                         <svg className="w-3 h-3 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
                    </div>
                    <div className="flex-1">
                        <p className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">Audience Reception</p>
                        <p className="text-xs text-gray-400 italic leading-relaxed">{perception}</p>
                    </div>
                    <div className="ml-auto pl-2">
                        <a 
                            href={scan.video_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-white hover:text-primary transition-colors flex items-center justify-center p-1"
                            title="Watch Video"
                        >
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/></svg>
                        </a>
                    </div>
              </div>
          </div>
      </div>
    </div>
  );
};

export default ReviewerCard;