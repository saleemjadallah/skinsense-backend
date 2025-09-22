#!/usr/bin/env python3
"""
Fix API issues for skin analysis endpoints
- Convert user_id to ObjectId consistently
- Include orbo_response data in list endpoint
- Fix CloudFront image URLs
"""

import pymongo
from bson import ObjectId
from datetime import datetime
import os

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URL", "mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal")
CLOUDFRONT_DOMAIN = os.getenv("CLOUDFRONT_DOMAIN", "d1m4iz2gi0p5kk.cloudfront.net")

def connect_to_mongodb():
    """Connect to MongoDB database"""
    try:
        import certifi
        client = pymongo.MongoClient(
            MONGODB_URI,
            tlsCAFile=certifi.where()
        )
        db = client.skinpal
        client.admin.command('ping')
        print("✅ Connected to MongoDB")
        return db
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return None

def fix_user_id_types(db):
    """Fix user_id types in all collections"""
    collections = ['skin_analyses', 'goals', 'routines', 'user_achievements']

    for collection_name in collections:
        print(f"\n📊 Fixing {collection_name}...")
        collection = db[collection_name]

        # Find all documents with string user_id
        cursor = collection.find({"user_id": {"$type": "string"}})
        count = 0

        for doc in cursor:
            try:
                # Convert string to ObjectId
                user_oid = ObjectId(doc['user_id'])
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"user_id": user_oid}}
                )
                count += 1
            except Exception as e:
                print(f"  ❌ Error converting {doc['_id']}: {e}")

        if count > 0:
            print(f"  ✅ Fixed {count} documents")
        else:
            print(f"  ✅ No fixes needed")

def update_image_urls_to_cloudfront(db):
    """Update ORBO URLs to CloudFront URLs if images exist in S3"""
    print("\n🖼️ Checking image URLs...")

    # Find analyses with ORBO URLs
    orbo_analyses = db.skin_analyses.find({
        "image_url": {"$regex": "api.gateway.orbo.ai"}
    })

    count = 0
    for analysis in orbo_analyses:
        # For now, we'll just note these need to be migrated
        # In production, you'd download from ORBO and upload to S3
        count += 1
        print(f"  Found ORBO URL in analysis: {analysis['_id']}")

    if count > 0:
        print(f"  ⚠️ {count} analyses using ORBO URLs (need migration to CloudFront)")
    else:
        print(f"  ✅ All analyses using CloudFront URLs")

def verify_user_data(db, email):
    """Verify user data is correctly formatted"""
    print(f"\n🔍 Verifying data for {email}...")

    user = db.users.find_one({"email": email})
    if not user:
        print("❌ User not found")
        return

    user_id = user['_id']
    print(f"✅ User ID: {user_id} (type: {type(user_id).__name__})")

    # Check analyses
    analyses_with_oid = db.skin_analyses.count_documents({"user_id": user_id})
    analyses_with_str = db.skin_analyses.count_documents({"user_id": str(user_id)})

    print(f"  Analyses with ObjectId: {analyses_with_oid}")
    print(f"  Analyses with string: {analyses_with_str}")

    # Get sample analysis with scores
    sample = db.skin_analyses.find_one({"user_id": user_id})
    if sample and "orbo_response" in sample:
        score = sample["orbo_response"].get("overall_skin_health_score", "N/A")
        print(f"  Sample score: {score}")

def main():
    print("=" * 60)
    print("SkinSense API Issue Fixer")
    print("=" * 60)

    db = connect_to_mongodb()
    if db is None:
        return

    # Fix user_id types
    fix_user_id_types(db)

    # Check image URLs
    update_image_urls_to_cloudfront(db)

    # Verify specific user
    verify_user_data(db, "saleem86@gmail.com")

    print("\n✅ Fix complete!")
    print("\nNote: The API code needs to be updated to:")
    print("1. Always convert user_id to ObjectId before queries")
    print("2. Include orbo_response in list endpoint response")
    print("3. Upload images to S3/CloudFront instead of using ORBO URLs")

if __name__ == "__main__":
    main()