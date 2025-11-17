from sqlalchemy import text
from app.database import SessionLocal
import sys

def reassign(old_id: int = 1, new_id: int = 2):
    db = SessionLocal()
    try:
        # Optional: show counts before change
        r_before = db.execute(
            text("SELECT COUNT(*) as c FROM analyses WHERE user_id = :old"),
            {"old": old_id},
        ).fetchone()
        print(f"Analyses currently assigned to user {old_id}: {r_before.c}")

        # Perform update
        result = db.execute(
            text("UPDATE analyses SET user_id = :new WHERE user_id = :old"),
            {"new": new_id, "old": old_id},
        )
        db.commit()
        print(f"Reassigned {result.rowcount} analyses from user {old_id} -> user {new_id}")

        # Optional: show counts after change
        r_after_new = db.execute(
            text("SELECT COUNT(*) as c FROM analyses WHERE user_id = :new"),
            {"new": new_id},
        ).fetchone()
        print(f"Analyses now assigned to user {new_id}: {r_after_new.c}")
    except Exception as e:
        db.rollback()
        print("Error:", e)
    finally:
        db.close()

if __name__ == "__main__":
    # allow CLI args: old_id new_id
    if len(sys.argv) >= 3:
        old = int(sys.argv[1])
        new = int(sys.argv[2])
    else:
        old, new = 1, 2
    reassign(old, new)
