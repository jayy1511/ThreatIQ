"""
Analysis Router - Gateway endpoints that call Analysis Service

This router handles:
- /api/analyze (authenticated) - Full analysis with history
- /api/analyze-public (public) - Analysis without history
- /api/analysis-service/health - Health proxy for mobile cold-start detection
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.schemas import AnalysisRequest, PublicAnalysisRequest, AnalysisResponse
from app.routers.auth import verify_firebase_token
from app.core.rate_limit import check_rate_limit
from app.models.database import Database
from app.services.analysis_client import call_analysis_service as call_analysis_service_with_retry
from app.config import settings
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()



@router.get("/analysis-service/health")
async def analysis_service_health():
    """
    Health proxy to check if analysis service is ready.
    Used by mobile to detect cold starts before calling analyze.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.analysis_service_url}/")
            
            if response.status_code == 200:
                return {
                    "status": "ready",
                    "analysis_service": response.json()
                }
            else:
                return {
                    "status": "warming_up",
                    "message": f"Service returned {response.status_code}",
                    "retry_after_seconds": 30
                }
                
    except httpx.TimeoutException:
        return {
            "status": "warming_up",
            "message": "Service timeout - cold start in progress",
            "retry_after_seconds": 30
        }
    except httpx.ConnectError:
        return {
            "status": "unavailable",
            "message": "Cannot connect to analysis service",
            "retry_after_seconds": 60
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "retry_after_seconds": 30
        }


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_message(
    http_request: Request,
    request: AnalysisRequest,
    user_data: dict = Depends(verify_firebase_token)
):
    """
    Analyze a message for phishing using the multi-agent system.
    
    Args:
        request: AnalysisRequest with message and optional user_guess
        user_data: Verified user data from Firebase token
        
    Returns:
        Complete analysis response with classification and coaching
    """
    try:
        logger.info(f"Analysis request from user: {request.user_id}")
        
        if request.user_id != user_data.get('uid'):
            raise HTTPException(status_code=403, detail="User ID mismatch")
        
        # Rate limit by authenticated user
        check_rate_limit(
            http_request,
            max_requests=settings.rate_limit_analysis,
            window_seconds=settings.rate_limit_analysis_window,
            user_id=request.user_id,
        )
        
        # Idempotency check
        if request.request_id:
            db = Database.get_db()
            existing = await db.interactions.find_one({
                "user_id": request.user_id,
                "request_id": request.request_id
            })
            if existing and existing.get("full_response"):
                logger.info(f"Idempotency hit for request_id: {request.request_id}, returning cached response.")
                return existing["full_response"]
        
        # Generate session ID early
        session_id = str(uuid.uuid4())
        
        # Get learning context from memory agent
        from app.agents.memory import memory_agent
        learning_context = await memory_agent.get_learning_context(request.user_id)
        
        # Call analysis service with retry
        result = await call_analysis_service_with_retry(
            message=request.message,
            user_guess=request.user_guess,
            learning_context=learning_context
        )
        
        # Determine was_correct
        was_correct = None
        if request.user_guess:
            was_correct = request.user_guess.lower() == result['classification']['label'].lower()
        
        # Update profile and log interaction (gateway owns DB writes)
        from app.tools.profile_tools import InteractionLogger
        
        category = result.get('category', 'general_phishing')
        
        await memory_agent.update_profile(
            user_id=request.user_id,
            category=category,
            was_correct=was_correct
        )
        
        # Add session_id to result for response compatibility
        result['session_id'] = session_id
        result['was_correct'] = was_correct
        
        await InteractionLogger.log_interaction(
            user_id=request.user_id,
            message=request.message,
            user_guess=request.user_guess,
            classification=result['classification'],
            was_correct=was_correct,
            session_id=session_id,
            request_id=request.request_id,
            full_response=result
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analysis endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed")


@router.post("/analyze-public")
async def analyze_message_public(http_request: Request, request: PublicAnalysisRequest):
    """
    Public analysis endpoint (no auth required) for testing.
    Limited functionality - doesn't save to user profile.
    
    Accepts only message and optional user_guess.
    Does not accept user_id or request_id.
    """
    try:
        # Rate limit by IP (no auth)
        check_rate_limit(
            http_request,
            max_requests=settings.rate_limit_public,
            window_seconds=settings.rate_limit_public_window,
        )
        
        logger.info("Public analysis request (no auth)")
        
        # Call analysis service with retry (no learning context)
        result = await call_analysis_service_with_retry(
            message=request.message,
            user_guess=request.user_guess,
            learning_context=None
        )
        
        # Add session_id for response compatibility
        import uuid
        result['session_id'] = str(uuid.uuid4())
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in public analysis endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed")
