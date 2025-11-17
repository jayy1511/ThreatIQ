from fastapi import APIRouter, Depends
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me", response_model=dict)
def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Return the currently authenticated user based on Firebase ID token.
    """
    return {
        "id": current_user.get("sub") or current_user.get("uid"),
        "email": current_user.get("email"),
        "role": current_user.get("role", "user"),
    }
