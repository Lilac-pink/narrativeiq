"""
Chat Routes — /api/chat/story
AI story consultant that rewrites episodes and rescores them.
"""
import os
import sys
import json
import re
import logging
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from groq import Groq

log = logging.getLogger(__name__)
router = APIRouter()

# Add backend root to path so pipeline imports work
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Rescore helper — reruns M6, M9, M12 on updated episodes
# ---------------------------------------------------------------------------

async def rescore_episodes(pipeline: dict) -> dict:
    """Re-run scoring modules on updated episode data."""

    # Module 6 — Emotional Arc
    try:
        from pipeline.module6_emotional_arc import run_emotional_arc
        pipeline = await run_emotional_arc(pipeline)
        log.info("[Chat rescore] Module 6 (emotional arc) ✓")
    except Exception as e:
        log.warning(f"[Chat rescore] Module 6 failed: {e}")

    # Module 9 — Continuity
    try:
        from pipeline.module9_continuity import run_continuity_auditor
        pipeline = await run_continuity_auditor(pipeline)
        log.info("[Chat rescore] Module 9 (continuity) ✓")
    except Exception as e:
        log.warning(f"[Chat rescore] Module 9 failed: {e}")

    # Module 12 — Drop-off predictor (with fallback if no trained model)
    try:
        from pipeline.module12_dropoff_predictor import run_dropoff_predictor
        pipeline = await run_dropoff_predictor(pipeline)
        log.info("[Chat rescore] Module 12 (drop-off) ✓")
    except Exception as e:
        log.warning(f"[Chat rescore] Module 12 failed: {e} — using score-based fallback")
        # Fallback: calculate drop-off from other scores
        for ep in pipeline.get("episodes", []):
            cs = ep.get("cliffhanger_score", 5) / 10.0
            em = ep.get("emotion_score", 0.5)
            co = ep.get("continuity_score", 0.8)
            ep["drop_off_probability"] = round(max(0.05, min(0.95, 1 - (cs * 0.4 + em * 0.3 + co * 0.3))), 2)
            ep["drop_off_risk_level"] = "high" if ep["drop_off_probability"] >= 0.55 else "low" if ep["drop_off_probability"] < 0.30 else "medium"

    # Module 8 — Cliffhanger (async, uses Groq — run only if key available)
    if os.environ.get("GROQ_API_KEY"):
        try:
            from pipeline.module8_cliffhanger import run_cliffhanger_engine
            pipeline = await run_cliffhanger_engine(pipeline)
            log.info("[Chat rescore] Module 8 (cliffhanger) ✓")
        except Exception as e:
            log.warning(f"[Chat rescore] Module 8 failed: {e}")

    # Rebuild retention heatmap
    try:
        from pipeline.module13_retention_heatmap import run_retention_heatmap
        pipeline = await run_retention_heatmap(pipeline)
        log.info("[Chat rescore] Module 13 (retention) ✓")
    except Exception as e:
        log.warning(f"[Chat rescore] Module 13 failed: {e}")

    # Regenerate suggestions
    try:
        from pipeline.module14_suggestion_engine import run_suggestion_engine
        pipeline = await run_suggestion_engine(pipeline)
        log.info("[Chat rescore] Module 14 (suggestions) ✓")
    except Exception as e:
        log.warning(f"[Chat rescore] Module 14 failed: {e}")

    return pipeline


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    series_title: str
    episodes: list[dict]
    suggestions: list[dict] = []
    full_pipeline: dict = {}  # full pipeline state if available

class ChatResponse(BaseModel):
    reply: str
    updated_episodes: list[dict] | None = None
    updated_pipeline: dict | None = None  # includes rescored arc, retention, suggestions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_target_episode(message: str, episodes: list[dict]) -> int | None:
    match = re.search(r"ep(?:isode)?\s*(\d+)", message.lower())
    if match:
        return int(match.group(1))
    for ep in episodes:
        title = ep.get("title", "").lower()
        if title and title in message.lower():
            return ep.get("episode_number")
    return None

def _wants_rewrite(message: str) -> bool:
    keywords = [
        "rewrite", "change", "update", "make", "add", "stronger",
        "more", "less", "different", "improve", "fix", "apply",
        "revise", "rework", "edit", "modify", "enhance", "replace",
        "give", "create", "write"
    ]
    return any(kw in message.lower() for kw in keywords)


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

