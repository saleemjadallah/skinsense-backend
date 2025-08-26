from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pymongo.database import Database
from typing import List, Optional
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
        
        routine_dict = routines[0]
        
        # Return response
        return RoutineResponse(
            id=str(routine_dict.get("_id", routine_dict.get("id"))),
            user_id=str(routine_dict["user_id"]),
            name=routine_dict["name"],
            type=routine_dict["type"],
            created_from=routine_dict["created_from"],
            target_concerns=routine_dict.get("target_concerns", []),
            steps=routine_dict.get("steps", []),
            total_duration_minutes=sum(step.get("duration_seconds", 0) / 60 for step in routine_dict.get("steps", [])),
            last_completed=routine_dict.get("last_completed"),
            completion_count=routine_dict.get("completion_count", 0),
            completion_streak=routine_dict.get("completion_streak", 0),
            effectiveness_scores=routine_dict.get("effectiveness_scores"),
            is_active=routine_dict.get("is_active", True),
            is_favorite=routine_dict.get("is_favorite", False),
            created_at=routine_dict.get("created_at", get_utc_now()),
            updated_at=routine_dict.get("updated_at", get_utc_now()),
            notes=routine_dict.get("notes"),
            tags=routine_dict.get("tags", [])
        )
        
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
        # Create routine
        routine = routine_service.create_routine(
            user_id=str(current_user.id),
            routine_data=routine_data.dict()
        )
        
        return RoutineResponse(
            id=str(routine.id),
            user_id=str(routine.user_id),
            name=routine.name,
            type=routine.type,
            created_from=routine.created_from,
            target_concerns=routine.target_concerns,
            steps=[step.dict() for step in routine.steps],
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
        )
        
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
        # Get routines
        routines = routine_service.get_user_routines(
            user_id=str(current_user.id),
            routine_type=type,
            is_active=is_active
        )
        
        # Convert to responses
        routine_responses = []
        for routine in routines[skip:skip+limit]:
            routine_responses.append(RoutineResponse(
                id=str(routine.id),
                user_id=str(routine.user_id),
                name=routine.name,
                type=routine.type,
                created_from=routine.created_from,
                target_concerns=routine.target_concerns,
                steps=[step.dict() for step in routine.steps],
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
        
        return RoutineListResponse(
            routines=routine_responses,
            total=len(routines),
            skip=skip,
            limit=limit
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
        
        # Filter for today's routines
        current_hour = get_utc_now().hour
        todays_routines = []
        
        for routine in routines:
            # Morning routines (before 12 PM)
            if routine.type == "morning" and current_hour < 12:
                todays_routines.append(routine)
            # Evening routines (after 5 PM)
            elif routine.type == "evening" and current_hour >= 17:
                todays_routines.append(routine)
            # Treatment routines (any time)
            elif routine.type == "treatment":
                todays_routines.append(routine)
        
        # Convert to responses
        routine_responses = []
        for routine in todays_routines:
            routine_responses.append(RoutineResponse(
                id=str(routine.id),
                user_id=str(routine.user_id),
                name=routine.name,
                type=routine.type,
                created_from=routine.created_from,
                target_concerns=routine.target_concerns,
                steps=[step.dict() for step in routine.steps],
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
        current_hour = get_utc_now().hour
        
        # Get active routines for the user
        routines = list(db.routines.find({
            "user_id": ObjectId(current_user.id),
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
                "user_id": ObjectId(current_user.id),
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
            "user_id": current_user.id
        })
        
        if not routine_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routine not found"
            )
        
        routine = RoutineModel(**routine_doc)
        
        return RoutineResponse(
            id=str(routine.id),
            user_id=str(routine.user_id),
            name=routine.name,
            type=routine.type,
            created_from=routine.created_from,
            target_concerns=routine.target_concerns,
            steps=[step.dict() for step in routine.steps],
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
        )
        
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
            "user_id": current_user.id
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
        
        return RoutineResponse(
            id=str(routine.id),
            user_id=str(routine.user_id),
            name=routine.name,
            type=routine.type,
            created_from=routine.created_from,
            target_concerns=routine.target_concerns,
            steps=[step.dict() for step in routine.steps],
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
        )
        
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
            "user_id": current_user.id
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
            "user_id": current_user.id
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
            "user_id": current_user.id
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
            "user_id": current_user.id
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
        
        return RoutineResponse(
            id=str(routine.id),
            user_id=str(routine.user_id),
            name=routine.name,
            type=routine.type,
            created_from=routine.created_from,
            target_concerns=routine.target_concerns,
            steps=[step.dict() for step in routine.steps],
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
        )
        
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
            
            template_responses.append(RoutineTemplateResponse(
                id=str(template["_id"]),
                name=template["name"],
                description=template.get("description", ""),
                type=template["type"],
                target_concerns=template.get("target_concerns", []),
                skin_types=template.get("suitable_for_skin_types", []),  # Map to skin_types
                steps=template.get("steps", []),
                difficulty_level=template.get("difficulty_level", "beginner"),
                estimated_cost=template.get("estimated_cost", "moderate"),
                popularity_score=template.get("popularity_score", 0),
                time_estimate_minutes=time_estimate_minutes  # Add calculated time
            ))
        
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
