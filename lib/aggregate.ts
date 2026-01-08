import { Scan, MovieAggregate, MovieMetadata } from '../types';
import { slugify } from './utils';
import { DEFAULT_POSTER } from '../constants';

// --- KOLLYWOOD / INDIAN CINEMA LEXICON ---

// "Sambavam" Tier - Absolute Peak
const TIER_S_GOD = ['masterpiece', 'vera level', 'sambavam', 'cult classic', 'industry hit', 'perfect', 'blast', 'extraordinary', 'world class', 'goated', 'peak cinema'];

// "Mass" Tier - High Energy / Theatre Experience
const TIER_A_MASS = ['goosebumps', 'fire', 'thala', 'thalapathy', 'superstar', 'celebration', 'festival', 'adrenalin', 'theatre experience', 'banger', 'on loop', 'hukum', 'engaging', 'racy'];

// "Good" Tier - Solid Watch
const TIER_B_GOOD = ['good', 'neat', 'clean', 'emotional', 'gripping', 'solid', 'super', 'enjoyable', 'worth', 'screenplay', 'comeback'];

// "Mid" Tier - The "One Time Watch" Trap
const TIER_C_MID = ['one time watch', 'average', 'mixed', 'okay', 'decent', 'passable', 'template', 'predictable', 'usual', 'commercial', 'pass time'];

// "Lag" Tier - The Audience Killer
const TIER_D_BAD = ['lag', 'drag', 'slow', 'boring', 'lengthy', 'flat', 'disappointed', 'weak', 'generic', 'logic', 'logicless', 'old wine'];

// "Cringe" Tier - Disaster
const TIER_F_DISASTER = ['cringe', 'serial', 'headache', 'torture', 'worst', 'waste', 'terrible', 'horrible', 'irritating', 'outdated', 'mockery'];

// --- SCORING ENGINE ---

/**
 * Analyzes text specifically for Indian Cinema nuances.
 * @param text The review summary or comment
 * @param isAudience If true, prioritizes "Mass" elements over "Logic"
 */
const calculateIndianCinemaScore = (text: string, isAudience: boolean): number => {
    if (!text) return 50;
    const lower = text.toLowerCase();
    
    // Start at a neutral 50
    let score = 50; 
    let detectedKeywords = 0;

    const scan = (words: string[], impact: number) => {
        words.forEach(w => {
            if (lower.includes(w)) {
                score += impact;
                detectedKeywords++;
            }
        });
    };

    // 1. "One Time Watch" Check (The Great Equalizer)
    // If a movie is explicitly called "one time watch", it rarely exceeds 65 or drops below 45.
    if (lower.includes('one time watch') || lower.includes('once watchable')) {
        return isAudience ? 58 : 52;
    }

    // 2. Apply Tier Weights
    if (isAudience) {
        // Audience values Hype/Mass more
        scan(TIER_S_GOD, 20);
        scan(TIER_A_MASS, 15); // "Goosebumps" matters more to fans
        scan(TIER_B_GOOD, 8);
        scan(TIER_C_MID, -2);
        scan(TIER_D_BAD, -12); // "Lag" hurts audience score massively
        scan(TIER_F_DISASTER, -20);
    } else {
        // Critics value Making/Screenplay more
        scan(TIER_S_GOD, 15);
        scan(TIER_A_MASS, 5);  // Critics care less about "Mass"
        scan(TIER_B_GOOD, 10); // Critics like "Neat/Gripping"
        scan(TIER_C_MID, -5);
        scan(TIER_D_BAD, -10);
        scan(TIER_F_DISASTER, -15);
    }

    // 3. Contextual Adjustments
    
    // The "Lag" Factor: Even good movies lose points if they lag
    if (lower.includes('second half lag') || lower.includes('lengthy')) {
        score -= isAudience ? 15 : 10;
    }

    // The "Family" Safety Net: Family movies rarely flop with audience
    if (lower.includes('family audience') || lower.includes('kids')) {
        score += isAudience ? 10 : 5;
    }

    // The "Logic" Factor: Critics hate no logic, Fans often forgive it
    if (lower.includes('logic')) {
        if (!isAudience) score -= 8; // Critics penalize
        // Audience doesn't penalize logic unless it's boring
    }

    // 4. Default drift if no keywords found
    if (detectedKeywords === 0) return 50;

    return Math.max(10, Math.min(98, score));
};

