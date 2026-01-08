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
      
      // Calculate Critic Score
      if (typeof r.sentiment_score === 'number') {
        // Assume score is normalized to 0-100 or 0-10
        totalCriticScore += r.sentiment_score <= 10 ? r.sentiment_score * 10 : r.sentiment_score;
        criticCount++;
      } else if (r.sentiment) {
        if (r.sentiment.toLowerCase() === 'positive') { totalCriticScore += 90; criticCount++; }
        else if (r.sentiment.toLowerCase() === 'negative') { totalCriticScore += 30; criticCount++; }
        else if (r.sentiment.toLowerCase() === 'mixed') { totalCriticScore += 60; criticCount++; }
        else { totalCriticScore += 50; criticCount++; } // Neutral
      }

      // Calculate Audience Score
      if (typeof r.audience_sentiment === 'number') {
        totalAudienceScore += r.audience_sentiment;
        audienceCount++;
      }

      // Collect topics/consensus seeds
      if (r.topics && Array.isArray(r.topics)) allTopics.push(...r.topics);
      if (r.sentiment) allSentiments.push(r.sentiment);
    });

    const critics_score = criticCount > 0 ? Math.round(totalCriticScore / criticCount) : 0;
    const audience_score = audienceCount > 0 ? Math.round(totalAudienceScore / audienceCount) : 0;

    // Simple Consensus Generation (Fallback if no AI summary yet)
    const positiveCount = allSentiments.filter(s => s.toLowerCase() === 'positive').length;
    const negativeCount = allSentiments.filter(s => s.toLowerCase() === 'negative').length;
    let consensus_line = "Reviews are mixed.";
    if (positiveCount > negativeCount * 2) consensus_line = "Acclaimed by critics.";
    else if (negativeCount > positiveCount) consensus_line = "Generally unfavorable reviews.";
    
    // Top Topics (Frequency Count)
    const topicFreq: Record<string, number> = {};
    allTopics.forEach(t => {
      const lowerT = t.toLowerCase();
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([t]) => t);

    // Metadata Fetching (Server-side)
    let metadata: MovieMetadata | undefined = undefined;
    if (fetchMeta) {
        // Note: In a production list view, fetchMeta should be false or batched to avoid rate limits.
        // We handle this in the detail view mostly.
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
