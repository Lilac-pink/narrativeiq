"""
MODULE 6 — Emotional Arc Analyser
NarrativeIQ Episodic Intelligence Engine

Uses a HuggingFace sentiment model to score emotion intensity
per episode on a 0–1 scale. Flags flat zones where the score
delta from the previous episode is less than 0.05.
Outputs series-level EmotionalArc object.
"""

import os
from typing import List, Optional, Tuple
from transformers import pipeline as hf_pipeline
from models.module1_models import Episode, EmotionAnalysis, EmotionalArc


# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

# Model: cardiffnlp/twitter-roberta-base-sentiment-latest
# Labels: Negative / Neutral / Positive
# We derive emotion INTENSITY (not polarity) from this —
# high negative OR high positive = high intensity
# neutral = low intensity

SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
FLAT_ZONE_THRESHOLD = 0.05   # delta below this = flat zone
INTENSITY_BOOST_NEGATIVE = 1.0   # negative emotion counts fully toward intensity
INTENSITY_BOOST_POSITIVE = 0.85  # positive emotion slightly discounted vs negative for drama scoring


# ─────────────────────────────────────────
# MODEL LOADER
# Lazy-loaded once on first call
# ─────────────────────────────────────────

_sentiment_pipeline = None

def get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        print("[Module 6] Loading HuggingFace sentiment model...")
        _sentiment_pipeline = hf_pipeline(
            task="sentiment-analysis",
            model=SENTIMENT_MODEL,
            top_k=None,        # return all label scores
            truncation=True,
            max_length=512
        )
        print("[Module 6] Model loaded.")
    return _sentiment_pipeline


# ─────────────────────────────────────────
# INTENSITY SCORER
# Converts raw sentiment scores → 0–1 intensity
# ─────────────────────────────────────────

def compute_intensity(sentiment_output: List[dict]) -> Tuple[float, str]:
    """
    Takes HuggingFace output like:
        [{"label": "Negative", "score": 0.71},
         {"label": "Neutral",  "score": 0.20},
         {"label": "Positive", "score": 0.09}]

    Returns:
        intensity (float 0–1): how emotionally charged the text is
        dominant_label (str): the highest-scoring sentiment label

    Logic:
        - Neutral score pulls intensity DOWN
        - Negative and Positive scores push intensity UP
        - Negative weighted slightly higher (drama = conflict)
    """
    scores = {item["label"].lower(): item["score"] for item in sentiment_output}

    negative = scores.get("negative", 0.0)
    positive = scores.get("positive", 0.0)
    neutral  = scores.get("neutral",  0.0)

    # Weighted intensity: high neg or pos = high intensity
    # Reduce neutral penalty - narrative text is naturally more neutral than tweets
    raw_intensity = (
        negative * INTENSITY_BOOST_NEGATIVE +
        positive * INTENSITY_BOOST_POSITIVE -
        neutral  * 0.15   # reduced from 0.3 — narrative text is naturally more neutral
    )

    # Clamp to 0–1
    intensity = max(0.0, min(1.0, raw_intensity))

    # Dominant label
    dominant_label = max(scores, key=scores.get)

    return round(intensity, 4), dominant_label


# ─────────────────────────────────────────
# EPISODE-LEVEL SCORER
# ─────────────────────────────────────────

def score_episode_emotion(episode: Episode) -> float:
    """
    Run sentiment model on episode text.
    Uses raw_text (full prose) for best results, falls back to plot_beat + closing_beat.
    Returns emotion intensity score 0-1.
    """
    pipe = get_sentiment_pipeline()

    # Prefer rich raw_text, fall back to combining plot + closing beats
    raw = getattr(episode, "raw_text", "") or ""
    plot = getattr(episode, "plot_beat", "") or ""
    closing = getattr(episode, "closing_beat", "") or ""

    # Build best available text - raw_text gives most signal
    if raw and len(raw.strip()) > 50:
        text = raw.strip()[:512]
    elif plot or closing:
        text = (plot + " " + closing).strip()[:512]
    else:
        return 0.3  # default mid-low instead of 0

    if not text:
        return 0.3

    output = pipe(text)[0]
    intensity, _ = compute_intensity(output)

    # Boost: narrative text tends to score lower than tweets
    # Apply a gentle normalisation so scores spread across 0.1-0.9 range
    boosted = 0.15 + (intensity * 0.85)
    return round(min(1.0, boosted), 4)


# ─────────────────────────────────────────
# FLAT ZONE DETECTION
# ─────────────────────────────────────────

def detect_flat_zones(scores: List[float], threshold: float = FLAT_ZONE_THRESHOLD) -> List[int]:
    """
    Given a list of emotion scores (one per episode),
    return episode numbers (1-indexed) where the delta
    from the previous episode is below the threshold.

    Episode 1 is never flagged (no previous to compare to).
    """
    flat = []
    for i in range(1, len(scores)):
        delta = abs(scores[i] - scores[i - 1])
        if delta < threshold:
            flat.append(i + 1)  # 1-indexed episode number
    return flat


# ─────────────────────────────────────────
# SERIES-LEVEL ANALYSER
# Called by Module 16 Orchestrator
# ─────────────────────────────────────────

