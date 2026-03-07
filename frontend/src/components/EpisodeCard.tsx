import { Episode } from "../types";

function scorePillColor(value: number, type: "dropoff" | "default") {
  if (type === "dropoff") {
    if (value < 0.25) return "bg-success/20 text-success";
    if (value <= 0.4) return "bg-warning/20 text-warning";
    return "bg-destructive/20 text-destructive";
  }
  return "bg-primary/20 text-primary";
}

export default function EpisodeCard({ episode }: { episode: Episode }) {
  return (
    <div className="glass-card p-5 space-y-4 animate-slide-up">
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-semibold text-accent">EP {episode.episode_number}</span>
        <h3 className="text-lg font-semibold text-foreground">{episode.title}</h3>
      </div>
      <p className="text-sm text-muted-foreground leading-relaxed">{episode.plot_beat}</p>

      <div className="flex flex-wrap gap-1.5">
        {episode.characters.map((c) => (
          <span key={c} className="px-2 py-0.5 text-xs rounded-full bg-primary/15 text-primary font-medium">{c}</span>
        ))}
        {episode.locations.map((l) => (
          <span key={l} className="px-2 py-0.5 text-xs rounded-full bg-secondary text-secondary-foreground font-medium">{l}</span>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <ScorePill label="Emotion" value={episode.emotion_score} />
        <ScorePill label="Drop-off" value={episode.drop_off_probability} type="dropoff" />
        <ScorePill label="Cliffhanger" value={episode.cliffhanger_score} max={10} />
        <ScorePill label="Continuity" value={episode.continuity_score} />
      </div>
    </div>
  );
}

function ScorePill({ label, value, max, type = "default" }: {
  label: string; value: number; max?: number; type?: "dropoff" | "default";
}) {
  const display = max ? `${value}/${max}` : `${(value * 100).toFixed(0)}%`;
  return (
    <div className={`flex items-center justify-between px-3 py-1.5 rounded-lg text-xs font-medium ${scorePillColor(type === "dropoff" ? value : 0, type === "dropoff" ? "dropoff" : "default")}`}>
      <span className="opacity-70">{label}</span>
      <span>{display}</span>
    </div>
  );
}
