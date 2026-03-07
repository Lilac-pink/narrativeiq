export interface Episode {
  episode_number: number;
  title: string;
  plot_beat: string;
  characters: string[];
  locations: string[];
  emotion_score: number;
  drop_off_probability: number;
  cliffhanger_score: number;
  continuity_score: number;
}

export interface CliffhangerCriterion {
  criterion: string;
  pass: boolean;
  reason: string;
}

export interface CliffhangerBreakdown {
  episode_number: number;
  title: string;
  score: number;
  criteria: CliffhangerCriterion[];
}

export interface HeatmapBlock {
  time_block: string;
  risk_level: "low" | "medium" | "high";
  reason: string;
}

export interface RetentionEpisode {
  episode_number: number;
  blocks: HeatmapBlock[];
}

export interface ContinuityIssue {
  transition: string;
  similarity_score: number;
  severity: "medium" | "high";
  issue: string;
}

export interface Suggestion {
  priority: number;
  episode: number;
  category: string;
  suggestion: string;
  impact_score: number;
}

export interface EmotionalArc {
  ideal_curve: number[];
  actual_curve: number[];
  flat_zones: number[];
}

export interface AnalysisResult {
  series_title: string;
  total_episodes: number;
  episodes: Episode[];
  emotional_arc: EmotionalArc;
  cliffhanger_breakdown: CliffhangerBreakdown[];
  retention_heatmap: RetentionEpisode[];
  continuity_issues: ContinuityIssue[];
  suggestions: Suggestion[];
}

// FIX: backend returns "running" not "processing"
export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "complete" | "failed";  // ← "running" not "processing"
  started_at: number;
  completed_at: number | null;
  error: string | null;
}

// Auth types
export interface User {
  id: string;
  name: string;
  email: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isLoggedIn: boolean;
}

export interface StoryHistoryItem {
  id: string;
  series_title: string;
  status: string;
  episode_count: number;
  created_at: string;
  completed_at: string | null;
}
