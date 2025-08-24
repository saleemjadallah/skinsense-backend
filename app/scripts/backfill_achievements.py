"""
Backfill achievements from skin_analyses.

Usage (from backend dir):
  python -m app.scripts.backfill_achievements
"""
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import ASCENDING
from app.database import get_database


def to_local_day_start_utc(ts: datetime, tz_offset_minutes: int) -> datetime:
    local = ts + timedelta(minutes=tz_offset_minutes)
    local_midnight = datetime(local.year, local.month, local.day)
    return local_midnight - timedelta(minutes=tz_offset_minutes)


def backfill(user_id: str | ObjectId | None = None, tz_offset_minutes: int = 0):
    db = get_database()

    query = {}
    if user_id is not None:
        query["user_id"] = ObjectId(str(user_id))

    db.skin_analyses.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    db.achievements.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)

    cursor = db.skin_analyses.find(query, {"user_id": 1, "created_at": 1}).sort("created_at", 1)
    count = 0
    for doc in cursor:
        uid = doc.get("user_id")
        created = doc.get("created_at")
        if not isinstance(uid, ObjectId) or not isinstance(created, datetime):
            continue
        day_start_utc = to_local_day_start_utc(created, tz_offset_minutes)
        db.achievements.update_one(
            {"user_id": uid, "date": day_start_utc},
            {
                "$setOnInsert": {"created_at": datetime.utcnow()},
                "$inc": {"photos_taken": 1},
            },
            upsert=True,
        )
        count += 1

    print(f"Backfilled {count} analysis events into achievements")


if __name__ == "__main__":
    backfill()


