"""
Module 7 — Arc Deviation Scorer
Phase 4: Scoring Engines

Compares the actual emotional curve (from Module 6 — Emotional Arc Analyser)
against the ideal curve (from Module 4 — Narrative DNA Classifier) episode by
episode and produces a rich deviation report.

No GPT calls. Pure math. Fast and deterministic.

Inputs (from pipeline):
  - module4_output: dict  → ideal_curve, story_type, cliffhanger_weight, pacing_note
  - module6_output: dict  → actual_curve, flat_zones, episode_scores

Outputs feed into:
  - Module 14 (Optimisation Suggestion Engine) — deviation context for GPT prompts
  - Module 15 (Score Explainer)               — scores to convert to plain English
  - Module 16 (Orchestrator)                  — aggregated into final JSON
  - Lovable frontend                           — emotional_arc block
"""

import math
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------

class EpisodeDeviation(BaseModel):
    episode_number: int
    actual_score: float = Field(..., ge=0.0, le=1.0)
    ideal_score: float = Field(..., ge=0.0, le=1.0)
    raw_deviation: float = Field(
        ...,
        description="Signed deviation: actual − ideal. Negative = below ideal, positive = above."
    )
    absolute_deviation: float = Field(
        ...,
        description="Absolute value of raw_deviation."
    )
    deviation_pct: float = Field(
        ...,
        description="Absolute deviation as a percentage of the ideal score (0–100)."
    )
    severity: str = Field(
        ...,
        description="One of: on_track | mild_deviation | moderate_deviation | severe_deviation"
    )
    direction: str = Field(
        ...,
        description="One of: above_ideal | below_ideal | on_target"
    )
    is_flat_zone: bool = Field(
        ...,
        description="True if Module 6 flagged this episode as a flat zone."
    )
    deviation_score: float = Field(
        ...,
        description="Inverted score 0–10. 10 = perfect match, 0 = maximum deviation."
    )
    note: str = Field(
        ...,
        description="Human-readable one-line diagnostic for this episode."
    )


class ArcDeviationReport(BaseModel):
    series_title: str
    story_type: str
    total_episodes: int

    # Per-episode breakdown
    episode_deviations: list[EpisodeDeviation]

    # Series-level aggregates
    mean_absolute_error: float = Field(
        ...,
        description="MAE across all episodes. Lower = better arc alignment."
    )
    root_mean_square_error: float = Field(
        ...,
        description="RMSE — penalises large deviations more than MAE."
    )
    overall_arc_score: float = Field(
        ...,
        description="Composite arc quality score 0–10. 10 = perfect match to ideal."
    )
    worst_episode: int = Field(
        ...,
        description="Episode number with highest absolute deviation."
    )
    best_episode: int = Field(
        ...,
        description="Episode number with lowest absolute deviation."
    )
    flat_zone_episodes: list[int] = Field(
        ...,
        description="Episodes flagged as flat zones by Module 6."
    )
    trend_diagnosis: str = Field(
        ...,
        description="Overall arc trend: consistently_below | consistently_above | volatile | well_aligned"
    )
    structural_warnings: list[str] = Field(
        default_factory=list,
        description="List of specific structural problems detected (e.g. flat midpoint, premature peak)."
    )
    pacing_note: str = Field(
        ...,
        description="Passed through from Module 4 template for context."
    )


# ---------------------------------------------------------------------------
# Severity thresholds
# ---------------------------------------------------------------------------

# Absolute deviation → severity label
SEVERITY_THRESHOLDS = [
    (0.00, 0.05,  "on_track"),
    (0.05, 0.12,  "mild_deviation"),
    (0.12, 0.22,  "moderate_deviation"),
    (0.22, 1.00,  "severe_deviation"),
]


def _severity(absolute_deviation: float) -> str:
    for lo, hi, label in SEVERITY_THRESHOLDS:
        if lo <= absolute_deviation < hi:
            return label
    return "severe_deviation"


def _direction(raw_deviation: float) -> str:
    if raw_deviation > 0.03:
        return "above_ideal"
    if raw_deviation < -0.03:
        return "below_ideal"
    return "on_target"


def _deviation_score(absolute_deviation: float) -> float:
    """
    Converts absolute deviation (0–1 range) to a 0–10 quality score.
    0.0 deviation  → 10.0 (perfect)
    0.5+ deviation → 0.0  (worst case)
    Uses a linear decay capped at 0.
    """
    score = 10.0 - (absolute_deviation / 0.5) * 10.0
    return round(max(0.0, min(10.0, score)), 2)


