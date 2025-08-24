from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database
from typing import List
from datetime import datetime

from app.database import get_database
from app.api.deps import get_current_active_user, require_admin
from app.models.user import UserModel
from app.schemas.notification import (
    FCMTokenUpdate, NotificationPreferences, NotificationSend,
    NotificationResponse, NotificationLog, NotificationStats,
    UnreadNotificationCount
)
from app.services.notification_service import notification_service
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/fcm-token", response_model=dict)
async def update_fcm_token(
    token_data: FCMTokenUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Update user's FCM token for push notifications"""
    try:
        notification_service.update_fcm_token(
            user_id=current_user.id,
            fcm_token=token_data.fcm_token,
            db=db
        )
        
        # Also store device info
        db.users.update_one(
            {"_id": current_user.id},
            {
                "$set": {
                    "device_type": token_data.device_type,
                    "device_id": token_data.device_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {"message": "FCM token updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating FCM token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update FCM token"
        )


@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get user's notification preferences"""
    user = db.users.find_one({"_id": current_user.id})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Return preferences or defaults
    preferences = user.get("notification_preferences", {})
    return NotificationPreferences(**preferences)


@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Update user's notification preferences"""
    try:
        db.users.update_one(
            {"_id": current_user.id},
            {
                "$set": {
                    "notification_preferences": preferences.dict(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Reschedule routine reminders if needed
        if preferences.push_enabled:
            notification_service.schedule_routine_reminders(
                current_user.id, db
            )
        
        return preferences
        
    except Exception as e:
        logger.error(f"Error updating notification preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    notification_data: NotificationSend,
    current_user: UserModel = Depends(require_admin),  # Admin only
    db: Database = Depends(get_database)
):
    """Send custom notification to users (Admin only)"""
    try:
        user_ids = [ObjectId(uid) for uid in notification_data.user_ids]
        
        results = notification_service.send_bulk_notifications(
            user_ids=user_ids,
            title=notification_data.title,
            body=notification_data.body,
            data=notification_data.data,
            db=db
        )
        
        return NotificationResponse(
            success=results["success"] > 0,
            message=f"Sent to {results['success']} users",
            sent_count=results["success"],
            failed_count=results["failed"],
            failed_users=results["failed_users"]
        )
        
    except Exception as e:
        logger.error(f"Error sending notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send notifications"
        )


@router.post("/test")
async def test_notification(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Send a test notification to the current user"""
    try:
        success = notification_service.send_push_notification(
            user_id=current_user.id,
            title="Test Notification 🧪",
            body="Your push notifications are working perfectly!",
            data={"type": "test", "timestamp": str(datetime.utcnow())},
            db=db
        )
        
        if success:
            return {"message": "Test notification sent successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send test notification. Please check your FCM token."
            )
            
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/unread-count", response_model=UnreadNotificationCount)
async def get_unread_notification_count(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get count of unread notifications"""
    try:
        count = db.notification_logs.count_documents({
            "user_id": current_user.id,
            "is_read": False
        })
        
        return UnreadNotificationCount(
            count=count,
            has_unread=count > 0
        )
        
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread count"
        )


@router.put("/mark-read/{notification_id}")
async def mark_notification_as_read(
    notification_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Mark a notification as read"""
    try:
        result = db.notification_logs.update_one(
            {
                "_id": ObjectId(notification_id),
                "user_id": current_user.id
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
            
        return {"message": "Notification marked as read"}
        
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        )


@router.put("/mark-all-read")
async def mark_all_notifications_as_read(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Mark all notifications as read"""
    try:
        result = db.notification_logs.update_many(
            {
                "user_id": current_user.id,
                "is_read": False
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "message": f"Marked {result.modified_count} notifications as read",
            "count": result.modified_count
        }
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read"
        )


@router.get("/history", response_model=List[NotificationLog])
async def get_notification_history(
    skip: int = 0,
    limit: int = 20,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get user's notification history"""
    try:
        notifications = list(db.notification_logs.find(
            {"user_id": current_user.id}
        ).sort("sent_at", -1).skip(skip).limit(limit))
        
        return [
            NotificationLog(
                id=str(n["_id"]),
                user_id=str(n["user_id"]),
                title=n["title"],
                body=n["body"],
                notification_type=n.get("type", "custom"),
                sent_at=n["sent_at"],
                status=n.get("status", "sent"),
                error_message=n.get("error_message"),
                is_read=n.get("is_read", False),
                read_at=n.get("read_at")
            )
            for n in notifications
        ]
        
    except Exception as e:
        logger.error(f"Error getting notification history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification history"
        )


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    days: int = 30,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get notification statistics"""
    try:
        stats = notification_service.get_notification_stats(
            user_id=current_user.id,
            days=days,
            db=db
        )
        
        # Get last sent notification
        last_notification = db.notification_logs.find_one(
            {"user_id": current_user.id},
            sort=[("sent_at", -1)]
        )
        
        return NotificationStats(
            total_sent=stats["total_sent"],
            by_type=stats["by_type"],
            period_days=stats["period_days"],
            last_sent=last_notification["sent_at"] if last_notification else None
        )
        
    except Exception as e:
        logger.error(f"Error getting notification stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification statistics"
        )


# Webhook endpoint for handling FCM token refresh
@router.post("/webhook/token-refresh")
async def handle_token_refresh(
    data: dict,
    db: Database = Depends(get_database)
):
    """Handle FCM token refresh webhook"""
    # This would be called by your mobile app when FCM token changes
    try:
        user_id = data.get("user_id")
        new_token = data.get("new_token")
        
        if user_id and new_token:
            notification_service.update_fcm_token(
                user_id=ObjectId(user_id),
                fcm_token=new_token,
                db=db
            )
            
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"Error handling token refresh: {e}")
        return {"status": "error", "message": str(e)}