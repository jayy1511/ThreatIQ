"""
Backend unit tests — no live server or database required.

These tests verify:
1. Pydantic request/response schema validation (correct types, ranges, limits)
2. Key constants stay in sync

All tests run offline (no HTTP calls, no MongoDB).
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.schemas import (
    AnalysisRequest,
    PublicAnalysisRequest,
    ClassificationResult,
    GmailTriageRequest,
    MAX_MESSAGE_LENGTH,
)


# ---------------------------------------------------------------------------
# AnalysisRequest
# ---------------------------------------------------------------------------

class TestAnalysisRequest:

    def test_valid_request(self):
        req = AnalysisRequest(
            message="Click here to claim your prize!",
            user_id="uid_abc123",
        )
        assert req.message == "Click here to claim your prize!"
        assert req.user_guess is None
        assert req.user_id == "uid_abc123"

    def test_valid_with_guess(self):
        req = AnalysisRequest(
            message="Normal message",
            user_id="uid_xyz",
            user_guess="phishing",
        )
        assert req.user_guess == "phishing"

    def test_invalid_guess_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(message="Hello", user_id="uid", user_guess="malware")

    def test_message_too_short(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(message="", user_id="uid")

    def test_message_too_long(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(message="a" * (MAX_MESSAGE_LENGTH + 1), user_id="uid")

    def test_message_at_max_length(self):
        req = AnalysisRequest(message="a" * MAX_MESSAGE_LENGTH, user_id="uid")
        assert len(req.message) == MAX_MESSAGE_LENGTH

    def test_missing_user_id(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(message="Hello")

    def test_optional_request_id(self):
        req = AnalysisRequest(
            message="Test", user_id="uid", request_id="req-001"
        )
        assert req.request_id == "req-001"


# ---------------------------------------------------------------------------
# PublicAnalysisRequest
# ---------------------------------------------------------------------------

class TestPublicAnalysisRequest:

    def test_valid_public_request(self):
        req = PublicAnalysisRequest(message="Is this email safe?")
        assert req.user_guess is None

    def test_public_request_no_user_id(self):
        # Public endpoint must NOT accept user_id — field should not exist
        # (ensuring schema separation between public and authenticated endpoints)
        req = PublicAnalysisRequest(message="Test message")
        assert not hasattr(req, "user_id")

    def test_public_request_with_guess(self):
        req = PublicAnalysisRequest(message="Test message", user_guess="safe")
        assert req.user_guess == "safe"


# ---------------------------------------------------------------------------
# ClassificationResult
# ---------------------------------------------------------------------------

class TestClassificationResult:

    def test_valid_classification(self):
        clf = ClassificationResult(
            label="phishing",
            confidence=0.95,
            reason_tags=["suspicious_link", "urgent_language"],
            explanation="Clear phishing indicators.",
        )
        assert clf.label == "phishing"
        assert clf.confidence == 0.95

    def test_confidence_must_be_in_range(self):
        with pytest.raises(ValidationError):
            ClassificationResult(
                label="safe", confidence=1.5, reason_tags=[], explanation="ok"
            )

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValidationError):
            ClassificationResult(
                label="safe", confidence=-0.1, reason_tags=[], explanation="ok"
            )


# ---------------------------------------------------------------------------
# GmailTriageRequest
# ---------------------------------------------------------------------------

class TestGmailTriageRequest:

    def test_defaults(self):
        req = GmailTriageRequest()
        assert req.limit == 10
        assert req.mark_spam is False
        assert req.archive_safe is False

    def test_limit_upper_bound(self):
        with pytest.raises(ValidationError):
            GmailTriageRequest(limit=51)

    def test_limit_lower_bound(self):
        with pytest.raises(ValidationError):
            GmailTriageRequest(limit=0)

    def test_valid_custom_limit(self):
        req = GmailTriageRequest(limit=25)
        assert req.limit == 25


# ---------------------------------------------------------------------------
# Constants alignment check
# ---------------------------------------------------------------------------

class TestConstants:
    def test_max_message_length_is_12k(self):
        """Ensure the constant hasn't been accidentally changed."""
        assert MAX_MESSAGE_LENGTH == 12_000
