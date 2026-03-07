"""
MODULE 5 — NLP Extractor
NarrativeIQ Episodic Intelligence Engine

Runs spaCy on each episode's plot beat text.
Extracts: named characters, locations, time references,
action verbs, and conflict keywords.
Attaches results to each Episode object.
"""

import spacy
from typing import List
from models.module1_models import Episode, NLPFeatures


# ─────────────────────────────────────────
# SETUP
# Run once before using:
#   python -m spacy download en_core_web_sm
# ─────────────────────────────────────────

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise OSError(
        "spaCy model not found. Run: python -m spacy download en_core_web_sm"
    )


# ─────────────────────────────────────────
# CONFLICT KEYWORD BANK
# Extend this list freely
# ─────────────────────────────────────────

CONFLICT_KEYWORDS = {
    # Threat / violence
    "attack", "threat", "fight", "kill", "murder", "stab", "shoot", "destroy",
    "ambush", "trap", "chase", "escape", "capture", "kidnap", "betray", "betray",
    # Tension / deception
    "lie", "secret", "hide", "deceive", "manipulate", "conspire", "expose",
    "blackmail", "confront", "accuse", "deny", "frame", "suspect",
    # Loss / failure
    "fail", "lose", "break", "crash", "collapse", "surrender", "abandon",
    "disappear", "vanish", "die", "dead", "death", "loss",
    # Power / control
    "control", "power", "force", "demand", "command", "override", "seize",
    "overthrow", "resist", "revolt", "rebel",
}

# ─────────────────────────────────────────
# ACTION VERB FILTER
# We want plot-relevant action verbs, not auxiliary/linking verbs
# ─────────────────────────────────────────

SKIP_VERBS = {
    "be", "is", "are", "was", "were", "am",
    "have", "has", "had",
    "do", "does", "did",
    "will", "would", "could", "should", "might", "may", "must", "shall",
    "seem", "appear", "become", "remain", "stay",
    "say", "tell", "ask", "know", "think", "feel", "want", "need",
    "get", "make", "take", "give", "go", "come", "use", "let",
}


# ─────────────────────────────────────────
# CORE EXTRACTION
# ─────────────────────────────────────────

def extract_from_text(text: str) -> NLPFeatures:
    """
    Run spaCy on a single episode's plot beat text.
    Returns a populated NLPFeatures object.
    """
    doc = nlp(text)

    characters: List[str] = []
    locations: List[str] = []
    time_references: List[str] = []

    # ── Named Entity Recognition ──
    for ent in doc.ents:
        label = ent.label_
        value = ent.text.strip()

        if label == "PERSON" and value not in characters:
            characters.append(value)

        elif label in ("GPE", "LOC", "FAC", "ORG") and value not in locations:
            # GPE = geopolitical (cities, countries)
            # LOC = natural locations
            # FAC = buildings, facilities
            # ORG = organisations can serve as locations in narrative context
            locations.append(value)

        elif label in ("DATE", "TIME", "EVENT") and value not in time_references:
            time_references.append(value)

    # ── Action Verbs ──
    action_verbs: List[str] = []
    for token in doc:
        if (
            token.pos_ == "VERB"
            and token.lemma_.lower() not in SKIP_VERBS
            and not token.is_stop
            and token.lemma_.lower() not in action_verbs
            and len(token.lemma_) > 2
        ):
            action_verbs.append(token.lemma_.lower())

    # ── Conflict Keywords ──
    tokens_lower = {token.lemma_.lower() for token in doc}
    conflict_keywords = sorted(list(tokens_lower & CONFLICT_KEYWORDS))

    return NLPFeatures(
        characters=characters,
        locations=locations,
        time_references=time_references,
        action_verbs=action_verbs,
        conflict_keywords=conflict_keywords,
    )


# ─────────────────────────────────────────
# EPISODE-LEVEL PROCESSOR
# ─────────────────────────────────────────

