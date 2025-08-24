#!/usr/bin/env python3
"""Fix effectiveness_predictions format in MongoDB plans"""

import pymongo
from bson import ObjectId
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
mongodb_url = os.getenv('MONGODB_URL')
client = pymongo.MongoClient(mongodb_url)
db = client.skinpal

print("=" * 60)
print("Fixing effectiveness_predictions Format")
print("=" * 60)

# Get all plans
plans = list(db.plans.find())
print(f"\nFound {len(plans)} plans to check")

fixed_count = 0
for plan in plans:
    plan_id = plan["_id"]
    predictions = plan.get("effectiveness_predictions", {})
    
    # Check if predictions need fixing
    needs_fix = False
    fixed_predictions = {}
    
    for key, value in predictions.items():
        if isinstance(value, dict):
            # This needs fixing - extract the predicted value
            if "predicted" in value:
                fixed_predictions[key] = float(value["predicted"])
            elif "improvement" in value:
                fixed_predictions[key] = float(value["improvement"])
            elif "current" in value and "predicted" in value:
                fixed_predictions[key] = float(value["predicted"])
            else:
                # Default to 0 if we can't find a value
                fixed_predictions[key] = 0.0
            needs_fix = True
        elif isinstance(value, (int, float)):
            # This is already in the correct format
            fixed_predictions[key] = float(value)
        else:
            # Unknown format, default to 0
            fixed_predictions[key] = 0.0
            needs_fix = True
    
    if needs_fix:
        print(f"\nFixing plan {plan_id}:")
        print(f"  Original: {predictions}")
        print(f"  Fixed: {fixed_predictions}")
        
        db.plans.update_one(
            {"_id": plan_id},
            {"$set": {"effectiveness_predictions": fixed_predictions}}
        )
        fixed_count += 1
        print("  ✓ Updated!")
    else:
        print(f"✓ Plan {plan_id} already has correct format")

# Also add default weekly_milestones if missing
print("\n" + "=" * 60)
print("Checking weekly_milestones...")

for plan in db.plans.find():
    if not plan.get("weekly_milestones"):
        print(f"Adding default milestones to plan {plan['_id']}")
        default_milestones = [
            {
                "week_number": 1,
                "title": "Week 1: Foundation",
                "description": "Establish your baseline routine",
                "expected_improvements": {"hydration": 75.0},
                "focus_areas": ["hydration"],
                "tips": ["Stay consistent", "Track progress"]
            }
        ]
        db.plans.update_one(
            {"_id": plan["_id"]},
            {"$set": {"weekly_milestones": default_milestones}}
        )

print("\n" + "=" * 60)
print(f"Fixed {fixed_count} plans")
print("=" * 60)

client.close()