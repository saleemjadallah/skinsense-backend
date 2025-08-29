#!/usr/bin/env python3
"""
Fix corrupted goals and achievements in MongoDB
This script will:
1. Remove goals with missing or null _id fields
2. Remove corrupted achievement records
3. Clean up any other data inconsistencies
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

def extract_db_name(url):
    """Extract database name from MongoDB URL"""
    if 'mongodb.net/' in url:
        url_without_params = url.split('?')[0]
        parts = url_without_params.split('/')
        if len(parts) > 3 and parts[-1]:
            return parts[-1]
    return 'skinpal'  # default

def main():
    load_dotenv()
    
    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URL'))
    db_name = extract_db_name(os.getenv('MONGODB_URL'))
    db = client[db_name]
    
    print(f"Connected to database: {db_name}")
    print("=" * 60)
    
    # Find the user
    user = db.users.find_one({'email': 'support@skinsense.app'})
    if not user:
        print("❌ User not found!")
        return
    
    user_id = user['_id']
    print(f"✅ Found user: {user['email']} (ID: {user_id})")
    print()
    
    # 1. Fix corrupted goals
    print("🔍 Analyzing goals collection...")
    
    total_goals = db.goals.count_documents({'user_id': user_id})
    valid_goals = db.goals.count_documents({'user_id': user_id, '_id': {'$ne': None, '$exists': True}})
    corrupted_goals = total_goals - valid_goals
    
    print(f"   Total goals: {total_goals}")
    print(f"   Valid goals: {valid_goals}")
    print(f"   Corrupted goals: {corrupted_goals}")
    
    if corrupted_goals > 0:
        print(f"🗑️  Removing {corrupted_goals} corrupted goals...")
        result = db.goals.delete_many({
            'user_id': user_id,
            '$or': [
                {'_id': None},
                {'_id': {'$exists': False}}
            ]
        })
        print(f"   ✅ Removed {result.deleted_count} corrupted goals")
    else:
        print("   ✅ No corrupted goals found")
    
    print()
    
    # 2. Fix corrupted achievements
    print("🔍 Analyzing achievements collection...")
    
    total_achievements = db.achievements.count_documents({'user_id': user_id})
    
    # Check for achievements with proper structure
    valid_achievements = db.achievements.count_documents({
        'user_id': user_id,
        'achievement_id': {'$exists': True, '$ne': None},
        'title': {'$exists': True, '$ne': None}
    })
    
    corrupted_achievements = total_achievements - valid_achievements
    
    print(f"   Total achievement records: {total_achievements}")
    print(f"   Valid achievements: {valid_achievements}")
    print(f"   Corrupted records: {corrupted_achievements}")
    
    if corrupted_achievements > 0:
        # Show what the corrupted records look like
        sample_corrupted = db.achievements.find_one({
            'user_id': user_id,
            '$or': [
                {'achievement_id': None},
                {'achievement_id': {'$exists': False}},
                {'title': None},
                {'title': {'$exists': False}}
            ]
        })
        
        if sample_corrupted:
            print(f"   Sample corrupted record fields: {list(sample_corrupted.keys())}")
        
        print(f"🗑️  Removing {corrupted_achievements} corrupted achievement records...")
        result = db.achievements.delete_many({
            'user_id': user_id,
            '$or': [
                {'achievement_id': None},
                {'achievement_id': {'$exists': False}},
                {'title': None},
                {'title': {'$exists': False}}
            ]
        })
        print(f"   ✅ Removed {result.deleted_count} corrupted achievement records")
    else:
        print("   ✅ No corrupted achievements found")
    
    print()
    
    # 3. Clean up goal_progress records for non-existent goals
    print("🔍 Cleaning up orphaned goal_progress records...")
    
    # Get all valid goal IDs
    valid_goal_ids = [goal['_id'] for goal in db.goals.find({'user_id': user_id}, {'_id': 1})]
    
    # Find progress records for non-existent goals
    orphaned_progress = db.goal_progress.count_documents({
        'user_id': user_id,
        'goal_id': {'$nin': valid_goal_ids}
    })
    
    if orphaned_progress > 0:
        print(f"🗑️  Removing {orphaned_progress} orphaned progress records...")
        result = db.goal_progress.delete_many({
            'user_id': user_id,
            'goal_id': {'$nin': valid_goal_ids}
        })
        print(f"   ✅ Removed {result.deleted_count} orphaned progress records")
    else:
        print("   ✅ No orphaned progress records found")
    
    print()
    
    # 4. Summary after cleanup
    print("📊 Final Summary:")
    print("=" * 60)
    
    final_goals = db.goals.count_documents({'user_id': user_id})
    final_achievements = db.achievements.count_documents({'user_id': user_id})
    final_progress = db.goal_progress.count_documents({'user_id': user_id})
    
    print(f"✅ Goals remaining: {final_goals}")
    print(f"✅ Achievements remaining: {final_achievements}")
    print(f"✅ Progress records remaining: {final_progress}")
    print()
    
    if final_goals > 0:
        # Show sample of remaining goals
        print("📋 Sample remaining goals:")
        sample_goals = db.goals.find({'user_id': user_id}).sort('created_at', -1).limit(3)
        for i, goal in enumerate(sample_goals, 1):
            print(f"   {i}. {goal.get('title', 'No title')} (Status: {goal.get('status', 'unknown')})")
    
    print()
    print("🎉 Database cleanup completed!")
    print("Your goals should now appear properly in the frontend.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)