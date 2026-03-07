"""
Module 16 — Pipeline Orchestrator
Controls the full NarrativeIQ execution order using asyncio.

Execution graph:
  [Sequential]  Module 3 → Module 4
  [Parallel]    Module 5, 6, 9, 10
  [Parallel]    Module 7, 8, 12, 13
  [Sequential]  Module 14 → Module 15
  [POST]        Final JSON → Lovable dashboard

Usage:
    python module_16_orchestrator.py --story "Your raw story idea here"
    python module_16_orchestrator.py --story "..." --lovable-url https://your-app.lovable.app
    python module_16_orchestrator.py --demo   # runs with built-in mock story
"""

import asyncio
import json
import logging
import os
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx  # async HTTP — pip install httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("NarrativeIQ.Orchestrator")

# ---------------------------------------------------------------------------
# Module imports  (each module exposes one async entry-point function)
# Replace these stubs with real imports once each module is built.
# ---------------------------------------------------------------------------
try:
    from pipeline.module3_story_decomposer      import run_story_decomposer
except ImportError:
    async def run_story_decomposer(raw_story: str) -> dict:          # STUB
        log.warning("Module 3 stub — returning mock decomposed story")
        return _stub_decomposed_story(raw_story)

try:
    from pipeline.module4_narrative_dna         import run_narrative_dna
except ImportError:
    async def run_narrative_dna(pipeline: dict) -> dict:             # STUB
        log.warning("Module 4 stub")
        pipeline.setdefault("story_type", "thriller")
        pipeline.setdefault("emotional_arc", {
            "ideal_curve": [0.3, 0.5, 0.65, 0.8, 0.95],
            "actual_curve": [], "flat_zones": [],
        })
        return pipeline

try:
    from pipeline.module5_nlp_extractor         import run_nlp_extractor
except ImportError:
    async def run_nlp_extractor(pipeline: dict) -> dict:             # STUB
        log.warning("Module 5 stub")
        return pipeline

try:
    from pipeline.module6_emotional_arc         import run_emotional_arc
except ImportError:
    async def run_emotional_arc(pipeline: dict) -> dict:             # STUB
        log.warning("Module 6 stub")
        import random
        for ep in pipeline.get("episodes", []):
            ep.setdefault("emotion_score", round(random.uniform(0.35, 0.95), 2))
        actual = [ep["emotion_score"] for ep in pipeline["episodes"]]
        pipeline["emotional_arc"]["actual_curve"] = actual
        pipeline["emotional_arc"]["flat_zones"] = [
            ep["episode_number"] for i, ep in enumerate(pipeline["episodes"])
            if i > 0 and abs(actual[i] - actual[i - 1]) < 0.05
        ]
        return pipeline

try:
    from pipeline.module9_continuity    import run_continuity_auditor
except ImportError:
    async def run_continuity_auditor(pipeline: dict) -> dict:        # STUB
        log.warning("Module 9 stub")
        pipeline.setdefault("continuity_issues", [])
        for ep in pipeline.get("episodes", []):
            ep.setdefault("continuity_score", 0.85)
        return pipeline

try:
    from pipeline.module10_character_consistency import run_character_consistency
except ImportError:
    async def run_character_consistency(pipeline: dict) -> dict:     # STUB
        log.warning("Module 10 stub")
        pipeline.setdefault("character_issues", [])
        return pipeline

try:
    from pipeline.module7_arc_deviation         import run_arc_deviation
except ImportError:
    async def run_arc_deviation(pipeline: dict) -> dict:             # STUB
        log.warning("Module 7 stub")
        ideal  = pipeline.get("emotional_arc", {}).get("ideal_curve", [])
        actual = pipeline.get("emotional_arc", {}).get("actual_curve", [])
        for i, ep in enumerate(pipeline.get("episodes", [])):
            dev = round(abs(ideal[i] - actual[i]), 3) if i < len(ideal) and i < len(actual) else 0.1
            ep.setdefault("arc_deviation", dev)
        return pipeline

try:
    from pipeline.module8_cliffhanger    import run_cliffhanger_engine
