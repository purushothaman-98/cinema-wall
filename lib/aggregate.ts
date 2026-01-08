import { Scan, MovieAggregate, MovieMetadata } from '../types';
import { slugify } from './utils';
import { DEFAULT_POSTER } from '../constants';

// --- ROBUST LEXICON MODEL ---

const TIER_S_POSITIVE = ['masterpiece', 'extraordinary', 'phenomenal', 'perfect', '10/10', 'classic', 'breathtaking', 'spectacular', 'landmark', 'top tier', 'goated'];
const TIER_A_POSITIVE = ['excellent', 'amazing', 'great', 'brilliant', 'superb', 'fantastic', 'awesome', 'wonderful', 'highly recommend', 'must watch', 'thrilling'];
const TIER_B_POSITIVE = ['good', 'solid', 'enjoyable', 'fun', 'entertaining', 'decent', 'worth watching', 'fresh', 'engaging', 'satisfying', 'nice'];

const TIER_C_MIXED = ['mixed', 'average', 'okay', 'one time', 'passable', 'mediocre', 'cliché', 'formulaic', 'predictable', 'fine', 'flawed'];

const TIER_D_NEGATIVE = ['bad', 'boring', 'dull', 'slow', 'disappointing', 'weak', 'skippable', 'mess', 'confusing', 'underwhelming', 'generic'];
const TIER_F_NEGATIVE = ['terrible', 'disaster', 'awful', 'waste', 'worst', 'garbage', 'rotten', 'torture', 'unbearable', 'horrible', 'trash', 'cringe'];

// Modifiers that dampen or boost sentiment
const MODIFIERS_DOWN = ['but', 'however', 'although', 'except', 'despite', 'little', 'bit'];
const MODIFIERS_UP = ['very', 'really', 'absolutely', 'extremely', 'highly', 'truly'];

// --- SCORING ENGINE ---

/**
 * Analyzes text and returns a granular score (0-100).
 * This allows "Positive" reviews to range from 70 to 95 based on word choice.
 */
const calculateTextNuance = (text: string): number => {
    if (!text) return 50;
    const lower = text.toLowerCase();
    
    let score = 50;
    let hits = 0;

    // Helper to scan layers
    const scanLayer = (words: string[], impact: number) => {
        let layerHits = 0;
        words.forEach(w => {
            if (lower.includes(w)) {
                score += impact;
                layerHits++;
            }
        });
        return layerHits;
    };

    // Apply Weights
    hits += scanLayer(TIER_S_POSITIVE, 15);  // Massive boost
    hits += scanLayer(TIER_A_POSITIVE, 10);  // Big boost
    hits += scanLayer(TIER_B_POSITIVE, 5);   // Small boost
    
    hits += scanLayer(TIER_C_MIXED, -2);     // Slight drag
    
    hits += scanLayer(TIER_D_NEGATIVE, -8);  // Big drag
    hits += scanLayer(TIER_F_NEGATIVE, -15); // Massive drag

    // If no specific keywords found, return neutral
    if (hits === 0) return 50;

    // Clamp score 0-100
    return Math.max(0, Math.min(100, score));
};

/**
 * Combines the explicit label (Anchor) with the text nuance (Shift).
 * @param sentiment The label (Positive/Negative/etc)
 * @param text The summary text
 * @returns An integer score (e.g., 76)
 */
const getHybridScore = (sentiment: string | undefined, text: string): number => {
    let anchor = 50; // Default Neutral

    // 1. Establish Anchor based on explicit label
    const s = (sentiment || '').toLowerCase();
    if (s.includes('positive')) anchor = 75;
    else if (s.includes('negative')) anchor = 35;
    else if (s.includes('mixed')) anchor = 55;
    else if (s.includes('neutral')) anchor = 50;

    // 2. Calculate Nuance from text (0-100 scale, usually centers around 50)
    const nuanceScore = calculateTextNuance(text);
    const nuanceShift = nuanceScore - 50; // e.g., +15 or -10

    // 3. Apply Shift to Anchor
    // We weight the Anchor heavier (70%) because the label is the reviewer's final verdict,
    // but we allow the text to sway it (30%) to create granularity.
    let finalScore = anchor + (nuanceShift * 0.8);

    // 4. Hard Clamps based on Label to prevent "Good" reviews becoming "Rotten"
    if (s.includes('positive')) finalScore = Math.max(60, finalScore);
    if (s.includes('negative')) finalScore = Math.min(49, finalScore);

    return Math.round(Math.max(10, Math.min(98, finalScore)));
};

// --- AGGREGATION LOGIC ---

