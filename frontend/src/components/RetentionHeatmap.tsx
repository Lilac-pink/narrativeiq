import { RetentionEpisode } from "../types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const riskColors: Record<string, string> = {
  low: "bg-success",
  medium: "bg-warning",
  high: "bg-destructive",
};

export default function RetentionHeatmap({ episodes }: { episodes: RetentionEpisode[] }) {
  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-foreground">Retention Heatmap</h2>
      <div className="space-y-3">
        {episodes.map((ep) => (
          <div key={ep.episode_number} className="glass-card p-4">
            <div className="flex items-center gap-4">
              <span className="text-sm font-medium text-muted-foreground w-20 shrink-0">
                Ep {ep.episode_number}
              </span>
              <div className="flex gap-1 flex-1">
                {ep.blocks.map((block) => (
                  <Tooltip key={block.time_block}>
                    <TooltipTrigger asChild>
                      <div className={`flex-1 h-10 rounded-md ${riskColors[block.risk_level]} opacity-70 hover:opacity-100 transition-opacity cursor-pointer flex items-center justify-center`}>
                        <span className="text-[10px] font-medium text-background">{block.time_block}</span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent className="bg-card border-border text-foreground max-w-xs">
                      <p className="font-medium">{block.time_block} — {block.risk_level} risk</p>
                      <p className="text-xs text-muted-foreground mt-1">{block.reason}</p>
                    </TooltipContent>
                  </Tooltip>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-success" /> Low risk</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-warning" /> Medium risk</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-destructive" /> High risk</span>
      </div>
    </div>
  );
}
