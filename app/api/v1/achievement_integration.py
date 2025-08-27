"""
Achievement tracking integration for existing endpoints.
This module provides helper functions to track achievements from other API endpoints.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

from ...models.achievement import AchievementAction
from ...services.achievement_service import AchievementService

logger = logging.getLogger(__name__)

# Initialize service
achievement_service = AchievementService()


def track_skin_analysis_completion(user_id: str, analysis_id: str, skin_score: Optional[float] = None):
    """Track achievement progress when a skin analysis is completed"""
    try:
        # Track analysis completion
        action = AchievementAction(
            action_type="skin_analysis_completed",
            data={
                "analysis_id": analysis_id,
                "skin_score": skin_score,
                "timestamp": datetime.now().isoformat()
            }
        )
        achievement_service.track_user_action(user_id, action)
        
        # If there's a skin score improvement, track that too
        if skin_score:
            # Get previous analyses to check for improvement
            from ...database import get_database
            db = get_database()
            
            # Get last analysis before this one
            previous_analyses = list(db.skin_analyses.find(
                {
                    "user_id": user_id,
                    "_id": {"$ne": analysis_id}
                }
            ).sort("created_at", -1).limit(1))
            
            if previous_analyses:
                prev_score = previous_analyses[0].get("orbo_response", {}).get("overall_skin_health_score", 0)
                if skin_score > prev_score:
                    improvement = skin_score - prev_score
                    action = AchievementAction(
                        action_type="skin_score_improved",
                        data={
                            "improvement": improvement,
                            "new_score": skin_score,
                            "old_score": prev_score
                        }
                    )
                    achievement_service.track_user_action(user_id, action)
                    
                    # Check for consecutive improvement (Steady Improver)
                    check_consecutive_improvement(user_id)
        
        logger.info(f"Tracked skin analysis achievements for user {user_id}")
    except Exception as e:
        logger.error(f"Error tracking skin analysis achievements: {str(e)}")


def track_goal_creation(user_id: str, goal_id: str, goal_type: str):
    """Track achievement progress when a goal is created"""
    try:
        action = AchievementAction(
            action_type="goal_created",
            data={
                "goal_id": goal_id,
                "goal_type": goal_type,
                "timestamp": datetime.now().isoformat()
            }
        )
        achievement_service.track_user_action(user_id, action)
        logger.info(f"Tracked goal creation achievement for user {user_id}")
    except Exception as e:
        logger.error(f"Error tracking goal achievement: {str(e)}")


def track_routine_creation(user_id: str, routine_id: str, routine_type: str):
    """Track achievement progress when a routine is created"""
    try:
        from ...database import get_database
        db = get_database()
        
        # Check if user has both AM and PM routines
        routines = list(db.routines.find({"user_id": user_id}))
        has_morning = any(r.get("type") == "morning" for r in routines)
        has_evening = any(r.get("type") == "evening" for r in routines)
        
        action = AchievementAction(
            action_type="routine_created",
            data={
                "routine_id": routine_id,
                "routine_type": routine_type,
                "has_morning": has_morning,
                "has_evening": has_evening,
                "timestamp": datetime.now().isoformat()
            }
        )
        achievement_service.track_user_action(user_id, action)
        logger.info(f"Tracked routine creation achievement for user {user_id}")
    except Exception as e:
        logger.error(f"Error tracking routine achievement: {str(e)}")


def track_daily_checkin(user_id: str):
    """Track daily check-in and calculate streak"""
    try:
        from ...database import get_database
        db = get_database()
        
        # Get user's check-in history
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check if already checked in today
        existing_checkin = db.daily_checkins.find_one({
            "user_id": user_id,
            "date": {"$gte": today}
        })
        
        if not existing_checkin:
            # Record check-in
            db.daily_checkins.insert_one({
                "user_id": user_id,
                "date": now,
                "created_at": now
            })
            
            # Calculate streak
            streak = calculate_user_streak(user_id)
            
            action = AchievementAction(
                action_type="daily_checkin",
                data={
                    "streak_days": streak,
                    "timestamp": now.isoformat()
                }
            )
            achievement_service.track_user_action(user_id, action)
            logger.info(f"Tracked daily check-in for user {user_id}: streak={streak}")
            
            return streak
        else:
            logger.info(f"User {user_id} already checked in today")
            return calculate_user_streak(user_id)
    except Exception as e:
        logger.error(f"Error tracking daily check-in: {str(e)}")
        return 0


def calculate_user_streak(user_id: str) -> int:
    """Calculate the current streak for a user"""
    from ...database import get_database
    from datetime import timedelta
    
    db = get_database()
    
    # Get all check-ins sorted by date descending
    checkins = list(db.daily_checkins.find(
        {"user_id": user_id}
    ).sort("date", -1))
    
    if not checkins:
        return 0
    
    streak = 1
    last_date = checkins[0]["date"].replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(1, len(checkins)):
        checkin_date = checkins[i]["date"].replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check if this check-in is exactly one day before the last
        if last_date - checkin_date == timedelta(days=1):
            streak += 1
            last_date = checkin_date
        else:
            # Streak broken
            break
    
    return streak


def check_consecutive_improvement(user_id: str):
    """Check if user has consecutive weeks of improvement (for Steady Improver achievement)"""
    try:
        from ...database import get_database
        from datetime import timedelta
        
        db = get_database()
        
        # Get analyses from last 4 weeks
        four_weeks_ago = datetime.now() - timedelta(weeks=4)
        analyses = list(db.skin_analyses.find({
            "user_id": user_id,
            "created_at": {"$gte": four_weeks_ago}
        }).sort("created_at", 1))
        
        if len(analyses) < 4:
            return
        
        # Group by week and check for improvement
        weeks_improved = 0
        last_week_score = None
        
        for analysis in analyses:
            score = analysis.get("orbo_response", {}).get("overall_skin_health_score", 0)
            week = analysis["created_at"].isocalendar()[1]  # Get week number
            
            if last_week_score is not None and score > last_week_score:
                weeks_improved += 1
            
            last_week_score = score
        
        if weeks_improved >= 4:
            action = AchievementAction(
                action_type="consecutive_improvement",
                data={
                    "weeks": weeks_improved,
                    "timestamp": datetime.now().isoformat()
                }
            )
            achievement_service.track_user_action(user_id, action)
            logger.info(f"User {user_id} achieved {weeks_improved} weeks of consecutive improvement")
    except Exception as e:
        logger.error(f"Error checking consecutive improvement: {str(e)}")


def track_ingredient_viewed(user_id: str, ingredient_name: str):
    """Track when a user views/learns about an ingredient"""
    try:
        action = AchievementAction(
            action_type="ingredient_viewed",
            data={
                "ingredient_name": ingredient_name,
                "timestamp": datetime.now().isoformat()
            }
        )
        achievement_service.track_user_action(user_id, action)
    except Exception as e:
        logger.error(f"Error tracking ingredient view: {str(e)}")


def track_tip_shared(user_id: str, tip_id: str):
    """Track when a user shares a tip with the community"""
    try:
        action = AchievementAction(
            action_type="tip_shared",
            data={
                "tip_id": tip_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        achievement_service.track_user_action(user_id, action)
    except Exception as e:
        logger.error(f"Error tracking tip shared: {str(e)}")


def track_member_helped(user_id: str, helped_user_id: str, post_id: str):
    """Track when a user helps another community member"""
    try:
        action = AchievementAction(
            action_type="member_helped",
            data={
                "helped_user_id": helped_user_id,
                "post_id": post_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        achievement_service.track_user_action(user_id, action)
    except Exception as e:
        logger.error(f"Error tracking member helped: {str(e)}")


def check_hydration_maintenance(user_id: str):
    """Check if user has maintained optimal hydration for 2 weeks"""
    try:
        from ...database import get_database
        from datetime import timedelta
        
        db = get_database()
        
        # Get analyses from last 2 weeks
        two_weeks_ago = datetime.now() - timedelta(weeks=2)
        analyses = list(db.skin_analyses.find({
            "user_id": user_id,
            "created_at": {"$gte": two_weeks_ago}
        }).sort("created_at", 1))
        
        if len(analyses) < 4:  # Need at least 4 analyses in 2 weeks
            return
        
        # Check if hydration has been optimal (>70) for all analyses
        all_optimal = all(
            analysis.get("orbo_response", {}).get("hydration", 0) >= 70
            for analysis in analyses
        )
        
        if all_optimal:
            action = AchievementAction(
                action_type="hydration_maintained",
                data={
                    "days": 14,
                    "analyses_count": len(analyses),
                    "timestamp": datetime.now().isoformat()
                }
            )
            achievement_service.track_user_action(user_id, action)
            logger.info(f"User {user_id} maintained optimal hydration for 2 weeks")
    except Exception as e:
        logger.error(f"Error checking hydration maintenance: {str(e)}")