from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pymongo.database import Database
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from bson import ObjectId
from app.utils.date_utils import get_utc_now

from app.database import get_database
from app.api.deps import get_current_active_user
from app.models.user import UserModel
from app.models.routine import RoutineModel, RoutineTemplate
from app.schemas.routine import (
    RoutineCreate, RoutineUpdate, RoutineResponse, RoutineListResponse,
    RoutineGenerateRequest, RoutineCompleteRequest, RoutineCompletionResponse,
    RoutineAnalysisInsight, RoutineTemplateResponse, RoutineDuplicateRequest
)
from app.services.routine_service import routine_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _convert_to_routine_response(routine) -> RoutineResponse:
    """Convert a routine model or dict to RoutineResponse with all fields"""
    # Handle both dict and model objects
    if hasattr(routine, 'dict'):
        routine_dict = routine.dict(by_alias=True)
        routine_id = str(routine.id) if routine.id else None
        user_id = str(routine.user_id)
        # Normalize steps to always include a product object for Flutter
        steps = []
        for step in routine.steps:
            step_dict = step.dict() if hasattr(step, 'dict') else dict(step)
            product = step_dict.get("product")
            if product is None:
                step_dict["product"] = {"name": step_dict.get("category", "Product")}
            if not step_dict.get("instructions"):
                step_dict["instructions"] = ""
            if not step_dict.get("frequency"):
                step_dict["frequency"] = "daily"
            steps.append(step_dict)
        effectiveness_scores = routine.effectiveness_scores.dict() if routine.effectiveness_scores else None
        based_on_analysis_id = str(routine.based_on_analysis_id) if getattr(routine, 'based_on_analysis_id', None) else None
        notes = getattr(routine, 'notes', None)
        tags = getattr(routine, 'tags', [])
    else:
        routine_dict = routine
        routine_id = str(routine.get("_id", routine.get("id")))
        user_id = str(routine["user_id"])
        # Normalize steps from raw dict
        raw_steps = routine.get("steps", [])
        steps = []
        for s in raw_steps:
            step_dict = dict(s)
            if step_dict.get("product") is None:
                step_dict["product"] = {"name": step_dict.get("category", "Product")}
            if not step_dict.get("instructions"):
                step_dict["instructions"] = ""
            if not step_dict.get("frequency"):
                step_dict["frequency"] = "daily"
            steps.append(step_dict)
        effectiveness_scores = routine.get("effectiveness_scores")
        based_on_analysis_id = str(routine["based_on_analysis_id"]) if routine.get("based_on_analysis_id") else None
        notes = routine.get("notes")
        tags = routine.get("tags", [])
    
    return RoutineResponse(
        id=routine_id,
        user_id=user_id,
        name=routine_dict.get("name", routine.get("name") if isinstance(routine, dict) else routine.name),
        type=routine_dict.get("type", routine.get("type") if isinstance(routine, dict) else routine.type),
        created_from=routine_dict.get("created_from", routine.get("created_from") if isinstance(routine, dict) else routine.created_from),
        target_concerns=routine_dict.get("target_concerns", routine.get("target_concerns", []) if isinstance(routine, dict) else routine.target_concerns),
        steps=steps,
        total_duration_minutes=routine_dict.get("total_duration_minutes", routine.get("total_duration_minutes", 0) if isinstance(routine, dict) else routine.total_duration_minutes),
        last_completed=routine_dict.get("last_completed", routine.get("last_completed") if isinstance(routine, dict) else routine.last_completed),
        completion_count=routine_dict.get("completion_count", routine.get("completion_count", 0) if isinstance(routine, dict) else routine.completion_count),
        completion_streak=routine_dict.get("completion_streak", routine.get("completion_streak", 0) if isinstance(routine, dict) else routine.completion_streak),
        effectiveness_scores=effectiveness_scores,
        based_on_analysis_id=based_on_analysis_id,
        is_active=routine_dict.get("is_active", routine.get("is_active", True) if isinstance(routine, dict) else routine.is_active),
        is_favorite=routine_dict.get("is_favorite", routine.get("is_favorite", False) if isinstance(routine, dict) else routine.is_favorite),
        created_at=routine_dict.get("created_at", routine.get("created_at", get_utc_now()) if isinstance(routine, dict) else routine.created_at),
        updated_at=routine_dict.get("updated_at", routine.get("updated_at", get_utc_now()) if isinstance(routine, dict) else routine.updated_at),
        notes=notes,
        tags=tags,
        ai_confidence_score=routine_dict.get("ai_confidence_score", routine.get("ai_confidence_score") if isinstance(routine, dict) else getattr(routine, 'ai_confidence_score', None)),
        estimated_monthly_cost=routine_dict.get("estimated_monthly_cost", routine.get("estimated_monthly_cost") if isinstance(routine, dict) else getattr(routine, 'estimated_monthly_cost', None))
    )


