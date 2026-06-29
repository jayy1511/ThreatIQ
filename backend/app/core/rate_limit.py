"""
In-memory sliding-window rate limiter for FastAPI.

Provides per-user (authenticated) and per-IP (public) rate limiting
via reusable FastAPI dependencies.

Limits are configurable via environment variables (see config.py).

NOTE – Production at scale:
    This implementation uses an in-memory dict, which means:
    * Limits reset on process restart.
    * Limits are per-process, not shared across workers/replicas.
    For multi-instance deployments, replace the storage backend with
    Redis (e.g. via ``aioredis``) or use a deployment-level rate limiter
    (e.g. Cloudflare, AWS API Gateway, Nginx ``limit_req``).
"""

import time
import logging
from collections import defaultdict

from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


class SlidingWindowCounter:
    """Simple sliding-window rate limiter (single-process, in-memory)."""

    def __init__(self) -> None:
        # key -> list of request timestamps (monotonic)
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if a request is allowed and record it if so."""
        now = time.monotonic()
        window_start = now - window_seconds

        # Prune expired entries
        timestamps = self._requests[key]
        self._requests[key] = [t for t in timestamps if t > window_start]

        if len(self._requests[key]) >= max_requests:
            return False

        self._requests[key].append(now)
        return True

    def retry_after(self, key: str, window_seconds: int) -> int:
        """Seconds until the oldest entry in the window expires."""
        entries = self._requests.get(key)
        if not entries:
            return 0
        oldest = min(entries)
        remaining = window_seconds - (time.monotonic() - oldest)
        return max(1, int(remaining))


# Singleton – shared across all routes in the process
limiter = SlidingWindowCounter()


def get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(
    request: Request,
    *,
    max_requests: int,
    window_seconds: int,
    user_id: str | None = None,
) -> None:
    """
    Enforce a rate limit, raising 429 if exceeded.

    Call this at the top of any endpoint handler.

    Args:
        request: The incoming FastAPI request (for IP extraction).
        max_requests: Allowed requests per window.
        window_seconds: Window duration in seconds.
        user_id: If provided, rate-limit by user_id; otherwise by IP.
    """
    key = f"uid:{user_id}" if user_id else f"ip:{get_client_ip(request)}"

    if not limiter.is_allowed(key, max_requests, window_seconds):
        retry = limiter.retry_after(key, window_seconds)
        logger.warning("Rate limit exceeded for %s", key)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry)},
        )
