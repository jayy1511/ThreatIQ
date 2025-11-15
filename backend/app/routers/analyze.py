import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user
from ..intel.heuristics import check_keywords, check_urls, check_grammar, check_sender
from ..intel.whois_check import check_domain_age
from ..intel.virustotal import check_url_virustotal
from ..intel.llm import analyze_with_gemini
from ..mongo import analyses_collection, serialize_analysis

router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.post("/")
def analyze_message(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    text = payload.get("text")
    sender = payload.get("sender", "")

    if not text:
        raise HTTPException(status_code=400, detail="Missing text field")

    # --- Run heuristics ---
    results: dict = {}
    results.update(check_keywords(text))
    results.update(check_urls(text))
    results.update(check_grammar(text))
    results.update(check_sender(sender))

    # Domain / URL checks
    results.update(check_domain_age(text))
    results.update(check_url_virustotal(text))

    # --- AI analysis (Gemini) ---
    ai_result = analyze_with_gemini(text, results)

    # --- Save in MongoDB ---
    doc = {
        "user_id": current_user["sub"],
        "text": text,
        "sender": sender,
        "result": {
            "analysis": results,
            "ai_result": ai_result,
        },
        "created_at": datetime.utcnow(),
    }
    insert_result = analyses_collection.insert_one(doc)
    doc["_id"] = insert_result.inserted_id

    saved_record = serialize_analysis(doc)

    return {
        "user": current_user,
        "analysis": results,
        "ai_result": ai_result,
        "saved_record": {
            "id": saved_record["id"],
            "created_at": saved_record["created_at"],
        },
    }


@router.get("/history")
def get_history(current_user: dict = Depends(get_current_user)):
    """
    Return history of analyses for the current user from MongoDB.
    """
    cursor = analyses_collection.find(
        {"user_id": current_user["sub"]}
    ).sort("created_at", -1)

    records = [serialize_analysis(doc) for doc in cursor]

    # result is already stored as dict, no need to json.loads
    return records
