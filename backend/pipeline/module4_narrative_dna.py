"""
Module 4 — Narrative DNA Classifier
Phase 2: Story Ingestion

Reads the decomposed series from Module 3 and uses GPT-4o to:
  1. Identify the precise story type / narrative archetype
  2. Map it to a predefined ideal emotional arc template
  3. Return structured metadata the rest of the pipeline uses for scoring

Outputs feed into:
  - Module 7  (Arc Deviation Scorer)   — ideal_curve used as the benchmark
  - Module 8  (Cliffhanger Scorer)     — story_type informs weighting
  - Module 14 (Suggestion Engine)      — archetype context improves GPT prompts
"""

import os
import json
from typing import Optional
from groq import Groq
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Ideal arc templates — one per recognised narrative archetype
# Curves are normalised emotion intensity values per episode (0.0 – 1.0).
# All templates are defined for 5 episodes; the classifier stretches/compresses
# them to match the actual episode count at runtime.
# ---------------------------------------------------------------------------

ARC_TEMPLATES: dict[str, dict] = {
    "thriller": {
        "description": "Rising tension with a false plateau, then explosive climax.",
        "base_curve": [0.30, 0.50, 0.55, 0.80, 0.95],
        "cliffhanger_weight": 1.3,
        "pacing_note": "Each act must end on escalating threat. Mid-point dip is a trap, not a rest.",
    },
    "mystery": {
        "description": "Slow revelation build with a sharp revelation spike near the end.",
        "base_curve": [0.25, 0.40, 0.60, 0.75, 0.95],
        "cliffhanger_weight": 1.2,
        "pacing_note": "Clues must drip-feed. Emotional intensity tracks information density.",
    },
    "romance": {
        "description": "Hopeful rise, emotional collapse at midpoint, triumphant resolution.",
        "base_curve": [0.40, 0.65, 0.35, 0.70, 0.90],
        "cliffhanger_weight": 0.9,
        "pacing_note": "The midpoint low (separation/conflict) is the structural heart of the story.",
    },
    "tragedy": {
        "description": "High hope early, gradual decline, devastating final collapse.",
        "base_curve": [0.75, 0.65, 0.50, 0.35, 0.15],
        "cliffhanger_weight": 1.0,
        "pacing_note": "Audience must feel the fall. Do not artificially lift the final episode.",
    },
    "hero_journey": {
        "description": "Reluctant start, transformative ordeal, victorious return.",
        "base_curve": [0.25, 0.45, 0.70, 0.60, 0.95],
        "cliffhanger_weight": 1.1,
        "pacing_note": "The dip in episode 4 is the dark night of the soul — necessary before the final rise.",
    },
    "conspiracy": {
        "description": "Creeping dread with layered reveals accelerating toward a systemic expose.",
        "base_curve": [0.30, 0.45, 0.65, 0.80, 0.95],
        "cliffhanger_weight": 1.25,
        "pacing_note": "Each reveal must feel bigger than the last. Emotional stakes = scope of the conspiracy.",
    },
    "horror": {
        "description": "Normalcy → creeping dread → terror → brief false relief → final shock.",
        "base_curve": [0.20, 0.40, 0.70, 0.55, 0.95],
        "cliffhanger_weight": 1.4,
        "pacing_note": "The false relief before the finale is essential — it makes the final hit land harder.",
    },
    "coming_of_age": {
        "description": "Tentative start, identity crisis, breakthrough, earned maturity.",
        "base_curve": [0.30, 0.50, 0.40, 0.65, 0.85],
        "cliffhanger_weight": 0.85,
        "pacing_note": "Internal emotional arcs matter more than plot. Character change IS the cliffhanger.",
    },
    "sci_fi_discovery": {
        "description": "Wonder → complication → ethical crisis → resolution with transformed worldview.",
        "base_curve": [0.35, 0.55, 0.65, 0.75, 0.90],
        "cliffhanger_weight": 1.1,
        "pacing_note": "Escalating wonder must be matched by escalating consequence. Discovery without cost is boring.",
    },
    "political_drama": {
        "description": "Idealism → compromise → corruption → crisis → pyrrhic victory or collapse.",
        "base_curve": [0.40, 0.55, 0.65, 0.80, 0.85],
        "cliffhanger_weight": 1.0,
        "pacing_note": "Moral ambiguity should increase each episode. Audience trust in the protagonist should erode.",
    },
}

KNOWN_ARCHETYPES = list(ARC_TEMPLATES.keys())


# ---------------------------------------------------------------------------
# Pydantic output schema
# ---------------------------------------------------------------------------

