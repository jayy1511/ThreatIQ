"""
Gmail OAuth 2.0 service for authorization code flow.

Handles OAuth URL generation, token exchange, refresh, and storage.
"""

import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import urlencode
import httpx
from app.config import settings
from app.models.database import Database
from app.services.crypto import crypto_service

logger = logging.getLogger(__name__)


class GmailOAuthError(Exception):
    """Raised when Gmail OAuth operations fail."""
    pass


class GmailOAuthService:
    """
    Service for Gmail OAuth 2.0 authorization code flow.
    
    Implements secure OAuth with state parameter for CSRF protection.
    Tokens are encrypted before storage in MongoDB.
    """
    
    OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
    OAUTH_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/userinfo.email",
    ]
    
    def __init__(self):
        """Initialize the OAuth service."""
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri
        logger.info("GmailOAuthService initialized")
    
    # OAuth state lifetime in seconds (10 minutes)
    OAUTH_STATE_TTL_SECONDS = 600
    
    async def build_auth_url(self, user_id: str) -> Dict[str, str]:
        """
        Build OAuth authorization URL with secure server-side state.
        
        Generates a cryptographically random state token and stores it
        server-side in MongoDB bound to the user_id, with an expiration.
        The state sent to Google is an opaque token — user_id is never
        embedded in the URL.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            Dict with 'url' and 'state'
            
        Raises:
            GmailOAuthError: If state cannot be persisted
        """
        state = secrets.token_urlsafe(32)
        
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self.OAUTH_STATE_TTL_SECONDS)
        
        try:
            db = Database.get_db()
            await db.oauth_states.insert_one({
                "state": state,
                "user_id": user_id,
                "created_at": now,
                "expires_at": expires_at,
            })
        except Exception as e:
            logger.error("Failed to persist OAuth state", exc_info=True)
            raise GmailOAuthError("Failed to initiate Gmail authorization") from e
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        
        url = f"{self.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
        logger.info(f"Generated auth URL for user: {user_id}")
        
        return {"url": url, "state": state}
    
    async def _validate_and_consume_state(self, state: str) -> str:
        """
        Validate an OAuth state token and consume it atomically.
        
        Looks up the state in MongoDB, verifies it has not expired,
        and deletes it in a single atomic operation to prevent replay.
        
        Args:
            state: Opaque state token from the OAuth callback
            
        Returns:
            The user_id bound to this state
            
        Raises:
            GmailOAuthError: If state is invalid, expired, or already consumed
        """
        if not state or len(state) < 16:
            raise GmailOAuthError("Invalid OAuth callback request")
        
        db = Database.get_db()
        
        # Atomically find and delete the state document to prevent replay
        state_doc = await db.oauth_states.find_one_and_delete(
            {"state": state}
        )
        
        if not state_doc:
            logger.warning("OAuth state not found or already consumed")
            raise GmailOAuthError("Invalid OAuth callback request")
        
        # Verify the state has not expired (belt-and-suspenders; TTL index also cleans up)
        if datetime.utcnow() > state_doc["expires_at"]:
            logger.warning("OAuth state expired")
            raise GmailOAuthError("Authorization request expired, please try again")
        
        user_id = state_doc.get("user_id")
        if not user_id:
            logger.error("OAuth state document missing user_id")
            raise GmailOAuthError("Invalid OAuth callback request")
        
        return user_id
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, str]:
        """
        Validate state, then exchange authorization code for tokens.
        
        State is validated and consumed BEFORE the code is exchanged with
        Google, preventing CSRF and account-linking attacks.
        
        Args:
            code: Authorization code from OAuth callback
            state: Opaque state token from OAuth callback
            
        Returns:
            Dict with user_id and email
            
        Raises:
            GmailOAuthError: If state validation or token exchange fails
        """
        # --- Step 1: Validate and consume state BEFORE touching the code ---
        user_id = await self._validate_and_consume_state(state)
        
        # --- Step 2: Exchange code for tokens ---
        try:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.OAUTH_TOKEN_URL, data=data)
                
                if response.status_code != 200:
                    logger.error(f"Token exchange failed with status {response.status_code}")
                    raise GmailOAuthError("Token exchange with Google failed")
                
                token_data = response.json()
                
                user_email = await self._get_user_email(token_data["access_token"])
                
                await self.store_tokens(user_id, token_data, user_email)
                
                logger.info(f"Successfully exchanged code for tokens for user: {user_id}")
                return {"user_id": user_id, "email": user_email}
                
        except GmailOAuthError:
            raise
        except Exception as e:
            logger.error("Error exchanging code for tokens", exc_info=True)
            raise GmailOAuthError("Failed to exchange authorization code") from e
    
    async def _get_user_email(self, access_token: str) -> str:
        """
        Get user email from Google userinfo endpoint.
        
        Args:
            access_token: Valid access token
            
        Returns:
            User's Gmail email address
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.OAUTH_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    userinfo = response.json()
                    return userinfo.get("email", "")
                
                return ""
        except Exception as e:
            logger.warning(f"Failed to get user email: {e}")
            return ""
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, any]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            Dict with new access_token and expires_in
            
        Raises:
            GmailOAuthError: If token refresh fails
        """
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.OAUTH_TOKEN_URL, data=data)
                
                if response.status_code != 200:
                    logger.error(f"Token refresh failed: {response.text}")
                    raise GmailOAuthError(f"Token refresh failed: {response.status_code}")
                
                token_data = response.json()
                logger.info("Successfully refreshed access token")
                
                return {
                    "access_token": token_data["access_token"],
                    "expires_in": token_data.get("expires_in", 3600),
                }
                
        except GmailOAuthError:
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {e}", exc_info=True)
            raise GmailOAuthError("Failed to refresh access token") from e
    
    async def store_tokens(self, user_id: str, token_data: Dict, email: str) -> None:
        """
        Encrypt and store OAuth tokens in MongoDB.
        
        Args:
            user_id: Firebase user ID
            token_data: Token response from Google (access_token, refresh_token, expires_in)
            email: User's Gmail email
        """
        try:
            encrypted_access = crypto_service.encrypt_token(token_data["access_token"])
            encrypted_refresh = crypto_service.encrypt_token(token_data["refresh_token"])
            
            expiry_ts = int(time.time()) + token_data.get("expires_in", 3600)
            
            db = Database.get_db()
            tokens_collection = db["gmail_tokens"]
            
            await tokens_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "email": email,
                        "scopes": self.SCOPES,
                        "encrypted_access_token": encrypted_access,
                        "encrypted_refresh_token": encrypted_refresh,
                        "expiry_ts": expiry_ts,
                        "updated_at": time.time(),
                    },
                    "$setOnInsert": {
                        "created_at": time.time(),
                    }
                },
                upsert=True
            )
            
            logger.info(f"Stored encrypted tokens for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Error storing tokens: {e}", exc_info=True)
            raise GmailOAuthError("Failed to store tokens") from e
    
    async def get_tokens(self, user_id: str) -> Optional[Dict[str, any]]:
        """
        Retrieve and decrypt OAuth tokens for a user.
        Auto-refreshes if token is expired.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            Dict with access_token, refresh_token, email, scopes or None if not found
            
        Raises:
            GmailOAuthError: If token retrieval or refresh fails
        """
        try:
            db = Database.get_db()
            tokens_collection = db["gmail_tokens"]
            
            token_doc = await tokens_collection.find_one({"user_id": user_id})
            
            if not token_doc:
                return None
            
            current_time = int(time.time())
            is_expired = token_doc["expiry_ts"] <= current_time + 300
            
            if is_expired:
                logger.info(f"Token expired for user {user_id}, refreshing...")
                encrypted_refresh = token_doc["encrypted_refresh_token"]
                refresh_token = crypto_service.decrypt_token(encrypted_refresh)
                
                new_token_data = await self.refresh_access_token(refresh_token)
                
                encrypted_access = crypto_service.encrypt_token(new_token_data["access_token"])
                expiry_ts = int(time.time()) + new_token_data["expires_in"]
                
                await tokens_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "encrypted_access_token": encrypted_access,
                            "expiry_ts": expiry_ts,
                            "updated_at": time.time(),
                        }
                    }
                )
                
                access_token = new_token_data["access_token"]
            else:
                encrypted_access = token_doc["encrypted_access_token"]
                access_token = crypto_service.decrypt_token(encrypted_access)
            
            encrypted_refresh = token_doc["encrypted_refresh_token"]
            refresh_token = crypto_service.decrypt_token(encrypted_refresh)
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "email": token_doc.get("email", ""),
                "scopes": token_doc.get("scopes", []),
            }
            
        except Exception as e:
            logger.error(f"Error getting tokens for user {user_id}: {e}", exc_info=True)
            raise GmailOAuthError("Failed to retrieve tokens") from e
    
    async def revoke_tokens(self, user_id: str) -> bool:
        """
        Revoke and delete OAuth tokens for a user.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            True if tokens were deleted, False if no tokens found
        """
        try:
            db = Database.get_db()
            tokens_collection = db["gmail_tokens"]
            
            token_doc = await tokens_collection.find_one({"user_id": user_id})
            
            if not token_doc:
                return False
            
            try:
                encrypted_access = token_doc["encrypted_access_token"]
                access_token = crypto_service.decrypt_token(encrypted_access)
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        self.OAUTH_REVOKE_URL,
                        data={"token": access_token}
                    )
            except Exception as e:
                logger.warning(f"Failed to revoke token with Google: {e}")
            
            result = await tokens_collection.delete_one({"user_id": user_id})
            
            logger.info(f"Deleted tokens for user: {user_id}")
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error revoking tokens: {e}", exc_info=True)
            raise GmailOAuthError("Failed to revoke tokens") from e


gmail_oauth_service = GmailOAuthService()
