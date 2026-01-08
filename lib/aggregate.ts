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
    if (val === undefined || val === null) return null;
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
    
    return 0;
};

const analyzeSentimentText = (text: string): { score: number, label: string } => {
    const lower = text.toLowerCase();
    if (lower.includes('masterpiece') || lower.includes('exceptional')) return { score: 95, label: 'Positive' };
    if (lower.includes('excellent') || lower.includes('must watch') || lower.includes('blockbuster')) return { score: 90, label: 'Positive' };
    if (lower.includes('good') || lower.includes('positive') || lower.includes('hit')) return { score: 75, label: 'Positive' };
    if (lower.includes('average') || lower.includes('mixed') || lower.includes('decent')) return { score: 60, label: 'Mixed' };
    if (lower.includes('bad') || lower.includes('negative') || lower.includes('flop') || lower.includes('boring')) return { score: 40, label: 'Negative' };
    if (lower.includes('terrible') || lower.includes('disaster') || lower.includes('worst')) return { score: 20, label: 'Negative' };
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
      // 1. Explicit Audience Score in DB
      const normAudience = normalizeScore(rawAudience);
      if (normAudience !== null) {
          totalAudienceScore += normAudience;
          audienceCount++;
      }
      // 2. If this is an Audience Scan, the "Main Score" IS the audience score
      else if (isAudienceScan) {
          const normMain = normalizeScore(rawScore);
          if (normMain !== null) {
              totalAudienceScore += normMain;
              audienceCount++;
          } else if (textForAnalysis) {
             const { score } = analyzeSentimentText(textForAnalysis);
             totalAudienceScore += score;
             audienceCount++;
          }
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
    const stopWords = ['movie', 'film', 'review', 'video', 'story', 'plot', 'first', 'half', 'second', 'watch'];
    allTopics.forEach(t => {
      const lowerT = String(t).toLowerCase().replace(/[^a-z\s]/g, '').trim();
      if(!lowerT || stopWords.includes(lowerT) || lowerT.length < 4) return;
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([t]) => t.charAt(0).toUpperCase() + t.slice(1));

    // Metadata & Poster
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