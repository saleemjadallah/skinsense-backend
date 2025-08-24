#!/usr/bin/env python3
"""Test script to check MongoDB plans collection"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import pymongo
from bson import ObjectId
import json
from datetime import datetime

# MongoDB connection string from the backend
mongodb_url = os.getenv('MONGODB_URL')
client = pymongo.MongoClient(mongodb_url)

# Get the database
db = client.skinpal

print("=" * 60)
print("MongoDB Plans Collection Investigation")
print("=" * 60)

# Check if plans collection exists
collections = db.list_collection_names()
print(f"\nTotal collections in database: {len(collections)}")
print("Plans collection exists:", "plans" in collections)
print("Plan_progress collection exists:", "plan_progress" in collections)

# Check plans collection
if "plans" in collections:
    count = db.plans.count_documents({})
    print(f"\nDocuments in plans collection: {count}")
    
    # Get a sample document if any exist
    sample = db.plans.find_one()
    if sample:
        print("\nSample plan document structure:")
        for key in sample.keys():
            value_type = type(sample[key]).__name__
            if key == "_id":
                print(f"  - {key}: {value_type} = {sample[key]}")
            else:
                print(f"  - {key}: {value_type}")
    
    # Check for active plans
    active_count = db.plans.count_documents({"status": "active"})
    print(f"\nActive plans: {active_count}")
else:
    print("\n⚠️  Plans collection does not exist! Creating it now...")
    db.create_collection("plans")
    print("✓ Plans collection created")

# Check for test user
print("\n" + "=" * 60)
print("Checking for test user...")
test_user = db.users.find_one({"email": "test@skinsense.com"})

if test_user:
    user_id = test_user["_id"]
    print(f"✓ Test user found with ID: {user_id}")
    
    # Check if this user has any plans
    user_plans = list(db.plans.find({"user_id": user_id}))
    print(f"Plans for test user: {len(user_plans)}")
    
    if len(user_plans) == 0:
        print("\n⚠️  No plans found for test user. Creating a sample plan...")
        
        # Create a sample plan for testing
        sample_plan = {
            "user_id": user_id,
            "name": "Hydration Revival Journey",
            "description": "A 3-week intensive hydration program to restore your skin's natural moisture balance",
            "plan_type": "hydration_boost",
            "status": "active",
            "current_week": 1,
            "duration_weeks": 3,
            "started_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "target_concerns": ["hydration", "smoothness", "radiance"],
            "routine_ids": [],
            "goal_ids": [],
            "personalization_data": {
                "skin_type": "dry",
                "age_group": "25-34",
                "focus_areas": ["hydration", "anti-aging"]
            },
            "weekly_milestones": [
                {
                    "week_number": 1,
                    "title": "Week 1: Foundation & Assessment",
                    "description": "Establish your baseline routine and begin intensive hydration",
                    "expected_improvements": {
                        "hydration": 75,
                        "smoothness": 72
                    },
                    "focus_areas": ["hydration", "smoothness"],
                    "tips": [
                        "Drink at least 8 glasses of water daily",
                        "Apply moisturizer within 3 minutes of cleansing",
                        "Use a humidifier at night"
                    ]
                },
                {
                    "week_number": 2,
                    "title": "Week 2: Building & Strengthening",
                    "description": "Intensify hydration treatments and monitor improvements",
                    "expected_improvements": {
                        "hydration": 82,
                        "smoothness": 78
                    },
                    "focus_areas": ["hydration", "radiance"],
                    "tips": [
                        "Add a hydrating serum to your routine",
                        "Try overnight hydrating masks",
                        "Avoid hot water when cleansing"
                    ]
                },
                {
                    "week_number": 3,
                    "title": "Week 3: Mastery & Maintenance",
                    "description": "Lock in hydration gains and establish long-term habits",
                    "expected_improvements": {
                        "hydration": 88,
                        "smoothness": 85,
                        "radiance": 80
                    },
                    "focus_areas": ["hydration", "radiance"],
                    "tips": [
                        "Continue consistent routine",
                        "Monitor skin's response to products",
                        "Plan for seasonal adjustments"
                    ]
                }
            ],
            "effectiveness_predictions": {
                "hydration": {"current": 68, "predicted": 88, "improvement": 20},
                "smoothness": {"current": 65, "predicted": 85, "improvement": 20},
                "radiance": {"current": 70, "predicted": 80, "improvement": 10}
            }
        }
        
        result = db.plans.insert_one(sample_plan)
        print(f"✓ Sample plan created with ID: {result.inserted_id}")
        
        # Also create some sample routines for the plan
        routine_ids = []
        routines_data = [
            {
                "user_id": user_id,
                "name": "Morning Hydration Routine",
                "type": "morning",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "steps": [
                    {"order": 1, "name": "Gentle Cleanser", "duration": 60},
                    {"order": 2, "name": "Hydrating Toner", "duration": 30},
                    {"order": 3, "name": "Hyaluronic Acid Serum", "duration": 30},
                    {"order": 4, "name": "Moisturizer", "duration": 60},
                    {"order": 5, "name": "SPF 30+", "duration": 30}
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
                    {"order": 2, "name": "Gentle Cleanser", "duration": 60},
                    {"order": 3, "name": "Hydrating Essence", "duration": 30},
                    {"order": 4, "name": "Night Cream", "duration": 60}
                ]
            }
        ]
        
        for routine in routines_data:
            result = db.routines.insert_one(routine)
            routine_ids.append(result.inserted_id)
            print(f"  - Created routine: {routine['name']}")
        
        # Update plan with routine IDs
        db.plans.update_one(
            {"_id": sample_plan["_id"]},
            {"$set": {"routine_ids": routine_ids}}
        )
        print(f"✓ Updated plan with {len(routine_ids)} routines")
        
        # Create sample goals
        goal_ids = []
        goals_data = [
            {
                "user_id": user_id,
                "title": "Achieve 85% Hydration Score",
                "description": "Improve skin hydration from 68% to 85%",
                "category": "hydration",
                "target_value": 85,
                "current_value": 68,
                "status": "active",
                "created_at": datetime.utcnow()
            },
            {
                "user_id": user_id,
                "title": "Daily Routine Consistency",
                "description": "Complete morning and evening routines for 21 days",
                "category": "consistency",
                "target_value": 21,
                "current_value": 0,
                "status": "active",
                "created_at": datetime.utcnow()
            }
        ]
        
        for goal in goals_data:
            result = db.goals.insert_one(goal)
            goal_ids.append(result.inserted_id)
            print(f"  - Created goal: {goal['title']}")
        
        # Update plan with goal IDs
        db.plans.update_one(
            {"_id": sample_plan["_id"]},
            {"$set": {"goal_ids": goal_ids}}
        )
        print(f"✓ Updated plan with {len(goal_ids)} goals")
        
    else:
        print("\nExisting plans for test user:")
        for i, plan in enumerate(user_plans, 1):
            print(f"  {i}. {plan.get('name', 'Unnamed')} - Status: {plan.get('status', 'unknown')}")
else:
    print("⚠️  Test user not found. Please create a test user first.")

print("\n" + "=" * 60)
print("Investigation complete!")
print("=" * 60)

client.close()