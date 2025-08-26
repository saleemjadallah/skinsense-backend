"""
Calendar API endpoints for unified event management
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from app.utils.date_utils import get_utc_now

from app.api.deps import get_current_user
from app.database import get_database
from app.services.smart_reminder_service import SmartReminderService

router = APIRouter()

def get_db():
    """Get database instance"""
    return get_database()

def get_reminder_service():
    """Get reminder service instance"""
    if not hasattr(get_reminder_service, "_instance"):
        get_reminder_service._instance = SmartReminderService()
    return get_reminder_service._instance


@router.get("/events")
async def get_calendar_events(
    start_date: datetime = Query(..., description="Start date for event range"),
    end_date: datetime = Query(..., description="End date for event range"),
    event_types: Optional[List[str]] = Query(None, description="Filter by event types"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all calendar events for a date range, aggregated from multiple sources
    """
    
    user_id = current_user["_id"]
    events = []
    db = get_db()
    
    # Helper function to normalize dates
    def normalize_date(dt):
        return datetime(dt.year, dt.month, dt.day)
    
    # 1. Get routine events
    if not event_types or "routine" in event_types:
        routines = list(db["routines"].find({
            "user_id": user_id,
            "is_active": True
        }))
        
        for routine in routines:
            # Generate routine events for each day in range
            current = start_date
            while current <= end_date:
                # Determine routine time based on type
                hour = 8 if routine.get("type") == "morning" else 20
                scheduled_time = datetime(
                    current.year, current.month, current.day, hour, 0
                )
                
                # Check if completed today
                completion = db["routine_completions"].find_one({
                    "user_id": user_id,
                    "routine_id": str(routine["_id"]),
                    "completed_at": {
                        "$gte": normalize_date(current),
                        "$lt": normalize_date(current) + timedelta(days=1)
                    }
                })
                
                events.append({
                    "id": f"routine-{routine['_id']}-{current.isoformat()}",
                    "userId": user_id,
                    "type": "routine",
                    "title": routine.get("name", f"{routine.get('type', 'Daily')} Routine"),
                    "scheduledFor": scheduled_time.isoformat(),
                    "status": "completed" if completion else "pending",
                    "priority": "high",
                    "icon": "sun" if routine.get("type") == "morning" else "moon",
                    "color": "gradient_orange" if routine.get("type") == "morning" else "gradient_purple",
                    "linkedEntityId": str(routine["_id"]),
                    "metadata": {
                        "routine_type": routine.get("type"),
                        "steps_count": len(routine.get("steps", [])),
                        "products": [step.get("product", {}).get("name") for step in routine.get("steps", []) if step.get("product")]
                    }
                })
                
                current += timedelta(days=1)
    
    # 2. Get analysis events (past analyses and scheduled reminders)
    if not event_types or "analysis" in event_types:
        # Past analyses
        analyses = list(db["skin_analyses"].find({
            "user_id": user_id,
            "created_at": {
                "$gte": start_date,
                "$lte": end_date
            }
        }))
        
        for analysis in analyses:
            events.append({
                "id": f"analysis-{analysis['_id']}",
                "userId": user_id,
                "type": "analysis",
                "title": "Skin Analysis",
                "scheduledFor": analysis["created_at"].isoformat(),
                "status": "completed",
                "priority": "medium",
                "icon": "camera",
                "color": "gradient_blue",
                "linkedEntityId": str(analysis["_id"]),
                "metadata": {
                    "overall_score": analysis.get("orbo_response", {}).get("overall_skin_health_score"),
                    "has_photo": True
                }
            })
        
        # Check for daily photo reminders
        today = get_utc_now()
        if start_date <= today <= end_date:
            # Check if photo taken today
            today_analysis = db["skin_analyses"].find_one({
                "user_id": user_id,
                "created_at": {
                    "$gte": normalize_date(today),
                    "$lt": normalize_date(today) + timedelta(days=1)
                }
            })
            
            if not today_analysis:
                events.append({
                    "id": f"analysis-reminder-{today.isoformat()}",
                    "userId": user_id,
                    "type": "analysis",
                    "title": "Daily Progress Photo",
                    "scheduledFor": datetime(today.year, today.month, today.day, 10, 0).isoformat(),
                    "status": "pending",
                    "priority": "medium",
                    "icon": "camera",
                    "color": "gradient_blue",
                    "metadata": {
                        "reminder_type": "daily_photo"
                    }
                })
    
    # 3. Get smart reminders
    if not event_types or "reminder" in event_types:
        reminders = list(db["smart_reminders"].find({
            "user_id": user_id,
            "scheduled_for": {
                "$gte": start_date,
                "$lte": end_date
            }
        }))
        
        for reminder in reminders:
            events.append({
                "id": str(reminder["_id"]),
                "userId": user_id,
                "type": "reminder",
                "title": reminder["content"]["title"],
                "scheduledFor": reminder["scheduled_for"].isoformat(),
                "status": reminder.get("status", "pending"),
                "priority": _map_priority(reminder.get("priority", 5)),
                "description": reminder["content"]["message"],
                "icon": reminder["content"].get("icon"),
                "color": reminder["content"].get("color"),
                "metadata": {
                    "category": reminder.get("category"),
                    "reminder_type": reminder.get("reminder_type"),
                    "action_text": reminder["content"].get("action_text"),
                    "action_route": reminder["content"].get("action_route")
                }
            })
    
    # 4. Get goal events (milestones and deadlines)
    if not event_types or "goal" in event_types:
        goals = list(db["goals"].find({
            "user_id": user_id,
            "status": "active",
            "target_date": {
                "$gte": start_date,
                "$lte": end_date
            }
        }))
        
        for goal in goals:
            events.append({
                "id": f"goal-{goal['_id']}",
                "userId": user_id,
                "type": "goal",
                "title": f"Goal: {goal['title']}",
                "scheduledFor": goal["target_date"].isoformat(),
                "status": "pending",
                "priority": "high" if (goal["target_date"] - get_utc_now()).days <= 7 else "medium",
                "icon": "flag",
                "color": "gradient_green",
                "linkedEntityId": str(goal["_id"]),
                "metadata": {
                    "current_progress": goal.get("current_progress", 0),
                    "target_value": goal.get("target_value", 100),
                    "metric": goal.get("target_metric"),
                    "days_remaining": (goal["target_date"] - get_utc_now()).days
                }
            })
    
    # Sort events by scheduled time
    events.sort(key=lambda x: x["scheduledFor"])
    
    return {
        "events": events,
        "total": len(events),
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }


