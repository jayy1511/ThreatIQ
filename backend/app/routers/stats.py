# app/routers/stats.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Analysis
import json

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/judgments")
def get_judgment_breakdown(db: Session = Depends(get_db)):
    rows = db.query(Analysis.result).all()

    counts = {"Safe": 0, "Phishing": 0, "Other": 0}
    for (result_str,) in rows:
        try:
            parsed = json.loads(result_str)
            # try both possible structures
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
        except Exception:
            counts["Other"] += 1

    return [{"type": k, "value": v} for k, v in counts.items() if v > 0]
