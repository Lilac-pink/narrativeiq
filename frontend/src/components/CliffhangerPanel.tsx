import { CliffhangerBreakdown } from "../types";
import { CheckCircle2, XCircle, Info } from "lucide-react";
import { useState } from "react";

// Criterion metadata — explains what each criterion means and why it matters
const CRITERION_META: Record<string, { why: string; tip: string; color: string }> = {
  "Unresolved question": {
    why: "Unanswered questions are the #1 driver of next-episode clicks. Audiences stay when they need closure.",
    tip: "End with a mystery, dilemma, or ambiguity that can only be resolved by watching on.",
    color: "hsl(239 84% 67%)",
  },
  "Emotional stakes raised": {
    why: "Viewers invest in characters, not plot. Elevated emotional stakes make the story feel personal.",
    tip: "Show what the protagonist stands to lose — relationship, identity, belief — not just physical safety.",
    color: "hsl(330 80% 60%)",
  },
  "Character in jeopardy": {
    why: "Threat to a named character triggers an instinctive 'I must know they're okay' response.",
    tip: "Put a character the audience cares about in a situation where the outcome is genuinely uncertain.",
    color: "hsl(20 90% 55%)",
  },
  "New information revealed": {
    why: "A well-timed revelation reframes everything the viewer thought they knew — it's addictive.",
    tip: "Reveal something that changes the meaning of a prior scene, not just adds new plot.",
    color: "hsl(160 70% 45%)",
  },
  "Time pressure present": {
    why: "Deadlines create urgency. When the clock is ticking, audiences feel it physiologically.",
    tip: "Introduce a countdown — deadline, expiry, window — that must be resolved in the next episode.",
    color: "hsl(45 95% 55%)",
  },
  "Scene ends on action beat": {
    why: "A kinetic final image carries momentum into the next episode. Passive endings bleed energy.",
    tip: "Close on a decision made, a door slammed, a gun raised — something that moves, not reflects.",
    color: "hsl(200 80% 55%)",
  },
};

function ScoreRing({ score, size = 72 }: { score: number; size?: number }) {
  const pct = (score / 10) * 100;
  const color =
    score >= 7.5 ? "hsl(160 70% 45%)" :
    score >= 5   ? "hsl(45 95% 55%)" :
                   "hsl(0 80% 55%)";
  const label =
    score >= 8 ? "Excellent" :
    score >= 6 ? "Good" :
    score >= 4 ? "Needs Work" :
                 "Weak";

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox="0 0 36 36" className="-rotate-90">
          <circle cx="18" cy="18" r="15.91" fill="none" stroke="hsl(228 12% 20%)" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="15.91" fill="none"
            stroke={color} strokeWidth="3"
            strokeDasharray={`${pct} ${100 - pct}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 0.6s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-foreground leading-none">{score.toFixed(1)}</span>
          <span className="text-[9px] text-muted-foreground leading-none">/ 10</span>
        </div>
      </div>
      <span className="text-xs font-medium" style={{ color }}>{label}</span>
    </div>
  );
}

function WeightBar({ weight, passed, contribution }: { weight: number; passed: boolean; contribution: number }) {
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${weight * 100}%`,
            background: passed ? "hsl(160 70% 45%)" : "hsl(0 80% 55%)",
            opacity: passed ? 1 : 0.4,
          }}
        />
      </div>
      <span className="text-[10px] text-muted-foreground w-16 text-right">
        {passed ? `+${contribution.toFixed(2)}` : `+0.00`} pts
      </span>
    </div>
  );
}