except ImportError:
    async def run_cliffhanger_engine(pipeline: dict) -> dict:        # STUB
        log.warning("Module 8 stub")
        pipeline.setdefault("cliffhanger_breakdown", [])
        for ep in pipeline.get("episodes", []):
            ep.setdefault("cliffhanger_score", 7.0)
        return pipeline

try:
    from pipeline.module12_dropoff_predictor     import run_dropoff_predictor
except ImportError:
    async def run_dropoff_predictor(pipeline: dict) -> dict:         # STUB
        log.warning("Module 12 stub")
        for ep in pipeline.get("episodes", []):
            cs  = ep.get("cliffhanger_score", 7) / 10
            em  = ep.get("emotion_score", 0.5)
            co  = ep.get("continuity_score", 0.85)
            ep.setdefault("drop_off_probability", round(max(0.05, 1 - (cs * 0.4 + em * 0.3 + co * 0.3)), 2))
        return pipeline

try:
    from pipeline.module13_retention_heatmap     import run_retention_heatmap
except ImportError:
    async def run_retention_heatmap(pipeline: dict) -> dict:         # STUB
        log.warning("Module 13 stub")
        pipeline.setdefault("retention_heatmap", [])
        return pipeline

try:
    from pipeline.module14_suggestion_engine     import run_suggestion_engine
except ImportError:
    async def run_suggestion_engine(pipeline: dict) -> dict:         # STUB
        log.warning("Module 14 stub")
        pipeline.setdefault("suggestions", [])
        return pipeline

try:
    from pipeline.module15_score_explainer       import run_score_explainer
except ImportError:
    async def run_score_explainer(pipeline: dict) -> dict:           # STUB
        log.warning("Module 15 stub")
        pipeline.setdefault("score_explanations", {"series_summary": "Stub summary.", "flat_list": []})
        return pipeline

# ---------------------------------------------------------------------------
# Pipeline state container
# ---------------------------------------------------------------------------
@dataclass
class PipelineState:
    raw_story:       str
    series_title:    str                  = "Untitled Series"
    started_at:      float                = field(default_factory=time.time)
    phase_timings:   dict[str, float]     = field(default_factory=dict)
    errors:          list[str]            = field(default_factory=list)
    data:            dict[str, Any]       = field(default_factory=dict)

    def elapsed(self) -> float:
        return round(time.time() - self.started_at, 2)

    def record(self, phase: str, t0: float):
        self.phase_timings[phase] = round(time.time() - t0, 2)
        log.info(f"  ✓ {phase} completed in {self.phase_timings[phase]}s")

# ---------------------------------------------------------------------------
# Helper — run a module safely, capturing exceptions without crashing pipeline
# ---------------------------------------------------------------------------
async def _safe(name: str, coro) -> dict | None:
    try:
        return await coro
    except Exception as exc:
        log.error(f"  ✗ {name} failed: {exc}")
        log.debug(traceback.format_exc())
        return None

# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------
async def _phase_1_sequential(state: PipelineState) -> None:
    """Module 3 → Module 4  (must be sequential: 4 depends on 3's output)"""
    t0 = time.time()
    log.info("── PHASE 1: Story Ingestion (sequential) ──────────────────")

    # Module 3 — decompose raw story into episode JSON
    log.info("  → Module 3: Story Decomposer")
    decomposed = await _safe("Module 3", run_story_decomposer(state.raw_story))
    if decomposed:
        state.data.update(decomposed)
        state.series_title = state.data.get("series_title", state.series_title)
    else:
        state.errors.append("Module 3 failed — pipeline cannot continue")
        raise RuntimeError("Module 3 (Story Decomposer) failed")

    # Module 4 — classify story DNA, attach ideal arc
    log.info("  → Module 4: Narrative DNA Classifier")
    enriched = await _safe("Module 4", run_narrative_dna(state.data))
    if enriched:
        state.data = enriched

    state.record("Phase 1 (M3→M4)", t0)


