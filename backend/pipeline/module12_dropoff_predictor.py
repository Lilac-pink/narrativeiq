from typing import Optional
"""
Module 12 — Drop-off Probability Predictor
NarrativeIQ Pipeline

Trains a GradientBoostingRegressor on synthetic data from Module 11.
At runtime, accepts an episode feature vector and returns a drop-off
probability between 0.0 and 1.0.

Usage:
    # Train and save model
    python module_12_dropoff_predictor.py --train --data synthetic_training_data.csv

    # Predict on a single episode (JSON feature vector)
    python module_12_dropoff_predictor.py --predict --features '{"emotion_score":0.58,...}'

    # Evaluate model on held-out test split
    python module_12_dropoff_predictor.py --evaluate --data synthetic_training_data.csv
"""

import argparse
import json
import os
import warnings
warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_PATH = "dropoff_model.joblib"

# Feature columns — must match Module 11's EpisodeFeatureVector exactly
FEATURE_COLS = [
    "emotion_score",
    "emotion_delta",
    "is_flat_zone",
    "arc_deviation",
    "cliffhanger_score",
    "cliffhanger_pass_count",
    "continuity_score",
    "continuity_severity",
    "character_outlier_count",
    "episode_position",
    "is_series_opener",
    "is_series_finale",
    "heatmap_high_risk_blocks",
    "heatmap_medium_risk_blocks",
]

TARGET_COL = "drop_off_probability"

