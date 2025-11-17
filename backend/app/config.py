from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    # Old JWT settings (still there but not used with Firebase)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "ThreatIQ")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")

    VIRUSTOTAL_API_KEY: str | None = os.getenv("VIRUSTOTAL_API_KEY")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "orca-mini-3b.Q4_0.gguf")
    DB_URL: str = os.getenv("DB_URL", "sqlite:///./threatiq.db")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    # MongoDB
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "threatiq")

    # Firebase (either JSON string or file path)
    FIREBASE_CREDENTIALS_JSON: str | None = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FIREBASE_CREDENTIALS_FILE: str | None = os.getenv("FIREBASE_CREDENTIALS_FILE")

settings = Settings()
