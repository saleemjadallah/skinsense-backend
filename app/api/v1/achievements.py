from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import logging

from ...models.achievement import (
    AchievementProgress, AchievementSync, AchievementAction,
    AchievementCategory, AchievementDifficulty, ACHIEVEMENT_DEFINITIONS
)
from ...services.achievement_service import AchievementService
from ..deps import get_current_user
from ...models.user import UserModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/achievements", tags=["achievements"])

# Initialize service
achievement_service = AchievementService()


@router.get("/", response_model=Dict[str, Any])
async def get_user_achievements(
    current_user: UserModel = Depends(get_current_user),
    category: Optional[AchievementCategory] = None,
    unlocked_only: bool = False,
    sync: bool = True  # Auto-sync by default
):
    """Get all achievements for the current user with their progress"""
    try:
        # Auto-sync achievements from existing data if requested
        if sync:
            try:
                sync_result = achievement_service.sync_achievements_from_existing_data(str(current_user.id))
                logger.info(f"Auto-synced {sync_result['synced_achievements']} achievements for user {current_user.id}")
                
                # CRITICAL FIX: Force re-sync if First Glow is not unlocked but user has analyses
                first_glow = achievement_service.achievements_collection.find_one({
                    "user_id": {"$in": [str(current_user.id), current_user.id]},
                    "achievement_id": "first_glow"
                })
                
                if not first_glow or not first_glow.get("is_unlocked", False):
                    # Force check if user has any analyses
                    from ...database import get_database
                    db = get_database()
                    
                    # Check both ObjectId and string formats
                    from bson import ObjectId
                    try:
                        user_oid = ObjectId(str(current_user.id))
                        analysis_count_oid = db.skin_analyses.count_documents({"user_id": user_oid})
                        analysis_count_str = db.skin_analyses.count_documents({"user_id": str(current_user.id)})
                        
                        total_analyses = max(analysis_count_oid, analysis_count_str)
                        
                        if total_analyses > 0:
                            logger.warning(f"User {current_user.id} has {total_analyses} analyses but First Glow not unlocked - forcing unlock")
                            achievement_service.update_achievement_progress(
                                str(current_user.id), 
                                "first_glow", 
                                1.0,
                                {"retroactive_fix": True, "analysis_count": total_analyses}
                            )
                    except Exception as e:
                        logger.error(f"Error in retroactive First Glow fix: {e}")
                        
            except Exception as e:
                logger.error(f"Error in auto-sync: {e}")
        
        achievements = achievement_service.get_user_achievements(str(current_user.id))
        
        # Log First Glow status for debugging
        first_glow = next((a for a in achievements if a.get("achievement_id") == "first_glow"), None)
        if first_glow:
            logger.info(f"First Glow for user {current_user.id}: unlocked={first_glow.get('is_unlocked')}, progress={first_glow.get('progress')}")
        
        # Filter by category if requested
        if category:
            achievements = [a for a in achievements if a.get("category") == category]
        
        # Filter by unlock status if requested
        if unlocked_only:
            achievements = [a for a in achievements if a.get("is_unlocked", False)]
        
        unlocked_count = len([a for a in achievements if a.get("is_unlocked", False)])
        logger.info(f"Returning {len(achievements)} achievements ({unlocked_count} unlocked) for user {current_user.id}")
        
        return {
            "achievements": achievements,
            "total": len(achievements),
            "unlocked": unlocked_count
        }
    except Exception as e:
        logger.error(f"Error getting achievements for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/definitions", response_model=List[Dict[str, Any]])
async def get_achievement_definitions(
    category: Optional[AchievementCategory] = None,
    difficulty: Optional[AchievementDifficulty] = None
):
    """Get all achievement definitions (static data)"""
    definitions = [a.dict() for a in ACHIEVEMENT_DEFINITIONS]
    
    # Filter by category
    if category:
        definitions = [d for d in definitions if d.get("category") == category]
    
    # Filter by difficulty
    if difficulty:
        definitions = [d for d in definitions if d.get("difficulty") == difficulty]
    
    return definitions


