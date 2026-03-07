"""
MODULE 2 — NarrativeIQ FastAPI Backend
Includes: Auth, DB persistence, Pipeline job queue, CORS
"""
import asyncio
import sys
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Optional

# ── Load .env FIRST before any other imports ──────────────────────────────
from dotenv import load_dotenv
# Walk up from api/ to backend/ to find the .env file
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)
print(f"[ENV] Loaded from: {_env_path}")
print(f"[ENV] GROQ_API_KEY set: {'Yes' if os.environ.get('GROQ_API_KEY') else 'NO - KEY MISSING'}")

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Make sure backend root is on sys.path ──────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Database ──────────────────────────────────────────────────────────────
from database import init_db

# ── Auth & Story routers ──────────────────────────────────────────────────
from routes.auth_routes import router as auth_router
from routes.story_routes import router as story_router
from routes.chat_routes import router as chat_router

# ── Env ───────────────────────────────────────────────────────────────────
LOVABLE_URL = os.environ.get("LOVABLE_URL", "")

# ── In-memory job store (anonymous pipeline runs) ─────────────────────────
job_store: dict = {}


# ─────────────────────────────────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("NarrativeIQ API v2 starting up...")
    init_db()
    yield
    print("NarrativeIQ API shutting down.")


# ─────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NarrativeIQ — Episodic Intelligence Engine",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(story_router)
app.include_router(chat_router)


# ─────────────────────────────────────────────────────────────────────────
# PIPELINE STUB (replace with real Module 16 when ready)
# ─────────────────────────────────────────────────────────────────────────
async def run_pipeline_stub(pipeline_input) -> dict:
    await asyncio.sleep(2)   # simulate work
    episodes = [
        {
            "episode_number": i + 1,
            "title": f"Episode {i + 1}",
            "plot_beat": "Pipeline not yet connected — this is stub data.",
            "characters": [],
            "locations": [],
            "emotion_score": round(0.3 + 0.6 * (i / max(pipeline_input.target_episodes - 1, 1)), 2),
            "cliffhanger_score": 7.0,
            "continuity_score": 0.85,
            "drop_off_probability": 0.25,
        }
        for i in range(pipeline_input.target_episodes)
    ]
    return {
        "series_title": pipeline_input.series_title,
        "total_episodes": pipeline_input.target_episodes,
        "episodes": episodes,
        "emotional_arc": {
            "ideal_curve": [round(0.3 + 0.65 * i / max(pipeline_input.target_episodes - 1, 1), 2)
                            for i in range(pipeline_input.target_episodes)],
            "actual_curve": [ep["emotion_score"] for ep in episodes],
            "flat_zones": [],
        },
        "cliffhanger_breakdown": [],
        "retention_heatmap": [],
        "continuity_issues": [],
        "suggestions": [],
    }


async def run_pipeline_job(job_id: str, pipeline_input):
    job_store[job_id]["status"] = "running"
    try:
        try:
            from pipeline.module16_orchestrator import run_pipeline
            result = await run_pipeline(
                raw_story=pipeline_input.story_idea,
            )
            # Inject series_title if pipeline didn't set one
            if not result.get("series_title"):
                result["series_title"] = pipeline_input.series_title
            if hasattr(result, "dict"):
                result = result.dict()
        except Exception as pipeline_err:
            print(f"[Pipeline] Module 16 error: {pipeline_err} — falling back to stub")
            result = await run_pipeline_stub(pipeline_input)

        job_store[job_id]["status"] = "complete"
        job_store[job_id]["result"] = result
        job_store[job_id]["completed_at"] = time.time()

        if LOVABLE_URL and not LOVABLE_URL.startswith("https://YOUR"):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.post(LOVABLE_URL, json=result)
            except Exception as e:
                print(f"[Lovable push failed] {e}")
    except Exception as e:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = str(e)
        job_store[job_id]["completed_at"] = time.time()
        print(f"[Pipeline] Job {job_id} failed:\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────
class PipelineInput(BaseModel):
    story_idea: str
    series_title: str
    target_episodes: int = 5


# ─────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "live",
        "timestamp": time.time(),
        "active_jobs": sum(1 for j in job_store.values() if j["status"] == "running"),
        "version": "2.0.0",
    }


@app.post("/api/analyse", status_code=202, tags=["Pipeline"])
async def analyse_anonymous(body: PipelineInput, background_tasks: BackgroundTasks):
    """Anonymous pipeline — results held in memory, not saved to DB."""
    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "started_at": time.time(),
        "completed_at": None,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(run_pipeline_job, job_id, body)
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Pipeline started.",
        "poll_url": f"/api/jobs/{job_id}",
    }


@app.get("/api/jobs/{job_id}", tags=["Pipeline"])
async def job_status(job_id: str):
    if job_id not in job_store:
        raise HTTPException(404, f"Job {job_id} not found.")
    j = job_store[job_id]
    return {
        "job_id": job_id,
        "status": j["status"],
        "started_at": j["started_at"],
        "completed_at": j["completed_at"],
        "error": j["error"],
    }


@app.get("/api/jobs/{job_id}/result", tags=["Pipeline"])
async def job_result(job_id: str):
    if job_id not in job_store:
        raise HTTPException(404, f"Job {job_id} not found.")
    j = job_store[job_id]
    if j["status"] in ("pending", "running"):
        raise HTTPException(425, "Pipeline still running.")
    if j["status"] == "failed":
        raise HTTPException(500, f"Pipeline failed: {j['error']}")
    return j["result"]


@app.delete("/api/jobs/{job_id}", tags=["Pipeline"])
async def delete_job(job_id: str):
    job_store.pop(job_id, None)
    return {"status": "deleted", "job_id": job_id}


# ─────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.module2_api:app", host="0.0.0.0", port=8000, reload=True)
