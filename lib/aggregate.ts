import { Scan, MovieAggregate, MovieMetadata } from '../types';
import { slugify } from './utils';
import { fetchMovieMetadata } from './tmdb';
import { DEFAULT_POSTER, TMDB_BASE_URL } from '../constants';

// Helper to safely extract values regardless of case
const safeGet = (obj: any, keys: string[]) => {
  if (!obj) return undefined;
  for (const key of keys) {
    if (obj[key] !== undefined) return obj[key];
    const lowerKey = key.toLowerCase();
    const found = Object.keys(obj).find(k => k.toLowerCase() === lowerKey);
    if (found && obj[found] !== undefined) return obj[found];
  }
  return undefined;
};

// Normalize any score to 0-100 integer
const normalizeScore = (val: any): number | null => {
    if (val === undefined || val === null || val === '') return null;
    let num = parseFloat(val);
    if (isNaN(num)) return null;

    // If score is 0-1 (e.g. 0.85), multiply by 100
    if (num <= 1 && num > 0) return Math.round(num * 100);
    // If score is 0-5, multiply by 20
    if (num <= 5 && num > 1) return Math.round(num * 20);
    // If score is 0-10, multiply by 10
    if (num <= 10 && num > 1) return Math.round(num * 10);
    // If score is 0-100, keep it
    if (num <= 100) return Math.round(num);
    
    // If 0, return 0 (only if it was explicitly 0)
    return 0;
};

const analyzeSentimentText = (text: string): { score: number, label: string } => {
    const lower = text.toLowerCase();
    // Super Positive
    if (lower.match(/(masterpiece|extraordinary|phenomenal|perfect|universal acclaim|blockbuster)/)) return { score: 95, label: 'Positive' };
    
    // Positive
    if (lower.match(/(excellent|great|good|enjoyable|hit|superb|brilliant|worth watch|solid|fresh)/)) return { score: 80, label: 'Positive' };
    
    // Mixed
    if (lower.match(/(mixed|average|decent|ok|okay|one time|fine|mediocre|passable)/)) return { score: 60, label: 'Mixed' };
    
    // Negative
    if (lower.match(/(bad|boring|poor|dull|slow|flop|disappointing|skippable)/)) return { score: 40, label: 'Negative' };
    
    // Super Negative
    if (lower.match(/(terrible|disaster|awful|waste|worst|garbage|rotten)/)) return { score: 20, label: 'Negative' };

    return { score: 50, label: 'Neutral' };
};

