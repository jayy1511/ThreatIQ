"""
Analysis Service - FastAPI Application

Stateless AI analysis microservice for ThreatIQ.
Handles message classification, evidence finding, and coaching.
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging

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

