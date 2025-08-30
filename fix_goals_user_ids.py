#!/usr/bin/env python3
"""
Fix user_id format in goals collection
Converts all string user_ids to ObjectId format
"""

import os
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fix_user_ids():
    """Convert all string user_ids to ObjectId in goals collection"""
    
    # Connect to MongoDB
    connection_string = os.getenv("MONGODB_URL")
    if not connection_string:
        print("❌ MONGODB_URL not found in environment variables")
        return
    
    try:
        client = MongoClient(connection_string)
        db = client.skinpal
        
        print("=" * 80)
        print("FIXING USER_IDs IN GOALS COLLECTION")
        print("=" * 80)
        
        # Find all goals with string user_id
        goals_with_string_id = list(db.goals.find({"user_id": {"$type": "string"}}))
        print(f"\nFound {len(goals_with_string_id)} goals with string user_id")
        
        fixed_count = 0
        error_count = 0
        
        for goal in goals_with_string_id:
            try:
                user_id_str = goal['user_id']
                
                # Check if it's a valid ObjectId string
                if ObjectId.is_valid(user_id_str):
                    user_oid = ObjectId(user_id_str)
                    
                    # Update the goal
                    result = db.goals.update_one(
                        {"_id": goal['_id']},
                        {"$set": {"user_id": user_oid}}
                    )
                    
                    if result.modified_count > 0:
                        print(f"✓ Fixed goal {goal['_id']}: {goal.get('title', 'No title')}")
                        fixed_count += 1
                    else:
                        print(f"⚠ No change for goal {goal['_id']}")
                else:
                    print(f"❌ Invalid ObjectId string: {user_id_str}")
                    error_count += 1
                    
            except Exception as e:
                print(f"❌ Error fixing goal {goal['_id']}: {str(e)}")
                error_count += 1
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"✓ Successfully fixed: {fixed_count} goals")
        print(f"❌ Errors: {error_count} goals")
        
        # Verify the fix
        string_count = db.goals.count_documents({"user_id": {"$type": "string"}})
        objectid_count = db.goals.count_documents({"user_id": {"$type": "objectId"}})
        
        print(f"\nAfter fix:")
        print(f"  Goals with string user_id: {string_count}")
        print(f"  Goals with ObjectId user_id: {objectid_count}")
        
        print("\n✅ Fix completed!")
        
    except Exception as e:
        print(f"❌ Error connecting to database: {str(e)}")

if __name__ == "__main__":
    fix_user_ids()