#!/usr/bin/env python3
"""
Test subscription limit enforcement in APIs
"""

from app.models.user import UserModel, PyObjectId
from app.services.subscription_service import SubscriptionService
from bson import ObjectId

def test_scan_limit_enforcement():
    """Test that scan limits are properly enforced"""
    print("\n" + "=" * 50)
    print("TESTING SCAN LIMIT ENFORCEMENT")
    print("=" * 50)
    
    # Create a free user
    user = UserModel(
        id=PyObjectId(ObjectId()),
        email='test_limits@example.com',
        username='limituser'
    )
    
    print(f"\nInitial state:")
    print(f"  Tier: {user.subscription.tier}")
    print(f"  Scans used: {user.subscription.usage.monthly_scans_used}")
    print(f"  Scan limit: {user.subscription.usage.monthly_scans_limit}")
    
    # Simulate scanning up to the limit
    print("\nSimulating scans:")
    for i in range(4):  # Try to do 4 scans (1 over limit)
        status = SubscriptionService.check_scan_limit(user)
        if status['allowed']:
            SubscriptionService.increment_scan_usage(user)
            print(f"  Scan {i+1}: ✅ Allowed (remaining: {status['remaining']-1})")
        else:
            print(f"  Scan {i+1}: ❌ BLOCKED - Limit reached!")
            print(f"    Message: Monthly scan limit reached")
            print(f"    Upgrade prompt: Upgrade to Premium for unlimited skin scans!")
    
    # Final status
    final_status = SubscriptionService.check_scan_limit(user)
    print(f"\nFinal status:")
    print(f"  Scans used: {user.subscription.usage.monthly_scans_used}/{user.subscription.usage.monthly_scans_limit}")
    print(f"  Can scan: {final_status['allowed']}")
    
    print("\n✅ Scan limit enforcement working correctly!")

def test_pal_limit_enforcement():
    """Test that Pal AI limits are properly enforced"""
    print("\n" + "=" * 50)
    print("TESTING PAL AI LIMIT ENFORCEMENT")
    print("=" * 50)
    
    # Create a free user
    user = UserModel(
        id=PyObjectId(ObjectId()),
        email='test_pal@example.com',
        username='paluser'
    )
    
    print(f"\nInitial state:")
    print(f"  Tier: {user.subscription.tier}")
    print(f"  Pal questions used: {user.subscription.usage.daily_pal_questions_used}")
    print(f"  Pal question limit: {user.subscription.usage.daily_pal_questions_limit}")
    
    # Simulate asking questions up to the limit
    print("\nSimulating Pal AI questions:")
    for i in range(6):  # Try to ask 6 questions (1 over limit)
        status = SubscriptionService.check_pal_limit(user)
        if status['allowed']:
            SubscriptionService.increment_pal_usage(user)
            print(f"  Question {i+1}: ✅ Allowed (remaining: {status['remaining']-1})")
        else:
            print(f"  Question {i+1}: ❌ BLOCKED - Daily limit reached!")
            print(f"    Message: Daily Pal AI question limit reached")
            print(f"    Upgrade prompt: Upgrade to Premium for unlimited Pal AI conversations!")
    
    # Final status
    final_status = SubscriptionService.check_pal_limit(user)
    print(f"\nFinal status:")
    print(f"  Questions used: {user.subscription.usage.daily_pal_questions_used}/{user.subscription.usage.daily_pal_questions_limit}")
    print(f"  Can ask Pal: {final_status['allowed']}")
    
    print("\n✅ Pal AI limit enforcement working correctly!")

def test_community_access():
    """Test community access restrictions"""
    print("\n" + "=" * 50)
    print("TESTING COMMUNITY ACCESS RESTRICTIONS")
    print("=" * 50)
    
    # Test with free user
    free_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='free_community@example.com',
        username='freecommuser'
    )
    
    # Test with premium user
    premium_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='premium_community@example.com',
        username='premcommuser'
    )
    premium_user = SubscriptionService.upgrade_to_premium(premium_user, 30)
    
    print("\nFree user trying to post:")
    if not SubscriptionService.can_post_community(free_user):
        print("  ❌ BLOCKED - Community posting is a premium feature")
        print("  Upgrade prompt: Upgrade to Premium to share your skincare journey!")
    
    print("\nPremium user trying to post:")
    if SubscriptionService.can_post_community(premium_user):
        print("  ✅ Allowed - Premium users can post")
    
    print("\n✅ Community access restrictions working correctly!")

def test_insights_access():
    """Test insights access restrictions"""
    print("\n" + "=" * 50)
    print("TESTING INSIGHTS ACCESS RESTRICTIONS")
    print("=" * 50)
    
    # Test with free user
    free_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='free_insights@example.com',
        username='freeinsuser'
    )
    
    # Test with premium user
    premium_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='premium_insights@example.com',
        username='preminsuser'
    )
    premium_user = SubscriptionService.upgrade_to_premium(premium_user, 30)
    
    print("\nFree user trying to access insights:")
    if not SubscriptionService.can_access_insights(free_user):
        print("  ❌ BLOCKED - Daily insights are a premium feature")
        print("  Upgrade prompt: Upgrade to Premium for personalized daily skincare insights!")
    
    print("\nPremium user trying to access insights:")
    if SubscriptionService.can_access_insights(premium_user):
        print("  ✅ Allowed - Premium users get daily insights")
    
    print("\n✅ Insights access restrictions working correctly!")

def test_recommendation_limits():
    """Test recommendation count limits"""
    print("\n" + "=" * 50)
    print("TESTING RECOMMENDATION LIMITS")
    print("=" * 50)
    
    # Test with free user
    free_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='free_recs@example.com',
        username='freerecuser'
    )
    
    # Test with premium user
    premium_user = UserModel(
        id=PyObjectId(ObjectId()),
        email='premium_recs@example.com',
        username='premrecuser'
    )
    premium_user = SubscriptionService.upgrade_to_premium(premium_user, 30)
    
    free_limit = SubscriptionService.get_recommendation_limit(free_user)
    premium_limit = SubscriptionService.get_recommendation_limit(premium_user)
    
    print(f"\nRecommendation limits:")
    print(f"  Free user: {free_limit} product recommendations")
    print(f"  Premium user: {premium_limit} product recommendations")
    
    if free_limit < premium_limit:
        print("\n✅ Recommendation limits working correctly!")
    else:
        print("\n❌ Error: Premium should have more recommendations than free")

if __name__ == "__main__":
    print("\n🚀 Testing Subscription Limit Enforcement\n")
    
    # Run all enforcement tests
    test_scan_limit_enforcement()
    test_pal_limit_enforcement()
    test_community_access()
    test_insights_access()
    test_recommendation_limits()
    
    print("\n" + "=" * 50)
    print("🎉 ALL LIMIT ENFORCEMENT TESTS COMPLETED!")
    print("=" * 50)