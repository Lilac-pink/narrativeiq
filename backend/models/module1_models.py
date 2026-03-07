"""
MODULE 1 — Episode Data Model
NarrativeIQ Episodic Intelligence Engine
All modules read from and write to these schemas.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


# ─────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class StoryType(str, Enum):
    THRILLER = "thriller"
    ROMANCE = "romance"
    MYSTERY = "mystery"
    DRAMA = "drama"
    HORROR = "horror"
    COMEDY = "comedy"
    SCI_FI = "sci_fi"
    FANTASY = "fantasy"
    CRIME = "crime"
    ADVENTURE = "adventure"


# ─────────────────────────────────────────
# MODULE 5 — NLP Extractor Output
# ─────────────────────────────────────────

class NLPFeatures(BaseModel):
    characters: List[str] = Field(default_factory=list, description="Named characters extracted by spaCy")
    locations: List[str] = Field(default_factory=list, description="Locations extracted by spaCy")
    time_references: List[str] = Field(default_factory=list, description="Time references e.g. 'next morning', '1991'")
    action_verbs: List[str] = Field(default_factory=list, description="Key action verbs extracted")
    conflict_keywords: List[str] = Field(default_factory=list, description="Conflict-related keywords")


# ─────────────────────────────────────────
# MODULE 6 — Emotional Arc Analyser Output
# ─────────────────────────────────────────

class EmotionAnalysis(BaseModel):
    emotion_score: float = Field(..., ge=0.0, le=1.0, description="HuggingFace sentiment intensity score 0–1")
    is_flat_zone: bool = Field(default=False, description="True if score delta from previous episode < 0.05")
    delta_from_previous: Optional[float] = Field(default=None, description="Change in emotion score from prior episode")


# ─────────────────────────────────────────
# MODULE 8 — Cliffhanger Scoring Engine Output
# ─────────────────────────────────────────

class CliffhangerCriterion(BaseModel):
    criterion: str = Field(..., description="Name of the scoring criterion")
    passed: bool = Field(..., description="GPT yes/no answer")
    weight: float = Field(..., description="Weight of this criterion in final score")
    reason: str = Field(..., description="One-line GPT explanation")

class CliffhangerScore(BaseModel):
    score: float = Field(..., ge=0.0, le=10.0, description="Weighted cliffhanger score out of 10")
    criteria: List[CliffhangerCriterion] = Field(default_factory=list)


# ─────────────────────────────────────────
# MODULE 9 — Continuity Auditor Output
# ─────────────────────────────────────────

class ContinuityIssue(BaseModel):
    transition: str = Field(..., description="e.g. 'Episode 2 → Episode 3'")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="MiniLM cosine similarity score")
    severity: Severity
    issue: str = Field(..., description="Plain-language description of the continuity gap")


# ─────────────────────────────────────────
# MODULE 10 — Character Consistency Checker Output
# ─────────────────────────────────────────

class CharacterInconsistency(BaseModel):
    character_name: str
    episode_a: int
    episode_b: int
    trait_a: str = Field(..., description="Trait description in episode A")
    trait_b: str = Field(..., description="Contradicting trait description in episode B")
    outlier_score: float = Field(..., description="Z-score or isolation forest anomaly score")


# ─────────────────────────────────────────
# MODULE 12 — Drop-off Probability Predictor Output
# ─────────────────────────────────────────

class DropOffPrediction(BaseModel):
    drop_off_probability: float = Field(..., ge=0.0, le=1.0, description="GradientBoosting model output")
    risk_level: RiskLevel
    feature_vector: Dict[str, float] = Field(
        default_factory=dict,
        description="Input features used by the model: emotion_score, cliffhanger_score, continuity_score, arc_deviation, is_flat_zone"
    )


# ─────────────────────────────────────────
# MODULE 13 — Retention Risk Heatmap Output
# ─────────────────────────────────────────

class RetentionBlock(BaseModel):
    time_block: str = Field(..., description="e.g. '0–15s', '15–30s'")
    risk_level: RiskLevel
    reason: str = Field(..., description="Heuristic rule that fired")

class RetentionHeatmap(BaseModel):
    episode_number: int
    blocks: List[RetentionBlock] = Field(default_factory=list, description="6 blocks of 15s each")


# ─────────────────────────────────────────
# MODULE 14 — Optimisation Suggestion Engine Output
# ─────────────────────────────────────────

class Suggestion(BaseModel):
    priority: int = Field(..., description="Rank order, 1 = highest impact")
    episode: int
    category: str = Field(..., description="e.g. Pacing, Cliffhanger, Continuity, Character, Emotional Arc")
    suggestion: str = Field(..., description="Specific actionable improvement from GPT")
    impact_score: float = Field(..., ge=0.0, le=10.0)


# ─────────────────────────────────────────
# MODULE 15 — Score Explainer Output
# ─────────────────────────────────────────

class ScoreExplanation(BaseModel):
    score_name: str = Field(..., description="e.g. 'cliffhanger_score', 'drop_off_probability'")
    raw_value: float
    explanation: str = Field(..., description="1–2 sentence plain-English creator-friendly summary")


# ─────────────────────────────────────────
# CORE EPISODE MODEL
# ─────────────────────────────────────────

class Episode(BaseModel):
    # Identity
    episode_number: int = Field(..., ge=1)
    title: str
    plot_beat: str = Field(..., description="One paragraph description of what happens in this episode")

    # Module 5 — NLP
    nlp_features: Optional[NLPFeatures] = None

    # Convenience top-level fields (populated from NLP for frontend compatibility)
    characters: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)

    # Module 6 — Emotion
    emotion_analysis: Optional[EmotionAnalysis] = None
    emotion_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Module 7 — Arc Deviation
    arc_deviation_score: Optional[float] = Field(default=None, description="MAE gap from ideal curve at this episode")

    # Module 8 — Cliffhanger
    cliffhanger: Optional[CliffhangerScore] = None
    cliffhanger_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)

    # Module 9 — Continuity (outbound — transition TO next episode)
    continuity_to_next: Optional[ContinuityIssue] = None
    continuity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Module 10 — Character consistency issues in this episode
    character_inconsistencies: List[CharacterInconsistency] = Field(default_factory=list)

    # Module 12 — Drop-off
    drop_off: Optional[DropOffPrediction] = None
    drop_off_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Module 13 — Retention heatmap
    retention_heatmap: Optional[RetentionHeatmap] = None

    # Module 15 — Score explanations for this episode
    score_explanations: List[ScoreExplanation] = Field(default_factory=list)


# ─────────────────────────────────────────
# MODULE 4 — Narrative DNA Classifier Output
# ─────────────────────────────────────────

class NarrativeDNA(BaseModel):
    story_type: StoryType
    ideal_curve: List[float] = Field(
        ...,
        description="Ideal emotion intensity value per episode for this story type"
    )
    arc_template_name: str = Field(..., description="e.g. 'Rising Tension', 'Hero Journey', 'Slow Burn'")
    reasoning: str = Field(..., description="GPT explanation for why this story type was assigned")


# ─────────────────────────────────────────
# MODULE 6 — Series-level Emotional Arc
# ─────────────────────────────────────────

class EmotionalArc(BaseModel):
    actual_curve: List[float] = Field(..., description="Emotion scores across all episodes in order")
    ideal_curve: List[float] = Field(..., description="Ideal curve from Narrative DNA Classifier")
    flat_zones: List[int] = Field(default_factory=list, description="Episode numbers flagged as flat zones")
    overall_deviation_score: Optional[float] = Field(default=None, description="Series-level MAE from Module 7")


# ─────────────────────────────────────────
# TOP-LEVEL PIPELINE OUTPUT
# This is what Module 16 assembles and POSTs to Lovable
# ─────────────────────────────────────────

class PipelineOutput(BaseModel):
    # Series metadata
    series_title: str
    total_episodes: int

    # All episodes with all module outputs attached
    episodes: List[Episode]

    # Series-level outputs
    narrative_dna: Optional[NarrativeDNA] = None
    emotional_arc: Optional[EmotionalArc] = None
    continuity_issues: List[ContinuityIssue] = Field(default_factory=list)
    character_inconsistencies: List[CharacterInconsistency] = Field(default_factory=list)

    # Cliffhanger breakdown (episodes with notable scores)
    cliffhanger_breakdown: List[dict] = Field(default_factory=list, description="Flattened for frontend rendering")

    # Retention heatmap (all episodes)
    retention_heatmap: List[RetentionHeatmap] = Field(default_factory=list)

    # Suggestions ranked by impact
    suggestions: List[Suggestion] = Field(default_factory=list)

    # Score explanations across all episodes
    score_explanations: List[ScoreExplanation] = Field(default_factory=list)

    class Config:
        use_enum_values = True


# ─────────────────────────────────────────
# PIPELINE INPUT
# What the user sends to kick off the pipeline
# ─────────────────────────────────────────

class PipelineInput(BaseModel):
    story_idea: str = Field(..., description="Raw story idea or prompt from the creator")
    series_title: str = Field(..., description="Title of the series")
    target_episodes: int = Field(default=5, ge=2, le=12, description="How many episodes to decompose into")
