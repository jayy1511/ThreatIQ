import os
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import HTTPException, Header


# Build Firebase credentials from environment variables
firebase_credentials = {
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": "dummy",
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": "dummy",
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
}

cred = credentials.Certificate(firebase_credentials)

# Initialize Firebase admin SDK once
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)


def get_current_user(authorization: str = Header(None)):
    """
    Extracts Firebase token from Authorization header and verifies it.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = authorization.split(" ", 1)[1]

    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception as e:
        print("Firebase verification error:", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