def process_episode(episode: Episode) -> Episode:
    """
    Run NLP extraction on a single episode.
    Attaches NLPFeatures and populates top-level
    characters and locations fields for frontend compatibility.
    Returns the updated episode.
    """
    features = extract_from_text(episode.plot_beat)
    episode.nlp_features = features

    # Merge with any characters/locations already set
    # (e.g. from Module 3 story decomposer)
    existing_chars = set(episode.characters)
    existing_locs = set(episode.locations)

    for char in features.characters:
        if char not in existing_chars:
            episode.characters.append(char)

    for loc in features.locations:
        if loc not in existing_locs:
            episode.locations.append(loc)

    return episode


# ─────────────────────────────────────────
# SERIES-LEVEL PROCESSOR
# Called by Module 16 Orchestrator
# ─────────────────────────────────────────

def extract_nlp_features(episodes: List[Episode]) -> List[Episode]:
    """
    Run NLP extraction across all episodes in the series.
    Returns the full list of episodes with NLPFeatures attached.

    Usage (Module 16):
        episodes = extract_nlp_features(episodes)
    """
    print(f"[Module 5] Running NLP extraction on {len(episodes)} episodes...")

    processed = []
    for episode in episodes:
        try:
            updated = process_episode(episode)
            processed.append(updated)
            print(
                f"  Episode {episode.episode_number}: "
                f"{len(updated.characters)} chars, "
                f"{len(updated.locations)} locs, "
                f"{len(updated.nlp_features.action_verbs)} verbs, "
                f"{len(updated.nlp_features.conflict_keywords)} conflict keywords"
            )
        except Exception as e:
            print(f"  Episode {episode.episode_number} NLP failed: {e}")
            processed.append(episode)  # pass through unchanged

    print(f"[Module 5] NLP extraction complete.")
    return processed


# ─────────────────────────────────────────
# STANDALONE TEST
# Run: python module5_nlp_extractor.py
# ─────────────────────────────────────────

if __name__ == "__main__":
    from models.module1_models import Episode

    test_episodes = [
        Episode(
            episode_number=1,
            title="Dead Air",
            plot_beat=(
                "Maya Chen, a late-night radio operator, picks up a mysterious signal "
                "from Station 7, a government facility that was sealed in 1991. "
                "Director Osei orders her to destroy the recording, but Maya secretly "
                "makes a copy before the signal vanishes at midnight."
            )
        ),
        Episode(
            episode_number=2,
            title="Interference",
            plot_beat=(
                "Maya traces the signal coordinates to an abandoned bunker outside the city. "
                "Dr. Reeves warns her that three investigators who found this location last year "
                "disappeared without a trace. Maya ignores the warning and drives to the bunker entrance at dawn."
            )
        ),
        Episode(
            episode_number=3,
            title="Static",
            plot_beat=(
                "Inside the bunker, Maya discovers encrypted files linking Director Osei "
                "to the original station shutdown. A hidden door reveals a deeper chamber. "
                "Someone has been here recently — the dust is disturbed and a coffee cup is still warm."
            )
        ),
    ]

    results = extract_nlp_features(test_episodes)

    print("\n─── RESULTS ───")
    for ep in results:
        print(f"\nEpisode {ep.episode_number}: {ep.title}")
        print(f"  Characters     : {ep.characters}")
        print(f"  Locations      : {ep.locations}")
        print(f"  Time refs      : {ep.nlp_features.time_references}")
        print(f"  Action verbs   : {ep.nlp_features.action_verbs}")
        print(f"  Conflict words : {ep.nlp_features.conflict_keywords}")


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_nlp_extractor(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    from models.module1_models import Episode
    episodes = [Episode(**ep) if isinstance(ep, dict) else ep
                for ep in pipeline.get("episodes", [])]
    updated = extract_nlp_features(episodes)
    pipeline["episodes"] = [ep.dict() for ep in updated]
    return pipeline
