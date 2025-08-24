#!/usr/bin/env python3
"""Debug the MongoDB query issue"""

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
print("Debugging MongoDB Queries")
print("=" * 60)

# Get the plan
plan = db.plans.find_one({"_id": ObjectId("68a962673e3eaf71161c8cc7")})
print(f"\nPlan found: {plan['name']}")

# Get routine_ids
routine_ids = plan.get("routine_ids", [])
print(f"\nRoutine IDs from plan ({len(routine_ids)}):")
for rid in routine_ids:
    print(f"  - {rid} (type: {type(rid).__name__})")

# Try the query
print("\nTrying query: db.routines.find({\"_id\": {\"$in\": routine_ids}})")
routines = list(db.routines.find({"_id": {"$in": routine_ids}}))
print(f"Found {len(routines)} routines")
for r in routines:
    print(f"  - {r['name']}")

# Also try with individual IDs
print("\nTrying individual queries:")
for rid in routine_ids:
    routine = db.routines.find_one({"_id": rid})
    if routine:
        print(f"  ✓ Found: {routine['name']}")
    else:
        print(f"  ✗ Not found: {rid}")

print("\n" + "=" * 60)

client.close()