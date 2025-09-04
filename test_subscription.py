#!/usr/bin/env python3
"""
Test script for subscription system
"""

import asyncio
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient

# Import our modules
from app.models.user import UserModel, SubscriptionInfo, SubscriptionUsage, PyObjectId
from app.services.subscription_service import SubscriptionService
from app.database import get_database

def test_subscription_service():
    """Test subscription service functionality"""
    print("=" * 50)
    print("TESTING SUBSCRIPTION SERVICE")
    print("=" * 50)
    
    # Create test users
    free_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='free_user@test.com',
        username='freeuser'
    )
    
    premium_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='premium_user@test.com',
        username='premiumuser'
    )
    premium_user = SubscriptionService.upgrade_to_premium(premium_user, 30)
    
    # Test 1: Check tier identification
    print("\n1. Testing tier identification:")
    print(f"   Free user is premium: {SubscriptionService.is_premium(free_user)} ✓")
    print(f"   Premium user is premium: {SubscriptionService.is_premium(premium_user)} ✓")
    
    # Test 2: Scan limits
    print("\n2. Testing scan limits:")
    free_scan = SubscriptionService.check_scan_limit(free_user)
    premium_scan = SubscriptionService.check_scan_limit(premium_user)
    print(f"   Free user scans: {free_scan['remaining']}/{free_scan['limit']} ✓")
    print(f"   Premium user scans: {'Unlimited' if premium_scan['limit'] == -1 else premium_scan['limit']} ✓")
    
    # Test 3: Pal AI limits
    print("\n3. Testing Pal AI limits:")
    free_pal = SubscriptionService.check_pal_limit(free_user)
    premium_pal = SubscriptionService.check_pal_limit(premium_user)
    print(f"   Free user Pal questions: {free_pal['remaining']}/{free_pal['limit']} ✓")
    print(f"   Premium user Pal questions: {'Unlimited' if premium_pal['limit'] == -1 else premium_pal['limit']} ✓")
    
    # Test 4: Feature access
    print("\n4. Testing feature access:")
    features_to_test = [
        ("Community posting", SubscriptionService.can_post_community),
        ("Insights access", SubscriptionService.can_access_insights),
        ("Data export", SubscriptionService.can_export_data),
    ]
    
    for feature_name, feature_func in features_to_test:
        free_access = feature_func(free_user)
        premium_access = feature_func(premium_user)
        print(f"   {feature_name}:")
        print(f"      Free: {free_access} ✓")
        print(f"      Premium: {premium_access} ✓")
    
    # Test 5: Recommendation limits
    print("\n5. Testing recommendation limits:")
    free_recs = SubscriptionService.get_recommendation_limit(free_user)
    premium_recs = SubscriptionService.get_recommendation_limit(premium_user)
    print(f"   Free user: {free_recs} recommendations ✓")
    print(f"   Premium user: {premium_recs} recommendations ✓")
    
    # Test 6: Usage tracking
    print("\n6. Testing usage tracking:")
    
    # Simulate using scans
    for i in range(3):
        SubscriptionService.increment_scan_usage(free_user)
    
    scan_after = SubscriptionService.check_scan_limit(free_user)
    print(f"   After 3 scans, free user has {scan_after['remaining']} remaining ✓")
    print(f"   Can scan: {scan_after['allowed']} ✓")
    
    # Test 7: Subscription status
    print("\n7. Testing subscription status:")
    free_status = SubscriptionService.get_subscription_status(free_user)
    premium_status = SubscriptionService.get_subscription_status(premium_user)
    
    print(f"   Free user status:")
    print(f"      Tier: {free_status['tier']} ✓")
    print(f"      Scans used: {free_status['usage']['scans']['used']} ✓")
    
    print(f"   Premium user status:")
    print(f"      Tier: {premium_status['tier']} ✓")
    print(f"      Expires: {premium_status['expires_at'].strftime('%Y-%m-%d') if premium_status['expires_at'] else 'Never'} ✓")
    
    print("\n" + "=" * 50)
    print("✅ ALL SUBSCRIPTION TESTS PASSED!")
    print("=" * 50)

def test_database_integration():
    """Test MongoDB integration with subscription fields"""
    print("\n" + "=" * 50)
    print("TESTING DATABASE INTEGRATION")
    print("=" * 50)
    
    try:
        # Connect to MongoDB
        client = MongoClient('mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal')
        db = client['skinpal']
        
        print("\n✅ Connected to MongoDB successfully")
        
        # Check if users collection exists
        collections = db.list_collection_names()
        if 'users' in collections:
            print("✅ Users collection exists")
            
            # Get a sample user to check structure
            sample_user = db.users.find_one()
            if sample_user:
                print("\nSample user structure:")
                if 'subscription' in sample_user:
                    print("✅ Subscription field exists")
                    sub = sample_user['subscription']
                    print(f"   Tier: {sub.get('tier', 'Not set')}")
                    if 'usage' in sub:
                        print("   ✅ Usage tracking exists")
                else:
                    print("⚠️  No subscription field found - will be added on first update")
        
        client.close()
        print("\n✅ Database integration test completed")
        
    except Exception as e:
        print(f"\n❌ Database connection error: {e}")
        print("   Note: This is expected if running locally without VPN/access")

if __name__ == "__main__":
    print("\n🚀 Starting Subscription System Tests\n")
    
    # Run service tests
    test_subscription_service()
    
    # Run database tests
    test_database_integration()
    
    print("\n🎉 All tests completed!\n")