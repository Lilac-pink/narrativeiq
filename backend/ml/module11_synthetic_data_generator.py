"""
Module 11 — Synthetic Training Data Generator
NarrativeIQ Pipeline

Generates labeled synthetic episode feature vectors for training
the Module 12 GradientBoosting drop-off predictor.

Each row = one episode's features + a drop-off probability label.
Output: synthetic_training_data.csv

Usage:
    python module_11_synthetic_data_generator.py
    python module_11_synthetic_data_generator.py --samples 2000 --output my_data.csv --seed 99
"""

import argparse
import csv
import random
import math
import os
from dataclasses import dataclass, fields, astuple


# ---------------------------------------------------------------------------
# Feature schema — mirrors the fields Module 12 will consume at runtime
# ---------------------------------------------------------------------------

@dataclass
class EpisodeFeatureVector:
    # Core NLP / scoring features (Modules 5–8)
    emotion_score: float            # 0.0–1.0  (Module 6)
    emotion_delta: float            # change from previous episode; -1.0–1.0
    is_flat_zone: int               # 1 if episode flagged as flat (Module 6)
    arc_deviation: float            # MAE gap from ideal curve (Module 7)
    cliffhanger_score: float        # 0.0–10.0 (Module 8)
    cliffhanger_pass_count: int     # 0–6 criteria passed (Module 8)

    # Embedding / similarity features (Modules 9–10)
    continuity_score: float         # 0.0–1.0 cosine similarity (Module 9)
    continuity_severity: int        # 0=none, 1=medium, 2=high (Module 9)
    character_outlier_count: int    # number of contradictory trait flags (Module 10)

    # Structural / positional features
    episode_position: float         # normalised position in series 0.0–1.0
    is_series_opener: int           # 1 if episode 1
    is_series_finale: int           # 1 if last episode

    # Retention heatmap aggregate features (Module 13)
    heatmap_high_risk_blocks: int   # 0–6 blocks rated high risk
    heatmap_medium_risk_blocks: int # 0–6 blocks rated medium risk

    # Label
    drop_off_probability: float     # 0.0–1.0  ← target variable


# ---------------------------------------------------------------------------
# Generation rules
# Realistic correlations based on domain logic:
#   - High drop-off when: flat zone + weak cliffhanger + poor continuity
#   - Low drop-off when: rising emotion + strong cliffhanger + good continuity
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _noise(scale: float = 0.05) -> float:
    """Small Gaussian noise."""
    return random.gauss(0, scale)


