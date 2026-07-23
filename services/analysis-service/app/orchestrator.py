"""
Analysis Service Orchestrator
Coordinates the analysis pipeline: Classifier -> Evidence -> Coach

C5: sender verification runs first (deterministic, no LLM) and feeds
a concise context string into the classifier prompt.
"""

import logging
from typing import Dict, Optional

from app.agents.classifier import classifier_agent
from app.agents.evidence import evidence_agent
from app.agents.coach import coach_agent
from app.schemas import AnalysisRequest, AnalysisResponse, LearningContext
from app.sender_verification import parse_and_verify, build_classifier_context

logger = logging.getLogger(__name__)


async def run_analysis(request: AnalysisRequest) -> Dict:
    """
    Run the complete analysis pipeline.

    Steps:
    0. Sender verification (C5) — deterministic, no LLM
    1. Classify the message (with optional sender context)
    2. Find similar examples (evidence)
    3. Generate coaching response

    Args:
        request: AnalysisRequest with message, user_guess, learning_context,
                 and optional header_text (C5).

    Returns:
        Complete analysis result including sender_verification.
    """
    logger.info("Starting analysis pipeline")

    # ── Step 0: Sender verification (C5) ─────────────────────────────────────
    logger.info("Step 0: Running sender verification")
    sender_verification = parse_and_verify(
        message=request.message,
        header_text=request.header_text,
    )
    sender_context = build_classifier_context(sender_verification)

    # ── Step 1: Classify the message ──────────────────────────────────────────
    logger.info("Step 1: Running Classifier Agent")
    classification = await classifier_agent.classify(
        request.message,
        sender_context=sender_context,
    )

    # Determine category
    category = classifier_agent.determine_category(
        classification['reason_tags'],
        request.message
    )

    # ── Step 2: Find similar examples ─────────────────────────────────────────
    logger.info("Step 2: Running Evidence Agent")
    similar_examples = await evidence_agent.find_evidence(
        message=request.message,
        reason_tags=classification['reason_tags'],
        category=category,
        max_examples=3
    )

    # ── Step 3: Generate coaching response ────────────────────────────────────
    logger.info("Step 3: Running Coach Agent")
    learning_context = {}
    if request.learning_context:
        learning_context = request.learning_context.model_dump()
    else:
        learning_context = {
            "total_messages": 0,
            "accuracy": 0.0,
            "weak_spots": [],
            "by_category": {},
            "is_new_user": True
        }

    coach_response = await coach_agent.generate_coaching(
        message=request.message,
        classification=classification,
        similar_examples=similar_examples,
        learning_context=learning_context
    )

    # Calculate was_correct if user_guess provided
    was_correct = None
    if request.user_guess:
        was_correct = request.user_guess.lower() == classification['label'].lower()

    logger.info("Analysis complete: %s | sender_verification: %s",
                classification['label'], sender_verification.get('status'))

    return {
        "classification":      classification,
        "coach_response":      coach_response,
        "was_correct":         was_correct,
        "category":            category,
        "sender_verification": sender_verification,
    }
