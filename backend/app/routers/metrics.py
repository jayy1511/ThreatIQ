from fastapi import APIRouter, Depends, HTTPException
from app.routers.auth import verify_admin_user
from app.models.database import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics")
async def get_metrics(user_data: dict = Depends(verify_admin_user)):
    """
    Basic system metrics for observability.

    Admin-only: requires the ``admin`` Firebase custom claim.

    Returned fields (example):
    - total_users: how many user profiles exist
    - total_messages: sum of total_messages over all users
    - total_interactions: number of interaction logs
    - avg_accuracy: average user accuracy across all profiles
    """
    try:
        db = Database.get_db()

        total_users = await db.user_profiles.count_documents({})
        total_interactions = await db.interactions.count_documents({})

        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_messages": {"$sum": "$total_messages"},
                    "correct_guesses": {"$sum": "$correct_guesses"},
                }
            }
        ]
        agg = await db.user_profiles.aggregate(pipeline).to_list(length=1)
        if agg:
            total_messages = int(agg[0].get("total_messages", 0))
            correct_guesses = int(agg[0].get("correct_guesses", 0))
        else:
            total_messages = 0
            correct_guesses = 0

        avg_accuracy = (
            correct_guesses / total_messages if total_messages > 0 else 0.0
        )

        return {
            "total_users": total_users,
            "total_messages": total_messages,
            "total_interactions": total_interactions,
            "avg_accuracy": round(avg_accuracy, 3),
        }

    except Exception as e:
        logger.error(f"Error computing metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to compute metrics",
        )
