from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import google.generativeai as genai
from datetime import datetime

from ..config import settings
from ..mongo import analyses_collection
from ..firebase_auth import get_current_user

router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
)

# Gemini
MODEL_NAME = "gemini-2.0-flash"
if settings.GEMINI_API_KEY:
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(MODEL_NAME)
    except:
        _model = None
else:
    _model = None

class AnalyzeRequest(BaseModel):
    text: str
    sender: Optional[str] = None

class AnalyzeResponse(BaseModel):
    text: str
    ai_result: Dict[str, Any]

def _fallback_result(reason: str) -> Dict[str, Any]:
    return {
        "judgment": "Unclear",
        "explanation": reason,
        "tips": [
            "Double-check the sender address.",
            "Avoid clicking unknown links."
        ],
    }

def _call_gemini_for_analysis(text: str) -> Dict[str, Any]:
    if _model is None:
        return _fallback_result("Gemini API key missing.")

    prompt = f"""
Analyze this message:

\"\"\"{text}\"\"\"

Return EXACTLY:

Judgment: Safe / Phishing / Unclear
Explanation: <text>
Tips:
- tip1
- tip2
"""

    try:
        raw = _model.generate_content(prompt).text.strip()
    except Exception as e:
        return _fallback_result(f"Gemini error: {e}")

    lines = [x.strip() for x in raw.splitlines() if x.strip()]
    judgment = "Unclear"
    explanation = ""
    tips: List[str] = []

    for line in lines:
        low = line.lower()
        if low.startswith("judgment:"):
            judgment = line.split(":", 1)[1].strip().capitalize()
        elif low.startswith("explanation:"):
            explanation = line.split(":", 1)[1].strip()
        elif line.startswith("-") or line.startswith("•"):
            tips.append(line.lstrip("-•").strip())

    if not explanation:
        explanation = raw
    if not tips:
        tips = ["Verify sender address", "Avoid unknown links"]

    return {
        "judgment": judgment,
        "explanation": explanation,
        "tips": tips,
    }

@router.post("/", response_model=AnalyzeResponse)
def analyze_message(body: AnalyzeRequest, user=Depends(get_current_user)):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    ai_result = _call_gemini_for_analysis(body.text)

    analyses_collection.insert_one({
        "user_id": user["uid"],   # FIXED
        "text": body.text,
        "sender": body.sender or "",
        "result": ai_result,
        "created_at": datetime.utcnow(),
    })

    return AnalyzeResponse(text=body.text, ai_result=ai_result)

@router.get("/history")
def get_history(user=Depends(get_current_user)):
    docs = analyses_collection.find(
        {"user_id": user["uid"]},   # FIXED
        {"_id": 0}
    )
    return list(docs)
