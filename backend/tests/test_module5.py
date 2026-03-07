"""
tests/test_module5.py
Tests for Module 5 — NLP Extractor
"""

import pytest
from models.module1_models import Episode, NLPFeatures


# ─────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────

@pytest.fixture
def sample_episode():
    return Episode(
        episode_number=1,
        title="Dead Air",
        plot_beat=(
            "Maya Chen, a late-night radio operator, picks up a mysterious signal "
            "from Station 7, a government facility that was sealed in 1991. "
            "Director Osei orders her to destroy the recording, but Maya secretly "
            "makes a copy before the signal vanishes at midnight."
        )
    )

@pytest.fixture
def conflict_episode():
    return Episode(
        episode_number=2,
        title="The Ambush",
        plot_beat=(
            "Maya tries to escape the bunker but Director Osei's men ambush her at the exit. "
            "She fights back, kills the guard, and betrays her handler to survive. "
            "The secret dies with the guard unless Maya can expose the conspiracy before dawn."
        )
    )

@pytest.fixture
def episode_list(sample_episode, conflict_episode):
    return [sample_episode, conflict_episode]


# ─────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────

class TestNLPExtractor:

    def test_import(self):
        """Module imports without error."""
        from pipeline.module5_nlp_extractor import extract_nlp_features, extract_from_text
        assert callable(extract_nlp_features)
        assert callable(extract_from_text)

    def test_returns_nlp_features_object(self, sample_episode):
        """extract_from_text returns an NLPFeatures instance."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(sample_episode.plot_beat)
        assert isinstance(result, NLPFeatures)

    def test_extracts_characters(self, sample_episode):
        """Detects named characters in text."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(sample_episode.plot_beat)
        assert len(result.characters) > 0
        names = [c.lower() for c in result.characters]
        assert any("maya" in n for n in names)

    def test_extracts_locations(self, sample_episode):
        """Detects locations in text."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(sample_episode.plot_beat)
        assert isinstance(result.locations, list)

    def test_extracts_time_references(self, sample_episode):
        """Detects time references like '1991' and 'midnight'."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(sample_episode.plot_beat)
        time_text = " ".join(result.time_references).lower()
        assert "1991" in time_text or "midnight" in time_text

    def test_extracts_action_verbs(self, sample_episode):
        """Extracts meaningful action verbs."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(sample_episode.plot_beat)
        assert len(result.action_verbs) > 0

    def test_no_skip_verbs_in_action_verbs(self, sample_episode):
        """Skip verbs like 'be', 'have', 'do' are not in action verbs."""
        from pipeline.module5_nlp_extractor import extract_from_text, SKIP_VERBS
        result = extract_from_text(sample_episode.plot_beat)
        for verb in result.action_verbs:
            assert verb not in SKIP_VERBS

    def test_detects_conflict_keywords(self, conflict_episode):
        """Detects conflict keywords like 'kill', 'betray', 'escape'."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(conflict_episode.plot_beat)
        assert len(result.conflict_keywords) > 0
        assert any(k in result.conflict_keywords for k in ["kill", "escape", "betray", "ambush", "fight"])

    def test_process_episode_attaches_nlp_features(self, sample_episode):
        """process_episode sets nlp_features on the episode."""
        from pipeline.module5_nlp_extractor import process_episode
        updated = process_episode(sample_episode)
        assert updated.nlp_features is not None
        assert isinstance(updated.nlp_features, NLPFeatures)

    def test_process_episode_merges_characters(self):
        """Characters from NLP are merged with existing characters, no duplicates."""
        from pipeline.module5_nlp_extractor import process_episode
        ep = Episode(
            episode_number=1,
            title="Test",
            plot_beat="Maya Chen fights Director Osei at the rooftop.",
            characters=["Maya Chen"]
        )
        updated = process_episode(ep)
        assert updated.characters.count("Maya Chen") == 1

    def test_extract_nlp_features_processes_all_episodes(self, episode_list):
        """Series-level function processes every episode."""
        from pipeline.module5_nlp_extractor import extract_nlp_features
        results = extract_nlp_features(episode_list)
        assert len(results) == len(episode_list)
        for ep in results:
            assert ep.nlp_features is not None

    def test_empty_plot_beat_doesnt_crash(self):
        """Empty plot beat returns empty NLPFeatures without crashing."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text("")
        assert isinstance(result, NLPFeatures)
        assert result.characters == []
        assert result.action_verbs == []

    def test_no_duplicate_characters(self, sample_episode):
        """Characters list contains no duplicates."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(sample_episode.plot_beat)
        assert len(result.characters) == len(set(result.characters))

    def test_no_duplicate_conflict_keywords(self, conflict_episode):
        """Conflict keywords list contains no duplicates."""
        from pipeline.module5_nlp_extractor import extract_from_text
        result = extract_from_text(conflict_episode.plot_beat)
        assert len(result.conflict_keywords) == len(set(result.conflict_keywords))
