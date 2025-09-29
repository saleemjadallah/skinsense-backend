#!/usr/bin/env python3
"""
Comprehensive fix and verification for ORBO metrics structure
This script will:
1. Fix any analyses with wrong structure
2. Verify the fixes
3. Generate a test progress summary
"""
import os
import sys
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Dict, Any, List
import json
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL')

def fix_metrics_structure(analysis: Dict[str, Any]) -> bool:
    """Fix the structure of orbo_response to ensure metrics are properly nested"""

    if 'orbo_response' not in analysis:
        return False

    orbo = analysis['orbo_response']

    # If orbo_response is None or not a dict, skip
    if not orbo or not isinstance(orbo, dict):
        return False

    # Check if metrics are already properly nested
    if 'metrics' in orbo and isinstance(orbo['metrics'], dict):
        # Already has proper structure
        return False

    # Check if metrics are at the top level of orbo_response
    metrics_keys = [
        'overall_skin_health_score', 'hydration', 'smoothness',
        'radiance', 'dark_spots', 'firmness', 'fine_lines_wrinkles',
        'acne', 'dark_circles', 'redness'
    ]

    # Extract metrics from top level
    metrics = {}
    has_metrics = False
    for key in metrics_keys:
        if key in orbo:
            metrics[key] = orbo[key]
            has_metrics = True

    if has_metrics:
        # Create properly structured orbo_response
        fixed_orbo = {
            'metrics': metrics,
            'skin_type': orbo.get('skin_type'),
            'concerns': orbo.get('concerns', []),
            'confidence': orbo.get('confidence', 0.85),
            'analysis_timestamp': orbo.get('analysis_timestamp', datetime.utcnow()),
            'raw_response': orbo.get('raw_response', {})
        }

        # Keep other non-metric fields
        for key, value in orbo.items():
            if key not in metrics_keys and key not in fixed_orbo:
                fixed_orbo[key] = value

        analysis['orbo_response'] = fixed_orbo
        return True

    return False


def main():
    if not MONGODB_URL:
        print("ERROR: MONGODB_URL not found in environment")
        return

    print("=" * 80)
    print("FIXING AND VERIFYING ORBO METRICS STRUCTURE")
    print("=" * 80)

    print("\nConnecting to MongoDB...")
    client = MongoClient(MONGODB_URL)
    db = client["skinpal"]

    # Step 1: Fix all analyses with wrong structure
    print("\n📝 STEP 1: Fixing analyses with wrong structure...")

    analyses = db.skin_analyses.find({
        "orbo_response": {"$exists": True, "$ne": None}
    })

    fixed_count = 0
    total_count = 0

    for analysis in analyses:
        total_count += 1
        if fix_metrics_structure(analysis):
            # Update the document
            result = db.skin_analyses.update_one(
                {"_id": analysis["_id"]},
                {"$set": {"orbo_response": analysis['orbo_response']}}
            )
            if result.modified_count > 0:
                fixed_count += 1
                print(f"  ✅ Fixed analysis {analysis['_id']}")

    print(f"\n  Fixed {fixed_count} out of {total_count} analyses")

    # Step 2: Verify the fixes for a specific user
    print("\n📊 STEP 2: Verifying metrics for user saleem86@gmail.com...")

    user = db.users.find_one({"email": "saleem86@gmail.com"})
    if not user:
        print("  ❌ User saleem86@gmail.com not found")
        return

    print(f"  ✅ Found user: {user['email']} (ID: {user['_id']})")

    # Get all analyses for this user
    user_analyses = list(db.skin_analyses.find({
        "user_id": {"$in": [user["_id"], str(user["_id"])]},
        "orbo_response": {"$exists": True, "$ne": None}
    }).sort("created_at", 1))

    print(f"  📈 Total analyses for user: {len(user_analyses)}")

    # Check structure of each analysis
    correct_structure = 0
    wrong_structure = 0

    for i, analysis in enumerate(user_analyses, 1):
        orbo = analysis.get('orbo_response', {})

        if isinstance(orbo, dict) and 'metrics' in orbo and isinstance(orbo['metrics'], dict):
            correct_structure += 1
            # Show sample metrics
            if i <= 3:  # Show first 3
                metrics = orbo['metrics']
                print(f"\n  Analysis {i} (ID: {analysis['_id']}):")
                print(f"    ✅ Correct structure")
                print(f"    Overall Score: {metrics.get('overall_skin_health_score', 'N/A')}")
                print(f"    Hydration: {metrics.get('hydration', 'N/A')}")
                print(f"    Acne: {metrics.get('acne', 'N/A')}")
        else:
            wrong_structure += 1
            print(f"  ❌ Analysis {i} has wrong structure")

    print(f"\n  Summary: {correct_structure} correct, {wrong_structure} wrong")

    # Step 3: Test progress calculation
    if len(user_analyses) >= 2:
        print("\n🧮 STEP 3: Testing progress calculation...")

        from app.services.progress_service import ProgressService
        progress_service = ProgressService()

        # Get first and last analysis
        first_analysis = user_analyses[0]
        last_analysis = user_analyses[-1]

        # Extract metrics
        first_metrics = progress_service._extract_metrics(first_analysis)
        last_metrics = progress_service._extract_metrics(last_analysis)

        print(f"\n  First analysis metrics: {len(first_metrics)} metrics found")
        print(f"  Last analysis metrics: {len(last_metrics)} metrics found")

        # Calculate improvements
        improvements = []
        for metric_key in last_metrics:
            if metric_key in first_metrics:
                old_value = first_metrics[metric_key]
                new_value = last_metrics[metric_key]
                if old_value > 0:
                    change = ((new_value - old_value) / old_value) * 100
                    improvements.append({
                        "metric": metric_key,
                        "name": progress_service.METRIC_INFO.get(metric_key, {}).get("name", metric_key),
                        "old_value": round(old_value, 1),
                        "new_value": round(new_value, 1),
                        "change": round(change, 1)
                    })

        if improvements:
            improvements.sort(key=lambda x: x["change"], reverse=True)
            print("\n  TOP IMPROVEMENTS:")
            for imp in improvements[:5]:
                symbol = "📈" if imp['change'] > 0 else "📉"
                print(f"    {symbol} {imp['name']}: {imp['old_value']} → {imp['new_value']} ({imp['change']:+.1f}%)")
        else:
            print("\n  ❌ No improvements calculated - this is the problem!")

        # Test actual summary generation
        print("\n  Testing full summary generation...")
        summary = progress_service.generate_progress_summary(
            user_id=user["_id"] if isinstance(user["_id"], ObjectId) else ObjectId(str(user["_id"])),
            db=db,
            period_days=90  # Use longer period to catch more analyses
        )

        print(f"\n  Summary Results:")
        print(f"    Has Progress: {summary.get('has_progress')}")
        print(f"    Analyses Count: {summary.get('analyses_count')}")
        print(f"    Top Improvements: {len(summary.get('top_improvements', []))} items")

        if summary.get('top_improvements'):
            print("\n  TOP IMPROVEMENTS FROM SUMMARY:")
            for imp in summary['top_improvements'][:3]:
                print(f"    📈 {imp['name']}: {imp['old_value']} → {imp['new_value']} ({imp['change']:+.1f}%)")

    print("\n" + "=" * 80)
    print("SCRIPT COMPLETE")
    print("=" * 80)

    # Close connection
    client.close()


if __name__ == "__main__":
    main()