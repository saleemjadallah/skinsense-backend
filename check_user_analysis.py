#!/usr/bin/env python3
"""Check user's skin analysis data in MongoDB"""

import os
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Connect to MongoDB
mongodb_url = os.getenv("MONGODB_URL")
if not mongodb_url:
    print("ERROR: MONGODB_URL not found in environment")
    exit(1)

client = MongoClient(mongodb_url)
db = client["skinpal"]  # Use the database name directly

# Find user by email
email = "saleem86@icloud.com"
user = db.users.find_one({"email": email})

if not user:
    print(f"User not found: {email}")
    exit(1)

print(f"User found: {user['_id']}")
print(f"Email: {user.get('email')}")
print(f"Subscription: {user.get('subscription', {}).get('tier', 'N/A')}")
print("=" * 50)

# Get recent analyses for this user
user_id = user["_id"]
analyses = list(db.skin_analyses.find(
    {"user_id": user_id}
).sort("created_at", -1).limit(5))

print(f"\nFound {len(analyses)} recent analyses:")
print("=" * 50)

for i, analysis in enumerate(analyses, 1):
    print(f"\nAnalysis {i}:")
    print(f"  ID: {analysis['_id']}")
    print(f"  Created: {analysis.get('created_at', 'N/A')}")
    print(f"  Status: {analysis.get('status', 'N/A')}")
    
    # Check for ORBO response
    orbo_response = analysis.get('orbo_response', {})
    if orbo_response:
        print(f"  Has ORBO Response: YES")
        metrics = orbo_response.get('metrics', {})
        if metrics:
            print(f"  Metrics found:")
            print(f"    - Overall Score: {metrics.get('overall_skin_health_score', 'N/A')}")
            print(f"    - Hydration: {metrics.get('hydration', 'N/A')}")
            print(f"    - Smoothness: {metrics.get('smoothness', 'N/A')}")
            print(f"    - Radiance: {metrics.get('radiance', 'N/A')}")
            print(f"    - Acne: {metrics.get('acne', 'N/A')}")
            # Count non-null metrics
            non_null_metrics = sum(1 for v in metrics.values() if v is not None and v != 'N/A')
            print(f"    - Total non-null metrics: {non_null_metrics}/10")
        else:
            print(f"  Metrics: MISSING or EMPTY")
            # Check if metrics are at top level of orbo_response
            if 'hydration' in orbo_response:
                print(f"  WARNING: Metrics found at top level of orbo_response (wrong structure)")
    else:
        print(f"  Has ORBO Response: NO")
    
    # Check for AI feedback
    ai_feedback = analysis.get('ai_feedback')
    if ai_feedback:
        print(f"  Has AI Feedback: YES")
        print(f"    - Summary: {ai_feedback.get('summary', 'N/A')[:50]}...")
    else:
        print(f"  Has AI Feedback: NO")
    
    # Check for analysis_data (legacy field)
    analysis_data = analysis.get('analysis_data')
    if analysis_data:
        print(f"  Has analysis_data: YES")
        if isinstance(analysis_data, dict):
            if 'overall_skin_health_score' in analysis_data:
                print(f"    - Overall Score (from analysis_data): {analysis_data.get('overall_skin_health_score', 'N/A')}")
    
    print("-" * 40)

# Check for the most recent analysis with complete data
print("\n" + "=" * 50)
print("CHECKING FOR COMPLETE ANALYSES:")
print("=" * 50)

complete_analyses = list(db.skin_analyses.find({
    "user_id": user_id,
    "orbo_response.metrics": {"$exists": True}
}).sort("created_at", -1).limit(3))

if complete_analyses:
    print(f"Found {len(complete_analyses)} analyses with metrics")
    latest = complete_analyses[0]
    metrics = latest.get('orbo_response', {}).get('metrics', {})
    print(f"\nLatest complete analysis:")
    print(f"  Created: {latest.get('created_at')}")
    print(f"  Overall Score: {metrics.get('overall_skin_health_score')}")
else:
    print("NO analyses found with proper metrics structure!")
    print("\nThis is likely the issue - metrics are not being saved properly.")
    
    # Check if metrics exist but in wrong structure
    wrong_structure = list(db.skin_analyses.find({
        "user_id": user_id,
        "orbo_response.hydration": {"$exists": True}
    }).limit(1))
    
    if wrong_structure:
        print("\nWARNING: Found metrics at wrong level in orbo_response!")
        print("Metrics should be in orbo_response.metrics, not directly in orbo_response")