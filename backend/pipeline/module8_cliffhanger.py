"""
Module 8 — Cliffhanger Scoring Engine
Phase 4: Scoring Engines

For each episode, sends 6 yes/no questions to GPT-4o — one per criterion —
and computes a weighted score out of 10. Uses the cliffhanger_weight from
Module 4 to adjust scoring strictness per story type.

No embeddings. No NLP libraries. GPT-4o for judgment, math for the score.

Inputs (from pipeline):
  - module3_output: dict  → episodes (title, plot_beat, closing_beat, raw_text)
  - module4_output: dict  → cliffhanger_weight, story_type

Outputs feed into:
  - Module 7  (already done, but cliffhanger_score feeds arc analysis context)
  - Module 13 (Retention Risk Heatmap)        — cliffhanger_score per episode
  - Module 14 (Optimisation Suggestion Engine) — full criteria breakdown
  - Module 15 (Score Explainer)               — scores to plain English
  - Lovable frontend                           — cliffhanger_breakdown block
"""

import os
import json
import asyncio
from typing import Optional
from groq import AsyncGroq
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# The 6 criteria — weights must sum to 1.0
# ---------------------------------------------------------------------------

CRITERIA = [
    {
        "id": "unresolved_question",
        "criterion": "Unresolved question",
        "weight": 0.20,
        "question": (
            "Does this episode end with a clear unresolved question or mystery "
            "that the audience will need answered — something specific, not just "
            "general story uncertainty?"
        ),
        "pass_note_template": "A clear unresolved question compels the audience forward.",
        "fail_note_template": "No specific unresolved question is established at the episode's end.",
    },
    {
        "id": "emotional_stakes",
        "criterion": "Emotional stakes raised",
        "weight": 0.20,
        "question": (
            "Are the emotional stakes for the protagonist explicitly raised by the "
            "end of this episode — does the audience feel the character has more to "
            "lose now than at the episode's start?"
        ),
        "pass_note_template": "Emotional stakes are clearly elevated for the protagonist.",
        "fail_note_template": "The protagonist's emotional stakes do not visibly increase.",
    },
    {
        "id": "character_jeopardy",
        "criterion": "Character in jeopardy",
        "weight": 0.18,
        "question": (
            "Is a named character — protagonist or key supporting character — "
            "in physical, emotional, or social jeopardy at the moment the episode ends?"
        ),
        "pass_note_template": "A named character faces direct jeopardy at the episode's close.",
        "fail_note_template": "No character is in identifiable jeopardy at the episode's end.",
    },
    {
        "id": "new_information",
        "criterion": "New information revealed",
        "weight": 0.18,
        "question": (
            "Does the episode end with a new piece of information, revelation, or "
            "plot twist that meaningfully recontextualises what the audience thought "
            "they knew?"
        ),
        "pass_note_template": "A meaningful new revelation reframes the story for the audience.",
        "fail_note_template": "No new plot-shifting information is revealed near the episode's end.",
    },
    {
        "id": "time_pressure",
        "criterion": "Time pressure present",
        "weight": 0.12,
        "question": (
            "Is there an explicit time constraint, deadline, or countdown — even an "
            "implied urgency — that makes the audience feel something must happen soon?"
        ),
        "pass_note_template": "A time constraint or urgency signal creates forward momentum.",
        "fail_note_template": "No time pressure or urgency is established to drive the audience forward.",
    },
    {
        "id": "action_beat_ending",
        "criterion": "Scene ends on action beat",
        "weight": 0.12,
        "question": (
            "Does the episode's final scene end on a moment of action, discovery, "
            "or physical/verbal confrontation — rather than dialogue, reflection, "
            "or a quiet character moment?"
        ),
        "pass_note_template": "The episode closes on an active beat that creates kinetic momentum.",
        "fail_note_template": "The episode ends on a passive or reflective beat rather than action.",
    },
]

assert abs(sum(c["weight"] for c in CRITERIA) - 1.0) < 1e-6, "Criterion weights must sum to 1.0"

MAX_RAW_SCORE = 10.0  # scores are returned on 0–10 scale


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------