function CriterionRow({ c, epTitle }: { c: any; epTitle: string }) {
  const [open, setOpen] = useState(false);
  const meta = CRITERION_META[c.criterion] || { why: "", tip: "", color: "hsl(239 84% 67%)" };

  return (
    <div className="border border-border/40 rounded-lg overflow-hidden">
      {/* Row header */}
      <div
        className="flex items-center gap-3 p-3 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        {/* Pass/fail icon */}
        {c.passed || c.pass
          ? <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
          : <XCircle className="w-4 h-4 text-red-400 shrink-0" />
        }

        {/* Criterion name */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground">{c.criterion}</span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
              style={{
                background: `${meta.color}22`,
                color: meta.color,
                border: `1px solid ${meta.color}44`,
              }}
            >
              {Math.round((c.weight || 0) * 100)}% weight
            </span>
          </div>
          {/* Weight bar */}
          <div className="mt-1.5">
            <WeightBar
              weight={c.weight || 0}
              passed={c.passed ?? c.pass ?? false}
              contribution={c.weighted_contribution ?? 0}
            />
          </div>
        </div>

        {/* Expand icon */}
        <Info className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
      </div>

      {/* AI reason */}
      <div className="px-3 pb-2 -mt-1">
        <p className="text-xs text-muted-foreground italic">"{c.reason}"</p>
      </div>

      {/* Expandable explanation */}
      {open && (
        <div className="border-t border-border/40 bg-white/[0.03] p-3 space-y-2">
          <div>
            <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Why this matters</p>
            <p className="text-xs text-foreground/80">{meta.why}</p>
          </div>
          {!(c.passed ?? c.pass) && meta.tip && (
            <div className="rounded-md p-2.5" style={{ background: `${meta.color}11`, border: `1px solid ${meta.color}33` }}>
              <p className="text-[11px] font-semibold mb-1" style={{ color: meta.color }}>💡 How to fix this</p>
              <p className="text-xs text-foreground/80">{meta.tip}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ScoreExplanation({ score, passCount }: { score: number; passCount: number }) {
  const total = 6;
  const verdict =
    score >= 8 ? { text: "Excellent cliffhanger — audiences will struggle to stop watching.", icon: "🔥" } :
    score >= 6 ? { text: "Solid cliffhanger with room to push the tension further.", icon: "✅" } :
    score >= 4 ? { text: "Weak ending — viewers may not feel compelled to continue.", icon: "⚠️" } :
                 { text: "Critical: this episode needs a stronger hook before release.", icon: "🚨" };

  return (
    <div className="rounded-lg p-3 border border-border/40 bg-white/[0.03] space-y-2">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">How the score is calculated</p>
      <p className="text-xs text-foreground/80">
        Each of the 6 criteria carries a weighted value that sums to 10 points.
        A criterion that <strong className="text-foreground">passes</strong> contributes its full weight × 10.
        One that <strong className="text-foreground">fails</strong> contributes 0.
        The raw score is then multiplied by the series' <em>cliffhanger weight</em> (from story type) to give the final adjusted score.
      </p>
      <div className="flex items-center gap-2 pt-1">
        <span className="text-lg">{verdict.icon}</span>
        <p className="text-xs text-foreground/90 font-medium">
          {passCount}/{total} criteria passed — {verdict.text}
        </p>
      </div>
    </div>
  );
}

export default function CliffhangerPanel({ breakdowns }: { breakdowns: CliffhangerBreakdown[] }) {
  const [activeEp, setActiveEp] = useState(breakdowns[0]?.episode_number ?? 1);
  const bd = breakdowns.find(b => b.episode_number === activeEp) ?? breakdowns[0];

  if (!bd) return <p className="text-muted-foreground text-sm">No cliffhanger data available.</p>;

  const passCount = bd.criteria.filter(c => c.passed ?? c.pass).length;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Cliffhanger Strength</h2>
        <p className="text-xs text-muted-foreground">Click any criterion to see explanation</p>
      </div>

      {/* Episode selector tabs */}
      <div className="flex gap-2 flex-wrap">
        {breakdowns.map(b => (
          <button
            key={b.episode_number}
            onClick={() => setActiveEp(b.episode_number)}
            className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
            style={{
              background: activeEp === b.episode_number ? "hsl(239 84% 67%)" : "hsl(228 12% 20%)",
              color: activeEp === b.episode_number ? "white" : "hsl(215 20% 65%)",
            }}
          >
            Ep {b.episode_number} · {b.score?.toFixed(1) ?? b.adjusted_score?.toFixed(1) ?? "—"}
          </button>
        ))}
      </div>

      {/* Active episode card */}
      <div className="glass-card p-5 space-y-5">
        {/* Header: ring + title + summary */}
        <div className="flex items-start gap-5">
          <ScoreRing score={bd.score ?? bd.adjusted_score ?? 0} />
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-foreground text-base">
              Episode {bd.episode_number}: {bd.title}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5 mb-3">
              {passCount} of 6 criteria passed
            </p>
            {/* Mini pass/fail dots */}
            <div className="flex gap-1.5">
              {bd.criteria.map((c, i) => (
                <div
                  key={i}
                  className="w-2.5 h-2.5 rounded-full"
                  title={c.criterion}
                  style={{
                    background: (c.passed ?? c.pass)
                      ? "hsl(160 70% 45%)"
                      : "hsl(0 80% 40%)",
                  }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Score explanation */}
        <ScoreExplanation score={bd.score ?? bd.adjusted_score ?? 0} passCount={passCount} />

        {/* Criteria rows */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Criteria Breakdown</p>
          {bd.criteria.map((c) => (
            <CriterionRow key={c.criterion} c={c} epTitle={bd.title} />
          ))}
        </div>
      </div>
    </div>
  );
}
