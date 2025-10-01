from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pymongo.database import Database
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.database import get_database
from app.api.deps import get_current_active_user
from app.models.user import UserModel
from app.models.routine import PersonalizedRoutine
from app.schemas.routine import (
    RoutineGenerateRequest,
    RoutineResponse,
    RoutineDetailResponse,
    RoutineUpdateRequest,
    RoutineRatingRequest,
    RoutineListResponse,
)
from app.services.routine_generator_service import routine_generator_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=RoutineDetailResponse)
def generate_personalized_routine(
    request: RoutineGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
):
    """Generate a new personalized routine using AI"""

    try:
        # Get latest skin analysis
        latest_analysis = db.skin_analyses.find_one(
            {"user_id": current_user.id}, sort=[("created_at", -1)]
        )

        if not latest_analysis:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No skin analysis found. Please complete a skin scan first.",
            )

        # Get user's products (optional)
        user_products = []
        if request.include_user_products:
            user_products = list(
                db.user_products.find({"user_id": current_user.id}).limit(20)
            )

        # Get weather data (if provided)
        weather_data = request.weather_data

        # Convert user model to dict for processing
        user_dict = {
            "_id": current_user.id,
            "profile": {
                "age_range": current_user.profile.age_range or current_user.onboarding.age_group or "25-34",
                "skin_type": current_user.profile.skin_type or current_user.onboarding.skin_type or "normal",
                "skin_concerns": current_user.profile.skin_concerns or [],
                "goals": current_user.profile.goals or [],
                "current_routine": current_user.profile.current_routine or [],
            },
        }

        # Generate routine (synchronous call)
        routine = routine_generator_service.generate_personalized_routine(
            user=user_dict,
            latest_analysis=latest_analysis,
            routine_type=request.routine_type,
            weather_data=weather_data,
            user_products=user_products,
            force_regenerate=request.force_regenerate,
        )

        # Save to database - use dedicated collection for AI routines
        routine_dict = routine.dict(by_alias=True)
        result = db.personalized_routines.insert_one(routine_dict)

        # Track usage analytics in background
        background_tasks.add_task(
            track_routine_generation,
            user_id=str(current_user.id),
            routine_type=request.routine_type,
            db=db,
        )

        return RoutineDetailResponse(
            id=str(result.inserted_id),
            routine_type=routine.routine_type,
            routine_name=routine.routine_name,
            description=routine.description,
            total_duration_minutes=routine.total_duration_minutes,
            difficulty_level=routine.difficulty_level,
            skin_concerns_addressed=routine.skin_concerns_addressed,
            weather_adapted=routine.weather_adapted,
            times_used=routine.times_used,
            user_rating=routine.user_rating,
            is_favorite=routine.is_favorite,
            created_at=routine.created_at,
            steps=[
                {
                    "step_number": step.step_number,
                    "product_category": step.product_category,
                    "product_name": step.product_name,
                    "instructions": step.instructions,
                    "duration_minutes": step.duration_minutes,
                    "key_benefits": step.key_benefits,
                    "technique_tips": step.technique_tips,
                }
                for step in routine.steps
            ],
            ai_reasoning=routine.ai_reasoning,
            confidence_score=routine.confidence_score,
            alternative_suggestions=routine.alternative_suggestions,
            current_weather_context=routine.current_weather_context,
            generated_from=routine.generated_from,
            last_used=routine.last_used,
        )

    except Exception as e:
        logger.error(f"Routine generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Routine generation failed: {str(e)}",
        )


@router.get("/my-routines", response_model=RoutineListResponse)
def get_user_routines(
    routine_type: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
):
    """Get user's saved routines"""

    # Convert user_id to string to match database format
    query = {"user_id": str(current_user.id), "is_active": True}

    if routine_type:
        query["routine_type"] = routine_type

    if is_favorite is not None:
        query["is_favorite"] = is_favorite

    routines_cursor = (
        db.personalized_routines.find(query).sort("created_at", -1).skip(skip).limit(limit)
    )
    routines = list(routines_cursor)
    total = db.personalized_routines.count_documents(query)

    routine_responses = []
    for routine in routines:
        routine_responses.append(
            RoutineResponse(
                id=str(routine["_id"]),
                routine_type=routine["routine_type"],
                routine_name=routine["routine_name"],
                description=routine["description"],
                total_duration_minutes=routine["total_duration_minutes"],
                difficulty_level=routine["difficulty_level"],
                skin_concerns_addressed=routine.get("skin_concerns_addressed", []),
                weather_adapted=routine.get("weather_adapted", False),
                times_used=routine.get("times_used", 0),
                user_rating=routine.get("user_rating"),
                is_favorite=routine.get("is_favorite", False),
                created_at=routine["created_at"],
            )
        )

    return RoutineListResponse(routines=routine_responses, total=total)


