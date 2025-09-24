from app.database import SessionLocal
from app.models import Analysis
from datetime import datetime, timedelta
import random, json

def seed_data():
    db = SessionLocal()
    try:
        # Clear old
        db.query(Analysis).delete()
        db.commit()

        today = datetime.utcnow()
        judgments = ["safe", "phishing"]

        for month_offset in range(6):  # last 6 months
            for i in range(10):  # 10 analyses per month
                created_at = today - timedelta(days=30 * month_offset + i)
                judgment = random.choice(judgments)

                analysis = Analysis(
                    user_id=2,  # 👈 put it under user 2
                    text=f"Seeded analysis {i} month-{month_offset}",
                    sender="system",
                    result=json.dumps({
                        "judgment": judgment,
                        "explanation": f"This is a {judgment} example.",
                        "tips": ["Tip 1", "Tip 2"]
                    }),
                    created_at=created_at
                )
                db.add(analysis)

        db.commit()
        print("✅ Seed data inserted for user 2")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
