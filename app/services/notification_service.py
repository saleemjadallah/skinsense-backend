import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, messaging
from pymongo.database import Database
from bson import ObjectId

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self):
        self.initialized = False
        
    def initialize(self):
        """Initialize Firebase Admin SDK"""
        try:
            if not self.initialized and settings.firebase_service_account_path:
                cred = credentials.Certificate(settings.firebase_service_account_path)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
    
    def send_push_notification(
        self,
        user_id: ObjectId,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        db: Database = None,
        notification_type: str = "custom"
    ) -> bool:
        """Send push notification to a specific user"""
        if db is None:
            logger.error("Database handle required for send_push_notification")
            return False

        log_status = "failed"
        error_message = None
        try:
            if not self.initialized:
                self.initialize()
            
            if not self.initialized:
                error_message = "Firebase not initialized"
                logger.error(error_message)
                return False
            
            # Get user's FCM token from database
            user = db.users.find_one({"_id": user_id})
            if not user or not user.get("fcm_token"):
                error_message = "No FCM token registered"
                logger.warning(f"No FCM token found for user {user_id}")
                return False
            
            # Create message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=user["fcm_token"],
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=title,
                                body=body,
                            ),
                            badge=1,
                            sound="default",
                        ),
                    ),
                ),
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            log_status = "sent"
            return True
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error sending push notification: {e}")
            return False
        finally:
            try:
                self._log_notification(
                    user_id=user_id,
                    title=title,
                    body=body,
                    db=db,
                    notification_type=notification_type,
                    status=log_status,
                    error_message=error_message,
                    data=data,
                )
            except Exception as log_error:
                logger.error(f"Failed to log notification: {log_error}")
    
    def send_bulk_notifications(
        self,
        user_ids: List[ObjectId],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        db: Database = None
    ) -> Dict[str, Any]:
        """Send notifications to multiple users"""
        results = {
            "success": 0,
            "failed": 0,
            "failed_users": []
        }
        
        for user_id in user_ids:
            success = self.send_push_notification(
                user_id, title, body, data, db
            )
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["failed_users"].append(str(user_id))
        
        return results
    
    def send_routine_reminder(
        self,
        user_id: ObjectId,
        routine_name: str,
        routine_type: str,
        db: Database
    ):
        """Send routine reminder notification"""
        time_of_day = "morning" if routine_type == "morning" else "evening"
        
        title = f"Time for your {time_of_day} routine! ✨"
        body = f"Your '{routine_name}' routine is waiting. Let's keep that streak going!"
        
        data = {
            "type": "routine_reminder",
            "routine_type": routine_type,
            "action": "open_routine"
        }
        
        return self.send_push_notification(user_id, title, body, data, db)
    
    def send_analysis_complete(
        self,
        user_id: ObjectId,
        analysis_id: str,
        overall_score: float,
        db: Database
    ):
        """Send notification when skin analysis is complete"""
        title = "Your skin analysis is ready! 🎉"
        body = f"Great news! Your skin health score is {overall_score:.0f}/100. View your personalized recommendations."
        
        data = {
            "type": "analysis_complete",
            "analysis_id": analysis_id,
            "action": "view_analysis"
        }
        
        return self.send_push_notification(user_id, title, body, data, db)
    
    def send_streak_milestone(
        self,
        user_id: ObjectId,
        streak_days: int,
        db: Database
    ):
        """Send notification for streak milestones"""
        milestones = {
            7: ("One week strong! 🌟", "You've completed your routine for 7 days straight!"),
            14: ("Two weeks of glow! ✨", "14-day streak achieved! Your skin thanks you."),
            30: ("30-day champion! 🏆", "Incredible! You've maintained your routine for a whole month!"),
            60: ("Skincare master! 👑", "60 days of dedication! You're glowing!"),
            100: ("Century club! 💯", "100-day streak! You're a skincare legend!")
        }
        
        if streak_days in milestones:
            title, body = milestones[streak_days]
            data = {
                "type": "streak_milestone",
                "streak_days": str(streak_days),
                "action": "view_progress"
            }
            return self.send_push_notification(user_id, title, body, data, db)
    
    def send_product_recommendation(
        self,
        user_id: ObjectId,
        product_name: str,
        reason: str,
        db: Database
    ):
        """Send personalized product recommendation"""
        title = "New product match found! 🎯"
        body = f"{product_name} could be perfect for {reason}"
        
        data = {
            "type": "product_recommendation",
            "action": "view_product"
        }
        
        return self.send_push_notification(user_id, title, body, data, db)
    
    def schedule_routine_reminders(
        self,
        user_id: ObjectId,
        db: Database
    ):
        """Schedule daily routine reminders based on user preferences"""
        # This would integrate with a task scheduler like Celery
        # For now, we'll just document the structure
        
        user = db.users.find_one({"_id": user_id})
        if not user:
            return
        
        preferences = user.get("notification_preferences", {})
        
        if preferences.get("morning_routine_enabled", True):
            morning_time = preferences.get("morning_routine_time", "07:00")
            # Schedule morning reminder
            
        if preferences.get("evening_routine_enabled", True):
            evening_time = preferences.get("evening_routine_time", "21:00")
            # Schedule evening reminder
    
    def update_fcm_token(
        self,
        user_id: ObjectId,
        fcm_token: str,
        db: Database
    ):
        """Update user's FCM token"""
        db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "fcm_token": fcm_token,
                    "fcm_token_updated_at": datetime.utcnow()
                }
            }
        )
    
    def _log_notification(
        self,
        user_id: ObjectId,
        title: str,
        body: str,
        db: Database,
        notification_type: str = "custom",
        status: str = "sent",
        error_message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """Log sent notifications for analytics and in-app history"""
        if db is None:
            return

        entry: Dict[str, Any] = {
            "user_id": user_id,
            "title": title,
            "body": body,
            "type": notification_type,
            "sent_at": datetime.utcnow(),
            "status": status,
            "error_message": error_message,
            "is_read": False,
            "read_at": None,
        }

        if data:
            entry["data"] = data

        db.notification_logs.insert_one(entry)
    
    def get_notification_stats(
        self,
        user_id: ObjectId,
        db: Database,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get notification statistics for a user"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        total_sent = db.notification_logs.count_documents({
            "user_id": user_id,
            "sent_at": {"$gte": since_date}
        })
        
        by_type = list(db.notification_logs.aggregate([
            {
                "$match": {
                    "user_id": user_id,
                    "sent_at": {"$gte": since_date}
                }
            },
            {
                "$group": {
                    "_id": "$type",
                    "count": {"$sum": 1}
                }
            }
        ]))
        
        return {
            "total_sent": total_sent,
            "by_type": {item["_id"]: item["count"] for item in by_type if item["_id"]},
            "period_days": days
        }


# Global instance
notification_service = NotificationService()
