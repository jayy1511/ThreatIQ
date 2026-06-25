from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth
from app.config import settings
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

try:
    private_key = settings.firebase_private_key.replace('\\n', '\n')
    
    cred_dict = {
        "type": "service_account",
        "project_id": settings.firebase_project_id,
        "private_key": private_key,
        "client_email": settings.firebase_client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialized successfully")
    
except Exception as e:
    logger.warning(f"Firebase initialization failed: {e}. Auth endpoints will not work.")


async def verify_firebase_token(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify Firebase ID token from Authorization header.
    
    Args:
        authorization: Authorization header with Bearer token
        
    Returns:
        Decoded token data with user info
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        parts = authorization.split(' ')
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        token = parts[1]
        
        decoded_token = auth.verify_id_token(token)
        
        logger.info(f"Token verified for user: {decoded_token.get('uid')}")
        return decoded_token
        
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Firebase token expired")
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        raise HTTPException(status_code=401, detail="Token verification failed")


async def verify_admin_user(user_data: dict = Depends(verify_firebase_token)) -> dict:
    """
    Verify that the authenticated user has admin privileges.

    Checks for the ``admin`` custom claim set via the Firebase Admin SDK
    (``auth.set_custom_user_claims(uid, {"admin": True})``).

    Returns:
        Decoded token data (same shape as verify_firebase_token)

    Raises:
        HTTPException 403: If the user is authenticated but not an admin
    """
    # Firebase custom claims are merged into the decoded token dict
    if not user_data.get("admin", False):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
        )
    return user_data


@router.post("/verify-token")
async def verify_token_endpoint(user_data: dict = Depends(verify_firebase_token)):
    """
    Endpoint to verify a Firebase token.
    Used by frontend to validate authentication.
    """
    return {
        "valid": True,
        "uid": user_data.get('uid'),
        "email": user_data.get('email')
    }