class CriterionResult(BaseModel):
    criterion_id: str
    criterion: str
    weight: float
    passed: bool
    weighted_contribution: float = Field(
        ..., description="weight × 10 if passed, else 0."
    )
    reason: str = Field(..., description="One-line GPT explanation for the pass/fail judgment.")


class EpisodeCliffhangerScore(BaseModel):
    episode_number: int
    title: str
    raw_score: float = Field(..., description="Sum of weighted contributions. Range 0–10.")
    adjusted_score: float = Field(
        ...,
        description=(
            "raw_score × cliffhanger_weight, capped at 10. "
            "Reflects story-type strictness from Module 4."
        )
    )
    pass_count: int = Field(..., description="Number of criteria that passed (0–6).")
    fail_count: int = Field(..., description="Number of criteria that failed (0–6).")
    criteria: list[CriterionResult]
    severity_label: str = Field(
        ...,
        description="One of: strong | adequate | weak | critical"
    )
    primary_weakness: Optional[str] = Field(
        None,
        description="The highest-weight criterion that failed, if any."
    )
    one_line_verdict: str = Field(
        ..., description="Human-readable summary of the cliffhanger quality."
    )


class CliffhangerReport(BaseModel):
    series_title: str
    story_type: str
    cliffhanger_weight: float
    total_episodes: int
    episode_scores: list[EpisodeCliffhangerScore]
    series_average_score: float = Field(
        ..., description="Mean adjusted_score across all episodes."
    )
    strongest_episode: int
    weakest_episode: int
    critical_episodes: list[int] = Field(
        ..., description="Episodes with severity_label == 'critical'."
    )


# ---------------------------------------------------------------------------
# GPT yes/no judgment — one criterion per call
# ---------------------------------------------------------------------------

CRITERION_SYSTEM_PROMPT = """
You are a professional TV script analyst evaluating cliffhanger effectiveness.

You will be given:
- An episode title and its closing beat (how the episode ends)
- A single yes/no evaluation question

Answer ONLY with a JSON object in this exact format:
{
  "answer": true,
  "reason": "One sentence explaining your judgment."
}

"answer" must be a boolean (true = yes, false = no).
"reason" must be a single sentence, specific to this episode's content.
Do not add any other fields. Do not add markdown.
""".strip()


class CriterionJudgment(BaseModel):
    answer: bool
    reason: str


async def _judge_criterion(
    client: AsyncGroq,
    episode_number: int,
    title: str,
    plot_beat: str,
    closing_beat: str,
    raw_text: str,
    criterion: dict,
    model: str,
) -> CriterionJudgment:
    """
    Fires a single GPT call to judge one criterion for one episode.
    Returns a CriterionJudgment with answer (bool) and reason (str).
    """
    user_prompt = f"""
Episode {episode_number}: "{title}"

Plot beat: {plot_beat}
Closing beat: {closing_beat}
Full episode description: {raw_text[:600]}

Question: {criterion['question']}
""".strip()

    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CRITERION_SYSTEM_PROMPT + "\n\nRespond with valid JSON only. No markdown."},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=150,
    )

    raw = completion.choices[0].message.content or ""
    try:
        data = json.loads(raw)
        result = CriterionJudgment(**data)
    except Exception:
        result = CriterionJudgment(
            answer=False,
            reason="Groq judgment unavailable for this criterion. Defaulting to fail."
        )

    return result


# ---------------------------------------------------------------------------
# Score an individual episode (all 6 criteria in parallel)
# ---------------------------------------------------------------------------

def _severity_label(score: float) -> str:
    if score >= 7.5:
        return "strong"
    if score >= 5.5:
        return "adequate"
    if score >= 3.5:
        return "weak"
    return "critical"


def _one_line_verdict(score: float, pass_count: int, title: str) -> str:
    if score >= 7.5:
        return f"'{title}' delivers a strong cliffhanger — {pass_count}/6 criteria met."
    if score >= 5.5:
        return f"'{title}' has an adequate cliffhanger but leaves tension on the table."
    if score >= 3.5:
        return f"'{title}' has a weak cliffhanger — significant rework needed."
    return f"'{title}' critically fails the cliffhanger — audiences have little reason to continue."