def generate_episode(
    episode_index: int,
    total_episodes: int,
    rng: random.Random,
    story_type: str,
) -> EpisodeFeatureVector:
    """
    Generate one synthetic episode feature vector with realistic correlations.
    story_type controls the general arc shape.
    """

    position = episode_index / max(total_episodes - 1, 1)   # 0.0 → 1.0
    is_opener = int(episode_index == 0)
    is_finale = int(episode_index == total_episodes - 1)

    # ---- Emotion score based on story type arc shape ----
    if story_type == "thriller":
        # gradual rise with a mid-series dip
        base_emotion = 0.3 + 0.6 * position - 0.15 * math.sin(position * math.pi)
    elif story_type == "romance":
        # U-shape: high open, dip middle, high finale
        base_emotion = 0.6 - 0.35 * math.sin(position * math.pi)
    elif story_type == "mystery":
        # slow build then sharp late rise
        base_emotion = 0.25 + 0.7 * (position ** 1.8)
    elif story_type == "drama":
        # steady rise
        base_emotion = 0.3 + 0.65 * position
    else:  # default
        base_emotion = 0.4 + 0.4 * position

    emotion_score = _clamp(base_emotion + _noise(0.08))

    # ---- Flat zone: 20% base chance, higher mid-series ----
    flat_prob = 0.12 + 0.18 * math.sin(position * math.pi)
    is_flat_zone = int(rng.random() < flat_prob)
    if is_flat_zone:
        emotion_score = _clamp(base_emotion + _noise(0.02))  # tighter cluster

    # ---- Emotion delta (vs previous) ----
    if episode_index == 0:
        emotion_delta = 0.0
    else:
        emotion_delta = _clamp(
            (0.0 if is_flat_zone else rng.uniform(-0.1, 0.25)) + _noise(0.04),
            lo=-1.0, hi=1.0
        )

    # ---- Arc deviation ----
    arc_deviation = _clamp(
        (0.18 if is_flat_zone else rng.uniform(0.02, 0.12)) + _noise(0.03)
    )

    # ---- Cliffhanger ----
    # Finales and openers score higher on average
    cliff_base = 7.0 + (1.5 if is_finale else 0) + (-1.0 if is_flat_zone else 0)
    cliffhanger_score = _clamp(
        cliff_base + rng.gauss(0, 1.2),
        lo=0.0, hi=10.0
    )
    # pass_count correlates with score
    cliffhanger_pass_count = min(6, max(0, round(cliffhanger_score / 10 * 6 + rng.gauss(0, 0.5))))

    # ---- Continuity ----
    continuity_score = _clamp(rng.uniform(0.6, 0.98) + _noise(0.04))
    if continuity_score < 0.65:
        continuity_severity = 2   # high
    elif continuity_score < 0.75:
        continuity_severity = 1   # medium
    else:
        continuity_severity = 0

    # ---- Character outliers ----
    character_outlier_count = rng.choices([0, 1, 2, 3], weights=[0.65, 0.20, 0.10, 0.05])[0]

    # ---- Retention heatmap blocks ----
    high_risk = rng.randint(0, 2) + (2 if is_flat_zone else 0)
    high_risk = min(high_risk, 6)
    medium_risk = rng.randint(0, 3 - high_risk // 2)
    medium_risk = min(medium_risk, 6 - high_risk)

    # ----------------------------------------------------------------
    # DROP-OFF PROBABILITY — derived from above features with noise
    # ----------------------------------------------------------------
    drop_off = 0.10   # baseline

    # Flat zone is the single strongest signal
    drop_off += 0.20 * is_flat_zone

    # Weak cliffhanger raises risk
    drop_off += _clamp(0.18 * (1 - cliffhanger_score / 10))

    # Arc deviation
    drop_off += 0.15 * arc_deviation

    # Poor continuity
    drop_off += 0.12 * (1 - continuity_score)
    drop_off += 0.06 * continuity_severity / 2

    # Character inconsistency
    drop_off += 0.04 * min(character_outlier_count, 3) / 3

    # Retention heatmap
    drop_off += 0.08 * high_risk / 6
    drop_off += 0.04 * medium_risk / 6

    # Series position: mid-series is highest natural churn point
    churn_curve = 0.08 * math.sin(position * math.pi)
    drop_off += churn_curve

    # Openers and finales retain better
    drop_off -= 0.08 * (is_opener + is_finale)

    # Add noise and clamp
    drop_off = _clamp(drop_off + _noise(0.04))

    return EpisodeFeatureVector(
        emotion_score=round(emotion_score, 4),
        emotion_delta=round(emotion_delta, 4),
        is_flat_zone=is_flat_zone,
        arc_deviation=round(arc_deviation, 4),
        cliffhanger_score=round(cliffhanger_score, 4),
        cliffhanger_pass_count=cliffhanger_pass_count,
        continuity_score=round(continuity_score, 4),
        continuity_severity=continuity_severity,
        character_outlier_count=character_outlier_count,
        episode_position=round(position, 4),
        is_series_opener=is_opener,
        is_series_finale=is_finale,
        heatmap_high_risk_blocks=high_risk,
        heatmap_medium_risk_blocks=medium_risk,
        drop_off_probability=round(drop_off, 4),
    )


def generate_dataset(
    n_samples: int = 1000,
    seed: int = 42,
    series_length_range: tuple = (3, 12),
) -> list[EpisodeFeatureVector]:
    """
    Generate n_samples episode records across many synthetic series.
    Each synthetic series has a random length and story type.
    """
    rng = random.Random(seed)
    story_types = ["thriller", "romance", "mystery", "drama", "other"]
    records: list[EpisodeFeatureVector] = []

    while len(records) < n_samples:
        series_len = rng.randint(*series_length_range)
        story_type = rng.choice(story_types)

        for ep_idx in range(series_len):
            record = generate_episode(ep_idx, series_len, rng, story_type)
            records.append(record)

            if len(records) >= n_samples:
                break

    return records[:n_samples]


def save_to_csv(records: list[EpisodeFeatureVector], output_path: str) -> None:
    """Write records to CSV with a header row."""
    header = [f.name for f in fields(EpisodeFeatureVector)]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for record in records:
            writer.writerow(astuple(record))

    print(f"[Module 11] Wrote {len(records)} records to {output_path}")


def print_stats(records: list[EpisodeFeatureVector]) -> None:
    """Print basic distribution stats for sanity checking."""
    n = len(records)
    drop_offs = [r.drop_off_probability for r in records]
    flat_zones = sum(r.is_flat_zone for r in records)
    high_cliffs = sum(1 for r in records if r.cliffhanger_score >= 7.5)

    print(f"\n[Module 11] Dataset statistics ({n} samples)")
    print(f"  Drop-off probability  — mean: {sum(drop_offs)/n:.3f}  "
          f"min: {min(drop_offs):.3f}  max: {max(drop_offs):.3f}")
    print(f"  Flat zones            — {flat_zones} ({100*flat_zones/n:.1f}%)")
    print(f"  Strong cliffhangers   — {high_cliffs} ({100*high_cliffs/n:.1f}%)")

    # Label distribution (for classification framing if needed)
    low   = sum(1 for d in drop_offs if d < 0.30)
    mid   = sum(1 for d in drop_offs if 0.30 <= d < 0.55)
    high  = sum(1 for d in drop_offs if d >= 0.55)
    print(f"  Drop-off buckets      — low (<0.30): {low}  "
          f"medium (0.30–0.55): {mid}  high (>=0.55): {high}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NarrativeIQ — Module 11: Synthetic Training Data Generator")
    parser.add_argument("--samples", type=int, default=1000, help="Number of episode records to generate (default: 1000)")
    parser.add_argument("--output",  type=str, default="synthetic_training_data.csv", help="Output CSV path")
    parser.add_argument("--seed",    type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--min-eps", type=int, default=3,  help="Minimum episodes per synthetic series")
    parser.add_argument("--max-eps", type=int, default=12, help="Maximum episodes per synthetic series")
    args = parser.parse_args()

    print(f"[Module 11] Generating {args.samples} synthetic episode records (seed={args.seed}) …")

    records = generate_dataset(
        n_samples=args.samples,
        seed=args.seed,
        series_length_range=(args.min_eps, args.max_eps),
    )

    print_stats(records)
    save_to_csv(records, args.output)
    print(f"[Module 11] Done. Feed {args.output} into Module 12 to train the drop-off predictor.")


if __name__ == "__main__":
    main()
