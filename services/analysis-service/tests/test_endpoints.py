"""
HTTP endpoint tests for the analysis service — B6.

These tests use FastAPI's TestClient to verify the /analyze
endpoint's internal API key authentication logic. No real Gemini
calls are made.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import logging

# We set a dummy api key in the settings for testing
TEST_API_KEY = "test_secret_key_123"

# ─── Fake LLM Response ───────────────────────────────────────────────────────

FAKE_ANALYSIS_RESULT = {
    "classification": {
        "label": "phishing",
        "confidence": 0.9,
        "reason_tags": ["suspicious_link"],
        "explanation": "Looks like phishing.",
    },
    "coach_response": {
        "verdict": "phishing",
        "explanation": "Be careful.",
        "similar_examples": [],
        "tips": ["Tip 1", "Tip 2"],
        "quiz": None,
    },
    "category": "fake_bank",
}

# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def analysis_client():
    """TestClient with mocked Gemini orchestrator and test API key."""
    from app.main import app
    from app.config import settings

    # Force the key for testing
    original_key = settings.analysis_service_api_key
    settings.analysis_service_api_key = TEST_API_KEY

    # The analysis service is stateless, no startup DB connections to clear.
    
    with patch("app.main.run_analysis", new=AsyncMock(return_value=FAKE_ANALYSIS_RESULT)):
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
            
    # Restore original key
    settings.analysis_service_api_key = original_key


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_health_endpoint(analysis_client):
    """Health check should return 200 without auth."""
    resp = analysis_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_without_key_rejected(analysis_client):
    """If production API key is configured, requests without it must be 401."""
    resp = analysis_client.post(
        "/analyze",
        json={"message": "Test message"}
    )
    assert resp.status_code == 401


def test_analyze_with_invalid_key_rejected(analysis_client):
    """Requests with wrong API key must be 401."""
    resp = analysis_client.post(
        "/analyze",
        json={"message": "Test message"},
        headers={"X-Internal-Service-Key": "wrong_key_456"}
    )
    assert resp.status_code == 401


def test_analyze_with_valid_key_accepted(analysis_client):
    """Requests with correct API key must be accepted."""
    resp = analysis_client.post(
        "/analyze",
        json={"message": "Test message"},
        headers={"X-Internal-Service-Key": TEST_API_KEY}
    )
    assert resp.status_code == 200
    assert resp.json()["classification"]["label"] == "phishing"


def test_analyze_without_key_accepted_in_dev_mode():
    """If no API key is configured (dev mode), requests without key should pass."""
    from app.main import app
    from app.config import settings

    original_key = settings.analysis_service_api_key
    settings.analysis_service_api_key = ""  # Simulate dev mode

    with patch("app.main.run_analysis", new=AsyncMock(return_value=FAKE_ANALYSIS_RESULT)):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/analyze",
                json={"message": "Test message"}
            )
            assert resp.status_code == 200

    settings.analysis_service_api_key = original_key
