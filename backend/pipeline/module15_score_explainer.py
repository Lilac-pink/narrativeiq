"""
Module 15 — Score Explainer
Converts all numerical scores across modules into plain-English,
creator-friendly 1–2 sentence explanations using GPT-4o.
"""

import asyncio
import json
import os
from typing import Any
from groq import AsyncGroq

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.1-8b-instant"

# ---------------------------------------------------------------------------
# Score definitions — every numeric score produced by Modules 6–13
# Each entry: (label, value, low_is_bad, scale_description)
# ---------------------------------------------------------------------------
def _build_score_items(episode: dict, series_meta: dict) -> list[dict]:
    """
    Collect every numeric score for a single episode into a flat list
    of dicts ready to be explained by the LLM.
    """
    ep_num   = episode["episode_number"]
    ep_title = episode["title"]

    items = [
        # Module 6 — Emotional Arc Analyser
        {
            "score_id": f"ep{ep_num}_emotion_score",
            "label": "Emotion Intensity Score",
            "episode": ep_num,
            "episode_title": ep_title,
            "module": 6,
            "value": episode.get("emotion_score"),
            "scale": "0 to 1 (higher = more emotionally intense)",
            "context": f"Flat zones flagged: {series_meta.get('emotional_arc', {}).get('flat_zones', [])}",
        },
        # Module 7 — Arc Deviation Scorer
        {
            "score_id": f"ep{ep_num}_arc_deviation",
            "label": "Arc Deviation Score",
            "episode": ep_num,
            "episode_title": ep_title,
            "module": 7,
            "value": episode.get("arc_deviation"),
            "scale": "0 to 1 (lower = closer to ideal; higher = bigger gap from ideal curve)",
            "context": f"Ideal emotion for this episode: {series_meta.get('emotional_arc', {}).get('ideal_curve', [])[ep_num - 1] if series_meta.get('emotional_arc', {}).get('ideal_curve') else 'N/A'}",
        },
        # Module 8 — Cliffhanger Scoring Engine
        {
            "score_id": f"ep{ep_num}_cliffhanger_score",
            "label": "Cliffhanger Score",
            "episode": ep_num,
            "episode_title": ep_title,
            "module": 8,
            "value": episode.get("cliffhanger_score"),
            "scale": "0 to 10 (higher = stronger cliffhanger across 6 criteria)",
            "context": str(
                next(
                    (c for c in series_meta.get("cliffhanger_breakdown", []) if c["episode_number"] == ep_num),
                    {}
                )
            ),
        },
        # Module 9 — Continuity Auditor
        {
            "score_id": f"ep{ep_num}_continuity_score",
            "label": "Continuity Score",
            "episode": ep_num,
            "episode_title": ep_title,
            "module": 9,
            "value": episode.get("continuity_score"),
            "scale": "0 to 1 (higher = stronger narrative continuity into next episode)",
            "context": str(
                [i for i in series_meta.get("continuity_issues", []) if f"Episode {ep_num}" in i.get("transition", "")]
            ),
        },
        # Module 12 — Drop-off Probability Predictor
        {
            "score_id": f"ep{ep_num}_drop_off_probability",
            "label": "Drop-off Probability",
            "episode": ep_num,
            "episode_title": ep_title,
            "module": 12,
            "value": episode.get("drop_off_probability"),
            "scale": "0 to 1 (higher = greater risk the audience stops watching after this episode)",
            "context": "Predicted by GradientBoosting ML model trained on story engagement features.",
        },
    ]

    # Module 13 — Retention Heatmap block-level risk
    heatmap_entry = next(
        (h for h in series_meta.get("retention_heatmap", []) if h["episode_number"] == ep_num), None
    )
    if heatmap_entry:
        risk_map = {"low": 0.2, "medium": 0.5, "high": 0.9}
        for block in heatmap_entry.get("blocks", []):
            items.append({
                "score_id": f"ep{ep_num}_retention_{block['time_block'].replace('–', '_').replace('s', '')}",
                "label": f"Retention Risk ({block['time_block']})",
                "episode": ep_num,
                "episode_title": ep_title,
                "module": 13,
                "value": risk_map.get(block["risk_level"], 0.5),
                "scale": "categorical mapped to 0.2 / 0.5 / 0.9 (low / medium / high risk)",
                "context": f"Risk level: {block['risk_level']}. Reason: {block['reason']}",
            })

    return [item for item in items if item["value"] is not None]


