#!/usr/bin/env python3
"""Verify user progress shows correctly after fix"""

import os
import sys
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

def check_progress():
    # Connect to MongoDB
    mongodb_url = os.getenv("MONGODB_URL")
    if mongodb_url and "mongodb+srv" in mongodb_url:
        if "?" in mongodb_url:
            mongodb_url += "&tlsAllowInvalidCertificates=true"
        else:
            mongodb_url += "?tlsAllowInvalidCertificates=true"
    client = MongoClient(mongodb_url)
    db = client.skinpal

    # Find user
    user = db.users.find_one({"email": "saleem86@gmail.com"})
    user_id = user["_id"]
    
    print("\n=== PROGRESS VERIFICATION ===\n")

    # Check latest skin analysis
    latest = db.skin_analyses.find_one(
        {"user_id": user_id, "status": "completed"},
        sort=[("created_at", -1)]
    )
    
    if latest and "orbo_response" in latest:
        score = latest["orbo_response"].get("overall_skin_health_score", 0)
        print(f"✓ Latest Skin Score: {score}/100")
    
    # Check achievements and streak
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    total = 0
    streak = 0
    expected = today
    
    achievements = list(db.achievements.find({"user_id": user_id}).sort("date", -1))
    
    for ach in achievements:
        photos = ach.get('photos_taken', 0)
        total += photos
        
        if photos > 0:
            ach_date = ach['date'].replace(hour=0, minute=0, second=0, microsecond=0)
            if ach_date == expected:
                streak += 1
                expected = expected - timedelta(days=1)
            elif ach_date < expected:
                break
    
    print(f"✓ Total Photos: {total}")
    print(f"✓ Current Streak: {streak} days")
    
    # Check if today has photos
    today_ach = db.achievements.find_one({"user_id": user_id, "date": today})
    today_photos = today_ach.get('photos_taken', 0) if today_ach else 0
    print(f"✓ Today's Photos: {today_photos}")
    
    # Calculate improvement (compare oldest to newest)
    analyses = list(db.skin_analyses.find(
        {"user_id": user_id, "status": "completed", "orbo_response": {"$exists": True}}
    ).sort("created_at", 1))
    
    if len(analyses) >= 2:
        oldest_score = analyses[0]["orbo_response"].get("overall_skin_health_score", 0)
        newest_score = analyses[-1]["orbo_response"].get("overall_skin_health_score", 0)
        improvement = ((newest_score - oldest_score) / oldest_score * 100) if oldest_score > 0 else 0
        print(f"✓ Overall Improvement: +{improvement:.1f}%")
    
    print("\n=== PROGRESS SHOULD NOW SHOW IN APP! ===")
    
    client.close()

check_progress()