@router.post("/sync", response_model=Dict[str, Any])
async def sync_user_achievements(
    current_user: UserModel = Depends(get_current_user)
):
    """Manually sync achievements based on existing user data"""
    try:
        sync_result = achievement_service.sync_achievements_from_existing_data(str(current_user.id))
        return sync_result
    except Exception as e:
        logger.error(f"Error syncing achievements for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=Dict[str, Any])
async def get_achievement_stats(
    current_user: UserModel = Depends(get_current_user)
):
    """Get achievement statistics for the current user"""
    try:
        stats = achievement_service.get_achievement_stats(str(current_user.id))
        return stats
    except Exception as e:
        logger.error(f"Error getting achievement stats for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{achievement_id}", response_model=Dict[str, Any])
async def get_achievement_detail(
    achievement_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get detailed information about a specific achievement"""
    try:
        achievements = achievement_service.get_user_achievements(str(current_user.id))
        achievement = next((a for a in achievements if a.get("achievement_id") == achievement_id), None)
        
        if not achievement:
            raise HTTPException(status_code=404, detail=f"Achievement {achievement_id} not found")
        
        return achievement
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting achievement {achievement_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{achievement_id}/progress", response_model=Dict[str, Any])
async def update_achievement_progress(
    achievement_id: str,
    progress_update: AchievementProgress,
    current_user: UserModel = Depends(get_current_user)
):
    """Update progress for a specific achievement (client-side update)"""
    try:
        # Validate achievement ID matches
        if achievement_id != progress_update.achievement_id:
            raise HTTPException(status_code=400, detail="Achievement ID mismatch")
        
        # Update progress
        result = achievement_service.update_achievement_progress(
            current_user.id,
            achievement_id,
            progress_update.progress,
            progress_update.progress_data
        )
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Achievement {achievement_id} not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating achievement {achievement_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{achievement_id}/unlock", response_model=Dict[str, Any])
async def unlock_achievement(
    achievement_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Mark an achievement as unlocked (client-side notification)"""
    try:
        # Set progress to 1.0 (100%)
        result = achievement_service.update_achievement_progress(
            current_user.id,
            achievement_id,
            1.0,
            {"unlocked_at": datetime.now().isoformat()}
        )
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Achievement {achievement_id} not found")
        
        return {
            "achievement": result,
            "unlocked": True,
            "unlocked_at": datetime.now()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlocking achievement {achievement_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/track", response_model=Dict[str, Any])
async def track_achievement_action(
    action: AchievementAction,
    current_user: UserModel = Depends(get_current_user)
):
    """Track a user action that might affect achievement progress"""
    try:
        updated_achievements = achievement_service.track_user_action(current_user.id, action)
        
        return {
            "action": action.action_type,
            "tracked_at": datetime.now(),
            "updated_achievements": updated_achievements,
            "updated_count": len(updated_achievements)
        }
    except Exception as e:
        logger.error(f"Error tracking action for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=Dict[str, Any])
async def sync_achievements(
    sync_data: AchievementSync,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Sync achievement progress from client.
    This endpoint is designed for periodic (weekly) verification of client-side progress.
    """
    try:
        result = achievement_service.sync_achievements(current_user.id, sync_data)
        
        # Log sync activity
        logger.info(f"Achievement sync for user {current_user.id}: "
                   f"updated={result['updated_count']}, "
                   f"verified={result['verified_count']}, "
                   f"rejected={result['rejected_count']}")
        
        return result
    except Exception as e:
        logger.error(f"Error syncing achievements for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_achievements(
    current_user: UserModel = Depends(get_current_user)
):
    """Initialize all achievements for the current user (called on first app launch)"""
    try:
        achievements = achievement_service.initialize_user_achievements(current_user.id)
        
        return {
            "initialized": True,
            "achievements": achievements,
            "total": len(achievements)
        }
    except Exception as e:
        logger.error(f"Error initializing achievements for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-all", response_model=Dict[str, Any])
async def verify_all_achievements(
    current_user: UserModel = Depends(get_current_user),
    admin_key: str = Query(None, description="Admin key for verification")
):
    """
    Manually verify all achievements for a user (admin endpoint).
    This is useful for resolving disputes or manual verification.
    """
    # Simple admin check - in production, use proper admin authentication
    if admin_key != "admin_secret_key_2024":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    try:
        result = achievement_service.verify_all_user_achievements(current_user.id)
        return result
    except Exception as e:
        logger.error(f"Error verifying achievements for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper endpoints for specific achievement types

@router.post("/track/analysis-completed", response_model=Dict[str, Any])
async def track_analysis_completed(
    current_user: UserModel = Depends(get_current_user)
):
    """Track that a skin analysis was completed"""
    action = AchievementAction(
        action_type="skin_analysis_completed",
        data={"timestamp": datetime.now().isoformat()}
    )
    return await track_achievement_action(action, current_user)


@router.post("/track/daily-checkin", response_model=Dict[str, Any])
async def track_daily_checkin(
    streak_days: int,
    current_user: UserModel = Depends(get_current_user)
):
    """Track a daily check-in with streak information"""
    action = AchievementAction(
        action_type="daily_checkin",
        data={"streak_days": streak_days}
    )
    return await track_achievement_action(action, current_user)


@router.post("/track/goal-created", response_model=Dict[str, Any])
async def track_goal_created(
    goal_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Track that a goal was created"""
    action = AchievementAction(
        action_type="goal_created",
        data={"goal_id": goal_id}
    )
    return await track_achievement_action(action, current_user)


@router.post("/track/routine-created", response_model=Dict[str, Any])
async def track_routine_created(
    has_morning: bool,
    has_evening: bool,
    current_user: UserModel = Depends(get_current_user)
):
    """Track that a routine was created"""
    action = AchievementAction(
        action_type="routine_created",
        data={"has_morning": has_morning, "has_evening": has_evening}
    )
    return await track_achievement_action(action, current_user)


@router.post("/fix-retroactive", response_model=Dict[str, Any])
async def fix_retroactive_achievements(
    current_user: UserModel = Depends(get_current_user),
    force: bool = False
):
    """
    CRITICAL BUG FIX: Retroactively fix achievements for users who have analyses
    but achievements weren't properly tracked due to ObjectId/string user_id bugs.
    """
    try:
        from ...database import get_database
        from bson import ObjectId
        
        db = get_database()
        user_id = str(current_user.id)
        
        logger.info(f"Starting retroactive achievement fix for user {user_id}")
        
        fixes_applied = []
        
        # Check both ObjectId and string formats for skin_analyses
        try:
            user_oid = ObjectId(user_id)
            analysis_count_oid = db.skin_analyses.count_documents({"user_id": user_oid})
            analysis_count_str = db.skin_analyses.count_documents({"user_id": user_id})
            
            total_analyses = max(analysis_count_oid, analysis_count_str)
            format_used = "ObjectId" if analysis_count_oid > analysis_count_str else "string"
            
            logger.info(f"User {user_id} has {total_analyses} total analyses (format: {format_used})")
            
            # Fix First Glow if user has analyses but achievement not unlocked
            first_glow = achievement_service.achievements_collection.find_one({
                "user_id": {"$in": [user_id, user_oid]},
                "achievement_id": "first_glow"
            })
            
            if total_analyses > 0 and (not first_glow or not first_glow.get("is_unlocked", False)):
                achievement_service.update_achievement_progress(
                    user_id, 
                    "first_glow", 
                    1.0,
                    {"retroactive_fix": True, "analysis_count": total_analyses, "format_used": format_used}
                )
                fixes_applied.append("first_glow")
                logger.info(f"Fixed First Glow achievement for user {user_id}")
            
            # Fix Progress Pioneer if user has 10+ analyses
            if total_analyses >= 10:
                progress_pioneer = achievement_service.achievements_collection.find_one({
                    "user_id": {"$in": [user_id, user_oid]},
                    "achievement_id": "progress_pioneer"
                })
                
                if not progress_pioneer or not progress_pioneer.get("is_unlocked", False):
                    achievement_service.update_achievement_progress(
                        user_id,
                        "progress_pioneer",
                        1.0,
                        {"retroactive_fix": True, "analysis_count": total_analyses}
                    )
                    fixes_applied.append("progress_pioneer")
                    logger.info(f"Fixed Progress Pioneer achievement for user {user_id}")
            
            # Check goals for Baseline Boss
            goal_count_oid = db.goals.count_documents({"user_id": user_oid})
            goal_count_str = db.goals.count_documents({"user_id": user_id})
            total_goals = max(goal_count_oid, goal_count_str)
            
            if total_goals > 0:
                baseline_boss = achievement_service.achievements_collection.find_one({
                    "user_id": {"$in": [user_id, user_oid]},
                    "achievement_id": "baseline_boss"
                })
                
                if not baseline_boss or not baseline_boss.get("is_unlocked", False):
                    achievement_service.update_achievement_progress(
                        user_id,
                        "baseline_boss",
                        1.0,
                        {"retroactive_fix": True, "goal_count": total_goals}
                    )
                    fixes_applied.append("baseline_boss")
                    logger.info(f"Fixed Baseline Boss achievement for user {user_id}")
            
            return {
                "success": True,
                "user_id": user_id,
                "fixes_applied": fixes_applied,
                "total_analyses": total_analyses,
                "total_goals": total_goals,
                "data_format_used": format_used,
                "message": f"Applied {len(fixes_applied)} retroactive fixes"
            }
            
        except Exception as e:
            logger.error(f"Error in retroactive fix: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }
            
    except Exception as e:
        logger.error(f"Fatal error in retroactive achievement fix: {e}")
        raise HTTPException(status_code=500, detail=str(e))