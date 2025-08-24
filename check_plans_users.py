#!/usr/bin/env python3
"""Check which users have plans and create test data if needed"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import pymongo
from bson import ObjectId
from datetime import datetime
import bcrypt

# MongoDB connection
mongodb_url = os.getenv('MONGODB_URL')
client = pymongo.MongoClient(mongodb_url)
db = client.skinpal

print("=" * 60)
print("Checking Plans and Users")
print("=" * 60)

# Get all plans and their user IDs
plans = list(db.plans.find({}, {"user_id": 1, "name": 1, "status": 1}))
print(f"\nFound {len(plans)} plans:")

user_ids_with_plans = set()
for plan in plans:
    user_id = plan.get("user_id")
    user_ids_with_plans.add(user_id)
    print(f"  - Plan '{plan.get('name')}' (status: {plan.get('status')}) belongs to user: {user_id}")

# Check if these users exist
print("\nChecking if users exist:")
for user_id in user_ids_with_plans:
    user = db.users.find_one({"_id": user_id}, {"email": 1, "username": 1})
    if user:
        print(f"  ✓ User {user_id} exists: {user.get('email', 'no-email')}")
    else:
        print(f"  ✗ User {user_id} NOT FOUND - orphaned plan!")

# Check test users
print("\n" + "=" * 60)
print("Checking test users...")

test_emails = ["test@skinsense.com", "existing@skinsense.com", "admin@skinsense.com"]
for email in test_emails:
    user = db.users.find_one({"email": email})
    if user:
        user_id = user["_id"]
        print(f"\n✓ Found user: {email} (ID: {user_id})")
        
        # Check plans for this user
        user_plans = list(db.plans.find({"user_id": user_id}))
        print(f"  Plans: {len(user_plans)}")
        
        if len(user_plans) == 0 and email == "test@skinsense.com":
            print(f"  Creating sample plan for {email}...")
            
            # Create a sample plan
            sample_plan = {
                "user_id": user_id,
                "name": "Hydration Revival Journey",
                "description": "A 3-week intensive hydration program",
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
                    "age_group": "25-34"
                },
                "weekly_milestones": [
                    {
                        "week_number": 1,
                        "title": "Week 1: Foundation",
                        "description": "Establish baseline",
                        "expected_improvements": {"hydration": 75},
                        "focus_areas": ["hydration"],
                        "tips": ["Drink water", "Use moisturizer"]
                    }
                ],
                "effectiveness_predictions": {
                    "hydration": {"current": 68, "predicted": 88, "improvement": 20}
                }
            }
            
            result = db.plans.insert_one(sample_plan)
            print(f"  ✓ Created plan with ID: {result.inserted_id}")
    else:
        print(f"\n✗ User {email} not found")

# Create test user if needed
print("\n" + "=" * 60)
test_user = db.users.find_one({"email": "test@skinsense.com"})

if not test_user:
    print("Creating test@skinsense.com user...")
    
    # Hash password
    password = os.getenv('TEST_USER_PASSWORD', 'Test1234!')  # Use env var or default
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    new_user = {
        "email": "test@skinsense.com",
        "username": "testuser",
        "password_hash": password_hash.decode('utf-8'),
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "profile": {
            "age_group": "25-34",
            "skin_type": "combination",
            "gender": "female"
        },
        "onboarding_completed": True,
        "subscription": {
            "tier": "premium",
            "expires_at": datetime(2025, 12, 31)
        }
    }
    
    result = db.users.insert_one(new_user)
    user_id = result.inserted_id
    print(f"✓ Created test user with ID: {user_id}")
    
    # Now create a plan for this user
    sample_plan = {
        "user_id": user_id,
        "name": "Hydration Revival Journey",
        "description": "Transform your skin with our intensive 3-week hydration program",
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
            "skin_type": "combination",
            "age_group": "25-34",
            "gender": "female"
        },
        "weekly_milestones": [
            {
                "week_number": 1,
                "title": "Week 1: Foundation & Assessment",
                "description": "Establish your baseline routine",
                "expected_improvements": {"hydration": 75, "smoothness": 72},
                "focus_areas": ["hydration", "smoothness"],
                "tips": ["Drink 8 glasses of water daily", "Apply moisturizer immediately after cleansing"]
            },
            {
                "week_number": 2,
                "title": "Week 2: Building & Strengthening",
                "description": "Intensify hydration treatments",
                "expected_improvements": {"hydration": 82, "smoothness": 78},
                "focus_areas": ["hydration", "radiance"],
                "tips": ["Add hydrating serum", "Use overnight masks"]
            },
            {
                "week_number": 3,
                "title": "Week 3: Mastery & Maintenance",
                "description": "Lock in your gains",
                "expected_improvements": {"hydration": 88, "smoothness": 85},
                "focus_areas": ["hydration", "radiance"],
                "tips": ["Maintain consistency", "Plan seasonal adjustments"]
            }
        ],
        "effectiveness_predictions": {
            "hydration": {"current": 68, "predicted": 88, "improvement": 20},
            "smoothness": {"current": 65, "predicted": 85, "improvement": 20},
            "radiance": {"current": 70, "predicted": 80, "improvement": 10}
        }
    }
    
    result = db.plans.insert_one(sample_plan)
    print(f"✓ Created sample plan with ID: {result.inserted_id}")
else:
    print(f"Test user already exists with ID: {test_user['_id']}")

print("\n" + "=" * 60)
print("Setup complete! You can now test with:")
print("  Email: test@skinsense.com")
print("  Password: Test1234!")
print("=" * 60)

client.close()