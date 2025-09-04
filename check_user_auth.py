#!/usr/bin/env python3
"""
Script to check and fix user authentication issues related to subscription fields
"""
import os
from pymongo import MongoClient
from datetime import datetime
import json
from bson import ObjectId

# MongoDB connection
MONGODB_URL = "mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal"
client = MongoClient(MONGODB_URL)
db = client['skinpal']

def check_user(email):
    """Check user details and fix issues"""
    print(f"\n{'='*60}")
    print(f"Checking user: {email}")
    print('='*60)
    
    # Find user
    user = db.users.find_one({"email": email})
    
    if not user:
        print(f"❌ User not found with email: {email}")
        return None
    
    print(f"✅ User found - ID: {user['_id']}")
    
    # Check critical fields
    print("\n📊 Critical Authentication Fields:")
    print(f"  - is_active: {user.get('is_active', 'NOT SET')}")
    print(f"  - is_verified: {user.get('is_verified', 'NOT SET')}")
    
    # Check subscription structure
    print("\n💳 Subscription Details:")
    subscription = user.get('subscription', {})
    if subscription:
        print(f"  - tier: {subscription.get('tier', 'NOT SET')}")
        print(f"  - is_active: {subscription.get('is_active', 'NOT SET')}")
        usage = subscription.get('usage', {})
        if usage:
            print("  - usage:")
            for key, value in usage.items():
                if isinstance(value, datetime):
                    print(f"      {key}: {value.isoformat()}")
                else:
                    print(f"      {key}: {value}")
        else:
            print("  - usage: NOT SET")
    else:
        print("  ⚠️ No subscription field found")
    
    # Check for issues
    issues_found = []
    
    if not user.get('is_active'):
        issues_found.append("is_active is False or missing")
    
    if not subscription:
        issues_found.append("subscription field is missing")
    elif not isinstance(subscription.get('usage'), dict):
        issues_found.append("subscription.usage is not properly formatted")
    
    if issues_found:
        print(f"\n⚠️ Issues Found: {', '.join(issues_found)}")
        return user
    else:
        print("\n✅ No authentication issues detected")
        return user

def fix_user(email):
    """Fix user authentication and subscription issues"""
    user = check_user(email)
    
    if not user:
        return
    
    print(f"\n🔧 Fixing issues for user: {email}")
    
    # Prepare update query
    update_query = {}
    
    # Ensure is_active is True
    if not user.get('is_active', False):
        update_query['is_active'] = True
        print("  - Setting is_active to True")
    
    # Fix subscription structure
    subscription = user.get('subscription', {})
    
    # Create proper subscription structure if missing or malformed
    proper_subscription = {
        "tier": subscription.get('tier', 'free'),
        "expires_at": subscription.get('expires_at', None),
        "stripe_customer_id": subscription.get('stripe_customer_id', None),
        "is_active": True,
        "usage": {
            "monthly_scans_used": subscription.get('usage', {}).get('monthly_scans_used', 0),
            "monthly_scans_limit": subscription.get('usage', {}).get('monthly_scans_limit', 3),
            "daily_pal_questions_used": subscription.get('usage', {}).get('daily_pal_questions_used', 0),
            "daily_pal_questions_limit": subscription.get('usage', {}).get('daily_pal_questions_limit', 5),
            "last_reset_date": subscription.get('usage', {}).get('last_reset_date', datetime.utcnow()),
            "last_pal_reset_date": subscription.get('usage', {}).get('last_pal_reset_date', datetime.utcnow())
        },
        "upgraded_at": subscription.get('upgraded_at', None),
        "cancelled_at": subscription.get('cancelled_at', None)
    }
    
    update_query['subscription'] = proper_subscription
    print("  - Fixed subscription structure")
    
    # Apply the update
    if update_query:
        result = db.users.update_one(
            {"_id": user['_id']},
            {"$set": update_query}
        )
        
        if result.modified_count > 0:
            print(f"\n✅ Successfully fixed user {email}")
            
            # Verify the fix
            print("\n📋 Verification:")
            check_user(email)
        else:
            print(f"\n⚠️ No changes were needed for user {email}")
    else:
        print("\n✅ No fixes needed")

def check_all_users_summary():
    """Check all users for similar issues"""
    print(f"\n{'='*60}")
    print("Checking all users for authentication issues")
    print('='*60)
    
    total_users = db.users.count_documents({})
    users_with_issues = []
    
    for user in db.users.find({}, {"email": 1, "is_active": 1, "subscription": 1}):
        issues = []
        
        if not user.get('is_active', False):
            issues.append("is_active")
        
        if not user.get('subscription'):
            issues.append("no_subscription")
        elif not isinstance(user.get('subscription', {}).get('usage'), dict):
            issues.append("bad_usage")
        
        if issues:
            users_with_issues.append({
                "email": user.get('email', 'unknown'),
                "issues": issues
            })
    
    print(f"\nTotal users: {total_users}")
    print(f"Users with issues: {len(users_with_issues)}")
    
    if users_with_issues:
        print("\nUsers needing fixes:")
        for u in users_with_issues[:10]:  # Show first 10
            print(f"  - {u['email']}: {', '.join(u['issues'])}")
        
        if len(users_with_issues) > 10:
            print(f"  ... and {len(users_with_issues) - 10} more")
    
    return users_with_issues

if __name__ == "__main__":
    # Fix the specific user
    fix_user("saleem86@icloud.com")
    
    # Check for other users with similar issues
    print("\n" + "="*60)
    print("Summary of other users:")
    check_all_users_summary()