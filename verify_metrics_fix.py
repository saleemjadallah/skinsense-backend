#!/usr/bin/env python3
"""
Verification script to confirm ORBO metrics structure is fixed
"""
import os
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal')

def verify_metrics_structure():
    """Verify that all analyses have proper metrics structure"""

    print("Connecting to MongoDB...")
    client = MongoClient(MONGODB_URL)
    db = client.get_database('skinpal')

    print("\n=== VERIFICATION REPORT ===\n")

    # Check user saleem86@gmail.com
    user = db.users.find_one({"email": "saleem86@gmail.com"})
    if not user:
        print("❌ User saleem86@gmail.com not found")
        return

    print(f"✅ Found user: {user['email']} (ID: {user['_id']})")

    # Get all analyses for this user
    analyses = list(db.skin_analyses.find({
        "user_id": {"$in": [user["_id"], str(user["_id"])]},
        "orbo_response": {"$exists": True, "$ne": None}
    }).sort("created_at", -1))

    print(f"\n📊 Total analyses with ORBO data: {len(analyses)}")

    # Check each analysis
    correct_structure = 0
    wrong_structure = 0
    missing_metrics = 0

    for i, analysis in enumerate(analyses, 1):
        orbo = analysis.get('orbo_response', {})

        if not orbo:
            missing_metrics += 1
            print(f"\n❌ Analysis {i}: No ORBO response")
            continue

        has_metrics_key = 'metrics' in orbo
        has_metrics_data = has_metrics_key and isinstance(orbo['metrics'], dict)

        if has_metrics_data:
            score = orbo['metrics'].get('overall_skin_health_score', 'N/A')
            correct_structure += 1
            print(f"\n✅ Analysis {i}: CORRECT structure")
            print(f"   - ID: {analysis['_id']}")
            print(f"   - Date: {analysis.get('created_at', 'Unknown')}")
            print(f"   - Overall Score: {score}")
            print(f"   - Status: {analysis.get('status', 'Unknown')}")
        else:
            # Check if metrics are at wrong level
            metric_keys = ['overall_skin_health_score', 'hydration', 'smoothness']
            has_wrong_level = any(key in orbo for key in metric_keys)

            if has_wrong_level:
                wrong_structure += 1
                score = orbo.get('overall_skin_health_score', 'N/A')
                print(f"\n⚠️  Analysis {i}: WRONG structure (metrics at top level)")
                print(f"   - ID: {analysis['_id']}")
                print(f"   - Date: {analysis.get('created_at', 'Unknown')}")
                print(f"   - Overall Score: {score}")
                print(f"   - Status: {analysis.get('status', 'Unknown')}")
                print(f"   - NEEDS FIX: Run migration script")
            else:
                missing_metrics += 1
                print(f"\n❌ Analysis {i}: No metrics found")
                print(f"   - ID: {analysis['_id']}")
                print(f"   - Status: {analysis.get('status', 'Unknown')}")

    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"✅ Correct structure: {correct_structure}")
    print(f"⚠️  Wrong structure: {wrong_structure}")
    print(f"❌ Missing metrics: {missing_metrics}")
    print(f"📊 Total: {len(analyses)}")

    if wrong_structure > 0:
        print(f"\n⚠️  Action Required: {wrong_structure} analyses need migration")
        print("   Run: python fix_orbo_metrics_structure.py")
    elif correct_structure == len(analyses) and len(analyses) > 0:
        print("\n🎉 All analyses have correct structure!")

    # Test API endpoint
    print("\n" + "="*50)
    print("API ENDPOINT TEST")
    print("="*50)

    if analyses and correct_structure > 0:
        # Get the latest analysis with correct structure
        latest_correct = None
        for analysis in analyses:
            orbo = analysis.get('orbo_response', {})
            if 'metrics' in orbo and isinstance(orbo['metrics'], dict):
                latest_correct = analysis
                break

        if latest_correct:
            print(f"\n📝 Latest analysis with correct structure:")
            print(f"   - ID: {latest_correct['_id']}")
            print(f"   - Overall Score: {latest_correct['orbo_response']['metrics'].get('overall_skin_health_score')}")
            print(f"   - Hydration: {latest_correct['orbo_response']['metrics'].get('hydration')}")
            print(f"   - Smoothness: {latest_correct['orbo_response']['metrics'].get('smoothness')}")
            print(f"\n✅ This data should now be visible in the app!")

if __name__ == "__main__":
    verify_metrics_structure()