"""
tests/test_pipeline.py
Integration tests for the full pipeline — Module 16 Orchestrator
Tests the complete flow from PipelineInput → PipelineOutput
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from models.module1_models import PipelineInput, PipelineOutput, Episode
import json


# ─────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────

@pytest.fixture
def sample_input():
    return PipelineInput(
        story_idea="A radio operator discovers a government conspiracy hidden in a 30-year-old signal.",
        series_title="The Forgotten Signal",
        target_episodes=3
    )

@pytest.fixture
def mock_episodes():
    return [
        Episode(episode_number=1, title="Dead Air", plot_beat="Maya picks up the signal at midnight."),
        Episode(episode_number=2, title="Interference", plot_beat="Maya traces the signal to a sealed bunker."),
        Episode(episode_number=3, title="Static", plot_beat="Maya discovers encrypted files inside the bunker."),
    ]


# ─────────────────────────────────────────
# PIPELINE OUTPUT SCHEMA TESTS
# ─────────────────────────────────────────

class TestPipelineOutput:

    def test_pipeline_output_schema(self, mock_episodes):
        """PipelineOutput can be instantiated with valid data."""
        output = PipelineOutput(
            series_title="The Forgotten Signal",
            total_episodes=3,
            episodes=mock_episodes
        )
        assert output.series_title == "The Forgotten Signal"
        assert output.total_episodes == 3
        assert len(output.episodes) == 3

    def test_pipeline_output_serialises_to_json(self, mock_episodes):
        """PipelineOutput serialises to JSON without error."""
        output = PipelineOutput(
            series_title="Test Series",
            total_episodes=3,
            episodes=mock_episodes
        )
        json_str = output.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["series_title"] == "Test Series"
        assert len(parsed["episodes"]) == 3

    def test_pipeline_output_has_all_top_level_fields(self, mock_episodes):
        """All required top-level fields exist on PipelineOutput."""
        output = PipelineOutput(
            series_title="Test",
            total_episodes=3,
            episodes=mock_episodes
        )
        assert hasattr(output, "episodes")
        assert hasattr(output, "emotional_arc")
        assert hasattr(output, "continuity_issues")
        assert hasattr(output, "suggestions")
        assert hasattr(output, "cliffhanger_breakdown")
        assert hasattr(output, "retention_heatmap")


# ─────────────────────────────────────────
# PIPELINE INPUT VALIDATION TESTS
# ─────────────────────────────────────────

class TestPipelineInput:

    def test_valid_input(self):
        inp = PipelineInput(
            story_idea="A mystery unfolds.",
            series_title="Mystery Show",
            target_episodes=5
        )
        assert inp.target_episodes == 5

    def test_target_episodes_minimum(self):
        with pytest.raises(Exception):
            PipelineInput(story_idea="x", series_title="x", target_episodes=1)

    def test_target_episodes_maximum(self):
        with pytest.raises(Exception):
            PipelineInput(story_idea="x", series_title="x", target_episodes=13)

    def test_default_target_episodes(self):
        inp = PipelineInput(story_idea="A story.", series_title="My Show")
        assert inp.target_episodes == 5


# ─────────────────────────────────────────
# ORCHESTRATOR INTEGRATION TESTS
# ─────────────────────────────────────────

class TestOrchestrator:

    def test_import(self):
        from pipeline.module16_orchestrator import run_pipeline
        assert callable(run_pipeline)

    @pytest.mark.asyncio
    @patch("pipeline.module16_orchestrator.run_story_decomposer", new_callable=AsyncMock)
    @patch("pipeline.module16_orchestrator.run_narrative_dna", new_callable=AsyncMock)
    async def test_run_pipeline_returns_pipeline_output(
        self, mock_dna, mock_decompose, sample_input, mock_episodes
    ):
        from pipeline.module16_orchestrator import run_pipeline
        from models.module1_models import NarrativeDNA, StoryType, EmotionalArc

        mock_decompose.return_value = mock_episodes
        mock_dna.return_value = NarrativeDNA(
            story_type=StoryType.THRILLER,
            ideal_curve=[0.3, 0.6, 0.9],
            arc_template_name="Rising Tension",
            reasoning="Classic thriller arc"
        )

        result = await run_pipeline(sample_input)
        assert isinstance(result, PipelineOutput)

    @pytest.mark.asyncio
    @patch("pipeline.module16_orchestrator.run_story_decomposer", new_callable=AsyncMock)
    @patch("pipeline.module16_orchestrator.run_narrative_dna", new_callable=AsyncMock)
    async def test_output_episode_count_matches_input(
        self, mock_dna, mock_decompose, sample_input, mock_episodes
    ):
        from pipeline.module16_orchestrator import run_pipeline
        from models.module1_models import NarrativeDNA, StoryType

        mock_decompose.return_value = mock_episodes
        mock_dna.return_value = NarrativeDNA(
            story_type=StoryType.THRILLER,
            ideal_curve=[0.3, 0.6, 0.9],
            arc_template_name="Rising Tension",
            reasoning="Classic thriller arc"
        )

        result = await run_pipeline(sample_input)
        assert len(result.episodes) == len(mock_episodes)

    @pytest.mark.asyncio
    @patch("pipeline.module16_orchestrator.run_story_decomposer", new_callable=AsyncMock)
    async def test_pipeline_handles_decomposer_failure(self, mock_decompose, sample_input):
        from pipeline.module16_orchestrator import run_pipeline

        mock_decompose.side_effect = Exception("GPT API timeout")

        with pytest.raises(Exception, match="GPT API timeout"):
            await run_pipeline(sample_input)


# ─────────────────────────────────────────
# API ENDPOINT INTEGRATION TESTS
# ─────────────────────────────────────────

class TestAPIEndpoints:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.module2_api import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "live"

    def test_analyse_endpoint_returns_202(self, client):
        response = client.post("/api/analyse", json={
            "story_idea": "A spy discovers a double agent in her own team.",
            "series_title": "Double Cross",
            "target_episodes": 5
        })
        assert response.status_code == 202

    def test_analyse_response_has_job_id(self, client):
        response = client.post("/api/analyse", json={
            "story_idea": "A detective solves an impossible cold case.",
            "series_title": "Cold Case",
            "target_episodes": 4
        })
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0

    def test_job_status_endpoint(self, client):
        post = client.post("/api/analyse", json={
            "story_idea": "Test story.",
            "series_title": "Test",
            "target_episodes": 2
        })
        job_id = post.json()["job_id"]
        status_response = client.get(f"/api/jobs/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] in ("pending", "running", "complete", "failed")

    def test_unknown_job_returns_404(self, client):
        response = client.get("/api/jobs/nonexistent-job-id-123")
        assert response.status_code == 404

    def test_list_jobs_endpoint(self, client):
        response = client.get("/api/jobs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
