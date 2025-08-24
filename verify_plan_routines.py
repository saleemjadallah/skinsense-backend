#!/usr/bin/env python3
"""Verify and fix plan routines linkage"""

import pymongo
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
mongodb_url = os.getenv('MONGODB_URL')
client = pymongo.MongoClient(mongodb_url)
db = client.skinpal

print("=" * 60)
print("Verifying Plan-Routine Linkage")
print("=" * 60)

# Get support user
support_user = db.users.find_one({"email": "support@skinsense.app"})
if not support_user:
    print("ERROR: support@skinsense.app not found!")
    exit(1)

user_id = support_user["_id"]
print(f"\nUser ID: {user_id}")

# Get the active plan
active_plan = db.plans.find_one({"user_id": user_id, "status": "active"})
if not active_plan:
    print("ERROR: No active plan found!")
    exit(1)

print(f"\nActive Plan: {active_plan['name']}")
print(f"Plan ID: {active_plan['_id']}")

# Check routine_ids in the plan
routine_ids = active_plan.get("routine_ids", [])
print(f"\nRoutine IDs in plan: {len(routine_ids)}")
for rid in routine_ids:
    print(f"  - {rid}")

# Check if these routines actually exist
print("\nVerifying routines exist:")
valid_routine_ids = []
for rid in routine_ids:
    routine = db.routines.find_one({"_id": rid})
    if routine:
        print(f"  ✓ {routine['name']} exists")
        valid_routine_ids.append(rid)
    else:
        print(f"  ✗ Routine {rid} NOT FOUND")

# Get all routines for this user
all_user_routines = list(db.routines.find({"user_id": user_id}))
print(f"\n\nTotal routines for user: {len(all_user_routines)}")
print("Available routines:")
for r in all_user_routines[:5]:  # Show first 5
    print(f"  - {r['name']} (ID: {r['_id']}, Type: {r.get('type', 'N/A')})")

# If plan has no valid routines, link some
if len(valid_routine_ids) == 0:
    print("\n⚠️  Plan has no valid routines. Linking available routines...")
    
    # Take morning and evening routines if available
    morning_routine = None
    evening_routine = None
    other_routines = []
    
    for r in all_user_routines:
        if r.get("type") == "morning" and not morning_routine:
            morning_routine = r["_id"]
        elif r.get("type") == "evening" and not evening_routine:
            evening_routine = r["_id"]
        else:
            other_routines.append(r["_id"])
    
    # Build list of routine IDs to link
    new_routine_ids = []
    if morning_routine:
        new_routine_ids.append(morning_routine)
    if evening_routine:
        new_routine_ids.append(evening_routine)
    # Add other routines if we don't have enough
    if len(new_routine_ids) < 2 and other_routines:
        new_routine_ids.extend(other_routines[:2-len(new_routine_ids)])
    
    if new_routine_ids:
        print(f"  Linking {len(new_routine_ids)} routines to plan")
        db.plans.update_one(
            {"_id": active_plan["_id"]},
            {"$set": {"routine_ids": new_routine_ids}}
        )
        print("  ✓ Routines linked!")
    else:
        print("  ✗ No routines available to link")

# Check goals as well
goal_ids = active_plan.get("goal_ids", [])
print(f"\n\nGoal IDs in plan: {len(goal_ids)}")
valid_goal_ids = []
for gid in goal_ids:
    goal = db.goals.find_one({"_id": gid})
    if goal:
        print(f"  ✓ {goal['title']} exists")
        valid_goal_ids.append(gid)
    else:
        print(f"  ✗ Goal {gid} NOT FOUND")

# Get all active goals for user
all_user_goals = list(db.goals.find({"user_id": user_id, "status": "active"}))
print(f"\nTotal active goals for user: {len(all_user_goals)}")

# If plan has no valid goals, link some
if len(valid_goal_ids) == 0 and all_user_goals:
    print("\n⚠️  Plan has no valid goals. Linking available goals...")
    new_goal_ids = [g["_id"] for g in all_user_goals[:3]]  # Take first 3
    
    db.plans.update_one(
        {"_id": active_plan["_id"]},
        {"$set": {"goal_ids": new_goal_ids}}
    )
    print(f"  ✓ Linked {len(new_goal_ids)} goals!")

print("\n" + "=" * 60)
print("Verification complete!")
print("=" * 60)

client.close()