async def _phase_2_parallel(state: PipelineState) -> None:
    """Modules 5, 6, 9, 10 in parallel (all read episodes, all write back)"""
    t0 = time.time()
    log.info("── PHASE 2: NLP & Embedding Extraction (parallel) ─────────")

    async def _run_m5(d): return await _safe("Module 5", run_nlp_extractor(d))
    async def _run_m6(d): return await _safe("Module 6", run_emotional_arc(d))
    async def _run_m9(d): return await _safe("Module 9", run_continuity_auditor(d))
    async def _run_m10(d): return await _safe("Module 10", run_character_consistency(d))

    # Each module receives a deep copy so they don't race on the same dict
    import copy
    snap = copy.deepcopy(state.data)

    results = await asyncio.gather(
        _run_m5(copy.deepcopy(snap)),
        _run_m6(copy.deepcopy(snap)),
        _run_m9(copy.deepcopy(snap)),
        _run_m10(copy.deepcopy(snap)),
    )

    module_names = ["Module 5 (NLP)", "Module 6 (Emotional Arc)",
                    "Module 9 (Continuity)", "Module 10 (Characters)"]

    # Merge results back — each module owns specific keys; episode-level scores
    # are merged per episode_number to avoid clobbering
    episode_index = {ep["episode_number"]: ep for ep in state.data.get("episodes", [])}

    EPISODE_KEYS_PER_MODULE = {
        0: ["characters", "locations", "action_verbs", "conflict_keywords", "time_refs"],  # M5
        1: ["emotion_score"],                                                               # M6
        2: ["continuity_score"],                                                            # M9
        3: [],                                                                              # M10 (series-level)
    }
    SERIES_KEYS_PER_MODULE = {
        0: [],
        1: ["emotional_arc"],
        2: ["continuity_issues"],
        3: ["character_issues"],
    }

    for i, result in enumerate(results):
        if result is None:
            log.warning(f"  ⚠ {module_names[i]} returned None — skipping merge")
            continue
        # merge episode-level keys
        for ep in result.get("episodes", []):
            num = ep.get("episode_number")
            if num in episode_index:
                for k in EPISODE_KEYS_PER_MODULE[i]:
                    if k in ep:
                        episode_index[num][k] = ep[k]
        # merge series-level keys
        for k in SERIES_KEYS_PER_MODULE[i]:
            if k in result:
                state.data[k] = result[k]

    state.record("Phase 2 (M5,6,9,10)", t0)


async def _phase_3_parallel(state: PipelineState) -> None:
    """Modules 7, 8, 12, 13 in parallel (scoring engines)"""
    t0 = time.time()
    log.info("── PHASE 3: Scoring Engines (parallel) ────────────────────")

    import copy

    async def _run_m7(d):  return await _safe("Module 7",  run_arc_deviation(d))
    async def _run_m8(d):  return await _safe("Module 8",  run_cliffhanger_engine(d))
    async def _run_m12(d): return await _safe("Module 12", run_dropoff_predictor(d))
    async def _run_m13(d): return await _safe("Module 13", run_retention_heatmap(d))

    snap = copy.deepcopy(state.data)

    results = await asyncio.gather(
        _run_m7(copy.deepcopy(snap)),
        _run_m8(copy.deepcopy(snap)),
        _run_m12(copy.deepcopy(snap)),
        _run_m13(copy.deepcopy(snap)),
    )

    episode_index = {ep["episode_number"]: ep for ep in state.data.get("episodes", [])}

    EPISODE_KEYS_PER_MODULE = {
        0: ["arc_deviation"],               # M7
        1: ["cliffhanger_score"],           # M8
        2: ["drop_off_probability"],        # M12
        3: [],                              # M13 (series-level)
    }
    SERIES_KEYS_PER_MODULE = {
        0: [],
        1: ["cliffhanger_breakdown"],
        2: [],
        3: ["retention_heatmap"],
    }

    module_names = ["Module 7 (Arc Dev)", "Module 8 (Cliffhanger)",
                    "Module 12 (Drop-off)", "Module 13 (Heatmap)"]

    for i, result in enumerate(results):
        if result is None:
            log.warning(f"  ⚠ {module_names[i]} returned None — skipping merge")
            continue
        for ep in result.get("episodes", []):
            num = ep.get("episode_number")
            if num in episode_index:
                for k in EPISODE_KEYS_PER_MODULE[i]:
                    if k in ep:
                        episode_index[num][k] = ep[k]
        for k in SERIES_KEYS_PER_MODULE[i]:
            if k in result:
                state.data[k] = result[k]

    state.record("Phase 3 (M7,8,12,13)", t0)


