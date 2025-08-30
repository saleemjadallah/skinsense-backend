#!/usr/bin/env python3
"""
Script to check goals in the database and diagnose the user_id format issue
"""

import os
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to MongoDB
client = MongoClient(os.getenv("MONGODB_URL"))
db = client.skinpal

def check_goals():
    """Check all goals and their user_id formats"""
    print("=" * 80)
    print("CHECKING GOALS IN DATABASE")
    print("=" * 80)
    
    # Get all goals
    goals = list(db.goals.find().limit(20))
    
    print(f"\nTotal goals found: {db.goals.count_documents({})}")
    print(f"Showing first {len(goals)} goals:\n")
    
    for goal in goals:
        user_id = goal.get('user_id')
        print(f"Goal ID: {goal.get('_id')}")
        print(f"  Title: {goal.get('title')}")
        print(f"  User ID: {user_id}")
        print(f"  User ID Type: {type(user_id).__name__}")
        print(f"  Created: {goal.get('created_at')}")
        print(f"  Status: {goal.get('status')}")
        print("-" * 40)
    
    # Check for different user_id formats
    print("\n" + "=" * 80)
    print("USER_ID FORMAT ANALYSIS")
    print("=" * 80)
    
    # Count by type
    string_count = db.goals.count_documents({"user_id": {"$type": "string"}})
    objectid_count = db.goals.count_documents({"user_id": {"$type": "objectId"}})
    
    print(f"Goals with string user_id: {string_count}")
    print(f"Goals with ObjectId user_id: {objectid_count}")
    
    # Check for the specific user
    test_email = "support@skinsense.app"
    user = db.users.find_one({"email": test_email})
    
    if user:
        user_id = user.get('_id')
        print(f"\n" + "=" * 80)
        print(f"CHECKING GOALS FOR USER: {test_email}")
        print("=" * 80)
        print(f"User ID: {user_id} (type: {type(user_id).__name__})")
        
        # Try different queries
        goals_with_oid = list(db.goals.find({"user_id": user_id}).limit(5))
        goals_with_str = list(db.goals.find({"user_id": str(user_id)}).limit(5))
        
        print(f"\nGoals found with ObjectId query: {len(goals_with_oid)}")
        for g in goals_with_oid:
            print(f"  - {g.get('title')} (created: {g.get('created_at')})")
        
        print(f"\nGoals found with string query: {len(goals_with_str)}")
        for g in goals_with_str:
            print(f"  - {g.get('title')} (created: {g.get('created_at')})")
    else:
        print(f"\nUser with email {test_email} not found!")
    
    # Check skin_analyses for the same user
    if user:
        print(f"\n" + "=" * 80)
        print("CHECKING SKIN ANALYSES FOR SAME USER")
        print("=" * 80)
        
        analyses_with_oid = db.skin_analyses.count_documents({"user_id": user_id})
        analyses_with_str = db.skin_analyses.count_documents({"user_id": str(user_id)})
        
        print(f"Analyses with ObjectId user_id: {analyses_with_oid}")
        print(f"Analyses with string user_id: {analyses_with_str}")

if __name__ == "__main__":
    check_goals()