"""
Pydantic schemas for Smart Reminders API
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ReminderContentSchema(BaseModel):
    """Schema for reminder content"""
    title: str
    message: str
    action_text: str
    action_route: str
    icon: str
    color: str


class CreateReminderRequest(BaseModel):
    """Request schema for creating a reminder"""
    reminder_type: str
    category: str
    priority: int = Field(ge=1, le=10)
    content: ReminderContentSchema
    scheduled_for: datetime
    recurrence: Optional[Dict[str, Any]] = None


class ReminderResponse(BaseModel):
    """Response schema for a reminder"""
    id: str
    user_id: str
    reminder_type: str
    category: str
    priority: int
    content: ReminderContentSchema
    scheduled_for: datetime
    status: str
    calendar_synced: bool = False
    calendar_event_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        orm_mode = True


class SmartReminderGenerationRequest(BaseModel):
    """Request for generating smart reminders"""
    include_calendar_sync: bool = True
    context: Optional[Dict[str, Any]] = None


class ReminderInteractionRequest(BaseModel):
    """Request for tracking reminder interaction"""
    action: str  # viewed, clicked, dismissed, snoozed, completed
    engagement_score: Optional[float] = Field(None, ge=0, le=1)


class SnoozeReminderRequest(BaseModel):
    """Request for snoozing a reminder"""
    duration_minutes: int = Field(ge=5, le=1440)  # 5 min to 24 hours


class ReminderPreferencesRequest(BaseModel):
    """Request for updating reminder preferences"""
    enabled: Optional[bool] = None
    calendar_auto_sync: Optional[bool] = None
    morning_routine_time: Optional[str] = None
    evening_routine_time: Optional[str] = None
    max_daily_reminders: Optional[int] = Field(None, ge=1, le=20)
    min_priority_to_show: Optional[int] = Field(None, ge=1, le=10)
    enabled_categories: Optional[List[str]] = None
    push_notifications: Optional[bool] = None
    email_notifications: Optional[bool] = None


class ReminderPreferencesResponse(BaseModel):
    """Response for reminder preferences"""
    enabled: bool
    calendar_auto_sync: bool
    morning_routine_time: str
    evening_routine_time: str
    max_daily_reminders: int
    min_priority_to_show: int
    enabled_categories: List[str]
    push_notifications: bool
    email_notifications: bool
    updated_at: datetime


class CalendarSyncRequest(BaseModel):
    """Request for syncing reminder to calendar"""
    create_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # daily, weekly, monthly
    end_date: Optional[datetime] = None


class CalendarEventResponse(BaseModel):
    """Response for calendar event"""
    id: str
    title: str
    description: Optional[str]
    event_type: str
    start_time: datetime
    end_time: datetime
    color: Optional[str]
    icon: Optional[str]
    is_from_reminder: bool = False
    reminder_id: Optional[str] = None
    status: str
    
    
class BulkReminderGenerationRequest(BaseModel):
    """Request for generating multiple reminders"""
    days_ahead: int = Field(default=7, ge=1, le=30)
    include_calendar_sync: bool = True
    categories: Optional[List[str]] = None