# ---------------------------------------------------------------------------
# Single-score explainer — one LLM call per score
# ---------------------------------------------------------------------------
async def _explain_score(item: dict) -> dict:
    prompt = f"""You are NarrativeIQ, a story analytics assistant talking directly to a creative writer.

Explain the following score in 1–2 plain-English sentences. Be specific, encouraging where the score is strong, and constructive where it needs improvement. Never use jargon like "cosine similarity" or "MAE". Talk like a script editor, not a data scientist.

Score details:
- Series episode: Episode {item['episode']} — "{item['episode_title']}"
- Score name: {item['label']} (Module {item['module']})
- Score value: {item['value']}
- Scale: {item['scale']}
- Supporting context: {item['context']}

Return ONLY the plain-English explanation. No bullet points, no labels, just the sentences."""

    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    explanation = response.choices[0].message.content.strip()
    return {**item, "explanation": explanation}


# ---------------------------------------------------------------------------
# Series-level summary
# ---------------------------------------------------------------------------
async def _explain_series_summary(series_data: dict) -> str:
    episodes = series_data.get("episodes", [])
    avg_emotion      = sum(e.get("emotion_score", 0) for e in episodes) / len(episodes)
    avg_cliffhanger  = sum(e.get("cliffhanger_score", 0) for e in episodes) / len(episodes)
    avg_drop_off     = sum(e.get("drop_off_probability", 0) for e in episodes) / len(episodes)
    avg_continuity   = sum(e.get("continuity_score", 0) for e in episodes) / len(episodes)
    flat_zones       = series_data.get("emotional_arc", {}).get("flat_zones", [])

    prompt = f"""You are NarrativeIQ, a story analytics assistant. Write a 3–4 sentence overall series health summary for a creative writer. Be direct, warm, and actionable. No jargon.

Series: "{series_data.get('series_title')}" ({series_data.get('total_episodes')} episodes)
Average emotion intensity: {avg_emotion:.2f} / 1.0
Average cliffhanger strength: {avg_cliffhanger:.1f} / 10
Average drop-off risk: {avg_drop_off:.2f} / 1.0
Average continuity score: {avg_continuity:.2f} / 1.0
Flat emotional zones at episodes: {flat_zones if flat_zones else 'None'}
Total continuity issues: {len(series_data.get('continuity_issues', []))}
Top suggestion: {series_data.get('suggestions', [{}])[0].get('suggestion', 'N/A') if series_data.get('suggestions') else 'N/A'}

Return ONLY the summary paragraph."""

    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def run_score_explainer(pipeline_output: dict) -> dict:
    """
    Main entry point for Module 15.

    Args:
        pipeline_output: The aggregated output dict from the pipeline orchestrator
                         (Module 16), containing 'episodes', 'emotional_arc',
                         'cliffhanger_breakdown', 'retention_heatmap',
                         'continuity_issues', and 'suggestions'.

    Returns:
        The same dict with a new top-level key 'score_explanations' containing:
            - series_summary: str
            - by_episode: { ep_number: { score_id: { value, explanation } } }
            - flat_list: [ { score_id, label, episode, value, explanation } ]
    """
    episodes   = pipeline_output.get("episodes", [])
    series_meta = pipeline_output  # full payload used for context lookups

    # --- Build all score items across all episodes ---
    all_items: list[dict] = []
    for episode in episodes:
        all_items.extend(_build_score_items(episode, series_meta))

    print(f"[Module 15] Explaining {len(all_items)} scores across {len(episodes)} episodes...")

    # --- Fire all LLM calls concurrently ---
    tasks = [_explain_score(item) for item in all_items]
    series_task = _explain_series_summary(pipeline_output)

    results, series_summary = await asyncio.gather(
        asyncio.gather(*tasks),
        series_task,
    )

    # --- Organise into by_episode dict ---
    by_episode: dict[int, dict[str, Any]] = {}
    for r in results:
        ep = r["episode"]
        if ep not in by_episode:
            by_episode[ep] = {
                "episode_number": ep,
                "episode_title": r["episode_title"],
                "scores": {},
            }
        by_episode[ep]["scores"][r["score_id"]] = {
            "label": r["label"],
            "module": r["module"],
            "value": r["value"],
            "scale": r["scale"],
            "explanation": r["explanation"],
        }

    flat_list = [
        {
            "score_id":    r["score_id"],
            "label":       r["label"],
            "episode":     r["episode"],
            "episode_title": r["episode_title"],
            "module":      r["module"],
            "value":       r["value"],
            "explanation": r["explanation"],
        }
        for r in results
    ]

    explanations_bundle = {
        "series_summary": series_summary,
        "by_episode":     by_episode,
        "flat_list":      flat_list,
        "total_scores_explained": len(flat_list),
    }

    print(f"[Module 15] ✓ Done. {len(flat_list)} scores explained.")

    # Return enriched pipeline output
    return {**pipeline_output, "score_explanations": explanations_bundle}


