import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getStoryHistory, getStoryResult, deleteStory, isLoggedIn } from "../services/api";
import { StoryHistoryItem } from "../types";
import { Clock, Trash2, ChevronRight, Loader2 } from "lucide-react";

export default function History() {
  const navigate = useNavigate();
  const [stories, setStories] = useState<StoryHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) {
      navigate("/login");
      return;
    }
    getStoryHistory()
      .then(setStories)
      .catch(() => setError("Failed to load history."))
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleLoad = async (storyId: string, status: string) => {
    if (status !== "complete") return;
    try {
      const result = await getStoryResult(storyId);
      sessionStorage.setItem("narrativeiq_result", JSON.stringify(result));
      navigate("/dashboard");
    } catch {
      setError("Could not load this story's results.");
    }
  };

  const handleDelete = async (storyId: string) => {
    await deleteStory(storyId);
    setStories((prev) => prev.filter((s) => s.id !== storyId));
  };

  const statusColour = (status: string) => {
    if (status === "complete") return "text-green-500";
    if (status === "failed") return "text-destructive";
    return "text-yellow-500";
  };

  return (
    <div className="min-h-screen bg-background p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Clock className="w-6 h-6 text-primary" />
        <h1 className="text-2xl font-bold text-foreground">Story History</h1>
        <button
          onClick={() => navigate("/")}
          className="ml-auto text-sm text-primary underline"
        >
          + New Story
        </button>
      </div>

      {loading && (
        <div className="flex justify-center mt-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      )}

      {error && <p className="text-destructive text-sm">{error}</p>}

      {!loading && stories.length === 0 && (
        <div className="text-center text-muted-foreground mt-20">
          <p>No stories yet.</p>
          <button onClick={() => navigate("/")} className="mt-3 text-primary underline text-sm">
            Analyse your first story
          </button>
        </div>
      )}

      <div className="space-y-3">
        {stories.map((story) => (
          <div
            key={story.id}
            className="glass-card p-4 flex items-center gap-4 cursor-pointer hover:border-primary/40 transition-colors"
            onClick={() => handleLoad(story.id, story.status)}
          >
            <div className="flex-1 min-w-0">
              <p className="font-medium text-foreground truncate">{story.series_title}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {story.episode_count} episodes ·{" "}
                {new Date(story.created_at).toLocaleDateString()}
              </p>
            </div>
            <span className={`text-xs font-medium capitalize ${statusColour(story.status)}`}>
              {story.status}
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); handleDelete(story.id); }}
              className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            {story.status === "complete" && (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
