from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Analysis

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/judgments")
def get_judgment_counts(db: Session = Depends(get_db)):
    rows = db.query(Analysis.result, func.count(Analysis.id)).group_by(Analysis.result).all()
    return [{"type": r[0], "value": r[1]} for r in rows]

@router.get("/monthly")
def get_monthly_counts(db: Session = Depends(get_db)):
    rows = (
        db.query(func.strftime("%Y-%m", Analysis.created_at), func.count(Analysis.id))
        .group_by(func.strftime("%Y-%m", Analysis.created_at))
        .all()
    )
    return [{"month": r[0], "value": r[1]} for r in rows]