const getHybridScore = (sentiment: string | undefined, text: string, isAudience: boolean): number => {
    // 1. Base Anchor from Label (If available)
    let anchor = 50;
    const s = (sentiment || '').toLowerCase();
    
    // Adjusted Anchors for Indian Context
    if (s.includes('positive')) anchor = 75;
    else if (s.includes('negative')) anchor = 35; // Indian critics are harsh when negative
    else if (s.includes('mixed')) anchor = 55;    // Mixed usually means "Average"
    else if (s.includes('neutral')) anchor = 50;

    // 2. Calculate Contextual Shift
    const calculatedScore = calculateIndianCinemaScore(text, isAudience);
    
    // 3. Merge: 
    // If Audience: Trust the text (feelings) more than the label.
    // If Critic: Trust the label (verdict) more than the text.
    const blendFactor = isAudience ? 0.7 : 0.4; // How much text overrides label
    
    let finalScore = (anchor * (1 - blendFactor)) + (calculatedScore * blendFactor);

    // 4. Sanity Clamps
    if (s.includes('positive')) finalScore = Math.max(60, finalScore);
    if (s.includes('negative')) finalScore = Math.min(50, finalScore);

    return Math.round(finalScore);
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
    movieScans.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    
    const chronologicalScans = [...movieScans].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    const primaryScan = chronologicalScans.find(s => s.thumbnail && s.thumbnail.startsWith('http')) || chronologicalScans[0];

    const releaseDate = primaryScan.created_at;
    const lastScanned = movieScans[0].created_at; 

    // Accumulators
    let criticSum = 0;
    let criticCount = 0;
    let audienceSum = 0;
    let audienceCount = 0;
    const allTopics: string[] = [];

    movieScans.forEach(scan => {
      const r = scan.result || {};
      const mode = (scan.mode || 'REVIEWER').toUpperCase();
      const isCommentsMode = mode === 'COMMENTS';

      const summaryText = r.overallSummary || r.summary || r.sentimentDescription || "";
      const sentimentLabel = r.sentiment || 'Neutral';

      // --- CRITIC CALCULATION ---
      if (!isCommentsMode) {
          // Critics look for technicality, screenplay, and story
          const score = getHybridScore(sentimentLabel, summaryText, false);
          criticSum += score;
          criticCount++;
          
          // --- AUDIENCE INFERENCE FROM CRITIC (If actual comments missing) ---
          // Critics might hate a "Masala" movie, but they usually admit "Fans will enjoy this".
          // We extract that admission to boost the audience score.
          let inferredAudienceScore = getHybridScore(sentimentLabel, summaryText, true); // Use Audience weighting
          
          // Adjust Inference based on Reviewer's "Fan Service" admission
          const lowerSum = summaryText.toLowerCase();
          if (lowerSum.includes('fan moments') || lowerSum.includes('celebration') || lowerSum.includes('mass')) {
              inferredAudienceScore = Math.max(inferredAudienceScore, 75); // Floor it at 75 if it's a celebration
          }
          if (lowerSum.includes('disconnect') || lowerSum.includes('outdated')) {
              inferredAudienceScore -= 10;
          }

          audienceSum += inferredAudienceScore;
          audienceCount++;
      }

      // --- AUDIENCE CALCULATION (From Real Comments) ---
      if (r.highQualityInsights && Array.isArray(r.highQualityInsights) && r.highQualityInsights.length > 0) {
          r.highQualityInsights.forEach((insight: any) => {
              const txt = insight.analysis || insight.text || "";
              if (!txt) return;
              
              // Pure Text Analysis for comments (No labels usually)
              // We prioritize "Mass", "Lag", "Super" keywords heavily here
              let voteScore = calculateIndianCinemaScore(txt, true);
              
              // Fan Polarity: Fans rarely rate 50/100. It's either 100 or 0.
              // We stretch the score distribution to reflect this passion.
              if (voteScore > 60) voteScore = Math.min(100, voteScore + 10);
              if (voteScore < 45) voteScore = Math.max(0, voteScore - 10);

              // Overwrite/Add to the inferred score with REAL data (Higher weight)
              audienceSum += (voteScore * 2); // Double weight for actual comments
              audienceCount += 2;
          });
      }

      const scanTopics = r.topics || [];
      if (Array.isArray(scanTopics)) allTopics.push(...scanTopics);
    });

    const critics_score = criticCount > 0 ? Math.round(criticSum / criticCount) : 0;
    const audience_score = audienceCount > 0 ? Math.round(audienceSum / audienceCount) : 0;

    // --- CONSENSUS LINES (Localized) ---
    let consensus_line = "Pending Analysis";
    if (criticCount > 0) {
        if (critics_score >= 90) consensus_line = "Cult Classic";
        else if (critics_score >= 80) consensus_line = "Blockbuster";
        else if (critics_score >= 70) consensus_line = "Super Hit";
        else if (critics_score >= 60) consensus_line = "Decent Watch";
        else if (critics_score >= 50) consensus_line = "Mixed Bag";
        else if (critics_score >= 40) consensus_line = "Below Average";
        else consensus_line = "Disaster";
    }

    // Topics Extraction
    const topicFreq: Record<string, number> = {};
    const stopWords = ['movie', 'film', 'review', 'video', 'story', 'plot', 'watch', 'cinema', 'really', 'actor', 'acting', 'director', 'screenplay', 'performance', 'audience'];
    allTopics.forEach(t => {
      const lowerT = String(t).toLowerCase().replace(/[^a-z\s]/g, '').trim();
      if(!lowerT || stopWords.includes(lowerT) || lowerT.length < 3) return;
      topicFreq[lowerT] = (topicFreq[lowerT] || 0) + 1;
    });
    
    const top_topics = Object.entries(topicFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3) 
      .map(([t]) => t.charAt(0).toUpperCase() + t.slice(1));

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