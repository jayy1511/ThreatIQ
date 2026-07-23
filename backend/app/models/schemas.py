from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict
from datetime import datetime

# Valid values for user_guess across all request schemas
UserGuess = Literal["phishing", "safe", "unclear"]

# Maximum message length accepted for analysis (characters)
MAX_MESSAGE_LENGTH = 12_000


class AnalysisRequest(BaseModel):
    """Request model for authenticated phishing analysis."""
    message: str = Field(
        ..., min_length=1, max_length=MAX_MESSAGE_LENGTH,
        description="Email or message to analyze",
    )
    user_guess: Optional[UserGuess] = Field(
        None, description="User's prediction: phishing, safe, or unclear",
    )
    user_id: str = Field(..., description="Firebase UID")
    request_id: Optional[str] = Field(None, description="Optional request ID for idempotency or tracking")
    # C5: optional email header block for sender verification.
    # Max 4000 chars to cover standard headers without storing full payloads.
    header_text: Optional[str] = Field(
        None, max_length=4_000,
        description="Raw email headers for sender verification (optional)",
    )


class PublicAnalysisRequest(BaseModel):
    """Request model for public (unauthenticated) phishing analysis.

    Does not accept user_id or request_id because public analysis
    is not saved to any user's profile or history.
    """
    message: str = Field(
        ..., min_length=1, max_length=MAX_MESSAGE_LENGTH,
        description="Email or message to analyze",
    )
    user_guess: Optional[UserGuess] = Field(
        None, description="User's prediction: phishing, safe, or unclear",
    )


class ClassificationResult(BaseModel):
    """Classification result from Classifier Agent."""
    label: str = Field(..., description="phishing, safe, or unclear")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reason_tags: List[str] = Field(default_factory=list, description="List of reason tags")
    explanation: str = Field(..., description="Brief explanation")


class PhishingExample(BaseModel):
    """Similar phishing example from dataset."""
    message: str
    category: str
    similarity: Optional[float] = None  # Similarity score (0-1)
    description: Optional[str] = None   # Made optional for backward compatibility


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
    session_id: str
    # C5: optional sender verification — absent on legacy responses
    sender_verification: Optional[Dict] = None


class UserProfile(BaseModel):
    """User profile model."""
    user_id: str
    total_messages: int = 0
    correct_guesses: int = 0
    by_category: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    weak_spots: List[str] = Field(default_factory=list)
    last_seen: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InteractionLog(BaseModel):
    """Interaction log model."""
    user_id: str
    message: str
    user_guess: Optional[str]
    classification: ClassificationResult
    was_correct: Optional[bool]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str


class GmailStatusResponse(BaseModel):
    """Gmail connection status response."""
    connected: bool
    email: Optional[str] = None
    scopes: Optional[List[str]] = None


class GmailConnectResponse(BaseModel):
    """Gmail OAuth connect URL response."""
    url: str


class GmailTriageRequest(BaseModel):
    """Gmail triage request parameters."""
    limit: Optional[int] = Field(10, ge=1, le=50, description="Max messages to process")
    mark_spam: Optional[bool] = Field(False, description="Mark phishing as spam")
    archive_safe: Optional[bool] = Field(False, description="Archive safe messages")


class GmailTriageResult(BaseModel):
    """Individual message triage result."""
    message_id: str
    from_: str = Field(alias="from")
    subject: str
    label: str
    confidence: float
    reasons: List[str]
    label_applied: bool
    success: bool
    error: Optional[str] = None
    
    class Config:
        populate_by_name = True


class GmailTriageResponse(BaseModel):
    """Gmail triage operation response."""
    processed: int
    results: List[GmailTriageResult]


class GmailTriageRecord(BaseModel):
    """Gmail triage history record."""
    id: str = Field(alias="_id")
    user_id: str
    gmail_message_id: str
    thread_id: str
    from_: str = Field(alias="from")
    subject: str
    date: str
    snippet: str
    body_excerpt: str
    label: str
    confidence: float
    reasons: List[str]
    label_applied: bool
    created_at: datetime
    
    class Config:
        populate_by_name = True


class GmailHistoryResponse(BaseModel):
    """Gmail triage history response."""
    items: List[GmailTriageRecord]

