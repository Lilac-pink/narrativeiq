"""
MODULE 9 — Continuity Auditor
NarrativeIQ Episodic Intelligence Engine

Uses MiniLM sentence embeddings and cosine similarity to check
whether each episode's cliffhanger/closing beat connects
narratively to the next episode's opening beat.

Flags transitions below 0.75 similarity as continuity issues
with severity levels: low / medium / high.
"""

import re
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from models.module1_models import Episode, ContinuityIssue, Severity


# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

MINIML_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Similarity thresholds
THRESHOLD_HIGH    = 0.60   # below this → HIGH severity
THRESHOLD_MEDIUM  = 0.75   # below this → MEDIUM severity
# at or above THRESHOLD_MEDIUM → no issue flagged

# How many sentences to extract for closing / opening beats
CLOSING_SENTENCE_COUNT = 2   # last N sentences of episode
OPENING_SENTENCE_COUNT = 2   # first N sentences of next episode


# ─────────────────────────────────────────
# MODEL LOADER
# Lazy-loaded once on first call
# ─────────────────────────────────────────

_model: Optional[SentenceTransformer] = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("[Module 9] Loading MiniLM model...")
        _model = SentenceTransformer(MINIML_MODEL)
        print("[Module 9] Model loaded.")
    return _model


# ─────────────────────────────────────────
# TEXT HELPERS
# ─────────────────────────────────────────