export async function aggregateScans(scans: Scan[], fetchMeta = false): Promise<MovieAggregate[]> {
  const grouped: Record<string, Scan[]> = {};

  scans.forEach(scan => {
    const key = scan.subject_name.trim();
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(scan);
  });

  const aggregates: MovieAggregate[] = [];

  for (const [subject, movieScans] of Object.entries(grouped)) {
    const uniqueReviewers = new Set(movieScans.map(s => s.reviewer_name)).size;
    
    // Sort by date desc
    movieScans.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    
    // Identify Primary Scan (Best Thumbnail + Earliest Date) for Poster/Release Date
    const chronologicalScans = [...movieScans].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    const primaryScan = chronologicalScans.find(s => s.thumbnail && s.thumbnail.startsWith('http')) || chronologicalScans[0];

    const releaseDate = primaryScan.created_at;
    const lastScanned = movieScans[0].created_at; 

    // --- ACCUMULATORS ---
    let criticSum = 0;
    let criticCount = 0;
    
    let audienceSum = 0;
    let audienceCount = 0;

    const allTopics: string[] = [];

    movieScans.forEach(scan => {
      const r = scan.result || {};
      const mode = (scan.mode || 'REVIEWER').toUpperCase();
      const isCommentsMode = mode === 'COMMENTS';

      // Gather Text for Analysis
      const summaryText = r.overallSummary || r.summary || r.sentimentDescription || "";
      const sentimentLabel = r.sentiment || 'Neutral';

      // 1. CALCULATE CRITIC SCORE (Source: Reviewer Video)
      if (!isCommentsMode) {
          const score = getHybridScore(sentimentLabel, summaryText);
          criticSum += score;
          criticCount++;
      }

      // 2. CALCULATE AUDIENCE SCORE (Source: High Quality Insights OR Inference)
      
      // Method A: "The Voting Booth" - Use High Quality Insights as individual votes
      // This is the most accurate method as it uses actual comment clusters
      if (r.highQualityInsights && Array.isArray(r.highQualityInsights) && r.highQualityInsights.length > 0) {
          r.highQualityInsights.forEach((insight: any) => {
              const txt = insight.analysis || insight.text || "";
              if (!txt) return;
              
              // Comments don't have labels, so we rely purely on text nuance
              // We boost the base calculation because fans tend to be hyperbolic
              let voteScore = calculateTextNuance(txt);
              
              // Fan bias adjustment: Fans rarely rate "Average". They usually love or hate.
              // Push scores away from 50.
              if (voteScore > 60) voteScore += 5; 
              if (voteScore < 40) voteScore -= 5;

              audienceSum += voteScore;
              audienceCount++;
          });
      } 
      // Method B: "The Inference" - If no comments scanned, infer audience reaction from Reviewer's description of the film
      else {
          let inferredScore = getHybridScore(sentimentLabel, summaryText);
          
          // Apply "Audience Bias" based on keywords in the review
          const lowerSum = summaryText.toLowerCase();
          
          // Factor: Lag / Length (Audience hates slow movies more than critics)
          if (lowerSum.includes('lag') || lowerSum.includes('slow') || lowerSum.includes('drag')) {
              inferredScore -= 10; 
          }
          // Factor: Theatrical Moments (Audience loves hype more than critics)
          if (lowerSum.includes('goosebumps') || lowerSum.includes('celebration') || lowerSum.includes('theatre') || lowerSum.includes('mass')) {
              inferredScore += 12;
          }
          // Factor: Logic (Audience cares less about logic holes in action movies)
          if (lowerSum.includes('logic') || lowerSum.includes('brain')) {
              inferredScore += 5; // Critics deduct for this, add it back for audience
          }

          audienceSum += Math.min(100, Math.max(0, inferredScore));
          audienceCount++;
      }

      // Gather Topics
      const scanTopics = r.topics || [];
      if (Array.isArray(scanTopics)) allTopics.push(...scanTopics);
    });

    // --- FINAL AGGREGATION ---
    const critics_score = criticCount > 0 ? Math.round(criticSum / criticCount) : 0;
    const audience_score = audienceCount > 0 ? Math.round(audienceSum / audienceCount) : 0;

    // Consensus Text Logic
    let consensus_line = "Pending Analysis";
    if (criticCount > 0) {
        if (critics_score >= 90) consensus_line = "Universal Acclaim";
        else if (critics_score >= 80) consensus_line = "Must Watch";
        else if (critics_score >= 70) consensus_line = "Generally Favorable";
        else if (critics_score >= 60) consensus_line = "Decent Watch";
        else if (critics_score >= 50) consensus_line = "Mixed or Average";
        else if (critics_score >= 35) consensus_line = "Generally Unfavorable";
        else consensus_line = "Disaster";
    }

    // Topics Extraction
    const topicFreq: Record<string, number> = {};
    const stopWords = ['movie', 'film', 'review', 'video', 'story', 'plot', 'watch', 'cinema', 'really', 'actor', 'acting', 'director', 'screenplay', 'performance'];
    allTopics.forEach(t => {
      const lowerT = String(t).toLowerCase().replace(/[^a-z\s]/g, '').trim();
      if(!lowerT || stopWords.includes(lowerT) || lowerT.length < 3) return;
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3) 
      .map(([t]) => t.charAt(0).toUpperCase() + t.slice(1));

    // Metadata
    const metadata: MovieMetadata = {
        release_date: releaseDate,
        genres: [] 
    };

    let poster_url = primaryScan.thumbnail || "";
    if (!poster_url || !poster_url.startsWith('http')) poster_url = DEFAULT_POSTER;

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