export async function aggregateScans(scans: Scan[], fetchMeta = false): Promise<MovieAggregate[]> {
  const grouped: Record<string, Scan[]> = {};

  scans.forEach(scan => {
    const key = scan.subject_name;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(scan);
  });

  const aggregates: MovieAggregate[] = [];

  for (const [subject, movieScans] of Object.entries(grouped)) {
    const uniqueReviewers = new Set(movieScans.map(s => s.reviewer_name)).size;
    const lastScanned = movieScans.reduce((max, s) => 
      new Date(s.created_at) > new Date(max) ? s.created_at : max, 
      movieScans[0].created_at
    );

    let totalCriticScore = 0;
    let criticCount = 0;
    let totalAudienceScore = 0;
    let audienceCount = 0;

    const allTopics: string[] = [];
    const allSentiments: string[] = [];

    movieScans.forEach(scan => {
      const r = scan.result || {};
      const mode = (scan.mode || 'REVIEWER').toUpperCase();
      const isAudienceScan = mode === 'AUDIENCE' || mode === 'COMMENTS';

      // Get Raw Scores
      const rawScore = safeGet(r, ['sentiment_score', 'sentimentScore', 'score']);
      const rawAudience = safeGet(r, ['audience_sentiment', 'audienceSentiment', 'audienceScore']);
      const textForAnalysis = safeGet(r, ['sentimentDescription', 'sentiment', 'overallSummary', 'summary']) || "";

      // --- CRITICS SCORE ---
      if (!isAudienceScan) {
          const norm = normalizeScore(rawScore);
          if (norm !== null) {
              totalCriticScore += norm;
              criticCount++;
              allSentiments.push(norm >= 60 ? 'Positive' : 'Negative');
          } else if (textForAnalysis) {
              const { score, label } = analyzeSentimentText(textForAnalysis);
              totalCriticScore += score;
              criticCount++;
              allSentiments.push(label);
          }
      }

      // --- AUDIENCE SCORE ---
      // We prioritize explicit scores, then fall back to analyzing the comments/insights
      let calculatedAudienceScore: number | null = null;
      
      const normAudience = normalizeScore(rawAudience);
      if (normAudience !== null && normAudience > 0) {
          calculatedAudienceScore = normAudience;
      }
      // If no explicit score, derive from High Quality Insights (Comments)
      else if (r.highQualityInsights && Array.isArray(r.highQualityInsights) && r.highQualityInsights.length > 0) {
          let insTotal = 0;
          let insCount = 0;
          r.highQualityInsights.forEach((ins: any) => {
             // Analyze the 'analysis' text which describes the comment sentiment
             const txt = ins.analysis || ins.text || "";
             if (!txt) return;
             
             // Check if the comment actually expresses an opinion
             const { score } = analyzeSentimentText(txt);
             insTotal += score;
             insCount++;
          });
          
          if (insCount > 0) {
              calculatedAudienceScore = Math.round(insTotal / insCount);
          }
      }
      // If this scan IS an audience scan but has no number, analyze the main text
      else if (isAudienceScan && textForAnalysis) {
          const { score } = analyzeSentimentText(textForAnalysis);
          calculatedAudienceScore = score;
      }

      if (calculatedAudienceScore !== null) {
          totalAudienceScore += calculatedAudienceScore;
          audienceCount++;
      }

      // Collect Topics
      const scanTopics = safeGet(r, ['topics', 'Topics']) || [];
      if (Array.isArray(scanTopics)) allTopics.push(...scanTopics);
    });

    const critics_score = criticCount > 0 ? Math.round(totalCriticScore / criticCount) : 0;
    const audience_score = audienceCount > 0 ? Math.round(totalAudienceScore / audienceCount) : 0;

    // Consensus Text
    let consensus_line = "Pending Analysis";
    if (criticCount > 0) {
        if (critics_score >= 80) consensus_line = "Universal Acclaim";
        else if (critics_score >= 60) consensus_line = "Generally Favorable";
        else if (critics_score >= 40) consensus_line = "Mixed or Average";
        else consensus_line = "Generally Unfavorable";
    }

    // Filter Topics
    const topicFreq: Record<string, number> = {};
    const stopWords = ['movie', 'film', 'review', 'video', 'story', 'plot', 'first', 'half', 'second', 'watch', 'cinema', 'really', 'actor', 'acting'];
    allTopics.forEach(t => {
      const lowerT = String(t).toLowerCase().replace(/[^a-z\s]/g, '').trim();
      if(!lowerT || stopWords.includes(lowerT) || lowerT.length < 4) return;
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([t]) => t.charAt(0).toUpperCase() + t.slice(1));

    // Metadata & Poster logic
    let metadata: MovieMetadata | undefined = undefined;
    if (fetchMeta) {
        metadata = await fetchMovieMetadata(subject);
    }

    let poster_url = "";
    if (metadata?.poster_path) poster_url = `${TMDB_BASE_URL}${metadata.poster_path}`;
    if ((!poster_url || poster_url === DEFAULT_POSTER)) {
        const scanWithThumb = movieScans.find(s => s.thumbnail && s.thumbnail.startsWith('http'));
        if (scanWithThumb) poster_url = scanWithThumb.thumbnail || "";
    }
    if (!poster_url) poster_url = DEFAULT_POSTER;

    aggregates.push({
      subject_name: subject,
      slug: slugify(subject),
      reviewers_count: uniqueReviewers,
      last_scanned: lastScanned,
      critics_score,
      audience_score,
      consensus_line,
      top_topics,
      scans: movieScans,
      metadata,
      poster_url
    });
  }

  return aggregates;
}