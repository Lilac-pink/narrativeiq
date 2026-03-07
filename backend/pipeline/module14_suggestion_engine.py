"""
Module 14 — Optimisation Suggestion Engine
Phase 4: Output & Explainability

Analyses all pipeline scores and generates prioritised, actionable suggestions
for the story creator. Uses Groq to generate intelligent narrative suggestions
based on the actual episode data.
"""

import os
import json
import asyncio
import logging
from typing import Optional
from groq import Groq

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "drop_off_high":       0.45,   # drop_off_probability above this = problem
    "drop_off_medium":     0.30,
    "cliffhanger_weak":    5.5,    # cliffhanger_score below this = problem
    "cliffhanger_medium":  7.0,
    "emotion_low":         0.30,   # emotion_score below this = problem
    "emotion_medium":      0.45,
    "continuity_poor":     0.65,   # continuity_score below this = problem
    "continuity_medium":   0.80,
    "arc_flat_threshold":  0.05,   # ideal vs actual deviation
}


# ---------------------------------------------------------------------------
# Rule-based issue detector
# ---------------------------------------------------------------------------

def _detect_issues(pipeline: dict) -> list[dict]:
    """
    Scan all episode scores and return a list of issues with severity.
    Each issue: {episode, field, value, severity, category, base_suggestion}
    """
    episodes = pipeline.get("episodes", [])
    issues = []

    for ep in episodes:
        ep_num = ep.get("episode_number", 0)
        title  = ep.get("title", f"Episode {ep_num}")

        drop_off    = ep.get("drop_off_probability", 0)
        cliffhanger = ep.get("cliffhanger_score", 5)
        emotion     = ep.get("emotion_score", 0.5)
        continuity  = ep.get("continuity_score", 0.8)

        # Drop-off risk
        if drop_off >= THRESHOLDS["drop_off_high"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Retention",
                "severity": "high",
                "value": drop_off,
                "field": "drop_off_probability",
                "base_suggestion": f"Episode {ep_num} ('{title}') has critical drop-off risk ({round(drop_off*100)}%). The pacing needs urgent attention.",
            })
        elif drop_off >= THRESHOLDS["drop_off_medium"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Retention",
                "severity": "medium",
                "value": drop_off,
                "field": "drop_off_probability",
                "base_suggestion": f"Episode {ep_num} ('{title}') has moderate drop-off risk ({round(drop_off*100)}%). Consider tightening the second act.",
            })

        # Cliffhanger weakness
        if cliffhanger < THRESHOLDS["cliffhanger_weak"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Cliffhanger",
                "severity": "high",
                "value": cliffhanger,
                "field": "cliffhanger_score",
                "base_suggestion": f"Episode {ep_num} ('{title}') ends weakly (cliffhanger score: {cliffhanger}/10). The closing scene needs a stronger hook.",
            })
        elif cliffhanger < THRESHOLDS["cliffhanger_medium"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Cliffhanger",
                "severity": "medium",
                "value": cliffhanger,
                "field": "cliffhanger_score",
                "base_suggestion": f"Episode {ep_num} ('{title}') has a serviceable but forgettable ending (score: {cliffhanger}/10). Punch it up.",
            })

        # Emotional flatness
        if emotion < THRESHOLDS["emotion_low"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Emotional Arc",
                "severity": "high",
                "value": emotion,
                "field": "emotion_score",
                "base_suggestion": f"Episode {ep_num} ('{title}') has very low emotional intensity ({round(emotion*100)}%). Characters feel distant — raise the personal stakes.",
            })
        elif emotion < THRESHOLDS["emotion_medium"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Emotional Arc",
                "severity": "medium",
                "value": emotion,
                "field": "emotion_score",
                "base_suggestion": f"Episode {ep_num} ('{title}') lacks emotional punch ({round(emotion*100)}%). Add a moment of vulnerability or conflict.",
            })

        # Continuity problems
        if continuity < THRESHOLDS["continuity_poor"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Continuity",
                "severity": "high",
                "value": continuity,
                "field": "continuity_score",
                "base_suggestion": f"Episode {ep_num} ('{title}') has serious continuity issues (score: {round(continuity*100)}%). Character or plot threads from previous episodes are breaking.",
            })
        elif continuity < THRESHOLDS["continuity_medium"]:
            issues.append({
                "episode": ep_num, "title": title,
                "category": "Continuity",
                "severity": "medium",
                "value": continuity,
                "field": "continuity_score",
                "base_suggestion": f"Episode {ep_num} ('{title}') has minor continuity gaps (score: {round(continuity*100)}%). Review character consistency.",
            })

    # Emotional arc shape issues
    arc  = pipeline.get("emotional_arc", {})
    ideal  = arc.get("ideal_curve", [])
    actual = arc.get("actual_curve", [])
    flat_zones = arc.get("flat_zones", [])

    if flat_zones:
        issues.append({
            "episode": flat_zones[0],
            "title": f"Episodes {', '.join(str(z) for z in flat_zones)}",
            "category": "Emotional Arc",
            "severity": "medium",
            "value": len(flat_zones),
            "field": "flat_zones",
            "base_suggestion": f"Flat emotional zones detected at episode(s) {', '.join(str(z) for z in flat_zones)}. The story loses momentum here — inject conflict, revelation, or character breakthrough.",
        })

    if ideal and actual and len(ideal) == len(actual):
        deviations = [abs(i - a) for i, a in zip(ideal, actual)]
        avg_dev = sum(deviations) / len(deviations)
        if avg_dev > 0.20:
            issues.append({
                "episode": 0,
                "title": "Series Arc",
                "category": "Series Structure",
                "severity": "medium",
                "value": avg_dev,
                "field": "arc_deviation",
                "base_suggestion": f"The overall emotional arc deviates significantly from the ideal curve (avg deviation: {round(avg_dev*100)}%). The series needs better pacing across its full run.",
            })

    return issues


