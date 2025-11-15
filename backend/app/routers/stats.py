from fastapi import APIRouter
from ..mongo import analyses_collection  # relative import

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/judgments")
def get_judgment_breakdown():
    """
    Aggregate phishing vs safe vs other from MongoDB analyses.
    """
    docs = analyses_collection.find({}, {"result": 1})

    counts = {"Safe": 0, "Phishing": 0, "Other": 0}

    for doc in docs:
        parsed = doc.get("result") or {}

        judgment = (
            parsed.get("judgment")
            or parsed.get("ai_result", {}).get("judgment")
            or "Other"
        )
        judgment = str(judgment).capitalize()

        if judgment in counts:
            counts[judgment] += 1
        else:
            counts["Other"] += 1

    return [{"type": k, "value": v} for k, v in counts.items() if v > 0]