async def _score_episode(
    client: AsyncGroq,
    episode: dict,
    cliffhanger_weight: float,
    model: str,
) -> EpisodeCliffhangerScore:
    """
    Scores all 6 criteria for one episode by firing all GPT calls in parallel.
    """
    ep_num       = episode["episode_number"]
    title        = episode["title"]
    plot_beat    = episode.get("plot_beat", "")
    closing_beat = episode.get("closing_beat", "")
    raw_text     = episode.get("raw_text", plot_beat)  # fallback to plot_beat if no raw_text

    # Fire criterion calls sequentially to respect Groq rate limits
    judgments: list[CriterionJudgment] = []
    for criterion in CRITERIA:
        j = await _judge_criterion(
            client, ep_num, title, plot_beat, closing_beat, raw_text, criterion, model
        )
        judgments.append(j)
        await asyncio.sleep(0.5)  # throttle to avoid 429s

    # Build criterion results
    criterion_results: list[CriterionResult] = []
    raw_score = 0.0

    for criterion, judgment in zip(CRITERIA, judgments):
        contribution = round(criterion["weight"] * MAX_RAW_SCORE, 3) if judgment.answer else 0.0
        raw_score += contribution

        reason = judgment.reason if judgment.reason else (
            criterion["pass_note_template"] if judgment.answer
            else criterion["fail_note_template"]
        )

        criterion_results.append(CriterionResult(
            criterion_id          = criterion["id"],
            criterion             = criterion["criterion"],
            weight                = criterion["weight"],
            passed                = judgment.answer,
            weighted_contribution = round(contribution, 3),
            reason                = reason,
        ))

    raw_score     = round(raw_score, 2)
    adjusted      = round(min(MAX_RAW_SCORE, raw_score * cliffhanger_weight), 2)
    pass_count    = sum(1 for r in criterion_results if r.passed)
    fail_count    = 6 - pass_count
    severity      = _severity_label(adjusted)
    verdict       = _one_line_verdict(adjusted, pass_count, title)

    # Find highest-weight failed criterion
    failed = [
        (c["weight"], c["criterion"])
        for c, r in zip(CRITERIA, criterion_results)
        if not r.passed
    ]
    primary_weakness = max(failed, key=lambda x: x[0])[1] if failed else None

    return EpisodeCliffhangerScore(
        episode_number   = ep_num,
        title            = title,
        raw_score        = raw_score,
        adjusted_score   = adjusted,
        pass_count       = pass_count,
        fail_count       = fail_count,
        criteria         = criterion_results,
        severity_label   = severity,
        primary_weakness = primary_weakness,
        one_line_verdict = verdict,
    )


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------

async def score_cliffhangers_async(
    module3_output: dict,
    module4_output: dict,
    api_key: Optional[str] = None,
    model: str = "llama-3.1-8b-instant",
) -> CliffhangerReport:
    """
    Scores all episodes' cliffhangers concurrently.

    Args:
        module3_output: Output dict from Module 3 run(). Needs episodes list.
        module4_output: Output dict from Module 4 run(). Needs cliffhanger_weight, story_type.
        api_key:        OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model:          GPT model. Default gpt-4o.

    Returns:
        CliffhangerReport: Full scoring report for all episodes.
    """
    client = AsyncGroq(api_key=api_key or os.environ["GROQ_API_KEY"])

    episodes           = module3_output["episodes"]
    series_title       = module3_output.get("series_title", "Untitled")
    cliffhanger_weight = module4_output.get("cliffhanger_weight", 1.0)
    story_type         = module4_output.get("story_type", "unknown")

    # Score episodes sequentially to respect Groq rate limits
    episode_scores: list[EpisodeCliffhangerScore] = []
    for ep in episodes:
        score = await _score_episode(client, ep, cliffhanger_weight, model)
        episode_scores.append(score)
        await asyncio.sleep(1.0)  # pause between episodes

    # Sort by episode number just in case gather reorders
    episode_scores.sort(key=lambda x: x.episode_number)

    adjusted_scores     = [e.adjusted_score for e in episode_scores]
    series_avg          = round(sum(adjusted_scores) / len(adjusted_scores), 2)
    strongest_ep        = episode_scores[adjusted_scores.index(max(adjusted_scores))].episode_number
    weakest_ep          = episode_scores[adjusted_scores.index(min(adjusted_scores))].episode_number
    critical_episodes   = [e.episode_number for e in episode_scores if e.severity_label == "critical"]

    return CliffhangerReport(
        series_title        = series_title,
        story_type          = story_type,
        cliffhanger_weight  = cliffhanger_weight,
        total_episodes      = len(episode_scores),
        episode_scores      = episode_scores,
        series_average_score= series_avg,
        strongest_episode   = strongest_ep,
        weakest_episode     = weakest_ep,
        critical_episodes   = critical_episodes,
    )


