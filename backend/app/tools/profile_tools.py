"""
Profile Tools - Wrapper for ADK tools

This module provides backward compatibility by wrapping ADK tools.
"""

from app.tools.adk_tools import get_user_profile, update_user_profile, log_interaction
from app.models.schemas import UserProfile
import logging

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manager for user profile operations (wrapper for ADK tools)."""
    
    @staticmethod
    async def load_user_profile(user_id: str) -> UserProfile:
        """Load user profile using ADK tool."""
        profile_dict = await get_user_profile(user_id)
        return UserProfile(**profile_dict)
    
    @staticmethod
    async def save_user_profile(profile: UserProfile) -> bool:
        """Save is handled by update_user_profile ADK tool."""
        return True
    
    @staticmethod
    async def update_profile_stats(user_id: str, category: str, was_correct: bool) -> UserProfile:
        """Update profile stats using ADK tool."""
        profile_dict = await update_user_profile(user_id, category, was_correct)
        return UserProfile(**profile_dict)
    
    @staticmethod
    async def get_user_summary(user_id: str) -> dict:
        """Get user summary."""
        profile = await ProfileManager.load_user_profile(user_id)
        
        accuracy = 0.0
        if profile.total_messages > 0:
            accuracy = (profile.correct_guesses / profile.total_messages) * 100
        
        return {
            "total_analyzed": profile.total_messages,
            "accuracy": round(accuracy, 1),
            "weak_spots": profile.weak_spots[:3] if profile.weak_spots else [],
            "categories_seen": len(profile.by_category)
        }


class InteractionLogger:
    """Logger for user interactions (wrapper for ADK tool)."""
    
    @staticmethod
    async def log_interaction(
        user_id: str,
        message: str,
        user_guess: str,
        classification: dict,
        was_correct: bool,
        session_id: str,
        request_id: str,
        full_response: dict = None
    ) -> bool:
        """Log interaction using ADK tool with idempotency."""
        return await log_interaction(
            user_id=user_id,
            message=message,
            classification=classification,
            was_correct=was_correct,
            session_id=session_id,
            request_id=request_id,
            full_response=full_response
        )
