"""
tests/test_module9.py
Tests for Module 9 — Continuity Auditor
"""

import pytest
from unittest.mock import patch
import numpy as np
from models.module1_models import Episode, ContinuityIssue


@pytest.fixture
def connected_episodes():
    """Episodes with strongly connected transitions."""
    return [
        Episode(episode_number=1, title="Ep1", plot_beat="Maya enters the bunker through the steel door."),
        Episode(episode_number=2, title="Ep2", plot_beat="Inside the bunker Maya walks down the corridor from the steel door."),
        Episode(episode_number=3, title="Ep3", plot_beat="At the end of the corridor Maya finds the encrypted files."),
    ]

@pytest.fixture
def disconnected_episodes():
    """Episodes with a jarring, disconnected transition."""
    return [
        Episode(episode_number=1, title="Ep1", plot_beat="Maya escapes on a motorbike through the desert highway at sunset."),
        Episode(episode_number=2, title="Ep2", plot_beat="In a Paris café Director Osei reads a classified newspaper over espresso."),
        Episode(episode_number=3, title="Ep3", plot_beat="A submarine surfaces near an Arctic research station at midnight."),
    ]


class TestContinuityAuditor:

    def test_import(self):
        from pipeline.module9_continuity import audit_continuity
        assert callable(audit_continuity)

    def test_returns_list(self, connected_episodes):
        from pipeline.module9_continuity import audit_continuity
        issues = audit_continuity(connected_episodes)
        assert isinstance(issues, list)

    def test_returns_n_minus_one_comparisons(self, connected_episodes):
        """For N episodes, there are N-1 transition pairs."""
        from pipeline.module9_continuity import audit_continuity
        issues = audit_continuity(connected_episodes)
        # Issues list contains only flagged ones, but internal comparison count = N-1
        assert len(issues) <= len(connected_episodes) - 1

    def test_continuity_issue_structure(self, disconnected_episodes):
        from pipeline.module9_continuity import audit_continuity
        issues = audit_continuity(disconnected_episodes)
        for issue in issues:
            assert isinstance(issue, ContinuityIssue)
            assert 0.0 <= issue.similarity_score <= 1.0
            assert issue.severity in ("low", "medium", "high")
            assert len(issue.transition) > 0

    def test_disconnected_episodes_flagged(self, disconnected_episodes):
        """Clearly disconnected episodes should produce at least one issue."""
        from pipeline.module9_continuity import audit_continuity
        issues = audit_continuity(disconnected_episodes)
        assert len(issues) >= 1

    def test_similarity_scores_are_floats(self, connected_episodes):
        from pipeline.module9_continuity import audit_continuity
        issues = audit_continuity(connected_episodes)
        for issue in issues:
            assert isinstance(issue.similarity_score, float)

    def test_transition_label_format(self, disconnected_episodes):
        """Transition label should contain episode numbers like 'Episode 1 → Episode 2'."""
        from pipeline.module9_continuity import audit_continuity
        issues = audit_continuity(disconnected_episodes)
        for issue in issues:
            assert "→" in issue.transition or "->" in issue.transition

    def test_single_episode_returns_no_issues(self):
        """Can't audit continuity with only one episode."""
        from pipeline.module9_continuity import audit_continuity
        episodes = [Episode(episode_number=1, title="Solo", plot_beat="Lone episode with no transitions.")]
        issues = audit_continuity(episodes)
        assert issues == []

    def test_episodes_updated_with_continuity_score(self, disconnected_episodes):
        """Each episode (except last) should have continuity_score set after audit."""
        from pipeline.module9_continuity import audit_continuity
        audit_continuity(disconnected_episodes)
        for ep in disconnected_episodes[:-1]:
            assert ep.continuity_score is not None
