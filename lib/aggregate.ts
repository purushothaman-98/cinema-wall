
import { Scan, MovieAggregate, MovieMetadata } from '../types';
import { slugify } from './utils';
import { DEFAULT_POSTER } from '../constants';

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

    // Scale 0-1 -> 0-100
    if (num <= 1 && num > 0) return Math.round(num * 100);
    // Scale 0-5 -> 0-100
    if (num <= 5 && num > 1) return Math.round(num * 20);
    // Scale 0-10 -> 0-100
    if (num <= 10 && num > 1) return Math.round(num * 10);
    // 0-100
    if (num <= 100) return Math.round(num);
    
    return 0;
};

const analyzeSentimentText = (text: string): { score: number, label: string } => {
    const lower = text.toLowerCase();
    // Weighted Keyword Analysis
    if (lower.match(/(masterpiece|extraordinary|phenomenal|perfect|10\/10|blockbuster)/)) return { score: 95, label: 'Positive' };
    if (lower.match(/(excellent|great|good|enjoyable|hit|superb|brilliant|worth watch|solid|fresh|must watch)/)) return { score: 80, label: 'Positive' };
    if (lower.match(/(mixed|average|decent|ok|okay|one time|fine|mediocre|passable|predictable)/)) return { score: 55, label: 'Mixed' };
    if (lower.match(/(bad|boring|poor|dull|slow|flop|disappointing|skippable|weak)/)) return { score: 35, label: 'Negative' };
    if (lower.match(/(terrible|disaster|awful|waste|worst|garbage|rotten|torture)/)) return { score: 15, label: 'Negative' };
    return { score: 50, label: 'Neutral' };
};

export async function aggregateScans(scans: Scan[], fetchMeta = false): Promise<MovieAggregate[]> {
  const grouped: Record<string, Scan[]> = {};

  scans.forEach(scan => {
    // Normalize Subject Name slightly to group better
    const key = scan.subject_name.trim();
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(scan);
  });

  const aggregates: MovieAggregate[] = [];

  for (const [subject, movieScans] of Object.entries(grouped)) {
    const uniqueReviewers = new Set(movieScans.map(s => s.reviewer_name)).size;
    
    // Sort scans by date descending (Newest first)
    movieScans.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    
    const lastScanned = movieScans[0].created_at; 
    // Proxy for Release Date: The date of the EARLIEST scan/video upload we have in DB
    const releaseDate = movieScans[movieScans.length - 1].created_at;

    let totalCriticScore = 0;
    let criticCount = 0;
    let totalAudienceScore = 0;
    let audienceCount = 0;

    const allTopics: string[] = [];

    movieScans.forEach(scan => {
      const r = scan.result || {};
      const mode = (scan.mode || 'REVIEWER').toUpperCase();
      const isAudienceScan = mode === 'AUDIENCE' || mode === 'COMMENTS';

      // Get Values
      const rawScore = safeGet(r, ['sentiment_score', 'sentimentScore', 'score']);
      const rawAudience = safeGet(r, ['audience_sentiment', 'audienceSentiment', 'audienceScore']);
      const textForAnalysis = safeGet(r, ['sentimentDescription', 'sentiment', 'overallSummary', 'summary']) || "";

      // --- CRITICS SCORE ---
      if (!isAudienceScan) {
          const norm = normalizeScore(rawScore);
          if (norm !== null) {
              totalCriticScore += norm;
              criticCount++;
          } else if (textForAnalysis) {
              const { score } = analyzeSentimentText(textForAnalysis);
              totalCriticScore += score;
              criticCount++;
          }
      }

      // --- AUDIENCE SCORE ---
      let calculatedAudienceScore: number | null = null;
      const normAudience = normalizeScore(rawAudience);

      if (normAudience !== null && normAudience > 0) {
          calculatedAudienceScore = normAudience;
      }
      // Insight Sentiment Analysis
      else if (r.highQualityInsights && Array.isArray(r.highQualityInsights) && r.highQualityInsights.length > 0) {
          let insTotal = 0;
          let insCount = 0;
          r.highQualityInsights.forEach((ins: any) => {
             const txt = ins.analysis || ins.text || "";
             if (!txt) return;
             const { score } = analyzeSentimentText(txt);
             insTotal += score;
             insCount++;
          });
          if (insCount > 0) calculatedAudienceScore = Math.round(insTotal / insCount);
      }
      // Fallback Text Analysis for Audience Mode
      else if (isAudienceScan && textForAnalysis) {
          const { score } = analyzeSentimentText(textForAnalysis);
          calculatedAudienceScore = score;
      }

      if (calculatedAudienceScore !== null) {
          totalAudienceScore += calculatedAudienceScore;
          audienceCount++;
      }

      const scanTopics = safeGet(r, ['topics', 'Topics']) || [];
      if (Array.isArray(scanTopics)) allTopics.push(...scanTopics);
    });

    const critics_score = criticCount > 0 ? Math.round(totalCriticScore / criticCount) : 0;
    const audience_score = audienceCount > 0 ? Math.round(totalAudienceScore / audienceCount) : 0;

    // Consensus Text Logic
    let consensus_line = "Pending Analysis";
    if (criticCount > 0) {
        if (critics_score >= 85) consensus_line = "Universal Acclaim";
        else if (critics_score >= 70) consensus_line = "Generally Favorable";
        else if (critics_score >= 50) consensus_line = "Mixed or Average";
        else if (critics_score >= 30) consensus_line = "Generally Unfavorable";
        else consensus_line = "Overwhelming Dislike";
    }

    // Topics Extraction
    const topicFreq: Record<string, number> = {};
    const stopWords = ['movie', 'film', 'review', 'video', 'story', 'plot', 'watch', 'cinema', 'really', 'actor', 'acting', 'director', 'screenplay'];
    allTopics.forEach(t => {
      const lowerT = String(t).toLowerCase().replace(/[^a-z\s]/g, '').trim();
      if(!lowerT || stopWords.includes(lowerT) || lowerT.length < 3) return;
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3) 
      .map(([t]) => t.charAt(0).toUpperCase() + t.slice(1));

    // Construct Metadata purely from DB
    const metadata: MovieMetadata = {
        release_date: releaseDate, // Used oldest scan date as release date
        genres: [] // No external genre data
    };

    let poster_url = "";
    // STRICT: Only use Scan Thumbnails
    const validScan = movieScans.find(s => s.thumbnail && s.thumbnail.startsWith('http'));
    if (validScan) poster_url = validScan.thumbnail || "";
    
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
