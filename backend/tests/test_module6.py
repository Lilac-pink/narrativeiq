"""
tests/test_module6.py
Tests for Module 6 — Emotional Arc Analyser
"""

import pytest
from unittest.mock import patch, MagicMock
from models.module1_models import Episode, EmotionAnalysis, EmotionalArc


@pytest.fixture
def five_episodes():
    plots = [
        "A quiet discovery in the radio tower.",
        "Maya races to the bunker in a panic, terrified of what she will find.",
        "She searches the bunker slowly, finding nothing new.",
        "Director Osei confronts Maya with explosive rage and threatens her life.",
        "Maya broadcasts the secret to the world in a final act of defiance.",
    ]
    return [
        Episode(episode_number=i+1, title=f"Ep {i+1}", plot_beat=p)
        for i, p in enumerate(plots)
    ]


class TestEmotionalArcAnalyser:

    def test_import(self):
        from pipeline.module6_emotional_arc import analyse_emotional_arc
        assert callable(analyse_emotional_arc)

    @patch("pipeline.module6_emotional_arc.sentiment_pipeline")
    def test_returns_episodes_with_emotion_scores(self, mock_pipe, five_episodes):
        from pipeline.module6_emotional_arc import analyse_emotional_arc
        mock_pipe.return_value = [{"label": "POSITIVE", "score": 0.85}]
        episodes, arc = analyse_emotional_arc(five_episodes, ideal_curve=[0.3,0.5,0.65,0.8,0.95])
        for ep in episodes:
            assert ep.emotion_score is not None
            assert 0.0 <= ep.emotion_score <= 1.0

    @patch("pipeline.module6_emotional_arc.sentiment_pipeline")
    def test_returns_emotional_arc_object(self, mock_pipe, five_episodes):
        from pipeline.module6_emotional_arc import analyse_emotional_arc
        mock_pipe.return_value = [{"label": "POSITIVE", "score": 0.7}]
        episodes, arc = analyse_emotional_arc(five_episodes, ideal_curve=[0.3,0.5,0.65,0.8,0.95])
        assert isinstance(arc, EmotionalArc)

    @patch("pipeline.module6_emotional_arc.sentiment_pipeline")
    def test_actual_curve_length_matches_episodes(self, mock_pipe, five_episodes):
        from pipeline.module6_emotional_arc import analyse_emotional_arc
        mock_pipe.return_value = [{"label": "POSITIVE", "score": 0.6}]
        episodes, arc = analyse_emotional_arc(five_episodes, ideal_curve=[0.3,0.5,0.65,0.8,0.95])
        assert len(arc.actual_curve) == len(five_episodes)

    @patch("pipeline.module6_emotional_arc.sentiment_pipeline")
    def test_flat_zone_flagged_correctly(self, mock_pipe, five_episodes):
        """Episode 3 should be flat if its score barely changes from episode 2."""
        from pipeline.module6_emotional_arc import analyse_emotional_arc

        # Return same score for all — all should be flat except first
        mock_pipe.return_value = [{"label": "POSITIVE", "score": 0.6}]
        episodes, arc = analyse_emotional_arc(five_episodes, ideal_curve=[0.3,0.5,0.65,0.8,0.95])
        # At least some flat zones should be detected when scores are identical
        assert len(arc.flat_zones) > 0

    @patch("pipeline.module6_emotional_arc.sentiment_pipeline")
    def test_emotion_score_attached_to_episode(self, mock_pipe, five_episodes):
        from pipeline.module6_emotional_arc import analyse_emotional_arc
        mock_pipe.return_value = [{"label": "NEGATIVE", "score": 0.9}]
        episodes, arc = analyse_emotional_arc(five_episodes, ideal_curve=[0.3,0.5,0.65,0.8,0.95])
        for ep in episodes:
            assert ep.emotion_analysis is not None
            assert isinstance(ep.emotion_analysis, EmotionAnalysis)
