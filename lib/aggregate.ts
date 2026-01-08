import { Scan, MovieAggregate, MovieMetadata } from '../types';
import { slugify } from './utils';
import { fetchMovieMetadata } from './tmdb';

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

    // 3. Critics Score (Reviewer Sentiment)
    let totalCriticScore = 0;
    let criticCount = 0;

    // 4. Audience Score (Comment Analysis)
    let totalAudienceScore = 0;
    let audienceCount = 0;

    const allTopics: string[] = [];
    const allSentiments: string[] = [];

    movieScans.forEach(scan => {
      const r = scan.result || {};
      
      // Try to find the data in various keys
      const sentimentScore = safeGet(r, ['sentiment_score', 'sentimentScore', 'score', 'rating']);
      const sentimentStr = safeGet(r, ['sentiment', 'Sentiment', 'overall_sentiment']);
      const audienceSentiment = safeGet(r, ['audience_sentiment', 'audienceSentiment', 'audienceScore']);
      const scanTopics = safeGet(r, ['topics', 'Topics', 'keywords']);

      // Calculate Critic Score
      if (typeof sentimentScore === 'number') {
        // Normalize: if score <= 10, multiply by 10. If > 10, assume 100 base.
        let normScore = sentimentScore;
        if (normScore <= 10) normScore *= 10;
        if (normScore > 100) normScore = 100;
        
        totalCriticScore += normScore;
        criticCount++;
      } else if (sentimentStr) {
        // Fallback: derive score from text string if numeric score is missing
        const s = String(sentimentStr).toLowerCase();
        if (s.includes('positive') || s.includes('good') || s.includes('great') || s.includes('excellent')) { totalCriticScore += 90; criticCount++; }
        else if (s.includes('negative') || s.includes('bad') || s.includes('poor') || s.includes('terrible')) { totalCriticScore += 30; criticCount++; }
        else if (s.includes('mixed') || s.includes('average')) { totalCriticScore += 60; criticCount++; }
        else { totalCriticScore += 50; criticCount++; } // Neutral/Other
      }

      // Calculate Audience Score
      if (typeof audienceSentiment === 'number') {
        let normAud = audienceSentiment;
        if (normAud <= 1) normAud *= 100; // Handle decimal 0.85
        if (normAud <= 10) normAud *= 10;
        totalAudienceScore += normAud;
        audienceCount++;
      }

      // Collect topics/consensus seeds
      if (scanTopics && Array.isArray(scanTopics)) allTopics.push(...scanTopics);
      if (sentimentStr) allSentiments.push(String(sentimentStr));
    });

    // Final Calculations
    const critics_score = criticCount > 0 ? Math.round(totalCriticScore / criticCount) : 0;
    const audience_score = audienceCount > 0 ? Math.round(totalAudienceScore / audienceCount) : 0;

    // Consensus Generation
    const positiveCount = allSentiments.filter(s => {
        const lower = s.toLowerCase();
        return lower.includes('positive') || lower.includes('great') || lower.includes('good');
    }).length;
    const negativeCount = allSentiments.filter(s => {
        const lower = s.toLowerCase();
        return lower.includes('negative') || lower.includes('bad') || lower.includes('poor');
    }).length;

    let consensus_line = "No consensus yet.";
    if (movieScans.length === 0) consensus_line = "No reviews available.";
    else if (positiveCount > negativeCount * 2 && positiveCount > 1) consensus_line = "Universal acclaim.";
    else if (positiveCount > negativeCount) consensus_line = "Generally favorable reviews.";
    else if (negativeCount > positiveCount) consensus_line = "Generally unfavorable reviews.";
    else if (allSentiments.length > 0) consensus_line = "Reviews are mixed.";
    
    // Top Topics (Frequency Count)
    const topicFreq: Record<string, number> = {};
    allTopics.forEach(t => {
      const lowerT = String(t).toLowerCase().trim();
      if(!lowerT) return;
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([t]) => t);

    // Metadata Fetching (Server-side)
    let metadata: MovieMetadata | undefined = undefined;
    if (fetchMeta) {
        metadata = await fetchMovieMetadata(subject);
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
      metadata
    });
  }

  return aggregates;
}