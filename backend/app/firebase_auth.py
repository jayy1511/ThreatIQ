import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, Header

# Load Firebase key
cred = credentials.Certificate("firebase-admin-key.json")

# Initialize Firebase app
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

def get_current_user(authorization: str = Header(None)):
    """
    Extracts Firebase ID token and verifies it.
    Returns decoded user dict:
    {
        "uid": ...,
        "email": ...
    }
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = authorization.split(" ", 1)[1]

    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
