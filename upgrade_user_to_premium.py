#!/usr/bin/env python3
"""
Script to upgrade a user to premium subscription for testing insights
"""

import sys
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection
MONGODB_URL = "mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal"
client = MongoClient(MONGODB_URL)
db = client["skinpal"]

def upgrade_user_to_premium(email: str):
    """Upgrade user to premium subscription"""
    print(f"\n=== Upgrading user {email} to premium ===\n")
    
    # Find user by email
    user = db.users.find_one({"email": email})
    if not user:
        print(f"❌ User with email {email} not found!")
        return
    
    user_id = user["_id"]
    print(f"✅ Found user: {user.get('username', 'N/A')} (ID: {user_id})")
    
    # Current subscription status
    current_subscription = user.get("subscription", {})
    current_tier = current_subscription.get("tier", "free")
    print(f"📋 Current subscription tier: {current_tier}")
    
    # Upgrade to premium
    update_data = {
        "subscription.tier": "premium",
        "subscription.status": "active", 
        "subscription.expires_at": datetime.utcnow() + timedelta(days=30),
        "subscription.updated_at": datetime.utcnow(),
        "subscription.usage.monthly_scans_used": 0,
        "subscription.usage.daily_pal_questions_used": 0
    }
    
    result = db.users.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        print(f"✅ User upgraded to premium successfully!")
        print(f"   - Tier: premium")
        print(f"   - Expires: {update_data['subscription.expires_at']}")
        print(f"   - Status: active")
        
        # Verify the update
        updated_user = db.users.find_one({"_id": user_id})
        updated_subscription = updated_user.get("subscription", {})
        print(f"\n📱 Verification:")
        print(f"   - New tier: {updated_subscription.get('tier')}")
        print(f"   - Can access insights: {updated_subscription.get('tier') == 'premium'}")
    else:
        print(f"⚠️ No changes made (user might already be premium)")

def downgrade_user_to_free(email: str):
    """Downgrade user back to free tier"""
    print(f"\n=== Downgrading user {email} to free ===\n")
    
    # Find user by email
    user = db.users.find_one({"email": email})
    if not user:
        print(f"❌ User with email {email} not found!")
        return
    
    user_id = user["_id"]
    
    # Downgrade to free
    update_data = {
        "subscription.tier": "free",
        "subscription.status": "active",
        "subscription.expires_at": None,
        "subscription.updated_at": datetime.utcnow()
    }
    
    result = db.users.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        print(f"✅ User downgraded to free tier")
    else:
        print(f"⚠️ No changes made")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upgrade_user_to_premium.py <email> [--downgrade]")
        print("Example: python upgrade_user_to_premium.py saleem86@icloud.com")
        print("To downgrade: python upgrade_user_to_premium.py saleem86@icloud.com --downgrade")
        sys.exit(1)
    
    email = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == "--downgrade":
        downgrade_user_to_free(email)
    else:
        upgrade_user_to_premium(email)
    
    print("\n" + "="*50 + "\n")