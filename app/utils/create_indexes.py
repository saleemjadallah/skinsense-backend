"""
Script to create MongoDB indexes for performance optimization
Run this script to ensure all necessary indexes are created
"""
import logging
import os
from pymongo import MongoClient, ASCENDING, DESCENDING

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get MongoDB URL from environment or use the one provided
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://support:olaabdel88@skinpal.h3jgomd.mongodb.net/?retryWrites=true&w=majority&appName=skinpal")
DATABASE_NAME = "skinpal"


def create_indexes():
    """Create all necessary indexes for optimal performance"""
    
    try:
        # Connect to MongoDB
        client = MongoClient(MONGODB_URL)
        db = client[DATABASE_NAME]
        
        logger.info(f"Connected to database: {DATABASE_NAME}")
        
        # Plans collection indexes
        logger.info("Creating indexes for plans collection...")
        
        # Compound index for user plans queries with status filter
        db.plans.create_index([
            ("user_id", ASCENDING),
            ("status", ASCENDING),
            ("created_at", DESCENDING)
        ], name="user_plans_status")
        
        # Single field index for plan lookups
        db.plans.create_index([("_id", ASCENDING)], name="plan_id")
        
        # Index for active plans
        db.plans.create_index([
            ("status", ASCENDING),
            ("user_id", ASCENDING)
        ], name="active_plans")
        
        logger.info("✓ Plans collection indexes created")
        
        # Plan Progress collection indexes
        logger.info("Creating indexes for plan_progress collection...")
        
        db.plan_progress.create_index([
            ("plan_id", ASCENDING),
            ("week_number", DESCENDING)
        ], name="plan_progress_week")
        
        db.plan_progress.create_index([
            ("user_id", ASCENDING),
            ("recorded_at", DESCENDING)
        ], name="user_progress_timeline")
        
        logger.info("✓ Plan progress collection indexes created")
        
        # Plan Daily Progress collection indexes
        logger.info("Creating indexes for plan_daily_progress collection...")
        
        db.plan_daily_progress.create_index([
            ("plan_id", ASCENDING),
            ("date", ASCENDING)
        ], name="daily_progress_date", unique=True)
        
        db.plan_daily_progress.create_index([
            ("user_id", ASCENDING),
            ("date", DESCENDING)
        ], name="user_daily_progress")
        
        logger.info("✓ Plan daily progress collection indexes created")
        
        # Routines collection indexes
        logger.info("Creating indexes for routines collection...")
        
        db.routines.create_index([
            ("user_id", ASCENDING),
            ("type", ASCENDING),
            ("is_active", ASCENDING)
        ], name="user_active_routines")
        
        db.routines.create_index([
            ("_id", ASCENDING),
            ("user_id", ASCENDING)
        ], name="routine_ownership")
        
        logger.info("✓ Routines collection indexes created")
        
        # Goals collection indexes
        logger.info("Creating indexes for goals collection...")
        
        db.goals.create_index([
            ("user_id", ASCENDING),
            ("status", ASCENDING),
            ("created_at", DESCENDING)
        ], name="user_goals_status")
        
        db.goals.create_index([
            ("_id", ASCENDING),
            ("user_id", ASCENDING)
        ], name="goal_ownership")
        
        logger.info("✓ Goals collection indexes created")
        
        # Skin analyses collection indexes
        logger.info("Creating indexes for skin_analyses collection...")
        
        db.skin_analyses.create_index([
            ("user_id", ASCENDING),
            ("created_at", DESCENDING)
        ], name="user_analyses_timeline")
        
        db.skin_analyses.create_index([
            ("user_id", ASCENDING),
            ("is_baseline", ASCENDING),
            ("created_at", DESCENDING)
        ], name="baseline_analyses")
        
        logger.info("✓ Skin analyses collection indexes created")
        
        # List all indexes for verification
        logger.info("\n=== Index Summary ===")
        for collection_name in ["plans", "plan_progress", "plan_daily_progress", 
                               "routines", "goals", "skin_analyses"]:
            collection = db[collection_name]
            indexes = collection.list_indexes()
            logger.info(f"\n{collection_name} indexes:")
            for index in indexes:
                logger.info(f"  - {index['name']}: {index['key']}")
        
        logger.info("\n✅ All indexes created successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")
        return False


if __name__ == "__main__":
    success = create_indexes()
    if success:
        print("\n✅ Database indexes created successfully!")
    else:
        print("\n❌ Failed to create some indexes. Check logs for details.")