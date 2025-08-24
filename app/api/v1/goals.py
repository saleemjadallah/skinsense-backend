from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import logging

from ..deps import get_current_active_user
from ...models.user import UserModel
from ...schemas.goal import (
    GoalCreate, GoalUpdate, GoalProgressUpdate, GoalGenerateRequest,
    GoalResponse, GoalListResponse, GoalProgressResponse,
    GoalInsight, AchievementResponse, AchievementListResponse,
    GoalTemplateResponse
)
from ...services.goal_service import GoalService

router = APIRouter(tags=["goals"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=List[GoalResponse])
async def generate_goals(
    request: GoalGenerateRequest,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Generate AI-powered goals based on skin analysis.
    
    This endpoint analyzes the user's skin data and creates personalized goals
    targeting parameters with scores below 80.
    """
    try:
        goal_service = GoalService()
        goals = goal_service.generate_goals(
            str(current_user.id),
            request
        )
        return goals
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating goals: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate goals"
        )


@router.post("/", response_model=GoalResponse)
async def create_goal(
    goal_data: GoalCreate,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Create a new goal manually.
    
    Users can create custom goals beyond AI recommendations.
    """
    try:
        goal_service = GoalService()
        goal = goal_service.create_goal(
            str(current_user.id),
            goal_data
        )
        return goal
    except Exception as e:
        logger.error(f"Error creating goal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create goal"
        )


@router.get("/", response_model=GoalListResponse)
async def get_goals(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: active, completed, abandoned"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get all goals for the current user.
    
    Returns goals with optional status filtering and pagination.
    """
    try:
        logger.info(f"Getting goals for user {current_user.id} with status={status_filter}, limit={limit}, skip={skip}")
        goal_service = GoalService()
        goals_response = goal_service.get_user_goals(
            str(current_user.id),
            status=status_filter,
            limit=limit,
            skip=skip
        )
        # goals_response is a GoalListResponse object, not a dict
        logger.info(f"Found {len(goals_response.goals)} goals for user {current_user.id}")
        return goals_response
    except Exception as e:
        logger.error(f"Error getting goals for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve goals"
        )


@router.get("/templates", response_model=List[GoalTemplateResponse])
async def get_goal_templates(
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get recommended goal templates.
    
    Returns pre-defined goal templates suitable for the user's profile.
    """
    try:
        goal_service = GoalService()
        templates = goal_service.get_goal_templates(
            str(current_user.id)
        )
        return templates
    except Exception as e:
        logger.error(f"Error getting goal templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve goal templates"
        )


@router.get("/achievements", response_model=List[AchievementResponse])
async def get_achievements(
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get all achievements for the current user.
    
    Returns both locked and unlocked achievements with progress.
    """
    try:
        goal_service = GoalService()
        achievements = goal_service.get_user_achievements(
            str(current_user.id)
        )
        return achievements
    except Exception as e:
        logger.error(f"Error getting achievements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve achievements"
        )


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: str,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get a specific goal by ID.
    """
    try:
        goal_service = GoalService()
        goal = goal_service.get_goal(
            str(current_user.id),
            goal_id
        )
        return goal
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting goal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve goal"
        )


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str,
    update_data: GoalUpdate,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Update a goal.
    
    Allows updating goal details, status, or abandoning a goal.
    """
    try:
        goal_service = GoalService()
        goal = goal_service.update_goal(
            str(current_user.id),
            goal_id,
            update_data
        )
        return goal
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating goal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update goal"
        )


@router.post("/{goal_id}/progress", response_model=GoalResponse)
async def update_goal_progress(
    goal_id: str,
    progress_data: GoalProgressUpdate,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Update progress for a goal.
    
    Records new progress data and updates goal completion percentage.
    """
    try:
        goal_service = GoalService()
        goal = goal_service.update_goal_progress(
            str(current_user.id),
            goal_id,
            progress_data
        )
        return goal
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating goal progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update goal progress"
        )


@router.get("/{goal_id}/progress", response_model=GoalProgressResponse)
async def get_goal_progress(
    goal_id: str,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get detailed progress history for a goal.
    
    Returns progress tracking data, streaks, and projections.
    """
    try:
        goal_service = GoalService()
        progress = goal_service.get_goal_progress(
            str(current_user.id),
            goal_id
        )
        return progress
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting goal progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve goal progress"
        )


@router.get("/{goal_id}/insights", response_model=GoalInsight)
async def get_goal_insights(
    goal_id: str,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get AI-powered insights for a goal.
    
    Returns success probability, helping/hindering factors, and recommendations.
    """
    try:
        goal_service = GoalService()
        insights = goal_service.get_goal_insights(
            str(current_user.id),
            goal_id
        )
        return insights
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting goal insights: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve goal insights"
        )


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: str,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Delete a goal.
    
    Note: Consider marking as 'abandoned' instead of deleting for data integrity.
    """
    try:
        # For now, we'll mark it as abandoned instead of deleting
        goal_service = GoalService()
        update_data = GoalUpdate(
            status="abandoned",
            abandon_reason="User deleted goal"
        )
        goal_service.update_goal(
            str(current_user.id),
            goal_id,
            update_data
        )
        return {"message": "Goal successfully removed"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting goal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete goal"
        )


# Quick stats endpoint for dashboard
@router.get("/stats/summary")
async def get_goal_stats(
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get quick goal statistics for dashboard display.
    """
    try:
        goal_service = GoalService()
        goals = goal_service.get_user_goals(
            str(current_user.id),
            limit=100
        )
        
        # Calculate stats
        active_goals = [g for g in goals.goals if g.status == "active"]
        
        # Find next milestone
        next_milestone = None
        for goal in active_goals:
            for milestone in goal.milestones:
                if not milestone.completed:
                    next_milestone = {
                        "goal_title": goal.title,
                        "milestone_title": milestone.title,
                        "progress_needed": milestone.target_value - goal.current_value
                        if milestone.target_value else None
                    }
                    break
            if next_milestone:
                break
        
        return {
            "active_goals_count": goals.active_count,
            "completed_goals_count": goals.completed_count,
            "total_goals_count": goals.total,
            "success_rate": (
                (goals.completed_count / (goals.completed_count + goals.abandoned_count) * 100)
                if (goals.completed_count + goals.abandoned_count) > 0
                else 0
            ),
            "next_milestone": next_milestone
        }
    except Exception as e:
        logger.error(f"Error getting goal stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve goal statistics"
        )