# ---------------------------------------------------------------------------
# Groq-powered suggestion enhancer
# ---------------------------------------------------------------------------

async def _enhance_suggestion_with_groq(
    issue: dict,
    series_title: str,
    episode_context: dict,
    client: Groq,
    model: str,
) -> str:
    """
    Takes a rule-based issue and asks Groq to write a specific, actionable suggestion
    tailored to the actual episode content.
    """
    plot_beat   = episode_context.get("plot_beat", "")
    closing_beat = episode_context.get("closing_beat", "")
    raw_text    = episode_context.get("raw_text", plot_beat)

    prompt = f"""You are a senior TV script consultant reviewing the series "{series_title}".

EPISODE {issue['episode']}: "{issue['title']}"
Plot: {plot_beat}
Closing scene: {closing_beat}
Episode summary: {raw_text[:300] if raw_text else 'Not available'}

ISSUE DETECTED: {issue['base_suggestion']}
Category: {issue['category']} | Severity: {issue['severity']}

Write ONE specific, actionable suggestion (2-3 sentences max) that tells the writer EXACTLY what to change or add to fix this issue. Be concrete — reference the actual episode content. No preamble, just the suggestion."""

    try:
        loop = asyncio.get_event_loop()
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=150,
            )
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        log.warning(f"Groq suggestion enhancement failed: {e} — using base suggestion")
        return issue["base_suggestion"]


# ---------------------------------------------------------------------------
# Priority scorer
# ---------------------------------------------------------------------------

def _priority_score(issue: dict) -> float:
    """Higher = more important. Used to rank suggestions."""
    severity_weight = {"high": 3.0, "medium": 1.5, "low": 0.5}.get(issue["severity"], 1.0)
    field_weight = {
        "drop_off_probability": 2.5,
        "cliffhanger_score": 2.0,
        "emotion_score": 1.8,
        "continuity_score": 1.5,
        "flat_zones": 1.3,
        "arc_deviation": 1.0,
    }.get(issue["field"], 1.0)

    value = issue.get("value", 0.5)
    if issue["field"] == "drop_off_probability":
        impact = value * 10
    elif issue["field"] == "cliffhanger_score":
        impact = (10 - value)
    elif issue["field"] in ("emotion_score", "continuity_score"):
        impact = (1 - value) * 10
    else:
        impact = 5.0

    return round(severity_weight * field_weight * (impact / 10) * 10, 1)


# ---------------------------------------------------------------------------
# Public API — called by Module 16
# ---------------------------------------------------------------------------

async def run_suggestion_engine(pipeline: dict, model: str = "llama-3.1-8b-instant") -> dict:
    """
    Analyses all pipeline scores and populates pipeline['suggestions']
    with a prioritised list of actionable suggestions.
    """
    log.info("[Module 14] Generating optimisation suggestions...")

    series_title = pipeline.get("series_title", "Untitled Series")
    episodes     = pipeline.get("episodes", [])

    if not episodes:
        log.warning("[Module 14] No episodes found — skipping")
        pipeline.setdefault("suggestions", [])
        return pipeline

    # Build episode lookup for context
    ep_lookup = {ep.get("episode_number"): ep for ep in episodes}

    # Step 1: Detect issues from scores
    issues = _detect_issues(pipeline)
    log.info(f"[Module 14] Detected {len(issues)} issues across {len(episodes)} episodes")

    if not issues:
        pipeline["suggestions"] = [{
            "priority": 1,
            "episode": 0,
            "category": "Overall",
            "suggestion": "Your story scores well across all metrics! Focus on ensuring each episode's cliffhanger feels earned and distinct from the others.",
            "impact_score": 5.0,
        }]
        return pipeline

    # Step 2: Sort by priority score
    issues.sort(key=_priority_score, reverse=True)
    top_issues = issues[:8]  # Max 8 suggestions to avoid rate limiting

    # Step 3: Enhance top issues with Groq (with rate limit throttling)
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        client  = Groq(api_key=api_key) if api_key else None
    except Exception:
        client = None

    suggestions = []
    for i, issue in enumerate(top_issues):
        ep_context = ep_lookup.get(issue["episode"], {})

        if client and ep_context:
            suggestion_text = await _enhance_suggestion_with_groq(
                issue, series_title, ep_context, client, model
            )
            await asyncio.sleep(0.5)  # throttle
        else:
            suggestion_text = issue["base_suggestion"]

        suggestions.append({
            "priority":     i + 1,
            "episode":      issue["episode"],
            "category":     issue["category"],
            "suggestion":   suggestion_text,
            "impact_score": _priority_score(issue),
        })

    pipeline["suggestions"] = suggestions
    log.info(f"[Module 14] Generated {len(suggestions)} suggestions ✓")
    return pipeline
