"""
MODULE 10 — Character Consistency Checker
NarrativeIQ Episodic Intelligence Engine

Embeds all character description mentions across episodes using MiniLM.
For each character, clusters their description embeddings and flags
any that sit as outliers using z-score or isolation forest.
Outputs contradictory trait pairs per character per episode.
"""

import re
import numpy as np
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import IsolationForest
from sklearn.metrics.pairwise import cosine_similarity
from scipy.stats import zscore

from models.module1_models import Episode, CharacterInconsistency


# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

MINIML_MODEL         = "sentence-transformers/all-MiniLM-L6-v2"
ZSCORE_THRESHOLD     = 1.8    # z-score above this = outlier trait
ISOLATION_CONTAMINATION = 0.2  # expected proportion of outliers
MIN_MENTIONS_FOR_ISO = 4      # use IsolationForest only if ≥ this many mentions
MIN_MENTIONS_FOR_Z   = 2      # use z-score if ≥ this many mentions
SIMILARITY_FLOOR     = 0.55   # pairs below this cosine similarity = contradictory


# ─────────────────────────────────────────
# MODEL LOADER
# ─────────────────────────────────────────

_model: Optional[SentenceTransformer] = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("[Module 10] Loading MiniLM model...")
        _model = SentenceTransformer(MINIML_MODEL)
        print("[Module 10] Model loaded.")
    return _model


# ─────────────────────────────────────────
# CHARACTER MENTION EXTRACTOR
# Pulls sentences that reference a character by name
# ─────────────────────────────────────────

def extract_character_mentions(
    character_name: str,
    episodes: List[Episode]
) -> List[Dict]:
    """
    Find all sentences across all episodes that mention a character.

    Returns list of dicts:
    {
        "episode_number": int,
        "sentence": str,
        "character": str
    }
    """
    mentions = []
    # Match any part of the name (first name, last name, or full)
    name_parts = character_name.strip().split()
    pattern = re.compile(
        r'(?i)\b(' + '|'.join(re.escape(p) for p in name_parts) + r')\b'
    )

    for episode in episodes:
        sentences = re.split(r'(?<=[.!?])\s+', episode.plot_beat.strip())
        for sentence in sentences:
            if pattern.search(sentence):
                mentions.append({
                    "episode_number": episode.episode_number,
                    "sentence": sentence.strip(),
                    "character": character_name
                })

    return mentions


# ─────────────────────────────────────────
# OUTLIER DETECTOR
# ─────────────────────────────────────────

def detect_outlier_mentions(
    embeddings: np.ndarray,
    n_mentions: int
) -> np.ndarray:
    """
    Given an array of sentence embeddings for a character,
    return a boolean mask where True = outlier.

    Uses IsolationForest for ≥ MIN_MENTIONS_FOR_ISO mentions,
    z-score on mean similarity otherwise.
    """
    if n_mentions < MIN_MENTIONS_FOR_Z:
        # Not enough data — nothing to flag
        return np.zeros(n_mentions, dtype=bool)

    # Compute mean cosine similarity of each mention to all others
    sim_matrix = cosine_similarity(embeddings)
    mean_sims = (sim_matrix.sum(axis=1) - 1.0) / max(n_mentions - 1, 1)
    # (subtract self-similarity of 1.0, divide by remaining)

    if n_mentions >= MIN_MENTIONS_FOR_ISO:
        # IsolationForest on the embeddings directly
        iso = IsolationForest(
            contamination=ISOLATION_CONTAMINATION,
            random_state=42
        )
        preds = iso.fit_predict(embeddings)
        iso_outliers = preds == -1

        # Z-score on mean similarities as secondary signal
        z_scores = np.abs(zscore(mean_sims)) if n_mentions > 2 else np.zeros(n_mentions)
        z_outliers = z_scores > ZSCORE_THRESHOLD

        # Union: flag if EITHER method flags it
        return iso_outliers | z_outliers

    else:
        # Z-score only
        if n_mentions > 2:
            z_scores = np.abs(zscore(mean_sims))
            return z_scores > ZSCORE_THRESHOLD
        else:
            # Only 2 mentions — flag if similarity is very low
            sim = sim_matrix[0, 1]
            outlier_mask = np.zeros(2, dtype=bool)
            if sim < SIMILARITY_FLOOR:
                outlier_mask[1] = True  # flag the second as the outlier
            return outlier_mask


