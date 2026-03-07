import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceArea } from "recharts";
import { EmotionalArc } from "../types";

interface Props {
  arc: EmotionalArc;
  totalEpisodes: number;
}

export default function EmotionalArcGraph({ arc, totalEpisodes }: Props) {
  const data = Array.from({ length: totalEpisodes }, (_, i) => ({
    episode: i + 1,
    actual: arc.actual_curve[i],
    ideal: arc.ideal_curve[i],
  }));

  return (
    <div className="glass-card p-6">
      <h2 className="text-lg font-semibold text-foreground mb-4">Emotional Arc</h2>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(228 12% 20%)" />
          {arc.flat_zones.map((zone) => (
            <ReferenceArea
              key={zone}
              x1={zone - 0.4}
              x2={zone + 0.4}
              fill="hsl(0 72% 51% / 0.1)"
              stroke="none"
            />
          ))}
          <XAxis dataKey="episode" stroke="hsl(215 15% 55%)" tick={{ fontSize: 12 }} label={{ value: "Episode", position: "insideBottom", offset: -2, fill: "hsl(215 15% 55%)" }} />
          <YAxis domain={[0, 1]} stroke="hsl(215 15% 55%)" tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(228 12% 12%)", border: "1px solid hsl(228 12% 20%)", borderRadius: "8px", color: "hsl(210 20% 92%)" }}
          />
          <Legend />
          <Line type="monotone" dataKey="actual" stroke="hsl(239 84% 67%)" strokeWidth={2.5} dot={{ r: 4, fill: "hsl(239 84% 67%)" }} name="Actual" />
          <Line type="monotone" dataKey="ideal" stroke="hsl(187 94% 43%)" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 3, fill: "hsl(187 94% 43%)" }} name="Ideal" />
        </LineChart>
      </ResponsiveContainer>
      {arc.flat_zones.length > 0 && (
        <p className="text-xs text-muted-foreground mt-3">
          ⚠ Flat zones detected at episode{arc.flat_zones.length > 1 ? "s" : ""}: {arc.flat_zones.join(", ")}
        </p>
      )}
    </div>
  );
}
