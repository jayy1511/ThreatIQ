# backend/app/routers/analyze.py

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

from ..config import settings

router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
)

# -------- Gemini setup --------
MODEL_NAME = "gemini-2.0-flash"  # use the model that works with your key

if settings.GEMINI_API_KEY:
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        print(f"Failed to init Gemini model {MODEL_NAME}: {e}")
        _model = None
else:
    _model = None


# -------- Schemas --------

class AnalyzeRequest(BaseModel):
    text: str
    sender: Optional[str] = None


class AnalyzeResponse(BaseModel):
    text: str
    ai_result: Dict[str, Any]


# -------- Helpers --------

def _fallback_result(reason: str) -> Dict[str, Any]:
    return {
        "judgment": "Unclear",
        "explanation": reason,
        "tips": [
            "Double-check the sender address and domain.",
            "Avoid clicking on links in messages you do not trust.",
        ],
    }


def _call_gemini_for_analysis(text: str) -> Dict[str, Any]:
    """
    Ask Gemini to classify the message.
    Output is parsed from a simple text format:

    Judgment: Safe / Phishing / Unclear
    Explanation: <short reason>
    Tips:
    - <tip 1>
    - <tip 2>
    """

    if _model is None:
        return _fallback_result("Gemini API key is not configured on the server.")

    prompt = f"""
You are a cybersecurity assistant.

The user sent this message or email content:

\"\"\"{text}\"\"\"

Your job is to decide if this is:

- Safe
- Phishing
- Unclear

Rules:
- If the message is very normal, with no suspicious content, you can say Safe.
- Do NOT call something phishing only because it contains a link.
  For example, a short message like "please click on this link: www.google.com"
  is usually Safe, unless there are other strong red flags.

Answer EXACTLY in this format:

Judgment: <Safe|Phishing|Unclear>
Explanation: <one concise paragraph>
Tips:
- <short practical safety tip 1>
- <short practical safety tip 2>
"""

    try:
        response = _model.generate_content(prompt)
        raw = response.text.strip()
    except Exception as e:
        return _fallback_result(f"Gemini error: {e}")

    # ----- parse answer -----
    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    judgment = "Unclear"
    explanation = ""
    tips: List[str] = []

    for line in lines:
        low = line.lower()
        if low.startswith("judgment:"):
            value = line.split(":", 1)[1].strip().capitalize()
            if value in {"Safe", "Phishing", "Unclear"}:
                judgment = value
        elif low.startswith("explanation:"):
            explanation = line.split(":", 1)[1].strip()
        elif low.startswith("tips:"):
            # just a header
            continue
        elif line.startswith("-") or line.startswith("•"):
            tip = line.lstrip("-•").strip()
            if tip:
                tips.append(tip)

    if not explanation:
        explanation = raw

    if not tips:
        tips = [
            "Double-check the sender address and domain.",
            "Avoid clicking on links in messages you do not trust.",
        ]

    return {
        "judgment": judgment,
        "explanation": explanation,
        "tips": tips,
    }


# -------- Routes --------

@router.post("/", response_model=AnalyzeResponse)
def analyze_message(body: AnalyzeRequest):
    """
    Main analysis endpoint used by the Analyze page.
    """
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    ai_result = _call_gemini_for_analysis(body.text)

    return AnalyzeResponse(
        text=body.text,
        ai_result=ai_result,
    )


@router.get("/history")
def get_history():
    """
    Simple stub for dashboard/history.
    You can later connect this to MongoDB if you want to store analyses.
    """
    return []
