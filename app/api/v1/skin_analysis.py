from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Request, Query
from pymongo.database import Database
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
import base64
from io import BytesIO
from app.utils.date_utils import get_utc_now

from app.database import get_database
from app.api.deps import get_current_active_user, require_subscription, get_current_user_optional
from app.models.user import UserModel
from app.models.skin_analysis import SkinAnalysisModel, HautAIResponse, AIFeedback, ImageMetadata, ORBOResponse, ORBOMetrics
from app.schemas.skin_analysis import (
    SkinAnalysisCreate, 
    SkinAnalysisResponse, 
    SkinAnalysisDetail,
    ProgressComparisonRequest,
    ProgressComparisonResponse
)
from app.services.orbo_service import OrboSkinAnalysisService
from app.services.openai_service import openai_service
from app.services.s3_service import s3_service
from app.services.perplexity_service import perplexity_service
from app.services.recommendation_service import recommendation_service
from app.services.progress_service import progress_service
from app.services.subscription_service import SubscriptionService
from app.services.notification_service import notification_service
from app.core.cache import cache_service
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

# Helper functions for score color coding
def get_score_color(score: float) -> str:
    """
    Get color code for a score (0-100 scale)
    Returns: 'green' for 81-100, 'yellow' for 0-80
    """
    if score >= 81:
        return "green"
    else:
        return "yellow"

def get_score_label(score: float) -> str:
    """
    Get descriptive label for a score
    Returns: 'Excellent', 'Good', 'Fair', or 'Needs Attention'
    """
    if score >= 81:
        return "Excellent"
    elif score >= 61:
        return "Good"
    elif score >= 41:
        return "Fair"
    else:
        return "Needs Attention"

def format_metric_with_color(name: str, score: float) -> Dict[str, Any]:
    """
    Format a metric with score, color, and label
    """
    return {
        "name": name,
        "score": round(score, 1),  # Round to 1 decimal place
        "color": get_score_color(score),
        "label": get_score_label(score),
        "percentage": f"{round(score)}%"
    }

