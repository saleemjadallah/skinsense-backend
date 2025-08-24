#!/usr/bin/env python3
"""Link plans to existing routines and goals for support user"""

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
print("Linking Plans to Routines and Goals")
print("=" * 60)

# Get the support user
support_user = db.users.find_one({"email": "support@skinsense.app"})
if not support_user:
    print("ERROR: support@skinsense.app user not found!")
    exit(1)

user_id = support_user["_id"]
print(f"\nUser ID: {user_id}")

# Get existing routines for this user
routines = list(db.routines.find({"user_id": user_id}))
print(f"\nFound {len(routines)} routines for this user:")
routine_ids = []
for routine in routines[:3]:  # Take first 3 routines
    routine_ids.append(routine["_id"])
    print(f"  - {routine.get('name', 'Unnamed')} (ID: {routine['_id']})")

# Get existing goals for this user
goals = list(db.goals.find({"user_id": user_id, "status": "active"}))
print(f"\nFound {len(goals)} active goals for this user:")
goal_ids = []
for goal in goals[:3]:  # Take first 3 goals
    goal_ids.append(goal["_id"])
    print(f"  - {goal.get('title', 'Unnamed')} (ID: {goal['_id']})")

# Update plans with these IDs
plans = list(db.plans.find({"user_id": user_id}))
print(f"\nUpdating {len(plans)} plans...")

for i, plan in enumerate(plans, 1):
    plan_id = plan["_id"]
    
    # Skip if plan already has routines and goals
    if plan.get("routine_ids") and plan.get("goal_ids"):
        print(f"\nPlan {i} ({plan_id}) already has routines and goals, skipping")
        continue
    
    print(f"\nUpdating Plan {i} ({plan_id}):")
    print(f"  Name: {plan.get('name', 'Unnamed')}")
    
    # Update with routine and goal IDs
    update = {
        "routine_ids": routine_ids,
        "goal_ids": goal_ids,
        "updated_at": datetime.utcnow()
    }
    
    db.plans.update_one(
        {"_id": plan_id},
        {"$set": update}
    )
    
    print(f"  ✓ Added {len(routine_ids)} routines")
    print(f"  ✓ Added {len(goal_ids)} goals")

# If no routines or goals exist, create some
if len(routine_ids) == 0:
    print("\n⚠️  No routines found, creating sample routines...")
    
    sample_routines = [
        {
            "user_id": user_id,
            "name": "Morning Hydration Routine",
            "type": "morning",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "steps": [
                {"order": 1, "name": "Gentle Cleanser", "duration": 60},
                {"order": 2, "name": "Hydrating Toner", "duration": 30},
                {"order": 3, "name": "Hyaluronic Serum", "duration": 30},
                {"order": 4, "name": "Moisturizer", "duration": 60},
                {"order": 5, "name": "SPF 50", "duration": 30}
            ]
        },
        {
            "user_id": user_id,
            "name": "Evening Recovery Routine",
            "type": "evening",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "steps": [
                {"order": 1, "name": "Oil Cleanser", "duration": 90},
                {"order": 2, "name": "Water Cleanser", "duration": 60},
                {"order": 3, "name": "Treatment Serum", "duration": 30},
                {"order": 4, "name": "Night Cream", "duration": 60}
            ]
        }
    ]
    
    new_routine_ids = []
    for routine in sample_routines:
        result = db.routines.insert_one(routine)
        new_routine_ids.append(result.inserted_id)
        print(f"  ✓ Created: {routine['name']}")
    
    # Update plans with new routine IDs
    db.plans.update_many(
        {"user_id": user_id},
        {"$set": {"routine_ids": new_routine_ids}}
    )
    print(f"  ✓ Updated plans with {len(new_routine_ids)} new routines")

if len(goal_ids) == 0:
    print("\n⚠️  No active goals found, creating sample goals...")
    
    sample_goals = [
        {
            "user_id": user_id,
            "title": "Boost Hydration to 85%",
            "category": "hydration",
            "target_value": 85,
            "current_value": 68,
            "status": "active",
            "created_at": datetime.utcnow()
        },
        {
            "user_id": user_id,
            "title": "21-Day Consistency",
            "category": "consistency",
            "target_value": 21,
            "current_value": 0,
            "status": "active",
            "created_at": datetime.utcnow()
        }
    ]
    
    new_goal_ids = []
    for goal in sample_goals:
        result = db.goals.insert_one(goal)
        new_goal_ids.append(result.inserted_id)
        print(f"  ✓ Created: {goal['title']}")
    
    # Update plans with new goal IDs
    db.plans.update_many(
        {"user_id": user_id},
        {"$set": {"goal_ids": new_goal_ids}}
    )
    print(f"  ✓ Updated plans with {len(new_goal_ids)} new goals")

print("\n" + "=" * 60)
print("Linking complete!")
print("=" * 60)

client.close()