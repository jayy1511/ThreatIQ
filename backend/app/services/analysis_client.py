"""
Analysis Service Client

Single, shared gateway to the analysis microservice.
Used by all backend routes and services that need to analyse a message
so that triage, authenticated analysis, and public analysis all go through
the same network path and auth header.
"""

import asyncio
import logging

import httpx
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry / timeout configuration (mirrored from previous inline config)
# ---------------------------------------------------------------------------
MAX_RETRIES = 5
RETRY_DELAYS = [2, 4, 8, 16, 20]   # seconds – exponential back-off
RETRYABLE_STATUS_CODES = {502, 503, 504}
REQUEST_TIMEOUT = 120.0             # generous for Render cold starts

# Short-timeout variant used for automated triage where we don't want one
# slow cold-start to block the whole inbox batch.
TRIAGE_TIMEOUT = 60.0
TRIAGE_MAX_RETRIES = 2
TRIAGE_RETRY_DELAYS = [3, 6]


def _build_headers() -> dict:
    """Return headers required by the analysis microservice."""
    headers = {"Content-Type": "application/json"}
    if settings.analysis_service_api_key:
        headers["X-Internal-Service-Key"] = settings.analysis_service_api_key
    return headers


async def call_analysis_service(
    message: str,
    user_guess: str | None = None,
    learning_context: dict | None = None,
    *,
    max_retries: int = MAX_RETRIES,
    retry_delays: list[int] = RETRY_DELAYS,
    timeout: float = REQUEST_TIMEOUT,
) -> dict:
    """
    Call the analysis microservice with retry / back-off logic.

    Args:
        message: The message text to analyse.
        user_guess: Optional user prediction ('phishing', 'safe', 'unclear').
        learning_context: Optional personalisation context dict.
        max_retries: How many total attempts to make.
        retry_delays: Per-attempt delay in seconds (back-off list).
        timeout: Per-request timeout in seconds.

    Returns:
        Raw analysis result dict from the microservice.

    Raises:
        HTTPException(502): When all retries are exhausted.
    """
    payload = {
        "message": message,
        "user_guess": user_guess,
        "learning_context": learning_context,
    }
    headers = _build_headers()
    last_error: str | None = None

    for attempt in range(max_retries):
        try:
            logger.info(
                "Analysis service call attempt %d/%d", attempt + 1, max_retries
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{settings.analysis_service_url}/analyze",
                    json=payload,
                    headers=headers,
                )

            if response.status_code == 200:
                logger.info("Analysis service succeeded on attempt %d", attempt + 1)
                return response.json()

            if response.status_code in RETRYABLE_STATUS_CODES:
                last_error = f"Service returned {response.status_code}"
                logger.warning(
                    "Analysis service returned %s (attempt %d) – likely cold start, retrying",
                    response.status_code,
                    attempt + 1,
                )
            else:
                # Non-retryable error – fail fast
                logger.error(
                    "Analysis service non-retryable error %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Analysis service error: {response.status_code}",
                )

        except httpx.TimeoutException:
            last_error = "Request timeout"
            logger.warning("Analysis service timeout (attempt %d)", attempt + 1)

        except httpx.ConnectError:
            last_error = "Connection failed"
            logger.warning(
                "Cannot connect to analysis service (attempt %d)", attempt + 1
            )

        except HTTPException:
            raise  # already formatted

        except Exception as exc:
            last_error = str(exc)
            logger.error("Unexpected error on attempt %d: %s", attempt + 1, exc)

        # Back-off before retry (skip sleep on last attempt)
        if attempt < max_retries - 1:
            delay = retry_delays[min(attempt, len(retry_delays) - 1)]
            logger.info("Waiting %ds before retry…", delay)
            await asyncio.sleep(delay)

    logger.error("All %d attempts failed. Last error: %s", max_retries, last_error)
    raise HTTPException(
        status_code=502,
        detail="Analysis service warming up, please retry in 30 seconds",
    )


async def call_analysis_service_for_triage(
    message: str,
) -> dict:
    """
    Lightweight wrapper for automated Gmail triage calls.

    Uses a shorter timeout and fewer retries so a single slow cold-start
    does not stall the whole inbox batch.  Returns None on failure so the
    caller can treat one bad email as a soft error without aborting the
    rest of the batch.
    """
    try:
        return await call_analysis_service(
            message=message,
            user_guess=None,
            learning_context=None,
            max_retries=TRIAGE_MAX_RETRIES,
            retry_delays=TRIAGE_RETRY_DELAYS,
            timeout=TRIAGE_TIMEOUT,
        )
    except Exception as exc:
        logger.error("Triage analysis call failed: %s", exc)
        return None
