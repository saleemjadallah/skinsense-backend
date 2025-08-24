"""
Test endpoints for development and testing
WARNING: These endpoints should be disabled in production!
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from bson import ObjectId
import logging

from ..deps import get_current_active_user
from ...models.user import UserModel
from ...database import get_database

router = APIRouter(tags=["test"])
logger = logging.getLogger(__name__)


@router.post("/create-mock-analysis")
async def create_mock_skin_analysis(
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Create a mock skin analysis for testing goals generation.
    This endpoint should only be available in development!
    """
    try:
        db = get_database()
        
        # Create mock ORBO response with various scores
        mock_orbo_response = {
            "data": {
                "output_score": [
                    {"concern": "skin_health", "score": 72, "riskLevel": 2},
                    {"concern": "hydration", "score": 65, "riskLevel": 3},  # Low - should trigger goal
                    {"concern": "smoothness", "score": 78, "riskLevel": 2},  # Low - should trigger goal
                    {"concern": "radiance", "score": 70, "riskLevel": 2},  # Low - should trigger goal
                    {"concern": "dark_spots", "score": 82, "riskLevel": 1},
                    {"concern": "firmness", "score": 85, "riskLevel": 1},
                    {"concern": "fine_lines", "score": 88, "riskLevel": 1},
                    {"concern": "acne", "score": 60, "riskLevel": 3},  # Low - should trigger goal
                    {"concern": "dark_circles", "score": 75, "riskLevel": 2},  # Low - should trigger goal
                    {"concern": "redness", "score": 90, "riskLevel": 1}
                ]
            }
        }
        
        # Create the analysis document
        analysis = {
            "user_id": str(current_user.id),  # Store as string to match existing pattern
            "image_url": "https://example.com/mock-image.jpg",
            "orbo_response": mock_orbo_response,
            "ai_feedback": {
                "summary": "Mock analysis for testing",
                "recommendations": ["Test recommendation 1", "Test recommendation 2"],
                "created_by": "test_endpoint"
            },
            "created_at": datetime.utcnow(),
            "is_baseline": False,
            "metadata": {
                "image_quality": 0.95,
                "confidence_score": 0.90,
                "processing_time": 1.23,
                "test_data": True
            }
        }
        
        # Insert into database
        result = db.skin_analyses.insert_one(analysis)
        
        logger.info(f"Created mock skin analysis {result.inserted_id} for user {current_user.id}")
        
        return {
            "message": "Mock skin analysis created successfully",
            "analysis_id": str(result.inserted_id),
            "user_id": str(current_user.id),
            "scores": {
                "hydration": 65,
                "acne": 60,
                "radiance": 70,
                "smoothness": 78,
                "dark_circles": 75
            },
            "note": "Low scores (<80) in hydration, acne, radiance, smoothness, and dark_circles should trigger goal generation"
        }
        
    except Exception as e:
        logger.error(f"Error creating mock analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mock analysis: {str(e)}"
        )


@router.delete("/cleanup-test-data")
async def cleanup_test_data(
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Clean up test data for the current user.
    Removes analyses and goals marked as test data.
    """
    try:
        db = get_database()
        
        # Delete test analyses
        analyses_result = db.skin_analyses.delete_many({
            "user_id": {"$in": [str(current_user.id), ObjectId(current_user.id)]},
            "metadata.test_data": True
        })
        
        # Delete all goals for this user (optional)
        goals_result = db.goals.delete_many({
            "user_id": {"$in": [str(current_user.id), ObjectId(current_user.id)]}
        })
        
        return {
            "message": "Test data cleaned up",
            "deleted_analyses": analyses_result.deleted_count,
            "deleted_goals": goals_result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up test data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup test data: {str(e)}"
        )