@router.post("/api/chat/story", response_model=ChatResponse)
async def story_chat(body: ChatRequest):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    episodes_json = json.dumps(body.episodes, indent=2)
    target_ep = _detect_target_episode(body.message, body.episodes)

    suggestions_summary = "\n".join([
        f"- Ep {s.get('episode')}: {s.get('suggestion', '')[:120]}"
        for s in body.suggestions[:5]
    ])

    if _wants_rewrite(body.message):
        if target_ep:
            target_info = f"The user wants to modify ONLY Episode {target_ep}. Leave all other episodes COMPLETELY UNCHANGED — copy their data exactly."
        else:
            target_info = "Identify which episode(s) need changes from the user message. Leave all unmentioned episodes COMPLETELY UNCHANGED."

        system = f"""You are an elite TV script consultant for the series "{body.series_title}".

CRITICAL RULES:
1. {target_info}
2. For UNCHANGED episodes: copy their EXACT data from the input — same title, plot_beat, opening_beat, closing_beat, raw_text, characters, locations, all scores. Do NOT summarise, shorten, or paraphrase them.
3. For the CHANGED episode: rewrite it fully based on the user request. Make raw_text 150-200 words of vivid prose.
4. Return ALL {len(body.episodes)} episodes.
5. Do NOT change scores (emotion_score, cliffhanger_score etc) — they will be recalculated automatically.

Full episode data — copy unchanged episodes EXACTLY from this:
{episodes_json}

Suggestions for context:
{suggestions_summary}

Respond in this exact JSON only:
{{
  "reply": "2-3 sentences explaining what you changed and why",
  "updated_episodes": [
    {{
      "episode_number": 1,
      "title": "...",
      "plot_beat": "...",
      "opening_beat": "...",
      "closing_beat": "...",
      "characters": ["Name"],
      "locations": ["Place"],
      "character_descriptions": {{"Name": "desc"}},
      "time_references": [],
      "action_verbs": ["verb"],
      "conflict_keywords": ["word"],
      "raw_text": "full prose paragraph"
    }}
  ]
}}

No markdown, only JSON."""

        max_tokens = 4000

    else:
        episodes_summary = "\n".join([
            f"Ep {ep.get('episode_number')}: {ep.get('title')} — {ep.get('plot_beat', '')[:150]}"
            for ep in body.episodes
        ])
        system = f"""You are an elite TV script consultant for "{body.series_title}".
Episodes: {episodes_summary}
Suggestions: {suggestions_summary}
Answer the user's question as an expert. Be specific, 3-4 sentences.
JSON only: {{"reply": "your answer", "updated_episodes": null}}"""
        max_tokens = 400

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": body.message},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=max_tokens,
        )

        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
        updated = data.get("updated_episodes")

        # Safety merge: if Groq returned fewer episodes, fill gaps with originals
        if updated and len(updated) < len(body.episodes):
            log.warning(f"Groq returned {len(updated)} episodes, expected {len(body.episodes)} — merging")
            updated_map = {ep.get("episode_number"): ep for ep in updated}
            merged = []
            for orig in body.episodes:
                ep_num = orig.get("episode_number")
                if ep_num in updated_map:
                    merged.append({**orig, **updated_map[ep_num]})
                else:
                    merged.append(orig)
            updated = merged

        # ── Rescore if episodes were updated ─────────────────────────────
        updated_pipeline = None
        if updated:
            # Build a pipeline dict from whatever state we have
            pipeline_state = dict(body.full_pipeline) if body.full_pipeline else {}
            pipeline_state["episodes"] = updated
            pipeline_state["series_title"] = body.series_title

            log.info("[Chat] Rescoring updated episodes through pipeline modules...")
            pipeline_state = await rescore_episodes(pipeline_state)

            updated = pipeline_state.get("episodes", updated)
            updated_pipeline = {
                "episodes":            updated,
                "emotional_arc":       pipeline_state.get("emotional_arc", {}),
                "retention_heatmap":   pipeline_state.get("retention_heatmap", []),
                "continuity_issues":   pipeline_state.get("continuity_issues", []),
                "cliffhanger_breakdown": pipeline_state.get("cliffhanger_breakdown", []),
                "suggestions":         pipeline_state.get("suggestions", []),
            }
            log.info("[Chat] Rescore complete ✓")

        return ChatResponse(
            reply=data.get("reply", "Done! Episodes updated and rescored."),
            updated_episodes=updated,
            updated_pipeline=updated_pipeline,
        )

    except Exception as e:
        log.error(f"Chat endpoint error: {e}")
        return ChatResponse(
            reply="I encountered an error. Please try again.",
            updated_episodes=None,
        )
