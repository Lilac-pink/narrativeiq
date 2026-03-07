"""
Module 3 — Story Decomposer
Phase 2: Story Ingestion

Takes a raw story idea (string) and uses GPT-4o structured outputs to return
a fully structured episode-by-episode JSON conforming to the Episode Data Model.
"""

import os
import json
import re
from typing import Optional
from groq import Groq
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Inline Episode schema (mirrors Module 1 — Episode Data Model)
# ---------------------------------------------------------------------------

class EpisodeDecomposed(BaseModel):
    episode_number: int = Field(..., description="Sequential episode number, starting at 1")
    title: str = Field(..., description="Short, evocative episode title")
    plot_beat: str = Field(..., description="4-6 sentence description of the core story beat with specific scenes and character actions")
    opening_beat: str = Field(..., description="How this episode opens (first scene description)")
    closing_beat: str = Field(..., description="How this episode ends / its cliffhanger setup")
    characters: list[str] = Field(..., description="Named characters who appear in this episode")
    locations: list[str] = Field(..., description="Named locations featured in this episode")
    character_descriptions: dict[str, str] = Field(
        default_factory=dict,
        description="Map of character name → trait/description for characters introduced or developed in this episode"
    )
    time_references: list[str] = Field(
        default_factory=list,
        description="Any explicit time references (e.g. '30 years ago', 'that night', '1991')"
    )
    action_verbs: list[str] = Field(
        default_factory=list,
        description="Key action verbs that describe what happens (for NLP Extractor)"
    )
    conflict_keywords: list[str] = Field(
        default_factory=list,
        description="Words/phrases that signal conflict or tension"
    )
    raw_text: str = Field(..., description="Full prose description of the episode for downstream NLP modules")


class DecomposedSeries(BaseModel):
    series_title: str = Field(..., description="Title of the overall series")
    genre: str = Field(..., description="Inferred genre (e.g. thriller, romance, mystery)")
    total_episodes: int = Field(..., description="Total number of episodes generated")
    logline: str = Field(..., description="One-sentence series logline")
    episodes: list[EpisodeDecomposed] = Field(..., description="Ordered list of decomposed episodes")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an elite TV showrunner and story architect — think Vince Gilligan, Shonda Rhimes, David Simon.

Your job is to take a raw story idea and decompose it into a gripping episode-by-episode breakdown. Every field must be LONG, SPECIFIC, and CINEMATIC. Vague summaries are unacceptable.

For each episode you MUST produce:

- title: A punchy, evocative episode title (3-6 words)

- plot_beat: 4-6 sentences. Describe EXACTLY what happens — specific scenes, character decisions, confrontations, revelations. Name characters. Show cause and effect. No vague summaries.

- opening_beat: 4-5 sentences. Set the scene in vivid detail — location, time of day, mood, what the character is doing and thinking as the episode begins.

- closing_beat: 4-5 sentences. The cliffhanger. End on a specific moment of tension, revelation, or danger. Make it impossible NOT to watch the next episode.

- characters: list of character names appearing in this episode

- locations: list of specific named locations (not just "a house" — "Marcus's childhood home in Detroit")

- character_descriptions: for each new or key character, write 2-3 sentences: age, appearance, fatal flaw, hidden strength, what they want, what they fear

- time_references: list of time markers as strings (e.g. ["3 days after the funeral", "midnight"])

- action_verbs: 5-8 strong verbs driving the episode (e.g. ["confronts", "betrays", "flees"])

- conflict_keywords: 5-8 tension words specific to this episode (e.g. ["inheritance", "addiction", "surveillance"])

- raw_text: A RICH 250-350 word prose passage describing the full episode in vivid, sensory detail. Write like a TV pitch document — specific characters by name, specific dialogue beats, specific emotional turning points, specific visual moments. This must read like a real episode synopsis that could convince a network executive. Include the opening image, the central conflict, a key scene description, and the closing image.

