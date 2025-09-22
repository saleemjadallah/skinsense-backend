#!/usr/bin/env python3
"""
Migration script to fix ORBO metrics structure in MongoDB
Ensures metrics are properly nested under orbo_response.metrics
"""
import os
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from typing import Dict, Any

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal')

def fix_metrics_structure(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Fix the structure of orbo_response to ensure metrics are properly nested"""

    if 'orbo_response' not in analysis:
        print(f"  No orbo_response field in analysis {analysis.get('_id')}")
        return analysis

    orbo = analysis['orbo_response']

    # If orbo_response is None or not a dict, skip
    if not orbo or not isinstance(orbo, dict):
        print(f"  Invalid orbo_response in analysis {analysis.get('_id')}")
        return analysis

    # Check if metrics are already properly nested
    if 'metrics' in orbo and isinstance(orbo['metrics'], dict):
        # Already has proper structure
        return analysis

    # Check if metrics are at the top level of orbo_response
    metrics_keys = [
        'overall_skin_health_score', 'hydration', 'smoothness',
        'radiance', 'dark_spots', 'firmness', 'fine_lines_wrinkles',
        'acne', 'dark_circles', 'redness'
    ]

    has_metrics_at_top_level = any(key in orbo for key in metrics_keys)

    if has_metrics_at_top_level:
        print(f"  Found metrics at wrong level in analysis {analysis.get('_id')}")

        # Extract metrics
        metrics = {}
        for key in metrics_keys:
            if key in orbo:
                metrics[key] = orbo[key]

        # Create properly structured orbo_response
        fixed_orbo = {
            'metrics': metrics,
            'skin_type': orbo.get('skin_type'),
            'concerns': orbo.get('concerns', []),
            'confidence': orbo.get('confidence', 0.85),
            'analysis_timestamp': orbo.get('analysis_timestamp', datetime.utcnow()),
            'raw_response': orbo.get('raw_response', {})
        }

        # Remove old metric keys from top level
        for key in metrics_keys:
            if key in fixed_orbo:
                del fixed_orbo[key]

        analysis['orbo_response'] = fixed_orbo
        print(f"  Fixed metrics structure for analysis {analysis.get('_id')}")
        return analysis

    return analysis


def main():
    print("Connecting to MongoDB...")
    client = MongoClient(MONGODB_URL)
    db = client.get_database('skinpal')  # Specify database name

    print("Fetching analyses with orbo_response...")

    # Find all analyses with orbo_response
    analyses = db.skin_analyses.find({
        "orbo_response": {"$exists": True, "$ne": None}
    })

    fixed_count = 0
    total_count = 0

    for analysis in analyses:
        total_count += 1
        original_orbo = analysis.get('orbo_response', {})
        fixed_analysis = fix_metrics_structure(analysis)

        # Check if structure was actually changed
        if fixed_analysis['orbo_response'] != original_orbo:
            # Update the document
            result = db.skin_analyses.update_one(
                {"_id": analysis["_id"]},
                {"$set": {"orbo_response": fixed_analysis['orbo_response']}}
            )

            if result.modified_count > 0:
                fixed_count += 1
                print(f"✓ Updated analysis {analysis['_id']}")

                # Verify the fix
                updated = db.skin_analyses.find_one({"_id": analysis["_id"]})
                if updated and 'orbo_response' in updated and 'metrics' in updated['orbo_response']:
                    metrics = updated['orbo_response']['metrics']
                    score = metrics.get('overall_skin_health_score', 'N/A')
                    print(f"  Verified: Overall score = {score}")

    print(f"\n✅ Migration complete!")
    print(f"Total analyses processed: {total_count}")
    print(f"Analyses fixed: {fixed_count}")

    # Test with specific user
    print("\nChecking user saleem86@gmail.com...")
    user = db.users.find_one({"email": "saleem86@gmail.com"})
    if user:
        user_analyses = list(db.skin_analyses.find({
            "user_id": {"$in": [user["_id"], str(user["_id"])]},
            "orbo_response.metrics": {"$exists": True}
        }).limit(5))

        print(f"Found {len(user_analyses)} analyses with proper metrics structure")
        for analysis in user_analyses:
            metrics = analysis['orbo_response']['metrics']
            score = metrics.get('overall_skin_health_score', 'N/A')
            print(f"  - Analysis from {analysis.get('created_at')}: Score = {score}")


if __name__ == "__main__":
    main()