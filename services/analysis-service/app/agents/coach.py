"""
Coach Agent - Generates personalized coaching responses
"""

from typing import Dict, List
import logging
import json

from app.llm.gemini_client import get_gemini_client
from app.schemas import CoachRawOutput

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    """Best-effort extraction of a JSON object from raw LLM output."""
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if "{" in candidate and "}" in candidate:
                text = candidate
                break

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


class CoachAgent:
    """Coach Agent - Generates personalized coaching, tips, and quizzes."""

    def __init__(self):
        self.gemini_client = get_gemini_client()

    async def generate_coaching(
        self,
        message: str,
        classification: Dict,
        similar_examples: List[Dict],
        learning_context: Dict,
    ) -> Dict:
        """Generate personalized coaching response."""
        try:
            prompt = self._build_coaching_prompt(
                message, classification, similar_examples, learning_context
            )

            response_text = await self.gemini_client.generate(
                prompt=prompt,
                system_instruction="",
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40,
                },
                use_cache=False,
            )

            json_text = _extract_json(response_text)
            raw_dict = json.loads(json_text)

            # Validate and normalise via Pydantic schema
            validated = CoachRawOutput.model_validate(raw_dict)
            result = validated.model_dump()

            # similar_examples come from the gateway/tool layer, not the LLM
            result["similar_examples"] = similar_examples

            logger.info("Generated coaching response for %s verdict", result["verdict"])
            return result

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error in coach: %s", exc)
            return self._get_fallback_response(classification, similar_examples)

        except Exception as exc:
            logger.error("Error generating coaching: %s", exc, exc_info=True)
            return self._get_fallback_response(classification, similar_examples)

    def _build_coaching_prompt(
        self,
        message: str,
        classification: Dict,
        similar_examples: List[Dict],
        learning_context: Dict,
    ) -> str:
        """Build the coaching prompt based on context."""
        user_level = "beginner" if learning_context.get("is_new_user", True) else "intermediate"
        weak_spots = learning_context.get("weak_spots", [])

        weak_spots_text = ""
        if weak_spots:
            weak_spots_text = f"\nThe user has struggled with: {', '.join(weak_spots)}."

        examples_text = ""
        if similar_examples:
            examples_text = "\n\nSIMILAR PHISHING EXAMPLES:\n"
            for i, ex in enumerate(similar_examples[:2], 1):
                examples_text += f"{i}. Category: {ex['category']}\n   Example: {ex['message'][:100]}...\n"

        label = classification.get("label", "unclear")
        confidence = classification.get("confidence", 0.5)
        reason_tags = classification.get("reason_tags", [])
        explanation = classification.get("explanation", "")

        prompt = f"""You are a security awareness coach. Help the user understand this message analysis.

MESSAGE ANALYZED:
{message}

CLASSIFICATION RESULT:
- Verdict: {label}
- Confidence: {confidence}
- Red Flags: {', '.join(reason_tags)}
- Reasoning: {explanation}

USER CONTEXT:
- Experience Level: {user_level}
- Total Messages Analyzed: {learning_context.get('total_messages', 0)}
- Current Accuracy: {learning_context.get('accuracy', 0):.1f}%{weak_spots_text}{examples_text}

Generate a coaching response as JSON with this EXACT structure:
{{
    "verdict": "{label}",
    "explanation": "Brief 2-3 sentence explanation. Be concise and direct. No markdown.",
    "tips": ["Short tip 1", "Short tip 2", "Short tip 3"],
    "quiz": {{
        "question": "One question about this message",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_answer": "Option X (must match exactly)"
    }}
}}

IMPORTANT RULES:
- explanation MUST be under 150 words (2-3 sentences max)
- tips should be 1 sentence each
- No markdown formatting"""

        return prompt

    def _get_default_tips(self, label: str) -> List[str]:
        """Get default tips based on label."""
        tips_map = {
            "phishing": [
                "Always verify the sender's email address carefully",
                "Hover over links before clicking to see the real URL",
                "Be suspicious of urgent language or threats",
            ],
            "safe": [
                "Continue being cautious with unexpected messages",
                "Always verify sender identity when in doubt",
                "Keep your security awareness skills sharp",
            ],
            "unclear": [
                "When in doubt, verify through official channels",
                "Don't click links in suspicious messages",
                "Contact the company directly using their official website",
            ],
        }
        return tips_map.get(label, tips_map["unclear"])

    def _get_fallback_response(self, classification: Dict, similar_examples: List[Dict]) -> Dict:
        """Get fallback response if AI generation or validation fails."""
        label = classification.get("label", "unclear")
        return {
            "verdict": label,
            "explanation": classification.get("explanation", "This message has been analyzed."),
            "similar_examples": similar_examples,
            "tips": self._get_default_tips(label),
            "quiz": None,
        }


coach_agent = CoachAgent()
