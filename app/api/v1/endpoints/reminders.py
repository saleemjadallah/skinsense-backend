"""
Smart Reminders API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId

from app.api.deps import get_current_user
from app.services.smart_reminder_service import SmartReminderService
from app.schemas.reminder import (
    CreateReminderRequest,
    ReminderResponse,
    SmartReminderGenerationRequest,
    ReminderInteractionRequest,
    SnoozeReminderRequest,
    ReminderPreferencesRequest,
    ReminderPreferencesResponse,
    CalendarSyncRequest,
    CalendarEventResponse,
    BulkReminderGenerationRequest
)
from app.services.weather_service import WeatherService

router = APIRouter()

def get_reminder_service():
    """Get reminder service instance"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not hasattr(get_reminder_service, "_instance"):
        logger.info("[REMINDERS API] Creating new SmartReminderService instance")
        try:
            get_reminder_service._instance = SmartReminderService()
            logger.info("[REMINDERS API] SmartReminderService instance created successfully")
        except Exception as e:
            logger.error(f"[REMINDERS API] Failed to create SmartReminderService: {str(e)}")
            logger.error(f"[REMINDERS API] Error type: {type(e).__name__}")
            logger.error("[REMINDERS API] Full traceback:", exc_info=True)
            raise
    else:
        logger.debug("[REMINDERS API] Returning existing SmartReminderService instance")
    return get_reminder_service._instance

def get_weather_service():
    """Get weather service instance"""
    if not hasattr(get_weather_service, "_instance"):
        get_weather_service._instance = WeatherService()
    return get_weather_service._instance


async def gather_user_context(user_id: str, location: Optional[Dict] = None) -> Dict[str, Any]:
    """Gather comprehensive user context for reminder generation"""
    
    context = {}
    
    # Get weather data if location provided
    if location:
        try:
            weather_service = get_weather_service()
            weather_data = weather_service.get_weather(
                location.get("city"),
                location.get("state"),
                location.get("country", "US")
            )
            context["weather"] = {
                "uv_index": weather_data.get("uv_index", 5),
                "temperature": weather_data.get("temperature", 72),
                "humidity": weather_data.get("humidity", 50)
            }
        except:
            # Use default weather if service fails
            context["weather"] = {
                "uv_index": 5,
                "temperature": 72,
                "humidity": 50
            }
    
    return context


@router.get("/smart", response_model=List[ReminderResponse])
async def get_smart_reminders(
    current_user: dict = Depends(get_current_user),
    include_calendar: bool = Query(True, description="Auto-sync to calendar"),
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=10)
):
    """
    Get personalized smart reminders with optional calendar sync
    """
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Convert UserModel to dict if necessary
        if hasattr(current_user, 'dict'):
            user_dict = current_user.dict()
        else:
            user_dict = current_user
            
        user_id = str(user_dict.get('id', user_dict.get('_id')))
        logger.info(f"[REMINDERS API] /smart endpoint called for user: {user_id}")
        
        # Get reminder service
        reminder_service = get_reminder_service()
        
        # First, try to get existing reminders for today (fast)
        logger.info(f"[REMINDERS API] Getting existing reminders for today")
        reminders = reminder_service._get_existing_reminders(user_id)
        
        # If no reminders exist for today, return empty list
        # The cron job will generate them daily
        if not reminders:
            logger.info(f"[REMINDERS API] No reminders found for today, returning empty list")
            reminders = []
        
        logger.info(f"[REMINDERS API] Received {len(reminders)} reminders from service")
        
        # Format response
        logger.info(f"[REMINDERS API] Formatting {min(len(reminders), limit)} reminders for response")
        formatted_reminders = []
        for i, reminder in enumerate(reminders[:limit]):
            try:
                logger.debug(f"[REMINDERS API] Formatting reminder {i+1}: {reminder}")
                formatted_reminder = ReminderResponse(
                    id=str(reminder.get("_id", reminder.get("id", ""))),
                    user_id=str(reminder.get("user_id", user_id)),
                    reminder_type=reminder["reminder_type"],
                    category=reminder["category"],
                    priority=reminder["priority"],
                    content=reminder["content"],
                    scheduled_for=reminder["scheduled_for"],
                    status=reminder["status"],
                    calendar_synced=reminder.get("calendar_synced", False),
                    calendar_event_id=reminder.get("calendar_event_id"),
                    created_at=reminder["created_at"]
                )
                formatted_reminders.append(formatted_reminder)
                logger.debug(f"[REMINDERS API] Successfully formatted reminder {i+1}")
            except Exception as format_error:
                logger.error(f"[REMINDERS API] Error formatting reminder {i+1}: {str(format_error)}")
                logger.error(f"[REMINDERS API] Reminder data that failed: {reminder}")
                raise
        
        logger.info(f"[REMINDERS API] Successfully returning {len(formatted_reminders)} formatted reminders")
        return formatted_reminders
        
    except Exception as e:
        logger.error(f"[REMINDERS API] Error in /smart endpoint: {str(e)}")
        logger.error(f"[REMINDERS API] Error type: {type(e).__name__}")
        logger.error(f"[REMINDERS API] Full traceback:", exc_info=True)
        raise


