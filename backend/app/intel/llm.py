import google.generativeai as genai
from ..config import settings

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

def analyze_with_gemini(user_text: str, heuristics: dict):
    if not settings.GEMINI_API_KEY:
        return {"error": "Gemini API key not configured"}

    prompt = f"""
    You are a phishing awareness assistant.
    The user submitted this message:

    {user_text}

    Here are heuristic analysis results:
    {heuristics}

    Your task:
    1. Decide if this looks like phishing or safe.
    2. Explain briefly why.
    3. Provide 2 short safety tips.

    Respond strictly in JSON with fields:
    - judgment (Phishing or Safe)
    - explanation
    - tips (array of 2 strings)
    """

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return {"error": str(e)}