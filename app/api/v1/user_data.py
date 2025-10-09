from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
import json
from typing import Any, Dict, List, Optional, Set, Tuple
from bson import ObjectId
from bson.errors import InvalidId
import io
import logging
from urllib.parse import urlparse

from ...database import get_database
from ..deps import get_current_user
from ...models.user import UserModel
from ...services.s3_service import s3_service

router = APIRouter(prefix="/user-data", tags=["user-data"])
logger = logging.getLogger(__name__)


def _build_user_identity(user_id: str) -> Tuple[Optional[ObjectId], List[Any]]:
    """Return ObjectId (if valid) and a list of acceptable identity variants."""
    variants: List[Any] = [user_id]
    user_oid: Optional[ObjectId] = None
    try:
        user_oid = ObjectId(user_id)
        variants.append(user_oid)
    except (InvalidId, TypeError):  # Support legacy string IDs
        user_oid = None
    return user_oid, variants

@router.get("/export")
async def export_user_data(
    current_user: UserModel = Depends(get_current_user)
) -> StreamingResponse:
    """
    Export all user data in JSON format.
    Includes profile, analyses, routines, goals, achievements, and more.
    """
    try:
        db = get_database()
        user_id = str(current_user.id)
        user_oid, user_id_variants = _build_user_identity(user_id)
        user_id_filter = {"$in": user_id_variants}
        
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
        user = db.users.find_one({"_id": {"$in": user_id_variants}})
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
        analyses = list(db.skin_analyses.find({"user_id": user_id_filter}))
        for analysis in analyses:
            analysis["_id"] = str(analysis["_id"])
            analysis["user_id"] = str(analysis["user_id"])
            if "created_at" in analysis and hasattr(analysis["created_at"], "isoformat"):
                analysis["created_at"] = analysis["created_at"].isoformat()
            if "updated_at" in analysis and hasattr(analysis["updated_at"], "isoformat"):
                analysis["updated_at"] = analysis["updated_at"].isoformat()
        export_data["skin_analyses"] = analyses
        
        # Get routines
        routines = list(db.routines.find({"user_id": user_id_filter}))
        for routine in routines:
            routine["_id"] = str(routine["_id"])
            routine["user_id"] = str(routine["user_id"])
            if "created_at" in routine and hasattr(routine["created_at"], "isoformat"):
                routine["created_at"] = routine["created_at"].isoformat()
            if "updated_at" in routine and hasattr(routine["updated_at"], "isoformat"):
                routine["updated_at"] = routine["updated_at"].isoformat()
        export_data["routines"] = routines
        
        # Get routine completions
        completions = list(db.routine_completions.find({"user_id": user_id_filter}))
        for completion in completions:
            completion["_id"] = str(completion["_id"])
            completion["user_id"] = str(completion["user_id"])
            completion["routine_id"] = str(completion["routine_id"])
            if "completed_at" in completion and hasattr(completion["completed_at"], "isoformat"):
                completion["completed_at"] = completion["completed_at"].isoformat()
        export_data["routine_completions"] = completions
        
        # Get goals
        goals = list(db.goals.find({"user_id": user_id_filter}))
        for goal in goals:
            goal["_id"] = str(goal["_id"])
            goal["user_id"] = str(goal["user_id"])
            if "created_at" in goal and hasattr(goal["created_at"], "isoformat"):
                goal["created_at"] = goal["created_at"].isoformat()
            if "target_date" in goal and hasattr(goal["target_date"], "isoformat"):
                goal["target_date"] = goal["target_date"].isoformat()
        export_data["goals"] = goals
        
        # Get user achievements
        achievements = list(db.user_achievements.find({"user_id": user_id_filter}))
        for achievement in achievements:
            achievement["_id"] = str(achievement["_id"])
            achievement["user_id"] = str(achievement["user_id"])
            if "unlocked_at" in achievement and hasattr(achievement["unlocked_at"], "isoformat"):
                achievement["unlocked_at"] = achievement["unlocked_at"].isoformat()
            if "created_at" in achievement and hasattr(achievement["created_at"], "isoformat"):
                achievement["created_at"] = achievement["created_at"].isoformat()
        export_data["achievements"] = achievements
        
        # Get user product interactions
        products = list(db.user_product_interactions.find({"user_id": user_id_filter}))
        for product in products:
            product["_id"] = str(product["_id"])
            product["user_id"] = str(product["user_id"])
            if "created_at" in product and hasattr(product["created_at"], "isoformat"):
                product["created_at"] = product["created_at"].isoformat()
        export_data["products"] = products
        
        # Get community posts (if exists)
        if db.list_collection_names(filter={"name": "community_posts"}):
            posts = list(db.community_posts.find({"user_id": user_id_filter}))
            for post in posts:
                post["_id"] = str(post["_id"])
                post["user_id"] = str(post["user_id"])
                if "created_at" in post and hasattr(post["created_at"], "isoformat"):
                    post["created_at"] = post["created_at"].isoformat()
            export_data["community_posts"] = posts
        
        # Get notification preferences
        if db.list_collection_names(filter={"name": "notification_preferences"}):
            notif_prefs = db.notification_preferences.find_one({"user_id": user_id_filter})
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
    current_user: UserModel = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a summary of what data will be exported.
    """
    try:
        db = get_database()
        user_id = str(current_user.id)
        user_oid, user_id_variants = _build_user_identity(user_id)
        user_id_filter = {"$in": user_id_variants}

        summary = {
            "profile_data": bool(db.users.find_one({"_id": {"$in": user_id_variants}})),
            "skin_analyses_count": db.skin_analyses.count_documents({"user_id": user_id_filter}),
            "routines_count": db.routines.count_documents({"user_id": user_id_filter}),
            "routine_completions_count": db.routine_completions.count_documents({"user_id": user_id_filter}),
            "goals_count": db.goals.count_documents({"user_id": user_id_filter}),
            "achievements_count": db.user_achievements.count_documents({"user_id": user_id_filter}),
            "product_interactions_count": db.user_product_interactions.count_documents({"user_id": user_id_filter}),
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

@router.delete("/images")
async def delete_user_images(
    current_user: UserModel = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Permanently delete all user-owned images (skin analyses, community posts, profile avatars) from S3 storage.
    Clears database references regardless of S3 availability.
    """
    db = get_database()
    user_id = str(current_user.id)
    user_oid, user_id_variants = _build_user_identity(user_id)
    user_identity_filter = {"$in": user_id_variants}

    image_urls: Set[str] = set()
    external_image_urls: Set[str] = set()

    def is_external_provider_url(url: str) -> bool:
        """Check if URL belongs to a third-party provider we need to unlink."""
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            return False
        if not host:
            return False
        external_domains = (
            "orbo.ai",
        )
        return any(host.endswith(domain) for domain in external_domains)

    def collect_url(value: Any) -> bool:
        """Add URL to deletion set if it's managed by our storage."""
        if not isinstance(value, str):
            return False
        url = value.strip()
        if not url:
            return False
        if s3_service.is_managed_url(url):
            image_urls.add(url)
            return True
        if is_external_provider_url(url):
            external_image_urls.add(url)
            return True
        return False

    try:
        # Gather analysis images (full-size, thumbnails, any internal copies)
        analyses_cursor = db.skin_analyses.find(
            {
                "user_id": user_identity_filter
            },
            {
                "image_url": 1,
                "thumbnail_url": 1,
                "internal_image_url": 1,
            }
        )
        for analysis in analyses_cursor:
            collect_url(analysis.get("image_url"))
            collect_url(analysis.get("thumbnail_url"))
            collect_url(analysis.get("internal_image_url"))

        # Gather community post images
        posts_cursor = db.community_posts.find(
            {
                "user_id": user_identity_filter
            },
            {"image_url": 1}
        )
        for post in posts_cursor:
            collect_url(post.get("image_url"))

        # Gather profile images
        user_document = db.users.find_one(
            {"_id": {"$in": user_id_variants}},
            {"profile.avatar_url": 1, "profile_image": 1}
        )
        user_updates: Dict[str, Any] = {}
        cleared_profile_fields: List[str] = []

        if user_document:
            if collect_url(user_document.get("profile_image")):
                user_updates["profile_image"] = None
                cleared_profile_fields.append("profile_image")

            profile_data = user_document.get("profile")
            if isinstance(profile_data, dict) and collect_url(profile_data.get("avatar_url")):
                user_updates["profile.avatar_url"] = None
                cleared_profile_fields.append("profile.avatar_url")
        else:
            cleared_profile_fields = []

        # Delete from S3 if configured
        deleted_count = 0
        failed_urls: List[str] = []
        if image_urls and s3_service.has_s3_config:
            for url in image_urls:
                try:
                    deleted = await s3_service.delete_image(url)
                    if deleted:
                        deleted_count += 1
                    else:
                        failed_urls.append(url)
                except Exception as exc:
                    logger.error("Failed to delete image '%s': %s", url, exc)
                    failed_urls.append(url)
        elif image_urls and not s3_service.has_s3_config:
            logger.warning(
                "S3 configuration missing while attempting to delete images for user %s. Only references will be cleared.",
                user_id,
            )

        # Clear analysis references for the images we attempted to delete
        urls_list: List[str] = list(image_urls.union(external_image_urls))
        analysis_updates = 0
        if urls_list:
            analysis_filter = {
                "user_id": user_identity_filter,
                "$or": [
                    {"image_url": {"$in": urls_list}},
                    {"thumbnail_url": {"$in": urls_list}},
                    {"internal_image_url": {"$in": urls_list}},
                ],
            }
            analysis_update_result = db.skin_analyses.update_many(
                analysis_filter,
                {
                    "$set": {
                        "image_url": None,
                        "thumbnail_url": None,
                    },
                    "$unset": {
                        "internal_image_url": "",
                    },
                },
            )
            analysis_updates = analysis_update_result.modified_count

        # Clear community post image references
        community_updates = 0
        if urls_list:
            community_update_result = db.community_posts.update_many(
                {
                    "user_id": user_identity_filter,
                    "image_url": {"$in": urls_list},
                },
                {"$set": {"image_url": None}},
            )
            community_updates = community_update_result.modified_count

        # Update user profile document if necessary
        if user_updates:
            db.users.update_one({"_id": {"$in": user_id_variants}}, {"$set": user_updates})

        # Prepare response payload
        status = "success"
        message = "All images removed from storage."

        total_identified = len(image_urls) + len(external_image_urls)
        if total_identified == 0:
            status = "nothing_to_delete"
            message = (
                "No user images were found. If your glow timeline still shows old data, "
                "try signing out and back in before taking new photos."
            )
        elif failed_urls:
            status = "partial_success"
            message = (
                "Image references were cleared, but some files could not be removed from storage. "
                "To refresh your glow timeline, sign out and back in, then capture new photos."
            )
        elif image_urls and not s3_service.has_s3_config:
            status = "references_cleared"
            message = (
                "Storage not configured; cleared saved references only. "
                "Please sign out and back in before taking new photos to rebuild your glow timeline."
            )
        elif image_urls and external_image_urls:
            status = "success"
            message = (
                "Managed images deleted and external links cleared. "
                "Sign out and back in, then take new photos to rebuild your glow timeline."
            )
        elif image_urls:
            status = "success"
            message = (
                "All images removed from storage. "
                "Sign out and back in, then take new photos to rebuild your glow timeline."
            )
        else:
            status = "references_cleared"
            message = (
                "External provider images were unlinked from your account. They will no longer appear in SkinSense. "
                "Sign out and back in before taking new photos to rebuild your glow timeline."
            )

        return {
            "status": status,
            "message": message,
            "data": {
                "images_identified": total_identified,
                "images_deleted": deleted_count,
                "images_failed": len(failed_urls),
                "external_images_identified": len(external_image_urls),
                "analysis_records_updated": analysis_updates,
                "community_posts_updated": community_updates,
                "profile_fields_cleared": cleared_profile_fields,
            },
        }

    except Exception as e:
        logger.exception("Failed to delete user images for user %s", user_id)
        raise HTTPException(status_code=500, detail=f"Failed to delete images: {str(e)}")
