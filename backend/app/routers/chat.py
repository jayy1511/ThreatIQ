from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

from ..config import settings

router = APIRouter(prefix="/security-chat", tags=["security-chat"])

MODEL_NAME = "gemini-2.0-flash"

if settings.GEMINI_API_KEY:
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        print(f"Failed to initialize Gemini model {MODEL_NAME}: {e}")
        _model = None
else:
    _model = None


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str


# ---------- Helper to clean Markdown / bullets ----------

def _strip_markdown(text: str) -> str:
    """
    Strip the most common Markdown noise so the frontend sees plain text:
    - **bold**, __bold__
    - leading bullet markers (*, -, +)
    - headings starting with '#'
    """
    lines: list[str] = []

    for line in text.splitlines():
        s = line.strip()

        # Remove headings like "# Title", "## Tips"
        while s.startswith("#"):
            s = s.lstrip("#").strip()

        # Remove bullet markers at start of line
        for prefix in ("- ", "* ", "+ "):
            if s.startswith(prefix):
                s = s[len(prefix):].lstrip()
                break

        # Remove bold / italic markers
        s = s.replace("**", "").replace("__", "")

        # Strip surrounding single *…*
        if s.startswith("*") and s.endswith("*") and len(s) > 2:
            s = s[1:-1].strip()

        if s:
            lines.append(s)

    return "\n".join(lines)


@router.post("/", response_model=ChatResponse)
def security_chat(body: ChatRequest):
    """
    General security assistant chat (no auth required).

    - If the user pastes an email / link and asks "is this safe?"
      or "is this phishing?", classify + explain + give tips.
    - Otherwise, behave like a normal security assistant.
    """
    if _model is None:
        raise HTTPException(
            status_code=500,
            detail="Gemini model is not configured on the server.",
        )

    # Build text transcript from history
    history_lines = []
    for msg in body.history:
        role = msg.role.lower()
        prefix = "User" if role == "user" else "Assistant"
        history_lines.append(f"{prefix}: {msg.content}")

    history_text = "\n".join(history_lines)

    prompt = f"""
You are "ThreatIQ", a helpful cybersecurity assistant.

You have TWO modes:

1) If the user shares an email, SMS, DM, or link and asks things like
   "is this safe?", "is this phishing?", or "can you check this message?",
   you MUST:
   - Start your answer with a clear judgment on one line:
     Judgment: Safe
     Judgment: Phishing
     Judgment: Unclear
   - Then explain briefly why.
   - Then give 2–3 short, practical safety tips.

2) For any other question about cybersecurity (passwords, Wi-Fi, scams,
   data privacy, etc.), answer like a normal assistant: be clear, concise,
   and practical.

IF THE USER EXPLICITLY ASKS FOR A LIST (e.g. "list of do's and don'ts",
"give me tips", "steps", "checklist"):
- You MAY answer using a short numbered list like:
  1. ...
  2. ...
  3. ...
- Each item should be one short sentence.

OUTPUT RULES (VERY IMPORTANT):
- Answer in plain text only.
- You MAY use numbered lists with "1.", "2.", "3." on separate lines.
- Do NOT use Markdown bullets with '-' or '*'.
- Do NOT use Markdown formatting like **bold**, __bold__, or headings (#).
- Do NOT wrap the answer in JSON or code blocks.
- Keep answers reasonably short and concrete.

Conversation so far (if any):
{history_text}

Current user message:
{body.message}
"""

    try:
        response = _model.generate_content(prompt)
        reply_text = (response.text or "").strip()
        clean_text = _strip_markdown(reply_text)
        return ChatResponse(reply=clean_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")
