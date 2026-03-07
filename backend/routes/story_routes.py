"""
STORY ROUTES
NarrativeIQ — /api/story/* endpoints
POST /api/story/analyse      — submit story (auth required)
GET  /api/story/history      — user's past stories (auth required)
GET  /api/story/:id          — get a specific story + results
GET  /api/story/:id/result   — get full pipeline output
DELETE /api/story/:id        — delete a story
"""

import json
import time
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from database import get_db
from models.auth_models import (
    UserDB, StoryDB, EpisodeDB, AnalysisDB,
    StoryCreateRequest, StoryResponse, StoryHistoryItem
)
from auth_utils import get_current_user

router = APIRouter(prefix="/api/story", tags=["Story"])

# In-memory job store (shared with module2_api)
# Import from module2 when wired together
job_store: dict = {}


# ─────────────────────────────────────────
# SUBMIT STORY FOR ANALYSIS
# ─────────────────────────────────────────

@router.post("/analyse", response_model=StoryResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyse_story(
    body: StoryCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """
    Submit a story for full pipeline analysis.
    Saves the story to the database immediately.
    Runs the pipeline in the background.
    Returns story_id for polling.
    """
    import uuid

    # Save story to DB immediately
    story = StoryDB(
        user_id=current_user.id,
        series_title=body.series_title,
        story_idea=body.story_idea,
        episode_count=body.target_episodes,
        status="pending",
        job_id=str(uuid.uuid4())
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    # Run pipeline in background
    background_tasks.add_task(
        _run_pipeline_and_save,
        story_id=story.id,
        job_id=story.job_id,
        body=body,
        user_id=current_user.id
    )

    return story


async def _run_pipeline_and_save(
    story_id: str,
    job_id: str,
    body: StoryCreateRequest,
    user_id: str
):
    """
    Background task: runs the pipeline then saves results to DB.
    """
    from database import SessionLocal
    db = SessionLocal()

    try:
        # Update status to running
        story = db.query(StoryDB).filter(StoryDB.id == story_id).first()
        if not story:
            return
        story.status = "running"
        db.commit()

        # ── Run pipeline (swap stub for real Module 16 when ready) ──
        try:
            from pipeline.module16_orchestrator import run_pipeline
            from models.auth_models import StoryCreateRequest as SCR
            # Build PipelineInput
            from models.module1_models import PipelineInput
            pipeline_input = PipelineInput(
                story_idea=body.story_idea,
                series_title=body.series_title,
                target_episodes=body.target_episodes
            )
            result = await run_pipeline(pipeline_input)
            result_dict = result if isinstance(result, dict) else result.dict()
        except Exception as e:
            print(f"[Story Routes] Pipeline error: {e} — using stub result")
            result_dict = _stub_result(body)

        # ── Save episodes to DB ──
        for ep in result_dict.get("episodes", []):
            episode = EpisodeDB(
                story_id=story_id,
                episode_number=ep.get("episode_number", 0),
                title=ep.get("title", ""),
                plot_beat=ep.get("plot_beat", ""),
                emotion_score=ep.get("emotion_score"),
                cliffhanger_score=ep.get("cliffhanger_score"),
                continuity_score=ep.get("continuity_score"),
                drop_off_probability=ep.get("drop_off_probability")
            )
            db.add(episode)

        # ── Save analysis summary to DB ──
        episodes = result_dict.get("episodes", [])
        arc = result_dict.get("emotional_arc", {})
        issues = result_dict.get("continuity_issues", [])
        suggestions = result_dict.get("suggestions", [])

        avg_cliff = (
            sum(ep.get("cliffhanger_score", 0) for ep in episodes) / len(episodes)
            if episodes else 0
        )
        avg_drop = (
            sum(ep.get("drop_off_probability", 0) for ep in episodes) / len(episodes)
            if episodes else 0
        )

        analysis = AnalysisDB(
            story_id=story_id,
            overall_arc_score=arc.get("overall_deviation_score"),
            avg_cliffhanger=round(avg_cliff, 3),
            avg_drop_off=round(avg_drop, 3),
            continuity_issues=len(issues),
            flat_zones=json.dumps(arc.get("flat_zones", [])),
            suggestions_json=json.dumps(result_dict)  # full pipeline output
        )
        db.add(analysis)

        # ── Mark complete ──
        story.status = "complete"
        story.completed_at = datetime.utcnow()
        db.commit()

        print(f"[Story Routes] Story {story_id} saved to DB successfully.")

    except Exception as e:
        print(f"[Story Routes] Failed to save story {story_id}: {e}")
        story = db.query(StoryDB).filter(StoryDB.id == story_id).first()
        if story:
            story.status = "failed"
            db.commit()
    finally:
        db.close()


def _stub_result(body: StoryCreateRequest) -> dict:
    """Fallback stub result if pipeline isn't connected yet."""
    episodes = []
    for i in range(1, body.target_episodes + 1):
        episodes.append({
            "episode_number": i,
            "title": f"Episode {i}",
            "plot_beat": f"Plot beat for episode {i} of {body.series_title}.",
            "characters": [],
            "locations": [],
            "emotion_score": round(0.3 + (0.6 * i / body.target_episodes), 2),
            "cliffhanger_score": 7.0,
            "continuity_score": 0.85,
            "drop_off_probability": 0.25
        })
    return {
        "series_title": body.series_title,
        "total_episodes": body.target_episodes,
        "episodes": episodes,
        "emotional_arc": {
            "ideal_curve": [round(0.3 + 0.65 * i / (body.target_episodes - 1), 2) for i in range(body.target_episodes)],
            "actual_curve": [ep["emotion_score"] for ep in episodes],
            "flat_zones": []
        },
        "cliffhanger_breakdown": [],
        "retention_heatmap": [],
        "continuity_issues": [],
        "suggestions": []
    }


# ─────────────────────────────────────────
# STORY HISTORY
# ─────────────────────────────────────────

@router.get("/history", response_model=List[StoryHistoryItem])
def get_history(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """
    Returns all stories submitted by the current user.
    Ordered by most recent first.
    """
    stories = (
        db.query(StoryDB)
        .filter(StoryDB.user_id == current_user.id)
        .order_by(StoryDB.created_at.desc())
        .all()
    )
    return stories


# ─────────────────────────────────────────
# GET SINGLE STORY STATUS
# ─────────────────────────────────────────

@router.get("/{story_id}", response_model=StoryResponse)
def get_story(
    story_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """
    Get a story's metadata and current status.
    Poll this after submitting a story.
    """
    story = db.query(StoryDB).filter(
        StoryDB.id == story_id,
        StoryDB.user_id == current_user.id
    ).first()

    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")

    return story


# ─────────────────────────────────────────
# GET FULL PIPELINE RESULT
# ─────────────────────────────────────────

@router.get("/{story_id}/result")
def get_story_result(
    story_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """
    Returns the full pipeline JSON output for a completed story.
    """
    story = db.query(StoryDB).filter(
        StoryDB.id == story_id,
        StoryDB.user_id == current_user.id
    ).first()

    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")

    if story.status in ("pending", "running"):
        raise HTTPException(status_code=425, detail="Pipeline still running. Try again shortly.")

    if story.status == "failed":
        raise HTTPException(status_code=500, detail="Pipeline failed for this story.")

    analysis = db.query(AnalysisDB).filter(AnalysisDB.story_id == story_id).first()
    if not analysis or not analysis.suggestions_json:
        raise HTTPException(status_code=404, detail="No results found for this story.")

    return json.loads(analysis.suggestions_json)


# ─────────────────────────────────────────
# DELETE STORY
# ─────────────────────────────────────────

@router.delete("/{story_id}")
def delete_story(
    story_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """Delete a story and all its related data."""
    story = db.query(StoryDB).filter(
        StoryDB.id == story_id,
        StoryDB.user_id == current_user.id
    ).first()

    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")

    db.delete(story)
    db.commit()
    return {"status": "deleted", "story_id": story_id}
