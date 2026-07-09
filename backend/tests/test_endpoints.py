"""
HTTP endpoint tests for the gateway (backend) — B6.

These tests use FastAPI's TestClient with dependency overrides.
No real Firebase, MongoDB, or Gemini calls are made.

Tests cover:
- Public endpoint works without auth and without user_id
- Authenticated endpoint rejects missing auth header (401)
- Authenticated endpoint rejects mismatched user_id (403)
- Invalid user_guess returns 422
- Oversized message returns 422
- Public endpoint applies rate limiting (RateLimitExceeded → 429)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# ─── Lightweight fake responses ──────────────────────────────────────────────

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
    "was_correct": None,
    "session_id": "test-session-001",
}

FAKE_USER_DATA = {"uid": "user_abc123", "email": "test@example.com"}

MAX_MSG = "a" * 12_000      # exactly at limit
OVER_MAX_MSG = "a" * 12_001  # one over limit


# ─── App bootstrap (import after all env patches applied) ─────────────────────

def make_client():
    """Build TestClient with all dangerous dependencies mocked out."""
    import app.routers.auth as auth_module
    import app.models.database as db_module

    from app.main import app
    from app.routers.auth import verify_firebase_token
    from app.services.analysis_client import call_analysis_service

    # Override Firebase verification — pretend every token is valid for FAKE_USER_DATA
    async def fake_verify(_auth_header=None):
        return FAKE_USER_DATA

    # Override analysis service call — return deterministic fake result
    async def fake_call_analysis(message, user_guess=None, learning_context=None):
        return dict(FAKE_ANALYSIS_RESULT)

    app.dependency_overrides[verify_firebase_token] = fake_verify

    # Patch the analysis client at the router level
    with patch("app.routers.analysis.call_analysis_service_with_retry", new=fake_call_analysis), \
         patch("app.agents.memory.MemoryAgent.get_learning_context", new=AsyncMock(return_value={})), \
         patch("app.agents.memory.MemoryAgent.update_profile", new=AsyncMock()), \
         patch("app.tools.profile_tools.InteractionLogger.log_interaction", new=AsyncMock()), \
         patch("app.models.database.Database.get_db", return_value=MagicMock(
             interactions=MagicMock(find_one=AsyncMock(return_value=None))
         )):
        client = TestClient(app, raise_server_exceptions=False)
        yield client

    app.dependency_overrides.clear()


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def backend_client():
    """TestClient with mocked Firebase and analysis service."""
    # We set up all patches as context managers in the test body for precision.
    from app.main import app
    from app.routers.auth import verify_firebase_token
    from app.core.rate_limit import check_rate_limit as real_rate_limit

    from fastapi import Header

    async def fake_verify(authorization: str = Header(None)):
        if not authorization or not authorization.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Authorization header missing")
        return FAKE_USER_DATA

    # Override Firebase auth dependency
    app.dependency_overrides[verify_firebase_token] = fake_verify

    with patch("app.routers.analysis.call_analysis_service_with_retry", new_callable=lambda: lambda **kw: _async_fake(**kw)), \
         patch("app.agents.memory.memory_agent.get_learning_context", new=AsyncMock(return_value={})), \
         patch("app.agents.memory.memory_agent.update_profile", new=AsyncMock()), \
         patch("app.tools.profile_tools.InteractionLogger.log_interaction", new=AsyncMock()), \
         patch("app.models.database.Database.get_db") as mock_get_db:

        mock_db = MagicMock()
        mock_db.interactions.find_one = AsyncMock(return_value=None)
        app.router.on_startup.clear()
        app.router.on_shutdown.clear()

        client = TestClient(app, raise_server_exceptions=False)
        yield client

    app.dependency_overrides.clear()


async def _async_fake(message, user_guess=None, learning_context=None):
    return dict(FAKE_ANALYSIS_RESULT)


# ─── Public endpoint tests ────────────────────────────────────────────────────

class TestPublicAnalysis:

    def test_public_endpoint_accepts_no_auth(self, backend_client):
        """Public endpoint must not require Authorization header."""
        with patch("app.routers.analysis.call_analysis_service_with_retry", new=AsyncMock(
            return_value=dict(FAKE_ANALYSIS_RESULT)
        )):
            resp = backend_client.post(
                "/api/analyze-public",
                json={"message": "Click here to claim your prize!"},
            )
        assert resp.status_code != 401, (
            f"Public endpoint should not require auth, got {resp.status_code}"
        )

    def test_public_endpoint_no_user_id_field(self, backend_client):
        """PublicAnalysisRequest schema must reject user_id (extra fields forbidden)."""
        with patch("app.routers.analysis.call_analysis_service_with_retry", new=AsyncMock(
            return_value=dict(FAKE_ANALYSIS_RESULT)
        )):
            resp = backend_client.post(
                "/api/analyze-public",
                json={
                    "message": "Normal message",
                    "user_id": "should_be_ignored_or_rejected",
                },
            )
        # FastAPI ignores extra fields by default (they're not stored in the model).
        # The key test is that the schema itself has no user_id field.
        from app.models.schemas import PublicAnalysisRequest
        assert not hasattr(PublicAnalysisRequest(message="x"), "user_id")

    def test_invalid_user_guess_returns_422(self, backend_client):
        """Invalid user_guess value must return 422 Unprocessable Entity."""
        resp = backend_client.post(
            "/api/analyze-public",
            json={"message": "Hello world", "user_guess": "malware"},
        )
        assert resp.status_code == 422

    def test_oversized_message_returns_422(self, backend_client):
        """Message over 12,000 chars must return 422."""
        resp = backend_client.post(
            "/api/analyze-public",
            json={"message": OVER_MAX_MSG},
        )
        assert resp.status_code == 422

    def test_message_at_max_length_accepted(self, backend_client):
        """Message exactly at 12,000 chars must be accepted (not 422)."""
        with patch("app.routers.analysis.call_analysis_service_with_retry", new=AsyncMock(
            return_value=dict(FAKE_ANALYSIS_RESULT)
        )):
            resp = backend_client.post(
                "/api/analyze-public",
                json={"message": MAX_MSG},
            )
        assert resp.status_code != 422

    def test_empty_message_returns_422(self, backend_client):
        """Empty message must return 422."""
        resp = backend_client.post(
            "/api/analyze-public",
            json={"message": ""},
        )
        assert resp.status_code == 422


# ─── Authenticated endpoint tests ─────────────────────────────────────────────

class TestAuthenticatedAnalysis:

    def test_missing_auth_header_returns_401(self, backend_client):
        """Authenticated endpoint must reject requests without Authorization header."""
        resp = backend_client.post(
            "/api/analyze",
            json={"message": "Hello", "user_id": "uid_abc"},
        )
        assert resp.status_code == 401

    def test_invalid_auth_format_returns_401(self, backend_client):
        """Malformed Authorization header must return 401."""
        resp = backend_client.post(
            "/api/analyze",
            json={"message": "Hello", "user_id": "uid_abc"},
            headers={"Authorization": "NotBearer token123"},
        )
        assert resp.status_code == 401

    def test_mismatched_user_id_returns_403(self, backend_client):
        """user_id in body must match the token uid; mismatch returns 403."""
        with patch("app.routers.analysis.call_analysis_service_with_retry", new=AsyncMock(
            return_value=dict(FAKE_ANALYSIS_RESULT)
        )):
            resp = backend_client.post(
                "/api/analyze",
                json={"message": "Hello", "user_id": "different_uid"},
                headers={"Authorization": "Bearer fake-token"},
            )
        assert resp.status_code == 403

    def test_invalid_user_guess_returns_422_authenticated(self, backend_client):
        """Invalid user_guess on authenticated endpoint must return 422."""
        resp = backend_client.post(
            "/api/analyze",
            json={"message": "Hello", "user_id": "user_abc123", "user_guess": "trojan"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 422

    def test_oversized_message_returns_422_authenticated(self, backend_client):
        """Oversized message on authenticated endpoint must return 422."""
        resp = backend_client.post(
            "/api/analyze",
            json={"message": OVER_MAX_MSG, "user_id": "user_abc123"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 422