def _seed_default_templates(db: Database):
    """Helper function to seed default templates"""
    templates = [
        {
            "_id": ObjectId(),
            "name": "Morning Glow Routine",
            "description": "A refreshing morning routine for radiant skin",
            "type": "morning",
            "target_concerns": ["hydration", "radiance", "protection"],
            "suitable_for_skin_types": ["normal", "dry", "combination"],
            "difficulty_level": "beginner",
            "estimated_cost": "moderate",
            "popularity_score": 4.5,
            "created_at": get_utc_now(),
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product_name": "Gentle Morning Cleanser",
                    "duration_seconds": 60,
                    "instructions": "Massage gently with lukewarm water"
                },
                {
                    "order": 2,
                    "category": "toner",
                    "product_name": "Hydrating Toner",
                    "duration_seconds": 30,
                    "instructions": "Pat into skin"
                },
                {
                    "order": 3,
                    "category": "serum",
                    "product_name": "Vitamin C Serum",
                    "duration_seconds": 30,
                    "instructions": "Apply 2-3 drops"
                },
                {
                    "order": 4,
                    "category": "moisturizer",
                    "product_name": "Daily Moisturizer",
                    "duration_seconds": 45,
                    "instructions": "Apply evenly"
                },
                {
                    "order": 5,
                    "category": "sunscreen",
                    "product_name": "SPF 30 Sunscreen",
                    "duration_seconds": 30,
                    "instructions": "Apply generously"
                }
            ]
        },
        {
            "_id": ObjectId(),
            "name": "Evening Repair Routine",
            "description": "Nourishing nighttime routine",
            "type": "evening",
            "target_concerns": ["anti-aging", "hydration"],
            "suitable_for_skin_types": ["all"],
            "difficulty_level": "intermediate",
            "estimated_cost": "premium",
            "popularity_score": 4.7,
            "created_at": get_utc_now(),
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product_name": "Oil Cleanser",
                    "duration_seconds": 90,
                    "instructions": "Massage to remove makeup"
                },
                {
                    "order": 2,
                    "category": "cleanser",
                    "product_name": "Foam Cleanser",
                    "duration_seconds": 60,
                    "instructions": "Double cleanse"
                },
                {
                    "order": 3,
                    "category": "treatment",
                    "product_name": "Retinol Treatment",
                    "duration_seconds": 30,
                    "instructions": "Apply thin layer"
                },
                {
                    "order": 4,
                    "category": "moisturizer",
                    "product_name": "Night Cream",
                    "duration_seconds": 45,
                    "instructions": "Apply generously"
                }
            ]
        },
        {
            "_id": ObjectId(),
            "name": "Acne Fighter Routine",
            "description": "For acne-prone skin",
            "type": "morning",
            "target_concerns": ["acne", "oil_control"],
            "suitable_for_skin_types": ["oily", "acne_prone"],
            "difficulty_level": "beginner",
            "estimated_cost": "budget",
            "popularity_score": 4.3,
            "created_at": get_utc_now(),
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product_name": "Salicylic Acid Cleanser",
                    "duration_seconds": 60,
                    "instructions": "Focus on T-zone"
                },
                {
                    "order": 2,
                    "category": "treatment",
                    "product_name": "Niacinamide Serum",
                    "duration_seconds": 30,
                    "instructions": "Apply to entire face"
                },
                {
                    "order": 3,
                    "category": "moisturizer",
                    "product_name": "Oil-Free Gel",
                    "duration_seconds": 30,
                    "instructions": "Light layer"
                },
                {
                    "order": 4,
                    "category": "sunscreen",
                    "product_name": "Mattifying SPF",
                    "duration_seconds": 30,
                    "instructions": "Non-comedogenic"
                }
            ]
        },
        {
            "_id": ObjectId(),
            "name": "Sensitive Skin Soother",
            "description": "Gentle routine for sensitive skin",
            "type": "evening",
            "target_concerns": ["redness", "sensitivity"],
            "suitable_for_skin_types": ["sensitive", "dry"],
            "difficulty_level": "beginner",
            "estimated_cost": "moderate",
            "popularity_score": 4.6,
            "created_at": get_utc_now(),
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product_name": "Cream Cleanser",
                    "duration_seconds": 60,
                    "instructions": "Gentle motions"
                },
                {
                    "order": 2,
                    "category": "serum",
                    "product_name": "Centella Serum",
                    "duration_seconds": 30,
                    "instructions": "Pat gently"
                },
                {
                    "order": 3,
                    "category": "moisturizer",
                    "product_name": "Ceramide Cream",
                    "duration_seconds": 45,
                    "instructions": "Apply thick layer"
                }
            ]
        },
        {
            "_id": ObjectId(),
            "name": "Anti-Aging Power",
            "description": "Advanced anti-aging routine",
            "type": "evening",
            "target_concerns": ["fine_lines", "firmness"],
            "suitable_for_skin_types": ["mature", "normal"],
            "difficulty_level": "advanced",
            "estimated_cost": "premium",
            "popularity_score": 4.8,
            "created_at": get_utc_now(),
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product_name": "Enzyme Cleanser",
                    "duration_seconds": 90,
                    "instructions": "Gentle exfoliation"
                },
                {
                    "order": 2,
                    "category": "serum",
                    "product_name": "Growth Factor Serum",
                    "duration_seconds": 45,
                    "instructions": "Focus on lines"
                },
                {
                    "order": 3,
                    "category": "treatment",
                    "product_name": "Retinol 0.5%",
                    "duration_seconds": 30,
                    "instructions": "Start gradually"
                },
                {
                    "order": 4,
                    "category": "moisturizer",
                    "product_name": "Collagen Night Cream",
                    "duration_seconds": 45,
                    "instructions": "Upward motions"
                }
            ]
        }
    ]
    
    try:
        result = db.routine_templates.insert_many(templates)
        logger.info(f"Successfully seeded {len(result.inserted_ids)} templates")
    except Exception as e:
        logger.error(f"Error seeding templates: {e}")