# GradientBoosting hyperparameters
GB_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 4,
    "min_samples_split": 10,
    "min_samples_leaf": 5,
    "subsample": 0.85,
    "max_features": "sqrt",
    "random_state": 42,
}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(data_path: str, model_path: str = MODEL_PATH) -> None:
    """Load CSV from Module 11, train model, save to disk."""

    print(f"[Module 12] Loading training data from {data_path} …")
    df = pd.read_csv(data_path)

    missing = [c for c in FEATURE_COLS + [TARGET_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in training data: {missing}")

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    print(f"[Module 12] Dataset: {len(df)} samples, {len(FEATURE_COLS)} features")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Pipeline: scaler + GBR
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("gbr", GradientBoostingRegressor(**GB_PARAMS)),
    ])

    print("[Module 12] Training GradientBoostingRegressor …")
    model.fit(X_train, y_train)

    # Evaluate on held-out test set
    y_pred = model.predict(X_test)
    y_pred = np.clip(y_pred, 0.0, 1.0)

    mae  = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    r2   = r2_score(y_test, y_pred)

    print(f"[Module 12] Test set results:")
    print(f"  MAE  : {mae:.4f}")
    print(f"  RMSE : {rmse:.4f}")
    print(f"  R²   : {r2:.4f}")

    # Cross-validation MAE
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="neg_mean_absolute_error")
    print(f"  5-Fold CV MAE: {-cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Feature importance
    gbr = model.named_steps["gbr"]
    importances = gbr.feature_importances_
    ranked = sorted(zip(FEATURE_COLS, importances), key=lambda x: x[1], reverse=True)
    print("\n[Module 12] Feature importances:")
    for name, score in ranked:
        bar = "█" * int(score * 40)
        print(f"  {name:<32} {score:.4f}  {bar}")

    # Save
    joblib.dump(model, model_path)
    print(f"\n[Module 12] Model saved → {model_path}")


# ---------------------------------------------------------------------------
# Prediction — called at runtime by Module 16 orchestrator
# ---------------------------------------------------------------------------

def load_model(model_path: str = MODEL_PATH) -> Pipeline:
    """Load trained model from disk."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model not found at '{model_path}'. "
            f"Run with --train first."
        )
    return joblib.load(model_path)


def predict_episode(features: dict, model: Optional[Pipeline] = None, model_path: str = MODEL_PATH) -> float:
    """
    Predict drop-off probability for a single episode.

    Args:
        features:   dict with keys matching FEATURE_COLS
        model:      pre-loaded Pipeline (pass to avoid re-loading in a loop)
        model_path: path to joblib file if model is None

    Returns:
        float between 0.0 and 1.0
    """
    if model is None:
        model = load_model(model_path)

    # Build feature vector in correct column order
    row = []
    for col in FEATURE_COLS:
        if col not in features:
            raise KeyError(f"Missing feature '{col}' in input dict.")
        row.append(float(features[col]))

    X = np.array([row])
    prob = float(np.clip(model.predict(X)[0], 0.0, 1.0))
    return round(prob, 4)


def predict_series(episodes: list[dict], model_path: str = MODEL_PATH) -> list[dict]:
    """
    Predict drop-off probability for every episode in a series.

    Args:
        episodes: list of feature dicts (one per episode)

    Returns:
        list of dicts: [{"episode_number": int, "drop_off_probability": float}, ...]
    """
    model = load_model(model_path)
    results = []

    for ep in episodes:
        prob = predict_episode(ep, model=model, model_path=model_path)
        results.append({
            "episode_number": ep.get("episode_number", None),
            "drop_off_probability": prob,
        })

    return results


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def evaluate(data_path: str, model_path: str = MODEL_PATH) -> None:
    """Run full evaluation on a CSV and print a distribution report."""
    print(f"[Module 12] Evaluating model against {data_path} …")
    model = load_model(model_path)
    df = pd.read_csv(data_path)

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    y_pred = np.clip(model.predict(X), 0.0, 1.0)
    mae  = mean_absolute_error(y, y_pred)
    rmse = mean_squared_error(y, y_pred) ** 0.5
    r2   = r2_score(y, y_pred)

    print(f"  Samples : {len(df)}")
    print(f"  MAE     : {mae:.4f}")
    print(f"  RMSE    : {rmse:.4f}")
    print(f"  R²      : {r2:.4f}")

    # Bucket accuracy
    def bucket(v): return "low" if v < 0.30 else ("high" if v >= 0.55 else "medium")
    actual_b  = [bucket(v) for v in y]
    pred_b    = [bucket(v) for v in y_pred]
    correct   = sum(a == p for a, p in zip(actual_b, pred_b))
    print(f"  Bucket accuracy (low/medium/high): {correct/len(df)*100:.1f}%")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NarrativeIQ — Module 12: Drop-off Probability Predictor")
    parser.add_argument("--train",    action="store_true", help="Train and save model")
    parser.add_argument("--predict",  action="store_true", help="Predict for a single episode")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate model on full dataset")
    parser.add_argument("--data",     type=str, default="synthetic_training_data.csv")
    parser.add_argument("--model",    type=str, default=MODEL_PATH)
    parser.add_argument("--features", type=str, help="JSON string of episode features for --predict")
    args = parser.parse_args()

    if args.train:
        train(args.data, args.model)

    elif args.predict:
        if not args.features:
            # Demo with a hardcoded flat-zone episode
            demo = {
                "emotion_score": 0.58, "emotion_delta": -0.03, "is_flat_zone": 1,
                "arc_deviation": 0.18, "cliffhanger_score": 5.4, "cliffhanger_pass_count": 3,
                "continuity_score": 0.72, "continuity_severity": 1, "character_outlier_count": 1,
                "episode_position": 0.5, "is_series_opener": 0, "is_series_finale": 0,
                "heatmap_high_risk_blocks": 2, "heatmap_medium_risk_blocks": 2,
            }
            print("[Module 12] No --features provided. Using demo episode (Episode 3 — Static).")
            features = demo
        else:
            features = json.loads(args.features)

        prob = predict_episode(features, model_path=args.model)
        print(f"[Module 12] Drop-off probability: {prob:.4f}  ({prob*100:.1f}%)")

    elif args.evaluate:
        evaluate(args.data, args.model)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

def _formula_dropoff(ep: dict, total_episodes: int) -> float:
    """
    Formula-based drop-off predictor used when no trained model is available.
    Combines cliffhanger, emotion, continuity and position into a probability.
    """
    ep_num   = ep.get("episode_number", 1)
    cs       = min(ep.get("cliffhanger_score", 5.0), 10.0) / 10.0   # 0-1
    em       = min(max(ep.get("emotion_score", 0.4), 0.0), 1.0)
    co       = min(max(ep.get("continuity_score", 0.8), 0.0), 1.0)
    is_flat  = 1.0 if ep.get("is_flat_zone", False) else 0.0

    # Position factor: middle episodes have slightly higher drop-off risk
    pos = ep_num / max(total_episodes, 1)
    position_risk = 0.1 if (0.3 < pos < 0.8) else 0.0

    # Weighted formula
    retention = (cs * 0.40) + (em * 0.30) + (co * 0.20)
    raw_prob = 1.0 - retention + (is_flat * 0.10) + position_risk

    # Normalise to 0.05 - 0.90
    return round(min(0.90, max(0.05, raw_prob)), 3)


async def run_dropoff_predictor(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    episodes = pipeline.get("episodes", [])
    total    = len(episodes)

    try:
        model = load_model()
        print("[Module 12] Trained model loaded — using ML predictor")
        use_ml = True
    except FileNotFoundError:
        print("[Module 12] No trained model — using formula-based drop-off predictor")
        use_ml = False

    for ep in episodes:
        try:
            if use_ml:
                features = {col: float(ep.get(col, 0)) for col in FEATURE_COLS}
                prob = predict_episode(features, model=model)
            else:
                prob = _formula_dropoff(ep, total)

            ep["drop_off_probability"] = prob
            ep["drop_off_risk_level"] = (
                "low" if prob < 0.30 else "high" if prob >= 0.55 else "medium"
            )
            print(f"  Episode {ep.get('episode_number')}: drop-off = {prob} ({ep['drop_off_risk_level']})")
        except Exception as e:
            print(f"  Episode {ep.get('episode_number')}: drop-off prediction failed — {e}")
            ep.setdefault("drop_off_probability", 0.35)
            ep.setdefault("drop_off_risk_level", "medium")

    return pipeline
