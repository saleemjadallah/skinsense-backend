#!/usr/bin/env python3
"""
Script to apply performance optimization indexes for Progress page
Run this once to create the necessary indexes in MongoDB
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
import logging
import certifi

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def apply_progress_indexes():
    """Apply optimized indexes for Progress page performance"""

    # Get MongoDB connection
    mongodb_url = os.getenv("MONGODB_URL")
    if not mongodb_url:
        logger.error("MONGODB_URL not found in environment variables")
        sys.exit(1)

    try:
        # Connect to MongoDB with proper SSL configuration
        if "mongodb+srv://" in mongodb_url or "mongodb.net" in mongodb_url:
            client = MongoClient(
                mongodb_url,
                tls=True,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                retryWrites=True
            )
        else:
            client = MongoClient(mongodb_url)

        # Use the configured database name (from your config it's "skinpal")
        db_name = os.getenv("DATABASE_NAME", "skinpal")  # The actual database name

        db = client[db_name]
        logger.info(f"Connected to MongoDB successfully (database: {db_name})")

        # Check existing indexes
        logger.info("\n=== Current Indexes ===")
        for collection in ["skin_analyses", "goals", "user_achievements", "achievements"]:
            indexes = db[collection].list_indexes()
            logger.info(f"\n{collection}:")
            for idx in indexes:
                logger.info(f"  - {idx['name']}: {idx.get('key', {})}")

        # Apply new indexes
        logger.info("\n=== Applying New Indexes ===")

        # 1. Optimized compound index for skin_analyses queries
        logger.info("Creating optimized skin_analyses indexes...")
        db.skin_analyses.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING), ("status", ASCENDING)],
            name="user_created_status_idx"
        )
        logger.info("  ✓ Created user_created_status_idx")

        # 2. Goals indexes for progress tracking
        logger.info("Creating goals indexes...")
        db.goals.create_index(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)],
            name="user_updated_idx"
        )
        logger.info("  ✓ Created user_updated_idx")

        # 3. User achievements indexes
        logger.info("Creating user_achievements indexes...")
        db.user_achievements.create_index(
            [("user_id", ASCENDING), ("unlocked_at", DESCENDING)],
            name="user_unlocked_idx"
        )
        db.user_achievements.create_index(
            [("user_id", ASCENDING), ("achievement_id", ASCENDING)],
            name="user_achievement_unique_idx",
            unique=True
        )
        db.user_achievements.create_index(
            [("user_id", ASCENDING), ("is_unlocked", ASCENDING)],
            name="user_unlocked_status_idx"
        )
        logger.info("  ✓ Created user_achievements indexes")

        # 4. Achievements collection indexes (for streak tracking)
        logger.info("Creating achievements collection indexes...")
        db.achievements.create_index(
            [("user_id", ASCENDING), ("date", DESCENDING), ("photos_taken", ASCENDING)],
            name="user_date_photos_idx"
        )
        logger.info("  ✓ Created user_date_photos_idx")

        logger.info("\n=== Index Creation Complete ===")
        logger.info("All indexes have been successfully created!")

        # Verify indexes were created
        logger.info("\n=== Verifying New Indexes ===")
        for collection in ["skin_analyses", "goals", "user_achievements", "achievements"]:
            indexes = db[collection].list_indexes()
            logger.info(f"\n{collection} (after):")
            for idx in indexes:
                logger.info(f"  - {idx['name']}: {idx.get('key', {})}")

    except Exception as e:
        logger.error(f"Error applying indexes: {str(e)}")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()
            logger.info("\nDisconnected from MongoDB")

if __name__ == "__main__":
    logger.info("Starting Progress Page Index Optimization")
    logger.info("=" * 50)
    apply_progress_indexes()
    logger.info("\n✨ Index optimization complete! Progress page queries should now be significantly faster.")