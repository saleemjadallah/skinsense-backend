#!/usr/bin/env python3
"""
Fix user_id type inconsistencies across all collections.
Converts all string user_ids to ObjectId for consistency.
"""

from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URL = "mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal"

def fix_collection_user_ids(db, collection_name):
    """Fix user_id types in a specific collection"""
    collection = db[collection_name]
    
    # First, count how many need fixing
    string_count = collection.count_documents({'user_id': {'$type': 'string'}})
    
    if string_count == 0:
        logger.info(f"✓ {collection_name}: No string user_ids found")
        return 0
    
    logger.info(f"⚠ {collection_name}: Found {string_count} documents with string user_ids")
    
    # Get all documents with string user_ids
    documents = list(collection.find({'user_id': {'$type': 'string'}}))
    
    fixed_count = 0
    for doc in documents:
        try:
            # Convert string to ObjectId
            old_user_id = doc['user_id']
            new_user_id = ObjectId(old_user_id)
            
            # Update the document
            result = collection.update_one(
                {'_id': doc['_id']},
                {'$set': {'user_id': new_user_id}}
            )
            
            if result.modified_count > 0:
                fixed_count += 1
                
        except Exception as e:
            logger.error(f"Error fixing document {doc['_id']} in {collection_name}: {e}")
    
    logger.info(f"✓ {collection_name}: Fixed {fixed_count}/{string_count} documents")
    return fixed_count

def check_achievement_triggers(db):
    """Check and trigger achievements for users who should have them"""
    logger.info("\n=== Checking Achievement Triggers ===")
    
    # Get all users
    users = list(db.users.find({'is_active': True}))
    
    for user in users:
        user_id = user['_id']
        
        # Check First Glow achievement (1+ skin analysis)
        analyses_count = db.skin_analyses.count_documents({'user_id': user_id})
        if analyses_count > 0:
            # Check if user has first_glow achievement
            first_glow = db.user_achievements.find_one({
                'user_id': user_id,
                'achievement_id': 'first_glow'
            })
            
            if not first_glow:
                # Create the achievement
                db.user_achievements.insert_one({
                    'user_id': user_id,
                    'achievement_id': 'first_glow',
                    'is_unlocked': True,
                    'unlocked_at': datetime.utcnow(),
                    'progress': 100.0,
                    'progress_data': {'analyses_completed': analyses_count},
                    'last_updated': datetime.utcnow()
                })
                logger.info(f"✓ Created first_glow achievement for user {user.get('email', user_id)}")
        
        # Check Baseline Boss achievement (has baseline + goal)
        has_baseline = db.skin_analyses.count_documents({
            'user_id': user_id,
            'is_baseline': True
        }) > 0
        
        has_goal = db.goals.count_documents({'user_id': user_id}) > 0
        
        if has_baseline and has_goal:
            baseline_boss = db.user_achievements.find_one({
                'user_id': user_id,
                'achievement_id': 'baseline_boss'
            })
            
            if not baseline_boss:
                db.user_achievements.insert_one({
                    'user_id': user_id,
                    'achievement_id': 'baseline_boss',
                    'is_unlocked': True,
                    'unlocked_at': datetime.utcnow(),
                    'progress': 100.0,
                    'progress_data': {'baseline_set': True, 'first_goal': True},
                    'last_updated': datetime.utcnow()
                })
                logger.info(f"✓ Created baseline_boss achievement for user {user.get('email', user_id)}")

def main():
    """Main migration function"""
    logger.info("=== Starting User ID Type Migration ===")
    
    try:
        # Connect to MongoDB
        client = MongoClient(MONGODB_URL)
        db = client['skinpal']
        
        # Collections to fix
        collections_to_fix = [
            'user_achievements',
            'goals',
            'skin_analyses',
            'routines',
            'achievements',  # This seems to be daily tracking, not user achievements
            'pal_sessions',
            'pal_chats',
            'goal_progress',
            'routine_completions',
            'daily_insights',
            'recommendation_cache',
            'user_product_interactions',
            'smart_reminders',
            'notifications',
            'community_posts',
            'post_interactions'
        ]
        
        total_fixed = 0
        
        # Fix each collection
        for collection_name in collections_to_fix:
            if collection_name in db.list_collection_names():
                fixed = fix_collection_user_ids(db, collection_name)
                total_fixed += fixed
        
        logger.info(f"\n=== Migration Complete ===")
        logger.info(f"Total documents fixed: {total_fixed}")
        
        # Now check and create missing achievements
        check_achievement_triggers(db)
        
        # Verify the fix for our test user
        logger.info("\n=== Verification for saleem86@icloud.com ===")
        user = db.users.find_one({'email': 'saleem86@icloud.com'})
        if user:
            for collection_name in ['user_achievements', 'goals', 'skin_analyses']:
                collection = db[collection_name]
                count = collection.count_documents({'user_id': user['_id']})
                logger.info(f"{collection_name}: {count} documents with ObjectId")
        
        client.close()
        logger.info("\n✓ Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    main()