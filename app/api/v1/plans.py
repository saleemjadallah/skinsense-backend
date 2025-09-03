from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
import logging

from app.schemas.plan import (
    PlanCreateRequest, PlanUpdateRequest, PlanProgressUpdate,
    PlanResponse, PlanDetailResponse, PlanListResponse,
    PlanProgressResponse, PlanInsightsResponse, PlanTemplateResponse,
    CompleteWeekRequest
)
from app.services.plan_service import PlanService
from ..deps import get_current_active_user as get_current_user
from app.models.user import UserModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plans", tags=["plans"])

# Initialize service
plan_service = PlanService()


@router.post("/generate", response_model=Dict[str, Any])
async def generate_ai_plan(
    request: PlanCreateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Generate a personalized AI plan based on user's skin analysis and existing data
    """
    try:
        logger.info(f"Generating AI plan for user {current_user.id}")
        
        result = plan_service.generate_ai_plan(
            user_id=str(current_user.id),
            plan_type=request.plan_type,
            custom_preferences=request.custom_preferences
        )
        
        return result
        
    except ValueError as e:
        logger.error(f"Validation error generating plan: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating AI plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate plan")


@router.get("/", response_model=List[PlanResponse])
async def get_user_plans(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get all plans for the current user
    """
    try:
        plans = plan_service.get_user_plans(
            user_id=str(current_user.id),
            status=status
        )
        
        # Convert to response format
        response_plans = []
        for plan in plans:
            response_plans.append(PlanResponse(
                id=plan["id"],
                name=plan["name"],
                description=plan["description"],
                plan_type=plan["plan_type"],
                status=plan["status"],
                current_week=plan["current_week"],
                duration_weeks=plan["duration_weeks"],
                completion_rate=plan["completion_rate"],
                routine_count=plan["routine_count"],
                goal_count=plan["goal_count"],
                target_concerns=plan.get("target_concerns", []),
                created_at=plan["created_at"],
                started_at=plan.get("started_at")
            ))
        
        return response_plans
        
    except Exception as e:
        logger.error(f"Error fetching user plans: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch plans")


@router.get("/active", response_model=Optional[PlanDetailResponse])
async def get_active_plan(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get the user's current active plan with full details
    """
    try:
        plans = plan_service.get_user_plans(
            user_id=str(current_user.id),
            status="active"
        )
        
        if not plans:
            logger.info(f"No active plans found for user {current_user.id}")
            return None
        
        # Get details of the first active plan
        plan_id = plans[0].get("id")
        if not plan_id:
            logger.warning(f"Active plan found but has no ID for user {current_user.id}")
            return None
            
        plan_details = plan_service.get_plan_details(plan_id)
        
        return PlanDetailResponse(**plan_details)
        
    except ValueError as e:
        logger.info(f"Plan not found or invalid: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error fetching active plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch active plan")


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan_details(
    plan_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get detailed information about a specific plan
    """
    try:
        plan_details = plan_service.get_plan_details(plan_id)
        
        # Verify ownership
        if str(plan_details.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to view this plan")
        
        return PlanDetailResponse(**plan_details)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching plan details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch plan details")


@router.put("/{plan_id}", response_model=Dict[str, Any])
async def update_plan(
    plan_id: str,
    request: PlanUpdateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Update a plan (e.g., pause, resume, cancel)
    """
    try:
        # Verify ownership first
        plan = plan_service.get_plan_details(plan_id)
        if str(plan.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to update this plan")
        
        # Update plan status
        update_data = request.dict(exclude_unset=True)
        if update_data:
            from app.database import get_database
            db = get_database()
            from bson import ObjectId
            from datetime import datetime
            
            update_data["updated_at"] = datetime.utcnow()
            db.plans.update_one(
                {"_id": ObjectId(plan_id)},
                {"$set": update_data}
            )
        
        return {"success": True, "message": "Plan updated successfully"}
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update plan")


@router.post("/{plan_id}/progress", response_model=Dict[str, Any])
async def update_plan_progress(
    plan_id: str,
    request: PlanProgressUpdate,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Update weekly progress for a plan
    """
    try:
        # Verify ownership
        plan = plan_service.get_plan_details(plan_id)
        if str(plan.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to update this plan")
        
        result = plan_service.update_plan_progress(
            plan_id=plan_id,
            week_number=request.week_number,
            progress_data=request.dict()
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating plan progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update progress")


@router.post("/{plan_id}/complete-day", response_model=Dict[str, Any])
async def complete_current_day(
    plan_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Mark today as complete for the plan
    """
    try:
        logger.info(f"Completing day for plan {plan_id} by user {current_user.id}")
        
        # Verify ownership
        plan = plan_service.get_plan_details(plan_id)
        plan_user_id = str(plan.get("user_id"))
        current_user_id = str(current_user.id)
        
        logger.info(f"Plan user_id: {plan_user_id}, Current user_id: {current_user_id}")
        
        if plan_user_id != current_user_id:
            logger.warning(f"Unauthorized access: plan user {plan_user_id} != current user {current_user_id}")
            raise HTTPException(status_code=403, detail="Not authorized to update this plan")
        
        # Mark today as complete
        result = plan_service.complete_day(plan_id)
        
        return result
        
    except ValueError as e:
        logger.error(f"ValueError in complete_day: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing day: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to complete day: {str(e)}")

@router.post("/{plan_id}/complete-week", response_model=Dict[str, Any])
async def complete_current_week(
    plan_id: str,
    request: Optional[CompleteWeekRequest] = None,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Mark the current week as complete and advance to the next week
    """
    try:
        # Verify ownership
        plan = plan_service.get_plan_details(plan_id)
        if str(plan.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to update this plan")
        
        # Record satisfaction if provided
        if request and request.satisfaction_rating:
            # Could store this in plan_progress
            pass
        
        result = plan_service.complete_week(plan_id)
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error completing week: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to complete week")


@router.get("/{plan_id}/insights", response_model=PlanInsightsResponse)
async def get_plan_insights(
    plan_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get AI-generated insights about plan progress
    """
    try:
        # Verify ownership
        plan = plan_service.get_plan_details(plan_id)
        if str(plan.get("user_id")) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to view this plan")
        
        insights = plan_service.get_plan_insights(plan_id)
        
        return PlanInsightsResponse(**insights)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting plan insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get insights")


@router.get("/templates/list", response_model=List[PlanTemplateResponse])
async def get_plan_templates(
    skin_type: Optional[str] = Query(None, description="Filter by skin type"),
    concern: Optional[str] = Query(None, description="Filter by concern"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get available plan templates
    """
    try:
        from app.database import get_database
        db = get_database()
        
        # Build query
        query = {}
        if skin_type:
            query["suitable_for_skin_types"] = skin_type
        if concern:
            query["suitable_for_concerns"] = concern
        
        # Get templates
        templates = list(db.plan_templates.find(query).sort("usage_count", -1).limit(10))
        
        response = []
        for template in templates:
            response.append(PlanTemplateResponse(
                id=str(template["_id"]),
                name=template["name"],
                description=template["description"],
                plan_type=template["plan_type"],
                duration_weeks=template["duration_weeks"],
                suitable_for_concerns=template.get("suitable_for_concerns", []),
                suitable_for_skin_types=template.get("suitable_for_skin_types", []),
                difficulty_level=template.get("difficulty_level", "intermediate"),
                expected_improvements=template.get("expected_improvements", {}),
                usage_count=template.get("usage_count", 0),
                average_completion_rate=template.get("average_completion_rate", 0.0),
                user_rating=template.get("user_rating", 0.0)
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error fetching plan templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch templates")


@router.post("/templates/{template_id}/adopt", response_model=Dict[str, Any])
async def adopt_plan_template(
    template_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Create a personalized plan from a template
    """
    try:
        from app.database import get_database
        from bson import ObjectId
        db = get_database()
        
        # Get template
        template = db.plan_templates.find_one({"_id": ObjectId(template_id)})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Generate plan based on template but personalized to user
        result = plan_service.generate_ai_plan(
            user_id=str(current_user.id),
            plan_type=template["plan_type"],
            custom_preferences={
                "template_id": template_id,
                "duration_weeks": template["duration_weeks"]
            }
        )
        
        # Update template usage count
        db.plan_templates.update_one(
            {"_id": ObjectId(template_id)},
            {"$inc": {"usage_count": 1}}
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error adopting template: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to adopt template")