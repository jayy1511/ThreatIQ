"""
Analysis Service - FastAPI Application

Stateless AI analysis microservice for ThreatIQ.
Handles message classification, evidence finding, and coaching.
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
import logging
import json

from app.schemas import AnalysisRequest, AnalysisResponse
from app.orchestrator import run_analysis
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ThreatIQ Analysis Service",
    description="Stateless AI analysis microservice for phishing detection",
    version="1.0.0"
)

# CORS middleware (allow gateway to call this service)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Internal service, gateway handles real CORS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_internal_key(
    x_internal_service_key: Optional[str] = Header(None),
) -> None:
    """
    Verify that the caller presents the correct internal service API key.

    In production (key configured), rejects requests without a valid key.
    In development (no key configured), logs a warning and allows the request.
    """
    expected_key = settings.analysis_service_api_key

    if not expected_key:
        # No key configured — development mode, allow through with a warning
        logger.warning("ANALYSIS_SERVICE_API_KEY not set — skipping internal auth")
        return

    if not x_internal_service_key or x_internal_service_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "ThreatIQ Analysis Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_message(
    request: AnalysisRequest,
    _: None = Depends(verify_internal_key),
):
    """
    Analyze a message for phishing indicators.
    
    Requires a valid X-Internal-Service-Key header.
    
    This endpoint runs the complete analysis pipeline:
    1. Classifier Agent - Determines if message is phishing/safe/unclear
    2. Evidence Agent - Finds similar phishing examples
    3. Coach Agent - Generates educational coaching response
    
    Args:
        request: AnalysisRequest with message, optional user_guess and learning_context
        
    Returns:
        Complete analysis with classification, coaching, and evidence
    """
    try:
        logger.info(f"Received analysis request: {len(request.message)} chars")
        
        result = await run_analysis(request)
        
        return result
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed")


def _sse_line(event: dict) -> str:
    """Format a dict as a single SSE data line ending with double newline."""
    return f"data: {json.dumps(event)}\n\n"


@app.post("/analyze/stream")
async def analyze_message_stream(
    request: AnalysisRequest,
    _: None = Depends(verify_internal_key),
):
    """
    Stage-based streaming analysis endpoint.

    Yields SSE (Server-Sent Events) data lines as each pipeline step completes:
      started → classification_complete → evidence_complete → coach_complete → complete
    or an 'error' event on failure.

    This is the real pipeline: events are emitted AFTER each agent actually finishes,
    not faked timers.
    """

    async def event_generator():
        try:
            yield _sse_line({"stage": "started", "message": "Analysis started"})

            # ── Step 1: Classify ──────────────────────────────────────────────
            yield _sse_line({"stage": "classification_started", "message": "Classifying message…"})

            from app.agents.classifier import classifier_agent
            classification = await classifier_agent.classify(request.message)
            category = classifier_agent.determine_category(
                classification["reason_tags"],
                request.message,
            )
            yield _sse_line({
                "stage": "classification_complete",
                "message": "Classification complete",
                "data": {
                    "label": classification["label"],
                    "confidence": classification["confidence"],
                },
            })

            # ── Step 2: Evidence ──────────────────────────────────────────────
            yield _sse_line({"stage": "evidence_started", "message": "Gathering evidence…"})

            from app.agents.evidence import evidence_agent
            similar_examples = await evidence_agent.find_evidence(
                message=request.message,
                reason_tags=classification["reason_tags"],
                category=category,
                max_examples=3,
            )
            yield _sse_line({
                "stage": "evidence_complete",
                "message": "Evidence gathered",
                "data": {"examples_found": len(similar_examples)},
            })

            # ── Step 3: Coach ─────────────────────────────────────────────────
            yield _sse_line({"stage": "coach_started", "message": "Preparing coaching…"})

            from app.agents.coach import coach_agent
            learning_context: dict = {}
            if request.learning_context:
                learning_context = request.learning_context.model_dump()
            else:
                learning_context = {
                    "total_messages": 0,
                    "accuracy": 0.0,
                    "weak_spots": [],
                    "by_category": {},
                    "is_new_user": True,
                }

            coach_response = await coach_agent.generate_coaching(
                message=request.message,
                classification=classification,
                similar_examples=similar_examples,
                learning_context=learning_context,
            )
            yield _sse_line({"stage": "coach_complete", "message": "Coaching explanation ready"})

            # ── Final result ──────────────────────────────────────────────────
            was_correct = None
            if request.user_guess:
                was_correct = request.user_guess.lower() == classification["label"].lower()

            result = {
                "classification": classification,
                "coach_response": coach_response,
                "was_correct": was_correct,
                "category": category,
            }
            yield _sse_line({"stage": "complete", "message": "Analysis complete", "result": result})

        except Exception as exc:
            logger.error("Streaming analysis failed: %s", exc, exc_info=True)
            yield _sse_line({"stage": "error", "message": "Analysis failed"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable Nginx buffering
        },
    )


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup - fast, no blocking loads."""
    logger.info("Analysis Service starting up...")
    if not settings.analysis_service_api_key:
        logger.warning(
            "ANALYSIS_SERVICE_API_KEY is not set. "
            "The /analyze endpoint is unprotected. "
            "Set this variable in production."
        )
    logger.info("Dataset will load lazily on first request")
    logger.info("Analysis Service ready!")
