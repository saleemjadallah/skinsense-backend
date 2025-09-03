from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.models.user import UserModel, SubscriptionUsage
from app.core.exceptions import SubscriptionLimitExceeded
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Service for managing user subscriptions and usage limits"""
    
    FEATURES = {
        "free": {
            "monthly_scans": 3,
            "daily_pal_questions": 5,
            "community_post": False,
            "insights_access": False,
            "progress_history_days": 7,
            "recommendations_count": 4,
            "export_data": False,
            "priority_support": False
        },
        "premium": {
            "monthly_scans": -1,  # Unlimited
            "daily_pal_questions": -1,  # Unlimited
            "community_post": True,
            "insights_access": True,
            "progress_history_days": -1,  # Unlimited
            "recommendations_count": 10,
            "export_data": True,
            "priority_support": True
        }
    }
    
    @classmethod
    def is_premium(cls, user: UserModel) -> bool:
        """Check if user has active premium subscription"""
        if user.subscription.tier == "premium":
            if user.subscription.expires_at:
                return user.subscription.expires_at > datetime.utcnow()
            return True
        return False
    
    @classmethod
    def check_scan_limit(cls, user: UserModel) -> Dict[str, Any]:
        """Check if user can perform a scan"""
        if cls.is_premium(user):
            return {"allowed": True, "remaining": -1, "limit": -1}
        
        # Reset monthly counter if needed
        cls._reset_monthly_usage_if_needed(user)
        
        usage = user.subscription.usage
        remaining = usage.monthly_scans_limit - usage.monthly_scans_used
        
        return {
            "allowed": usage.monthly_scans_used < usage.monthly_scans_limit,
            "remaining": max(0, remaining),
            "limit": usage.monthly_scans_limit,
            "reset_date": cls._get_next_reset_date(usage.last_reset_date)
        }
    
    @classmethod
    def increment_scan_usage(cls, user: UserModel) -> None:
        """Increment scan usage counter"""
        if not cls.is_premium(user):
            cls._reset_monthly_usage_if_needed(user)
            user.subscription.usage.monthly_scans_used += 1
    
    @classmethod
    def check_pal_limit(cls, user: UserModel) -> Dict[str, Any]:
        """Check if user can ask Pal AI a question"""
        if cls.is_premium(user):
            return {"allowed": True, "remaining": -1, "limit": -1}
        
        # Reset daily counter if needed
        cls._reset_daily_pal_usage_if_needed(user)
        
        usage = user.subscription.usage
        remaining = usage.daily_pal_questions_limit - usage.daily_pal_questions_used
        
        return {
            "allowed": usage.daily_pal_questions_used < usage.daily_pal_questions_limit,
            "remaining": max(0, remaining),
            "limit": usage.daily_pal_questions_limit,
            "reset_time": cls._get_next_daily_reset_time()
        }
    
    @classmethod
    def increment_pal_usage(cls, user: UserModel) -> None:
        """Increment Pal AI usage counter"""
        if not cls.is_premium(user):
            cls._reset_daily_pal_usage_if_needed(user)
            user.subscription.usage.daily_pal_questions_used += 1
    
    @classmethod
    def can_post_community(cls, user: UserModel) -> bool:
        """Check if user can post in community"""
        return cls.is_premium(user)
    
    @classmethod
    def can_access_insights(cls, user: UserModel) -> bool:
        """Check if user can access daily insights"""
        return cls.is_premium(user)
    
    @classmethod
    def get_recommendation_limit(cls, user: UserModel) -> int:
        """Get number of product recommendations to show"""
        tier = "premium" if cls.is_premium(user) else "free"
        return cls.FEATURES[tier]["recommendations_count"]
    
    @classmethod
    def get_progress_history_limit(cls, user: UserModel) -> int:
        """Get number of days of progress history to show"""
        tier = "premium" if cls.is_premium(user) else "free"
        limit = cls.FEATURES[tier]["progress_history_days"]
        return limit if limit != -1 else 365  # Convert unlimited to 365 days
    
    @classmethod
    def can_export_data(cls, user: UserModel) -> bool:
        """Check if user can export data"""
        return cls.is_premium(user)
    
    @classmethod
    def upgrade_to_premium(cls, user: UserModel, duration_days: int = 30) -> UserModel:
        """Upgrade user to premium subscription"""
        user.subscription.tier = "premium"
        user.subscription.expires_at = datetime.utcnow() + timedelta(days=duration_days)
        user.subscription.upgraded_at = datetime.utcnow()
        user.subscription.is_active = True
        
        # Reset usage counters
        user.subscription.usage.monthly_scans_used = 0
        user.subscription.usage.daily_pal_questions_used = 0
        
        logger.info(f"User {user.id} upgraded to premium for {duration_days} days")
        return user
    
    @classmethod
    def downgrade_to_free(cls, user: UserModel) -> UserModel:
        """Downgrade user to free tier"""
        user.subscription.tier = "free"
        user.subscription.cancelled_at = datetime.utcnow()
        user.subscription.usage.monthly_scans_limit = 3
        user.subscription.usage.daily_pal_questions_limit = 5
        
        logger.info(f"User {user.id} downgraded to free tier")
        return user
    
    @classmethod
    def get_subscription_status(cls, user: UserModel) -> Dict[str, Any]:
        """Get detailed subscription status"""
        is_premium = cls.is_premium(user)
        scan_status = cls.check_scan_limit(user)
        pal_status = cls.check_pal_limit(user)
        
        return {
            "tier": user.subscription.tier,
            "is_premium": is_premium,
            "expires_at": user.subscription.expires_at,
            "features": cls.FEATURES["premium" if is_premium else "free"],
            "usage": {
                "scans": {
                    "used": user.subscription.usage.monthly_scans_used,
                    "remaining": scan_status["remaining"],
                    "limit": scan_status["limit"],
                    "reset_date": scan_status.get("reset_date")
                },
                "pal_questions": {
                    "used": user.subscription.usage.daily_pal_questions_used,
                    "remaining": pal_status["remaining"],
                    "limit": pal_status["limit"],
                    "reset_time": pal_status.get("reset_time")
                }
            }
        }
    
    @classmethod
    def _reset_monthly_usage_if_needed(cls, user: UserModel) -> None:
        """Reset monthly usage counters if a month has passed"""
        usage = user.subscription.usage
        now = datetime.utcnow()
        
        # Check if a month has passed
        if usage.last_reset_date:
            next_reset = cls._get_next_reset_date(usage.last_reset_date)
            if now >= next_reset:
                usage.monthly_scans_used = 0
                usage.last_reset_date = now
                logger.info(f"Reset monthly scan usage for user {user.id}")
    
    @classmethod
    def _reset_daily_pal_usage_if_needed(cls, user: UserModel) -> None:
        """Reset daily Pal AI usage counter if a day has passed"""
        usage = user.subscription.usage
        now = datetime.utcnow()
        
        # Check if a day has passed
        if usage.last_pal_reset_date:
            if now.date() > usage.last_pal_reset_date.date():
                usage.daily_pal_questions_used = 0
                usage.last_pal_reset_date = now
                logger.info(f"Reset daily Pal questions for user {user.id}")
    
    @classmethod
    def _get_next_reset_date(cls, last_reset: datetime) -> datetime:
        """Get the next monthly reset date"""
        # Add one month to the last reset date
        if last_reset.month == 12:
            return last_reset.replace(year=last_reset.year + 1, month=1)
        else:
            return last_reset.replace(month=last_reset.month + 1)
    
    @classmethod
    def _get_next_daily_reset_time(cls) -> datetime:
        """Get the next daily reset time (midnight UTC)"""
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)