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
from app.config import settings
import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

# Retry configuration for Render cold starts
MAX_RETRIES = 5
RETRY_DELAYS = [2, 4, 8, 16, 20]  # Exponential backoff (seconds)
RETRYABLE_STATUS_CODES = {502, 503, 504}
REQUEST_TIMEOUT = 120.0  # Increased for cold starts


async def call_analysis_service_with_retry(
    message: str, 
    user_guess: str = None, 
    learning_context: dict = None
) -> dict:
    """
    Call the analysis-service with retry logic for Render cold starts.
    
    Implements exponential backoff for 502/503/504 errors and timeouts.
    Sends X-Internal-Service-Key header for internal authentication.
    """
    payload = {
        "message": message,
        "user_guess": user_guess,
        "learning_context": learning_context
    }
    
    # Build internal service auth headers
    headers = {"Content-Type": "application/json"}
    if settings.analysis_service_api_key:
        headers["X-Internal-Service-Key"] = settings.analysis_service_api_key
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Analysis service call attempt {attempt + 1}/{MAX_RETRIES}")
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{settings.analysis_service_url}/analyze",
                    json=payload,
                    headers=headers,
                )
                
                # Success
                if response.status_code == 200:
                    logger.info(f"Analysis service succeeded on attempt {attempt + 1}")
                    return response.json()
                
                # Retryable error (cold start)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    logger.warning(
                        f"Analysis service returned {response.status_code} on attempt {attempt + 1}, "
                        f"likely cold start - will retry"
                    )
                    last_error = f"Service returned {response.status_code}"
                    
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                        logger.info(f"Waiting {delay}s before retry...")
                        await asyncio.sleep(delay)
                        continue
                
                # Non-retryable error
                logger.error(f"Analysis service returned {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Analysis service error: {response.status_code}"
                )
                
        except httpx.TimeoutException:
            logger.warning(f"Analysis service timeout on attempt {attempt + 1}")
            last_error = "Request timeout"
            
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.info(f"Waiting {delay}s before retry...")
                await asyncio.sleep(delay)
                continue
                
        except httpx.ConnectError:
            logger.warning(f"Cannot connect to analysis service on attempt {attempt + 1}")
            last_error = "Connection failed"
            
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.info(f"Waiting {delay}s before retry...")
                await asyncio.sleep(delay)
                continue
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            last_error = str(e)
            
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                await asyncio.sleep(delay)
                continue
    
    # All retries exhausted
    logger.error(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")
    raise HTTPException(
        status_code=502,
        detail="Analysis service warming up, please retry in 30 seconds"
    )


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
        
        await InteractionLogger.log_interaction(
            user_id=request.user_id,
            message=request.message,
            user_guess=request.user_guess,
            classification=result['classification'],
            was_correct=was_correct,
            session_id=None,
            request_id=request.request_id
        )
        
        # Add session_id to result for response compatibility
        import uuid
        result['session_id'] = str(uuid.uuid4())
        result['was_correct'] = was_correct
        
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