def analyse_emotional_arc(
    episodes: List[Episode],
    ideal_curve: Optional[List[float]] = None
) -> Tuple[List[Episode], EmotionalArc]:
    """
    Run emotion scoring across all episodes.
    Attaches EmotionAnalysis to each episode.
    Returns updated episodes + series-level EmotionalArc.

    Args:
        episodes:     List of Episode objects with plot_beat set
        ideal_curve:  Optional ideal curve from Module 4 Narrative DNA Classifier.
                      If None, a generic rising curve is used as placeholder.

    Usage (Module 16):
        episodes, arc = analyse_emotional_arc(episodes, ideal_curve)
    """
    print(f"[Module 6] Scoring emotional arc for {len(episodes)} episodes...")

    actual_scores: List[float] = []

    # ── Score each episode ──
    for episode in episodes:
        try:
            score = score_episode_emotion(episode)
        except Exception as e:
            print(f"  Episode {episode.episode_number} scoring failed: {e}. Defaulting to 0.5.")
            score = 0.5

        actual_scores.append(score)
        print(f"  Episode {episode.episode_number} ({episode.title}): intensity = {score}")

    # ── Detect flat zones ──
    flat_zone_episodes = detect_flat_zones(actual_scores)
    if flat_zone_episodes:
        print(f"  Flat zones detected at episodes: {flat_zone_episodes}")
    else:
        print("  No flat zones detected.")

    # ── Attach EmotionAnalysis to each episode ──
    for i, episode in enumerate(episodes):
        delta = None
        if i > 0:
            delta = round(actual_scores[i] - actual_scores[i - 1], 4)

        episode.emotion_analysis = EmotionAnalysis(
            emotion_score=actual_scores[i],
            is_flat_zone=(episode.episode_number in flat_zone_episodes),
            delta_from_previous=delta
        )
        episode.emotion_score = actual_scores[i]

    # ── Build ideal curve fallback ──
    if ideal_curve is None:
        n = len(episodes)
        # Generic rising curve: 0.3 → 0.95 linearly
        ideal_curve = [
            round(0.3 + (0.65 * i / max(n - 1, 1)), 4)
            for i in range(n)
        ]
        print("  No ideal curve provided — using default linear rising curve.")

    # ── Build EmotionalArc ──
    arc = EmotionalArc(
        actual_curve=actual_scores,
        ideal_curve=ideal_curve,
        flat_zones=flat_zone_episodes
    )

    print(f"[Module 6] Emotional arc analysis complete.")
    print(f"  Actual curve : {actual_scores}")
    print(f"  Ideal curve  : {ideal_curve}")
    print(f"  Flat zones   : {flat_zone_episodes}")

    return episodes, arc


# ─────────────────────────────────────────
# STANDALONE TEST
# Run: python module6_emotional_arc.py
# ─────────────────────────────────────────

if __name__ == "__main__":
    from models.module1_models import Episode

    test_episodes = [
        Episode(
            episode_number=1,
            title="Dead Air",
            plot_beat=(
                "Maya Chen, a late-night radio operator, picks up a mysterious signal "
                "from Station 7, a government facility sealed in 1991. "
                "Director Osei orders her to destroy the recording."
            )
        ),
        Episode(
            episode_number=2,
            title="Interference",
            plot_beat=(
                "Maya traces the signal coordinates to an abandoned bunker. "
                "Dr. Reeves warns that three investigators who found this location disappeared. "
                "Maya ignores the warning and drives there alone at dawn."
            )
        ),
        Episode(
            episode_number=3,
            title="Static",
            plot_beat=(
                "Inside the bunker, Maya finds encrypted files. "
                "She reads through documents and takes notes carefully. "
                "The files seem to contain some records from years ago."
            )
        ),
        Episode(
            episode_number=4,
            title="Frequency",
            plot_beat=(
                "Director Osei confronts Maya at gunpoint inside the government building. "
                "The Voice reveals it is an AI abandoned since 1991, and it threatens to "
                "expose everything unless Maya helps it broadcast the truth to the world."
            )
        ),
        Episode(
            episode_number=5,
            title="Broadcast",
            plot_beat=(
                "Maya faces an impossible choice: destroy the AI and bury the secret forever, "
                "or trigger a broadcast that will collapse the government and expose decades "
                "of crimes — with her life on the line either way."
            )
        ),
    ]

    updated_episodes, arc = analyse_emotional_arc(test_episodes)

    print("\n─── RESULTS ───")
    for ep in updated_episodes:
        flat_tag = " ⚠ FLAT ZONE" if ep.emotion_analysis.is_flat_zone else ""
        delta_str = f"  Δ{ep.emotion_analysis.delta_from_previous:+.4f}" if ep.emotion_analysis.delta_from_previous is not None else "  Δ—"
        print(f"Episode {ep.episode_number}: {ep.title}")
        print(f"  Score : {ep.emotion_score}{delta_str}{flat_tag}")

    print(f"\nSeries EmotionalArc:")
    print(f"  Actual : {arc.actual_curve}")
    print(f"  Ideal  : {arc.ideal_curve}")
    print(f"  Flat zones at episodes: {arc.flat_zones}")


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_emotional_arc(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    from models.module1_models import Episode
    episodes = [Episode(**ep) if isinstance(ep, dict) else ep
                for ep in pipeline.get("episodes", [])]
    ideal_curve = pipeline.get("emotional_arc", {}).get("ideal_curve", None)
    updated_episodes, arc = analyse_emotional_arc(episodes, ideal_curve)
    pipeline["episodes"] = [ep.dict() for ep in updated_episodes]
    pipeline["emotional_arc"] = arc.dict()
    return pipeline
