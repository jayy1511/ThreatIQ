import random
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import Analysis, User

def seed_data():
    db = SessionLocal()

    # Make sure we have a user (otherwise ForeignKey will fail)
    user = db.query(User).first()
    if not user:
        user = User(email="test@example.com", password_hash="fakehash", role="user")
        db.add(user)
        db.commit()
        db.refresh(user)

    # Clear old analyses
    db.query(Analysis).delete()
    db.commit()

    judgments = ["safe", "phishing", "other"]

    today = datetime.utcnow()
    for month_offset in range(6):  # last 6 months
        for i in range(random.randint(5, 15)):
            created_at = today - timedelta(days=30 * month_offset + random.randint(0, 29))
            judgment = random.choice(judgments)

            analysis = Analysis(
                user_id=user.id,
                text=f"Test message {i} month-{month_offset}",
                sender="system",
                result=judgment,  # put judgment string into result
                created_at=created_at,
            )
            db.add(analysis)

    db.commit()
    db.close()
    print("✅ Seeding complete!")

if __name__ == "__main__":
    seed_data()
