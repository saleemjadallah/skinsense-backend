#!/usr/bin/env python3
"""
Quick script to check user's skin analysis data
"""

from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to MongoDB
mongodb_url = os.getenv("MONGODB_URL")
client = MongoClient(mongodb_url)
db = client.skinpal  # or client.get_database()

# User ID from the login response
user_id = "6898bdc1d9a3847d8ed38ee9"

print("=== Checking User Data ===")
print(f"User ID: {user_id}")

# Check user exists
user = db.users.find_one({"_id": ObjectId(user_id)})
if user:
    print(f"✅ User found: {user.get('email')}")
    print(f"   Profile: {user.get('profile', {})}")
else:
    print("❌ User not found")

print("\n=== Checking Skin Analyses ===")

# Try different query formats
queries = [
    {"user_id": ObjectId(user_id)},
    {"user_id": user_id},
    {"user_id": str(user_id)},
]

for i, query in enumerate(queries, 1):
    print(f"\nQuery {i}: {query}")
    count = db.skin_analyses.count_documents(query)
    print(f"   Found: {count} analyses")
    
    if count > 0:
        # Get the latest one
        latest = db.skin_analyses.find_one(
            query,
            sort=[("created_at", -1)]
        )
        if latest:
            print(f"   Latest analysis ID: {latest.get('_id')}")
            print(f"   Created at: {latest.get('created_at')}")
            print(f"   Overall score: {latest.get('overall_skin_health_score', 'N/A')}")
            print(f"   Hydration: {latest.get('hydration', 'N/A')}")
            print(f"   Has orbo_response: {'orbo_response' in latest}")
            
            # Check if scores are in orbo_response
            if 'orbo_response' in latest:
                orbo = latest['orbo_response']
                print(f"   ORBO overall: {orbo.get('overall_skin_health_score', 'N/A')}")
                print(f"   ORBO hydration: {orbo.get('hydration', 'N/A')}")

print("\n=== Collection Stats ===")
print(f"Total users: {db.users.count_documents({})}")
print(f"Total skin_analyses: {db.skin_analyses.count_documents({})}")

# Show a sample skin analysis structure
print("\n=== Sample Skin Analysis Structure ===")
sample = db.skin_analyses.find_one({})
if sample:
    print("Keys in document:", list(sample.keys())[:10])
    if 'orbo_response' in sample:
        print("Keys in orbo_response:", list(sample['orbo_response'].keys())[:10])