# ─────────────────────────────────────────
# CONTRADICTION PAIR BUILDER
# ─────────────────────────────────────────

def find_contradictory_pairs(
    mentions: List[Dict],
    outlier_mask: np.ndarray,
    embeddings: np.ndarray
) -> List[Tuple[Dict, Dict, float]]:
    """
    For each outlier mention, find the most contradictory
    non-outlier mention (lowest cosine similarity).

    Returns list of (mention_a, mention_b, similarity_score) tuples.
    """
    pairs = []
    outlier_indices = np.where(outlier_mask)[0]
    normal_indices  = np.where(~outlier_mask)[0]

    if len(normal_indices) == 0:
        # All are outliers — compare all pairs
        normal_indices = np.arange(len(mentions))

    for oi in outlier_indices:
        sims = cosine_similarity([embeddings[oi]], embeddings[normal_indices])[0]
        most_different_idx = normal_indices[np.argmin(sims)]
        min_sim = float(sims[np.argmin(sims)])

        if min_sim < SIMILARITY_FLOOR:
            pairs.append((
                mentions[most_different_idx],
                mentions[oi],
                round(min_sim, 4)
            ))

    return pairs


# ─────────────────────────────────────────
# CHARACTER CHECKER
# ─────────────────────────────────────────

def check_character(
    character_name: str,
    episodes: List[Episode]
) -> List[CharacterInconsistency]:
    """
    Check a single character for trait inconsistencies across episodes.
    Returns a list of CharacterInconsistency objects.
    """
    mentions = extract_character_mentions(character_name, episodes)

    if len(mentions) < MIN_MENTIONS_FOR_Z:
        print(f"    {character_name}: only {len(mentions)} mention(s) — skipping.")
        return []

    # Embed all mention sentences
    model = get_model()
    sentences = [m["sentence"] for m in mentions]
    embeddings = model.encode(sentences)

    # Detect outliers
    outlier_mask = detect_outlier_mentions(embeddings, len(mentions))
    n_outliers = outlier_mask.sum()

    if n_outliers == 0:
        print(f"    {character_name}: {len(mentions)} mentions, no inconsistencies.")
        return []

    print(f"    {character_name}: {len(mentions)} mentions, {n_outliers} outlier(s) flagged.")

    # Find contradictory pairs
    contradiction_pairs = find_contradictory_pairs(mentions, outlier_mask, embeddings)

    inconsistencies = []
    for mention_a, mention_b, sim in contradiction_pairs:
        inconsistency = CharacterInconsistency(
            character_name=character_name,
            episode_a=mention_a["episode_number"],
            episode_b=mention_b["episode_number"],
            trait_a=mention_a["sentence"],
            trait_b=mention_b["sentence"],
            outlier_score=round(1.0 - sim, 4)   # invert similarity → contradiction score
        )
        inconsistencies.append(inconsistency)
        print(
            f"      ↳ Ep{mention_a['episode_number']} vs Ep{mention_b['episode_number']}: "
            f"similarity={sim} | contradiction={inconsistency.outlier_score}"
        )

    return inconsistencies


# ─────────────────────────────────────────
# SERIES-LEVEL CHECKER
# Called by Module 16 Orchestrator
# ─────────────────────────────────────────

def check_character_consistency(
    episodes: List[Episode]
) -> Tuple[List[Episode], List[CharacterInconsistency]]:
    """
    Run character consistency check across all episodes.

    Collects all unique character names from episode.characters fields,
    checks each for trait inconsistencies, attaches findings to episodes,
    and returns a flat list of all CharacterInconsistency objects.

    Usage (Module 16):
        episodes, char_issues = check_character_consistency(episodes)
    """
    print(f"[Module 10] Checking character consistency across {len(episodes)} episodes...")

    # Collect all unique characters across the series
    all_characters: Dict[str, int] = defaultdict(int)
    for episode in episodes:
        for char in episode.characters:
            if char.strip():
                all_characters[char.strip()] += 1

    # Only check characters that appear in more than one episode
    recurring = {
        name: count
        for name, count in all_characters.items()
        if count >= MIN_MENTIONS_FOR_Z
    }

    print(f"  {len(all_characters)} unique characters found. "
          f"{len(recurring)} recurring (appear ≥{MIN_MENTIONS_FOR_Z}x).")

    all_inconsistencies: List[CharacterInconsistency] = []

    for character_name in recurring:
        try:
            issues = check_character(character_name, episodes)
            all_inconsistencies.extend(issues)
        except Exception as e:
            print(f"    {character_name}: check failed — {e}")

    # Attach inconsistencies to relevant episodes
    for episode in episodes:
        episode_issues = [
            issue for issue in all_inconsistencies
            if issue.episode_a == episode.episode_number
            or issue.episode_b == episode.episode_number
        ]
        episode.character_inconsistencies = episode_issues

    print(
        f"[Module 10] Character consistency check complete. "
        f"{len(all_inconsistencies)} inconsistency/ies found."
    )
    return episodes, all_inconsistencies