@router.post("/events/{event_id}/complete")
async def complete_calendar_event(
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a calendar event as completed
    """
    
    db = get_db()
    
    # Parse event ID to determine type
    if event_id.startswith("routine-"):
        # Complete routine
        parts = event_id.split("-")
        routine_id = parts[1]
        
        # Record completion
        db["routine_completions"].insert_one({
            "user_id": current_user["_id"],
            "routine_id": routine_id,
            "completed_at": get_utc_now(),
            "steps_completed": [],  # Could be enhanced
            "duration_minutes": 0,  # Could be calculated
        })
        
        return {"success": True, "message": "Routine marked as completed"}
    
    elif event_id.startswith("analysis-"):
        # Analysis events are completed by taking a photo
        return {"success": True, "message": "Please take a photo to complete analysis"}
    
    elif event_id.startswith("goal-"):
        # Goals are completed through progress updates
        return {"success": True, "message": "Goal progress updated"}
    
    else:
        # Assume it's a reminder ID
        db["smart_reminders"].update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"status": "completed"}}
        )
        
        return {"success": True, "message": "Event marked as completed"}


@router.put("/events/{event_id}/reschedule")
async def reschedule_calendar_event(
    event_id: str,
    new_time: datetime,
    current_user: dict = Depends(get_current_user)
):
    """
    Reschedule a calendar event
    """
    
    db = get_db()
    
    # For reminders
    if not event_id.startswith("routine-") and not event_id.startswith("analysis-"):
        db["smart_reminders"].update_one(
            {"_id": ObjectId(event_id), "user_id": current_user["_id"]},
            {"$set": {"scheduled_for": new_time}}
        )
    
    return {"success": True, "message": "Event rescheduled", "new_time": new_time.isoformat()}


@router.get("/summary/{date}")
async def get_day_summary(
    date: datetime,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a summary of events for a specific day
    """
    
    start_of_day = datetime(date.year, date.month, date.day)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get all events for the day
    result = await get_calendar_events(
        start_date=start_of_day,
        end_date=end_of_day,
        current_user=current_user
    )
    
    events = result["events"]
    
    # Calculate summary statistics
    total_events = len(events)
    completed_events = len([e for e in events if e["status"] == "completed"])
    pending_events = len([e for e in events if e["status"] == "pending"])
    
    # Check for specific event types
    has_analysis = any(e["type"] == "analysis" for e in events)
    has_routines = any(e["type"] == "routine" for e in events)
    
    return {
        "date": date.isoformat(),
        "totalEvents": total_events,
        "completedEvents": completed_events,
        "pendingEvents": pending_events,
        "events": events,
        "isFullyCompleted": pending_events == 0 and completed_events > 0,
        "hasAnalysis": has_analysis,
        "hasRoutines": has_routines,
        "completionRate": completed_events / total_events if total_events > 0 else 0
    }


def _map_priority(priority_int: int) -> str:
    """Map integer priority to string"""
    if priority_int >= 9:
        return "urgent"
    elif priority_int >= 7:
        return "high"
    elif priority_int >= 4:
        return "medium"
    else:
        return "low"