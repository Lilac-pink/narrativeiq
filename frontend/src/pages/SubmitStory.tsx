import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  submitStory,
  submitStoryAuth,
  getJobStatus,
  getStoryStatus,
  getJobResult,
  getStoryResult,
  checkHealth,
  isLoggedIn,
} from "../services/api";
import { mockData } from "../mockData";
import { Radio, Loader2, Sparkles, LogIn } from "lucide-react";

const PIPELINE_STEPS = [
  "Decomposing story...",
  "Analysing emotional arc...",
  "Scoring cliffhangers...",
  "Predicting drop-off risk...",
  "Generating suggestions...",
];

export default function SubmitStory() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [numEpisodes, setNumEpisodes] = useState(5);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState("");
  const [isLive, setIsLive] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [userName, setUserName] = useState("");

  useEffect(() => {
    checkHealth().then(setIsLive);
    const loggedInStatus = isLoggedIn();
    setLoggedIn(loggedInStatus);
    if (loggedInStatus) {
      const user = localStorage.getItem("narrativeiq_user");
      if (user) {
        try { setUserName(JSON.parse(user).name); } catch {}
      }
    }
  }, []);

  // Animate pipeline steps while loading
  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setCurrentStep((prev) => (prev < PIPELINE_STEPS.length - 1 ? prev + 1 : prev));
    }, 2500);
    return () => clearInterval(interval);
  }, [loading]);

  const handleSubmit = useCallback(async () => {
    if (!description.trim()) return;
    setLoading(true);
    setCurrentStep(0);
    setError("");

    // ── Mock mode (backend not running) ──────────────────────
    if (!isLive) {
      await new Promise((r) => setTimeout(r, 4000));
      sessionStorage.setItem("narrativeiq_result", JSON.stringify(mockData));
      navigate("/dashboard");
      return;
    }

    try {
      const payload = {
        series_title: title || "Untitled Series",
        story_description: description,
        num_episodes: numEpisodes,
      };

      if (loggedIn) {
        // ── Authenticated: saves to DB ────────────────────────
        const { id: storyId } = await submitStoryAuth(payload);

        const poll = async () => {
          const status = await getStoryStatus(storyId);
          if (status.status === "complete") {
            const result = await getStoryResult(storyId);
            sessionStorage.setItem("narrativeiq_result", JSON.stringify(result));
            navigate("/dashboard");
          } else if (status.status === "failed") {
            setError("Analysis failed. Please try again.");
            setLoading(false);
          } else {
            setTimeout(poll, 3000);
          }
        };
        poll();

      } else {
        // ── Anonymous: in-memory only ─────────────────────────
        const { job_id } = await submitStory(payload);

        const poll = async () => {
          const status = await getJobStatus(job_id);
          if (status.status === "complete") {
            const result = await getJobResult(job_id);
            sessionStorage.setItem("narrativeiq_result", JSON.stringify(result));
            navigate("/dashboard");
          } else if (status.status === "failed") {
            setError("Analysis failed. Please try again.");
            setLoading(false);
          } else {
            // "pending" or "running" — keep polling
            setTimeout(poll, 3000);
          }
        };
        poll();
      }
    } catch {
      setError("Could not connect to the server.");
      setLoading(false);
    }
  }, [description, title, numEpisodes, isLive, loggedIn, navigate]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-8 max-w-md mx-auto px-6">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-primary/10 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-foreground">Analysing your story</h2>
            <p className="text-sm text-muted-foreground">
              {isLive
                ? loggedIn
                  ? "Connected · results will be saved to your account"
                  : "Connected to NarrativeIQ engine"
                : "Running with mock data"}
            </p>
          </div>
          <div className="space-y-3 text-left">
            {PIPELINE_STEPS.map((step, i) => (
              <div
                key={step}
                className={`flex items-center gap-3 transition-all duration-500 ${i <= currentStep ? "opacity-100" : "opacity-30"}`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    i < currentStep
                      ? "bg-green-500"
                      : i === currentStep
                      ? "bg-primary animate-pulse"
                      : "bg-muted"
                  }`}
                />
                <span className={`text-sm ${i <= currentStep ? "text-foreground" : "text-muted-foreground"}`}>
                  {step}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-2xl space-y-8">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
            <Radio className="w-7 h-7 text-primary" />
          </div>
          <h1 className="text-3xl font-bold text-foreground tracking-tight">NarrativeIQ</h1>
          <p className="text-muted-foreground">AI-powered story analysis for series creators</p>

          {/* Status row */}
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${isLive ? "bg-green-500" : "bg-muted-foreground"}`} />
              <span className="text-xs text-muted-foreground">
                {isLive ? "Backend connected" : "Mock mode"}
              </span>
            </div>
            {loggedIn ? (
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-xs text-muted-foreground">Signed in as {userName}</span>
                <button
                  onClick={() => navigate("/history")}
                  className="text-xs text-primary underline"
                >
                  My history
                </button>
              </div>
            ) : (
              <button
                onClick={() => navigate("/login")}
                className="flex items-center gap-1 text-xs text-primary underline"
              >
                <LogIn className="w-3 h-3" />
                Sign in to save results
              </button>
            )}
          </div>
        </div>

        {/* Form */}
        <div className="glass-card p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Series Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. The Forgotten Signal"
              className="w-full px-4 py-2.5 rounded-lg bg-secondary border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Describe your story idea
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              placeholder="A radio operator picks up a signal from a station that closed 30 years ago..."
              className="w-full px-4 py-2.5 rounded-lg bg-secondary border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Number of episodes
            </label>
            <input
              type="number"
              min={2}
              max={12}
              value={numEpisodes}
              onChange={(e) =>
                setNumEpisodes(Math.min(12, Math.max(2, parseInt(e.target.value) || 2)))
              }
              className="w-24 px-4 py-2.5 rounded-lg bg-secondary border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm"
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <button
            onClick={handleSubmit}
            disabled={!description.trim()}
            className="w-full py-3 rounded-lg bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            Analyse My Story
          </button>

          {!loggedIn && isLive && (
            <p className="text-xs text-center text-muted-foreground">
              Results won't be saved.{" "}
              <button onClick={() => navigate("/login")} className="text-primary underline">
                Sign in
              </button>{" "}
              to keep your history.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
