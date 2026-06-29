"""
Analysis Service - Pydantic Schemas
"""

from pydantic import BaseModel, Field
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
