#!/usr/bin/env python3
"""
Manually generate reminders for a specific user (for testing)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from app.services.smart_reminder_service import SmartReminderService
from app.database import connect_to_mongo, get_database
from bson import ObjectId
import argparse

def main():
    parser = argparse.ArgumentParser(description='Generate reminders for a user')
    parser.add_argument('--email', type=str, default='support@skinsense.app',
                        help='User email to generate reminders for')
    parser.add_argument('--force', action='store_true',
                        help='Force generation even if reminders exist')
    args = parser.parse_args()
    
    print(f"Generating reminders for: {args.email}")
    
    # Initialize database
    connect_to_mongo()
    database = get_database()
    
    # Find user
    user = database["users"].find_one({"email": args.email})
    if not user:
        print(f"User not found: {args.email}")
        return
    
    user_id = str(user["_id"])
    print(f"User ID: {user_id}")
    
    # Check existing reminders
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    existing_count = database["smart_reminders"].count_documents({
        "user_id": user_id,
        "scheduled_for": {"$gte": today, "$lt": tomorrow},
        "status": "pending"
    })
    
    if existing_count > 0 and not args.force:
        print(f"User already has {existing_count} reminders for today")
        print("Use --force to regenerate")
        return
    
    if args.force and existing_count > 0:
        # Delete existing reminders for today
        result = database["smart_reminders"].delete_many({
            "user_id": user_id,
            "scheduled_for": {"$gte": today, "$lt": tomorrow}
        })
        print(f"Deleted {result.deleted_count} existing reminders")
    
    # Initialize reminder service
    reminder_service = SmartReminderService()
    
    # Generate reminders
    try:
        reminders = reminder_service.generate_personalized_reminders(
            user_id,
            {},
            include_calendar_sync=True
        )
        
        print(f"\n✅ Generated {len(reminders)} reminders:")
        for reminder in reminders:
            content = reminder.get("content", {})
            scheduled = reminder.get("scheduled_for")
            print(f"  - {content.get('title')} at {scheduled}")
            
    except Exception as e:
        print(f"❌ Failed to generate reminders: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()