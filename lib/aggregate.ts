import { Scan, MovieAggregate, MovieMetadata } from '../types';
import { slugify } from './utils';
import { fetchMovieMetadata } from './tmdb';

// In a real app with massive data, this should be a Materialized View in Postgres.
// For this app, we compute on fetch.

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
      
      // Normalize keys (handle camelCase or snake_case)
      const sentimentScore = typeof r.sentiment_score === 'number' ? r.sentiment_score : (r as any).sentimentScore;
      const sentimentStr = r.sentiment || (r as any).Sentiment;
      const audienceSentiment = typeof r.audience_sentiment === 'number' ? r.audience_sentiment : (r as any).audienceSentiment;
      const scanTopics = r.topics || (r as any).Topics;

      // Calculate Critic Score
      if (typeof sentimentScore === 'number') {
        // Assume score is normalized to 0-100 or 0-10
        totalCriticScore += sentimentScore <= 10 ? sentimentScore * 10 : sentimentScore;
        criticCount++;
      } else if (sentimentStr) {
        const s = sentimentStr.toLowerCase();
        if (s.includes('positive') || s.includes('good') || s.includes('great')) { totalCriticScore += 90; criticCount++; }
        else if (s.includes('negative') || s.includes('bad') || s.includes('poor')) { totalCriticScore += 30; criticCount++; }
        else if (s.includes('mixed')) { totalCriticScore += 60; criticCount++; }
        else { totalCriticScore += 50; criticCount++; } // Neutral/Other
      }

      // Calculate Audience Score
      if (typeof audienceSentiment === 'number') {
        totalAudienceScore += audienceSentiment;
        audienceCount++;
      }

      // Collect topics/consensus seeds
      if (scanTopics && Array.isArray(scanTopics)) allTopics.push(...scanTopics);
      if (sentimentStr) allSentiments.push(sentimentStr);
    });

    // Default scores if no data but reviews exist
    // If we have reviews but no numeric scores, we rely on the derived score from text sentiment
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

    let consensus_line = "Reviews are mixed.";
    if (movieScans.length === 0) consensus_line = "No reviews yet.";
    else if (positiveCount > negativeCount * 2 && positiveCount > 1) consensus_line = "Acclaimed by critics.";
    else if (positiveCount > negativeCount) consensus_line = "Generally favorable.";
    else if (negativeCount > positiveCount) consensus_line = "Generally unfavorable reviews.";
    
    // Top Topics (Frequency Count)
    const topicFreq: Record<string, number> = {};
    allTopics.forEach(t => {
      const lowerT = t.toLowerCase().trim();
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