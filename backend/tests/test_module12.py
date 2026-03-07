"""
tests/test_module12.py
Tests for Module 12 — Drop-off Probability Predictor
"""

import pytest
import os
from models.module1_models import Episode, DropOffPrediction


MODEL_PATH = "ml/trained_model.joblib"


@pytest.fixture
def scored_episode():
    ep = Episode(episode_number=1, title="Dead Air", plot_beat="Maya picks up a mysterious signal.")
    ep.emotion_score = 0.42
    ep.cliffhanger_score = 7.2
    ep.continuity_score = 0.91
    ep.arc_deviation_score = 0.1
    ep.emotion_analysis = type("obj", (object,), {"is_flat_zone": False})()
    return ep

@pytest.fixture
def high_risk_episode():
    ep = Episode(episode_number=3, title="Static", plot_beat="Slow episode with no tension.")
    ep.emotion_score = 0.1
    ep.cliffhanger_score = 1.5
    ep.continuity_score = 0.3
    ep.arc_deviation_score = 0.9
    ep.emotion_analysis = type("obj", (object,), {"is_flat_zone": True})()
    return ep

@pytest.fixture
def low_risk_episode():
    ep = Episode(episode_number=5, title="Broadcast", plot_beat="Explosive finale.")
    ep.emotion_score = 0.95
    ep.cliffhanger_score = 9.5
    ep.continuity_score = 0.95
    ep.arc_deviation_score = 0.05
    ep.emotion_analysis = type("obj", (object,), {"is_flat_zone": False})()
    return ep


class TestDropOffPredictor:

    def test_model_file_exists(self):
        """Trained model file must exist before running predictions."""
        assert os.path.exists(MODEL_PATH), (
            f"Model not found at {MODEL_PATH}. Run: python ml/module11_synthetic_data.py"
        )

    def test_import(self):
        from pipeline.module12_dropoff_predictor import predict_drop_off
        assert callable(predict_drop_off)

    def test_returns_episode_with_drop_off(self, scored_episode):
        from pipeline.module12_dropoff_predictor import predict_drop_off
        updated = predict_drop_off(scored_episode)
        assert updated.drop_off is not None
        assert isinstance(updated.drop_off, DropOffPrediction)

    def test_probability_in_valid_range(self, scored_episode):
        from pipeline.module12_dropoff_predictor import predict_drop_off
        updated = predict_drop_off(scored_episode)
        assert 0.0 <= updated.drop_off_probability <= 1.0

    def test_risk_level_is_valid(self, scored_episode):
        from pipeline.module12_dropoff_predictor import predict_drop_off
        updated = predict_drop_off(scored_episode)
        assert updated.drop_off.risk_level in ("low", "medium", "high")

    def test_high_risk_episode_has_higher_probability(self, high_risk_episode, low_risk_episode):
        from pipeline.module12_dropoff_predictor import predict_drop_off
        high = predict_drop_off(high_risk_episode)
        low = predict_drop_off(low_risk_episode)
        assert high.drop_off_probability > low.drop_off_probability

    def test_feature_vector_populated(self, scored_episode):
        from pipeline.module12_dropoff_predictor import predict_drop_off
        updated = predict_drop_off(scored_episode)
        fv = updated.drop_off.feature_vector
        assert "emotion_score" in fv
        assert "cliffhanger_score" in fv
        assert "continuity_score" in fv
        assert "arc_deviation" in fv
        assert "is_flat_zone" in fv

    def test_top_level_probability_synced(self, scored_episode):
        from pipeline.module12_dropoff_predictor import predict_drop_off
        updated = predict_drop_off(scored_episode)
        assert updated.drop_off_probability == updated.drop_off.drop_off_probability

    def test_missing_scores_handled_gracefully(self):
        """Episode with None scores should not crash — use defaults."""
        from pipeline.module12_dropoff_predictor import predict_drop_off
        ep = Episode(episode_number=1, title="Empty", plot_beat="Nothing here.")
        # All scores are None
        updated = predict_drop_off(ep)
        assert updated.drop_off_probability is not None