STRICT LENGTH REQUIREMENTS — SHORT RESPONSES WILL BE REJECTED:
- plot_beat: minimum 4 sentences
- opening_beat: minimum 4 sentences  
- closing_beat: minimum 4 sentences
- raw_text: minimum 250 words

Series-level rules:
- Emotional intensity MUST escalate: early episodes build dread, middle episodes explode, finale delivers catharsis
- Every episode ending must create a specific unanswered question
- Characters must have consistent, specific flaws that drive conflict
- Locations must feel real and specific — they should have atmosphere

Output ONLY valid JSON. No preamble, no markdown, no explanation outside the JSON.
""".strip()


# ---------------------------------------------------------------------------
# Core decomposer function
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# JSON Normaliser — fixes common Groq field name mismatches
# ---------------------------------------------------------------------------

def _normalise_data(data: dict) -> dict:
    """Fix common field name variants Groq returns instead of our schema."""

    # Top-level field aliases
    if "genre" not in data:
        data["genre"] = data.pop("genres", data.pop("type", data.pop("story_type", "Drama")))
    if "total_episodes" not in data:
        data["total_episodes"] = data.pop("episode_count", data.pop("num_episodes", len(data.get("episodes", []))))
    if "logline" not in data:
        data["logline"] = data.pop("summary", data.pop("description", data.pop("premise", "")))

    # Episode-level fixes
    for ep in data.get("episodes", []):
        # episode_number
        if "episode_number" not in ep:
            ep["episode_number"] = ep.pop("episode", ep.pop("ep_number", ep.pop("number", 0)))

        # time_references must be a list, not a dict or string
        tr = ep.get("time_references", [])
        if isinstance(tr, dict):
            ep["time_references"] = list(tr.values())
        elif isinstance(tr, str):
            ep["time_references"] = [tr] if tr else []
        elif not isinstance(tr, list):
            ep["time_references"] = []

        # characters must be a list of strings
        chars = ep.get("characters", [])
        if isinstance(chars, dict):
            ep["characters"] = list(chars.keys())
        elif isinstance(chars, str):
            ep["characters"] = [chars]

        # locations must be a list of strings
        locs = ep.get("locations", [])
        if isinstance(locs, dict):
            ep["locations"] = list(locs.keys())
        elif isinstance(locs, str):
            ep["locations"] = [locs]

        # action_verbs / conflict_keywords — ensure lists
        for field in ("action_verbs", "conflict_keywords"):
            val = ep.get(field, [])
            if isinstance(val, str):
                ep[field] = [val]
            elif not isinstance(val, list):
                ep[field] = []

        # character_descriptions — ensure dict
        if not isinstance(ep.get("character_descriptions"), dict):
            ep["character_descriptions"] = {}

        # Ensure string fields exist
        for field in ("plot_beat", "opening_beat", "closing_beat", "raw_text"):
            if field not in ep or not isinstance(ep[field], str):
                ep[field] = ep.get(field, "") or ""

    return data


def decompose_story(
    raw_story_idea: str,
    num_episodes: Optional[int] = None,
    api_key: Optional[str] = None,
    model: str = "llama-3.1-8b-instant",
) -> DecomposedSeries:
    """
    Takes a raw story idea string and returns a fully structured DecomposedSeries object.

    Args:
        raw_story_idea: The creator's raw story pitch or idea.
        num_episodes:   Optional target episode count (defaults to GPT's judgment, usually 5–8).
        api_key:        OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model:          Model to use. Default is gpt-4o.

    Returns:
        DecomposedSeries: Pydantic model with all episodes structured.

    Raises:
        ValueError: If the API response cannot be parsed into the schema.
        openai.OpenAIError: On API-level failures.
    """
    client = Groq(api_key=api_key or os.environ["GROQ_API_KEY"])

    # Build the user prompt
    episode_instruction = (
        f"Generate exactly {num_episodes} episodes." if num_episodes
        else "Choose the optimal number of episodes for this story (typically 5–8)."
    )

    user_prompt = f"""
Story idea:
\"\"\"{raw_story_idea}\"\"\"

{episode_instruction}

Decompose this into a complete episode-by-episode breakdown. Return only valid JSON.
""".strip()

    # Call Groq with JSON mode
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
        max_tokens=6000,
    )

    raw = completion.choices[0].message.content or ""

    # ── Resilient JSON parsing ───────────────────────────────────────────────
    # Groq occasionally returns malformed JSON (unmatched quotes, trailing
    # commas, cut-off content). Try several recovery strategies before giving up.
    data = None

    # Strategy 1: standard parse
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences if present
    if data is None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Strategy 3: extract the largest {...} block (handles prefix/suffix junk)
    if data is None:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # Strategy 4: truncated JSON — try to close open structures
    if data is None:
        attempt = raw.strip()
        # Count unclosed braces/brackets and close them
        open_braces   = attempt.count("{") - attempt.count("}")
        open_brackets = attempt.count("[") - attempt.count("]")
        attempt += "]" * open_brackets + "}" * open_braces
        try:
            data = json.loads(attempt)
        except json.JSONDecodeError:
            pass

    if data is None:
        raise ValueError(f"Story Decomposer: Failed to parse Groq response.\nRaw output:\n{raw[:500]}")

    # Normalise field names before Pydantic validation
    data = _normalise_data(data)

    try:
        result = DecomposedSeries(**data)
    except Exception as e:
        raise ValueError(f"Story Decomposer: Schema validation failed: {e}") from e

    return result


# ---------------------------------------------------------------------------
# Pipeline-compatible wrapper
# ---------------------------------------------------------------------------

def run(raw_story_idea: str, num_episodes: Optional[int] = None) -> dict:
    """
    Pipeline entry point called by the Module 16 Orchestrator.

    Args:
        raw_story_idea: Raw story pitch string from the creator.
        num_episodes:   Optional episode count override.

    Returns:
        dict: JSON-serialisable dict matching the DecomposedSeries schema,
              ready to be passed to Module 4 (Narrative DNA Classifier)
              and Module 5 (NLP Extractor).
    """
    series = decompose_story(raw_story_idea, num_episodes=num_episodes)
    return series.model_dump()


# ---------------------------------------------------------------------------
# CLI — run directly for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import textwrap

    sample_idea = """
    A marine biologist discovers that whale song patterns have been changing globally
    in a way that forms a coherent mathematical sequence. As she digs deeper, she
    realises the whales may be responding to a signal — not from the ocean, but from
    beneath the ocean floor. Governments are covering it up. She has 72 hours before
    the next pulse, which her models predict will be catastrophic.
    """

    print("=" * 60)
    print("MODULE 3 — STORY DECOMPOSER")
    print("=" * 60)
    print(f"\nInput idea:\n{textwrap.dedent(sample_idea).strip()}\n")
    print("Calling GPT-4o...\n")

    try:
        output = run(raw_story_idea=sample_idea, num_episodes=5)
        print(json.dumps(output, indent=2))

        # Quick sanity checks
        print("\n" + "=" * 60)
        print(f"✅ Series: {output['series_title']}")
        print(f"✅ Genre: {output['genre']}")
        print(f"✅ Episodes generated: {output['total_episodes']}")
        for ep in output["episodes"]:
            print(f"  Ep {ep['episode_number']}: {ep['title']} — {len(ep['characters'])} chars, {len(ep['locations'])} locations")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────
# MODULE 16 ADAPTER
# run_story_decomposer is the name Module 16 imports
# ─────────────────────────────────────────

async def run_story_decomposer(raw_story: str, num_episodes: int = None) -> dict:
    """Async adapter for Module 16 orchestrator."""
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: run(raw_story, num_episodes))
    return result
