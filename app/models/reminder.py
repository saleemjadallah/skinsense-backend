"""
Smart Reminder models for MongoDB
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from bson import ObjectId


class ReminderContent(BaseModel):
    """Content for a reminder"""
    title: str
    message: str
    action_text: str
    action_route: str
    icon: str
    color: str


class TriggerConditions(BaseModel):
    """Conditions that trigger a reminder"""
    time_based: Optional[datetime] = None
    event_based: Optional[str] = None
    metric_based: Optional[Dict[str, Any]] = Field(default=None)
    weather_based: Optional[Dict[str, Any]] = Field(default=None)


class CalendarIntegration(BaseModel):
    """Calendar integration settings for a reminder"""
    synced_to_calendar: bool = False
    calendar_event_id: Optional[str] = None
    event_type: Optional[str] = None
    event_color: Optional[str] = None
    recurrence: Optional[Dict[str, Any]] = None


class PersonalizationContext(BaseModel):
    """Personalization context for generating reminders"""
    skin_scores: Optional[Dict[str, float]] = None
    active_goals: Optional[List[str]] = None
    routine_completion_rate: Optional[float] = None
    preferred_reminder_times: Optional[List[str]] = None
    interaction_history: Optional[Dict[str, Any]] = None


class SmartReminder(BaseModel):
    """Smart reminder model"""
    user_id: str
    reminder_type: str  # action, knowledge, motivation, preventive
    category: str  # routine, goal, achievement, product, education, community
    priority: int = Field(ge=1, le=10)
    
    content: ReminderContent
    trigger_conditions: TriggerConditions
    calendar_integration: CalendarIntegration = Field(default_factory=CalendarIntegration)
    personalization_context: PersonalizationContext = Field(default_factory=PersonalizationContext)
    
    status: str = "pending"  # pending, shown, interacted, dismissed, snoozed, completed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_for: datetime
    shown_at: Optional[datetime] = None
    interacted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "reminder_type": "action",
                "category": "routine",
                "priority": 8,
                "content": {
                    "title": "Morning Routine Time!",
                    "message": "Your skin hydration improved 12% this week. Keep the momentum!",
                    "action_text": "Start Routine",
                    "action_route": "/routine/morning",
                    "icon": "sun",
                    "color": "gradient_blue"
                },
                "scheduled_for": "2024-01-15T08:00:00Z"
            }
        }


class ReminderInteraction(BaseModel):
    """Track user interactions with reminders"""
    user_id: str
    reminder_id: str
    action: str  # viewed, clicked, dismissed, snoozed, completed
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    engagement_score: float = Field(ge=0, le=1)
    
    
class ReminderPreferences(BaseModel):
    """User preferences for reminders"""
    user_id: str
    enabled: bool = True
    calendar_auto_sync: bool = True
    
    # Time preferences
    morning_routine_time: Optional[str] = "08:00"
    evening_routine_time: Optional[str] = "20:00"
    
    # Frequency preferences
    max_daily_reminders: int = 5
    min_priority_to_show: int = 3
    
    # Category preferences
    enabled_categories: List[str] = Field(default_factory=lambda: [
        "routine", "goal", "achievement", "product", "education", "community"
    ])
    
    # Notification preferences
    push_notifications: bool = True
    email_notifications: bool = False
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CalendarEvent(BaseModel):
    """Enhanced calendar event model with reminder integration"""
    user_id: str
    title: str
    description: Optional[str] = None
    event_type: str  # routine, reminder, appointment, photo, product
    start_time: datetime
    end_time: datetime
    
    # Reminder linkage
    reminder_linked: Optional[Dict[str, Any]] = None
    
    color: Optional[str] = None
    icon: Optional[str] = None
    location: Optional[str] = None
    
    recurrence: Optional[Dict[str, Any]] = None
    notifications: Optional[List[Dict[str, Any]]] = None
    
    status: str = "scheduled"  # scheduled, completed, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)