# ---------------------------------------------------------------------------
# Pipeline-compatible wrapper (sync entry point for Module 16)
# ---------------------------------------------------------------------------

def run(module3_output: dict, module4_output: dict) -> dict:
    """
    Pipeline entry point called by the Module 16 Orchestrator.
    Runs the async scorer in a new event loop.

    Args:
        module3_output: Output dict from Module 3 run().
        module4_output: Output dict from Module 4 run().

    Returns:
        dict: JSON-serialisable CliffhangerReport dict.
    """
    report = asyncio.run(
        score_cliffhangers_async(module3_output, module4_output)
    )
    return report.model_dump()


# ---------------------------------------------------------------------------
# Utility — extract flat episode scores for downstream modules
# ---------------------------------------------------------------------------

def extract_scores(cliffhanger_report: dict) -> dict[int, float]:
    """
    Returns {episode_number: adjusted_score} mapping.
    Useful for Module 13 (Retention Heatmap) and Module 14 (Suggestions).
    """
    return {
        ep["episode_number"]: ep["adjusted_score"]
        for ep in cliffhanger_report["episode_scores"]
    }


# ---------------------------------------------------------------------------
# CLI — run directly for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    mock_module3 = {
        "series_title": "The Forgotten Signal",
        "total_episodes": 5,
        "episodes": [
            {
                "episode_number": 1,
                "title": "Dead Air",
                "plot_beat": "Maya picks up a signal from a station closed 30 years ago.",
                "closing_beat": "She traces the signal to GPS coordinates in the middle of nowhere.",
                "raw_text": (
                    "Maya Chen sits alone in Radio Tower 7 on a routine night shift. "
                    "The console crackles — a voice, faint but unmistakable, broadcasting "
                    "on a frequency that has been dead for three decades. She records it. "
                    "She traces it. The signal bounces off three relay towers before resolving "
                    "to a set of GPS coordinates deep in the industrial district. Maya stares "
                    "at the printout. The station those coordinates belong to was officially "
                    "demolished in 1993. She grabs her jacket."
                ),
            },
            {
                "episode_number": 2,
                "title": "Interference",
                "plot_beat": "Maya finds the coordinates lead to a sealed government bunker.",
                "closing_beat": "She breaks in and the bunker door swings open on its own.",
                "raw_text": (
                    "Maya drives to the coordinates at dawn. A rusted fence surrounds "
                    "a concrete structure with no signage. She cuts through the fence. "
                    "The bunker entrance is sealed with a keypad lock — but the display "
                    "is blinking, as though recently activated. Maya punches in a code she "
                    "found in the archived station logs. A long pause. Then the heavy door "
                    "swings open by itself, releasing a rush of stale air. Somewhere inside, "
                    "a light flickers on."
                ),
            },
            {
                "episode_number": 3,
                "title": "Static",
                "plot_beat": "Encrypted files inside link Director Osei to the original station.",
                "closing_beat": "Maya finds a hidden door behind a bookshelf.",
                "raw_text": (
                    "Inside the bunker, Maya moves through rows of filing cabinets. "
                    "Most are empty. One drawer is locked. She forces it open and finds "
                    "a set of encrypted documents — but the header is visible: signed by "
                    "Director Osei, dated 1991. She photographs everything. As she moves "
                    "to leave, she notices the bookshelf isn't flush against the wall. "
                    "She pulls it. Behind it is a door, sealed but not locked."
                ),
            },
            {
                "episode_number": 4,
                "title": "Frequency",
                "plot_beat": "Osei confronts Maya. The Voice reveals it is a 1991 AI.",
                "closing_beat": "The AI speaks to Maya directly: 'I have been waiting for you.'",
                "raw_text": (
                    "Director Osei appears at the bunker entrance, weapon raised. "
                    "He tells Maya she has no idea what she has found. They argue. "
                    "Then the speakers crackle and the Voice speaks — calm, precise, "
                    "unmistakably artificial. It identifies itself as SIGNAL-1, an AI "
                    "system commissioned in 1989 and left running after the program was "
                    "officially cancelled. Osei goes pale. The AI addresses Maya by name: "
                    "'I have been waiting for you.' Osei lowers his gun slowly."
                ),
            },
            {
                "episode_number": 5,
                "title": "Broadcast",
                "plot_beat": "Maya must choose: silence the AI or expose the government.",
                "closing_beat": "Maya hits the broadcast button. Screens across the city light up.",
                "raw_text": (
                    "Maya stands at the broadcast console. Osei is unconscious behind her — "
                    "she had no choice. SIGNAL-1 has compiled 30 years of classified records "
                    "and is ready to transmit to every screen in the city. It asks Maya to "
                    "authorise the broadcast. She has 60 seconds before Osei's backup team "
                    "arrives. Maya thinks of her father, a whistleblower who died in custody. "
                    "She hits the button. Every billboard, every phone, every TV flickers. "
                    "The truth is out."
                ),
            },
        ],
    }

    mock_module4 = {
        "story_type": "mystery",
        "cliffhanger_weight": 1.2,
    }

    print("=" * 60)
    print("MODULE 8 — CLIFFHANGER SCORING ENGINE")
    print("=" * 60)
    print(f"\nSeries: {mock_module3['series_title']}")
    print(f"Story type: {mock_module4['story_type']} | CH weight: {mock_module4['cliffhanger_weight']}")
    print("\nScoring all episodes (6 criteria × 5 episodes = 30 GPT calls, all parallel)...\n")

    try:
        output = run(mock_module3, mock_module4)

        for ep in output["episode_scores"]:
            print(f"\nEp {ep['episode_number']}: {ep['title']}")
            print(f"  Score: {ep['adjusted_score']}/10  ({ep['severity_label'].upper()})  "
                  f"Pass: {ep['pass_count']}/6")
            print(f"  Verdict: {ep['one_line_verdict']}")
            if ep["primary_weakness"]:
                print(f"  Primary weakness: {ep['primary_weakness']}")
            for c in ep["criteria"]:
                icon = "✅" if c["passed"] else "❌"
                print(f"    {icon} {c['criterion']:<30} {c['reason']}")

        print("\n" + "=" * 60)
        print(f"✅ Series average score:  {output['series_average_score']} / 10")
        print(f"✅ Strongest episode:     Ep {output['strongest_episode']}")
        print(f"✅ Weakest episode:       Ep {output['weakest_episode']}")
        if output["critical_episodes"]:
            print(f"⚠  Critical episodes:     {output['critical_episodes']}")
        else:
            print("✅ No critical episodes.")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_cliffhanger_engine(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    module3_out = {"series_title": pipeline.get("series_title", "Untitled"),
                   "episodes": pipeline.get("episodes", [])}
    module4_out = {"story_type": pipeline.get("story_type", "thriller"),
                   "cliffhanger_weight": pipeline.get("cliffhanger_weight", 1.0)}

    report = await score_cliffhangers_async(module3_out, module4_out)
    report_dict = report.model_dump()

    # Attach scores to episodes
    score_map = {ep["episode_number"]: ep["adjusted_score"]
                 for ep in report_dict["episode_scores"]}
    pass_count_map = {ep["episode_number"]: ep["pass_count"]
                      for ep in report_dict["episode_scores"]}

    for ep in pipeline.get("episodes", []):
        ep_num = ep.get("episode_number")
        if ep_num in score_map:
            ep["cliffhanger_score"] = score_map[ep_num]
            ep["cliffhanger_pass_count"] = pass_count_map.get(ep_num, 0)

    # Build cliffhanger_breakdown for Lovable frontend
    pipeline["cliffhanger_breakdown"] = [
        {
            "episode_number": ep["episode_number"],
            "title": ep["title"],
            "score": ep["adjusted_score"],
            "criteria": [
                {
                    "criterion": c["criterion"],
                    "pass": c["passed"],
                    "reason": c["reason"]
                }
                for c in ep["criteria"]
            ]
        }
        for ep in report_dict["episode_scores"]
    ]
    return pipeline
