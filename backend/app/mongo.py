from pymongo import MongoClient
from datetime import datetime
from .config import settings

client = MongoClient(settings.MONGO_URL)
db = client[settings.MONGO_DB_NAME]

# Collection for storing analyses
analyses_collection = db["analyses"]


def serialize_analysis(doc: dict) -> dict:
    """
    Convert MongoDB document into a JSON-serializable dict for responses.
    """
    return {
        "id": str(doc.get("_id")),
        "user_id": doc.get("user_id"),
        "text": doc.get("text", ""),
        "sender": doc.get("sender") or "",
        "result": doc.get("result") or {},
        "created_at": doc.get("created_at", datetime.utcnow()),
    }
