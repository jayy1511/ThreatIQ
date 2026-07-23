"""
Analysis Router - Gateway endpoints that call Analysis Service

This router handles:
- /api/analyze (authenticated) - Full analysis with history
- /api/analyze/stream (authenticated) - Stage-based SSE streaming analysis
- /api/analyze-public (public) - Analysis without history
- /api/analysis-service/health - Health proxy for mobile cold-start detection
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import AnalysisRequest, PublicAnalysisRequest, AnalysisResponse
from app.routers.auth import verify_firebase_token
from app.core.rate_limit import check_rate_limit
from app.models.database import Database
from app.services.analysis_client import call_analysis_service as call_analysis_service_with_retry
from app.config import settings
import logging
import uuid
import json
import httpx

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
            learning_context=learning_context,
            header_text=getattr(request, 'header_text', None),
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
        
        # Read user's privacy preference for message text storage
        db = Database.get_db()
        user_profile = await db.user_profiles.find_one({"user_id": request.user_id})
        save_message_text = True  # safe default: preserve existing behaviour
        if user_profile is not None:
            save_message_text = user_profile.get("save_message_text", True)
        
        await InteractionLogger.log_interaction(
            user_id=request.user_id,
            message=request.message,
            user_guess=request.user_guess,
            classification=result['classification'],
            was_correct=was_correct,
            session_id=session_id,
            request_id=request.request_id,
            full_response=result,
            save_message_text=save_message_text,
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


# ---------------------------------------------------------------------------
# Helper: format a single SSE data line
# ---------------------------------------------------------------------------

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# ---------------------------------------------------------------------------
# Streaming analysis endpoint — gateway layer
# ---------------------------------------------------------------------------

@router.post("/analyze/stream")
async def analyze_message_stream(
    http_request: Request,
    request: AnalysisRequest,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Stage-based streaming analysis using SSE.

    Auth, rate-limiting, idempotency and DB writes are identical to
    /api/analyze.  The difference is that progress events are emitted
    to the client as each pipeline step completes in the analysis service.

    Event stages (in order):
      started → classification_started → classification_complete
      → evidence_started → evidence_complete
      → coach_started → coach_complete → complete | error
    """
    # ── Auth ──────────────────────────────────────────────────────────────
    if request.user_id != user_data.get("uid"):
        raise HTTPException(status_code=403, detail="User ID mismatch")

    # ── Rate limit ────────────────────────────────────────────────────────
    check_rate_limit(
        http_request,
        max_requests=settings.rate_limit_analysis,
        window_seconds=settings.rate_limit_analysis_window,
        user_id=request.user_id,
    )

    # ── Idempotency (same logic as /api/analyze) ──────────────────────────
    if request.request_id:
        db = Database.get_db()
        existing = await db.interactions.find_one({
            "user_id": request.user_id,
            "request_id": request.request_id,
        })
        if existing and existing.get("full_response"):
            logger.info("Idempotency hit for request_id %s (stream)", request.request_id)
            # Replay a minimal event stream from cache
            async def replay():
                yield _sse({"stage": "started", "message": "Analysis started (cached)"})
                yield _sse({"stage": "classification_complete", "message": "Classification complete"})
                yield _sse({"stage": "evidence_complete", "message": "Evidence gathered"})
                yield _sse({"stage": "coach_complete", "message": "Coaching explanation ready"})
                yield _sse({"stage": "complete", "message": "Analysis complete",
                            "result": existing["full_response"]})
            return StreamingResponse(replay(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    session_id = str(uuid.uuid4())

    # ── Learning context ──────────────────────────────────────────────────
    from app.agents.memory import memory_agent
    learning_context = await memory_agent.get_learning_context(request.user_id)

    # ── Build request payload for analysis service ────────────────────────
    payload = {
        "message": request.message,
        "user_guess": request.user_guess,
        "learning_context": learning_context,
    }
    # C5: forward optional header_text for sender verification
    if getattr(request, 'header_text', None):
        payload["header_text"] = request.header_text
    headers: dict = {"Content-Type": "application/json"}
    if settings.analysis_service_api_key:
        headers["X-Internal-Service-Key"] = settings.analysis_service_api_key

    # ── Generator: stream from analysis service → client ─────────────────
    async def event_generator():
        final_result: dict | None = None
        stream_error = False

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                async with client.stream(
                    "POST",
                    f"{settings.analysis_service_url}/analyze/stream",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.status_code != 200:
                        logger.error("Analysis service stream returned %s", resp.status_code)
                        yield _sse({"stage": "error", "message": "Analysis service unavailable"})
                        stream_error = True
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[len("data: "):]
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        # Pass event through to the client
                        yield _sse(event)

                        if event.get("stage") == "complete":
                            final_result = event.get("result")
                        elif event.get("stage") == "error":
                            stream_error = True

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error("Stream connection to analysis service failed: %s", exc)
            yield _sse({"stage": "error", "message": "Analysis service unavailable"})
            stream_error = True
        except Exception as exc:
            logger.error("Unexpected error in stream gateway: %s", exc, exc_info=True)
            yield _sse({"stage": "error", "message": "Analysis failed"})
            stream_error = True

        # ── After stream: write DB/profile (same as /api/analyze) ─────────
        if final_result and not stream_error:
            try:
                classification = final_result.get("classification", {})
                category = final_result.get("category", "general_phishing")
                was_correct = None
                if request.user_guess:
                    was_correct = request.user_guess.lower() == classification.get("label", "").lower()

                final_result["session_id"] = session_id
                final_result["was_correct"] = was_correct

                from app.tools.profile_tools import InteractionLogger
                await memory_agent.update_profile(
                    user_id=request.user_id,
                    category=category,
                    was_correct=was_correct,
                )

                db = Database.get_db()
                user_profile = await db.user_profiles.find_one({"user_id": request.user_id})
                save_message_text = True
                if user_profile is not None:
                    save_message_text = user_profile.get("save_message_text", True)

                await InteractionLogger.log_interaction(
                    user_id=request.user_id,
                    message=request.message,
                    user_guess=request.user_guess,
                    classification=classification,
                    was_correct=was_correct,
                    session_id=session_id,
                    request_id=request.request_id,
                    full_response=final_result,
                    save_message_text=save_message_text,
                )
            except Exception as exc:
                # Non-fatal: stream already delivered to client
                logger.error("Post-stream DB write failed: %s", exc, exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
