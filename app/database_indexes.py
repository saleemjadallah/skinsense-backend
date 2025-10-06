"""
Database indexes for MongoDB collections
Run this script to create necessary indexes for optimal performance
"""
from pymongo import ASCENDING, DESCENDING, TEXT
from app.database import get_database
import logging

logger = logging.getLogger(__name__)

def create_indexes():
    """Create all necessary database indexes"""
    from app.database import connect_to_mongo
    connect_to_mongo()
    db = get_database()
    
    # User collection indexes
    logger.info("Creating user collection indexes...")
    db.users.create_index("email", unique=True)
    try:
        db.users.drop_index("username_1")
    except Exception:
        pass
    db.users.create_index("username")
    db.users.create_index([("created_at", DESCENDING)])
    db.users.create_index("subscription.tier")
    
    # Skin analyses collection indexes
    logger.info("Creating skin analyses collection indexes...")
    db.skin_analyses.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.skin_analyses.create_index("analysis_id", unique=True, sparse=True)  # For ORBO internal IDs
    db.skin_analyses.create_index("orbo_session_id", sparse=True)
    db.skin_analyses.create_index("status")
    db.skin_analyses.create_index([("created_at", DESCENDING)])
    db.skin_analyses.create_index("is_baseline")
    
    # Compound index for data sovereignty queries
    db.skin_analyses.create_index([
        ("user_id", ASCENDING),
        ("status", ASCENDING),
        ("created_at", DESCENDING)
    ])
    
    # Products collection indexes
    logger.info("Creating products collection indexes...")
    db.products.create_index("barcode", unique=True, sparse=True)
    db.products.create_index([("name", TEXT), ("brand", TEXT)])
    db.products.create_index("category")
    db.products.create_index([("community_rating", DESCENDING)])
    
    # Recommendations cache collection indexes with TTL
    logger.info("Creating recommendations cache collection indexes...")
    db.recommendation_cache.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.recommendation_cache.create_index("expires_at", expireAfterSeconds=0)  # TTL index

    # Achievements cache (optional, denormalized)
    logger.info("Creating achievements collection indexes...")
    db.achievements.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
    db.achievements.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    
    # User product interactions collection indexes
    logger.info("Creating user product interactions collection indexes...")
    db.user_product_interactions.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.user_product_interactions.create_index([("user_id", ASCENDING), ("interaction_type", ASCENDING)])
    db.user_product_interactions.create_index("product_data.barcode", sparse=True)
    
    # Routines collection indexes
    logger.info("Creating routines collection indexes...")
    db.routines.create_index([("user_id", ASCENDING), ("is_active", ASCENDING)])
    db.routines.create_index([("user_id", ASCENDING), ("type", ASCENDING)])
    db.routines.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    
    # Routine completions collection indexes
    logger.info("Creating routine completions collection indexes...")
    db.routine_completions.create_index([("user_id", ASCENDING), ("routine_id", ASCENDING)])
    db.routine_completions.create_index([("user_id", ASCENDING), ("completed_at", DESCENDING)])
    db.routine_completions.create_index([("routine_id", ASCENDING), ("completed_at", DESCENDING)])
    
    # Goals collection indexes
    logger.info("Creating goals collection indexes...")
    db.goals.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    db.goals.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    
    # Community posts collection indexes
    logger.info("Creating community posts collection indexes...")
    db.community_posts.create_index([("created_at", DESCENDING)])
    db.community_posts.create_index([("author_id", ASCENDING), ("created_at", DESCENDING)])
    db.community_posts.create_index("tags")
    db.community_posts.create_index([("likes_count", DESCENDING)])
    
    # Notifications collection indexes
    logger.info("Creating notifications collection indexes...")
    db.notifications.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.notifications.create_index([("user_id", ASCENDING), ("read", ASCENDING)])
    db.notifications.create_index("sent_at", expireAfterSeconds=2592000)  # 30 days TTL
    
    # Smart reminders collection indexes
    logger.info("Creating smart reminders collection indexes...")
    db.smart_reminders.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    db.smart_reminders.create_index([("user_id", ASCENDING), ("scheduled_for", ASCENDING)])
    db.smart_reminders.create_index([("user_id", ASCENDING), ("priority", DESCENDING)])
    db.smart_reminders.create_index("expires_at", expireAfterSeconds=0)  # TTL index
    
    # Calendar events collection indexes
    logger.info("Creating calendar events collection indexes...")
    db.calendar_events.create_index([("user_id", ASCENDING), ("start_time", ASCENDING)])
    db.calendar_events.create_index([("user_id", ASCENDING), ("event_type", ASCENDING)])
    
    # Reminder preferences collection indexes
    logger.info("Creating reminder preferences collection indexes...")
    db.reminder_preferences.create_index("user_id", unique=True)
    
    # Reminder interactions collection indexes
    logger.info("Creating reminder interactions collection indexes...")
    db.reminder_interactions.create_index([("user_id", ASCENDING), ("reminder_id", ASCENDING)])
    db.reminder_interactions.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
    
    logger.info("All indexes created successfully!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_indexes()
    print("Database indexes created successfully!")