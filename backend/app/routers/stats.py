from fastapi import APIRouter, Depends
from ..mongo import analyses_collection
from ..firebase_auth import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/judgments")
def get_judgment_breakdown(user=Depends(get_current_user)):
    docs = analyses_collection.find(
        {"user_id": user["uid"]},  
        {"result": 1}
    )

    counts = {"Safe": 0, "Phishing": 0, "Other": 0}

    for doc in docs:
        parsed = doc.get("result", {})

        judgment = (
            parsed.get("judgment")
            or parsed.get("ai_result", {}).get("judgment")
            or "Other"
        )

        judgment = str(judgment).capitalize()

        if judgment not in counts:
            judgment = "Other"

        counts[judgment] += 1

    return [
        {"type": k, "value": v}
        for k, v in counts.items()
        if v > 0
    ]
