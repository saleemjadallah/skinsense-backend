#!/usr/bin/env python3
"""
Script to check insights data for a specific user
"""

import sys
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection
MONGODB_URL = "mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal"
client = MongoClient(MONGODB_URL)
db = client["skinpal"]  # Specify the database name

def check_user_insights(email: str):
    """Check insights data for a specific user"""
    print(f"\n=== Checking insights for user: {email} ===\n")
    
    # Find user by email
    user = db.users.find_one({"email": email})
    if not user:
        print(f"❌ User with email {email} not found!")
        return
    
    user_id = user["_id"]
    print(f"✅ Found user: {user.get('username', 'N/A')} (ID: {user_id})")
    
    # Check subscription status
    subscription = user.get("subscription", {})
    print(f"📋 Subscription tier: {subscription.get('tier', 'free')}")
    
    # Check insights preferences
    insights_prefs = user.get("insights_preferences", {})
    print(f"🔧 Insights preferences:")
    print(f"   - Opt out: {insights_prefs.get('opt_out', False)}")
    print(f"   - Frequency: {insights_prefs.get('insight_frequency', 'daily')}")
    
    # Check for insights in database
    print(f"\n=== Daily Insights Data ===")
    
    # Get all insights for this user
    all_insights = list(db.daily_insights.find(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    ).limit(10))
    
    if not all_insights:
        print(f"❌ No insights found for this user")
    else:
        print(f"✅ Found {len(all_insights)} insights records")
        
        for idx, insight in enumerate(all_insights, 1):
            print(f"\n📊 Insight #{idx}:")
            print(f"   - ID: {insight['_id']}")
            print(f"   - Created: {insight.get('created_at', 'N/A')}")
            print(f"   - For date: {insight.get('generated_for_date', 'N/A')}")
            print(f"   - Expires: {insight.get('expires_at', 'N/A')}")
            print(f"   - Viewed: {insight.get('viewed', False)}")
            print(f"   - Insights count: {len(insight.get('insights', []))}")
            
            if insight.get('insights'):
                for i, item in enumerate(insight['insights'][:3], 1):
                    print(f"      {i}. {item.get('title', 'N/A')} ({item.get('category', 'N/A')})")
    
    # Check today's insights specifically
    print(f"\n=== Today's Insights ===")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_insights = db.daily_insights.find_one({
        "user_id": user_id,
        "generated_for_date": {"$gte": today, "$lt": today + timedelta(days=1)}
    })
    
    if today_insights:
        print(f"✅ Today's insights found:")
        print(f"   - Generated at: {today_insights.get('created_at', 'N/A')}")
        print(f"   - Insights count: {len(today_insights.get('insights', []))}")
        for idx, insight in enumerate(today_insights.get('insights', []), 1):
            print(f"   {idx}. {insight.get('title', 'N/A')}")
            print(f"      Category: {insight.get('category', 'N/A')}")
            print(f"      Description: {insight.get('description', 'N/A')[:100]}...")
    else:
        print(f"❌ No insights generated for today")
    
    # Check recent skin analyses
    print(f"\n=== Recent Skin Analyses (used for insights) ===")
    recent_analyses = list(db.skin_analyses.find(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    ).limit(3))
    
    if recent_analyses:
        print(f"✅ Found {len(recent_analyses)} recent analyses")
        for idx, analysis in enumerate(recent_analyses, 1):
            print(f"   {idx}. Analysis from {analysis.get('created_at', 'N/A')}")
            if 'orbo_response' in analysis:
                metrics = analysis['orbo_response'].get('metrics', {})
                overall = metrics.get('overall_skin_health_score', 'N/A')
                print(f"      Overall score: {overall}")
    else:
        print(f"❌ No skin analyses found")
    
    # Check routines (for context)
    print(f"\n=== Active Routines ===")
    active_routines = list(db.routines.find({
        "user_id": user_id,
        "is_active": True
    }))
    print(f"📋 Active routines: {len(active_routines)}")
    
    # Check goals
    print(f"\n=== Active Goals ===")
    active_goals = list(db.goals.find({
        "user_id": user_id,
        "status": "active"
    }))
    print(f"🎯 Active goals: {len(active_goals)}")

if __name__ == "__main__":
    email = "saleem86@icloud.com"
    if len(sys.argv) > 1:
        email = sys.argv[1]
    
    check_user_insights(email)
    print("\n" + "="*50 + "\n")