def _episode_note(ep: int, raw_dev: float, severity: str, is_flat: bool) -> str:
    """Generates a one-line diagnostic note for an episode."""
    direction_word = "above" if raw_dev > 0 else "below"
    delta = abs(raw_dev)

    if severity == "on_track":
        note = f"Ep {ep}: Emotion intensity is well-aligned with the ideal arc."
    elif severity == "mild_deviation":
        note = f"Ep {ep}: Slightly {direction_word} ideal by {delta:.2f} — acceptable variance."
    elif severity == "moderate_deviation":
        note = f"Ep {ep}: Noticeably {direction_word} ideal by {delta:.2f} — review pacing."
    else:
        note = f"Ep {ep}: Severely {direction_word} ideal by {delta:.2f} — structural rewrite may be needed."

    if is_flat:
        note += " ⚠ Flat zone detected — intensity stagnant between this and adjacent episode."

    return note


# ---------------------------------------------------------------------------
# Structural warnings detector
# ---------------------------------------------------------------------------

def _detect_structural_warnings(
    deviations: list[EpisodeDeviation],
    actual_curve: list[float],
    ideal_curve: list[float],
    story_type: str,
) -> list[str]:
    """
    Runs a set of heuristic checks against the full arc and returns
    plain-English warnings for the suggestion engine.
    """
    warnings = []
    n = len(actual_curve)

    if n < 2:
        return warnings

    # 1. Premature emotional peak — actual peaks before last 2 episodes
    peak_idx = actual_curve.index(max(actual_curve))
    if peak_idx < n - 2:
        warnings.append(
            f"Premature emotional peak at episode {peak_idx + 1}. "
            f"The story's highest intensity should land in the final episodes."
        )

    # 2. Flat opening — first episode emotion too low vs ideal
    if actual_curve[0] < ideal_curve[0] - 0.15:
        warnings.append(
            f"Weak opening: episode 1 emotion ({actual_curve[0]:.2f}) is well below "
            f"the ideal ({ideal_curve[0]:.2f}). Risk of losing audience before episode 2."
        )

    # 3. Sagging middle — episodes 2 to n-2 all below ideal
    if n >= 4:
        mid_slice_actual = actual_curve[1:-1]
        mid_slice_ideal  = ideal_curve[1:-1]
        if all(a < i - 0.08 for a, i in zip(mid_slice_actual, mid_slice_ideal)):
            warnings.append(
                "Sagging middle: all mid-series episodes fall below the ideal arc. "
                "Audience drop-off risk is elevated."
            )

    # 4. Emotional cliff at finale — last episode drops vs second-to-last
    if actual_curve[-1] < actual_curve[-2] - 0.05:
        warnings.append(
            f"Emotional cliff at finale: episode {n} ({actual_curve[-1]:.2f}) drops below "
            f"episode {n - 1} ({actual_curve[-2]:.2f}). Finales should sustain or exceed prior intensity."
        )

    # 5. Zero progression — overall range too narrow (flat series arc)
    arc_range = max(actual_curve) - min(actual_curve)
    if arc_range < 0.25:
        warnings.append(
            f"Flat series arc: total emotional range is only {arc_range:.2f}. "
            "The series lacks emotional contrast — consider amplifying highs and lows."
        )

    # 6. Consecutive declining episodes mid-series (3 or more in a row, not at the end)
    if n >= 4:
        decline_run = 0
        for i in range(1, n - 1):
            if actual_curve[i] < actual_curve[i - 1]:
                decline_run += 1
                if decline_run >= 2:
                    warnings.append(
                        f"Three or more consecutive episodes of declining emotion starting at "
                        f"episode {i - 1}. Sustained downward trend mid-series kills momentum."
                    )
                    break
            else:
                decline_run = 0

    # 7. Story-type-specific check — tragedy shouldn't end high
    if story_type == "tragedy" and actual_curve[-1] > 0.60:
        warnings.append(
            "Tragedy arc anomaly: the finale emotion score is high, suggesting a positive resolution. "
            "Tragedies should end with emotional devastation, not triumph."
        )

    # 8. Story-type-specific check — romance missing midpoint dip
    if story_type == "romance" and n >= 3:
        mid = n // 2
        if actual_curve[mid] > actual_curve[mid - 1]:
            warnings.append(
                "Romance arc anomaly: the midpoint episode does not show the expected emotional dip "
                "(the separation/conflict beat). This weakens the emotional payoff of the reunion."
            )

    return warnings


# ---------------------------------------------------------------------------
# Trend diagnosis
# ---------------------------------------------------------------------------

