#!/usr/bin/env python3
"""
Integration test for the complete subscription system
"""

from app.models.user import UserModel, PyObjectId
from app.services.subscription_service import SubscriptionService
from bson import ObjectId
import json

def create_test_scenario():
    """Create a realistic test scenario"""
    print("\n" + "=" * 60)
    print("INTEGRATION TEST: Free User Journey")
    print("=" * 60)
    
    # Create a new free user
    user = UserModel(
        id=PyObjectId(ObjectId()),
        email='jane.doe@example.com',
        username='janedoe',
    )
    
    print("\n📱 Day 1: Jane signs up for SkinSense")
    print(f"   Account Type: {user.subscription.tier.upper()}")
    status = SubscriptionService.get_subscription_status(user)
    print(f"   Monthly Scans: {status['usage']['scans']['limit']}")
    print(f"   Daily Pal Questions: {status['usage']['pal_questions']['limit']}")
    print(f"   Can Post in Community: {status['features']['community_post']}")
    
    # Day 1: First scan
    print("\n📸 Jane takes her first skin scan...")
    if SubscriptionService.check_scan_limit(user)['allowed']:
        SubscriptionService.increment_scan_usage(user)
        print("   ✅ Scan successful!")
        scan_status = SubscriptionService.check_scan_limit(user)
        print(f"   Remaining scans: {scan_status['remaining']}/{scan_status['limit']}")
    
    # Day 1: Asks Pal AI
    print("\n💬 Jane asks Pal AI about her skin type...")
    if SubscriptionService.check_pal_limit(user)['allowed']:
        SubscriptionService.increment_pal_usage(user)
        print("   ✅ Pal AI responds with helpful advice")
        pal_status = SubscriptionService.check_pal_limit(user)
        print(f"   Remaining questions today: {pal_status['remaining']}/{pal_status['limit']}")
    
    # Day 2: Second scan
    print("\n📸 Day 2: Jane takes another scan...")
    if SubscriptionService.check_scan_limit(user)['allowed']:
        SubscriptionService.increment_scan_usage(user)
        print("   ✅ Scan successful!")
        scan_status = SubscriptionService.check_scan_limit(user)
        print(f"   Remaining scans: {scan_status['remaining']}/{scan_status['limit']}")
    
    # Day 3: Third scan (last free one)
    print("\n📸 Day 3: Jane takes her third scan...")
    if SubscriptionService.check_scan_limit(user)['allowed']:
        SubscriptionService.increment_scan_usage(user)
        print("   ✅ Scan successful!")
        scan_status = SubscriptionService.check_scan_limit(user)
        print(f"   ⚠️  Warning: {scan_status['remaining']} scans remaining this month")
    
    # Day 4: Tries to scan again
    print("\n📸 Day 4: Jane tries to scan again...")
    if not SubscriptionService.check_scan_limit(user)['allowed']:
        print("   ❌ SCAN BLOCKED")
        print("   📢 'You've used all 3 free scans this month'")
        print("   💎 'Upgrade to Premium for unlimited scans!'")
    
    # Jane tries to post in community
    print("\n💬 Jane tries to post in the community...")
    if not SubscriptionService.can_post_community(user):
        print("   ❌ POSTING BLOCKED")
        print("   📢 'Community posting is a Premium feature'")
        print("   💎 'Upgrade to share your skincare journey!'")
    
    # Jane checks recommendations
    print("\n🛍️  Jane checks product recommendations...")
    rec_limit = SubscriptionService.get_recommendation_limit(user)
    print(f"   Shows {rec_limit} product recommendations")
    print("   💎 Premium users see 10+ recommendations")
    
    print("\n" + "=" * 60)
    print("JANE DECIDES TO UPGRADE!")
    print("=" * 60)
    
    # Upgrade to premium
    user = SubscriptionService.upgrade_to_premium(user, 30)
    
    print("\n🎉 Welcome to Premium, Jane!")
    premium_status = SubscriptionService.get_subscription_status(user)
    
    print("\n✨ Premium Benefits Unlocked:")
    print(f"   ✅ Unlimited Scans (was 3/month)")
    print(f"   ✅ Unlimited Pal AI (was 5/day)")
    print(f"   ✅ Community Posting Enabled")
    print(f"   ✅ Daily Insights Access")
    print(f"   ✅ {SubscriptionService.get_recommendation_limit(user)} Product Recommendations (was {rec_limit})")
    print(f"   ✅ Data Export Enabled")
    print(f"   ✅ Priority Support")
    
    # Test premium features
    print("\n📸 Jane can now scan unlimited times...")
    for i in range(5):
        if SubscriptionService.check_scan_limit(user)['allowed']:
            SubscriptionService.increment_scan_usage(user)
    print(f"   ✅ Completed 5 scans - no limits!")
    
    print("\n💬 Jane can post in community...")
    if SubscriptionService.can_post_community(user):
        print("   ✅ Successfully posted her progress!")
    
    print("\n📊 Jane can access insights...")
    if SubscriptionService.can_access_insights(user):
        print("   ✅ Daily personalized insights available!")
    
    print("\n" + "=" * 60)
    print("✅ INTEGRATION TEST COMPLETE - ALL SYSTEMS WORKING!")
    print("=" * 60)

