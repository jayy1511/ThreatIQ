from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .utils import decode_token
from .database import get_db as _get_db

auth_scheme = HTTPBearer()

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    try:
        return decode_token(creds.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def require_admin(current = Depends(get_current_user)):
    if current.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )
    return current

# Expose DB dependency for use in routes
def get_db() -> Session:
    return next(_get_db())