@router.post("/generate")
async def generate_reminders(
    request: SmartReminderGenerationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger generation of new smart reminders
    """
    
    # Generate reminders with provided context
    reminder_service = get_reminder_service()
    reminders = reminder_service.generate_personalized_reminders(
        current_user["_id"],
        request.context or {},
        include_calendar_sync=request.include_calendar_sync
    )
    
    return {
        "success": True,
        "reminders_generated": len(reminders),
        "calendar_synced": sum(1 for r in reminders if r.get("calendar_synced"))
    }


@router.post("/bulk-generate")
async def bulk_generate_reminders(
    request: BulkReminderGenerationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate reminders for multiple days ahead
    """
    
    all_reminders = []
    
    # Generate reminders for each day
    for day in range(request.days_ahead):
        context = {
            "target_date": (datetime.utcnow() + timedelta(days=day)).isoformat()
        }
        
        if request.categories:
            context["categories"] = request.categories
        
        reminder_service = get_reminder_service()
        reminders = reminder_service.generate_personalized_reminders(
            current_user["_id"],
            context,
            include_calendar_sync=request.include_calendar_sync
        )
        
        all_reminders.extend(reminders)
    
    return {
        "success": True,
        "total_generated": len(all_reminders),
        "days_covered": request.days_ahead,
        "calendar_synced": sum(1 for r in all_reminders if r.get("calendar_synced"))
    }


@router.get("/upcoming", response_model=List[ReminderResponse])
async def get_upcoming_reminders(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(5, ge=1, le=20),
    min_priority: Optional[int] = Query(None, ge=1, le=10)
):
    """
    Get upcoming reminders for the user
    """
    
    reminder_service = get_reminder_service()
    reminders = reminder_service.get_upcoming_reminders(
        current_user["_id"],
        limit=limit,
        min_priority=min_priority
    )
    
    # Format response
    formatted_reminders = []
    for reminder in reminders:
        formatted_reminders.append(ReminderResponse(
            id=str(reminder.get("_id", reminder.get("id", ""))),
            user_id=str(reminder["user_id"]),
            reminder_type=reminder["reminder_type"],
            category=reminder["category"],
            priority=reminder["priority"],
            content=reminder["content"],
            scheduled_for=reminder["scheduled_for"],
            status=reminder["status"],
            calendar_synced=reminder.get("calendar_synced", False),
            calendar_event_id=reminder.get("calendar_integration", {}).get("calendar_event_id"),
            created_at=reminder["created_at"]
        ))
    
    return formatted_reminders


@router.post("/{reminder_id}/interact")
async def track_reminder_interaction(
    reminder_id: str,
    request: ReminderInteractionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Track user interaction with a reminder
    """
    
    reminder_service = get_reminder_service()
    success = reminder_service.track_interaction(
        reminder_id,
        current_user["_id"],
        request.action,
        request.engagement_score or 0.5
    )
    
    return {"success": success}


@router.post("/{reminder_id}/complete")
async def complete_reminder(
    reminder_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a reminder as completed
    """
    
    reminder_service = get_reminder_service()
    success = reminder_service.track_interaction(
        reminder_id,
        current_user["_id"],
        "completed",
        1.0
    )
    
    return {"success": success, "status": "completed"}


@router.post("/{reminder_id}/snooze")
async def snooze_reminder(
    reminder_id: str,
    request: SnoozeReminderRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Snooze a reminder for specified duration
    """
    
    reminder_service = get_reminder_service()
    result = reminder_service.snooze_reminder(
        reminder_id,
        current_user["_id"],
        request.duration_minutes
    )
    
    return result


@router.post("/{reminder_id}/dismiss")
async def dismiss_reminder(
    reminder_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Dismiss a reminder
    """
    
    reminder_service = get_reminder_service()
    success = reminder_service.track_interaction(
        reminder_id,
        current_user["_id"],
        "dismissed",
        0.0
    )
    
    return {"success": success, "status": "dismissed"}


@router.post("/{reminder_id}/sync-to-calendar")
async def sync_reminder_to_calendar(
    reminder_id: str,
    request: Optional[CalendarSyncRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually sync a reminder to the calendar
    """
    
    # Get the reminder
    reminder_service = get_reminder_service()
    reminder = reminder_service.reminders_collection.find_one({
        "_id": ObjectId(reminder_id),
        "user_id": current_user["_id"]
    })
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Check if already synced
    if reminder.get("calendar_integration", {}).get("synced_to_calendar"):
        return {
            "success": True,
            "message": "Reminder already synced to calendar",
            "calendar_event_id": reminder["calendar_integration"]["calendar_event_id"]
        }
    
    # Add recurrence if requested
    if request and request.create_recurring:
        reminder["calendar_integration"] = reminder.get("calendar_integration", {})
        reminder["calendar_integration"]["recurrence"] = {
            "enabled": True,
            "pattern": request.recurrence_pattern or "daily",
            "end_date": request.end_date
        }
    
    # Sync to calendar
    calendar_event_id = reminder_service.sync_to_calendar(
        current_user["_id"],
        reminder
    )
    
    return {
        "success": True,
        "calendar_event_id": calendar_event_id,
        "message": "Reminder synced to calendar successfully"
    }


@router.delete("/{reminder_id}/calendar-sync")
async def remove_calendar_sync(
    reminder_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a reminder from calendar
    """
    
    # Get the reminder
    reminder_service = get_reminder_service()
    reminder = reminder_service.reminders_collection.find_one({
        "_id": ObjectId(reminder_id),
        "user_id": current_user["_id"]
    })
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Check if synced
    if not reminder.get("calendar_integration", {}).get("synced_to_calendar"):
        return {
            "success": True,
            "message": "Reminder not synced to calendar"
        }
    
    # Remove calendar event
    calendar_event_id = reminder["calendar_integration"]["calendar_event_id"]
    reminder_service.calendar_collection.delete_one({
        "_id": ObjectId(calendar_event_id)
    })
    
    # Update reminder
    reminder_service.reminders_collection.update_one(
        {"_id": ObjectId(reminder_id)},
        {
            "$set": {
                "calendar_integration.synced_to_calendar": False,
                "calendar_integration.calendar_event_id": None
            }
        }
    )
    
    return {
        "success": True,
        "message": "Reminder removed from calendar"
    }


@router.get("/calendar-view")
async def get_calendar_formatted_reminders(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """
    Get reminders formatted for calendar view
    """
    
    reminder_service = get_reminder_service()
    query = {
        "user_id": current_user["_id"],
        "calendar_integration.synced_to_calendar": True
    }
    
    if start_date and end_date:
        query["scheduled_for"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    
    reminders = list(reminder_service.reminders_collection.find(query))
    
    # Format for calendar
    calendar_events = []
    for reminder in reminders:
        calendar_events.append({
            "id": str(reminder["_id"]),
            "title": reminder["content"]["title"],
            "start": reminder["scheduled_for"].isoformat(),
            "end": (reminder["scheduled_for"] + timedelta(minutes=15)).isoformat(),
            "color": reminder["content"]["color"],
            "icon": reminder["content"]["icon"],
            "type": "reminder",
            "priority": reminder["priority"]
        })
    
    return calendar_events


@router.put("/{reminder_id}/reschedule")
async def reschedule_reminder(
    reminder_id: str,
    new_time: datetime,
    current_user: dict = Depends(get_current_user)
):
    """
    Reschedule a reminder and update calendar if synced
    """
    
    # Update reminder
    reminder_service = get_reminder_service()
    result = reminder_service.reminders_collection.update_one(
        {"_id": ObjectId(reminder_id), "user_id": current_user["_id"]},
        {
            "$set": {
                "scheduled_for": new_time,
                "status": "pending"
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Update calendar event if synced
    reminder = reminder_service.reminders_collection.find_one({"_id": ObjectId(reminder_id)})
    if reminder and reminder.get("calendar_integration", {}).get("calendar_event_id"):
        reminder_service.calendar_collection.update_one(
            {"_id": ObjectId(reminder["calendar_integration"]["calendar_event_id"])},
            {
                "$set": {
                    "start_time": new_time,
                    "end_time": new_time + timedelta(minutes=15),
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    return {
        "success": True,
        "new_time": new_time.isoformat()
    }


@router.get("/preferences", response_model=ReminderPreferencesResponse)
async def get_reminder_preferences(
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's reminder preferences
    """
    
    reminder_service = get_reminder_service()
    prefs = reminder_service._get_user_preferences(current_user["_id"])
    
    return ReminderPreferencesResponse(
        enabled=prefs["enabled"],
        calendar_auto_sync=prefs["calendar_auto_sync"],
        morning_routine_time=prefs["morning_routine_time"],
        evening_routine_time=prefs["evening_routine_time"],
        max_daily_reminders=prefs["max_daily_reminders"],
        min_priority_to_show=prefs["min_priority_to_show"],
        enabled_categories=prefs["enabled_categories"],
        push_notifications=prefs["push_notifications"],
        email_notifications=prefs["email_notifications"],
        updated_at=prefs["updated_at"]
    )


@router.put("/preferences")
async def update_reminder_preferences(
    request: ReminderPreferencesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update user's reminder preferences
    """
    
    update_data = {}
    
    if request.enabled is not None:
        update_data["enabled"] = request.enabled
    if request.calendar_auto_sync is not None:
        update_data["calendar_auto_sync"] = request.calendar_auto_sync
    if request.morning_routine_time:
        update_data["morning_routine_time"] = request.morning_routine_time
    if request.evening_routine_time:
        update_data["evening_routine_time"] = request.evening_routine_time
    if request.max_daily_reminders is not None:
        update_data["max_daily_reminders"] = request.max_daily_reminders
    if request.min_priority_to_show is not None:
        update_data["min_priority_to_show"] = request.min_priority_to_show
    if request.enabled_categories:
        update_data["enabled_categories"] = request.enabled_categories
    if request.push_notifications is not None:
        update_data["push_notifications"] = request.push_notifications
    if request.email_notifications is not None:
        update_data["email_notifications"] = request.email_notifications
    
    update_data["updated_at"] = datetime.utcnow()
    
    reminder_service = get_reminder_service()
    reminder_service.preferences_collection.update_one(
        {"user_id": current_user["_id"]},
        {"$set": update_data},
        upsert=True
    )
    
    return {
        "success": True,
        "message": "Preferences updated successfully"
    }


@router.post("/preferences/calendar-sync")
async def configure_calendar_sync(
    enable: bool = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Configure automatic calendar sync for reminders
    """
    
    reminder_service = get_reminder_service()
    reminder_service.preferences_collection.update_one(
        {"user_id": current_user["_id"]},
        {"$set": {"calendar_auto_sync": enable}},
        upsert=True
    )
    
    return {
        "success": True,
        "calendar_auto_sync": enable
    }