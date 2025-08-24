"""
API endpoints for personalized insights
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime, date
from bson import ObjectId

from ...models.insights import DailyInsights, InsightContent, UserInsightPreferences
from ...models.user import UserModel
from ...services.insights_service import get_insights_service
from ...api.deps import get_current_user
from ...database import db
from pydantic import BaseModel

router = APIRouter(tags=["insights"])

class InsightsResponse(BaseModel):
    """Response model for daily insights"""
    id: str
    insights: List[InsightContent]
    generated_for_date: datetime  # Changed from date to datetime
    viewed: bool
    expires_at: datetime

class InsightInteractionRequest(BaseModel):
    """Request model for tracking insight interactions"""
    interaction_type: str  # "clicked", "dismissed", "shared"
    insight_index: int

class InsightPreferencesUpdate(BaseModel):
    """Request model for updating insight preferences"""
    preferred_categories: Optional[List[str]] = None
    blocked_categories: Optional[List[str]] = None
    insight_frequency: Optional[str] = None  # "daily", "weekly", "on_demand"
    opt_out: Optional[bool] = None

@router.get("/daily", response_model=InsightsResponse)
async def get_daily_insights(current_user: UserModel = Depends(get_current_user)):
    """
    Get daily personalized insights for the current user.
    Generates new insights if none exist for today.
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[INSIGHTS_API] Daily insights requested for user: {current_user.id}")
        
        # Generate or retrieve insights
        insights_service = get_insights_service()
        insights = insights_service.generate_daily_insights(str(current_user.id))
        
        if not insights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not generate insights"
            )
        
        # Mark as viewed
        insights_service.mark_insights_viewed(
            str(current_user.id), 
            str(insights.id)
        )
        
        return InsightsResponse(
            id=str(insights.id),
            insights=insights.insights,
            generated_for_date=insights.generated_for_date,
            viewed=True,  # We just marked it as viewed
            expires_at=insights.expires_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving insights: {str(e)}"
        )

@router.post("/generate")
async def generate_new_insights(
    force: bool = False,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Force generation of new insights for the user.
    Admin only endpoint or when force=True with user confirmation.
    """
    try:
        # If forcing, delete existing insights for today
        if force:
            today = date.today()
            start_of_day = datetime.combine(today, datetime.min.time())
            end_of_day = datetime.combine(today, datetime.max.time())
            db.daily_insights.delete_many({
                "user_id": ObjectId(str(current_user.id)),
                "generated_for_date": {"$gte": start_of_day, "$lte": end_of_day}
            })
        
        # Generate new insights
        insights_service = get_insights_service()
        insights = insights_service.generate_daily_insights(str(current_user.id))
        
        if not insights:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate insights"
            )
        
        return {
            "message": "Insights generated successfully",
            "insights_count": len(insights.insights),
            "id": str(insights.id)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating insights: {str(e)}"
        )

@router.post("/{insights_id}/interact")
async def track_insight_interaction(
    insights_id: str,
    interaction: InsightInteractionRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Track user interaction with an insight (click, dismiss, share, etc.)
    """
    try:
        # Verify the insights belong to the user
        insights = db.daily_insights.find_one({
            "_id": ObjectId(insights_id),
            "user_id": ObjectId(str(current_user.id))
        })
        
        if not insights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insights not found"
            )
        
        # Track the interaction
        insights_service = get_insights_service()
        insights_service.track_insight_interaction(
            str(current_user.id),
            insights_id,
            interaction.interaction_type,
            interaction.insight_index
        )
        
        return {"message": "Interaction tracked successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error tracking interaction: {str(e)}"
        )

@router.get("/history")
async def get_insights_history(
    limit: int = 7,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get historical insights for the user (last N days)
    """
    try:
        # Retrieve historical insights
        insights_cursor = db.daily_insights.find(
            {"user_id": ObjectId(str(current_user.id))},
            sort=[("created_at", -1)],
            limit=limit
        )
        
        insights_list = []
        for insight_doc in insights_cursor:
            insights_list.append({
                "id": str(insight_doc["_id"]),
                "date": insight_doc["generated_for_date"],
                "insights": insight_doc["insights"],
                "viewed": insight_doc.get("viewed", False),
                "interactions": len(insight_doc.get("interactions", []))
            })
        
        return {
            "total": len(insights_list),
            "insights": insights_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving insights history: {str(e)}"
        )

@router.get("/preferences")
async def get_insight_preferences(current_user: UserModel = Depends(get_current_user)):
    """
    Get user's insight preferences
    """
    try:
        user = db.users.find_one({"_id": ObjectId(str(current_user.id))})
        
        preferences = user.get("insights_preferences", {
            "preferred_categories": [],
            "blocked_categories": [],
            "insight_frequency": "daily",
            "opt_out": False
        })
        
        return preferences
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving preferences: {str(e)}"
        )

@router.put("/preferences")
async def update_insight_preferences(
    preferences: InsightPreferencesUpdate,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Update user's insight preferences
    """
    try:
        update_data = {}
        
        if preferences.preferred_categories is not None:
            update_data["insights_preferences.preferred_categories"] = preferences.preferred_categories
        if preferences.blocked_categories is not None:
            update_data["insights_preferences.blocked_categories"] = preferences.blocked_categories
        if preferences.insight_frequency is not None:
            update_data["insights_preferences.insight_frequency"] = preferences.insight_frequency
        if preferences.opt_out is not None:
            update_data["insights_preferences.opt_out"] = preferences.opt_out
        
        if update_data:
            db.users.update_one(
                {"_id": ObjectId(str(current_user.id))},
                {"$set": update_data}
            )
        
        return {"message": "Preferences updated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating preferences: {str(e)}"
        )

@router.get("/categories")
async def get_available_categories():
    """
    Get list of available insight categories
    """
    return {
        "categories": [
            {"key": "skin_trend", "name": "Skin Trends", "description": "Trends in your skin metrics"},
            {"key": "product_tip", "name": "Product Tips", "description": "How to use products effectively"},
            {"key": "environmental", "name": "Environmental", "description": "Weather and seasonal advice"},
            {"key": "habit_formation", "name": "Habit Building", "description": "Building good skincare habits"},
            {"key": "ingredient_focus", "name": "Ingredient Education", "description": "Learn about skincare ingredients"},
            {"key": "prevention", "name": "Prevention", "description": "Preventive care tips"},
            {"key": "celebration", "name": "Celebrations", "description": "Achievements and milestones"},
            {"key": "recommendation", "name": "Recommendations", "description": "Personalized suggestions"}
        ]
    }