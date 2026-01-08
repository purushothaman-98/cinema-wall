import { Scan, MovieAggregate, MovieMetadata } from '../types';
import { slugify } from './utils';
import { fetchMovieMetadata } from './tmdb';
import { DEFAULT_POSTER, TMDB_BASE_URL } from '../constants';

// Helper to safely extract values regardless of case
const safeGet = (obj: any, keys: string[]) => {
  if (!obj) return undefined;
  for (const key of keys) {
    if (obj[key] !== undefined) return obj[key];
    // Check lowercase version
    const lowerKey = key.toLowerCase();
    const found = Object.keys(obj).find(k => k.toLowerCase() === lowerKey);
    if (found && obj[found] !== undefined) return obj[found];
  }
  return undefined;
};

// Helper to deduce score from text if numeric score is missing
const analyzeSentimentText = (text: string): { score: number, label: string } => {
    const lower = text.toLowerCase();
    
    // Strong Positive
    if (lower.includes('universal acclaim') || lower.includes('masterpiece') || lower.includes('exceptional')) return { score: 95, label: 'Positive' };
    if (lower.includes('highly recommended') || lower.includes('excellent') || lower.includes('must watch')) return { score: 90, label: 'Positive' };
    
    // Positive
    if (lower.includes('positive') || lower.includes('good') || lower.includes('great') || lower.includes('enjoyable') || lower.includes('hit')) return { score: 75, label: 'Positive' };
    
    // Negative
    if (lower.includes('terrible') || lower.includes('disaster') || lower.includes('awful') || lower.includes('waste')) return { score: 20, label: 'Negative' };
    if (lower.includes('negative') || lower.includes('bad') || lower.includes('boring') || lower.includes('poor')) return { score: 40, label: 'Negative' };
    
    // Mixed / Neutral
    if (lower.includes('mixed') || lower.includes('average') || lower.includes('decent') || lower.includes('one time watch')) return { score: 60, label: 'Mixed' };

    return { score: 50, label: 'Neutral' }; // Default
};

export async function aggregateScans(scans: Scan[], fetchMeta = false): Promise<MovieAggregate[]> {
  const grouped: Record<string, Scan[]> = {};

  // Group by Subject Name
  scans.forEach(scan => {
    const key = scan.subject_name;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(scan);
  });

  const aggregates: MovieAggregate[] = [];

  for (const [subject, movieScans] of Object.entries(grouped)) {
    // 1. Reviewer Count
    const uniqueReviewers = new Set(movieScans.map(s => s.reviewer_name)).size;

    // 2. Last Scanned
    const lastScanned = movieScans.reduce((max, s) => 
      new Date(s.created_at) > new Date(max) ? s.created_at : max, 
      movieScans[0].created_at
    );

    // 3. Scores Calculation
    let totalCriticScore = 0;
    let criticCount = 0;
    let totalAudienceScore = 0;
    let audienceCount = 0;

    const allTopics: string[] = [];
    const allSentiments: string[] = [];

    movieScans.forEach(scan => {
      const r = scan.result || {};
      
      // -- READ DATA FROM VARIOUS SCHEMAS --
      // Explicit numeric score (Usually Critic/Reviewer score)
      const explicitScore = safeGet(r, ['sentiment_score', 'sentimentScore', 'score']);
      
      // Text description (DeepAnalysisResult uses 'sentimentDescription' or 'overallSummary')
      const textForAnalysis = safeGet(r, ['sentimentDescription', 'sentiment', 'overallSummary', 'summary']) || "";
      
      // Explicit Audience Score (from comments analysis)
      const explicitAudience = safeGet(r, ['audience_sentiment', 'audienceSentiment']);
      
      // Topics
      const scanTopics = safeGet(r, ['topics', 'Topics']) || []; // Original schema
      const insights = r.highQualityInsights || []; // DeepAnalysisResult schema

      // --- LOGIC: CRITIC vs AUDIENCE ---
      
      // Critic Score: Derived from what the Reviewer said (or the main sentiment of the scan)
      if (typeof explicitScore === 'number') {
         let s = explicitScore;
         if (s <= 10) s *= 10;
         totalCriticScore += s;
         criticCount++;
      } else if (textForAnalysis) {
         // Fallback: Infer critic score from text summary
         const { score, label } = analyzeSentimentText(textForAnalysis);
         totalCriticScore += score;
         criticCount++;
         allSentiments.push(label);
      }

      // Audience Score: Derived from 'audience_sentiment' OR deep analysis of comments
      if (typeof explicitAudience === 'number') {
        let s = explicitAudience;
        if (s <= 1) s *= 100;
        totalAudienceScore += s;
        audienceCount++;
      } else {
        // If we don't have an explicit audience number, but we have a text analysis of comments
        // (DeepAnalysisResult is fundamentally an analysis of comments/audience)
        // We can infer the audience score from the text sentiment if the scan mode implies comment analysis.
        const { score } = analyzeSentimentText(textForAnalysis);
        totalAudienceScore += score;
        audienceCount++;
      }

      // -- AGGREGATE TOPICS --
      if (Array.isArray(scanTopics)) allTopics.push(...scanTopics);
      if (Array.isArray(insights)) {
         insights.forEach((i: any) => {
             const words = i.analysis?.split(' ') || [];
             words.forEach((w: string) => {
                 if(w.length > 5 && /^[a-zA-Z]+$/.test(w)) allTopics.push(w);
             });
         });
      }
    });

    // Final Averages
    const critics_score = criticCount > 0 ? Math.round(totalCriticScore / criticCount) : 0;
    const audience_score = audienceCount > 0 ? Math.round(totalAudienceScore / audienceCount) : 0;

    // Consensus Generation
    const positiveCount = allSentiments.filter(s => s === 'Positive').length;
    const negativeCount = allSentiments.filter(s => s === 'Negative').length;
    
    let consensus_line = "No data available.";
    if (movieScans.length > 0) {
        if (positiveCount > negativeCount) consensus_line = "Generally Favorable.";
        else if (negativeCount > positiveCount) consensus_line = "Generally Unfavorable.";
        else consensus_line = "Reviews are Mixed.";
    }

    // Top Topics
    const topicFreq: Record<string, number> = {};
    const stopWords = ['movie', 'film', 'this', 'that', 'with', 'review', 'about', 'really', 'comment', 'watch', 'video'];
    allTopics.forEach(t => {
      const lowerT = String(t).toLowerCase().replace(/[^a-z]/g, '');
      if(!lowerT || stopWords.includes(lowerT)) return;
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([t]) => t.charAt(0).toUpperCase() + t.slice(1));

    // Metadata Fetching
    let metadata: MovieMetadata | undefined = undefined;
    if (fetchMeta) {
        metadata = await fetchMovieMetadata(subject);
    }

    // --- THUMBNAIL LOGIC ---
    // Priority: TMDB Poster -> First Scan Thumbnail -> Default
    let poster_url = DEFAULT_POSTER;
    
    if (metadata?.poster_path) {
        poster_url = `${TMDB_BASE_URL}${metadata.poster_path}`;
    } else {
        // Fallback to finding a thumbnail from the scans
        const scanWithThumb = movieScans.find(s => s.thumbnail && s.thumbnail.startsWith('http'));
        if (scanWithThumb?.thumbnail) {
            poster_url = scanWithThumb.thumbnail;
        }
    }

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