async def _phase_4_sequential(state: PipelineState) -> None:
    """Module 14 → Module 15  (15 needs 14's suggestions to explain them)"""
    t0 = time.time()
    log.info("── PHASE 4: Output & Explainability (sequential) ──────────")

    log.info("  → Module 14: Optimisation Suggestion Engine")
    with_suggestions = await _safe("Module 14", run_suggestion_engine(state.data))
    if with_suggestions:
        state.data = with_suggestions

    log.info("  → Module 15: Score Explainer")
    with_explanations = await _safe("Module 15", run_score_explainer(state.data))
    if with_explanations:
        state.data = with_explanations

    state.record("Phase 4 (M14→M15)", t0)


# ---------------------------------------------------------------------------
# Schema normaliser — ensure output matches Lovable frontend contract
# ---------------------------------------------------------------------------
def _normalise_to_lovable_schema(data: dict, state: PipelineState) -> dict:
    """
    Guarantees the output dict has every key the Lovable frontend expects.
    Missing keys are filled with safe defaults so the dashboard never crashes.
    """
    episodes = data.get("episodes", [])

    # Ensure every episode has all required score fields
    for ep in episodes:
        ep.setdefault("emotion_score",        0.0)
        ep.setdefault("drop_off_probability", 0.5)
        ep.setdefault("cliffhanger_score",    5.0)
        ep.setdefault("continuity_score",     0.5)
        ep.setdefault("arc_deviation",        0.0)
        ep.setdefault("characters",           [])
        ep.setdefault("locations",            [])
        ep.setdefault("plot_beat",            "")

    output = {
        # Core identity
        "series_title":         data.get("series_title", state.series_title),
        "total_episodes":       len(episodes),
        "story_type":           data.get("story_type", "unknown"),

        # Episode cards (Modules 17+)
        "episodes":             episodes,

        # Emotional arc graph (Module 18)
        "emotional_arc":        data.get("emotional_arc", {
            "ideal_curve":  [],
            "actual_curve": [ep["emotion_score"] for ep in episodes],
            "flat_zones":   [],
        }),

        # Cliffhanger breakdown (Module 19)
        "cliffhanger_breakdown": data.get("cliffhanger_breakdown", []),

        # Retention heatmap (Module 20)
        "retention_heatmap":    data.get("retention_heatmap", []),

        # Continuity issues (Module 21)
        "continuity_issues":    data.get("continuity_issues", []),

        # Suggestions (Module 22)
        "suggestions":          data.get("suggestions", []),

        # Score explanations (Module 15)
        "score_explanations":   data.get("score_explanations", {}),

        # Character issues (Module 10)
        "character_issues":     data.get("character_issues", []),

        # Pipeline metadata
        "_pipeline_meta": {
            "generated_at":   datetime.now(timezone.utc).isoformat(),
            "total_time_s":   state.elapsed(),
            "phase_timings":  state.phase_timings,
            "errors":         state.errors,
            "modules_run":    [3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15],
        },
    }
    return output