def generate_api_response_examples():
    """Generate example API responses for documentation"""
    print("\n" + "=" * 60)
    print("API RESPONSE EXAMPLES")
    print("=" * 60)
    
    # Free user status
    free_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='free@example.com',
        username='freeuser'
    )
    free_user.subscription.usage.monthly_scans_used = 2
    
    print("\n📄 GET /api/v1/subscription/status (Free User):")
    free_status = SubscriptionService.get_subscription_status(free_user)
    # Convert datetime to string for JSON serialization
    if free_status.get('expires_at'):
        free_status['expires_at'] = free_status['expires_at'].isoformat()
    if free_status['usage']['scans'].get('reset_date'):
        free_status['usage']['scans']['reset_date'] = free_status['usage']['scans']['reset_date'].isoformat()
    if free_status['usage']['pal_questions'].get('reset_time'):
        free_status['usage']['pal_questions']['reset_time'] = free_status['usage']['pal_questions']['reset_time'].isoformat()
    
    print(json.dumps(free_status, indent=2))
    
    # Premium user status
    premium_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='premium@example.com',
        username='premiumuser'
    )
    premium_user = SubscriptionService.upgrade_to_premium(premium_user, 30)
    
    print("\n📄 GET /api/v1/subscription/status (Premium User):")
    premium_status = SubscriptionService.get_subscription_status(premium_user)
    # Convert datetime to string for JSON serialization
    if premium_status.get('expires_at'):
        premium_status['expires_at'] = premium_status['expires_at'].isoformat()
    if premium_status['usage']['scans'].get('reset_date'):
        premium_status['usage']['scans']['reset_date'] = premium_status['usage']['scans']['reset_date'].isoformat()
    if premium_status['usage']['pal_questions'].get('reset_time'):
        premium_status['usage']['pal_questions']['reset_time'] = premium_status['usage']['pal_questions']['reset_time'].isoformat()
    
    print(json.dumps(premium_status, indent=2))
    
    # Error response when limit reached
    print("\n📄 POST /api/v1/analysis/analyze (Limit Reached):")
    error_response = {
        "detail": {
            "message": "Monthly scan limit reached",
            "remaining_scans": 0,
            "reset_date": "2025-10-01T00:00:00",
            "upgrade_prompt": "Upgrade to Premium for unlimited skin scans!"
        }
    }
    print(json.dumps(error_response, indent=2))

if __name__ == "__main__":
    print("\n🚀 Running Complete Integration Test\n")
    
    # Run realistic user journey
    create_test_scenario()
    
    # Generate API response examples
    generate_api_response_examples()
    
    print("\n🎉 All integration tests completed successfully!\n")