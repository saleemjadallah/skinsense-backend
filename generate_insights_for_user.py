#!/usr/bin/env python3
"""
Manual script to generate insights for a specific user
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from bson import ObjectId

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent))

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

async def generate_insights_for_user_by_email(email: str):
    """Generate insights for a specific user by email"""
    try:
        logger.info(f"Generating insights for user with email: {email}")
        
        # Get database instance
        db = get_database()
        
        # Find user by email
        user = db.users.find_one({"email": email})
        if not user:
            logger.error(f"User with email {email} not found!")
            return None
        
        user_id = str(user["_id"])
        logger.info(f"Found user: {user.get('username', 'N/A')} (ID: {user_id})")
        
        # Check subscription status
        subscription = user.get("subscription", {})
        tier = subscription.get("tier", "free")
        logger.info(f"User subscription tier: {tier}")
        
        # For testing, we'll bypass the premium check
        if tier == "free":
            logger.warning("User has free tier, but generating insights anyway for testing...")
        
        # Generate insights
        insights_service = get_insights_service()
        insights = await insights_service.generate_daily_insights(user_id)
        
        if insights:
            logger.info(f"Successfully generated {len(insights.insights)} insights:")
            for i, insight in enumerate(insights.insights):
                logger.info(f"  {i+1}. {insight.title} ({insight.category})")
                logger.info(f"     Priority: {insight.priority}")
                logger.info(f"     Description: {insight.description[:100]}...")
            
            # Verify it was saved to database
            saved_insights = db.daily_insights.find_one({"_id": ObjectId(insights.id)})
            if saved_insights:
                logger.info(f"✅ Insights saved to database with ID: {insights.id}")
            else:
                logger.error("❌ Insights were not saved to database!")
        else:
            logger.error("Failed to generate insights")
        
        return insights
        
    except Exception as e:
        logger.error(f"Error generating insights: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

async def check_and_clean_old_insights(email: str):
    """Check and optionally clean old insights for a user"""
    try:
        # Get database instance
        db = get_database()
        
        # Find user by email
        user = db.users.find_one({"email": email})
        if not user:
            logger.error(f"User with email {email} not found!")
            return
        
        user_id = user["_id"]
        
        # Check existing insights
        existing_insights = list(db.daily_insights.find(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        ).limit(10))
        
        logger.info(f"Found {len(existing_insights)} existing insights for user")
        
        if existing_insights:
            for insight in existing_insights:
                logger.info(f"  - Created: {insight.get('created_at', 'N/A')}, Insights count: {len(insight.get('insights', []))}")
        
        # Clean up old insights (optional)
        week_ago = datetime.utcnow() - timedelta(days=7)
        deleted = db.daily_insights.delete_many({
            "user_id": user_id,
            "created_at": {"$lt": week_ago}
        })
        
        if deleted.deleted_count > 0:
            logger.info(f"Cleaned up {deleted.deleted_count} old insights")
        
    except Exception as e:
        logger.error(f"Error checking insights: {str(e)}")
        raise

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate insights for a specific SkinSense user')
    parser.add_argument('email', help='User email address')
    parser.add_argument('--clean', action='store_true', help='Clean old insights before generating')
    
    args = parser.parse_args()
    
    if args.clean:
        asyncio.run(check_and_clean_old_insights(args.email))
    
    # Generate new insights
    asyncio.run(generate_insights_for_user_by_email(args.email))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_insights_for_user.py <email>")
        print("Example: python generate_insights_for_user.py saleem86@icloud.com")
        sys.exit(1)
    
    main()