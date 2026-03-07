import { AnalysisResult } from "./types";

export const mockData: AnalysisResult = {
  series_title: "The Forgotten Signal",
  total_episodes: 5,
  episodes: [
    {
      episode_number: 1, title: "Dead Air",
      plot_beat: "A radio operator picks up a signal from a station that closed 30 years ago.",
      characters: ["Maya Chen", "Director Osei", "The Voice"],
      locations: ["Radio Tower 7", "Government Building"],
      emotion_score: 0.42, drop_off_probability: 0.18, cliffhanger_score: 7.2, continuity_score: 0.91,
    },
    {
      episode_number: 2, title: "Interference",
      plot_beat: "Maya traces the signal and finds coordinates leading to a sealed bunker.",
      characters: ["Maya Chen", "Dr. Reeves", "The Voice"],
      locations: ["Radio Tower 7", "Bunker Entrance", "City Archives"],
      emotion_score: 0.61, drop_off_probability: 0.24, cliffhanger_score: 8.1, continuity_score: 0.87,
    },
    {
      episode_number: 3, title: "Static",
      plot_beat: "Inside the bunker, Maya discovers encrypted files linking Director Osei to the original station.",
      characters: ["Maya Chen", "Director Osei", "Dr. Reeves"],
      locations: ["Bunker Interior", "Government Building"],
      emotion_score: 0.58, drop_off_probability: 0.41, cliffhanger_score: 5.4, continuity_score: 0.72,
    },
    {
      episode_number: 4, title: "Frequency",
      plot_beat: "Director Osei confronts Maya. The Voice reveals it is an AI left running since 1991.",
      characters: ["Maya Chen", "Director Osei", "The Voice", "Dr. Reeves"],
      locations: ["Government Building", "Bunker Interior"],
      emotion_score: 0.79, drop_off_probability: 0.29, cliffhanger_score: 8.8, continuity_score: 0.85,
    },
    {
      episode_number: 5, title: "Broadcast",
      plot_beat: "Maya must choose between silencing the AI or letting it expose the government secrets.",
      characters: ["Maya Chen", "Director Osei", "The Voice"],
      locations: ["Radio Tower 7", "Bunker Interior", "City Broadcast Hub"],
      emotion_score: 0.91, drop_off_probability: 0.15, cliffhanger_score: 9.3, continuity_score: 0.94,
    },
  ],
  emotional_arc: {
    ideal_curve: [0.3, 0.5, 0.65, 0.8, 0.95],
    actual_curve: [0.42, 0.61, 0.58, 0.79, 0.91],
    flat_zones: [3],
  },
  cliffhanger_breakdown: [
    {
      episode_number: 3, title: "Static", score: 5.4,
      criteria: [
        { criterion: "Unresolved question", pass: true, reason: "Encrypted files raise unanswered questions" },
        { criterion: "Emotional stakes raised", pass: false, reason: "No direct threat to Maya in this episode" },
        { criterion: "Character in jeopardy", pass: false, reason: "Maya is not in immediate danger" },
        { criterion: "New information revealed", pass: true, reason: "Osei connection is a new plot thread" },
        { criterion: "Time pressure present", pass: false, reason: "No deadline or urgency established" },
        { criterion: "Scene ends on action beat", pass: true, reason: "Ends on Maya finding a hidden door" },
      ],
    },
  ],
  retention_heatmap: [
    {
      episode_number: 1,
      blocks: [
        { time_block: "0-15s", risk_level: "low", reason: "Strong hook with mystery signal" },
        { time_block: "15-30s", risk_level: "low", reason: "Character introduced with clear goal" },
        { time_block: "30-45s", risk_level: "medium", reason: "Pacing slows during exposition" },
        { time_block: "45-60s", risk_level: "medium", reason: "No new information in this block" },
        { time_block: "60-75s", risk_level: "low", reason: "Tension returns with mysterious interference" },
        { time_block: "75-90s", risk_level: "low", reason: "Cliffhanger lands strongly" },
      ],
    },
    {
      episode_number: 3,
      blocks: [
        { time_block: "0-15s", risk_level: "low", reason: "Picks up directly from bunker entrance" },
        { time_block: "15-30s", risk_level: "medium", reason: "Slow search sequence, low tension" },
        { time_block: "30-45s", risk_level: "high", reason: "Dialogue-heavy, no visual tension" },
        { time_block: "45-60s", risk_level: "high", reason: "Repetitive exposition of known facts" },
        { time_block: "60-75s", risk_level: "medium", reason: "Discovery of files re-engages viewer" },
        { time_block: "75-90s", risk_level: "low", reason: "Hidden door cliffhanger recovers interest" },
      ],
    },
  ],
  continuity_issues: [
    {
      transition: "Episode 2 → Episode 3", similarity_score: 0.72, severity: "medium",
      issue: "Episode 2 ends with Maya outside the bunker entrance but Episode 3 opens with her already inside with no transition shown.",
    },
    {
      transition: "Episode 3 → Episode 4", similarity_score: 0.58, severity: "high",
      issue: "Dr. Reeves disappears after Episode 3 with no explanation and reappears in Episode 4 without acknowledgement.",
    },
  ],
  suggestions: [
    { priority: 1, episode: 3, category: "Pacing", suggestion: "Cut the 30-60s exposition block and replace with a physical discovery to maintain tension.", impact_score: 9.1 },
    { priority: 2, episode: 3, category: "Cliffhanger", suggestion: "Add a time-pressure element — have Maya hear footsteps approaching the bunker.", impact_score: 8.7 },
    { priority: 3, episode: 2, category: "Continuity", suggestion: "Add a 5-second transition shot of Maya bypassing the bunker lock.", impact_score: 7.9 },
    { priority: 4, episode: 3, category: "Character", suggestion: "Show Dr. Reeves leaving with an explicit reason so his Episode 4 return feels earned.", impact_score: 7.4 },
    { priority: 5, episode: 1, category: "Emotional Arc", suggestion: "Lower the opening emotion score slightly by starting with silence before the signal hits.", impact_score: 6.8 },
  ],
};
