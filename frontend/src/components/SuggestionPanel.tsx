import { useState, useRef, useEffect } from "react";
import { Suggestion, AnalysisResult } from "../types";
import { API_BASE } from "../config";
import { Sparkles, Send, Loader2, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  updatedEpisodes?: AnalysisResult["episodes"];
}

interface Props {
  suggestions: Suggestion[];
  analysisData: AnalysisResult;
  onEpisodesUpdated?: (episodes: AnalysisResult["episodes"]) => void;
  onPipelineUpdated?: (pipeline: Partial<AnalysisResult>) => void;
}

export default function SuggestionPanel({ suggestions, analysisData, onEpisodesUpdated }: Props) {
  const sorted = [...suggestions].sort((a, b) => a.priority - b.priority);
  // Keep a local copy of pipeline state so subsequent messages always send fresh data
  const [localPipeline, setLocalPipeline] = useState<AnalysisResult>(analysisData);

  // Sync if parent passes new analysisData (e.g. on first load)
  useEffect(() => {
    setLocalPipeline(analysisData);
  }, [analysisData.series_title]);

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I am your story consultant AI. I have analysed " + analysisData.series_title + " and generated the suggestions above.\n\nYou can ask me to rewrite any episode, suggest structural changes, or explore what-if scenarios. Try something like:\n- Rewrite episode 2 with a stronger cliffhanger\n- Make episode 3 more emotionally intense\n- What if the protagonist betrays the antagonist in episode 4?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedSuggestion, setExpandedSuggestion] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat/story`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg,
          series_title: localPipeline.series_title,
          episodes: localPipeline.episodes,
          suggestions: localPipeline.suggestions?.length ? localPipeline.suggestions : suggestions,
          full_pipeline: {
            series_title: localPipeline.series_title,
            total_episodes: localPipeline.total_episodes,
            episodes: localPipeline.episodes,
            emotional_arc: localPipeline.emotional_arc,
            cliffhanger_breakdown: localPipeline.cliffhanger_breakdown,
            retention_heatmap: localPipeline.retention_heatmap,
            continuity_issues: localPipeline.continuity_issues,
          },
        }),
      });

      const data = await res.json();
      const assistantMsg: Message = {
        role: "assistant",
        content: data.reply,
        updatedEpisodes: data.updated_episodes || undefined,
      };

      setMessages(prev => [...prev, assistantMsg]);

      // Apply full rescored pipeline if available
      if (data.updated_pipeline) {
        // Update local state immediately so next message uses fresh data
        const merged = { ...localPipeline, ...data.updated_pipeline };
        setLocalPipeline(merged);
        if (onPipelineUpdated) onPipelineUpdated(data.updated_pipeline);
        // Persist to session
        try {
          const stored = sessionStorage.getItem("narrativeiq_result");
          const base = stored ? JSON.parse(stored) : {};
          sessionStorage.setItem("narrativeiq_result", JSON.stringify({ ...base, ...data.updated_pipeline }));
        } catch {}
      } else if (data.updated_episodes) {
        const merged = { ...localPipeline, episodes: data.updated_episodes };
        setLocalPipeline(merged);
        if (onEpisodesUpdated) onEpisodesUpdated(data.updated_episodes);
        try {
          const stored = sessionStorage.getItem("narrativeiq_result");
          const base = stored ? JSON.parse(stored) : {};
          sessionStorage.setItem("narrativeiq_result", JSON.stringify({ ...base, episodes: data.updated_episodes }));
        } catch {}
      }
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "Sorry, I could not connect to the backend. Make sure the server is running on port 8080.",
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetChat = () => {
    setMessages([{
      role: "assistant",
      content: "Chat reset. I am ready to help you refine " + analysisData.series_title + ". What would you like to change?",
    }]);
  };

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">AI Suggestions</h2>
        {sorted.length === 0 && (
          <p className="text-sm text-muted-foreground">No suggestions generated yet.</p>
        )}
        {sorted.map((s) => (
          <div
            key={s.priority}
            className={"glass-card transition-all cursor-pointer" + (s.impact_score > 8 ? " border-primary/40 glow-impact" : "")}
            onClick={() => setExpandedSuggestion(expandedSuggestion === s.priority ? null : s.priority)}
          >
            <div className="p-4 flex items-center gap-3 flex-wrap">
              <span className="w-7 h-7 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-bold shrink-0">
                {s.priority}
              </span>
              <span className="px-2 py-0.5 text-xs rounded-full bg-accent/15 text-accent font-medium">
                {s.episode > 0 ? "Ep " + s.episode : "Series"}
              </span>
              <span className="px-2 py-0.5 text-xs rounded-full bg-secondary text-secondary-foreground font-medium">
                {s.category}
              </span>
              <span className="ml-auto text-sm font-semibold text-foreground">{s.impact_score}/10</span>
              {expandedSuggestion === s.priority
                ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
                : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
            </div>
            {expandedSuggestion === s.priority && (
              <div className="px-4 pb-4 space-y-3 border-t border-border pt-3">
                <p className="text-sm text-muted-foreground leading-relaxed">{s.suggestion}</p>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setInput("Apply this suggestion to episode " + s.episode + ": " + s.suggestion);
                  }}
                  className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
                >
                  <Sparkles className="w-3 h-3" />
                  Send to AI consultant
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="glass-card flex flex-col" style={{ height: "520px" }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <span className="text-sm font-semibold text-foreground">Story Consultant AI</span>
            <span className="text-xs text-muted-foreground">— rewrites episodes on demand</span>
          </div>
          <button onClick={resetChat} className="text-muted-foreground hover:text-foreground transition-colors">
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={"flex " + (msg.role === "user" ? "justify-end" : "justify-start")}>
              <div className={"max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap " + (msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary text-foreground")}>
                {msg.content}
                {msg.updatedEpisodes && (
                  <div className="mt-2 pt-2 border-t border-border/50">
                    <span className="text-xs text-accent flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      Episodes updated — check the Episodes tab
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-secondary rounded-xl px-4 py-3 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-accent" />
                <span className="text-sm text-muted-foreground">Thinking...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="p-3 border-t border-border shrink-0">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask me to rewrite an episode, change the tone, add a twist..."
              rows={2}
              className="flex-1 bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="bg-primary hover:bg-primary/80 disabled:opacity-40 text-primary-foreground rounded-lg px-3 flex items-center justify-center transition-colors shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground mt-1.5 pl-1">Press Enter to send · Shift+Enter for new line</p>
        </div>
      </div>
    </div>
  );
}
