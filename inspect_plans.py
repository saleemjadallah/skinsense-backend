#!/usr/bin/env python3
"""Inspect plans data for support user"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import pymongo
from bson import ObjectId
import json

# MongoDB connection
mongodb_url = os.getenv('MONGODB_URL')
client = pymongo.MongoClient(mongodb_url)
db = client.skinpal

print("=" * 60)
print("Inspecting Plans for support@skinsense.app")
print("=" * 60)

# Get the support user
support_user = db.users.find_one({"email": "support@skinsense.app"})
if not support_user:
    print("ERROR: support@skinsense.app user not found!")
    exit(1)

user_id = support_user["_id"]
print(f"\nUser ID: {user_id}")

# Get all plans for this user
plans = list(db.plans.find({"user_id": user_id}))
print(f"\nFound {len(plans)} plans for this user:")

for i, plan in enumerate(plans, 1):
    print(f"\n--- Plan {i} ---")
    print(f"ID: {plan['_id']}")
    print(f"Name: {plan.get('name', 'NO NAME')}")
    print(f"Status: {plan.get('status', 'NO STATUS')}")
    print(f"Type: {plan.get('plan_type', 'NO TYPE')}")
    
    # Check routine_ids
    routine_ids = plan.get("routine_ids", [])
    print(f"\nRoutine IDs ({len(routine_ids)}):")
    for rid in routine_ids:
        if rid is None:
            print(f"  - None (THIS IS THE PROBLEM!)")
        else:
            print(f"  - {rid} (type: {type(rid).__name__})")
            # Check if routine exists
            routine = db.routines.find_one({"_id": rid})
            if routine:
                print(f"    ✓ Routine exists: {routine.get('name', 'unnamed')}")
            else:
                print(f"    ✗ Routine NOT FOUND!")
    
    # Check goal_ids
    goal_ids = plan.get("goal_ids", [])
    print(f"\nGoal IDs ({len(goal_ids)}):")
    for gid in goal_ids:
        if gid is None:
            print(f"  - None (THIS IS THE PROBLEM!)")
        else:
            print(f"  - {gid} (type: {type(gid).__name__})")
            # Check if goal exists
            goal = db.goals.find_one({"_id": gid})
            if goal:
                print(f"    ✓ Goal exists: {goal.get('title', 'unnamed')}")
            else:
                print(f"    ✗ Goal NOT FOUND!")
    
    # Check for other potentially problematic fields
    print(f"\nOther fields:")
    print(f"  weekly_milestones: {len(plan.get('weekly_milestones', []))} items")
    print(f"  target_concerns: {plan.get('target_concerns', [])}")
    print(f"  current_week: {plan.get('current_week', 'MISSING')}")
    print(f"  duration_weeks: {plan.get('duration_weeks', 'MISSING')}")

print("\n" + "=" * 60)

# Now let's fix any None values we find
print("\nFixing None values in plans...")
fixed_count = 0

for plan in plans:
    needs_update = False
    updates = {}
    
    # Clean routine_ids
    routine_ids = plan.get("routine_ids", [])
    cleaned_routine_ids = [rid for rid in routine_ids if rid is not None]
    if len(cleaned_routine_ids) != len(routine_ids):
        updates["routine_ids"] = cleaned_routine_ids
        needs_update = True
        print(f"\nFixing plan {plan['_id']}:")
        print(f"  Cleaned routine_ids: removed {len(routine_ids) - len(cleaned_routine_ids)} None values")
    
    # Clean goal_ids
    goal_ids = plan.get("goal_ids", [])
    cleaned_goal_ids = [gid for gid in goal_ids if gid is not None]
    if len(cleaned_goal_ids) != len(goal_ids):
        updates["goal_ids"] = cleaned_goal_ids
        needs_update = True
        print(f"  Cleaned goal_ids: removed {len(goal_ids) - len(cleaned_goal_ids)} None values")
    
    if needs_update:
        db.plans.update_one(
            {"_id": plan["_id"]},
            {"$set": updates}
        )
        fixed_count += 1
        print(f"  ✓ Fixed!")

if fixed_count > 0:
    print(f"\nFixed {fixed_count} plans")
else:
    print(f"\nNo plans needed fixing")

print("=" * 60)

client.close()