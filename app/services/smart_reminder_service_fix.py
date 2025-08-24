"""
Fixed Smart Reminder Service - Always returns reminders
Apply this fix to your smart_reminder_service.py
"""

def generate_personalized_reminders_fixed(
    self,
    user_id: str,
    user_context=None,
    include_calendar_sync=True
):
    """Fixed version that always returns reminders"""
    
    import logging
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    logger.info(f"[FIXED] Generating reminders for user: {user_id}")
    
    try:
        # Check for existing reminders
        existing = self._get_existing_reminders(user_id)
        if existing and len(existing) > 0:
            logger.info(f"[FIXED] Found {len(existing)} existing reminders")
            return existing
        
        logger.info("[FIXED] No existing reminders found, generating new ones")
        
    except Exception as e:
        logger.error(f"[FIXED] Error checking existing: {e}")
    
    # ALWAYS generate fallback reminders if we reach here
    now = datetime.utcnow()
    hour = now.hour
    reminders = []
    
    # Generate time-appropriate reminders
    if 5 <= hour < 12:  # Morning
        reminders.append({
            "id": f"gen_{user_id}_{now.strftime('%Y%m%d')}_morning",
            "user_id": user_id,
            "reminder_type": "action",
            "category": "routine",
            "priority": 8,
            "content": {
                "title": "Morning Skincare Routine",
                "message": "Start your day with clean, protected skin. Don't forget SPF!",
                "action_text": "Start Routine",
                "action_route": "/routine/morning",
                "icon": "sun",
                "color": "gradient_orange"
            },
            "scheduled_for": datetime(now.year, now.month, now.day, 8, 0) if hour < 8 else now + timedelta(minutes=30),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    if 11 <= hour < 15:  # Midday
        reminders.append({
            "id": f"gen_{user_id}_{now.strftime('%Y%m%d')}_hydration",
            "user_id": user_id,
            "reminder_type": "knowledge",
            "category": "education",
            "priority": 6,
            "content": {
                "title": "Hydration Check",
                "message": "Stay hydrated! Your skin needs water from within to glow.",
                "action_text": "Track Water",
                "action_route": "/progress",
                "icon": "droplet",
                "color": "gradient_blue"
            },
            "scheduled_for": datetime(now.year, now.month, now.day, 13, 0) if hour < 13 else now + timedelta(hours=1),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    if 16 <= hour < 22:  # Evening
        reminders.append({
            "id": f"gen_{user_id}_{now.strftime('%Y%m%d')}_evening",
            "user_id": user_id,
            "reminder_type": "action",
            "category": "routine",
            "priority": 7,
            "content": {
                "title": "Evening Skincare",
                "message": "Time to cleanse and repair. Your skin regenerates while you sleep.",
                "action_text": "Start Routine",
                "action_route": "/routine/evening",
                "icon": "moon",
                "color": "gradient_purple"
            },
            "scheduled_for": datetime(now.year, now.month, now.day, 20, 0) if hour < 20 else now + timedelta(minutes=30),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Always have at least one reminder
    if not reminders:
        reminders.append({
            "id": f"gen_{user_id}_{now.strftime('%Y%m%d')}_tip",
            "user_id": user_id,
            "reminder_type": "knowledge",
            "category": "education",
            "priority": 5,
            "content": {
                "title": "Skincare Tip",
                "message": "Consistency is key! Keep up with your daily routine for best results.",
                "action_text": "View Tips",
                "action_route": "/care-hub/learn",
                "icon": "lightbulb",
                "color": "gradient_yellow"
            },
            "scheduled_for": now + timedelta(hours=1),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Add progress photo reminder on certain days
    if now.weekday() in [2, 5]:  # Wednesday or Saturday
        reminders.append({
            "id": f"gen_{user_id}_{now.strftime('%Y%m%d')}_photo",
            "user_id": user_id,
            "reminder_type": "action",
            "category": "progress",
            "priority": 6,
            "content": {
                "title": "Progress Photo Time",
                "message": "Track your skin journey with a quick photo.",
                "action_text": "Take Photo",
                "action_route": "/scan",
                "icon": "camera",
                "color": "gradient_pink"
            },
            "scheduled_for": now + timedelta(hours=2),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Try to save to database (but don't fail if it doesn't work)
    try:
        for reminder in reminders:
            reminder_copy = reminder.copy()
            reminder_copy.pop('id', None)  # Remove id for MongoDB
            self.db["smart_reminders"].insert_one(reminder_copy)
        logger.info(f"[FIXED] Saved {len(reminders)} reminders to database")
    except Exception as save_error:
        logger.warning(f"[FIXED] Could not save to DB: {save_error}, returning in-memory reminders")
    
    logger.info(f"[FIXED] Returning {len(reminders)} reminders")
    return reminders


# Also fix the _get_existing_reminders to be more lenient
def _get_existing_reminders_fixed(self, user_id: str):
    """Fixed version that handles edge cases better"""
    try:
        from datetime import datetime, timedelta
        
        # Get today's date range (but be more flexible)
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        # Look for ANY reminders for this user that are still relevant
        query = {
            "user_id": user_id,
            "status": {"$in": ["pending", "snoozed"]},
            "$or": [
                # Today's reminders
                {"scheduled_for": {"$gte": today, "$lt": tomorrow}},
                # Future reminders within next 24 hours
                {"scheduled_for": {"$gte": now, "$lt": now + timedelta(hours=24)}},
                # Recent reminders that might still be relevant
                {"created_at": {"$gte": now - timedelta(hours=6)}}
            ]
        }
        
        existing = list(self.db["smart_reminders"].find(query))
        
        # Convert ObjectId to string
        for reminder in existing:
            reminder["id"] = str(reminder.pop("_id", ""))
        
        return existing
        
    except Exception as e:
        print(f"[ERROR] Failed to get existing reminders: {e}")
        return []  # Return empty list instead of failing