def _diagnose_trend(deviations: list[EpisodeDeviation]) -> str:
    above = sum(1 for d in deviations if d.direction == "above_ideal")
    below = sum(1 for d in deviations if d.direction == "below_ideal")
    n = len(deviations)

    if above / n >= 0.7:
        return "consistently_above"
    if below / n >= 0.7:
        return "consistently_below"

    severe_count = sum(1 for d in deviations if d.severity == "severe_deviation")
    if severe_count >= n * 0.4:
        return "volatile"

    return "well_aligned"


# ---------------------------------------------------------------------------
# Core scorer function
# ---------------------------------------------------------------------------

def score_arc_deviation(
    module4_output: dict,
    module6_output: dict,
) -> ArcDeviationReport:
    """
    Computes arc deviation scores by comparing actual vs ideal emotional curves.

    Args:
        module4_output: Output dict from Module 4 run().
                        Required keys: ideal_curve, story_type, pacing_note, series_title, total_episodes
        module6_output: Output dict from Module 6 run().
                        Required keys: actual_curve, flat_zones, episode_scores (list of dicts with episode_number)

    Returns:
        ArcDeviationReport: Full deviation breakdown, series scores, and structural warnings.

    Raises:
        ValueError: If curves have mismatched lengths or missing keys.
    """
    # --- Extract inputs ---
    ideal_curve: list[float]  = module4_output["ideal_curve"]
    story_type: str           = module4_output["story_type"]
    pacing_note: str          = module4_output.get("pacing_note", "")
    series_title: str         = module4_output.get("series_title", "Untitled")

    actual_curve: list[float] = module6_output["actual_curve"]
    flat_zones: list[int]     = module6_output.get("flat_zones", [])     # episode numbers (1-indexed)

    if len(actual_curve) != len(ideal_curve):
        raise ValueError(
            f"Arc Deviation Scorer: Curve length mismatch. "
            f"actual={len(actual_curve)}, ideal={len(ideal_curve)}. "
            f"Ensure Module 4 scaled ideal_curve to the correct episode count."
        )

    n = len(actual_curve)

    # --- Per-episode deviation ---
    episode_deviations: list[EpisodeDeviation] = []

    for i, (actual, ideal) in enumerate(zip(actual_curve, ideal_curve)):
        ep_num     = i + 1
        raw_dev    = round(actual - ideal, 4)
        abs_dev    = round(abs(raw_dev), 4)
        dev_pct    = round((abs_dev / ideal) * 100, 1) if ideal > 0 else 0.0
        severity   = _severity(abs_dev)
        direction  = _direction(raw_dev)
        is_flat    = ep_num in flat_zones
        dev_score  = _deviation_score(abs_dev)
        note       = _episode_note(ep_num, raw_dev, severity, is_flat)

        episode_deviations.append(EpisodeDeviation(
            episode_number    = ep_num,
            actual_score      = round(actual, 4),
            ideal_score       = round(ideal, 4),
            raw_deviation     = raw_dev,
            absolute_deviation= abs_dev,
            deviation_pct     = dev_pct,
            severity          = severity,
            direction         = direction,
            is_flat_zone      = is_flat,
            deviation_score   = dev_score,
            note              = note,
        ))

    # --- Series-level aggregates ---
    abs_devs = [d.absolute_deviation for d in episode_deviations]

    mae  = round(sum(abs_devs) / n, 4)
    rmse = round(math.sqrt(sum(d ** 2 for d in abs_devs) / n), 4)

    # Overall arc score: invert MAE on 0–10 scale
    # MAE of 0.0 → 10.0 | MAE of 0.4+ → 0.0
    overall_arc_score = round(max(0.0, 10.0 - (mae / 0.4) * 10.0), 2)

    worst_ep = episode_deviations[
        abs_devs.index(max(abs_devs))
    ].episode_number

    best_ep = episode_deviations[
        abs_devs.index(min(abs_devs))
    ].episode_number

    trend = _diagnose_trend(episode_deviations)

    structural_warnings = _detect_structural_warnings(
        episode_deviations, actual_curve, ideal_curve, story_type
    )

    return ArcDeviationReport(
        series_title        = series_title,
        story_type          = story_type,
        total_episodes      = n,
        episode_deviations  = episode_deviations,
        mean_absolute_error = mae,
        root_mean_square_error = rmse,
        overall_arc_score   = overall_arc_score,
        worst_episode       = worst_ep,
        best_episode        = best_ep,
        flat_zone_episodes  = flat_zones,
        trend_diagnosis     = trend,
        structural_warnings = structural_warnings,
        pacing_note         = pacing_note,
    )


# ---------------------------------------------------------------------------
# Pipeline-compatible wrapper
# ---------------------------------------------------------------------------

