#!/usr/bin/env python3
"""
Daily cron job to generate personalized insights for all active users
Run this script daily at 6 AM local time (or adjust based on your needs)

Cron example:
0 6 * * * /usr/bin/python3 /path/to/generate_daily_insights.py

Or use Celery Beat for more robust scheduling
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.database import get_database
from app.services.insights_service import get_insights_service
from app.core.config import settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def generate_insights_for_all_users():
    """Generate daily insights for all active users"""
    try:
        logger.info("Starting daily insights generation job")
        
        # Get database instance
        db = get_database()
        
        # Get all active users who haven't opted out
        users = db.users.find({
            "is_active": True,
            "$or": [
                {"insights_preferences.opt_out": False},
                {"insights_preferences": {"$exists": False}}
            ]
        })
        
        total_users = 0
        successful = 0
        failed = 0
        
        for user in users:
            total_users += 1
            user_id = str(user["_id"])
            
            try:
                # Generate insights for user
                insights_service = get_insights_service()
                insights = await insights_service.generate_daily_insights(user_id)
                
                if insights:
                    successful += 1
                    logger.info(f"Generated insights for user {user_id}")
                else:
                    failed += 1
                    logger.warning(f"Failed to generate insights for user {user_id}")
                    
            except Exception as e:
                failed += 1
                logger.error(f"Error generating insights for user {user_id}: {str(e)}")
                continue
            
            # Add small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)
        
        logger.info(f"Insights generation completed. Total: {total_users}, Successful: {successful}, Failed: {failed}")
        
        # Clean up old insights (older than 7 days)
        cleanup_date = datetime.utcnow() - timedelta(days=7)
        deleted = db.daily_insights.delete_many({
            "created_at": {"$lt": cleanup_date}
        })
        logger.info(f"Cleaned up {deleted.deleted_count} old insight records")
        
        return {
            "total_users": total_users,
            "successful": successful,
            "failed": failed,
            "cleanup_count": deleted.deleted_count
        }
        
    except Exception as e:
        logger.error(f"Fatal error in insights generation job: {str(e)}")
        raise

async def generate_insights_for_user(user_id: str):
    """Generate insights for a specific user (useful for testing)"""
    try:
        logger.info(f"Generating insights for user {user_id}")
        insights_service = get_insights_service()
        insights = await insights_service.generate_daily_insights(user_id)
        
        if insights:
            logger.info(f"Successfully generated {len(insights.insights)} insights")
            for i, insight in enumerate(insights.insights):
                logger.info(f"Insight {i+1}: {insight.title} ({insight.category})")
        else:
            logger.error("Failed to generate insights")
            
        return insights
        
    except Exception as e:
        logger.error(f"Error generating insights: {str(e)}")
        raise

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate daily insights for SkinSense users')
    parser.add_argument('--user-id', help='Generate insights for specific user ID')
    parser.add_argument('--dry-run', action='store_true', help='Test run without saving to database')
    
    args = parser.parse_args()
    
    if args.user_id:
        # Generate for specific user
        asyncio.run(generate_insights_for_user(args.user_id))
    else:
        # Generate for all users
        result = asyncio.run(generate_insights_for_all_users())
        print(f"Job completed: {result}")

if __name__ == "__main__":
    main()