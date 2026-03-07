"""
Module 13 — Retention Risk Heatmap
NarrativeIQ Pipeline

For each episode, divides it into 6 time blocks of 15 seconds each (0–90s total).
Runs a heuristic rule engine across each block using signals from upstream modules:
  - Flat emotion zone (Module 6)
  - Weak cliffhanger score (Module 8)
  - Low continuity score (Module 9)
  - No action verbs detected (Module 5)
  - Arc deviation (Module 7)
  - Character outlier flags (Module 10)
  - Drop-off probability (Module 12)

Outputs per episode:
  - 6 blocks, each with: time_block label, risk_level (low/medium/high), reason string
  - An aggregate episode risk summary

Usage (standalone):
    python module_13_retention_heatmap.py

Runtime (called by Module 16):
    from module_13_retention_heatmap import generate_retention_heatmap
    heatmap = generate_retention_heatmap(episodes)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Literal

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

RiskLevel = Literal["low", "medium", "high"]

TIME_BLOCKS = [
    "0–15s",
    "15–30s",
    "30–45s",
    "45–60s",
    "60–75s",
    "75–90s",
]

# Block role in a typical short-form episode
BLOCK_ROLES = [
    "hook",          # 0–15s  — must grab attention immediately
    "setup",         # 15–30s — establish character/goal
    "development",   # 30–45s — build tension or introduce complication
    "midpoint",      # 45–60s — key information or reversal
    "escalation",    # 60–75s — raise stakes toward ending
    "cliffhanger",   # 75–90s — closing beat must compel next episode
]


@dataclass
class TimeBlock:
    time_block: str       # e.g. "0–15s"
    risk_level: RiskLevel
    reason: str
    risk_score: int       # internal 0–100, not exposed to frontend


@dataclass
class EpisodeHeatmap:
    episode_number: int
    title: str
    blocks: list[TimeBlock]
    overall_risk: RiskLevel
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    summary: str


# ---------------------------------------------------------------------------
# Rule engine — one function per block role
# Each returns (risk_score: int, reason: str)
# risk_score: 0–100  →  <35 low, 35–65 medium, >65 high
# ---------------------------------------------------------------------------

def _score_to_level(score: int) -> RiskLevel:
    if score >= 66:
        return "high"
    elif score >= 35:
        return "medium"
    return "low"


def _rule_hook(ep: dict) -> tuple[int, str]:
    """
    0–15s: Hook block.
    Risk drivers: flat emotion, low cliffhanger of PREVIOUS episode (cold open),
    no action verbs, high drop-off probability.
    """
    score = 0
    reasons = []

    # Flat opening emotion
    if ep.get("is_flat_zone"):
        score += 30
        reasons.append("episode opens in a flat emotional zone")

    # Very low emotion score at episode start
    emotion = ep.get("emotion_score", 0.5)
    if emotion < 0.30:
        score += 20
        reasons.append("low opening emotion intensity")
    elif emotion < 0.45:
        score += 10

    # No action verbs detected means passive cold open
    action_verbs = ep.get("action_verbs", [])
    if not action_verbs:
        score += 20
        reasons.append("no action verbs detected — hook may feel passive")

    # Poor continuity from previous episode weakens cold open
    continuity = ep.get("continuity_score", 1.0)
    if continuity < 0.65:
        score += 20
        reasons.append("weak link from previous episode's cliffhanger")
    elif continuity < 0.75:
        score += 10

    # High overall drop-off risk bleeds into hook
    drop_off = ep.get("drop_off_probability", 0.0)
    if drop_off > 0.55:
        score += 10

    reason = (
        "Strong hook — " + _top_positive_hook(ep)
        if score < 35
        else "Hook risk: " + "; ".join(reasons) if reasons
        else "Moderate hook — monitor opening pacing"
    )
    return min(score, 100), reason


def _top_positive_hook(ep: dict) -> str:
    if ep.get("continuity_score", 1.0) >= 0.85:
        return "strong cold-open continuation from previous cliffhanger"
    if ep.get("emotion_score", 0.5) >= 0.6:
        return "high opening emotional intensity grabs attention"
    if ep.get("action_verbs"):
        return f"action-driven opening ({ep['action_verbs'][0]} leads the scene)"
    return "episode opens without major risk signals"


def _rule_setup(ep: dict) -> tuple[int, str]:
    """
    15–30s: Setup block.
    Risk drivers: too many characters introduced at once, flat emotion,
    no locations detected (disorienting), low action verb count.
    """
    score = 0
    reasons = []

    characters = ep.get("characters", [])
    if len(characters) > 4:
        score += 25
        reasons.append(f"{len(characters)} characters present — may overwhelm viewer")
    elif len(characters) == 0:
        score += 15
        reasons.append("no characters detected in episode data")

    if ep.get("is_flat_zone"):
        score += 20
        reasons.append("flat emotional zone makes setup feel inert")

    locations = ep.get("locations", [])
    if not locations:
        score += 15
        reasons.append("no locations identified — spatial context unclear")

    action_verbs = ep.get("action_verbs", [])
    if len(action_verbs) < 2:
        score += 15
        reasons.append("low action verb density — setup may feel static")

    arc_dev = ep.get("arc_deviation", 0.0)
    if arc_dev > 0.20:
        score += 10
        reasons.append("emotion arc deviating from ideal early in episode")

    reason = (
        "Clean setup — character and location context established clearly"
        if score < 35
        else "Setup risk: " + "; ".join(reasons) if reasons
        else "Setup needs monitoring — moderate risk signals"
    )
    return min(score, 100), reason


def _rule_development(ep: dict) -> tuple[int, str]:
    """
    30–45s: Development / complication block.
    This is statistically the highest natural drop-off window.
    Risk drivers: flat zone, high arc deviation, no conflict keywords,
    low cliffhanger score (weak tension building).
    """
    score = 15  # base risk — development block is inherently vulnerable
    reasons = []

    if ep.get("is_flat_zone"):
        score += 30
        reasons.append("flat emotional zone — no tension escalation in development")

    arc_dev = ep.get("arc_deviation", 0.0)
    if arc_dev > 0.15:
        score += 20
        reasons.append(f"arc deviating {arc_dev:.2f} from ideal — pacing drift")

    conflict_keywords = ep.get("conflict_keywords", [])
    if not conflict_keywords:
        score += 20
        reasons.append("no conflict keywords detected — stakes unclear")

    cliff_score = ep.get("cliffhanger_score", 5.0)
    if cliff_score < 5.0:
        score += 15
        reasons.append("weak overall cliffhanger suggests low episode tension")

    drop_off = ep.get("drop_off_probability", 0.0)
    if drop_off > 0.40:
        score += 10
        reasons.append("high predicted drop-off risk for this episode")

    reason = (
        "Development on track — tension signals present"
        if score < 35
        else "Development risk: " + "; ".join(reasons) if reasons
        else "Development block needs attention — tension may be insufficient"
    )
    return min(score, 100), reason


def _rule_midpoint(ep: dict) -> tuple[int, str]:
    """
    45–60s: Midpoint / reversal block.
    Risk drivers: flat zone persisting past midpoint, no new character
    introductions, repeated locations only, low emotion score.
    """
    score = 0
    reasons = []

    if ep.get("is_flat_zone"):
        score += 35
        reasons.append("flat zone extends into midpoint — critical pacing failure")

    emotion = ep.get("emotion_score", 0.5)
    if emotion < 0.40:
        score += 25
        reasons.append("emotion intensity below 0.40 at midpoint")
    elif emotion < 0.55:
        score += 10

    arc_dev = ep.get("arc_deviation", 0.0)
    if arc_dev > 0.20:
        score += 20
        reasons.append("significant arc deviation — midpoint reversal likely missing")

    continuity = ep.get("continuity_score", 1.0)
    if continuity < 0.70:
        score += 15
        reasons.append("continuity gap may confuse viewer at episode midpoint")

    outliers = ep.get("character_outlier_count", 0)
    if outliers >= 2:
        score += 10
        reasons.append(f"{outliers} character inconsistencies detected — viewer may disengage")

    reason = (
        "Midpoint strong — reversal or new information likely present"
        if score < 35
        else "Midpoint risk: " + "; ".join(reasons) if reasons
        else "Midpoint needs a clearer reversal beat"
    )
    return min(score, 100), reason


def _rule_escalation(ep: dict) -> tuple[int, str]:
    """
    60–75s: Escalation block — stakes must rise toward the cliffhanger.
    Risk drivers: emotion not rising, weak cliffhanger score,
    no action verbs in late episode, flat zone.
    """
    score = 0
    reasons = []

    cliff_score = ep.get("cliffhanger_score", 5.0)
    if cliff_score < 5.0:
        score += 30
        reasons.append(f"cliffhanger score {cliff_score:.1f}/10 — ending unlikely to retain viewer")
    elif cliff_score < 7.0:
        score += 15
        reasons.append(f"cliffhanger score {cliff_score:.1f}/10 — escalation may feel weak")

    if ep.get("is_flat_zone"):
        score += 25
        reasons.append("flat zone persisting into escalation window — no stakes increase")

    emotion = ep.get("emotion_score", 0.5)
    if emotion < 0.55:
        score += 20
        reasons.append("emotion score below threshold for late-episode escalation")

    action_verbs = ep.get("action_verbs", [])
    if not action_verbs:
        score += 15
        reasons.append("no action verbs — escalation may be dialogue-only")

    arc_dev = ep.get("arc_deviation", 0.0)
    if arc_dev > 0.15:
        score += 10

    reason = (
        "Escalation strong — emotion and tension rising toward cliffhanger"
        if score < 35
        else "Escalation risk: " + "; ".join(reasons) if reasons
        else "Escalation needs sharper stakes before the closing beat"
    )
    return min(score, 100), reason


def _rule_cliffhanger_block(ep: dict) -> tuple[int, str]:
    """
    75–90s: Closing cliffhanger block — the most critical retention window.
    Risk drivers: low cliffhanger score, failed criteria count,
    low continuity to next episode, weak emotion at close.
    """
    score = 0
    reasons = []

    cliff_score = ep.get("cliffhanger_score", 5.0)
    if cliff_score < 5.0:
        score += 40
        reasons.append(f"cliffhanger score {cliff_score:.1f}/10 — closing beat is too weak")
    elif cliff_score < 7.0:
        score += 20
        reasons.append(f"cliffhanger score {cliff_score:.1f}/10 — closing beat needs strengthening")
    elif cliff_score >= 8.5:
        score -= 10  # bonus credit for strong cliffhanger

    pass_count = ep.get("cliffhanger_pass_count", 3)
    if pass_count <= 2:
        score += 25
        reasons.append(f"only {pass_count}/6 cliffhanger criteria passed")
    elif pass_count <= 3:
        score += 10

    continuity = ep.get("continuity_score", 1.0)
    if continuity < 0.65:
        score += 20
        reasons.append("low continuity — cliffhanger may not connect to next episode's opening")
    elif continuity < 0.75:
        score += 10

    emotion = ep.get("emotion_score", 0.5)
    if emotion < 0.50:
        score += 15
        reasons.append("low closing emotion — cliffhanger lacks emotional punch")

    drop_off = ep.get("drop_off_probability", 0.0)
    if drop_off > 0.50:
        score += 10
        reasons.append("high overall drop-off probability reinforces closing risk")

    reason = (
        "Strong cliffhanger — closing beat should compel next-episode play"
        if score < 35
        else "Cliffhanger risk: " + "; ".join(reasons) if reasons
        else "Closing beat needs reinforcement to drive next-episode retention"
    )
    return min(max(score, 0), 100), reason


# ---------------------------------------------------------------------------
# Block dispatcher
# ---------------------------------------------------------------------------

BLOCK_RULES = [
    _rule_hook,
    _rule_setup,
    _rule_development,
    _rule_midpoint,
    _rule_escalation,
    _rule_cliffhanger_block,
]


def _evaluate_blocks(ep: dict) -> list[TimeBlock]:
    """Run all 6 rule functions and return TimeBlock list."""
    blocks = []
    for i, (label, rule_fn) in enumerate(zip(TIME_BLOCKS, BLOCK_RULES)):
        risk_score, reason = rule_fn(ep)
        risk_level = _score_to_level(risk_score)
        blocks.append(TimeBlock(
            time_block=label,
            risk_level=risk_level,
            reason=reason,
            risk_score=risk_score,
        ))
    return blocks


# ---------------------------------------------------------------------------
# Episode-level aggregation
# ---------------------------------------------------------------------------

def _overall_risk(blocks: list[TimeBlock]) -> RiskLevel:
    """Derive overall episode risk from block distribution."""
    high   = sum(1 for b in blocks if b.risk_level == "high")
    medium = sum(1 for b in blocks if b.risk_level == "medium")

    if high >= 3:
        return "high"
    elif high >= 1 or medium >= 3:
        return "medium"
    return "low"


def _episode_summary(ep: dict, blocks: list[TimeBlock], overall: RiskLevel) -> str:
    """Plain-language one-line summary for the episode."""
    title = ep.get("title", f"Episode {ep.get('episode_number', '?')}")
    high_blocks = [b.time_block for b in blocks if b.risk_level == "high"]
    medium_blocks = [b.time_block for b in blocks if b.risk_level == "medium"]

    if overall == "low":
        return f"{title} has strong retention across all time blocks with no critical risk windows."
    elif overall == "medium":
        concern = ", ".join(medium_blocks) if medium_blocks else "mid-episode"
        return f"{title} shows moderate retention risk, particularly in the {concern} window(s)."
    else:
        concern = ", ".join(high_blocks) if high_blocks else "multiple"
        return (
            f"{title} has high drop-off risk in {concern} — "
            f"immediate structural attention recommended."
        )


# ---------------------------------------------------------------------------
# Public API — called by Module 16
# ---------------------------------------------------------------------------

def generate_retention_heatmap(episodes: list[dict]) -> list[dict]:
    """
    Main entry point for Module 16.

    Args:
        episodes: list of episode dicts from the pipeline. Each dict should
                  contain fields populated by Modules 5, 6, 7, 8, 9, 10, 12.

    Returns:
        List of episode heatmap dicts matching the Lovable frontend schema.

    Expected episode dict fields (all optional with safe defaults):
        episode_number          int
        title                   str
        is_flat_zone            int     (0/1, from Module 6)
        emotion_score           float   (0–1, from Module 6)
        arc_deviation           float   (0–1, from Module 7)
        cliffhanger_score       float   (0–10, from Module 8)
        cliffhanger_pass_count  int     (0–6, from Module 8)
        continuity_score        float   (0–1, from Module 9)
        character_outlier_count int     (from Module 10)
        drop_off_probability    float   (0–1, from Module 12)
        action_verbs            list[str] (from Module 5)
        conflict_keywords       list[str] (from Module 5)
        characters              list[str] (from Module 5)
        locations               list[str] (from Module 5)
    """
    results = []

    for ep in episodes:
        blocks = _evaluate_blocks(ep)
        overall = _overall_risk(blocks)
        summary = _episode_summary(ep, blocks, overall)

        heatmap = EpisodeHeatmap(
            episode_number=ep.get("episode_number", 0),
            title=ep.get("title", f"Episode {ep.get('episode_number', '?')}"),
            blocks=blocks,
            overall_risk=overall,
            high_risk_count=sum(1 for b in blocks if b.risk_level == "high"),
            medium_risk_count=sum(1 for b in blocks if b.risk_level == "medium"),
            low_risk_count=sum(1 for b in blocks if b.risk_level == "low"),
            summary=summary,
        )
        results.append(heatmap)

    return _serialize(results)


def _serialize(heatmaps: list[EpisodeHeatmap]) -> list[dict]:
    """Convert dataclasses to plain dicts, stripping internal risk_score."""
    output = []
    for hm in heatmaps:
        d = asdict(hm)
        # Remove internal field — not part of Lovable schema
        for block in d["blocks"]:
            block.pop("risk_score", None)
        output.append(d)
    return output


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

DEMO_EPISODES = [
    {
        "episode_number": 1,
        "title": "Dead Air",
        "is_flat_zone": 0,
        "emotion_score": 0.42,
        "arc_deviation": 0.08,
        "cliffhanger_score": 7.2,
        "cliffhanger_pass_count": 4,
        "continuity_score": 0.91,
        "character_outlier_count": 0,
        "drop_off_probability": 0.18,
        "action_verbs": ["intercepts", "traces", "activates"],
        "conflict_keywords": ["signal", "closed", "forbidden"],
        "characters": ["Maya Chen", "Director Osei", "The Voice"],
        "locations": ["Radio Tower 7", "Government Building"],
    },
    {
        "episode_number": 3,
        "title": "Static",
        "is_flat_zone": 1,
        "emotion_score": 0.58,
        "arc_deviation": 0.19,
        "cliffhanger_score": 5.4,
        "cliffhanger_pass_count": 3,
        "continuity_score": 0.72,
        "character_outlier_count": 1,
        "drop_off_probability": 0.41,
        "action_verbs": [],
        "conflict_keywords": ["encrypted", "classified"],
        "characters": ["Maya Chen", "Director Osei", "Dr. Reeves"],
        "locations": ["Bunker Interior", "Government Building"],
    },
    {
        "episode_number": 5,
        "title": "Broadcast",
        "is_flat_zone": 0,
        "emotion_score": 0.91,
        "arc_deviation": 0.04,
        "cliffhanger_score": 9.3,
        "cliffhanger_pass_count": 6,
        "continuity_score": 0.94,
        "character_outlier_count": 0,
        "drop_off_probability": 0.15,
        "action_verbs": ["exposes", "chooses", "broadcasts", "confronts"],
        "conflict_keywords": ["secret", "expose", "silence", "choice"],
        "characters": ["Maya Chen", "Director Osei", "The Voice"],
        "locations": ["Radio Tower 7", "Bunker Interior", "City Broadcast Hub"],
    },
]


def _print_heatmap(heatmap: dict) -> None:
    COLOURS = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    print(f"\n{'═'*62}")
    print(f"  Ep {heatmap['episode_number']} — {heatmap['title']}   "
          f"[Overall: {heatmap['overall_risk'].upper()}]")
    print(f"  {heatmap['summary']}")
    print(f"{'─'*62}")
    for block in heatmap["blocks"]:
        icon = COLOURS[block["risk_level"]]
        print(f"  {icon}  {block['time_block']:<8}  {block['risk_level'].upper():<7}  {block['reason']}")
    print(f"  Blocks — 🔴 {heatmap['high_risk_count']}  🟡 {heatmap['medium_risk_count']}  🟢 {heatmap['low_risk_count']}")


if __name__ == "__main__":
    print("[Module 13] Running retention risk heatmap on demo episodes …")
    results = generate_retention_heatmap(DEMO_EPISODES)
    for hm in results:
        _print_heatmap(hm)
    print(f"\n[Module 13] JSON output (first episode):")
    print(json.dumps(results[0], indent=2))


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_retention_heatmap(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    heatmaps = generate_retention_heatmap(pipeline.get("episodes", []))
    pipeline["retention_heatmap"] = heatmaps
    return pipeline
