import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..intel.heuristics import check_keywords, check_urls, check_grammar, check_sender
from ..intel.whois_check import check_domain_age
from ..intel.virustotal import check_url_virustotal
from ..intel.llm import analyze_with_gemini
from .. import models, schemas

router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.post("/")
def analyze_message(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    text = payload.get("text")
    sender = payload.get("sender", "")

    if not text:
        raise HTTPException(status_code=400, detail="Missing text field")

    # --- Run heuristics ---
    results = {}
    results.update(check_keywords(text))
    results.update(check_urls(text))
    results.update(check_grammar(text))
    results.update(check_sender(sender))

    # --- Extra intelligence ---
    vt_results = []
    whois_results = []
    for domain in results.get("domains", []):
        whois_results.append(check_domain_age(domain))
    for url in results.get("urls", []):
        vt_results.append(check_url_virustotal(url))

    results["virustotal"] = vt_results
    results["whois"] = whois_results

    # --- AI analysis (Gemini) ---
    ai_result = analyze_with_gemini(text, results)

    # --- Save in DB ---
    analysis = models.Analysis(
        user_id=current_user["sub"],
        text=text,
        sender=sender,
        result=json.dumps({
            "analysis": results,
            "ai_result": ai_result
        })
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {
        "user": current_user,
        "analysis": results,
        "ai_result": ai_result,
        "saved_record": {
            "id": analysis.id,
            "created_at": analysis.created_at
        }
    }

@router.get("/history", response_model=list[schemas.AnalysisOut])
def get_history(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    records = db.query(models.Analysis).filter(
        models.Analysis.user_id == current_user["sub"]
    ).all()

    # Convert JSON string back to dict for response
    for r in records:
        try:
            r.result = json.loads(r.result)
        except:
            r.result = {}
    return records