class NarrativeDNA(BaseModel):
    story_type: str = Field(
        ...,
        description=f"One of: {', '.join(KNOWN_ARCHETYPES)}"
    )
    archetype_confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="GPT's confidence that this archetype is the best fit (0–1)"
    )
    secondary_archetype: Optional[str] = Field(
        None,
        description="A secondary archetype if the story blends two types"
    )
    archetype_reasoning: str = Field(
        ...,
        description="1–2 sentence explanation of why this archetype was chosen"
    )
    ideal_curve: list[float] = Field(
        ...,
        description="Normalised emotion intensity values per episode (0–1), scaled to actual episode count"
    )
    cliffhanger_weight: float = Field(
        ...,
        description="Multiplier applied to cliffhanger scores for this story type (from template)"
    )
    pacing_note: str = Field(
        ...,
        description="Structural pacing guidance for this archetype"
    )
    thematic_keywords: list[str] = Field(
        ...,
        description="5–10 keywords that define the thematic DNA of this specific story (not just the archetype)"
    )
    protagonist_arc: str = Field(
        ...,
        description="One sentence describing the protagonist's internal transformation across the series"
    )
    series_title: str = Field(..., description="Series title passed through from Module 3")
    total_episodes: int = Field(..., description="Total episode count passed through from Module 3")


# ---------------------------------------------------------------------------
# Arc curve scaling
# ---------------------------------------------------------------------------

