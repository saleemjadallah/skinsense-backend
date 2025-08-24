from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal
from datetime import datetime


class FCMTokenUpdate(BaseModel):
    """Schema for updating FCM token"""
    fcm_token: str = Field(..., min_length=1)
    device_type: Literal["ios", "android"] = "ios"
    device_id: Optional[str] = None


class NotificationPreferences(BaseModel):
    """User notification preferences"""
    push_enabled: bool = True
    
    # Routine reminders
    morning_routine_enabled: bool = True
    morning_routine_time: str = "07:00"  # HH:MM format
    evening_routine_enabled: bool = True
    evening_routine_time: str = "21:00"
    
    # Analysis notifications
    analysis_complete_enabled: bool = True
    weekly_progress_enabled: bool = True
    
    # Product recommendations
    product_recommendations_enabled: bool = True
    
    # Community
    community_mentions_enabled: bool = True
    community_likes_enabled: bool = False
    
    # Achievements
    achievement_unlocked_enabled: bool = True
    streak_milestones_enabled: bool = True


class NotificationSend(BaseModel):
    """Schema for sending custom notification"""
    user_ids: List[str]  # List of user IDs
    title: str = Field(..., max_length=100)
    body: str = Field(..., max_length=300)
    data: Optional[Dict[str, str]] = None
    notification_type: Literal[
        "custom", "routine_reminder", "analysis_complete", 
        "product_recommendation", "achievement", "community"
    ] = "custom"


class NotificationResponse(BaseModel):
    """Response after sending notification"""
    success: bool
    message: str
    sent_count: int = 0
    failed_count: int = 0
    failed_users: List[str] = Field(default_factory=list)


class NotificationLog(BaseModel):
    """Notification log entry"""
    id: str
    user_id: str
    title: str
    body: str
    notification_type: str
    sent_at: datetime
    status: Literal["sent", "failed", "pending"]
    error_message: Optional[str] = None
    is_read: bool = False
    read_at: Optional[datetime] = None


class NotificationStats(BaseModel):
    """Notification statistics"""
    total_sent: int
    by_type: Dict[str, int]
    period_days: int
    last_sent: Optional[datetime] = None


class UnreadNotificationCount(BaseModel):
    """Unread notification count response"""
    count: int
    has_unread: bool