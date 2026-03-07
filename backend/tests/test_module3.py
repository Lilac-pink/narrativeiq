"""
tests/test_module3.py
Tests for Module 3 — Story Decomposer
"""

import pytest
from unittest.mock import patch, MagicMock
from models.module1_models import PipelineInput, Episode


# ─────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────

@pytest.fixture
def sample_input():
    return PipelineInput(
        story_idea="A radio operator picks up a signal from a government station sealed 30 years ago. She traces the signal to a bunker and discovers the government's darkest secret.",
        series_title="The Forgotten Signal",
        target_episodes=5
    )

MOCK_GPT_RESPONSE = {
    "episodes": [
        {"episode_number": 1, "title": "Dead Air", "plot_beat": "Maya picks up the mysterious signal.", "characters": ["Maya Chen"], "locations": ["Radio Tower 7"]},
        {"episode_number": 2, "title": "Interference", "plot_beat": "Maya traces coordinates to a bunker.", "characters": ["Maya Chen", "Dr. Reeves"], "locations": ["Bunker Entrance"]},
        {"episode_number": 3, "title": "Static", "plot_beat": "Inside the bunker, Maya finds encrypted files.", "characters": ["Maya Chen"], "locations": ["Bunker Interior"]},
        {"episode_number": 4, "title": "Frequency", "plot_beat": "Director Osei confronts Maya.", "characters": ["Maya Chen", "Director Osei"], "locations": ["Government Building"]},
        {"episode_number": 5, "title": "Broadcast", "plot_beat": "Maya must choose to expose or silence the AI.", "characters": ["Maya Chen"], "locations": ["Radio Tower 7"]},
    ]
}


# ─────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────

class TestStoryDecomposer:

    def test_import(self):
        """Module imports without error."""
        from pipeline.module3_story_decomposer import decompose_story
        assert callable(decompose_story)

    @patch("pipeline.module3_story_decomposer.openai_client")
    def test_returns_correct_episode_count(self, mock_client, sample_input):
        """Returns exactly target_episodes episodes."""
        from pipeline.module3_story_decomposer import decompose_story
        import json

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(MOCK_GPT_RESPONSE)
        mock_client.chat.completions.create.return_value = mock_response

        import asyncio
        episodes = asyncio.run(decompose_story(sample_input))

        assert len(episodes) == sample_input.target_episodes

    @patch("pipeline.module3_story_decomposer.openai_client")
    def test_episodes_are_episode_objects(self, mock_client, sample_input):
        """All returned items are Episode instances."""
        from pipeline.module3_story_decomposer import decompose_story
        import json, asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(MOCK_GPT_RESPONSE)
        mock_client.chat.completions.create.return_value = mock_response

        episodes = asyncio.run(decompose_story(sample_input))
        for ep in episodes:
            assert isinstance(ep, Episode)

    @patch("pipeline.module3_story_decomposer.openai_client")
    def test_episode_numbers_sequential(self, mock_client, sample_input):
        """Episode numbers start at 1 and are sequential."""
        from pipeline.module3_story_decomposer import decompose_story
        import json, asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(MOCK_GPT_RESPONSE)
        mock_client.chat.completions.create.return_value = mock_response

        episodes = asyncio.run(decompose_story(sample_input))
        numbers = [ep.episode_number for ep in episodes]
        assert numbers == list(range(1, sample_input.target_episodes + 1))

    @patch("pipeline.module3_story_decomposer.openai_client")
    def test_episodes_have_titles_and_plot_beats(self, mock_client, sample_input):
        """Every episode has a non-empty title and plot_beat."""
        from pipeline.module3_story_decomposer import decompose_story
        import json, asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(MOCK_GPT_RESPONSE)
        mock_client.chat.completions.create.return_value = mock_response

        episodes = asyncio.run(decompose_story(sample_input))
        for ep in episodes:
            assert ep.title and len(ep.title) > 0
            assert ep.plot_beat and len(ep.plot_beat) > 0

    @patch("pipeline.module3_story_decomposer.openai_client")
    def test_handles_malformed_gpt_response(self, mock_client, sample_input):
        """Raises ValueError on malformed GPT JSON."""
        from pipeline.module3_story_decomposer import decompose_story
        import asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "not valid json {{{"
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises((ValueError, Exception)):
            asyncio.run(decompose_story(sample_input))
