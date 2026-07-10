"""
Dashboard Router — B8

Single authenticated endpoint that returns all data needed by the
frontend dashboard in one request.

Endpoint:
  GET /api/dashboard

Response (all sections fault-isolated — a single failure never blocks
the rest):
  {
    "summary":         {...} | null,
    "lesson_progress": {...} | null,
    "today_lesson":    {...} | null,
    "gmail":           {"connected": bool, "email": str | null}
  }
"""

import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from fastapi import APIRouter, Depends

from app.models.database import Database
from app.routers.auth import verify_firebase_token
from app.services.gmail_oauth import gmail_oauth_service
from app.data.lessons import get_lesson_of_day

logger = logging.getLogger(__name__)
router = APIRouter()

PARIS_TZ = pytz.timezone("Europe/Paris")


def _today_str() -> str:
    return datetime.now(PARIS_TZ).strftime("%Y-%m-%d")


def _calculate_level(xp_total: int) -> int:
    return (xp_total // 100) + 1


# ── helpers (each returns None on failure, never raises) ─────────────────────

async def _fetch_summary(user_id: str) -> dict | None:
    try:
        db = Database.get_db()
        profile = await db.user_profiles.find_one({"user_id": user_id})
        if not profile:
            return {
                "total_analyzed": 0,
                "accuracy": 0.0,
                "categories_seen": 0,
                "weak_spots": [],
            }
        total = profile.get("total_messages", 0)
        correct = profile.get("correct_guesses", 0)
        accuracy = round((correct / total) * 100, 1) if total > 0 else 0.0
        by_category = profile.get("by_category", {})
        weak_spots = profile.get("weak_spots", [])
        return {
            "total_analyzed": total,
            "accuracy": accuracy,
            "categories_seen": len(by_category),
            "weak_spots": weak_spots[:3],
        }
    except Exception:
        logger.warning("dashboard: could not fetch summary for %s", user_id, exc_info=True)
        return None


async def _fetch_lesson_progress(user_id: str) -> dict | None:
    try:
        db = Database.get_db()
        profile = await db.user_profiles.find_one({"user_id": user_id})
        if not profile:
            return {
                "xp_total": 0,
                "level": 1,
                "streak_current": 0,
                "streak_best": 0,
                "last_lesson_completed_date": None,
                "lessons_completed": 0,
            }
        xp = profile.get("xp_total", 0)
        lessons_completed = await db.lesson_completions.count_documents(
            {"user_id": user_id}
        )
        return {
            "xp_total": xp,
            "level": _calculate_level(xp),
            "streak_current": profile.get("streak_current", 0),
            "streak_best": profile.get("streak_best", 0),
            "last_lesson_completed_date": profile.get("last_lesson_completed_date"),
            "lessons_completed": lessons_completed,
        }
    except Exception:
        logger.warning(
            "dashboard: could not fetch lesson progress for %s", user_id, exc_info=True
        )
        return None


async def _fetch_today_lesson(user_id: str) -> dict | None:
    try:
        lesson = get_lesson_of_day()
        today = _today_str()
        db = Database.get_db()
        completion = await db.lesson_completions.find_one(
            {"user_id": user_id, "date": today}
        )
        already_completed = completion is not None
        return {
            "lesson": {
                "lesson_id": lesson.get("lesson_id"),
                "title": lesson.get("title"),
                "topic": lesson.get("topic"),
            },
            "date": today,
            "already_completed": already_completed,
            "completion_score": completion.get("score_percent") if completion else None,
        }
    except Exception:
        logger.warning(
            "dashboard: could not fetch today lesson for %s", user_id, exc_info=True
        )
        return None


async def _fetch_gmail_status(user_id: str) -> dict:
    try:
        tokens = await gmail_oauth_service.get_tokens(user_id)
        if tokens:
            return {"connected": True, "email": tokens.get("email")}
    except Exception:
        logger.warning(
            "dashboard: could not fetch gmail status for %s", user_id, exc_info=True
        )
    return {"connected": False, "email": None}


# ── endpoint ──────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(user_data: dict = Depends(verify_firebase_token)):
    """
    Aggregate dashboard endpoint.

    Returns all data needed by the frontend dashboard in a single
    authenticated request. Each section is fetched concurrently and is
    fault-isolated — a failure in one section returns null for that
    section without failing the whole response.
    """
    user_id = user_data.get("uid")

    summary, lesson_progress, today_lesson, gmail = await asyncio.gather(
        _fetch_summary(user_id),
        _fetch_lesson_progress(user_id),
        _fetch_today_lesson(user_id),
        _fetch_gmail_status(user_id),
    )

    return {
        "summary": summary,
        "lesson_progress": lesson_progress,
        "today_lesson": today_lesson,
        "gmail": gmail,
    }
