# backend/app/reassign_analyses.py
from sqlalchemy import text
from app.database import SessionLocal

def reassign(old_id: int = 1, new_id: int = 2):
    db = SessionLocal()
    try:
        query = text("UPDATE analyses SET user_id = :new WHERE user_id = :old")
        result = db.execute(query, {"new": new_id, "old": old_id})
        db.commit()
        print(f"✅ Reassigned {result.rowcount} analyses from user {old_id} -> user {new_id}")
    except Exception as e:
        db.rollback()
        print("Error:", e)
    finally:
        db.close()

if __name__ == "__main__":
    reassign(1, 2)
