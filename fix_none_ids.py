#!/usr/bin/env python3
"""Fix None ObjectIds in MongoDB collections"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import pymongo
from bson import ObjectId

# MongoDB connection
mongodb_url = os.getenv('MONGODB_URL')
client = pymongo.MongoClient(mongodb_url)
db = client.skinpal

print("=" * 60)
print("Fixing None ObjectIds in Plans")
print("=" * 60)

support_user = db.users.find_one({"email": "support@skinsense.app"})
if not support_user:
    print("ERROR: support@skinsense.app user not found!")
    exit(1)

user_id = support_user["_id"]
print(f"\nUser ID: {user_id}")

# Get all plans for this user
plans = list(db.plans.find({"user_id": user_id}))
print(f"\nFound {len(plans)} plans")

for plan in plans:
    plan_id = plan.get("_id")
    print(f"\nChecking plan: {plan_id}")
    
    # Clean routine_ids
    routine_ids = plan.get("routine_ids", [])
    cleaned_routine_ids = []
    for rid in routine_ids:
        if rid is not None and rid != "None":
            # Verify the routine exists
            if db.routines.find_one({"_id": rid}):
                cleaned_routine_ids.append(rid)
            else:
                print(f"  ✗ Removing non-existent routine ID: {rid}")
        else:
            print(f"  ✗ Removing None/invalid routine ID")
    
    # Clean goal_ids
    goal_ids = plan.get("goal_ids", [])
    cleaned_goal_ids = []
    for gid in goal_ids:
        if gid is not None and gid != "None":
            # Verify the goal exists
            if db.goals.find_one({"_id": gid}):
                cleaned_goal_ids.append(gid)
            else:
                print(f"  ✗ Removing non-existent goal ID: {gid}")
        else:
            print(f"  ✗ Removing None/invalid goal ID")
    
    # Update if needed
    if len(cleaned_routine_ids) != len(routine_ids) or len(cleaned_goal_ids) != len(goal_ids):
        print(f"  Updating plan...")
        print(f"    Routines: {len(routine_ids)} → {len(cleaned_routine_ids)}")
        print(f"    Goals: {len(goal_ids)} → {len(cleaned_goal_ids)}")
        
        db.plans.update_one(
            {"_id": plan_id},
            {"$set": {
                "routine_ids": cleaned_routine_ids,
                "goal_ids": cleaned_goal_ids
            }}
        )
        print(f"  ✓ Updated!")

# Also check for plans with _id = None (which shouldn't exist)
bad_plans = list(db.plans.find({"_id": None}))
if bad_plans:
    print(f"\n⚠️  Found {len(bad_plans)} plans with _id=None, deleting them...")
    db.plans.delete_many({"_id": None})
    print("  ✓ Deleted!")

# Also remove duplicates - keep only one active plan per user
print(f"\nChecking for duplicate active plans...")
active_plans = list(db.plans.find({"user_id": user_id, "status": "active"}))
if len(active_plans) > 1:
    print(f"  Found {len(active_plans)} active plans, keeping only the first one")
    # Keep the first one, deactivate others
    for i, plan in enumerate(active_plans[1:], 1):
        print(f"  Deactivating duplicate plan {i}: {plan['_id']}")
        db.plans.update_one(
            {"_id": plan["_id"]},
            {"$set": {"status": "paused"}}
        )

print("\n" + "=" * 60)
print("Cleanup complete!")
print("=" * 60)

client.close()