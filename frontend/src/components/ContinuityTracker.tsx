import { ContinuityIssue } from "../types";
import { CheckCircle2, AlertTriangle, XCircle, GitBranch } from "lucide-react";

interface Props {
  issues: ContinuityIssue[];
  episodes?: { episode_number: number; title: string }[];
}

function SeverityBadge({ severity }: { severity: string }) {
  if (severity === "high") return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-500/15 text-red-400 border border-red-500/30">
      <XCircle className="w-3 h-3" /> High
    </span>
  );
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
      <AlertTriangle className="w-3 h-3" /> Medium
    </span>
  );
}

function SimilarityBar({ score }: { score: number }) {
  const pct = score * 100;
  const color =
    score >= 0.75 ? "hsl(160 70% 45%)" :
    score >= 0.60 ? "hsl(45 95% 55%)" :
                    "hsl(0 80% 55%)";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Narrative similarity</span>
        <span style={{ color }}>{pct.toFixed(0)}%</span>
      </div>
      <div className="w-full h-2 rounded-full bg-secondary overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <p className="text-[10px] text-muted-foreground">
        {score >= 0.75 ? "Strong narrative connection between episodes" :
         score >= 0.60 ? "Moderate gap — consider bridging the narrative" :
                         "Weak connection — audiences may feel lost"}
      </p>
    </div>
  );
}

function parseTransition(transition: string): { from: number; to: number } {
  const match = transition.match(/Episode\s+(\d+)\s*→\s*Episode\s+(\d+)/i);
  return match
    ? { from: parseInt(match[1]), to: parseInt(match[2]) }
    : { from: 0, to: 0 };
}

function extractBeats(issueText: string): { closing: string; opening: string } | null {
  const match = issueText.match(/closes: "(.+?)" — Episode \d+ opens: "(.+?)"\./);
  if (match) return { closing: match[1], opening: match[2] };
  return null;
}

export default function ContinuityTracker({ issues, episodes = [] }: Props) {
  const totalTransitions = Math.max(episodes.length - 1, issues.length, 1);
  const issueMap: Record<string, ContinuityIssue> = {};
  issues.forEach(i => {
    const { from } = parseTransition(i.transition);
    issueMap[from] = i;
  });

  const highCount = issues.filter(i => i.severity === "high").length;
  const medCount  = issues.filter(i => i.severity === "medium").length;
  const okCount   = totalTransitions - issues.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Continuity Audit</h2>
        <div className="flex gap-3 text-xs">
          <span className="flex items-center gap-1 text-green-400"><CheckCircle2 className="w-3.5 h-3.5" />{okCount} OK</span>
          <span className="flex items-center gap-1 text-yellow-400"><AlertTriangle className="w-3.5 h-3.5" />{medCount} Medium</span>
          <span className="flex items-center gap-1 text-red-400"><XCircle className="w-3.5 h-3.5" />{highCount} High</span>
        </div>
      </div>

      {/* What is continuity? */}
      <div className="glass-card p-4 border border-border/40">
        <p className="text-xs text-muted-foreground leading-relaxed">
          <span className="text-foreground font-medium">How this works: </span>
          Each episode's closing beat is compared to the next episode's opening beat using sentence embeddings.
          A similarity below <strong className="text-yellow-400">75%</strong> flags a narrative gap — meaning audiences
          may feel disoriented by the transition. Below <strong className="text-red-400">60%</strong> is a critical gap
          that could cause drop-off.
        </p>
      </div>

      {/* No issues state */}
      {issues.length === 0 && (
        <div className="glass-card p-8 flex flex-col items-center gap-3 text-center">
          <CheckCircle2 className="w-10 h-10 text-green-400" />
          <p className="font-semibold text-foreground">No continuity issues detected</p>
          <p className="text-sm text-muted-foreground max-w-sm">
            All episode transitions have strong narrative connections. Your story flows smoothly from episode to episode.
          </p>
        </div>
      )}

      {/* Issues list */}
      {issues.map((issue) => {
        const beats = extractBeats(issue.issue);
        const { from, to } = parseTransition(issue.transition);
        return (
          <div key={issue.transition} className="glass-card p-5 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-muted-foreground" />
                <h3 className="font-semibold text-foreground">{issue.transition}</h3>
              </div>
              <SeverityBadge severity={issue.severity} />
            </div>

            {/* Similarity bar */}
            <SimilarityBar score={issue.similarity_score} />

            {/* Beat comparison */}
            {beats && (
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg p-3 border border-border/40 bg-white/[0.02]">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                    Ep {from} closes with
                  </p>
                  <p className="text-xs text-foreground/80 italic">"{beats.closing}"</p>
                </div>
                <div className="rounded-lg p-3 border border-border/40 bg-white/[0.02]">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                    Ep {to} opens with
                  </p>
                  <p className="text-xs text-foreground/80 italic">"{beats.opening}"</p>
                </div>
              </div>
            )}

            {/* Suggestion */}
            <div
              className="rounded-lg p-3"
              style={{
                background: issue.severity === "high" ? "hsl(0 80% 55% / 0.08)" : "hsl(45 95% 55% / 0.08)",
                border: `1px solid ${issue.severity === "high" ? "hsl(0 80% 55% / 0.25)" : "hsl(45 95% 55% / 0.25)"}`,
              }}
            >
              <p className="text-[11px] font-semibold mb-1"
                style={{ color: issue.severity === "high" ? "hsl(0 80% 65%)" : "hsl(45 95% 65%)" }}>
                💡 How to fix
              </p>
              <p className="text-xs text-foreground/80">
                {issue.severity === "high"
                  ? `Add a brief recap moment at the start of Episode ${to} that directly references how Episode ${from} ended. Or strengthen Episode ${from}'s closing beat to foreshadow what opens Episode ${to}.`
                  : `Consider adding a line of dialogue or a visual callback in Episode ${to} that echoes the final moment of Episode ${from}. A small narrative bridge goes a long way.`
                }
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