# ─────────────────────────────────────────
# STANDALONE TEST
# Run: python module10_character_consistency.py
# ─────────────────────────────────────────

if __name__ == "__main__":
    from models.module1_models import Episode

    test_episodes = [
        Episode(
            episode_number=1,
            title="Dead Air",
            plot_beat=(
                "Maya Chen is a cautious, methodical radio operator who follows every protocol. "
                "Director Osei is a calm and authoritative figure who speaks in measured tones. "
                "Maya carefully logs the mysterious signal before doing anything else."
            ),
            characters=["Maya Chen", "Director Osei"]
        ),
        Episode(
            episode_number=2,
            title="Interference",
            plot_beat=(
                "Maya recklessly drives to the bunker alone at night, ignoring all safety warnings. "
                "Director Osei screams orders over the phone in a panic, completely out of control. "
                "Dr. Reeves is introduced as a quiet academic who avoids confrontation."
            ),
            characters=["Maya Chen", "Director Osei", "Dr. Reeves"]
        ),
        Episode(
            episode_number=3,
            title="Static",
            plot_beat=(
                "Maya moves carefully through the bunker, documenting everything methodically. "
                "Dr. Reeves suddenly becomes aggressive and threatens Maya to stop investigating. "
                "Director Osei sends a calm and professional written memo to the department."
            ),
            characters=["Maya Chen", "Director Osei", "Dr. Reeves"]
        ),
        Episode(
            episode_number=4,
            title="Frequency",
            plot_beat=(
                "Maya is bold and fearless as she confronts Director Osei directly. "
                "Director Osei pulls a gun — cold, calculated, completely in control. "
                "Dr. Reeves arrives as a mediator, gentle and non-threatening as always."
            ),
            characters=["Maya Chen", "Director Osei", "Dr. Reeves"]
        ),
        Episode(
            episode_number=5,
            title="Broadcast",
            plot_beat=(
                "Maya hesitates at the console — her careful nature making her second-guess. "
                "Director Osei stands silently, resigned and composed. "
                "Dr. Reeves sacrifices himself to buy Maya time, showing unexpected bravery."
            ),
            characters=["Maya Chen", "Director Osei", "Dr. Reeves"]
        ),
    ]

    updated_episodes, inconsistencies = check_character_consistency(test_episodes)

    print("\n─── RESULTS ───")
    print(f"\nTotal inconsistencies found: {len(inconsistencies)}")
    for issue in inconsistencies:
        print(f"\n  Character      : {issue.character_name}")
        print(f"  Episodes       : {issue.episode_a} vs {issue.episode_b}")
        print(f"  Trait A (Ep{issue.episode_a}) : {issue.trait_a[:80]}...")
        print(f"  Trait B (Ep{issue.episode_b}) : {issue.trait_b[:80]}...")
        print(f"  Contradiction  : {issue.outlier_score:.4f} (higher = more contradictory)")

    print(f"\nPer-episode breakdown:")
    for ep in updated_episodes:
        count = len(ep.character_inconsistencies)
        tag = f" — {count} issue(s)" if count else " — clean"
        print(f"  Episode {ep.episode_number}: {ep.title}{tag}")


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_character_consistency(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    from models.module1_models import Episode
    episodes = [Episode(**ep) if isinstance(ep, dict) else ep
                for ep in pipeline.get("episodes", [])]
    updated_episodes, issues = check_character_consistency(episodes)
    pipeline["episodes"] = [ep.dict() for ep in updated_episodes]
    pipeline["character_issues"] = [i.dict() for i in issues]
    return pipeline
