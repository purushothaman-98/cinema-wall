
export interface ScanResult {
  // Original keys
  sentiment?: 'Positive' | 'Negative' | 'Neutral' | 'Mixed';
  sentiment_score?: number; 
  audience_sentiment?: number;
  topics?: string[];
  summary?: string;
  
  // DeepAnalysisResult keys (from the AI generator)
  sentimentDescription?: string;
  overallSummary?: string;
  reviewerStyleAnalysis?: string;
  botDetection?: {
    overallThreatLevel: "NOMINAL" | "ELEVATED" | "CRITICAL";
    coordinatedClusters?: any[];
  };
  highQualityInsights?: {
    username: string;
    text: string;
    analysis: string;
  }[];
  movieMetadata?: {
    releaseMode?: string;
  };
  
  // Legacy/Fallback keys
  is_bot?: boolean;
  bot_probability?: number;
}

export interface Scan {
  id: string;
  created_at: string;
  mode: string;
  subject_name: string;
  reviewer_name: string;
  title: string;
  result: ScanResult | null; // JSON column
  video_url?: string; 
}

export interface MovieMetadata {
  poster_path?: string | null;
  release_date?: string;
  overview?: string;
  backdrop_path?: string | null;
  vote_average?: number;
  genres?: { id: number; name: string }[];
  runtime?: number;
}

export interface MovieAggregate {
  subject_name: string;
  slug: string;
  reviewers_count: number;
  last_scanned: string;
  critics_score: number; // 0-100
  audience_score: number; // 0-100
  consensus_line: string;
  top_topics: string[];
  scans: Scan[];
  metadata?: MovieMetadata;
}

export interface NewsItem {
  id: number;
  created_at: string;
  title: string;
  content: string;
  url?: string;
  image_url?: string;
}

export interface VaultItem {
  id: string;
  created_at: string;
  movie_name: string;
  summary_report: string;
}
