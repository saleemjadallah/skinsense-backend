#!/usr/bin/env python3
"""
Daily cron job to generate personalized reminders for all active users
Run this at 6 AM daily to prepare reminders for the day
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from app.services.smart_reminder_service import SmartReminderService
from app.database import db, get_database
from bson import ObjectId
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_reminders_for_user(user_id: str, reminder_service: SmartReminderService):
    """Generate reminders for a single user"""
    try:
        logger.info(f"Generating reminders for user: {user_id}")
        
        # Build context for the user
        user_context = {}
        
        # Generate reminders
        reminders = reminder_service.generate_personalized_reminders(
            user_id,
            user_context,
            include_calendar_sync=True
        )
        
        logger.info(f"Generated {len(reminders)} reminders for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate reminders for user {user_id}: {e}")
        return False

def main():
    """Main function to generate daily reminders for all users"""
    logger.info("="*60)
    logger.info("Starting daily reminder generation")
    logger.info("="*60)
    
    try:
        # Initialize database connection first
        from app.database import connect_to_mongo
        connect_to_mongo()
        
        # Get database
        database = get_database()
        
        # Initialize reminder service
        reminder_service = SmartReminderService()
        
        # Get all active users
        # For now, just process specific users or those with recent activity
        users_collection = database["users"]
        
        # Find users who have logged in recently (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        active_users = users_collection.find({
            "$or": [
                {"last_login": {"$gte": thirty_days_ago}},
                {"email": "support@skinsense.app"}  # Always include test user
            ]
        })
        
        success_count = 0
        fail_count = 0
        
        for user in active_users:
            user_id = str(user["_id"])
            user_email = user.get("email", "Unknown")
            
            logger.info(f"Processing user: {user_email} ({user_id})")
            
            # Check if reminders already exist for today
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            
            existing_count = database["smart_reminders"].count_documents({
                "user_id": user_id,
                "scheduled_for": {"$gte": today, "$lt": tomorrow},
                "status": "pending"
            })
            
            if existing_count > 0:
                logger.info(f"  User already has {existing_count} reminders for today, skipping")
                continue
            
            # Generate reminders
            if generate_reminders_for_user(user_id, reminder_service):
                success_count += 1
            else:
                fail_count += 1
        
        logger.info("="*60)
        logger.info(f"Daily reminder generation completed")
        logger.info(f"  Success: {success_count} users")
        logger.info(f"  Failed: {fail_count} users")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Fatal error in daily reminder generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()