# ---------------------------------------------------------------------------
# POST to Lovable
# ---------------------------------------------------------------------------
async def _post_to_lovable(payload: dict, lovable_url: str) -> bool:
    endpoint = lovable_url.rstrip("/") + "/api/pipeline/results"
    log.info(f"── POST → {endpoint}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            log.info(f"  ✓ Lovable responded {resp.status_code}: {resp.text[:120]}")
            return True
    except Exception as exc:
        log.error(f"  ✗ POST to Lovable failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main orchestrator entry point
# ---------------------------------------------------------------------------
async def run_pipeline(
    raw_story:    str,
    lovable_url:  str | None = None,
    output_file:  str | None = "pipeline_output.json",
) -> dict:
    """
    Run the full NarrativeIQ pipeline and return the final JSON payload.

    Args:
        raw_story:    The raw story idea string from the creator.
        lovable_url:  If provided, POST the result to the Lovable dashboard.
        output_file:  If provided, write the final JSON to this path.

    Returns:
        Final normalised pipeline output dict.
    """
    log.info("═" * 60)
    log.info("  NarrativeIQ Pipeline — Module 16 Orchestrator")
    log.info("═" * 60)

    state = PipelineState(raw_story=raw_story)

    # ── Phase 1: Sequential ──────────────────────────────────────────────────
    await _phase_1_sequential(state)

    # ── Phase 2: Parallel ────────────────────────────────────────────────────
    await _phase_2_parallel(state)

    # ── Phase 3: Parallel ────────────────────────────────────────────────────
    await _phase_3_parallel(state)

    # ── Phase 4: Sequential ──────────────────────────────────────────────────
    await _phase_4_sequential(state)

    # ── Normalise to Lovable schema ──────────────────────────────────────────
    log.info("── Normalising output to Lovable schema ────────────────────")
    final_output = _normalise_to_lovable_schema(state.data, state)

    # ── Write to file ────────────────────────────────────────────────────────
    if output_file:
        with open(output_file, "w") as f:
            json.dump(final_output, f, indent=2)
        log.info(f"── Output written → {output_file}")

    # ── POST to Lovable ──────────────────────────────────────────────────────
    if lovable_url:
        await _post_to_lovable(final_output, lovable_url)
    else:
        log.info("── No Lovable URL provided — skipping POST")
        log.info("   To connect: set --lovable-url https://your-app.lovable.app")

    # ── Summary ──────────────────────────────────────────────────────────────
    log.info("═" * 60)
    log.info(f"  ✅ Pipeline complete in {state.elapsed()}s")
    log.info(f"  Episodes processed : {final_output['total_episodes']}")
    log.info(f"  Suggestions generated: {len(final_output.get('suggestions', []))}")
    log.info(f"  Continuity issues  : {len(final_output.get('continuity_issues', []))}")
    log.info(f"  Errors             : {len(state.errors)}")
    if state.errors:
        for e in state.errors:
            log.warning(f"    ⚠ {e}")
    log.info("═" * 60)

    return final_output


# ---------------------------------------------------------------------------
# Stub helpers (used when real modules are missing)
# ---------------------------------------------------------------------------
def _stub_decomposed_story(raw_story: str) -> dict:
    """Minimal valid pipeline payload for stub mode."""
    return {
        "series_title": "Untitled Series",
        "total_episodes": 3,
        "episodes": [
            {
                "episode_number": i,
                "title": f"Episode {i}",
                "plot_beat": f"Plot beat for episode {i} derived from: {raw_story[:60]}...",
                "characters": [],
                "locations":  [],
            }
            for i in range(1, 4)
        ],
        "emotional_arc": {
            "ideal_curve": [0.3, 0.6, 0.9],
            "actual_curve": [],
            "flat_zones": [],
        },
        "cliffhanger_breakdown": [],
        "retention_heatmap": [],
        "continuity_issues": [],
        "suggestions": [],
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NarrativeIQ Pipeline Orchestrator")
    parser.add_argument("--story", type=str, help="Raw story idea to process")
    parser.add_argument("--lovable-url", type=str, default=None,
                        help="Lovable dashboard URL (e.g. https://your-app.lovable.app)")
    parser.add_argument("--output", type=str, default="pipeline_output.json",
                        help="Output JSON file path (default: pipeline_output.json)")
    parser.add_argument("--demo", action="store_true",
                        help="Run with a built-in demo story")
    args = parser.parse_args()

    DEMO_STORY = """
    A radio operator named Maya Chen picks up a mysterious signal from a station that
    closed 30 years ago. As she investigates, she discovers encrypted government files
    and an AI that has been running in an abandoned bunker since 1991. She must choose
    between silencing the AI or exposing the government's darkest secrets to the world.
    The story spans 5 episodes with escalating tension and a morally complex finale.
    """

    story_input = DEMO_STORY if args.demo else args.story

    if not story_input:
        parser.error("Provide --story 'your story idea' or use --demo")

    lovable_url = args.lovable_url or os.environ.get("LOVABLE_URL")

    asyncio.run(run_pipeline(
        raw_story=story_input.strip(),
        lovable_url=lovable_url,
        output_file=args.output,
    ))
