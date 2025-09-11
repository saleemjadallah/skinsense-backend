from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
import json
from typing import Any, Dict
from bson import ObjectId
import io

from app.core.database import get_database
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/user-data", tags=["user-data"])

@router.get("/export")
async def export_user_data(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database)
) -> StreamingResponse:
    """
    Export all user data in JSON format.
    Includes profile, analyses, routines, goals, achievements, and more.
    """
    try:
        user_id = current_user["_id"]
        user_oid = ObjectId(user_id)
        
        # Prepare the export data
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "user_profile": {},
            "skin_analyses": [],
            "routines": [],
            "routine_completions": [],
            "goals": [],
            "achievements": [],
            "products": [],
            "community_posts": [],
            "notifications": []
        }
        
        # Get user profile (exclude sensitive data)
        user = db.users.find_one({"_id": user_oid})
        if user:
            # Remove sensitive fields
            user.pop("password_hash", None)
            user.pop("_id", None)
            user.pop("verification_token", None)
            user.pop("reset_password_token", None)
            
            # Convert ObjectId to string for JSON serialization
            if "created_at" in user and hasattr(user["created_at"], "isoformat"):
                user["created_at"] = user["created_at"].isoformat()
            if "updated_at" in user and hasattr(user["updated_at"], "isoformat"):
                user["updated_at"] = user["updated_at"].isoformat()
            
            export_data["user_profile"] = user
        
        # Get skin analyses
        analyses = list(db.skin_analyses.find({"user_id": user_oid}))
        for analysis in analyses:
            analysis["_id"] = str(analysis["_id"])
            analysis["user_id"] = str(analysis["user_id"])
            if "created_at" in analysis and hasattr(analysis["created_at"], "isoformat"):
                analysis["created_at"] = analysis["created_at"].isoformat()
            if "updated_at" in analysis and hasattr(analysis["updated_at"], "isoformat"):
                analysis["updated_at"] = analysis["updated_at"].isoformat()
        export_data["skin_analyses"] = analyses
        
        # Get routines
        routines = list(db.routines.find({"user_id": user_oid}))
        for routine in routines:
            routine["_id"] = str(routine["_id"])
            routine["user_id"] = str(routine["user_id"])
            if "created_at" in routine and hasattr(routine["created_at"], "isoformat"):
                routine["created_at"] = routine["created_at"].isoformat()
            if "updated_at" in routine and hasattr(routine["updated_at"], "isoformat"):
                routine["updated_at"] = routine["updated_at"].isoformat()
        export_data["routines"] = routines
        
        # Get routine completions
        completions = list(db.routine_completions.find({"user_id": user_oid}))
        for completion in completions:
            completion["_id"] = str(completion["_id"])
            completion["user_id"] = str(completion["user_id"])
            completion["routine_id"] = str(completion["routine_id"])
            if "completed_at" in completion and hasattr(completion["completed_at"], "isoformat"):
                completion["completed_at"] = completion["completed_at"].isoformat()
        export_data["routine_completions"] = completions
        
        # Get goals
        goals = list(db.goals.find({"user_id": user_oid}))
        for goal in goals:
            goal["_id"] = str(goal["_id"])
            goal["user_id"] = str(goal["user_id"])
            if "created_at" in goal and hasattr(goal["created_at"], "isoformat"):
                goal["created_at"] = goal["created_at"].isoformat()
            if "target_date" in goal and hasattr(goal["target_date"], "isoformat"):
                goal["target_date"] = goal["target_date"].isoformat()
        export_data["goals"] = goals
        
        # Get user achievements
        achievements = list(db.user_achievements.find({"user_id": user_oid}))
        for achievement in achievements:
            achievement["_id"] = str(achievement["_id"])
            achievement["user_id"] = str(achievement["user_id"])
            if "unlocked_at" in achievement and hasattr(achievement["unlocked_at"], "isoformat"):
                achievement["unlocked_at"] = achievement["unlocked_at"].isoformat()
            if "created_at" in achievement and hasattr(achievement["created_at"], "isoformat"):
                achievement["created_at"] = achievement["created_at"].isoformat()
        export_data["achievements"] = achievements
        
        # Get user product interactions
        products = list(db.user_product_interactions.find({"user_id": user_oid}))
        for product in products:
            product["_id"] = str(product["_id"])
            product["user_id"] = str(product["user_id"])
            if "created_at" in product and hasattr(product["created_at"], "isoformat"):
                product["created_at"] = product["created_at"].isoformat()
        export_data["products"] = products
        
        # Get community posts (if exists)
        if db.list_collection_names(filter={"name": "community_posts"}):
            posts = list(db.community_posts.find({"user_id": user_oid}))
            for post in posts:
                post["_id"] = str(post["_id"])
                post["user_id"] = str(post["user_id"])
                if "created_at" in post and hasattr(post["created_at"], "isoformat"):
                    post["created_at"] = post["created_at"].isoformat()
            export_data["community_posts"] = posts
        
        # Get notification preferences
        if db.list_collection_names(filter={"name": "notification_preferences"}):
            notif_prefs = db.notification_preferences.find_one({"user_id": user_oid})
            if notif_prefs:
                notif_prefs["_id"] = str(notif_prefs["_id"])
                notif_prefs["user_id"] = str(notif_prefs["user_id"])
                export_data["notification_preferences"] = notif_prefs
        
        # Convert to JSON with pretty formatting
        json_data = json.dumps(export_data, indent=2, default=str)
        
        # Create a file-like object from the JSON string
        file_like = io.BytesIO(json_data.encode())
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"skinsense_data_export_{timestamp}.json"
        
        return StreamingResponse(
            file_like,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export data: {str(e)}")

@router.get("/export/summary")
async def get_export_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database)
) -> Dict[str, Any]:
    """
    Get a summary of what data will be exported.
    """
    try:
        user_id = current_user["_id"]
        user_oid = ObjectId(user_id)
        
        summary = {
            "profile_data": bool(db.users.find_one({"_id": user_oid})),
            "skin_analyses_count": db.skin_analyses.count_documents({"user_id": user_oid}),
            "routines_count": db.routines.count_documents({"user_id": user_oid}),
            "routine_completions_count": db.routine_completions.count_documents({"user_id": user_oid}),
            "goals_count": db.goals.count_documents({"user_id": user_oid}),
            "achievements_count": db.user_achievements.count_documents({"user_id": user_oid}),
            "product_interactions_count": db.user_product_interactions.count_documents({"user_id": user_oid}),
            "estimated_size_kb": 0
        }
        
        # Estimate size (rough calculation)
        estimated_size = (
            1 +  # profile
            summary["skin_analyses_count"] * 5 +  # ~5KB per analysis
            summary["routines_count"] * 2 +  # ~2KB per routine
            summary["goals_count"] * 1 +  # ~1KB per goal
            summary["achievements_count"] * 0.5 +  # ~0.5KB per achievement
            summary["product_interactions_count"] * 0.5  # ~0.5KB per interaction
        )
        summary["estimated_size_kb"] = round(estimated_size, 1)
        
        return {
            "status": "success",
            "data": summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get export summary: {str(e)}")