def _scale_curve(base_curve: list[float], target_length: int) -> list[float]:
    """
    Linearly interpolates the 5-point base curve to match the actual episode count.
    Works for any target length from 1 to 20.
    """
    if target_length == len(base_curve):
        return base_curve

    if target_length == 1:
        return [base_curve[0]]

    scaled = []
    n = len(base_curve)
    for i in range(target_length):
        # Map index i in [0, target_length-1] to position in [0, n-1]
        pos = i * (n - 1) / (target_length - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        val = base_curve[lo] * (1 - frac) + base_curve[hi] * frac
        scaled.append(round(val, 3))

    return scaled


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a narrative structure expert and story analyst with deep knowledge of
screenwriting, genre theory, and audience engagement psychology.

You will receive a decomposed story series (title, logline, genre hint, and
episode summaries) and must classify it into one of the following narrative
archetypes:

{archetypes}

Your task:
1. Identify the PRIMARY archetype that best describes the story's structural DNA
2. Identify a SECONDARY archetype if the story meaningfully blends two types
3. State your confidence level (0–1) in the classification
4. Extract 5–10 thematic keywords specific to THIS story (not generic archetype words)
5. Describe the protagonist's internal transformation arc in one sentence
6. Provide a 1–2 sentence reasoning for your classification

Output ONLY valid JSON matching the schema. No preamble, no markdown.
""".strip()


# ---------------------------------------------------------------------------
# Core classifier function
# ---------------------------------------------------------------------------

def classify_narrative_dna(
    decomposed_series: dict,
    api_key: Optional[str] = None,
    model: str = "llama-3.1-8b-instant",
) -> NarrativeDNA:
    """
    Classifies the narrative archetype of a decomposed series and returns the
    ideal emotional arc template scaled to the actual episode count.

    Args:
        decomposed_series: Output dict from Module 3 (run() return value).
        api_key:           OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model:             Model to use. Default is gpt-4o.

    Returns:
        NarrativeDNA: Pydantic model with archetype, ideal curve, and metadata.

    Raises:
        ValueError: If archetype returned by GPT is not in the known list,
                    or if JSON parsing fails.
    """
    client = Groq(api_key=api_key or os.environ["GROQ_API_KEY"])

    total_episodes: int = decomposed_series.get("total_episodes", 5)
    series_title: str = decomposed_series.get("series_title", "Untitled")
    logline: str = decomposed_series.get("logline", "")
    genre_hint: str = decomposed_series.get("genre", "")

    # Build a compact episode summary for the prompt (avoid token bloat)
    episode_summaries = []
    for ep in decomposed_series.get("episodes", []):
        episode_summaries.append(
            f"Ep {ep['episode_number']} — {ep['title']}: {ep['plot_beat']} "
            f"[Opens: {ep.get('opening_beat', '')}] "
            f"[Closes: {ep.get('closing_beat', '')}]"
        )

    archetype_list = "\n".join(f"- {k}: {v['description']}" for k, v in ARC_TEMPLATES.items())

    system = SYSTEM_PROMPT.format(archetypes=archetype_list)

    user_prompt = f"""
Series title: {series_title}
Genre hint: {genre_hint}
Logline: {logline}
Total episodes: {total_episodes}

Episode summaries:
{chr(10).join(episode_summaries)}

Classify this story's narrative DNA and return only valid JSON.
Required fields: story_type, archetype_confidence, secondary_archetype,
archetype_reasoning, thematic_keywords, protagonist_arc.

story_type must be exactly one of: {', '.join(KNOWN_ARCHETYPES)}
""".strip()

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system + "\n\nRespond with valid JSON only. No markdown, no explanation."},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1024,
    )

    raw = completion.choices[0].message.content
    try:
        data = json.loads(raw)
        result = NarrativeDNA(**data)
    except Exception as e:
        raise ValueError(
            f"Narrative DNA Classifier: Failed to parse Groq response.\nRaw:\n{raw}"
        ) from e

    # Validate archetype is in our known list
    if result.story_type not in KNOWN_ARCHETYPES:
        raise ValueError(
            f"Narrative DNA Classifier: GPT returned unknown archetype '{result.story_type}'. "
            f"Valid: {KNOWN_ARCHETYPES}"
        )

    # Pull the matching template and scale the curve to actual episode count
    template = ARC_TEMPLATES[result.story_type]
    scaled_curve = _scale_curve(template["base_curve"], total_episodes)

    # Inject template fields that don't come from GPT
    result.ideal_curve = scaled_curve
    result.cliffhanger_weight = template["cliffhanger_weight"]
    result.pacing_note = template["pacing_note"]
    result.series_title = series_title
    result.total_episodes = total_episodes

    return result


# ---------------------------------------------------------------------------
# Pipeline-compatible wrapper
# ---------------------------------------------------------------------------

def run(decomposed_series: dict) -> dict:
    """
    Pipeline entry point called by the Module 16 Orchestrator.

    Args:
        decomposed_series: Output dict from Module 3 run().

    Returns:
        dict: JSON-serialisable NarrativeDNA dict.
              Passed to Module 7 (ideal_curve), Module 8 (cliffhanger_weight),
              and Module 14 (archetype context).
    """
    dna = classify_narrative_dna(decomposed_series)
    return dna.model_dump()


# ---------------------------------------------------------------------------
# CLI — run directly for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Minimal mock of Module 3 output for standalone testing
    mock_module3_output = {
        "series_title": "The Forgotten Signal",
        "genre": "mystery",
        "logline": "A radio operator discovers signals from a dead station and uncovers a government conspiracy 30 years in the making.",
        "total_episodes": 5,
        "episodes": [
            {
                "episode_number": 1,
                "title": "Dead Air",
                "plot_beat": "Maya picks up a signal from a station closed 30 years ago.",
                "opening_beat": "Maya alone at the tower, routine shift, silence — then static.",
                "closing_beat": "She traces the signal to GPS coordinates in the middle of nowhere.",
            },
            {
                "episode_number": 2,
                "title": "Interference",
                "plot_beat": "Maya finds the coordinates lead to a sealed government bunker.",
                "opening_beat": "Maya drives to the coordinates at dawn, finds a rusted fence.",
                "closing_beat": "She breaks in and the bunker door swings open on its own.",
            },
            {
                "episode_number": 3,
                "title": "Static",
                "plot_beat": "Encrypted files inside link Director Osei to the original station.",
                "opening_beat": "Maya is inside the bunker, flashlight, rows of filing cabinets.",
                "closing_beat": "She finds a hidden door behind a bookshelf.",
            },
            {
                "episode_number": 4,
                "title": "Frequency",
                "plot_beat": "Osei confronts Maya. The Voice is revealed to be a 1991 AI.",
                "opening_beat": "Osei appears at the bunker entrance, gun raised.",
                "closing_beat": "The AI speaks directly to Maya: 'I've been waiting for you.'",
            },
            {
                "episode_number": 5,
                "title": "Broadcast",
                "plot_beat": "Maya must choose: silence the AI or expose the government.",
                "opening_beat": "Maya at the broadcast controls, Osei unconscious behind her.",
                "closing_beat": "She hits the button. Screens across the city light up.",
            },
        ],
    }

    print("=" * 60)
    print("MODULE 4 — NARRATIVE DNA CLASSIFIER")
    print("=" * 60)
    print(f"\nClassifying: {mock_module3_output['series_title']}")
    print("Calling GPT-4o...\n")

    try:
        output = run(mock_module3_output)
        print(json.dumps(output, indent=2))

        print("\n" + "=" * 60)
        print(f"✅ Story type:       {output['story_type']}")
        print(f"✅ Confidence:       {output['archetype_confidence']}")
        print(f"✅ Secondary:        {output['secondary_archetype']}")
        print(f"✅ Ideal curve:      {output['ideal_curve']}")
        print(f"✅ CH weight:        {output['cliffhanger_weight']}")
        print(f"✅ Protagonist arc:  {output['protagonist_arc']}")
        print(f"✅ Keywords:         {', '.join(output['thematic_keywords'])}")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# ─────────────────────────────────────────

async def run_narrative_dna(pipeline: dict) -> dict:
    """Async adapter for Module 16 orchestrator."""
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: run(pipeline))
    pipeline["narrative_dna"] = result
    pipeline.setdefault("emotional_arc", {
        "ideal_curve": result.get("ideal_curve", []),
        "actual_curve": [],
        "flat_zones": []
    })
    pipeline["story_type"] = result.get("story_type", "unknown")
    pipeline["cliffhanger_weight"] = result.get("cliffhanger_weight", 1.0)
    return pipeline
