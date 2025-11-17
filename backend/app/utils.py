from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import json

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

from .config import settings

# Password hashing (kept for compatibility – not used with Firebase login)
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd.verify(plain, hashed)


def create_access_token(sub: str, role: str, email: str, expires_minutes: int = 120) -> str:
    """
    Old JWT-based token generator (no longer used with Firebase,
    but kept so nothing else in the codebase breaks).
    """
    payload = {
        "sub": sub,
        "role": role,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


# ---------- NEW: Firebase token verification ----------

_firebase_initialized = False


def _ensure_firebase():
    """
    Initialize Firebase Admin SDK once, using either:
      - FIREBASE_CREDENTIALS_JSON (full JSON string), or
      - FIREBASE_CREDENTIALS_FILE (path to JSON file)
    """
    global _firebase_initialized
    if _firebase_initialized:
        return

    cred_obj = None

    # Option 1: full JSON string in env var
    if settings.FIREBASE_CREDENTIALS_JSON:
        cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
        cred_obj = credentials.Certificate(cred_dict)

    # Option 2: path to JSON file (this is what you'll use)
    elif settings.FIREBASE_CREDENTIALS_FILE:
        with open(settings.FIREBASE_CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            cred_dict = json.load(f)
        cred_obj = credentials.Certificate(cred_dict)

    if cred_obj is None:
        raise RuntimeError(
            "Firebase credentials not configured. Set either "
            "FIREBASE_CREDENTIALS_FILE (path to JSON) or "
            "FIREBASE_CREDENTIALS_JSON (full JSON string)."
        )

    firebase_admin.initialize_app(cred_obj)
    _firebase_initialized = True


def decode_token(token: str) -> dict:
    """
    Verify a Firebase ID token and normalize it into:
    {
      'sub': <uid>,
      'email': <email>,
      'role': 'user' | ...
    }
    """
    _ensure_firebase()
    decoded = firebase_auth.verify_id_token(token)

    # Normalize fields so the rest of the app can use them
    decoded["sub"] = decoded.get("sub") or decoded.get("uid")
    if "role" not in decoded:
        decoded["role"] = "user"

    return decoded
