"""
Gmail integration API endpoints.

Provides OAuth connection, status, triage, and history endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import RedirectResponse
from app.routers.auth import verify_firebase_token
from app.core.rate_limit import check_rate_limit
from app.services.gmail_oauth import gmail_oauth_service, GmailOAuthError
from app.services.gmail_triage import gmail_triage_service, GmailTriageError
from app.models.schemas import (
    GmailStatusResponse,
    GmailConnectResponse,
    GmailTriageRequest,
    GmailTriageResponse,
    GmailTriageResult,
    GmailHistoryResponse,
    GmailTriageRecord,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gmail/connect", response_model=GmailConnectResponse)
async def connect_gmail(user_data: dict = Depends(verify_firebase_token)):
    """
    Generate OAuth authorization URL for Gmail connection.
    
    Requires Firebase authentication.
    
    Returns:
        OAuth URL for user to authorize Gmail access
    """
    try:
        user_id = user_data.get('uid')
        
        auth_data = await gmail_oauth_service.build_auth_url(user_id)
        
        logger.info(f"Generated Gmail auth URL for user: {user_id}")
        
        return GmailConnectResponse(url=auth_data['url'])
        
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")


@router.get("/gmail/callback")
async def gmail_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter")
):
    """
    OAuth callback endpoint.
    
    Exchanges authorization code for tokens and stores them encrypted.
    Redirects to frontend dashboard with success/error status.
    
    No Firebase auth required (state parameter validates user).
    """
    try:
        result = await gmail_oauth_service.exchange_code_for_tokens(code, state)
        
        logger.info(f"OAuth callback successful for user: {result['user_id']}")
        
        redirect_url = f"{settings.frontend_url}/dashboard?gmail=connected"
        return RedirectResponse(url=redirect_url)
        
    except GmailOAuthError as e:
        logger.error(f"OAuth callback error: {e}")
        redirect_url = f"{settings.frontend_url}/dashboard?gmail=error"
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        logger.error(f"Unexpected error in OAuth callback: {e}", exc_info=True)
        redirect_url = f"{settings.frontend_url}/dashboard?gmail=error"
        return RedirectResponse(url=redirect_url)


@router.get("/gmail/status", response_model=GmailStatusResponse)
async def get_gmail_status(user_data: dict = Depends(verify_firebase_token)):
    """
    Get Gmail connection status for the authenticated user.
    
    Returns:
        Connection status, email, and scopes if connected
    """
    try:
        user_id = user_data.get('uid')
        
        tokens = await gmail_oauth_service.get_tokens(user_id)
        
        if not tokens:
            return GmailStatusResponse(connected=False)
        
        return GmailStatusResponse(
            connected=True,
            email=tokens.get('email'),
            scopes=tokens.get('scopes')
        )
        
    except GmailOAuthError as e:
        logger.error(f"Error checking Gmail status: {e}")
        return GmailStatusResponse(connected=False)
    except Exception as e:
        logger.error(f"Unexpected error checking Gmail status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check Gmail status")


@router.post("/gmail/disconnect")
async def disconnect_gmail(user_data: dict = Depends(verify_firebase_token)):
    """
    Disconnect Gmail by revoking and deleting stored tokens.
    
    Returns:
        Success confirmation
    """
    try:
        user_id = user_data.get('uid')
        
        deleted = await gmail_oauth_service.revoke_tokens(user_id)
        
        if deleted:
            logger.info(f"Disconnected Gmail for user: {user_id}")
            return {"ok": True, "message": "Gmail disconnected successfully"}
        else:
            return {"ok": True, "message": "No Gmail connection found"}
        
    except GmailOAuthError as e:
        logger.error(f"Error disconnecting Gmail: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect Gmail")
    except Exception as e:
        logger.error(f"Unexpected error disconnecting Gmail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to disconnect Gmail")


@router.post("/gmail/triage", response_model=GmailTriageResponse)
async def triage_inbox(
    http_request: Request,
    request: GmailTriageRequest,
    user_data: dict = Depends(verify_firebase_token)
):
    """
    Triage Gmail inbox using ThreatIQ analysis.
    
    Fetches unread messages, analyzes each with ThreatIQ,
    applies labels, and optionally marks spam or archives.
    
    Args:
        request: Triage parameters (limit, mark_spam, archive_safe)
    
    Returns:
        Processing results with classified messages
    """
    try:
        user_id = user_data.get('uid')
        
        # Rate limit by authenticated user
        check_rate_limit(
            http_request,
            max_requests=settings.rate_limit_gmail_triage,
            window_seconds=settings.rate_limit_gmail_triage_window,
            user_id=user_id,
        )
        
        logger.info(f"Starting inbox triage for user {user_id}")
        
        result = await gmail_triage_service.triage_inbox(
            user_id=user_id,
            limit=request.limit,
            mark_spam=request.mark_spam,
            archive_safe=request.archive_safe
        )
        
        triage_results = []
        for item in result['results']:
            triage_results.append(
                GmailTriageResult(
                    message_id=item.get('message_id', ''),
                    from_=item.get('from', ''),
                    subject=item.get('subject', ''),
                    label=item.get('label', 'UNKNOWN'),
                    confidence=item.get('confidence', 0.0),
                    reasons=item.get('reasons', []),
                    label_applied=item.get('label_applied', False),
                    success=item.get('success', False),
                    error=item.get('error')
                )
            )
        
        return GmailTriageResponse(
            processed=result['processed'],
            results=triage_results
        )
        
    except GmailTriageError as e:
        logger.error(f"Triage error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during triage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to triage inbox")


@router.get("/gmail/history", response_model=GmailHistoryResponse)
async def get_triage_history(
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    user_data: dict = Depends(verify_firebase_token)
):
    """
    Get Gmail triage history for the authenticated user.
    
    Args:
        limit: Maximum number of records to return (1-100)
    
    Returns:
        List of historical triage records
    """
    try:
        user_id = user_data.get('uid')
        
        records = await gmail_triage_service.get_triage_history(user_id, limit)
        
        triage_records = []
        for record in records:
            triage_records.append(
                GmailTriageRecord(
                    _id=record.get('_id', ''),
                    user_id=record.get('user_id', ''),
                    gmail_message_id=record.get('gmail_message_id', ''),
                    thread_id=record.get('thread_id', ''),
                    from_=record.get('from', ''),
                    subject=record.get('subject', ''),
                    date=record.get('date', ''),
                    snippet=record.get('snippet', ''),
                    body_excerpt=record.get('body_excerpt', ''),
                    label=record.get('label', ''),
                    confidence=record.get('confidence', 0.0),
                    reasons=record.get('reasons', []),
                    label_applied=record.get('label_applied', False),
                    created_at=record.get('created_at')
                )
            )
        
        return GmailHistoryResponse(items=triage_records)
        
    except Exception as e:
        logger.error(f"Error fetching triage history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch triage history")
