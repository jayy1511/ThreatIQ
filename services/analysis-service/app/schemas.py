"""
Analysis Service - Pydantic Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Dict, Any

# Must stay aligned with backend/app/models/schemas.py
UserGuess = Literal["phishing", "safe", "unclear"]
MAX_MESSAGE_LENGTH = 12_000


class LearningContext(BaseModel):
    """User learning context passed from gateway."""
    total_messages: int = 0
    accuracy: float = 0.0
    weak_spots: List[str] = Field(default_factory=list)
    by_category: Dict[str, Any] = Field(default_factory=dict)
    is_new_user: bool = True


class AnalysisRequest(BaseModel):
    """Request model for analysis endpoint."""
    message: str = Field(
        ..., min_length=1, max_length=MAX_MESSAGE_LENGTH,
        description="Message to analyze",
    )
    user_guess: Optional[UserGuess] = Field(None, description="User's prediction")
    learning_context: Optional[LearningContext] = None


class ClassificationResult(BaseModel):
    """Classification result from Classifier Agent."""
    label: str = Field(..., description="phishing, safe, or unclear")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason_tags: List[str] = Field(default_factory=list)
    explanation: str = Field(...)


class PhishingExample(BaseModel):
    """Similar phishing example from dataset."""
    message: str
    category: str
    similarity: Optional[float] = None
    description: Optional[str] = None


class QuizQuestion(BaseModel):
    """Quiz question from Coach Agent."""
    question: str
    options: List[str]
    correct_answer: str


# ---------------------------------------------------------------------------
# Internal LLM output validation models
# These are used to parse and validate raw Gemini JSON before trusting it.
# They are NOT the same as the HTTP-layer response schemas below.
# ---------------------------------------------------------------------------

ValidLabel = Literal["phishing", "safe", "unclear"]


class ClassifierRawOutput(BaseModel):
    """Strict schema used to validate the Classifier Agent's raw LLM output."""
    label: str = Field(default="unclear")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason_tags: List[str] = Field(default_factory=list)
    explanation: str = Field(default="Analysis completed.")

    @field_validator("label", mode="before")
    @classmethod
    def normalise_label(cls, v: object) -> str:
        """Accept any casing and map to canonical values; fall back to 'unclear'."""
        if not isinstance(v, str):
            return "unclear"
        normalised = v.strip().lower()
        return normalised if normalised in ("phishing", "safe", "unclear") else "unclear"

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: object) -> float:
        """Clamp any numeric value to [0, 1]; return 0.5 on failure."""
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("reason_tags", mode="before")
    @classmethod
    def coerce_reason_tags(cls, v: object) -> List[str]:
        """Ensure reason_tags is always a list of strings."""
        if isinstance(v, list):
            return [str(t) for t in v]
        return []


class QuizRawOutput(BaseModel):
    """Strict schema for an optional quiz embedded in the coach response."""
    question: str
    options: List[str] = Field(default_factory=list)
    correct_answer: str = Field(default="")

    @field_validator("options", mode="before")
    @classmethod
    def ensure_options_list(cls, v: object) -> List[str]:
        if isinstance(v, list):
            return [str(o) for o in v]
        return []


class CoachRawOutput(BaseModel):
    """Strict schema used to validate the Coach Agent's raw LLM output."""
    verdict: str = Field(default="unclear")
    explanation: str = Field(default="Analysis complete.")
    tips: List[str] = Field(default_factory=list)
    quiz: Optional[QuizRawOutput] = None

    @field_validator("verdict", mode="before")
    @classmethod
    def normalise_verdict(cls, v: object) -> str:
        if not isinstance(v, str):
            return "unclear"
        normalised = v.strip().lower()
        return normalised if normalised in ("phishing", "safe", "unclear") else "unclear"

    @field_validator("tips", mode="before")
    @classmethod
    def coerce_tips(cls, v: object) -> List[str]:
        if isinstance(v, list):
            return [str(t) for t in v]
        return []


class CoachResponse(BaseModel):
    """Response from Coach Agent."""
    verdict: str
    explanation: str
    similar_examples: List[PhishingExample]
    tips: List[str]
    quiz: Optional[QuizQuestion] = None


class AnalysisResponse(BaseModel):
    """Complete analysis response."""
    classification: ClassificationResult
    coach_response: CoachResponse
    was_correct: Optional[bool] = None
    category: str
