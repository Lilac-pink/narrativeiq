"""
tests/test_module8.py
Tests for Module 8 — Cliffhanger Scoring Engine
"""

import pytest
from unittest.mock import patch, MagicMock
from models.module1_models import Episode, CliffhangerScore
import json


@pytest.fixture
def sample_episode():
    return Episode(
        episode_number=3,
        title="Static",
        plot_beat=(
            "Inside the bunker, Maya discovers encrypted files linking Director Osei "
            "to the original station. A hidden door reveals a deeper chamber. "
            "Someone has been here recently — the dust is disturbed and a coffee cup is still warm."
        )
    )

MOCK_GPT_CRITERIA_RESPONSE = json.dumps({
    "criteria": [
        {"criterion": "Unresolved question", "pass": True, "reason": "Encrypted files raise unanswered questions"},
        {"criterion": "Emotional stakes raised", "pass": False, "reason": "No direct threat to Maya"},
        {"criterion": "Character in jeopardy", "pass": False, "reason": "Maya is not in immediate danger"},
        {"criterion": "New information revealed", "pass": True, "reason": "Osei connection is a new plot thread"},
        {"criterion": "Time pressure present", "pass": False, "reason": "No deadline established"},
        {"criterion": "Scene ends on action beat", "pass": True, "reason": "Ends on Maya finding a hidden door"},
    ]
})


class TestCliffhangerScoringEngine:

    def test_import(self):
        from pipeline.module8_cliffhanger import score_cliffhangers
        assert callable(score_cliffhangers)

    @patch("pipeline.module8_cliffhanger.openai_client")
    def test_returns_episode_with_cliffhanger_score(self, mock_client, sample_episode):
        from pipeline.module8_cliffhanger import score_episode_cliffhanger
        import asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = MOCK_GPT_CRITERIA_RESPONSE
        mock_client.chat.completions.create.return_value = mock_response

        updated = asyncio.run(score_episode_cliffhanger(sample_episode))
        assert updated.cliffhanger is not None
        assert isinstance(updated.cliffhanger, CliffhangerScore)

    @patch("pipeline.module8_cliffhanger.openai_client")
    def test_score_in_valid_range(self, mock_client, sample_episode):
        from pipeline.module8_cliffhanger import score_episode_cliffhanger
        import asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = MOCK_GPT_CRITERIA_RESPONSE
        mock_client.chat.completions.create.return_value = mock_response

        updated = asyncio.run(score_episode_cliffhanger(sample_episode))
        assert 0.0 <= updated.cliffhanger.score <= 10.0

    @patch("pipeline.module8_cliffhanger.openai_client")
    def test_exactly_six_criteria(self, mock_client, sample_episode):
        from pipeline.module8_cliffhanger import score_episode_cliffhanger
        import asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = MOCK_GPT_CRITERIA_RESPONSE
        mock_client.chat.completions.create.return_value = mock_response

        updated = asyncio.run(score_episode_cliffhanger(sample_episode))
        assert len(updated.cliffhanger.criteria) == 6

    @patch("pipeline.module8_cliffhanger.openai_client")
    def test_all_pass_gives_high_score(self, mock_client, sample_episode):
        from pipeline.module8_cliffhanger import score_episode_cliffhanger
        import asyncio

        all_pass = json.dumps({"criteria": [
            {"criterion": c, "pass": True, "reason": "Strong"}
            for c in ["Unresolved question", "Emotional stakes raised",
                      "Character in jeopardy", "New information revealed",
                      "Time pressure present", "Scene ends on action beat"]
        ]})
        mock_response = MagicMock()
        mock_response.choices[0].message.content = all_pass
        mock_client.chat.completions.create.return_value = mock_response

        updated = asyncio.run(score_episode_cliffhanger(sample_episode))
        assert updated.cliffhanger.score >= 8.0

    @patch("pipeline.module8_cliffhanger.openai_client")
    def test_all_fail_gives_low_score(self, mock_client, sample_episode):
        from pipeline.module8_cliffhanger import score_episode_cliffhanger
        import asyncio

        all_fail = json.dumps({"criteria": [
            {"criterion": c, "pass": False, "reason": "Weak"}
            for c in ["Unresolved question", "Emotional stakes raised",
                      "Character in jeopardy", "New information revealed",
                      "Time pressure present", "Scene ends on action beat"]
        ]})
        mock_response = MagicMock()
        mock_response.choices[0].message.content = all_fail
        mock_client.chat.completions.create.return_value = mock_response

        updated = asyncio.run(score_episode_cliffhanger(sample_episode))
        assert updated.cliffhanger.score <= 2.0

    @patch("pipeline.module8_cliffhanger.openai_client")
    def test_top_level_score_synced(self, mock_client, sample_episode):
        """episode.cliffhanger_score mirrors episode.cliffhanger.score"""
        from pipeline.module8_cliffhanger import score_episode_cliffhanger
        import asyncio

        mock_response = MagicMock()
        mock_response.choices[0].message.content = MOCK_GPT_CRITERIA_RESPONSE
        mock_client.chat.completions.create.return_value = mock_response

        updated = asyncio.run(score_episode_cliffhanger(sample_episode))
        assert updated.cliffhanger_score == updated.cliffhanger.score