@router.post("/generate", response_model=RoutineResponse)
async def generate_routine(
    request: RoutineGenerateRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Generate AI-powered routine based on skin analysis"""
    try:
        # Generate routine using the service
        routines = routine_service.generate_ai_routine(
            user_id=str(current_user.id),
            request=request
        )
        
        if not routines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to generate routine"
            )
        
        # Use helper to convert to response
        return _convert_to_routine_response(routines[0])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating routine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate routine: {str(e)}"
        )


@router.post("/", response_model=RoutineResponse)
async def create_routine(
    routine_data: RoutineCreate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Create a custom routine"""
    try:
        # Initialize service if needed
        if routine_service.db is None:
            routine_service.initialize()
            
        # Create routine
        routine = routine_service.create_routine(
            user_id=str(current_user.id),
            routine_data=routine_data.dict()
        )
        
        return _convert_to_routine_response(routine)
        
    except Exception as e:
        logger.error(f"Error creating routine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create routine"
        )


@router.get("/", response_model=RoutineListResponse)
async def get_routines(
    skip: int = 0,
    limit: int = 20,
    type: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get user's routines"""
    try:
        logger.info(f"Getting routines for user {current_user.id}, type={type}, is_active={is_active}")
        
        # Initialize service if needed
        if routine_service.db is None:
            routine_service.initialize()
            
        # Get routines
        routines = routine_service.get_user_routines(
            user_id=str(current_user.id),
            routine_type=type,
            is_active=is_active
        )
        
        logger.info(f"Found {len(routines)} routines for user {current_user.id}")
        
        # Convert to responses
        routine_responses = []
        for routine in routines[skip:skip+limit]:
            # Ensure we have an ID (use _id from dict if model.id is None)
            routine_id = str(routine.id) if routine.id else str(routine.dict(by_alias=True).get('_id'))
            # Normalize steps so mobile always receives a product object
            normalized_steps = []
            for step in routine.steps:
                s = step.dict()
                if s.get("product") is None:
                    s["product"] = {"name": s.get("category", "Product")}
                if not s.get("instructions"):
                    s["instructions"] = ""
                if not s.get("frequency"):
                    s["frequency"] = "daily"
                normalized_steps.append(s)
            routine_responses.append(RoutineResponse(
                id=routine_id,
                user_id=str(routine.user_id),
                name=routine.name,
                type=routine.type,
                created_from=routine.created_from,
                target_concerns=routine.target_concerns,
                steps=normalized_steps,
                total_duration_minutes=routine.calculate_total_duration(),
                last_completed=routine.last_completed,
                completion_count=routine.completion_count,
                completion_streak=routine.completion_streak,
                effectiveness_scores=routine.effectiveness_scores.dict() if routine.effectiveness_scores else None,
                is_active=routine.is_active,
                is_favorite=routine.is_favorite,
                created_at=routine.created_at,
                updated_at=routine.updated_at,
                notes=routine.notes,
                tags=routine.tags
            ))
        
        # Count active and favorite routines
        active_count = sum(1 for r in routines if r.is_active)
        favorite_count = sum(1 for r in routines if r.is_favorite)
        
        return RoutineListResponse(
            routines=routine_responses,
            total=len(routines),
            active_count=active_count,
            favorite_count=favorite_count
        )
        
    except Exception as e:
        logger.error(f"Error getting routines: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get routines"
        )


@router.get("/today", response_model=List[RoutineResponse])
async def get_todays_routines(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get today's scheduled routines"""
    try:
        # Get active routines
        routines = routine_service.get_user_routines(
            user_id=str(current_user.id),
            is_active=True
        )
        
        # Filter for today's routines with minimal scheduling
        now = get_utc_now()
        current_hour = now.hour
        current_day = now.isoweekday()  # 1..7 Mon..Sun
        todays_routines = []
        
        for routine in routines:
            # Respect schedule_days if present
            if getattr(routine, 'schedule_days', None):
                if current_day not in routine.schedule_days:
                    continue
            # Use explicit schedule_time if set; otherwise fall back to type
            time_slot = getattr(routine, 'schedule_time', None) or routine.type
            if time_slot == "morning" and current_hour < 12:
                todays_routines.append(routine)
            elif time_slot == "afternoon" and 12 <= current_hour < 17:
                todays_routines.append(routine)
            elif time_slot == "evening" and current_hour >= 17:
                todays_routines.append(routine)
            elif routine.type == "treatment":
                todays_routines.append(routine)
        
        # Convert to responses
        routine_responses = []
        for routine in todays_routines:
            normalized_steps = []
            for step in routine.steps:
                s = step.dict()
                if s.get("product") is None:
                    s["product"] = {"name": s.get("category", "Product")}
                if not s.get("instructions"):
                    s["instructions"] = ""
                if not s.get("frequency"):
                    s["frequency"] = "daily"
                normalized_steps.append(s)
            routine_responses.append(RoutineResponse(
                id=str(routine.id),
                user_id=str(routine.user_id),
                name=routine.name,
                type=routine.type,
                created_from=routine.created_from,
                target_concerns=routine.target_concerns,
                steps=normalized_steps,
                total_duration_minutes=routine.calculate_total_duration(),
                last_completed=routine.last_completed,
                completion_count=routine.completion_count,
                completion_streak=routine.completion_streak,
                effectiveness_scores=routine.effectiveness_scores.dict() if routine.effectiveness_scores else None,
                is_active=routine.is_active,
                is_favorite=routine.is_favorite,
                created_at=routine.created_at,
                updated_at=routine.updated_at,
                notes=routine.notes,
                tags=routine.tags
            ))
        
        return routine_responses
        
    except Exception as e:
        logger.error(f"Error getting today's routines: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get today's routines"
        )


@router.get("/summary", response_model=dict)
async def get_routine_summary(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get routine summary for homepage widget"""
    try:
        # Get today's routines
        now = get_utc_now()
        current_hour = now.hour
        
        # Get active routines for the user
        routines = list(db.routines.find({
            "user_id": ObjectId(str(current_user.id)),
            "is_active": True
        }))
        
        # Filter for today's routines based on type and time
        todays_routines = []
        for routine in routines:
            if routine["type"] == "morning" and current_hour < 12:
                todays_routines.append(routine)
            elif routine["type"] == "evening" and current_hour >= 17:
                todays_routines.append(routine)
            elif routine["type"] == "treatment":
                todays_routines.append(routine)
        
        # Count completed steps for today
        today_start = get_utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        completed_today = 0
        total_steps = 0
        
        for routine in todays_routines:
            total_steps += len(routine.get("steps", []))
            
            # Check if this routine was completed today
            completion = db.routine_completions.find_one({
                "routine_id": routine["_id"],
                "user_id": ObjectId(str(current_user.id)),
                "completed_at": {"$gte": today_start}
            })
            
            if completion:
                completed_today += len(completion.get("steps_completed", []))
        
        return {
            "completed_steps": completed_today,
            "total_steps": total_steps,
            "routines_count": len(todays_routines),
            "current_routine_type": "morning" if current_hour < 12 else "evening" if current_hour >= 17 else "treatment"
        }
        
    except Exception as e:
        logger.error(f"Error getting routine summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get routine summary"
        )


@router.get("/{routine_id}", response_model=RoutineResponse)
async def get_routine(
    routine_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get a specific routine"""
    try:
        # Get routine
        routine_doc = db.routines.find_one({
            "_id": ObjectId(routine_id),
            "user_id": ObjectId(str(current_user.id))
        })
        
        if not routine_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine not found"
            )
        
        routine = RoutineModel(**routine_doc)
        
        return _convert_to_routine_response(routine)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting routine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get routine"
        )


@router.put("/{routine_id}", response_model=RoutineResponse)
async def update_routine(
    routine_id: str,
    routine_update: RoutineUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Update a routine"""
    try:
        # Check routine exists
        existing = db.routines.find_one({
            "_id": ObjectId(routine_id),
            "user_id": ObjectId(str(current_user.id))
        })
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine not found"
            )
        
        # Update routine
        update_data = routine_update.dict(exclude_unset=True)
        update_data["updated_at"] = get_utc_now()
        
        db.routines.update_one(
            {"_id": ObjectId(routine_id)},
            {"$set": update_data}
        )
        
        # Get updated routine
        routine_doc = db.routines.find_one({"_id": ObjectId(routine_id)})
        routine = RoutineModel(**routine_doc)
        
        return _convert_to_routine_response(routine)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating routine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update routine"
        )


@router.delete("/{routine_id}")
async def delete_routine(
    routine_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Delete a routine"""
    try:
        # Check routine exists
        existing = db.routines.find_one({
            "_id": ObjectId(routine_id),
            "user_id": ObjectId(str(current_user.id))
        })
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine not found"
            )
        
        # Delete routine
        db.routines.delete_one({"_id": ObjectId(routine_id)})
        
        # Delete related completions
        db.routine_completions.delete_many({"routine_id": ObjectId(routine_id)})
        
        return {"message": "Routine deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting routine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete routine"
        )


@router.post("/{routine_id}/complete")
async def complete_routine(
    routine_id: str,
    completion_data: RoutineCompleteRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Mark a routine as completed"""
    try:
        # Check routine exists
        routine = db.routines.find_one({
            "_id": ObjectId(routine_id),
            "user_id": ObjectId(str(current_user.id))
        })
        
        if not routine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine not found"
            )
        
        # Complete routine
        completion = routine_service.complete_routine(
            user_id=str(current_user.id),
            routine_id=routine_id,
            completion_data=completion_data.dict()
        )
        
        # Get updated routine for streak and completion count
        updated_routine = db.routines.find_one({"_id": ObjectId(routine_id)})
        
        # Return the full completion data that Flutter expects
        return {
            "id": str(completion.id),
            "user_id": str(completion.user_id),
            "routine_id": str(completion.routine_id),
            "completed_at": completion.completed_at.isoformat(),
            "duration_minutes": completion.duration_minutes,
            "steps_completed": completion.steps_completed,
            "skipped_steps": completion.skipped_steps,
            "mood": completion.mood,
            "skin_feel": completion.skin_feel,
            "notes": completion.notes,
            "new_streak": updated_routine.get("completion_streak", 1),
            "total_completions": updated_routine.get("completion_count", 1)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing routine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete routine"
        )


@router.get("/{routine_id}/insights", response_model=RoutineAnalysisInsight)
async def get_routine_insights(
    routine_id: str,
    days: int = 30,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get insights about routine effectiveness"""
    try:
        # Check routine exists
        routine = db.routines.find_one({
            "_id": ObjectId(routine_id),
            "user_id": ObjectId(str(current_user.id))
        })
        
        if not routine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine not found"
            )
        
        # Get insights
        insights = routine_service.get_routine_insights(
            routine_id=ObjectId(routine_id),
            db=db,
            days=days
        )
        
        return RoutineAnalysisInsight(**insights)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting routine insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get routine insights"
        )


@router.post("/{routine_id}/duplicate", response_model=RoutineResponse)
async def duplicate_routine(
    routine_id: str,
    duplicate_data: RoutineDuplicateRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Duplicate an existing routine"""
    try:
        # Get original routine
        original = db.routines.find_one({
            "_id": ObjectId(routine_id),
            "user_id": ObjectId(str(current_user.id))
        })
        
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine not found"
            )
        
        # Create duplicate
        duplicate = original.copy()
        duplicate.pop("_id", None)
        duplicate["name"] = duplicate_data.new_name
        duplicate["created_at"] = get_utc_now()
        duplicate["updated_at"] = get_utc_now()
        duplicate["completion_count"] = 0
        duplicate["completion_streak"] = 0
        duplicate["last_completed"] = None
        
        # Insert duplicate
        result = db.routines.insert_one(duplicate)
        duplicate["_id"] = result.inserted_id
        
        routine = RoutineModel(**duplicate)
        
        return _convert_to_routine_response(routine)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating routine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to duplicate routine"
        )


@router.get("/templates/", response_model=List[RoutineTemplateResponse])
async def get_routine_templates(
    skin_type: Optional[str] = None,
    concern: Optional[str] = None,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get routine templates"""
    try:
        # Auto-seed templates if empty
        count = db.routine_templates.count_documents({})
        logger.info(f"Template count in database: {count}")
        if count == 0:
            logger.info("No templates found, auto-seeding...")
            _seed_default_templates(db)
            # Check count again after seeding
            new_count = db.routine_templates.count_documents({})
            logger.info(f"After seeding, template count: {new_count}")
        
        # Build query
        query = {}
        if skin_type:
            query["suitable_for_skin_types"] = skin_type
        if concern:
            query["target_concerns"] = concern
        
        # Get templates
        templates = list(db.routine_templates.find(query).sort("popularity_score", -1).limit(20))
        
        # Convert to responses
        template_responses = []
        for template in templates:
            # Calculate total time from steps
            steps = template.get("steps", [])
            total_seconds = sum(step.get("duration_seconds", 30) for step in steps)
            time_estimate_minutes = round(total_seconds / 60)
            
            template_response = RoutineTemplateResponse(
                id=str(template["_id"]),
                name=template["name"],
                description=template.get("description", ""),
                type=template["type"],
                target_concerns=template.get("target_concerns", []),
                suitable_for_skin_types=template.get("suitable_for_skin_types", []),  # Use DB field name
                steps=template.get("steps", []),
                difficulty_level=template.get("difficulty_level", "beginner"),
                estimated_cost=template.get("estimated_cost", "moderate"),
                popularity_score=template.get("popularity_score", 0),
                time_estimate_minutes=time_estimate_minutes,
                is_featured=template.get("is_featured", False),
                usage_count=template.get("usage_count", 0),
                average_rating=template.get("average_rating"),
                tags=template.get("tags", []),
                created_by=template.get("created_by"),
                created_at=template.get("created_at")
            )
            template_responses.append(template_response)
        
        return template_responses
        
    except Exception as e:
        logger.error(f"Error getting routine templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get routine templates"
        )


@router.post("/seed-templates")
async def seed_templates(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Seed routine templates (for testing)"""
    try:
        # Force clear and reseed for testing
        db.routine_templates.delete_many({})
        logger.info("Cleared existing templates")
        
        # Use the existing seed function
        _seed_default_templates(db)
        
        # Check count after seeding
        new_count = db.routine_templates.count_documents({})
        logger.info(f"After seeding, template count: {new_count}")
        
        return {
            "message": f"Successfully seeded {new_count} routine templates!",
            "count": new_count
        }
        
    except Exception as e:
        logger.error(f"Error seeding templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed templates: {str(e)}"
        )


@router.post("/templates/{template_id}/adopt", response_model=RoutineResponse)
async def adopt_template(
    template_id: str,
    request: Optional[Dict] = None,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Adopt a routine template as user's own routine"""
    try:
        logger.info(f"User {current_user.id} adopting template {template_id}")
        logger.info(f"Request data: {request}")
        
        # Get the template
        template = db.routine_templates.find_one({"_id": ObjectId(template_id)})
        
        if not template:
            logger.error(f"Template {template_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Get custom name from request if provided
        custom_name = None
        if request and 'custom_name' in request:
            custom_name = request['custom_name']
        
        # Transform template steps to match routine model
        transformed_steps = []
        for step in template.get("steps", []):
            # Normalize product to match mobile schema
            product = None
            # Prefer nested 'product' dict if present in template
            if isinstance(step.get("product"), dict):
                prod_obj = step.get("product", {})
                product = {
                    "name": prod_obj.get("name") or step.get("product_name") or step.get("category", "Product"),
                    "brand": prod_obj.get("brand") or step.get("product_brand"),
                    "product_id": prod_obj.get("product_id") or step.get("product_id"),
                    "image_url": prod_obj.get("image_url"),
                }
            elif step.get("product_name"):
                product = {
                    "name": step.get("product_name"),
                    "brand": step.get("product_brand"),
                    "product_id": step.get("product_id")
                }
            else:
                # Always provide a minimal product object to satisfy Flutter schema
                product = {
                    "name": step.get("category", "Product")
                }

            transformed_step = {
                "order": step.get("order"),
                "category": step.get("category"),
                "product": product,
                "duration_seconds": step.get("duration_seconds", 30),
                "instructions": step.get("instructions", ""),
                "ai_reasoning": step.get("ai_reasoning"),
                "is_optional": step.get("is_optional", False),
                "frequency": step.get("frequency", "daily")
            }
            transformed_steps.append(transformed_step)
        
        # Create a new routine based on the template
        # CRITICAL: Convert PyObjectId to ObjectId for consistency
        routine_data = {
            "user_id": ObjectId(str(current_user.id)),
            "name": custom_name or template["name"],
            "type": template["type"],
            "created_from": "template",
            "based_on_template_id": ObjectId(template_id),
            "target_concerns": template.get("target_concerns", []),
            "steps": transformed_steps,
            "total_duration_minutes": sum(step.get("duration_seconds", 30) for step in template.get("steps", [])) // 60,
            "is_active": True,
            "is_favorite": False,
            "completion_count": 0,
            "completion_streak": 0,
            "created_at": get_utc_now(),
            "updated_at": get_utc_now(),
            "notes": f"Created from template: {template['name']}",
            "tags": ["from_template"] + template.get("target_concerns", [])[:3]
        }
        
        # Insert the new routine
        logger.info(f"Inserting routine for user {current_user.id}: {routine_data['name']}")
        result = db.routines.insert_one(routine_data)
        routine_data["_id"] = result.inserted_id
        logger.info(f"Routine inserted with ID: {result.inserted_id}")
        
        # Verify insertion
        inserted_routine = db.routines.find_one({"_id": result.inserted_id})
        if not inserted_routine:
            logger.error(f"Failed to retrieve inserted routine {result.inserted_id}")
        else:
            logger.info(f"Successfully verified routine in database: {inserted_routine['name']}")
        
        # Create the response
        routine = RoutineModel(**routine_data)
        
        return _convert_to_routine_response(routine)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adopting template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adopt template: {str(e)}"
        )