def split_sentences(text: str) -> List[str]:
    """
    Simple sentence splitter using punctuation.
    Falls back to whole text if no sentence boundaries found.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences if sentences else [text.strip()]


def extract_closing_beat(plot_beat: str, n: int = CLOSING_SENTENCE_COUNT) -> str:
    """Extract the last N sentences — the cliffhanger / closing beat."""
    sentences = split_sentences(plot_beat)
    closing = sentences[-n:] if len(sentences) >= n else sentences
    return " ".join(closing)


def extract_opening_beat(plot_beat: str, n: int = OPENING_SENTENCE_COUNT) -> str:
    """Extract the first N sentences — the episode opening beat."""
    sentences = split_sentences(plot_beat)
    opening = sentences[:n] if len(sentences) >= n else sentences
    return " ".join(opening)


# ─────────────────────────────────────────
# SIMILARITY SCORER
# ─────────────────────────────────────────

def compute_similarity(text_a: str, text_b: str) -> float:
    """
    Embed two text strings with MiniLM and compute cosine similarity.
    Returns a float between 0.0 and 1.0.
    """
    model = get_model()
    embeddings = model.encode([text_a, text_b])
    sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    return round(float(sim), 4)


# ─────────────────────────────────────────
# SEVERITY CLASSIFIER
# ─────────────────────────────────────────

def classify_severity(similarity_score: float) -> Optional[Severity]:
    """
    Returns severity level based on similarity score.
    Returns None if no issue (score is acceptable).
    """
    if similarity_score < THRESHOLD_HIGH:
        return Severity.HIGH
    elif similarity_score < THRESHOLD_MEDIUM:
        return Severity.MEDIUM
    else:
        return None  # No issue


def build_issue_description(
    ep_a: Episode,
    ep_b: Episode,
    closing_beat: str,
    opening_beat: str,
    severity: Severity
) -> str:
    """
    Build a plain-language description of the continuity gap.
    """
    if severity == Severity.HIGH:
        prefix = "Significant continuity break"
    else:
        prefix = "Potential continuity gap"

    return (
        f"{prefix} between Episode {ep_a.episode_number} and Episode {ep_b.episode_number}. "
        f"Episode {ep_a.episode_number} closes with: \"{closing_beat.strip()}\" — "
        f"but Episode {ep_b.episode_number} opens with: \"{opening_beat.strip()}\". "
        f"These beats have low narrative overlap (similarity: {ep_a.episode_number})."
    )


# ─────────────────────────────────────────
# PAIR AUDITOR
# ─────────────────────────────────────────

def audit_pair(
    ep_a: Episode,
    ep_b: Episode
) -> Tuple[float, Optional[ContinuityIssue]]:
    """
    Audit the transition between two consecutive episodes.

    Returns:
        similarity_score (float): cosine similarity between closing/opening beats
        issue (ContinuityIssue | None): populated if severity is medium or high
    """
    closing_beat = extract_closing_beat(ep_a.plot_beat)
    opening_beat = extract_opening_beat(ep_b.plot_beat)

    similarity = compute_similarity(closing_beat, opening_beat)
    severity = classify_severity(similarity)

    transition_label = f"Episode {ep_a.episode_number} → Episode {ep_b.episode_number}"

    if severity is None:
        print(f"  {transition_label}: ✅ OK (similarity = {similarity})")
        return similarity, None

    issue_text = (
        f"Episode {ep_a.episode_number} closes: \"{closing_beat}\" — "
        f"Episode {ep_b.episode_number} opens: \"{opening_beat}\". "
        f"Low narrative connection detected."
    )

    issue = ContinuityIssue(
        transition=transition_label,
        similarity_score=similarity,
        severity=severity,
        issue=issue_text
    )

    severity_tag = "⚠ MEDIUM" if severity == Severity.MEDIUM else "🔴 HIGH"
    print(f"  {transition_label}: {severity_tag} (similarity = {similarity})")

    return similarity, issue


# ─────────────────────────────────────────
# SERIES-LEVEL AUDITOR
# Called by Module 16 Orchestrator
# ─────────────────────────────────────────

def audit_continuity(episodes: List[Episode]) -> Tuple[List[Episode], List[ContinuityIssue]]:
    """
    Run continuity audit across all consecutive episode pairs.

    Attaches continuity_score and continuity_to_next to each episode.
    Returns updated episodes and a flat list of all ContinuityIssues.

    Usage (Module 16):
        episodes, continuity_issues = audit_continuity(episodes)
    """
    print(f"[Module 9] Auditing continuity across {len(episodes)} episodes...")

    if len(episodes) < 2:
        print("[Module 9] Fewer than 2 episodes — nothing to audit.")
        return episodes, []

    # Sort episodes by episode number to be safe
    episodes = sorted(episodes, key=lambda e: e.episode_number)

    all_issues: List[ContinuityIssue] = []

    for i in range(len(episodes) - 1):
        ep_a = episodes[i]
        ep_b = episodes[i + 1]

        try:
            similarity, issue = audit_pair(ep_a, ep_b)

            # Attach outbound continuity score to ep_a
            episodes[i].continuity_score = similarity
            episodes[i].continuity_to_next = issue

            if issue:
                all_issues.append(issue)

        except Exception as e:
            print(f"  Pair {ep_a.episode_number}→{ep_b.episode_number} audit failed: {e}")
            episodes[i].continuity_score = None

    # Last episode has no outbound transition
    episodes[-1].continuity_score = None
    episodes[-1].continuity_to_next = None

    print(f"[Module 9] Continuity audit complete. {len(all_issues)} issue(s) found.")
    return episodes, all_issues


# ─────────────────────────────────────────
# STANDALONE TEST
# Run: python module9_continuity.py
# ─────────────────────────────────────────

if __name__ == "__main__":
    from models.module1_models import Episode

    test_episodes = [
        Episode(
            episode_number=1,
            title="Dead Air",
            plot_beat=(
                "Maya Chen picks up a mysterious radio signal from Station 7. "
                "Director Osei orders her to destroy the recording immediately. "
                "Maya secretly makes a copy before the signal vanishes at midnight."
            )
        ),
        Episode(
            episode_number=2,
            title="Interference",
            plot_beat=(
                "Maya decodes the coordinates from the signal and finds they point to an old bunker. "
                "Dr. Reeves warns her that investigators who went there before disappeared. "
                "Maya parks her car at the bunker entrance as the sun rises."
            )
        ),
        Episode(
            episode_number=3,
            title="Static",
            plot_beat=(
                "Three weeks later, Maya is back at her desk reviewing old case files. "
                "She suddenly remembers the bunker and decides to return. "
                "Inside, she discovers a room full of encrypted government documents."
            )
            # ↑ This should flag HIGH — time jump with no bridge to Ep 2's cliffhanger
        ),
        Episode(
            episode_number=4,
            title="Frequency",
            plot_beat=(
                "Maya confronts Director Osei with the documents she found in the bunker. "
                "He pulls a gun and orders her to hand them over. "
                "The Voice crackles through a nearby radio and announces it is an AI from 1991."
            )
        ),
        Episode(
            episode_number=5,
            title="Broadcast",
            plot_beat=(
                "With Osei's gun still pointed at her, Maya reaches for the broadcast console. "
                "She must choose: silence the AI or let it expose the government's secrets. "
                "Her finger hovers over the switch as sirens wail outside."
            )
        ),
    ]

    updated_episodes, issues = audit_continuity(test_episodes)

    print("\n─── RESULTS ───")
    print(f"\nContinuity Scores per Episode:")
    for ep in updated_episodes:
        score_str = f"{ep.continuity_score:.4f}" if ep.continuity_score is not None else "N/A (last)"
        issue_tag = " ← ISSUE FLAGGED" if ep.continuity_to_next else ""
        print(f"  Episode {ep.episode_number} ({ep.title}): {score_str}{issue_tag}")

    print(f"\nIssues Found ({len(issues)}):")
    for issue in issues:
        print(f"\n  Transition : {issue.transition}")
        print(f"  Severity   : {issue.severity}")
        print(f"  Similarity : {issue.similarity_score}")
        print(f"  Issue      : {issue.issue[:120]}...")


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_continuity_auditor(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    from models.module1_models import Episode
    episodes = [Episode(**ep) if isinstance(ep, dict) else ep
                for ep in pipeline.get("episodes", [])]
    updated_episodes, issues = audit_continuity(episodes)
    pipeline["episodes"] = [ep.dict() for ep in updated_episodes]
    pipeline["continuity_issues"] = [i.dict() for i in issues]
    return pipeline