# ---------------------------------------------------------------------------
# CLI / standalone test
# ---------------------------------------------------------------------------
async def _demo():
    """Run Module 15 against mock data to verify output."""

    MOCK_DATA = {
        "series_title": "The Forgotten Signal",
        "total_episodes": 5,
        "episodes": [
            {"episode_number": 1, "title": "Dead Air",      "emotion_score": 0.42, "arc_deviation": 0.12, "cliffhanger_score": 7.2, "continuity_score": 0.91, "drop_off_probability": 0.18},
            {"episode_number": 2, "title": "Interference",  "emotion_score": 0.61, "arc_deviation": 0.11, "cliffhanger_score": 8.1, "continuity_score": 0.87, "drop_off_probability": 0.24},
            {"episode_number": 3, "title": "Static",        "emotion_score": 0.58, "arc_deviation": 0.07, "cliffhanger_score": 5.4, "continuity_score": 0.72, "drop_off_probability": 0.41},
            {"episode_number": 4, "title": "Frequency",     "emotion_score": 0.79, "arc_deviation": 0.01, "cliffhanger_score": 8.8, "continuity_score": 0.85, "drop_off_probability": 0.29},
            {"episode_number": 5, "title": "Broadcast",     "emotion_score": 0.91, "arc_deviation": 0.04, "cliffhanger_score": 9.3, "continuity_score": 0.94, "drop_off_probability": 0.15},
        ],
        "emotional_arc": {
            "ideal_curve": [0.3, 0.5, 0.65, 0.8, 0.95],
            "actual_curve": [0.42, 0.61, 0.58, 0.79, 0.91],
            "flat_zones": [3],
        },
        "cliffhanger_breakdown": [
            {
                "episode_number": 3, "title": "Static", "score": 5.4,
                "criteria": [
                    {"criterion": "Unresolved question",   "pass": True,  "reason": "Encrypted files raise unanswered questions"},
                    {"criterion": "Emotional stakes raised","pass": False, "reason": "No direct threat to Maya"},
                    {"criterion": "Character in jeopardy",  "pass": False, "reason": "Maya is not in immediate danger"},
                    {"criterion": "New information revealed","pass": True,  "reason": "Osei connection is a new plot thread"},
                    {"criterion": "Time pressure present",  "pass": False, "reason": "No deadline established"},
                    {"criterion": "Scene ends on action beat","pass": True, "reason": "Ends on Maya finding a hidden door"},
                ],
            }
        ],
        "retention_heatmap": [
            {
                "episode_number": 3,
                "blocks": [
                    {"time_block": "0–15s",  "risk_level": "low",    "reason": "Picks up directly from bunker entrance"},
                    {"time_block": "15–30s", "risk_level": "medium", "reason": "Slow search sequence, low tension"},
                    {"time_block": "30–45s", "risk_level": "high",   "reason": "Dialogue-heavy, no visual tension"},
                    {"time_block": "45–60s", "risk_level": "high",   "reason": "Repetitive exposition of known facts"},
                    {"time_block": "60–75s", "risk_level": "medium", "reason": "Discovery of files re-engages viewer"},
                    {"time_block": "75–90s", "risk_level": "low",    "reason": "Hidden door cliffhanger recovers interest"},
                ],
            }
        ],
        "continuity_issues": [
            {"transition": "Episode 2 → Episode 3", "similarity_score": 0.72, "severity": "medium", "issue": "Maya appears inside bunker with no transition shown."},
            {"transition": "Episode 3 → Episode 4", "similarity_score": 0.58, "severity": "high",   "issue": "Dr. Reeves disappears without explanation."},
        ],
        "suggestions": [
            {"priority": 1, "episode": 3, "category": "Pacing", "suggestion": "Cut the 30–60s exposition block.", "impact_score": 9.1},
        ],
    }

    output = await run_score_explainer(MOCK_DATA)
    print("\n" + "=" * 60)
    print("SERIES SUMMARY")
    print("=" * 60)
    print(output["score_explanations"]["series_summary"])
    print("\n" + "=" * 60)
    print("SAMPLE SCORE EXPLANATIONS")
    print("=" * 60)
    for item in output["score_explanations"]["flat_list"][:6]:
        print(f"\n[Ep {item['episode']} · {item['label']}]")
        print(f"  Value: {item['value']}")
        print(f"  → {item['explanation']}")

    # Dump full output to file
    with open("/mnt/user-data/outputs/module_15_sample_output.json", "w") as f:
        json.dump(output["score_explanations"], f, indent=2)
    print("\n✓ Full output written to module_15_sample_output.json")


if __name__ == "__main__":
    asyncio.run(_demo())
