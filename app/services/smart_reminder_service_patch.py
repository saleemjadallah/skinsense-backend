"""
Patch for Smart Reminder Service to ensure reminders are always generated
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any

def get_fallback_reminders(user_id: str) -> List[Dict[str, Any]]:
    """Generate fallback reminders when database is empty or AI fails"""
    
    now = datetime.utcnow()
    hour = now.hour
    reminders = []
    
    # Morning routine reminder (6 AM - 10 AM)
    if 6 <= hour < 10:
        reminders.append({
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
            "scheduled_for": datetime(now.year, now.month, now.day, 8, 0),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Midday hydration reminder (11 AM - 2 PM)
    if 11 <= hour < 14:
        reminders.append({
            "user_id": user_id,
            "reminder_type": "knowledge",
            "category": "education",
            "priority": 6,
            "content": {
                "title": "Hydration Check",
                "message": "Remember to drink water for healthy, glowing skin from within.",
                "action_text": "Track Water",
                "action_route": "/progress",
                "icon": "droplet",
                "color": "gradient_blue"
            },
            "scheduled_for": datetime(now.year, now.month, now.day, 13, 0),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Afternoon skincare tip (2 PM - 5 PM)
    if 14 <= hour < 17:
        reminders.append({
            "user_id": user_id,
            "reminder_type": "insight",
            "category": "education",
            "priority": 5,
            "content": {
                "title": "Skincare Tip",
                "message": "Apply SPF even indoors! UV rays can penetrate windows.",
                "action_text": "Learn More",
                "action_route": "/care-hub/learn",
                "icon": "lightbulb",
                "color": "gradient_yellow"
            },
            "scheduled_for": datetime(now.year, now.month, now.day, 15, 0),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Evening routine reminder (6 PM - 10 PM)
    if 18 <= hour < 22:
        reminders.append({
            "user_id": user_id,
            "reminder_type": "action",
            "category": "routine",
            "priority": 7,
            "content": {
                "title": "Evening Skincare",
                "message": "Time to cleanse away the day and nourish your skin overnight.",
                "action_text": "Start Routine",
                "action_route": "/routine/evening",
                "icon": "moon",
                "color": "gradient_purple"
            },
            "scheduled_for": datetime(now.year, now.month, now.day, 20, 0),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Progress photo reminder (any time, but especially on weekends)
    if now.weekday() in [5, 6]:  # Saturday or Sunday
        reminders.append({
            "user_id": user_id,
            "reminder_type": "action",
            "category": "progress",
            "priority": 5,
            "content": {
                "title": "Progress Photo Time",
                "message": "Track your skin journey with a quick photo.",
                "action_text": "Take Photo",
                "action_route": "/scan",
                "icon": "camera",
                "color": "gradient_pink"
            },
            "scheduled_for": now + timedelta(hours=1),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Always include at least one reminder
    if not reminders:
        reminders.append({
            "user_id": user_id,
            "reminder_type": "knowledge",
            "category": "education",
            "priority": 5,
            "content": {
                "title": "Daily Skincare Tip",
                "message": "Consistency is key! Stick to your routine for best results.",
                "action_text": "View Tips",
                "action_route": "/care-hub/learn",
                "icon": "star",
                "color": "gradient_gold"
            },
            "scheduled_for": now + timedelta(hours=2),
            "status": "pending",
            "calendar_synced": False,
            "created_at": now,
            "updated_at": now
        })
    
    # Add IDs to reminders
    for i, reminder in enumerate(reminders):
        reminder["id"] = f"fallback_{user_id}_{now.date()}_{i}"
    
    return reminders


def patch_generate_personalized_reminders(self, user_id: str, user_context=None, include_calendar_sync=True):
    """Patched version that always returns reminders"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[PATCHED] Generating reminders for user: {user_id}")
    
    try:
        # Try to get existing reminders first
        existing = self._get_existing_reminders(user_id)
        if existing:
            logger.info(f"[PATCHED] Found {len(existing)} existing reminders")
            return existing
        
        # Try to generate with AI
        try:
            logger.info("[PATCHED] No existing reminders, trying AI generation")
            
            # Build context
            context = self._build_user_context(user_id, user_context or {})
            
            # Generate with AI
            ai_reminders = self._generate_with_ai(context)
            
            if ai_reminders:
                # Save to database
                saved = self._save_reminders(user_id, ai_reminders)
                logger.info(f"[PATCHED] Generated and saved {len(saved)} AI reminders")
                return saved
                
        except Exception as ai_error:
            logger.error(f"[PATCHED] AI generation failed: {str(ai_error)}")
    
    except Exception as e:
        logger.error(f"[PATCHED] Error in reminder generation: {str(e)}")
    
    # Always return fallback reminders if everything else fails
    logger.info("[PATCHED] Using fallback reminders")
    fallback = get_fallback_reminders(user_id)
    
    # Try to save fallbacks to database for next time
    try:
        for reminder in fallback:
            self.db["smart_reminders"].insert_one(reminder.copy())
        logger.info(f"[PATCHED] Saved {len(fallback)} fallback reminders to database")
    except Exception as save_error:
        logger.error(f"[PATCHED] Could not save fallback reminders: {str(save_error)}")
    
    return fallback