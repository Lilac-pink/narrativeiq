import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { mockData } from "../mockData";
import { checkHealth, logout, isLoggedIn } from "../services/api";
import { AnalysisResult } from "../types";
import EpisodeCard from "../components/EpisodeCard";
import EmotionalArcGraph from "../components/EmotionalArcGraph";
import CliffhangerPanel from "../components/CliffhangerPanel";
import RetentionHeatmap from "../components/RetentionHeatmap";
import ContinuityTracker from "../components/ContinuityTracker";
import SuggestionPanel from "../components/SuggestionPanel";
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger,
} from "@/components/ui/sidebar";
import { LayoutGrid, TrendingUp, Anchor, Grid3x3, GitBranch, Lightbulb, ArrowLeft, LogOut, History } from "lucide-react";

const sections = [
  { id: "episodes",      label: "Episodes",       icon: LayoutGrid },
  { id: "emotional-arc", label: "Emotional Arc",  icon: TrendingUp },
  { id: "cliffhangers",  label: "Cliffhangers",   icon: Anchor },
  { id: "retention",     label: "Retention",      icon: Grid3x3 },
  { id: "continuity",    label: "Continuity",     icon: GitBranch },
  { id: "suggestions",   label: "Suggestions",    icon: Lightbulb },
];

// ── Fallback: generate basic retention heatmap from episode scores ──────────
function buildFallbackRetention(episodes: AnalysisResult["episodes"]) {
  return episodes.map((ep) => ({
    episode_number: ep.episode_number,
    blocks: [
      { time_block: "0–15s",  risk_level: ep.drop_off_probability > 0.5 ? "high" : "low"    as any, reason: "Opening hook" },
      { time_block: "15–30s", risk_level: ep.emotion_score < 0.3 ? "high" : "medium"        as any, reason: "Emotional build" },
      { time_block: "30–45s", risk_level: "medium"                                           as any, reason: "Mid-episode tension" },
      { time_block: "45–60s", risk_level: ep.cliffhanger_score > 7 ? "low" : "high"         as any, reason: "Act break" },
      { time_block: "60–75s", risk_level: ep.continuity_score < 0.7 ? "high" : "medium"     as any, reason: "Story momentum" },
      { time_block: "75–90s", risk_level: ep.drop_off_probability > 0.4 ? "high" : "low"    as any, reason: "Closing hook strength" },
    ],
  }));
}