def run(module4_output: dict, module6_output: dict) -> dict:
    """
    Pipeline entry point called by the Module 16 Orchestrator.

    Args:
        module4_output: Output dict from Module 4 run().
        module6_output: Output dict from Module 6 run().

    Returns:
        dict: JSON-serialisable ArcDeviationReport dict.
    """
    report = score_arc_deviation(module4_output, module6_output)
    return report.model_dump()


# ---------------------------------------------------------------------------
# CLI — run directly for testing (uses mock Module 4 + 6 outputs)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    # Mock Module 4 output (Narrative DNA Classifier)
    mock_module4 = {
        "series_title": "The Forgotten Signal",
        "story_type": "mystery",
        "total_episodes": 5,
        "ideal_curve": [0.25, 0.40, 0.60, 0.75, 0.95],
        "cliffhanger_weight": 1.2,
        "pacing_note": (
            "Clues must drip-feed. Emotional intensity tracks information density."
        ),
        "archetype_confidence": 0.88,
        "thematic_keywords": ["conspiracy", "signal", "truth", "government", "isolation"],
        "protagonist_arc": "Maya transforms from passive observer to active disruptor of institutional power.",
    }

    # Mock Module 6 output (Emotional Arc Analyser)
    # Episode 3 is intentionally flat/off to trigger warnings
    mock_module6 = {
        "actual_curve": [0.42, 0.61, 0.58, 0.79, 0.91],
        "flat_zones": [3],
        "episode_scores": [
            {"episode_number": 1, "emotion_score": 0.42},
            {"episode_number": 2, "emotion_score": 0.61},
            {"episode_number": 3, "emotion_score": 0.58},
            {"episode_number": 4, "emotion_score": 0.79},
            {"episode_number": 5, "emotion_score": 0.91},
        ],
    }

    print("=" * 60)
    print("MODULE 7 — ARC DEVIATION SCORER")
    print("=" * 60)
    print(f"\nSeries: {mock_module4['series_title']}")
    print(f"Story type: {mock_module4['story_type']}")
    print(f"\nIdeal curve:  {mock_module4['ideal_curve']}")
    print(f"Actual curve: {mock_module6['actual_curve']}")
    print(f"Flat zones:   {mock_module6['flat_zones']}\n")

    try:
        output = run(mock_module4, mock_module6)

        # Print episode table
        print(f"{'Ep':<4} {'Actual':>7} {'Ideal':>7} {'RawDev':>8} {'AbsDev':>8} {'Score':>7}  Severity")
        print("-" * 65)
        for ep in output["episode_deviations"]:
            flat_marker = " ⚠" if ep["is_flat_zone"] else ""
            print(
                f"Ep{ep['episode_number']:<2} "
                f"{ep['actual_score']:>7.3f} "
                f"{ep['ideal_score']:>7.3f} "
                f"{ep['raw_deviation']:>+8.3f} "
                f"{ep['absolute_deviation']:>8.3f} "
                f"{ep['deviation_score']:>7.1f}  "
                f"{ep['severity']}{flat_marker}"
            )

        print("\n" + "=" * 60)
        print(f"✅ MAE:               {output['mean_absolute_error']}")
        print(f"✅ RMSE:              {output['root_mean_square_error']}")
        print(f"✅ Overall arc score: {output['overall_arc_score']} / 10")
        print(f"✅ Worst episode:     Ep {output['worst_episode']}")
        print(f"✅ Best episode:      Ep {output['best_episode']}")
        print(f"✅ Trend diagnosis:   {output['trend_diagnosis']}")

        if output["structural_warnings"]:
            print(f"\n⚠  Structural warnings ({len(output['structural_warnings'])}):")
            for w in output["structural_warnings"]:
                print(f"   • {w}")
        else:
            print("\n✅ No structural warnings detected.")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_arc_deviation(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    module4_out = pipeline.get("narrative_dna", {})
    module6_out = pipeline.get("emotional_arc", {})

    if not module4_out or not module6_out:
        print("[Module 7] Missing narrative_dna or emotional_arc — skipping arc deviation.")
        return pipeline

    report = score_arc_deviation(module4_out, module6_out)
    report_dict = report.dict()

    # Attach per-episode arc_deviation scores back to episodes
    ep_deviations = {d["episode_number"]: d["absolute_deviation"]
                     for d in report_dict["episode_deviations"]}
    for ep in pipeline.get("episodes", []):
        ep_num = ep.get("episode_number")
        if ep_num in ep_deviations:
            ep["arc_deviation"] = ep_deviations[ep_num]

    pipeline["arc_deviation_report"] = report_dict
    pipeline.setdefault("emotional_arc", {})["overall_deviation_score"] = report_dict["overall_arc_score"]
    return pipeline
