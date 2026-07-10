from fastapi import APIRouter, HTTPException, Depends
from app.tools.profile_tools import ProfileManager
from app.routers.auth import verify_firebase_token
from app.models.database import Database
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: str,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Get user profile and statistics (full object).
    Returns:
      {
        "profile": UserProfile,
        "summary": {...}
      }
    """
    try:
        if user_id != user_data.get("uid"):
            raise HTTPException(
                status_code=403,
                detail="Cannot access other user's profile",
            )

        profile = await ProfileManager.load_user_profile(user_id)
        summary = await ProfileManager.get_user_summary(user_id)

        return {
            "profile": profile.model_dump(),
            "summary": summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get profile",
        )


@router.get("/profile/{user_id}/summary")
async def get_profile_summary(
    user_id: str,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Get summary of user's learning progress.
    """
    try:
        if user_id != user_data.get("uid"):
            raise HTTPException(
                status_code=403,
                detail="Cannot access other user's data",
            )

        summary = await ProfileManager.get_user_summary(user_id)
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get summary",
        )


@router.get("/profile/{user_id}/history")
async def get_user_history(
    user_id: str,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Get recent interaction history for the user (most recent first).
    The `message` field is null for items where the user opted out of text storage.
    """
    try:
        if user_id != user_data.get("uid"):
            raise HTTPException(
                status_code=403,
                detail="Cannot access other user's data",
            )

        db = Database.get_db()
        cursor = (
            db.interactions.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(50)
        )

        history = []
        async for doc in cursor:
            ts = doc.get("timestamp")
            if isinstance(ts, datetime):
                ts_val = ts.isoformat()
            else:
                ts_val = str(ts) if ts is not None else None

            history.append(
                {
                    "id": str(doc.get("_id")),
                    # message is None when user opted out of text storage
                    "message": doc.get("message"),
                    "classification": doc.get("classification", {}),
                    "was_correct": doc.get("was_correct"),
                    "session_id": doc.get("session_id"),
                    "timestamp": ts_val,
                }
            )

        return {"history": history}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get history",
        )


@router.delete("/profile/{user_id}/history/{item_id}", status_code=200)
async def delete_history_item(
    user_id: str,
    item_id: str,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Delete a single history item belonging to the authenticated user.
    """
    try:
        if user_id != user_data.get("uid"):
            raise HTTPException(status_code=403, detail="Cannot delete other user's history")

        try:
            oid = ObjectId(item_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid item ID")

        db = Database.get_db()
        result = await db.interactions.delete_one({"_id": oid, "user_id": user_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="History item not found")

        return {"deleted": True, "id": item_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting history item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete history item")


@router.delete("/profile/{user_id}/history", status_code=200)
async def clear_user_history(
    user_id: str,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Delete all interaction history for the authenticated user.
    """
    try:
        if user_id != user_data.get("uid"):
            raise HTTPException(status_code=403, detail="Cannot clear other user's history")

        db = Database.get_db()
        result = await db.interactions.delete_many({"user_id": user_id})

        logger.info(f"Cleared {result.deleted_count} history items for user {user_id}")
        return {"deleted": True, "count": result.deleted_count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to clear history")


class PrivacySettings(BaseModel):
    save_message_text: bool


@router.patch("/profile/{user_id}/settings", status_code=200)
async def update_privacy_settings(
    user_id: str,
    settings: PrivacySettings,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Update the user's privacy settings.

    save_message_text:
      true  – full message text is stored in interaction history (existing default)
      false – only metadata (label, confidence, timestamp, etc.) is stored; message
              text is set to null in new interaction records
    """
    try:
        if user_id != user_data.get("uid"):
            raise HTTPException(status_code=403, detail="Cannot update other user's settings")

        db = Database.get_db()
        await db.user_profiles.update_one(
            {"user_id": user_id},
            {"$set": {"save_message_text": settings.save_message_text}},
            upsert=True,
        )

        logger.info(
            f"Updated privacy settings for user {user_id}: "
            f"save_message_text={settings.save_message_text}"
        )
        return {"save_message_text": settings.save_message_text}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating privacy settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update settings")
