#!/usr/bin/env python3
"""Fix plans data in MongoDB - remove None values from routine_ids and goal_ids"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import pymongo
from bson import ObjectId
from datetime import datetime

# MongoDB connection
mongodb_url = os.getenv('MONGODB_URL')
client = pymongo.MongoClient(mongodb_url)
db = client.skinpal

print("=" * 60)
print("Fixing Plans Data in MongoDB")
print("=" * 60)

# Get all plans
plans = list(db.plans.find())
print(f"\nFound {len(plans)} plans to check")

fixed_count = 0
for plan in plans:
    plan_id = plan["_id"]
    user_id = plan.get("user_id")
    
    # Check routine_ids and goal_ids
    routine_ids = plan.get("routine_ids", [])
    goal_ids = plan.get("goal_ids", [])
    
    # Clean routine_ids - remove None values
    cleaned_routine_ids = [rid for rid in routine_ids if rid is not None]
    
    # Clean goal_ids - remove None values  
    cleaned_goal_ids = [gid for gid in goal_ids if gid is not None]
    
    # Check if we need to update
    needs_update = (len(cleaned_routine_ids) != len(routine_ids) or 
                   len(cleaned_goal_ids) != len(goal_ids))
    
    if needs_update:
        print(f"\n✗ Plan {plan_id} needs fixing:")
        print(f"  User: {user_id}")
        print(f"  Original routine_ids: {routine_ids}")
        print(f"  Cleaned routine_ids: {cleaned_routine_ids}")
        print(f"  Original goal_ids: {goal_ids}")
        print(f"  Cleaned goal_ids: {cleaned_goal_ids}")
        
        # Update the plan
        db.plans.update_one(
            {"_id": plan_id},
            {"$set": {
                "routine_ids": cleaned_routine_ids,
                "goal_ids": cleaned_goal_ids,
                "updated_at": datetime.utcnow()
            }}
        )
        fixed_count += 1
        print(f"  ✓ Fixed!")
    else:
        print(f"✓ Plan {plan_id} is OK")

print(f"\n" + "=" * 60)
print(f"Fixed {fixed_count} plans")

# Now let's also create some routines and goals for the support user if they don't exist
support_user = db.users.find_one({"email": "support@skinsense.app"})
if support_user:
    user_id = support_user["_id"]
    print(f"\nChecking routines and goals for support@skinsense.app (ID: {user_id})")
    
    # Check existing routines
    existing_routines = list(db.routines.find({"user_id": user_id}))
    print(f"  Existing routines: {len(existing_routines)}")
    
    if len(existing_routines) == 0:
        print("  Creating sample routines...")
        
        routines_data = [
            {
                "user_id": user_id,
                "name": "Morning Hydration Boost",
                "type": "morning",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "steps": [
                    {"order": 1, "name": "Gentle Foam Cleanser", "duration": 60, "product": "CeraVe Hydrating Cleanser"},
                    {"order": 2, "name": "Hydrating Toner", "duration": 30, "product": "Klairs Supple Preparation Toner"},
                    {"order": 3, "name": "Hyaluronic Acid Serum", "duration": 30, "product": "The Ordinary Hyaluronic Acid 2%"},
                    {"order": 4, "name": "Moisturizer", "duration": 60, "product": "CeraVe Daily Moisturizing Lotion"},
                    {"order": 5, "name": "Sunscreen", "duration": 30, "product": "La Roche-Posay Anthelios SPF 50"}
                ],
                "completion_count": 0,
                "last_completed": None
            },
            {
                "user_id": user_id,
                "name": "Evening Repair Routine",
                "type": "evening",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "steps": [
                    {"order": 1, "name": "Oil Cleanser", "duration": 90, "product": "DHC Deep Cleansing Oil"},
                    {"order": 2, "name": "Water-Based Cleanser", "duration": 60, "product": "CeraVe Foaming Cleanser"},
                    {"order": 3, "name": "Essence", "duration": 30, "product": "COSRX Snail 96 Mucin Essence"},
                    {"order": 4, "name": "Night Serum", "duration": 30, "product": "The Ordinary Niacinamide 10%"},
                    {"order": 5, "name": "Night Cream", "duration": 60, "product": "CeraVe PM Facial Moisturizing Lotion"}
                ],
                "completion_count": 0,
                "last_completed": None
            }
        ]
        
        routine_ids = []
        for routine in routines_data:
            result = db.routines.insert_one(routine)
            routine_ids.append(result.inserted_id)
            print(f"    ✓ Created routine: {routine['name']}")
        
        # Update plans with these routine IDs
        db.plans.update_many(
            {"user_id": user_id, "routine_ids": []},
            {"$set": {"routine_ids": routine_ids}}
        )
        print(f"    ✓ Updated plans with {len(routine_ids)} routines")
    
    # Check existing goals
    existing_goals = list(db.goals.find({"user_id": user_id}))
    print(f"  Existing goals: {len(existing_goals)}")
    
    if len(existing_goals) == 0:
        print("  Creating sample goals...")
        
        goals_data = [
            {
                "user_id": user_id,
                "title": "Achieve 85% Hydration Score",
                "description": "Improve skin hydration to optimal levels",
                "category": "hydration",
                "target_value": 85,
                "current_value": 68,
                "unit": "%",
                "status": "active",
                "priority": "high",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "deadline": datetime(2025, 9, 30),
                "milestones": [
                    {"value": 75, "title": "Good Hydration", "achieved": False},
                    {"value": 80, "title": "Very Good Hydration", "achieved": False},
                    {"value": 85, "title": "Excellent Hydration", "achieved": False}
                ]
            },
            {
                "user_id": user_id,
                "title": "21-Day Routine Streak",
                "description": "Complete morning and evening routines for 21 consecutive days",
                "category": "consistency",
                "target_value": 21,
                "current_value": 0,
                "unit": "days",
                "status": "active",
                "priority": "medium",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "deadline": datetime(2025, 9, 15),
                "milestones": [
                    {"value": 7, "title": "One Week", "achieved": False},
                    {"value": 14, "title": "Two Weeks", "achieved": False},
                    {"value": 21, "title": "Three Weeks", "achieved": False}
                ]
            },
            {
                "user_id": user_id,
                "title": "Reduce Dark Spots by 30%",
                "description": "Improve skin tone uniformity",
                "category": "appearance",
                "target_value": 30,
                "current_value": 0,
                "unit": "% reduction",
                "status": "active",
                "priority": "medium",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "deadline": datetime(2025, 10, 31),
                "milestones": [
                    {"value": 10, "title": "Visible Improvement", "achieved": False},
                    {"value": 20, "title": "Significant Progress", "achieved": False},
                    {"value": 30, "title": "Goal Achieved", "achieved": False}
                ]
            }
        ]
        
        goal_ids = []
        for goal in goals_data:
            result = db.goals.insert_one(goal)
            goal_ids.append(result.inserted_id)
            print(f"    ✓ Created goal: {goal['title']}")
        
        # Update plans with these goal IDs
        db.plans.update_many(
            {"user_id": user_id, "goal_ids": []},
            {"$set": {"goal_ids": goal_ids}}
        )
        print(f"    ✓ Updated plans with {len(goal_ids)} goals")

print("\n" + "=" * 60)
print("Data fix complete!")
print("=" * 60)

client.close()