@router.get("/{routine_id}", response_model=RoutineDetailResponse)
def get_routine_detail(
    routine_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
):
    """Get detailed routine information"""

    try:
        routine = db.personalized_routines.find_one(
            {"_id": ObjectId(routine_id), "user_id": str(current_user.id)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid routine ID"
        )

    if not routine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found"
        )

    return RoutineDetailResponse(
        id=str(routine["_id"]),
        routine_type=routine["routine_type"],
        routine_name=routine["routine_name"],
        description=routine["description"],
        total_duration_minutes=routine["total_duration_minutes"],
        difficulty_level=routine["difficulty_level"],
        skin_concerns_addressed=routine.get("skin_concerns_addressed", []),
        weather_adapted=routine.get("weather_adapted", False),
        times_used=routine.get("times_used", 0),
        user_rating=routine.get("user_rating"),
        is_favorite=routine.get("is_favorite", False),
        created_at=routine["created_at"],
        steps=[
            {
                "step_number": step["step_number"],
                "product_category": step["product_category"],
                "product_name": step.get("product_name"),
                "instructions": step["instructions"],
                "duration_minutes": step["duration_minutes"],
                "key_benefits": step.get("key_benefits", []),
                "technique_tips": step.get("technique_tips"),
            }
            for step in routine.get("steps", [])
        ],
        ai_reasoning=routine.get("ai_reasoning", ""),
        confidence_score=routine.get("confidence_score", 0.0),
        alternative_suggestions=routine.get("alternative_suggestions", []),
        current_weather_context=routine.get("current_weather_context"),
        generated_from=routine.get("generated_from", {}),
        last_used=routine.get("last_used"),
    )


@router.post("/{routine_id}/use")
def mark_routine_used(
    routine_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
):
    """Track routine usage"""

    try:
        result = db.personalized_routines.update_one(
            {"_id": ObjectId(routine_id), "user_id": str(current_user.id)},
            {"$inc": {"times_used": 1}, "$set": {"last_used": datetime.utcnow()}},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid routine ID"
        )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found"
        )

    return {"message": "Routine usage tracked"}


@router.put("/{routine_id}/favorite")
def toggle_favorite(
    routine_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
):
    """Toggle routine favorite status"""

    try:
        routine = db.personalized_routines.find_one(
            {"_id": ObjectId(routine_id), "user_id": str(current_user.id)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid routine ID"
        )

    if not routine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found"
        )

    new_favorite_status = not routine.get("is_favorite", False)

    db.personalized_routines.update_one(
        {"_id": ObjectId(routine_id)}, {"$set": {"is_favorite": new_favorite_status}}
    )

    return {"is_favorite": new_favorite_status}


@router.put("/{routine_id}/rating")
def rate_routine(
    routine_id: str,
    request: RoutineRatingRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
):
    """Rate and provide feedback on routine"""

    try:
        result = db.personalized_routines.update_one(
            {"_id": ObjectId(routine_id), "user_id": str(current_user.id)},
            {
                "$set": {
                    "user_rating": request.rating,
                    "user_feedback": request.feedback,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid routine ID"
        )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found"
        )

    return {"message": "Rating saved successfully"}


@router.delete("/{routine_id}")
def delete_routine(
    routine_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
):
    """Soft delete routine"""

    try:
        result = db.personalized_routines.update_one(
            {"_id": ObjectId(routine_id), "user_id": str(current_user.id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid routine ID"
        )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found"
        )

    return {"message": "Routine deleted successfully"}


def track_routine_generation(user_id: str, routine_type: str, db: Database):
    """Background task to track analytics"""
    try:
        # Track analytics (can be expanded later)
        db.routine_analytics.insert_one(
            {
                "user_id": ObjectId(user_id),
                "routine_type": routine_type,
                "generated_at": datetime.utcnow(),
            }
        )
    except Exception as e:
        logger.error(f"Failed to track routine analytics: {str(e)}")