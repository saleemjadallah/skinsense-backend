#!/usr/bin/env python3
"""Debug achievement issues for a specific user"""

import os
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import sys

# MongoDB connection
MONGODB_URL = "mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal"

def debug_user_achievements(email):
    """Debug achievements for a user by email"""
    
    client = MongoClient(MONGODB_URL)
    db = client.skinpal
    
    print(f"\n🔍 Debugging achievements for: {email}")
    print("=" * 60)
    
    # Find user
    user = db.users.find_one({"email": email})
    if not user:
        print(f"❌ User not found: {email}")
        return
    
    user_id = user["_id"]
    print(f"✓ User found: {user_id}")
    print(f"  Name: {user.get('username', 'N/A')}")
    print(f"  Created: {user.get('created_at', 'N/A')}")
    
    # Count skin analyses
    analyses_count = db.skin_analyses.count_documents({"user_id": user_id})
    print(f"\n📊 Skin Analyses: {analyses_count}")
    
    # List all analyses
    analyses = list(db.skin_analyses.find(
        {"user_id": user_id},
        {"_id": 1, "created_at": 1, "status": 1}
    ).sort("created_at", -1))
    
    for i, analysis in enumerate(analyses[:5], 1):
        print(f"  {i}. {analysis['_id']} - {analysis.get('created_at', 'N/A')} - Status: {analysis.get('status', 'N/A')}")
    
    # Check user_achievements collection
    print(f"\n🏆 Achievement Records:")
    achievements = list(db.user_achievements.find({"user_id": str(user_id)}))
    
    if not achievements:
        print("  ⚠️  No achievement records found! (This is the problem)")
        print("  Creating achievement records now...")
        
        # Initialize achievements
        from app.services.achievement_service import AchievementService
        service = AchievementService()
        service.initialize_user_achievements(str(user_id))
        
        achievements = list(db.user_achievements.find({"user_id": str(user_id)}))
    
    # Show First Glow and Progress Pioneer status
    for ach in achievements:
        if ach["achievement_id"] in ["first_glow", "progress_pioneer"]:
            print(f"\n  📌 {ach['achievement_id']}:")
            print(f"     Progress: {ach.get('progress', 0) * 100:.0f}%")
            print(f"     Unlocked: {ach.get('is_unlocked', False)}")
            print(f"     Progress Data: {ach.get('progress_data', {})}")
            print(f"     Last Updated: {ach.get('last_updated', 'Never')}")
    
    # Check achievement_actions collection
    print(f"\n📝 Achievement Actions:")
    actions_count = db.achievement_actions.count_documents({
        "user_id": str(user_id),
        "action_type": "skin_analysis_completed"
    })
    print(f"  skin_analysis_completed actions: {actions_count}")
    
    # Force sync achievements
    print(f"\n🔄 Force syncing achievements from existing data...")
    from app.services.achievement_service import AchievementService
    service = AchievementService()
    
    # Sync from existing data
    sync_result = service.sync_achievements_from_existing_data(str(user_id))
    print(f"  Synced {sync_result['synced_achievements']} achievements")
    print(f"  Analysis count: {sync_result['analysis_count']}")
    
    # Check First Glow after sync
    first_glow = db.user_achievements.find_one({
        "user_id": str(user_id),
        "achievement_id": "first_glow"
    })
    
    if first_glow:
        print(f"\n✅ First Glow Status After Sync:")
        print(f"   Progress: {first_glow.get('progress', 0) * 100:.0f}%")
        print(f"   Unlocked: {first_glow.get('is_unlocked', False)}")
        print(f"   Progress Data: {first_glow.get('progress_data', {})}")
    
    # Check Progress Pioneer
    progress_pioneer = db.user_achievements.find_one({
        "user_id": str(user_id),
        "achievement_id": "progress_pioneer"
    })
    
    if progress_pioneer:
        print(f"\n✅ Progress Pioneer Status After Sync:")
        print(f"   Progress: {progress_pioneer.get('progress', 0) * 100:.0f}%")
        print(f"   Unlocked: {progress_pioneer.get('is_unlocked', False)}")
        print(f"   Photo Count: {progress_pioneer.get('progress_data', {}).get('photo_count', 0)}")
    
    print("\n" + "=" * 60)
    print("Debug complete!\n")

if __name__ == "__main__":
    # Add backend directory to path
    sys.path.insert(0, '/Users/saleemjadallah/Desktop/SkinSense(Dev)/backend')
    
    # Debug the Apple user
    debug_user_achievements("saleem86@icloud.com")