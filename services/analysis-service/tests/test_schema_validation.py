"""
Unit tests for LLM output validation schemas (B2).

These tests do NOT call Gemini. They verify that ClassifierRawOutput and
CoachRawOutput correctly validate, normalise, and fall back on bad input.
"""

import pytest
from pydantic import ValidationError

from app.schemas import ClassifierRawOutput, CoachRawOutput, QuizRawOutput


# ---------------------------------------------------------------------------
# ClassifierRawOutput tests
# ---------------------------------------------------------------------------

class TestClassifierRawOutput:

    def test_valid_phishing(self):
        result = ClassifierRawOutput.model_validate({
            "label": "phishing",
            "confidence": 0.9,
            "reason_tags": ["suspicious_link", "urgent_language"],
            "explanation": "Clear phishing attempt.",
        })
        assert result.label == "phishing"
        assert result.confidence == 0.9
        assert "suspicious_link" in result.reason_tags

    def test_valid_safe(self):
        result = ClassifierRawOutput.model_validate({
            "label": "safe",
            "confidence": 0.85,
            "reason_tags": [],
            "explanation": "Looks fine.",
        })
        assert result.label == "safe"

    def test_label_normalised_to_lowercase(self):
        result = ClassifierRawOutput.model_validate({
            "label": "PHISHING",
            "confidence": 0.8,
        })
        assert result.label == "phishing"

    def test_invalid_label_falls_back_to_unclear(self):
        result = ClassifierRawOutput.model_validate({
            "label": "DEFINITELY_A_SCAM",
            "confidence": 0.9,
        })
        assert result.label == "unclear"

    def test_missing_label_falls_back_to_unclear(self):
        result = ClassifierRawOutput.model_validate({
            "confidence": 0.5,
        })
        assert result.label == "unclear"

    def test_confidence_clamped_above_1(self):
        result = ClassifierRawOutput.model_validate({
            "label": "phishing",
            "confidence": 99.9,
        })
        assert result.confidence == 1.0

    def test_confidence_clamped_below_0(self):
        result = ClassifierRawOutput.model_validate({
            "label": "safe",
            "confidence": -5.0,
        })
        assert result.confidence == 0.0

    def test_confidence_string_coerced(self):
        result = ClassifierRawOutput.model_validate({
            "label": "safe",
            "confidence": "0.75",
        })
        assert result.confidence == pytest.approx(0.75)

    def test_invalid_confidence_falls_back_to_05(self):
        result = ClassifierRawOutput.model_validate({
            "label": "safe",
            "confidence": "not_a_number",
        })
        assert result.confidence == 0.5

    def test_reason_tags_defaults_to_empty_list(self):
        result = ClassifierRawOutput.model_validate({
            "label": "phishing",
            "confidence": 0.8,
        })
        assert result.reason_tags == []

    def test_reason_tags_non_list_replaced_with_empty(self):
        result = ClassifierRawOutput.model_validate({
            "label": "phishing",
            "confidence": 0.8,
            "reason_tags": "suspicious_link",  # wrong type
        })
        assert result.reason_tags == []

    def test_explanation_defaults(self):
        result = ClassifierRawOutput.model_validate({
            "label": "unclear",
            "confidence": 0.5,
        })
        assert result.explanation == "Analysis completed."

    def test_empty_dict_produces_safe_defaults(self):
        result = ClassifierRawOutput.model_validate({})
        assert result.label == "unclear"
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reason_tags, list)
        assert isinstance(result.explanation, str)


# ---------------------------------------------------------------------------
# CoachRawOutput tests
# ---------------------------------------------------------------------------

class TestCoachRawOutput:

    def test_valid_coach_response(self):
        result = CoachRawOutput.model_validate({
            "verdict": "phishing",
            "explanation": "This is a phishing email.",
            "tips": ["Tip 1", "Tip 2"],
            "quiz": {
                "question": "What is phishing?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        })
        assert result.verdict == "phishing"
        assert len(result.tips) == 2
        assert result.quiz is not None
        assert result.quiz.question == "What is phishing?"

    def test_verdict_normalised(self):
        result = CoachRawOutput.model_validate({"verdict": "SAFE"})
        assert result.verdict == "safe"

    def test_invalid_verdict_falls_back(self):
        result = CoachRawOutput.model_validate({"verdict": "banana"})
        assert result.verdict == "unclear"

    def test_tips_non_list_replaced_with_empty(self):
        result = CoachRawOutput.model_validate({
            "verdict": "safe",
            "tips": "just a string",
        })
        assert result.tips == []

    def test_missing_quiz_is_none(self):
        result = CoachRawOutput.model_validate({
            "verdict": "safe",
            "explanation": "ok",
            "tips": [],
        })
        assert result.quiz is None

    def test_empty_dict_produces_safe_defaults(self):
        result = CoachRawOutput.model_validate({})
        assert result.verdict == "unclear"
        assert isinstance(result.explanation, str)
        assert isinstance(result.tips, list)
        assert result.quiz is None


# ---------------------------------------------------------------------------
# QuizRawOutput tests
# ---------------------------------------------------------------------------

class TestQuizRawOutput:

    def test_valid_quiz(self):
        result = QuizRawOutput.model_validate({
            "question": "Is this safe?",
            "options": ["Yes", "No", "Maybe", "Unsure"],
            "correct_answer": "No",
        })
        assert result.question == "Is this safe?"
        assert result.options == ["Yes", "No", "Maybe", "Unsure"]

    def test_options_non_list_replaced_with_empty(self):
        result = QuizRawOutput.model_validate({
            "question": "Q?",
            "options": "Yes, No",
            "correct_answer": "Yes",
        })
        assert result.options == []