// ── Fallback: generate suggestions from episode scores ─────────────────────
function buildFallbackSuggestions(episodes: AnalysisResult["episodes"]) {
  const suggestions = [];
  let priority = 1;
  for (const ep of episodes) {
    if (ep.drop_off_probability > 0.4) {
      suggestions.push({
        priority: priority++,
        episode: ep.episode_number,
        category: "Retention",
        suggestion: `Episode ${ep.episode_number} has a high drop-off risk (${Math.round(ep.drop_off_probability * 100)}%). Strengthen the opening hook and tighten the mid-episode pacing to keep viewers engaged.`,
        impact_score: Math.round(ep.drop_off_probability * 10 * 10) / 10,
      });
    }
    if (ep.cliffhanger_score < 6) {
      suggestions.push({
        priority: priority++,
        episode: ep.episode_number,
        category: "Cliffhanger",
        suggestion: `Episode ${ep.episode_number} ends with a weak cliffhanger (${ep.cliffhanger_score}/10). Add a shocking revelation or unresolved threat in the final 30 seconds to compel viewers to continue.`,
        impact_score: Math.round((10 - ep.cliffhanger_score) * 10) / 10,
      });
    }
    if (ep.emotion_score < 0.35) {
      suggestions.push({
        priority: priority++,
        episode: ep.episode_number,
        category: "Emotional Arc",
        suggestion: `Episode ${ep.episode_number} has low emotional intensity (${Math.round(ep.emotion_score * 100)}%). Deepen character vulnerability or raise personal stakes to create a stronger emotional response.`,
        impact_score: Math.round((1 - ep.emotion_score) * 8 * 10) / 10,
      });
    }
    if (ep.continuity_score < 0.75) {
      suggestions.push({
        priority: priority++,
        episode: ep.episode_number,
        category: "Continuity",
        suggestion: `Episode ${ep.episode_number} has continuity issues (score: ${Math.round(ep.continuity_score * 100)}%). Review character behaviour and plot threads carried over from previous episodes.`,
        impact_score: Math.round((1 - ep.continuity_score) * 7 * 10) / 10,
      });
    }
  }
  return suggestions.sort((a, b) => b.impact_score - a.impact_score).slice(0, 8);
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState("episodes");
  const [isLive, setIsLive] = useState(false);
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [userName, setUserName] = useState("");

  useEffect(() => {
    checkHealth().then(setIsLive);
    const stored = sessionStorage.getItem("narrativeiq_result");
    if (stored) {
      try { setData(JSON.parse(stored)); } catch { setData(mockData); }
    } else {
      setData(mockData);
    }
    const user = localStorage.getItem("narrativeiq_user");
    if (user) {
      try { setUserName(JSON.parse(user).name?.split(" ")[0] || ""); } catch {}
    }
  }, []);

  const handleLogout = () => {
    logout();
    sessionStorage.removeItem("narrativeiq_result");
    navigate("/login");
  };

  if (!data) return null;

  // ── Fix empty retention / suggestions using fallback generators ──────────
  const retentionData = data.retention_heatmap?.length > 0
    ? data.retention_heatmap
    : buildFallbackRetention(data.episodes);

  const suggestionsData = data.suggestions?.length > 0
    ? data.suggestions
    : buildFallbackSuggestions(data.episodes);

  // ── Fix emotional arc — ensure curves are populated ──────────────────────
  const arcData = {
    ...data.emotional_arc,
    actual_curve: data.emotional_arc?.actual_curve?.length > 0
      ? data.emotional_arc.actual_curve
      : data.episodes.map(ep => ep.emotion_score),
    ideal_curve: data.emotional_arc?.ideal_curve?.length > 0
      ? data.emotional_arc.ideal_curve
      : data.episodes.map((_, i) => Math.round((0.3 + 0.6 * (i / Math.max(data.total_episodes - 1, 1))) * 100) / 100),
    flat_zones: data.emotional_arc?.flat_zones || [],
  };

  const renderSection = () => {
    switch (activeSection) {
      case "episodes":
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.episodes.map((ep) => (
              <EpisodeCard key={ep.episode_number} episode={ep} />
            ))}
          </div>
        );
      case "emotional-arc":
        return <EmotionalArcGraph arc={arcData} totalEpisodes={data.total_episodes} />;
      case "cliffhangers":
        return <CliffhangerPanel breakdowns={data.cliffhanger_breakdown} />;
      case "retention":
        return <RetentionHeatmap episodes={retentionData} />;
      case "continuity":
        return <ContinuityTracker issues={data.continuity_issues ?? []} episodes={data.episodes} />;
      case "suggestions":
        return <SuggestionPanel 
          suggestions={suggestionsData} 
          analysisData={data}
          onEpisodesUpdated={(eps) => setData(prev => prev ? {...prev, episodes: eps} : prev)}
          onPipelineUpdated={(pipeline) => setData(prev => prev ? {...prev, ...pipeline} : prev)}
        />;
      default:
        return null;
    }
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        <Sidebar collapsible="icon">
          <SidebarContent className="pt-4">
            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu>
                  {sections.map((s) => (
                    <SidebarMenuItem key={s.id}>
                      <SidebarMenuButton
                        onClick={() => setActiveSection(s.id)}
                        className={`${activeSection === s.id ? "bg-sidebar-accent text-sidebar-accent-foreground" : ""}`}
                      >
                        <s.icon className="w-4 h-4" />
                        <span>{s.label}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>

        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-14 flex items-center justify-between border-b border-border px-4 shrink-0">
            <div className="flex items-center gap-3">
              <SidebarTrigger />
              <button onClick={() => navigate("/")} className="text-muted-foreground hover:text-foreground transition-colors">
                <ArrowLeft className="w-4 h-4" />
              </button>
              <h1 className="text-lg font-semibold text-foreground truncate">{data.series_title}</h1>
              <span className="text-xs text-muted-foreground">({data.total_episodes} episodes)</span>
            </div>

            <div className="flex items-center gap-3">
              <span className={`w-2 h-2 rounded-full ${isLive ? "bg-green-500" : "bg-muted-foreground"}`} />
              <span className="text-xs text-muted-foreground">{isLive ? "Live Data" : "Mock Data"}</span>

              {isLoggedIn() && (
                <>
                  <button
                    onClick={() => navigate("/history")}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <History className="w-3.5 h-3.5" />
                    {userName && <span>{userName}</span>}
                  </button>
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Sign out</span>
                  </button>
                </>
              )}
            </div>
          </header>

          <main className="flex-1 p-6 overflow-y-auto">
            {renderSection()}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