@router.post("/analyze", response_model=SkinAnalysisResponse)
async def create_skin_analysis(
    analysis_data: SkinAnalysisCreate,
    background_tasks: BackgroundTasks,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Create new skin analysis"""
    
    # Check scan limits using subscription service
    scan_status = SubscriptionService.check_scan_limit(current_user)
    if not scan_status["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Monthly scan limit reached",
                "remaining_scans": 0,
                "reset_date": scan_status.get("reset_date").isoformat() if scan_status.get("reset_date") else None,
                "upgrade_prompt": "Upgrade to Premium for unlimited skin scans!"
            }
        )
    
    # Increment scan usage
    SubscriptionService.increment_scan_usage(current_user)
    # Update user in database with model_dump() for Pydantic v2
    db.users.update_one(
        {"_id": current_user.id},
        {"$set": {"subscription": current_user.subscription.model_dump()}}
    )
    
    try:
        # Decode base64 image
        if not analysis_data.image_data.startswith('data:image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format"
            )
        
        # Extract image bytes
        header, encoded = analysis_data.image_data.split(',', 1)
        image_bytes = base64.b64decode(encoded)
        
        # Upload image to S3
        image_url, thumbnail_url = await s3_service.upload_image(
            image_bytes, 
            str(current_user.id),
            "analysis"
        )
        
        # Create initial analysis record - CRITICAL: use ObjectId for user_id
        analysis = SkinAnalysisModel(
            user_id=ObjectId(str(current_user.id)),
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            is_baseline=analysis_data.is_baseline,
            tags=analysis_data.tags,
            created_at=get_utc_now()
        )
        
        # Insert into database
        result = db.skin_analyses.insert_one(analysis.dict(by_alias=True))
        analysis_id = result.inserted_id
        
        # Update achievements cache for streak tracking  
        day_start = get_utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate current streak
        yesterday_start = day_start - timedelta(days=1)
        yesterday_entry = db.achievements.find_one({
            "user_id": ObjectId(str(current_user.id)),
            "date": yesterday_start
        })
        
        current_streak = 1  # Today counts as 1
        if yesterday_entry and yesterday_entry.get("photos_taken", 0) > 0:
            # Continue counting backwards to find full streak
            streak_days = 1
            check_date = yesterday_start
            while True:
                check_date = check_date - timedelta(days=1)
                entry = db.achievements.find_one({
                    "user_id": ObjectId(str(current_user.id)),
                    "date": check_date
                })
                if entry and entry.get("photos_taken", 0) > 0:
                    streak_days += 1
                else:
                    break
            current_streak = streak_days + 1  # Add today
        
        logger.info(f"Calculated streak for user {current_user.id}: {current_streak} days (analyze endpoint)")
        
        db.achievements.update_one(
            {"user_id": ObjectId(str(current_user.id)), "date": day_start},
            {
                "$setOnInsert": {"created_at": get_utc_now()},
                "$inc": {"photos_taken": 1},
                "$addToSet": {"analysis_ids": str(analysis_id)},
                "$set": {"streak_current": current_streak, "updated_at": get_utc_now()}
            },
            upsert=True
        )
        
        # Process analysis in background
        background_tasks.add_task(
            process_skin_analysis,
            analysis_id,
            image_bytes,
            current_user.dict(),
            db
        )
        
        return SkinAnalysisResponse(
            id=str(analysis_id),
            user_id=str(current_user.id),
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            analysis_complete=False,
            created_at=analysis.created_at,
            is_baseline=analysis.is_baseline
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create analysis: {str(e)}"
        )

async def process_skin_analysis(
    analysis_id: ObjectId,
    image_bytes: bytes,
    user_data: dict,
    db: Database
):
    """Background task to process skin analysis"""
    
    try:
        # Get previous analyses for comparison
        previous_analyses = list(db.skin_analyses.find(
            {"user_id": ObjectId(user_data["id"])},
            {"analysis_data": 1, "created_at": 1}
        ).sort("created_at", -1).limit(3))
        
        # Exclude current analysis
        previous_analyses = [a for a in previous_analyses if a["_id"] != analysis_id]
        
        # Initialize ORBO service with database
        orbo_service = OrboSkinAnalysisService(db)
        
        # Analyze with ORBO (now includes user_id for error tracking)
        orbo_analysis = await orbo_service.complete_analysis_pipeline(
            image_bytes, 
            user_id=str(user_data["id"])
        )
        
        # Generate AI feedback
        ai_feedback = openai_service.generate_skin_feedback(
            orbo_analysis,
            user_data.get("profile", {}),
            previous_analyses
        )
        
        # Create metadata
        metadata = ImageMetadata(
            image_quality_score=8.5,  # You can implement actual quality scoring
            face_detected=True,
            analysis_version="v1.0"
        )
        
        # Update analysis with results
        update_data = {
            "analysis_data": orbo_analysis,
            "orbo_response": orbo_analysis,
            "ai_feedback": AIFeedback(**ai_feedback),
            "metadata": metadata.dict(),
            "updated_at": get_utc_now()
        }
        
        db.skin_analyses.update_one(
            {"_id": analysis_id},
            {"$set": update_data}
        )

        # Invalidate progress-related caches for this user
        user_id_str = str(user_data["id"])
        cache_service.invalidate_user_cache(user_id_str)
        logger.info(f"Invalidated progress cache for user {user_id_str} after new analysis")

        # Track achievement for completed analysis
        from .achievement_integration import track_skin_analysis_completion
        
        # Get the overall skin score from ORBO response
        skin_score = orbo_analysis.get("overall_skin_health_score", 0) if orbo_analysis else None
        
        # Track the achievement
        track_skin_analysis_completion(
            user_id=str(user_data["id"]),
            analysis_id=str(analysis_id),
            skin_score=skin_score
        )
        
        logger.info(f"Tracked achievement for analysis {analysis_id}, user {user_data['id']}, score: {skin_score}")
        
        # TODO: Send push notification about completed analysis
        
    except Exception as e:
        # Log error and update analysis with error status
        logger.error(f"Skin analysis failed for user {user_data['id']}: {str(e)}")
        
        # Store user-friendly error in database
        error_info = {
            "error": str(e),
            "user_message": "Analysis failed. Please try taking a new photo.",
            "timestamp": get_utc_now().isoformat()
        }
        
        db.skin_analyses.update_one(
            {"_id": analysis_id},
            {"$set": {
                "analysis_data": error_info,
                "status": "failed",
                "updated_at": get_utc_now()
            }}
        )

@router.get("/config-check")
async def check_configuration(
    current_user: UserModel = Depends(get_current_active_user),
):
    """Check API configuration status (for debugging)"""
    try:
        from app.core.config import settings
        
        perplexity_key = settings.PERPLEXITY_API_KEY
        openai_key = settings.OPENAI_API_KEY
        
        return {
            "perplexity_configured": bool(perplexity_key),
            "openai_configured": bool(openai_key),
            "orbo_configured": bool(settings.ORBO_API_KEY or settings.ORBO_AI_API_KEY),
            "aws_configured": bool(settings.AWS_ACCESS_KEY_ID),
            "perplexity_key_prefix": perplexity_key[:10] + "..." if perplexity_key else "NOT SET",
            "openai_key_prefix": openai_key[:10] + "..." if openai_key else "NOT SET"
        }
    except Exception as e:
        logger.error(f"Config check error: {e}", exc_info=True)
        return {
            "error": str(e),
            "message": "Failed to check configuration"
        }

@router.get("/quick-recommendations", response_model=Dict[str, Any])
async def get_quick_recommendations(
    city: str = Query(..., description="User's city (required)"),
    state: str = Query(..., description="User's state code (required)"),
    zip_code: str = Query(..., description="User's ZIP code (required)"),
    skin_type: Optional[str] = None,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get quick product recommendations without new analysis"""
    try:
        logger.info(f"Quick recommendations requested for user {current_user.id}")
        
        user_location = {
            "city": city,
            "state": state,
            "zip_code": zip_code
        }
        
        recommendations = await recommendation_service.get_quick_recommendations(
            user=current_user,
            user_location=user_location,
            db=db,
            skin_type_override=skin_type
        )
        
        logger.info(f"Quick recommendations generated: {len(recommendations.get('recommendations', []))} products")
        return recommendations
        
    except Exception as e:
        logger.error(f"Quick recommendations endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendations: {str(e)}"
        )

@router.get("/", response_model=List[SkinAnalysisResponse])
async def get_user_analyses(
    skip: int = 0,
    limit: int = 20,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get user's skin analyses"""
    
    # CRITICAL FIX: Check both ObjectId and string formats for user_id
    # Also filter out failed analyses to ensure we only return analyses with data
    user_oid = ObjectId(str(current_user.id))
    analyses = list(db.skin_analyses.find(
        {
            "user_id": {"$in": [user_oid, str(current_user.id)]},
            # Only return analyses that have data (exclude failed ones)
            "$or": [
                {"status": {"$in": ["completed", "awaiting_ai"]}},
                {"orbo_response": {"$exists": True, "$ne": None}}
            ]
        }
    ).sort("created_at", -1).skip(skip).limit(limit))
    
    return [
        SkinAnalysisResponse(
            id=str(analysis["_id"]),
            user_id=str(analysis["user_id"]),
            image_url=analysis["image_url"],
            thumbnail_url=analysis.get("thumbnail_url"),
            analysis_complete=bool(analysis.get("analysis_data") or analysis.get("orbo_response")),
            created_at=analysis["created_at"],
            is_baseline=analysis.get("is_baseline", False),
            orbo_response=analysis.get("orbo_response"),  # Include ORBO scores
            # Convert ai_feedback to string if it's a dict
            ai_feedback=(
                analysis.get("ai_feedback").get("summary")
                if isinstance(analysis.get("ai_feedback"), dict)
                else analysis.get("ai_feedback")
            )
        )
        for analysis in analyses
    ]

@router.get("/latest-successful", response_model=SkinAnalysisResponse)
async def get_latest_successful_analysis(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get user's latest successful skin analysis (with ORBO data)"""
    
    user_oid = ObjectId(str(current_user.id))
    
    # Find the most recent analysis with actual data
    analysis = db.skin_analyses.find_one(
        {
            "user_id": {"$in": [user_oid, str(current_user.id)]},
            # Must have ORBO response data
            "orbo_response": {"$exists": True, "$ne": None},
            # Exclude failed analyses
            "status": {"$ne": "failed"}
        },
        sort=[("created_at", -1)]
    )
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="No successful analyses found"
        )
    
    return SkinAnalysisResponse(
        id=str(analysis["_id"]),
        user_id=str(analysis["user_id"]),
        image_url=analysis["image_url"],
        thumbnail_url=analysis.get("thumbnail_url"),
        analysis_complete=bool(analysis.get("orbo_response")),
        created_at=analysis["created_at"],
        is_baseline=analysis.get("is_baseline", False),
        orbo_response=analysis.get("orbo_response"),
        ai_feedback=(
            analysis.get("ai_feedback").get("summary")
            if isinstance(analysis.get("ai_feedback"), dict)
            else analysis.get("ai_feedback")
        )
    )

@router.get("/{analysis_id}", response_model=SkinAnalysisDetail)
async def get_analysis_detail(
    analysis_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get detailed analysis results"""
    
    # CRITICAL FIX: Convert user_id to ObjectId for query
    user_oid = ObjectId(str(current_user.id))
    analysis = db.skin_analyses.find_one({
        "_id": ObjectId(analysis_id),
        "user_id": {"$in": [user_oid, str(current_user.id)]}
    })
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    return SkinAnalysisDetail(
        id=str(analysis["_id"]),
        user_id=str(analysis["user_id"]),
        image_url=analysis["image_url"],
        thumbnail_url=analysis.get("thumbnail_url"),
        analysis_data=analysis.get("analysis_data", {}),
        ai_feedback=analysis.get("ai_feedback"),
        metadata=analysis.get("metadata", {}),
        created_at=analysis["created_at"],
        is_baseline=analysis.get("is_baseline", False),
        tags=analysis.get("tags", [])
    )

@router.get("/{analysis_id}/recommendations", response_model=Dict[str, Any])
async def get_analysis_recommendations(
    analysis_id: str,
    city: str = Query(..., description="User's city (required)"),
    state: str = Query(..., description="User's state code (required)"), 
    zip_code: str = Query(..., description="User's ZIP code (required)"),
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get product recommendations based on completed skin analysis"""
    
    # Get the analysis
    # CRITICAL FIX: Convert user_id to ObjectId for query
    user_oid = ObjectId(str(current_user.id))
    analysis = db.skin_analyses.find_one({
        "_id": ObjectId(analysis_id),
        "user_id": {"$in": [user_oid, str(current_user.id)]}
    })
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    if not analysis.get("analysis_data"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analysis not yet complete"
        )
    
    # Validate location parameters
    if not city or city == "Unknown" or not state or state == "Unknown":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid location parameters (city, state, zip_code) are required for personalized recommendations"
        )
    
    # Build user location
    user_location = {
        "city": city,
        "state": state,
        "zip_code": zip_code
    }
    
    logger.info(f"Getting recommendations for location: {city}, {state} {zip_code}")
    
    # Generate recommendations
    recommendations = await perplexity_service.get_personalized_recommendations(
        user=current_user,
        skin_analysis=analysis["analysis_data"],
        user_location=user_location,
        db=db,
        limit=5
    )
    
    return recommendations

@router.get("/{analysis_id}/annotations", response_model=Dict[str, Any])
async def get_analysis_annotations(
    analysis_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get annotated images for a specific analysis showing detected skin concerns"""
    
    # Convert string ID to ObjectId
    try:
        analysis_oid = ObjectId(analysis_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analysis ID format"
        )
    
    # Fetch analysis
    analysis = db.skin_analyses.find_one(
        {"_id": analysis_oid, "user_id": str(current_user.id)}
    )
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Extract annotations from ORBO response
    orbo_response = analysis.get('orbo_response', {})
    raw_response = orbo_response.get('raw_response', {})
    
    # Check both locations for annotations
    annotations = {}
    if 'data' in raw_response and 'annotations' in raw_response['data']:
        annotations = raw_response['data']['annotations']
    elif 'annotations' in orbo_response:
        annotations = orbo_response['annotations']
    
    # Get the original image URL
    input_image = ""
    if 'data' in raw_response and 'input_image' in raw_response['data']:
        input_image = raw_response['data']['input_image']
    elif 'image_url' in analysis:
        input_image = analysis['image_url']
    
    return {
        "analysis_id": analysis_id,
        "input_image": input_image,
        "annotations": annotations,
        "available_concerns": list(annotations.keys()) if annotations else [],
        "total_annotations": len(annotations),
        "message": "Each annotation URL shows the detected areas for that specific skin concern"
    }

@router.post("/products/interaction")
async def track_product_interaction(
    interaction_data: Dict[str, Any],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Track user interaction with recommended products"""

    await perplexity_service.track_product_interaction(
        user_id=current_user.id,
        product_data=interaction_data.get("product_data"),
        interaction_type=interaction_data.get("interaction_type"),
        db=db,
        skin_analysis_id=ObjectId(interaction_data.get("analysis_id")) if interaction_data.get("analysis_id") else None
    )

    return {"message": "Interaction tracked successfully"}

@router.get("/products/saved")
async def get_saved_products(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get user's saved products"""
    try:
        user_oid = ObjectId(str(current_user.id))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user_id format: {str(e)}"
        )

    # Fetch all saved product interactions
    saved_interactions = list(db.user_product_interactions.find({
        "user_id": user_oid,
        "interaction_type": "saved"
    }).sort("created_at", -1))

    # Extract unique products (deduplicate by product name/brand)
    products = []
    seen_products = set()

    for interaction in saved_interactions:
        product_data = interaction.get("product_data", {})

        # Create a unique key based on product name and brand
        product_key = f"{product_data.get('name', '')}_{product_data.get('brand', '')}"

        if product_key not in seen_products and product_data:
            seen_products.add(product_key)
            products.append(product_data)

    return {
        "products": products,
        "total": len(products),
        "message": f"Retrieved {len(products)} saved products"
    }

@router.post("/complete-pipeline", response_model=Dict[str, Any])
async def complete_ai_pipeline(
    analysis_data: SkinAnalysisCreate,
    background_tasks: BackgroundTasks,
    city: str = Query(..., description="User's city (required)"),
    state: str = Query(..., description="User's state code (required)"),
    zip_code: str = Query(..., description="User's ZIP code (required)"),
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Create analysis and get immediate AI recommendations"""
    
    # Check rate limits for free users
    if current_user.subscription.tier == "basic":
        start_of_month = get_utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_count = db.skin_analyses.count_documents({
            "user_id": ObjectId(str(current_user.id)),
            "created_at": {"$gte": start_of_month}
        })
        
        if monthly_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Monthly analysis limit reached. Upgrade to Plus for unlimited analyses."
            )
    
    try:
        # Decode base64 image
        if not analysis_data.image_data.startswith('data:image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format"
            )
        
        # Extract image bytes
        header, encoded = analysis_data.image_data.split(',', 1)
        image_bytes = base64.b64decode(encoded)
        
        # Upload image to S3
        image_url, thumbnail_url = await s3_service.upload_image(
            image_bytes, 
            str(current_user.id),
            "analysis"
        )
        
        # Create initial analysis record - CRITICAL: use ObjectId for user_id
        analysis = SkinAnalysisModel(
            user_id=ObjectId(str(current_user.id)),
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            is_baseline=analysis_data.is_baseline,
            tags=analysis_data.tags,
            created_at=get_utc_now()
        )
        
        # Insert into database
        result = db.skin_analyses.insert_one(analysis.dict(by_alias=True))
        analysis_id = result.inserted_id
        
        # Update achievements cache for streak tracking
        day_start = get_utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate current streak
        yesterday_start = day_start - timedelta(days=1)
        yesterday_entry = db.achievements.find_one({
            "user_id": ObjectId(str(current_user.id)),
            "date": yesterday_start
        })
        
        current_streak = 1  # Today counts as 1
        if yesterday_entry and yesterday_entry.get("photos_taken", 0) > 0:
            # Continue counting backwards to find full streak
            streak_days = 1
            check_date = yesterday_start
            while True:
                check_date = check_date - timedelta(days=1)
                entry = db.achievements.find_one({
                    "user_id": ObjectId(str(current_user.id)),
                    "date": check_date
                })
                if entry and entry.get("photos_taken", 0) > 0:
                    streak_days += 1
                else:
                    break
            current_streak = streak_days + 1  # Add today
        
        logger.info(f"Calculated streak for user {current_user.id}: {current_streak} days (complete-pipeline)")
        
        db.achievements.update_one(
            {"user_id": ObjectId(str(current_user.id)), "date": day_start},
            {
                "$setOnInsert": {"created_at": get_utc_now()},
                "$inc": {"photos_taken": 1},
                "$addToSet": {"analysis_ids": str(analysis_id)},
                "$set": {"streak_current": current_streak, "updated_at": get_utc_now()}
            },
            upsert=True
        )
        
        # Build user location
        user_location = {
            "city": city,
            "state": state,
            "zip_code": zip_code
        }
        
        # Execute complete AI pipeline
        complete_results = await recommendation_service.complete_ai_pipeline(
            user=current_user,
            image_url=image_url,
            user_location=user_location,
            db=db,
            analysis_id=analysis_id
        )
        
        # Update analysis with results and mark as completed
        skin_analysis_payload = complete_results.get("skin_analysis")
        update_fields = {
            "analysis_data": skin_analysis_payload,
            "ai_feedback": complete_results.get("ai_feedback"),
            "product_recommendations": complete_results.get("product_recommendations"),
            "status": "completed",
            "analysis_completed_at": get_utc_now(),
            "processing_complete": True,
            "updated_at": get_utc_now()
        }

        if skin_analysis_payload is not None:
            update_fields["orbo_response"] = skin_analysis_payload

        db.skin_analyses.update_one(
            {"_id": analysis_id},
            {"$set": update_fields}
        )
        
        # Track achievement for completed analysis
        from .achievement_integration import track_skin_analysis_completion
        
        # Get the overall skin score from the results
        skin_score = complete_results.get("skin_analysis", {}).get("overall_skin_health_score", 0)
        
        # Track the achievement
        track_skin_analysis_completion(
            user_id=str(current_user.id),
            analysis_id=str(analysis_id),
            skin_score=skin_score
        )
        
        logger.info(f"Tracked achievement for complete-pipeline analysis {analysis_id}, user {current_user.id}, score: {skin_score}")

        # Invalidate cached progress data for this user so new metrics render immediately
        cache_service.invalidate_user_cache(str(current_user.id))
        
        return complete_results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete AI pipeline: {str(e)}"
        )

@router.post("/product-compatibility", response_model=Dict[str, Any])
async def check_product_compatibility(
    product_info: Dict[str, Any],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Check if a product is compatible with user's skin"""
    
    compatibility = await recommendation_service.analyze_product_compatibility(
        user=current_user,
        product_info=product_info,
        db=db
    )
    
    return compatibility

@router.post("/routine-plan", response_model=Dict[str, Any])
async def generate_routine_plan(
    routine_request: Dict[str, Any],
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Generate personalized skincare routine plan"""
    
    routine_plan = await recommendation_service.generate_routine_plan(
        user=current_user,
        products=routine_request.get("products", []),
        goals=routine_request.get("goals", []),
        db=db
    )
    
    return routine_plan

@router.post("/orbo-sdk-result", response_model=Dict[str, Any])
async def save_orbo_sdk_result(
    orbo_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
    run_ai: bool = False,
):
    """
    Save ORBO SDK scan results and process through complete AI pipeline
    This endpoint is called when the native ORBO SDK completes a scan
    
    Flow: ORBO Analysis → OpenAI Feedback → Perplexity Recommendations
    """
    
    logger.info(f"Starting AI pipeline for ORBO SDK result - user {current_user.id}")
    logger.debug(f"ORBO data received: {json.dumps(orbo_data, default=str)}")
    
    try:
        # Enforce subscription scan limits for ORBO SDK scans
        scan_status = SubscriptionService.check_scan_limit(current_user)
        if not scan_status.get("allowed"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Monthly scan limit reached",
                    "remaining_scans": 0,
                    "reset_date": scan_status.get("reset_date").isoformat() if scan_status.get("reset_date") else None,
                    "upgrade_prompt": "Upgrade to Premium for unlimited skin scans!",
                },
            )
        # Increment usage and persist immediately so the UI can reflect it
        SubscriptionService.increment_scan_usage(current_user)

        # Log before and after for debugging
        logger.info(f"User {current_user.id} scan count before: {current_user.subscription.usage.monthly_scans_used}")

        # Use model_dump() instead of deprecated dict() for Pydantic v2
        subscription_data = current_user.subscription.model_dump()

        result = db.users.update_one(
            {"_id": current_user.id},
            {"$set": {"subscription": subscription_data}},
        )

        logger.info(f"Update result - matched: {result.matched_count}, modified: {result.modified_count}")
        logger.info(f"Subscription data being saved: monthly_scans_used = {subscription_data['usage']['monthly_scans_used']}")

        # Fetch previous analysis metrics for comparison before inserting new data
        previous_analysis = db.skin_analyses.find_one(
            {
                "user_id": current_user.id,
                "is_test": {"$ne": True},
            },
            sort=[("created_at", -1)],
            projection={
                "orbo_response.metrics": 1,
                "metrics": 1,
                "skin_metrics": 1,
                "created_at": 1,
            },
        )

        def normalize_previous_metrics(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            if not raw or not isinstance(raw, dict):
                return {}
            legacy_key_map = {
                'overall_health': 'overall_skin_health_score',
                'overall': 'overall_skin_health_score',
                'fine_lines': 'fine_lines_wrinkles',
            }
            normalized: Dict[str, Any] = {}
            for key, value in raw.items():
                target_key = legacy_key_map.get(key, key)
                normalized[target_key] = value
            return normalized

        previous_metrics: Dict[str, Any] = {}
        if previous_analysis:
            raw_metrics = previous_analysis.get('orbo_response', {}).get('metrics')
            if not raw_metrics:
                raw_metrics = previous_analysis.get('metrics')
            if not raw_metrics:
                raw_metrics = previous_analysis.get('skin_metrics')
            previous_metrics = normalize_previous_metrics(raw_metrics)

        # Handle both wrapped and direct formats for extracting images and annotations
        if 'raw_response' in orbo_data:
            # Wrapped format from mobile SDK
            sdk_data = orbo_data.get('raw_response', {}).get('data', {})
        else:
            # Direct format
            sdk_data = orbo_data.get('data', {})
        
        # Extract image URLs and annotations from the correct location
        image_url = sdk_data.get('input_image', '')
        annotations = sdk_data.get('annotations', {})
        
        # If no input_image in SDK data, check for base64 or other image formats
        if not image_url:
            image_url = orbo_data.get('annotated_image_url', '')
            
        if not image_url and 'image_base64' in orbo_data:
            # If image is provided as base64, upload to S3
            image_bytes = base64.b64decode(orbo_data['image_base64'])
            image_url, thumbnail_url = await s3_service.upload_image(
                image_bytes,
                str(current_user.id),
                "orbo-analysis"
            )
        else:
            thumbnail_url = image_url
        
        # Map ORBO SDK results to our metrics structure
        # The SDK can return data in two formats:
        # 1. Direct: {"data": {"output_score": [...]}}
        # 2. Wrapped: {"raw_response": {"data": {"output_score": [...]}}}
        
        # Check for wrapped format first (from mobile SDK)
        if 'raw_response' in orbo_data:
            sdk_data = orbo_data.get('raw_response', {}).get('data', {})
        else:
            # Direct format
            sdk_data = orbo_data.get('data', {})
        
        output_scores = sdk_data.get('output_score', [])
        
        # Convert array of scores to dictionary
        orbo_scores = {}
        for item in output_scores:
            concern = item.get('concern')
            score = item.get('score', 0)
            if concern:
                orbo_scores[concern] = score
        
        # Log the actual concern names received from ORBO for debugging
        logger.info(f"ORBO concern names received: {list(orbo_scores.keys())}")
        logger.info(f"ORBO scores sample: {dict(list(orbo_scores.items())[:3])}")
        
        # Validate that we have actual scores from ORBO
        if not orbo_scores:
            logger.error(f"No scores received from ORBO SDK for user {current_user.id}")
            logger.error(f"ORBO data structure: {json.dumps(orbo_data, default=str)[:500]}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ORBO scan data: No scores found. Please ensure ORBO SDK is properly configured."
            )
        
        # Check if all scores are 0 (indicates a problem)
        non_zero_scores = [v for v in orbo_scores.values() if isinstance(v, (int, float)) and v > 0]
        if not non_zero_scores:
            logger.error(f"All ORBO scores are zero for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ORBO scan: All metrics returned zero. Please try scanning again with better lighting."
            )
        
        # Helper to pull scores while gracefully handling alternate concern names
        def get_score(*keys: str, default: float = 70.0) -> float:
            for key in keys:
                value = orbo_scores.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
            return float(default)

        # Calculate overall skin health score using ORBO-provided value when available,
        # otherwise average all known concern scores.
        numeric_scores = [float(v) for v in orbo_scores.values() if isinstance(v, (int, float))]
        average_score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 70.0
        overall_score = get_score(
            'overall_skin_health_score',
            'skin_health',
            'overall_score',
            default=average_score,
        )

        logger.info(
            "Overall skin health score determined: %s (fallback average: %s)",
            overall_score,
            average_score,
        )

        orbo_metrics = ORBOMetrics(
            overall_skin_health_score=overall_score,
            hydration=get_score('hydration'),
            smoothness=get_score('smoothness', 'texture', 'uneven_skin'),
            radiance=get_score('radiance', 'skin_dullness', 'shine'),
            dark_spots=get_score('dark_spots', 'pigmentation'),
            firmness=get_score('firmness', 'elasticity'),
            fine_lines_wrinkles=get_score('fine_lines_wrinkles', 'face_wrinkles', 'wrinkles', 'eye_wrinkles'),
            acne=get_score('acne', 'blemishes'),
            dark_circles=get_score('dark_circles', 'dark_circle'),
            redness=get_score('redness', 'sensitivity'),
        )

        metric_drop_events: List[Dict[str, Any]] = []
        if previous_metrics:
            current_metrics = orbo_metrics.dict()
            metric_labels = {
                'overall_skin_health_score': 'Overall Health',
                'hydration': 'Hydration',
                'smoothness': 'Smoothness',
                'radiance': 'Radiance',
                'dark_spots': 'Dark Spots',
                'firmness': 'Firmness',
                'fine_lines_wrinkles': 'Fine Lines',
                'acne': 'Acne',
                'dark_circles': 'Dark Circles',
                'redness': 'Redness',
            }

            def as_float(value: Any) -> Optional[float]:
                if isinstance(value, (int, float)):
                    return float(value)
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            for key, label in metric_labels.items():
                previous_value = as_float(previous_metrics.get(key))
                current_value = as_float(current_metrics.get(key))

                if previous_value is None or current_value is None:
                    continue
                if previous_value <= 0:
                    continue

                change_ratio = (current_value - previous_value) / previous_value
                if change_ratio <= -0.05:  # More than 5% drop
                    drop_percent = abs(change_ratio) * 100
                    metric_drop_events.append({
                        'key': key,
                        'label': label,
                        'previous': previous_value,
                        'current': current_value,
                        'drop_percent': drop_percent,
                    })

            metric_drop_events.sort(key=lambda item: item['drop_percent'], reverse=True)
        
        # Create ORBOResponse
        orbo_response = ORBOResponse(
            metrics=orbo_metrics,
            skin_type=orbo_data.get('skin_type'),
            concerns=orbo_data.get('concerns', []),
            confidence=orbo_data.get('confidence', 0.85),
            analysis_timestamp=get_utc_now(),
            raw_response=orbo_data
        )
        
        # Create the skin analysis document
        analysis = SkinAnalysisModel(
            user_id=current_user.id,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            orbo_response=orbo_response,
            metadata=ImageMetadata(
                face_detected=True,
                image_quality_score=orbo_data.get('quality_score', 0.8),
                analysis_version="orbo_sdk_v1"
            ),
            status="processing",  # Set to processing while AI pipeline runs
            tags=["orbo_sdk", "mobile_scan"],
            created_at=get_utc_now()
        )
        
        # Save initial analysis to MongoDB
        # Properly serialize nested Pydantic models
        analysis_dict = analysis.dict(by_alias=True)

        # Ensure nested ORBOResponse is properly serialized
        if orbo_response and isinstance(analysis_dict.get('orbo_response'), dict):
            # Make sure metrics are properly nested
            if 'metrics' not in analysis_dict['orbo_response']:
                # If metrics are at the wrong level, fix them
                analysis_dict['orbo_response'] = {
                    'metrics': orbo_metrics.dict() if hasattr(orbo_metrics, 'dict') else orbo_metrics,
                    'skin_type': orbo_response.skin_type,
                    'concerns': orbo_response.concerns,
                    'confidence': orbo_response.confidence,
                    'analysis_timestamp': orbo_response.analysis_timestamp.isoformat() if isinstance(orbo_response.analysis_timestamp, datetime) else orbo_response.analysis_timestamp,
                    'raw_response': orbo_response.raw_response
                }

        # Log the metrics being saved for debugging
        if 'orbo_response' in analysis_dict and 'metrics' in analysis_dict['orbo_response']:
            metrics = analysis_dict['orbo_response']['metrics']
            logger.info(f"Saving metrics to MongoDB - Overall: {metrics.get('overall_skin_health_score')}, "
                       f"Hydration: {metrics.get('hydration')}, Acne: {metrics.get('acne')}")
        
        result = db.skin_analyses.insert_one(analysis_dict)
        analysis_id = str(result.inserted_id)
        
        logger.info(f"ORBO analysis saved with ID: {analysis_id}")
        
        # Verify the save by reading it back
        saved_analysis = db.skin_analyses.find_one({"_id": result.inserted_id})
        if saved_analysis and 'orbo_response' in saved_analysis and 'metrics' in saved_analysis['orbo_response']:
            logger.info(f"Verified saved metrics - Overall score: {saved_analysis['orbo_response']['metrics'].get('overall_skin_health_score')}")
        else:
            logger.error(f"WARNING: Metrics may not have been saved properly for analysis {analysis_id}")

        if metric_drop_events:
            top_drop = metric_drop_events[0]
            title = f"{top_drop['label']} score dipped {top_drop['drop_percent']:.1f}%"

            if len(metric_drop_events) == 1:
                body = (
                    f"{top_drop['label']} went from {top_drop['previous']:.0f} to {top_drop['current']:.0f} since your last scan. "
                    "Open your insights for recovery tips."
                )
            else:
                other_labels = [event['label'] for event in metric_drop_events[1:]]
                if len(other_labels) == 1:
                    extras = f"{other_labels[0]} also dipped."
                else:
                    extras = ", ".join(other_labels[:2])
                    if len(other_labels) > 2:
                        extras += " and others dipped."
                    else:
                        extras += " also dipped."
                body = (
                    f"{top_drop['label']} fell from {top_drop['previous']:.0f} to {top_drop['current']:.0f}. "
                    f"{extras} Check today's analysis for guidance."
                )

            notification_data = {
                'type': 'metric_drop',
                'analysis_id': analysis_id,
                'primary_metric': top_drop['key'],
                'drop_percent': f"{top_drop['drop_percent']:.1f}",
                'previous_score': f"{top_drop['previous']:.1f}",
                'current_score': f"{top_drop['current']:.1f}",
                'affected_metrics': json.dumps([
                    {
                        'metric': event['key'],
                        'drop_percent': round(event['drop_percent'], 1),
                        'previous': round(event['previous'], 1),
                        'current': round(event['current'], 1),
                    }
                    for event in metric_drop_events
                ]),
            }

            notification_sent = notification_service.send_push_notification(
                user_id=current_user.id,
                title=title,
                body=body,
                data=notification_data,
                db=db,
                notification_type='metric_drop'
            )
            logger.info(
                "Metric drop notification processed for analysis %s (sent=%s)",
                analysis_id,
                notification_sent,
            )
        
        # Update achievements: per-day photo count for streaks and totals
        try:
            # Ensure unique index on (user_id, date)
            db.achievements.create_index([("user_id", 1), ("date", 1)], unique=True)
        except Exception:
            pass
        day_start = get_utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate current streak to update in cache
        from datetime import timedelta
        
        # Check if user has an entry for yesterday
        yesterday_start = day_start - timedelta(days=1)
        yesterday_entry = db.achievements.find_one({
            "user_id": ObjectId(str(current_user.id)),
            "date": yesterday_start
        })
        
        # Calculate streak - if yesterday has photos, we're continuing a streak
        # Otherwise, we're starting a new streak today
        current_streak = 1  # Today counts as 1
        if yesterday_entry and yesterday_entry.get("photos_taken", 0) > 0:
            # Continue counting backwards to find full streak
            streak_days = 1
            check_date = yesterday_start
            while True:
                check_date = check_date - timedelta(days=1)
                entry = db.achievements.find_one({
                    "user_id": ObjectId(str(current_user.id)),
                    "date": check_date
                })
                if entry and entry.get("photos_taken", 0) > 0:
                    streak_days += 1
                else:
                    break
            current_streak = streak_days + 1  # Add today
        
        logger.info(f"Calculated streak for user {current_user.id}: {current_streak} days")
        
        # Update the achievements entry with streak information
        db.achievements.update_one(
            {"user_id": ObjectId(str(current_user.id)), "date": day_start},
            {
                "$setOnInsert": {"created_at": get_utc_now()},
                "$inc": {"photos_taken": 1},
                "$addToSet": {"analysis_ids": analysis_id},
                "$set": {"streak_current": current_streak, "updated_at": get_utc_now()},
            },
            upsert=True,
        )
        
        # If we are isolating ORBO (default), return early and let the client
        # call a separate endpoint to run AI. This avoids long-running calls
        # and isolates possible 500s from third-party services.
        if not run_ai:
            db.skin_analyses.update_one(
                {"_id": result.inserted_id},
                {"$set": {"status": "awaiting_ai"}}
            )
            return {
                "analysis_id": analysis_id,
                "user_id": str(current_user.id),
                "timestamp": get_utc_now().isoformat(),
                "skin_metrics": {
                    "overall_health": orbo_metrics.overall_skin_health_score,
                    "hydration": orbo_metrics.hydration,
                    "smoothness": orbo_metrics.smoothness,
                    "radiance": orbo_metrics.radiance,
                    "dark_spots": orbo_metrics.dark_spots,
                    "firmness": orbo_metrics.firmness,
                    "fine_lines_wrinkles": orbo_metrics.fine_lines_wrinkles,
                    "acne": orbo_metrics.acne,
                    "dark_circles": orbo_metrics.dark_circles,
                    "redness": orbo_metrics.redness,
                },
                "skin_profile": {
                    "skin_type": orbo_response.skin_type,
                    "main_concerns": orbo_response.concerns[:3] if orbo_response.concerns else [],
                    "confidence_score": orbo_response.confidence,
                },
                "image_url": image_url,
                "thumbnail_url": thumbnail_url,
                "annotations": annotations,  # Include annotation URLs for each concern
                "status": "awaiting_ai",
                "processing_complete": False,
                "ai_pending": True,
            }
        
        # Otherwise, continue with AI pipeline as before
        # Step 1: Generate OpenAI Feedback
        ai_feedback = None
        try:
            logger.info("Generating OpenAI feedback...")
            ai_feedback_dict = openai_service.generate_skin_feedback(
                orbo_response.dict(),
                current_user.dict()
            )
            if ai_feedback_dict:
                ai_feedback = AIFeedback(
                    summary=ai_feedback_dict.get('summary', ''),
                    recommendations=ai_feedback_dict.get('recommendations', []),
                    routine_suggestions=ai_feedback_dict.get('routine_suggestions', ''),
                    progress_notes=ai_feedback_dict.get('progress_notes'),
                    encouragement=ai_feedback_dict.get('encouragement', ''),
                    next_steps=ai_feedback_dict.get('next_steps', [])
                )
                db.skin_analyses.update_one(
                    {"_id": result.inserted_id},
                    {"$set": {"ai_feedback": ai_feedback.dict()}}
                )
                logger.info("OpenAI feedback generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate AI feedback: {e}")
            ai_feedback = AIFeedback(
                summary=f"AI analysis temporarily unavailable: {str(e)}",
                recommendations=[],
                routine_suggestions="",
                encouragement="",
                next_steps=[]
            )
        
        # Step 2: Get Perplexity Product Recommendations
        product_recommendations = None
        try:
            logger.info("Fetching Perplexity product recommendations...")
            user_location = {"city": "Los Angeles", "state": "CA", "zip_code": "90210"}
            recommendations = await recommendation_service.get_recommendations_for_analysis(
                analysis_id=analysis_id,
                user=current_user,
                user_location=user_location,
                db=db,
            )
            product_recommendations = recommendations
            logger.info(f"Generated {len(recommendations.get('products', []))} product recommendations")
        except Exception as e:
            logger.error(f"Failed to get Perplexity recommendations: {e}")
            product_recommendations = {"products": [], "routine": {}, "error": f"Recommendation service unavailable: {str(e)}"}
        
        db.skin_analyses.update_one(
            {"_id": result.inserted_id},
            {"$set": {"status": "completed", "analysis_completed_at": get_utc_now(), "product_recommendations": product_recommendations}}
        )
        
        complete_response = {
            "analysis_id": analysis_id,
            "user_id": str(current_user.id),
            "timestamp": get_utc_now().isoformat(),
            "skin_metrics": {
                "overall_health": orbo_metrics.overall_skin_health_score,
                "hydration": orbo_metrics.hydration,
                "smoothness": orbo_metrics.smoothness,
                "radiance": orbo_metrics.radiance,
                "dark_spots": orbo_metrics.dark_spots,
                "firmness": orbo_metrics.firmness,
                "fine_lines_wrinkles": orbo_metrics.fine_lines_wrinkles,
                "acne": orbo_metrics.acne,
                "dark_circles": orbo_metrics.dark_circles,
                "redness": orbo_metrics.redness,
            },
            "skin_metrics_colored": {
                "overall_health": format_metric_with_color("Overall Health", orbo_metrics.overall_skin_health_score),
                "hydration": format_metric_with_color("Hydration", orbo_metrics.hydration),
                "smoothness": format_metric_with_color("Smoothness", orbo_metrics.smoothness),
                "radiance": format_metric_with_color("Radiance", orbo_metrics.radiance),
                "dark_spots": format_metric_with_color("Dark Spots", orbo_metrics.dark_spots),
                "firmness": format_metric_with_color("Firmness", orbo_metrics.firmness),
                "fine_lines_wrinkles": format_metric_with_color("Fine Lines & Wrinkles", orbo_metrics.fine_lines_wrinkles),
                "acne": format_metric_with_color("Acne", orbo_metrics.acne),
                "dark_circles": format_metric_with_color("Dark Circles", orbo_metrics.dark_circles),
                "redness": format_metric_with_color("Redness", orbo_metrics.redness),
            },
            "skin_profile": {
                "skin_type": orbo_response.skin_type,
                "main_concerns": orbo_response.concerns[:3] if orbo_response.concerns else [],
                "confidence_score": orbo_response.confidence,
            },
            "ai_feedback": {
                "summary": ai_feedback.summary if ai_feedback else "",
                "key_insights": ai_feedback.recommendations[:3] if ai_feedback else [],
                "routine_advice": ai_feedback.routine_suggestions if ai_feedback else "",
                "encouragement": ai_feedback.encouragement if ai_feedback else "",
                "next_steps": ai_feedback.next_steps[:3] if ai_feedback else [],
            },
            "product_recommendations": product_recommendations.get('products', [])[:5] if product_recommendations else [],
            "suggested_routine": product_recommendations.get('routine', {}) if product_recommendations else {},
            "image_url": image_url,
            "thumbnail_url": thumbnail_url,
            "annotations": annotations,  # Include annotation URLs for each concern
            "status": "completed",
            "processing_complete": True,
        }
        
        # Track achievement for completed analysis
        from .achievement_integration import track_skin_analysis_completion
        
        # Track the achievement
        track_skin_analysis_completion(
            user_id=str(current_user.id),
            analysis_id=analysis_id,
            skin_score=orbo_metrics.overall_skin_health_score
        )
        
        logger.info(f"Tracked achievement for ORBO SDK analysis {analysis_id}, user {current_user.id}, score: {orbo_metrics.overall_skin_health_score}")
        logger.info(f"AI pipeline completed for analysis {analysis_id}")
        return complete_response
        
    except Exception as e:
        logger.error(f"Error in ORBO AI pipeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process analysis: {str(e)}"
        )

@router.post("/{analysis_id}/run-ai", response_model=Dict[str, Any])
async def run_ai_for_analysis(
    analysis_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
    city: str = "Los Angeles",
    state: str = "CA",
    zip_code: str = "90210",
):
    """Run AI feedback and recommendations for an existing ORBO analysis."""
    logger.info(f"Running AI pipeline for analysis {analysis_id}, user {current_user.id}")
    
    # CRITICAL FIX: Convert user_id to ObjectId for query
    user_oid = ObjectId(str(current_user.id))
    analysis = db.skin_analyses.find_one({"_id": ObjectId(analysis_id), "user_id": {"$in": [user_oid, str(current_user.id)]}})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    orbo_response = analysis.get("orbo_response")
    if not orbo_response:
        raise HTTPException(status_code=400, detail="ORBO results not found for this analysis")
    
    # Generate OpenAI feedback
    ai_feedback = None
    try:
        logger.info("Generating OpenAI feedback...")
        logger.info(f"ORBO response keys: {orbo_response.keys() if orbo_response else 'None'}")
        
        # Log the actual metric values we're about to send
        if 'metrics' in orbo_response:
            logger.info(f"ORBO metrics found: {orbo_response['metrics'].keys()}")
            sample_metrics = {k: orbo_response['metrics'].get(k) for k in ['hydration', 'acne', 'overall_skin_health_score'] if k in orbo_response['metrics']}
            logger.info(f"Sample metric values: {sample_metrics}")
        else:
            # Check if metrics are at top level
            if 'hydration' in orbo_response:
                logger.info("Metrics at top level of orbo_response")
                sample_metrics = {k: orbo_response.get(k) for k in ['hydration', 'acne', 'overall_skin_health_score'] if k in orbo_response}
                logger.info(f"Sample metric values: {sample_metrics}")
            else:
                logger.info("No metrics found in orbo_response!")
        
        # Call OpenAI synchronously (PyMongo is sync, not async)
        ai_feedback_dict = openai_service.generate_skin_feedback(orbo_response, current_user.dict())
        logger.info(f"OpenAI raw response: {ai_feedback_dict}")
        if ai_feedback_dict:
            logger.info(f"OpenAI feedback generated with {len(ai_feedback_dict.get('recommendations', []))} recommendations")
            ai_feedback = AIFeedback(
                summary=ai_feedback_dict.get('summary', ''),
                recommendations=ai_feedback_dict.get('recommendations', []),
                routine_suggestions=ai_feedback_dict.get('routine_suggestions', ''),
                progress_notes=ai_feedback_dict.get('progress_notes'),
                encouragement=ai_feedback_dict.get('encouragement', ''),
                next_steps=ai_feedback_dict.get('next_steps', []),
            )
            db.skin_analyses.update_one({"_id": ObjectId(analysis_id)}, {"$set": {"ai_feedback": ai_feedback.dict()}})
            logger.info(f"AI feedback saved: {ai_feedback.dict()}")
        else:
            logger.warning("OpenAI returned empty feedback - using fallback")
            # Use fallback if OpenAI returns nothing
            ai_feedback = AIFeedback(
                summary="Your skin analysis is complete! Based on your results, I've prepared personalized insights for you.",
                recommendations=[
                    "Stay hydrated by drinking at least 8 glasses of water daily",
                    "Apply SPF 30+ sunscreen every morning, even on cloudy days",
                    "Maintain a consistent skincare routine morning and evening"
                ],
                routine_suggestions="Start with a gentle cleanser, followed by a lightweight moisturizer in the morning and a richer one at night.",
                encouragement="You're taking great steps in your skincare journey! Remember, consistency is key to seeing results.",
                next_steps=["Track your progress with weekly photos", "Note any skin changes in your journal"]
            )
            db.skin_analyses.update_one({"_id": ObjectId(analysis_id)}, {"$set": {"ai_feedback": ai_feedback.dict()}})
            logger.info(f"Fallback AI feedback saved: {ai_feedback.dict()}")
    except Exception as e:
        logger.error(f"OpenAI feedback generation failed: {e} - using fallback")
        # Use fallback on error
        ai_feedback = AIFeedback(
            summary="Analysis complete! While I process your detailed insights, here are some personalized recommendations.",
            recommendations=[
                "Cleanse your face gently twice daily",
                "Apply moisturizer while skin is still damp",
                "Never skip sunscreen during the day"
            ],
            routine_suggestions="Build a simple routine: cleanser, toner, moisturizer, and SPF in the morning.",
            encouragement="Every step you take matters! Your skin will thank you for the consistency.",
            next_steps=["Continue your current routine", "Take progress photos weekly"]
        )
        db.skin_analyses.update_one({"_id": ObjectId(analysis_id)}, {"$set": {"ai_feedback": ai_feedback.dict()}})
        logger.info(f"Error fallback AI feedback saved: {ai_feedback.dict()}")
    
    # TEMPORARILY DISABLED: Perplexity recommendations to debug OpenAI first
    recs = None
    # try:
    #     user_location = {"city": city, "state": state, "zip_code": zip_code}
    #     logger.info(f"Getting Perplexity recommendations for location: {user_location}")
    #     recs = await recommendation_service.get_recommendations_for_analysis(
    #         analysis_id=analysis_id, user=current_user, user_location=user_location, db=db
    #     )
    #     if recs:
    #         logger.info(f"Recommendations result: {recs.get('source_mix', {})}")
    #         if 'recommendations' in recs:
    #             logger.info(f"Got {len(recs['recommendations'])} product recommendations")
    #         else:
    #             logger.warning(f"Recommendations structure unexpected: {recs.keys()}")
    # except Exception as e:
    #     logger.error(f"Perplexity recommendation generation failed: {e}")
    #     # Create fallback recommendations
    #     logger.info("Using fallback recommendations due to error")
    #     recs = {"products": [], "recommendations": [], "routine": {}, "error": str(e), "source": "fallback"}
    
    # For now, just use empty recommendations
    logger.info("Perplexity temporarily disabled for debugging")
    recs = {"products": [], "recommendations": [], "routine": {}, "source": "disabled_for_debug"}
    
    db.skin_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {"product_recommendations": recs, "status": "completed", "analysis_completed_at": get_utc_now()}},
    )
    
    # Get product recommendations from either 'products' or 'recommendations' key
    product_list = recs.get("products", [])
    if not product_list and "recommendations" in recs:
        product_list = recs.get("recommendations", [])
    
    logger.info(f"Returning {len(product_list)} product recommendations to frontend")
    
    # Track achievement for completed analysis (if not already tracked)
    from .achievement_integration import track_skin_analysis_completion
    
    # Get the overall skin score from the ORBO response
    # Check both possible locations: metrics.overall_skin_health_score or direct
    skin_score = 0
    if isinstance(orbo_response, dict):
        if 'metrics' in orbo_response and isinstance(orbo_response['metrics'], dict):
            skin_score = orbo_response['metrics'].get('overall_skin_health_score', 0)
        else:
            skin_score = orbo_response.get('overall_skin_health_score', 0)
    
    logger.info(f"Extracted skin score for achievement tracking: {skin_score}")
    
    # Track the achievement
    track_skin_analysis_completion(
        user_id=str(current_user.id),
        analysis_id=analysis_id,
        skin_score=skin_score
    )
    
    logger.info(f"Tracked achievement for run-ai analysis {analysis_id}, user {current_user.id}, score: {skin_score}")
    
    return {
        "analysis_id": analysis_id,
        "ai_feedback": ai_feedback.dict() if ai_feedback else {},
        "product_recommendations": product_list,
        "suggested_routine": recs.get("routine", {}),
        "status": "completed",
    }

@router.post("/test-auth", response_model=Dict[str, Any])
async def test_authentication(
    current_user: UserModel = Depends(get_current_active_user),
):
    """Test endpoint to verify authentication is working"""
    return {
        "success": True,
        "user_id": str(current_user.id),
        "email": current_user.email,
        "message": "Authentication successful"
    }

@router.post("/orbo-sdk-test", response_model=Dict[str, Any])
async def test_orbo_sdk_result(
    orbo_data: Dict[str, Any],
    db: Database = Depends(get_database),
):
    """
    TEST ENDPOINT - No authentication required
    Save ORBO SDK scan results without authentication for testing
    """
    
    logger.info(f"TEST: ORBO SDK result received")
    logger.info(f"ORBO data: {json.dumps(orbo_data, default=str)}")
    
    try:
        # Map ORBO SDK results to our metrics structure
        # The SDK returns data in the format: {"data": {"output_score": [...]}}
        sdk_data = orbo_data.get('data', {})
        output_scores = sdk_data.get('output_score', [])
        
        # Convert array of scores to dictionary
        orbo_scores = {}
        for item in output_scores:
            concern = item.get('concern')
            score = item.get('score', 0)
            if concern:
                orbo_scores[concern] = score
        
        def get_score(*keys: str, default: float = 70.0) -> float:
            for key in keys:
                value = orbo_scores.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
            return float(default)

        numeric_scores = [float(v) for v in orbo_scores.values() if isinstance(v, (int, float))]
        average_score = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 70.0

        # Map to SkinSense metrics (higher = better)
        metrics = {
            'overall_skin_health_score': get_score('overall_skin_health_score', 'skin_health', 'overall_score', default=average_score),
            'hydration': get_score('hydration'),
            'smoothness': get_score('smoothness', 'texture', 'uneven_skin'),
            'radiance': get_score('radiance', 'skin_dullness', 'shine'),
            'dark_spots': get_score('dark_spots', 'pigmentation'),
            'firmness': get_score('firmness', 'elasticity'),
            'fine_lines_wrinkles': get_score('fine_lines_wrinkles', 'face_wrinkles', 'wrinkles', 'eye_wrinkles'),
            'acne': get_score('acne', 'blemishes'),
            'dark_circles': get_score('dark_circles', 'dark_circle'),
            'redness': get_score('redness', 'sensitivity'),
        }
        
        # Create test user ID
        test_user_id = "test_user_12345"
        
        # Save analysis to database
        analysis_doc = {
            "user_id": test_user_id,
            "orbo_response": orbo_data,
            "metrics": metrics,
            "created_at": get_utc_now(),
            "status": "completed",
            "is_test": True,
            "raw_scores": orbo_scores
        }
        
        result = db.skin_analyses.insert_one(analysis_doc)
        analysis_id = str(result.inserted_id)
        
        logger.info(f"TEST: Analysis saved with ID {analysis_id}")
        
        # Add color-coded metrics
        metrics_colored = {
            "overall_health": format_metric_with_color("Overall Health", metrics['overall_skin_health_score']),
            "hydration": format_metric_with_color("Hydration", metrics['hydration']),
            "smoothness": format_metric_with_color("Smoothness", metrics['smoothness']),
            "radiance": format_metric_with_color("Radiance", metrics['radiance']),
            "dark_spots": format_metric_with_color("Dark Spots", metrics['dark_spots']),
            "firmness": format_metric_with_color("Firmness", metrics['firmness']),
            "fine_lines_wrinkles": format_metric_with_color("Fine Lines & Wrinkles", metrics['fine_lines_wrinkles']),
            "acne": format_metric_with_color("Acne", metrics['acne']),
            "dark_circles": format_metric_with_color("Dark Circles", metrics['dark_circles']),
            "redness": format_metric_with_color("Redness", metrics['redness']),
        }
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "metrics": metrics,
            "metrics_colored": metrics_colored,
            "message": "Test endpoint - ORBO SDK result saved successfully",
            "raw_scores": orbo_scores
        }
        
    except Exception as e:
        logger.error(f"TEST: Error processing ORBO SDK result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process test analysis: {str(e)}"
        )

@router.get("/progress-insights", response_model=Dict[str, Any])
async def get_progress_insights(
    period_days: int = 30,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get detailed progress insights over time with Redis caching"""

    # Try to get from cache first
    cache_key = f"{str(current_user.id)}_{period_days}"
    cached_data = cache_service.get("progress_insights", cache_key)

    if cached_data:
        logger.debug(f"Cache hit for progress_insights:{cache_key}")
        return cached_data

    insights = await recommendation_service.get_progress_insights(
        user=current_user,
        db=db,
        period_days=period_days
    )

    # Cache the result for 5 minutes
    cache_service.set("progress_insights", cache_key, insights, ttl_seconds=300)
    logger.debug(f"Cached progress_insights:{cache_key} for 300 seconds")

    return insights

# Progress tracking endpoints
@router.get("/achievements/summary", response_model=Dict[str, Any])
async def achievements_summary(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
    tz_offset_minutes: int = 0,
    period_days: int = 365,
):
    """Return photos taken totals and current streak.

    Permanent approach: compute from skin_analyses as source of truth using a
    timezone offset (in minutes) to determine local calendar days. If the
    achievements cache exists, it is used for fast paths; otherwise we fall back
    to live computation so the UI never shows zeros after a save.
    """

    user_oid = ObjectId(str(current_user.id))
    
    # Debug logging
    logger.info(f"[ACHIEVEMENTS DEBUG] Fetching for user: {current_user.id} (OID: {user_oid})")
    logger.info(f"[ACHIEVEMENTS DEBUG] TZ offset minutes: {tz_offset_minutes}")

    # Helper to shift a UTC datetime by tz_offset to local time, then normalize
    def to_local_day(dt: datetime) -> datetime:
        local = dt + timedelta(minutes=tz_offset_minutes)
        local_midnight = datetime(local.year, local.month, local.day)
        # Return the UTC moment corresponding to local midnight by reversing offset
        return local_midnight - timedelta(minutes=tz_offset_minutes)

    # Today start (UTC) corresponding to local midnight
    now_utc = get_utc_now()  # Already returns naive UTC datetime
    # For achievements cache, use plain UTC midnight (same as how we save)
    today_start_utc_plain = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    # For skin_analyses fallback, use timezone-adjusted
    today_start_utc = to_local_day(now_utc)

    # Fast path: achievements cache (use plain UTC to match how we save)
    today_doc = db.achievements.find_one({"user_id": user_oid, "date": today_start_utc_plain}) or {}
    logger.info(f"[ACHIEVEMENTS DEBUG] Today's doc (plain UTC): {today_doc}")
    
    total_agg = list(
        db.achievements.aggregate([
            {"$match": {"user_id": user_oid}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$photos_taken", 0]}}}},
        ])
    )
    cached_total = int(total_agg[0]["total"]) if total_agg else 0
    cached_today = int(today_doc.get("photos_taken", 0))
    
    logger.info(f"[ACHIEVEMENTS DEBUG] Cached total: {cached_total}, Today: {cached_today}")

    # Compute streak from cache if available
    streak_cached = 0
    cursor = db.achievements.find({"user_id": user_oid, "photos_taken": {"$gt": 0}}).sort("date", -1)
    achievement_docs = list(cursor)
    logger.info(f"[ACHIEVEMENTS DEBUG] Found {len(achievement_docs)} achievement records with photos")
    
    days_cached = []
    for doc in achievement_docs:
        date_val = doc.get("date")
        if isinstance(date_val, datetime):
            days_cached.append(date_val)
            logger.info(f"[ACHIEVEMENTS DEBUG] Achievement date: {date_val}, photos: {doc.get('photos_taken')}")
    
    # Use plain UTC for streak calculation (matches how we save)
    expected = today_start_utc_plain
    logger.info(f"[ACHIEVEMENTS DEBUG] Starting streak calc from today (plain UTC): {expected}")
    
    for d in days_cached:
        d0 = d.replace(hour=0, minute=0, second=0, microsecond=0)
        logger.info(f"[ACHIEVEMENTS DEBUG] Checking date {d0} against expected {expected}")
        if d0 == expected:
            streak_cached += 1
            logger.info(f"[ACHIEVEMENTS DEBUG] Streak day found! Current streak: {streak_cached}")
            expected = expected - timedelta(days=1)
        elif d0 < expected:
            logger.info(f"[ACHIEVEMENTS DEBUG] Date {d0} is before expected {expected}, breaking")
            break

    # If cache has any signal, prefer it but enrich streak/today with skin_analyses when needed
    if cached_total > 0 or cached_today > 0 or streak_cached > 0:
        enriched_streak = streak_cached
        enriched_today = cached_today

        # If cached streak is 0 (or missing), compute streak from skin_analyses using tz-aware bucketing
        if streak_cached == 0:
            try:
                # Determine user_id format that exists in skin_analyses
                total_analyses_count = db.skin_analyses.count_documents({"user_id": user_oid})
                if total_analyses_count == 0:
                    total_analyses_count = db.skin_analyses.count_documents({"user_id": str(current_user.id)})
                    user_query = str(current_user.id) if total_analyses_count > 0 else user_oid
                else:
                    user_query = user_oid

                # Build local-day buckets for the last year
                start_utc = today_start_utc - timedelta(days=period_days - 1)
                docs = db.skin_analyses.find({
                    "user_id": user_query,
                    "created_at": {"$gte": start_utc},
                }, {"created_at": 1}).sort("created_at", 1)

                local_days = []
                for doc in docs:
                    created_at = doc.get("created_at")
                    if isinstance(created_at, datetime):
                        day_utc = to_local_day(created_at)
                        if not local_days or local_days[-1] != day_utc:
                            local_days.append(day_utc)

                # tz-aware today count
                enriched_today = db.skin_analyses.count_documents({
                    "user_id": user_query,
                    "created_at": {"$gte": today_start_utc, "$lt": today_start_utc + timedelta(days=1)},
                })

                local_days_sorted = sorted(local_days, reverse=True)
                expected = today_start_utc
                tmp_streak = 0
                for d in local_days_sorted:
                    if d == expected:
                        tmp_streak += 1
                        expected = expected - timedelta(days=1)
                    elif d < expected:
                        break

                if tmp_streak > 0:
                    enriched_streak = tmp_streak
            except Exception as _:
                # On any failure, keep cached values
                pass

        return {
            "total_photos": cached_total,
            "streak_current": enriched_streak,
            "today_count": enriched_today,
            "source": "achievements_cache_enriched" if enriched_streak != streak_cached or enriched_today != cached_today else "achievements_cache",
        }

    # Fallback: compute from skin_analyses (source of truth)
    logger.info("[ACHIEVEMENTS DEBUG] Cache empty, falling back to skin_analyses collection")
    start_utc = today_start_utc - timedelta(days=period_days - 1)
    
    # Count total analyses for this user - try both ObjectId and string formats
    total_analyses_count = db.skin_analyses.count_documents({"user_id": user_oid})
    if total_analyses_count == 0:
        # Try with string user_id
        total_analyses_count = db.skin_analyses.count_documents({"user_id": str(current_user.id)})
        logger.info(f"[ACHIEVEMENTS DEBUG] Total analyses for user (string ID): {total_analyses_count}")
        # If string format has data, use it
        if total_analyses_count > 0:
            user_query = str(current_user.id)
        else:
            user_query = user_oid
    else:
        user_query = user_oid
        logger.info(f"[ACHIEVEMENTS DEBUG] Total analyses for user (ObjectId): {total_analyses_count}")
    
    docs = db.skin_analyses.find({
        "user_id": user_query,
        "created_at": {"$gte": start_utc},
    }, {"created_at": 1}).sort("created_at", 1)

    # Build a set of local-day buckets
    local_days = []  # list of UTC day-starts corresponding to local days
    total_photos = 0
    for doc in docs:
        created_at = doc.get("created_at")
        if isinstance(created_at, datetime):
            total_photos += 1
            day_utc = to_local_day(created_at)
            if not local_days or local_days[-1] != day_utc:
                local_days.append(day_utc)

    # Today count = number of docs that fall into today's local bucket
    today_count = db.skin_analyses.count_documents({
        "user_id": user_query,  # Use the same query format that worked above
        "created_at": {"$gte": today_start_utc, "$lt": today_start_utc + timedelta(days=1)},
    })

    # Compute streak from local_days (descending)
    local_days_sorted = sorted(local_days, reverse=True)
    streak = 0
    expected = today_start_utc
    for d in local_days_sorted:
        if d == expected:
            streak += 1
            expected = expected - timedelta(days=1)
        elif d < expected:
            break

    return {
        "total_photos": total_photos,
        "streak_current": streak,
        "today_count": int(today_count),
        "source": "skin_analyses_fallback",
    }
@router.get("/debug/user-data", response_model=Dict[str, Any])
async def debug_user_data(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Debug endpoint to check user data in MongoDB"""
    user_oid = ObjectId(str(current_user.id))
    
    # Check achievements collection
    achievements_count = db.achievements.count_documents({"user_id": user_oid})
    achievements_sample = list(db.achievements.find({"user_id": user_oid}).limit(2))
    
    # Check skin_analyses with ObjectId
    analyses_oid_count = db.skin_analyses.count_documents({"user_id": user_oid})
    
    # Check skin_analyses with string
    analyses_str_count = db.skin_analyses.count_documents({"user_id": str(current_user.id)})
    
    # Get a sample analysis to see the user_id format
    sample_analysis = db.skin_analyses.find_one()
    user_id_type = type(sample_analysis["user_id"]).__name__ if sample_analysis else "None"
    
    return {
        "current_user_id": str(current_user.id),
        "user_oid": str(user_oid),
        "achievements": {
            "count": achievements_count,
            "samples": [{"date": str(a.get("date")), "photos_taken": a.get("photos_taken")} for a in achievements_sample]
        },
        "skin_analyses": {
            "with_objectid": analyses_oid_count,
            "with_string": analyses_str_count,
            "sample_user_id_type": user_id_type,
            "sample_user_id": str(sample_analysis["user_id"]) if sample_analysis else None
        }
    }

@router.get("/progress/metrics/{metric_name}", response_model=Dict[str, Any])
async def get_metric_progress(
    metric_name: str,
    period_days: int = 30,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get progress data for a specific metric with Redis caching"""

    # Validate metric name
    valid_metrics = [
        "overall_skin_health_score", "hydration", "smoothness", "radiance",
        "dark_spots", "firmness", "fine_lines_wrinkles", "acne",
        "dark_circles", "redness"
    ]

    if metric_name not in valid_metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric name. Valid metrics: {', '.join(valid_metrics)}"
        )

    # Ensure user_id is ObjectId
    from bson import ObjectId
    try:
        user_oid = current_user.id if isinstance(current_user.id, ObjectId) else ObjectId(str(current_user.id))
    except:
        user_oid = ObjectId(str(current_user.id))

    # Try to get from cache first
    cache_key = f"{str(user_oid)}_{metric_name}_{period_days}"
    cached_data = cache_service.get("metric_progress", cache_key)

    if cached_data:
        logger.debug(f"Cache hit for metric_progress:{cache_key}")
        return cached_data

    trend_data = progress_service.get_trend_data(
        user_id=user_oid,
        db=db,
        metric_name=metric_name,
        period_days=period_days
    )

    # Cache the result for 5 minutes
    cache_service.set("metric_progress", cache_key, trend_data, ttl_seconds=300)
    logger.debug(f"Cached metric_progress:{cache_key} for 300 seconds")

    return trend_data

@router.get("/progress/metrics/{metric_name}/history", response_model=List[Dict[str, Any]])
async def get_metric_history(
    metric_name: str,
    limit: int = 10,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get historical values for a specific metric"""
    
    history = progress_service.get_metric_history(
        user_id=current_user.id,
        db=db,
        metric_name=metric_name,
        limit=limit
    )
    
    return history

@router.post("/progress/comparison", response_model=Dict[str, Any])
async def compare_analyses(
    comparison_request: ProgressComparisonRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Compare two specific analyses"""
    
    # Fetch both analyses
    current_analysis = db.skin_analyses.find_one({
        "_id": ObjectId(comparison_request.current_analysis_id),
        "user_id": {"$in": [ObjectId(str(current_user.id)), str(current_user.id)]}
    })
    
    previous_analysis = db.skin_analyses.find_one({
        "_id": ObjectId(comparison_request.previous_analysis_id),
        "user_id": {"$in": [ObjectId(str(current_user.id)), str(current_user.id)]}
    })
    
    if not current_analysis or not previous_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both analyses not found"
        )
    
    comparison = progress_service.calculate_metric_changes(
        current_analysis=current_analysis,
        previous_analysis=previous_analysis
    )
    
    return {
        "comparison": comparison.dict(),
        "current_analysis": {
            "id": str(current_analysis["_id"]),
            "date": current_analysis["created_at"].isoformat(),
            "image_url": current_analysis.get("thumbnail_url")
        },
        "previous_analysis": {
            "id": str(previous_analysis["_id"]),
            "date": previous_analysis["created_at"].isoformat(),
            "image_url": previous_analysis.get("thumbnail_url")
        }
    }

@router.get("/progress/summary", response_model=Dict[str, Any])
async def get_progress_summary(
    period_days: int = 30,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get comprehensive progress summary with Redis caching"""

    # Ensure user_id is ObjectId
    from bson import ObjectId
    try:
        user_oid = current_user.id if isinstance(current_user.id, ObjectId) else ObjectId(str(current_user.id))
    except:
        user_oid = ObjectId(str(current_user.id))

    # Try to get from cache first
    cache_key = f"{str(user_oid)}_{period_days}"
    cached_data = cache_service.get("progress_summary", cache_key)

    if cached_data:
        logger.debug(f"Cache hit for progress_summary:{cache_key}")
        return cached_data

    # Generate fresh data if not in cache
    summary = progress_service.generate_progress_summary(
        user_id=user_oid,
        db=db,
        period_days=period_days
    )

    # Cache the result for 5 minutes
    cache_service.set("progress_summary", cache_key, summary, ttl_seconds=300)
    logger.debug(f"Cached progress_summary:{cache_key} for 300 seconds")

    return summary

@router.get("/progress/trends", response_model=Dict[str, Any])
async def get_all_trends(
    period_days: int = 30,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get trend data for all metrics with Redis caching"""

    # Ensure user_id is ObjectId
    from bson import ObjectId
    try:
        user_oid = current_user.id if isinstance(current_user.id, ObjectId) else ObjectId(str(current_user.id))
    except:
        user_oid = ObjectId(str(current_user.id))

    # Try to get from cache first
    cache_key = f"{str(user_oid)}_{period_days}"
    cached_data = cache_service.get("progress_trends", cache_key)

    if cached_data:
        logger.debug(f"Cache hit for progress_trends:{cache_key}")
        return cached_data

    metrics = [
        "overall_skin_health_score", "hydration", "smoothness", "radiance",
        "dark_spots", "firmness", "fine_lines_wrinkles", "acne",
        "dark_circles", "redness"
    ]

    trends = {}
    for metric in metrics:
        trends[metric] = progress_service.get_trend_data(
            user_id=user_oid,
            db=db,
            metric_name=metric,
            period_days=period_days
        )

    result = {
        "period_days": period_days,
        "metrics": trends,
        "generated_at": get_utc_now().isoformat()
    }

    # Cache the result for 5 minutes
    cache_service.set("progress_trends", cache_key, result, ttl_seconds=300)
    logger.debug(f"Cached progress_trends:{cache_key} for 300 seconds")

    return result

# ORBO AI Integration Endpoints
@router.post("/orbo/analyze-skin")
async def analyze_skin_with_orbo(
    image: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
    request: Request = None
):
    """
    Complete skin analysis using ORBO API with data sovereignty
    """
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read image data
        image_data = await image.read()
        
        # Prepare image metadata
        image_metadata = {
            "original_filename": image.filename,
            "file_size": len(image_data),
            "content_type": image.content_type,
            "upload_timestamp": get_utc_now().isoformat(),
            "user_agent": request.headers.get("user-agent", "") if request else "",
            "client_ip": request.client.host if request else "unknown"
        }
        
        # Initialize ORBO service with database
        orbo_service = OrboSkinAnalysisService(db)
        
        # Run complete analysis pipeline WITH middleware
        result = await orbo_service.complete_analysis_pipeline_with_middleware(
            image_data, 
            str(current_user.id),
            image_metadata
        )
        
        if not result['success']:
            # Extract user-friendly error message
            error_details = result.get('error', {})
            if isinstance(error_details, dict):
                user_message = error_details.get('message', 'Analysis failed')
                error_code = error_details.get('error_code', 'unknown')
                action = error_details.get('action', 'Please try again')
                
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": user_message,
                        "action": action,
                        "error_code": error_code,
                        "retry_allowed": error_details.get('retry_allowed', True)
                    }
                )
            else:
                raise HTTPException(status_code=400, detail=str(error_details))
        
        # Generate AI recommendations using our stored data
        recommendations = await recommendation_service.generate_recommendations(
            result['metrics'], 
            current_user.profile if hasattr(current_user, 'profile') else {}
        )
        
        return {
            'internal_analysis_id': result['internal_analysis_id'],
            'orbo_session_id': result.get('session_id'),
            'skin_metrics': result['metrics'],
            'recommendations': recommendations,
            'annotations': result.get('annotations', {}),
            'data_sovereignty_compliant': result['data_sovereignty_compliant'],
            'database_stored': result['database_stored']
        }
        
    except Exception as e:
        logger.error(f"Skin analysis with middleware error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/orbo/analysis/{internal_analysis_id}")
async def get_orbo_analysis_by_internal_id(
    internal_analysis_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Get analysis by our internal ID (not ORBO session ID)
    """
    try:
        analysis = db.skin_analyses.find_one({
            "analysis_id": internal_analysis_id,
            "user_id": str(current_user.id)
        })
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return {
            'analysis_id': analysis['analysis_id'],
            'status': analysis['status'],
            'skin_metrics': analysis.get('orbo_metrics', {}),
            'annotations': analysis.get('orbo_response', {}).get('annotations', {}),
            'internal_image_url': analysis['internal_image_url'],
            'created_at': analysis['created_at'],
            'data_sovereignty_compliant': analysis['data_sovereignty_compliant']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve analysis")

@router.get("/orbo/analysis/{analysis_id}/annotations")
async def get_orbo_analysis_annotations(
    analysis_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Get annotated images for specific ORBO analysis
    """
    try:
        analysis = db.skin_analyses.find_one({
            "analysis_id": analysis_id,
            "user_id": str(current_user.id)
        })
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        annotations = analysis.get('orbo_response', {}).get('annotations', {})
        
        return {
            'input_image': analysis.get('internal_image_url'),
            'annotations': annotations,
            'parameters': list(annotations.keys()) if annotations else []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve annotations")

# Development/Test endpoints
@router.post("/test/populate-sample-data", response_model=Dict[str, Any])
async def populate_sample_data(
    days_back: int = 14,
    photos_per_day: int = 1,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Populate sample skin analyses for testing purposes.
    Creates sample data across multiple days for streak calculation.
    
    WARNING: This is for development/testing only!
    """
    import random
    
    user_oid = ObjectId(str(current_user.id))
    created_count = 0
    
    # Create sample analyses for the past N days
    for day_offset in range(days_back):
        # Skip some days randomly to create realistic streaks
        if day_offset > 0 and random.random() < 0.1:  # 10% chance to skip a day
            continue
            
        for photo_num in range(photos_per_day):
            # Create timestamp for this analysis
            analysis_time = get_utc_now() - timedelta(days=day_offset, hours=random.randint(0, 23))
            
            # Generate realistic skin metrics
            base_score = random.uniform(70, 90)
            
            # Create sample ORBO metrics
            orbo_metrics = ORBOMetrics(
                overall_skin_health_score=base_score + random.uniform(-5, 5),
                hydration=base_score + random.uniform(-10, 10),
                smoothness=base_score + random.uniform(-8, 8),
                radiance=base_score + random.uniform(-7, 7),
                dark_spots=max(0, base_score + random.uniform(-15, 5)),
                firmness=base_score + random.uniform(-10, 10),
                fine_lines_wrinkles=max(0, base_score + random.uniform(-20, 10)),
                acne=max(0, 100 - base_score + random.uniform(-10, 10)),
                dark_circles=max(0, base_score + random.uniform(-15, 15)),
                redness=max(0, 100 - base_score + random.uniform(-5, 5))
            )
            
            # Create sample analysis
            analysis = {
                "user_id": user_oid,
                "image_url": f"https://example.com/sample-image-{day_offset}-{photo_num}.jpg",
                "thumbnail_url": f"https://example.com/sample-thumb-{day_offset}-{photo_num}.jpg",
                "is_baseline": day_offset == days_back - 1 and photo_num == 0,
                "tags": ["test", "sample"],
                "created_at": analysis_time,
                "updated_at": analysis_time,
                "analysis_data": {
                    "overall_skin_health_score": orbo_metrics.overall_skin_health_score,
                    "hydration": orbo_metrics.hydration,
                    "smoothness": orbo_metrics.smoothness,
                    "radiance": orbo_metrics.radiance,
                    "dark_spots": orbo_metrics.dark_spots,
                    "firmness": orbo_metrics.firmness,
                    "fine_lines_wrinkles": orbo_metrics.fine_lines_wrinkles,
                    "acne": orbo_metrics.acne,
                    "dark_circles": orbo_metrics.dark_circles,
                    "redness": orbo_metrics.redness
                },
                "orbo_metrics": orbo_metrics.dict(),
                "ai_feedback": {
                    "summary": f"Sample analysis from {day_offset} days ago",
                    "recommendations": [
                        "Keep up your skincare routine",
                        "Stay hydrated",
                        "Use sunscreen daily"
                    ]
                }
            }
            
            # Insert the analysis
            db.skin_analyses.insert_one(analysis)
            created_count += 1
            
            # Update achievements cache for this day
            day_start = datetime(
                analysis_time.year, 
                analysis_time.month, 
                analysis_time.day
            )
            
            # Update or create achievement record
            db.achievements.update_one(
                {
                    "user_id": user_oid,
                    "date": day_start
                },
                {
                    "$inc": {"photos_taken": 1},
                    "$set": {
                        "updated_at": get_utc_now(),
                        "last_analysis_id": str(analysis.get("_id", ""))
                    }
                },
                upsert=True
            )
    
    # Calculate current streak for verification
    today_start = get_utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = db.achievements.find(
        {"user_id": user_oid, "photos_taken": {"$gt": 0}}
    ).sort("date", -1)
    
    days_with_photos = [d.get("date") for d in cursor if isinstance(d.get("date"), datetime)]
    
    # Calculate streak
    streak = 0
    expected = today_start
    for d in days_with_photos:
        d0 = d.replace(hour=0, minute=0, second=0, microsecond=0)
        if d0 == expected:
            streak += 1
            expected = expected - timedelta(days=1)
        elif d0 < expected:
            break
    
    # Get total photos
    total_photos = db.skin_analyses.count_documents({"user_id": user_oid})
    
    return {
        "message": f"Successfully created {created_count} sample analyses",
        "total_photos": total_photos,
        "current_streak": streak,
        "days_covered": days_back,
        "user_id": str(current_user.id)
    }

@router.get("/calendar/insights", response_model=Dict[str, Any])
async def get_calendar_ai_insights(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database),
    tz_offset_minutes: int = 0,
):
    """Generate AI Calendar Insights based on reminders, analysis day, and smart schedule stats.
    Returns a small set of concise cards. Falls back to deterministic tips when OpenAI is not configured.
    """
    try:
        # Build context
        user_id = str(current_user.id)

        # Today window (tz-adjusted)
        now_utc = get_utc_now()
        def to_local_day(dt: datetime) -> datetime:
            local = dt + timedelta(minutes=tz_offset_minutes)
            local_midnight = datetime(local.year, local.month, local.day)
            return local_midnight - timedelta(minutes=tz_offset_minutes)
        today_start_utc = to_local_day(now_utc)
        today_end_utc = today_start_utc + timedelta(days=1)

        # Smart reminders today
        reminders = list(db.smart_reminders.find({
            "user_id": {"$in": [user_id, ObjectId(user_id)]},
            "scheduled_for": {"$gte": today_start_utc, "$lt": today_end_utc},
        }).limit(50)) if hasattr(db, 'smart_reminders') else []

        # Analysis done today?
        has_analysis_today = db.skin_analyses.count_documents({
            "user_id": {"$in": [user_id, ObjectId(user_id)]},
            "created_at": {"$gte": today_start_utc, "$lt": today_end_utc},
        }) > 0

        # Achievements/streak
        achievements = await achievements_summary(current_user=current_user, db=db, tz_offset_minutes=tz_offset_minutes)  # reuse logic

        # Compose minimal context
        context = {
            "today": {
                "analysis_done": has_analysis_today,
                "reminders_count": len(reminders),
                "reminder_categories": list({r.get("category", "general") for r in reminders}),
            },
            "smart_schedule": {
                "streak_current": achievements.get("streak_current", 0),
                "total_photos": achievements.get("total_photos", 0),
            }
        }

        # If OpenAI available, generate insights
        try:
            from app.core.config import settings as app_settings
            import openai as _openai
            if getattr(app_settings, 'OPENAI_API_KEY', ''):
                client = _openai.OpenAI(api_key=app_settings.OPENAI_API_KEY)
                prompt = (
                    "You are a concise skincare coach. Create 2-3 short 'AI Calendar Insights' for today's calendar, "
                    "using this JSON context. Focus on: 1) whether analysis was done today, 2) the number & type of reminders, "
                    "3) current streak. Each insight must be 1-2 sentences, actionable and encouraging. Respond as JSON: "
                    "{\"insights\":[{\"title\":string,\"body\":string,\"icon\":string}]}\n\nContext:\n" + json.dumps(context)
                )
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Return valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.6,
                    max_tokens=400,
                )
                raw = resp.choices[0].message.content or "{}"
                if raw.startswith("```"):
                    raw = raw.strip("` ")
                    raw = raw.replace("json", "")
                data = json.loads(raw)
                insights = data.get("insights")
                if isinstance(insights, list) and insights:
                    return {"insights": insights[:3], "source": "openai"}
        except Exception as e:
            logger.warning(f"AI Calendar Insights fallback: {e}")

        # Deterministic fallback
        fallback = []
        streak = context["smart_schedule"]["streak_current"]
        if context["today"]["analysis_done"]:
            fallback.append({
                "title": "Great job snapping progress",
                "body": "Today's analysis keeps your streak moving. Compare results to adjust your routine.",
                "icon": "insights"
            })
        if context["today"]["reminders_count"] > 0:
            fallback.append({
                "title": "Stay on track",
                "body": f"You have {context['today']['reminders_count']} reminder(s) today. Complete them to boost results.",
                "icon": "checklist"
            })
        if streak > 0:
            fallback.append({
                "title": "Consistency pays off",
                "body": f"You're on a {streak}-day streak—keep momentum for better long-term outcomes.",
                "icon": "trending_up"
            })
        if not fallback:
            fallback.append({
                "title": "Quick win for today",
                "body": "Take a progress photo or schedule a reminder to kickstart your momentum.",
                "icon": "bolt"
            })
        return {"insights": fallback[:3], "source": "fallback"}

    except Exception as e:
        logger.error(f"Calendar insights failed: {e}")
        return {"insights": [{"title": "Insights unavailable", "body": "Please try again later.", "icon": "warning"}], "source": "error"}
