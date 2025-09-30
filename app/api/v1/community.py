from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, File, UploadFile
from pymongo.database import Database
from typing import List, Optional, Any
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database import get_database
from app.api.deps import get_current_active_user
from app.core.cache import cache_service
from app.models.user import UserModel
from app.models.community import CommunityPost, Comment, PostInteraction
from app.schemas.community import (
    PostCreate, PostUpdate, PostResponse, PostListResponse,
    CommentCreate, CommentUpdate, CommentResponse,
    LikeResponse, SaveResponse, PostStats, UserProfile
)
from app.services.s3_service import s3_service
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_user_profile(user_id: Any, db: Database, is_anonymous: bool = False) -> UserProfile:
    """Get user profile info for posts/comments"""
    if is_anonymous:
        return UserProfile(
            id="anonymous",
            username="Anonymous User",
            profile_image=None,
            is_expert=False,
            expert_title=None,
            is_anonymous=True
        )

    user = db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use existing name or username (prefer name for display)
    username = user.get("username")
    display_name = user.get("name")

    # Use name if available, otherwise fall back to username or generate one
    if display_name:
        username = display_name  # Use the actual name for display
    elif not username:
        # Generate username from email if both name and username are missing
        if user.get("email"):
            username = user["email"].split("@")[0]
        else:
            username = f"user_{str(user_id)[-8:]}"

        # Update the user document with the generated username
        db.users.update_one(
            {"_id": user_id},
            {"$set": {"username": username}}
        )
        logger.info(f"Generated username '{username}' for user {user_id}")

    # Check if user is an expert
    expert = db.expert_profiles.find_one({"user_id": user_id})

    return UserProfile(
        id=str(user_id),
        username=username,
        profile_image=user.get("profile_image"),
        is_expert=expert is not None,
        expert_title=expert.get("title") if expert else None,
        is_anonymous=False
    )


def get_post_interactions(post_id: Any, user_id: Any, db: Database) -> dict:
    """Get user's interactions with a post"""
    post = db.community_posts.find_one({"_id": post_id})
    if not post:
        return {"is_liked": False, "is_saved": False}
    
    return {
        "is_liked": user_id in post.get("likes", []),
        "is_saved": user_id in post.get("saves", [])
    }


@router.post("/posts/json", response_model=PostResponse)
async def create_post_json(
    post_data: PostCreate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Create a new community post (JSON version without image support)"""
    
    # Check if user can post (premium only)
    if not SubscriptionService.can_post_community(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Community posting is a premium feature",
                "upgrade_prompt": "Upgrade to Premium to share your skincare journey and connect with the community!"
            }
        )
    
    try:
        # Log incoming post data
        logger.info(f"Creating post - User: {current_user.id}, Content: '{post_data.content[:50]}...', Anonymous: {post_data.is_anonymous}")

        # Create post document
        post = CommunityPost(
            user_id=current_user.id,
            content=post_data.content,
            image_url=post_data.image_url,
            tags=post_data.tags,
            post_type=post_data.post_type,
            is_anonymous=post_data.is_anonymous
        )

        # Insert into database, letting MongoDB generate the _id
        post_document = post.model_dump(by_alias=True, exclude_none=True)
        result = db.community_posts.insert_one(post_document)
        post.id = result.inserted_id

        logger.info(f"Post created with ID: {post.id}")

        # Get user profile (handle anonymous)
        user_profile = get_user_profile(current_user.id, db, is_anonymous=post.is_anonymous)

        logger.info(f"User profile retrieved - Username: {user_profile.username}, Anonymous: {user_profile.is_anonymous}")

        # Invalidate cached community data
        cache_service.invalidate_prefix("community_posts")
        cache_service.invalidate_prefix("community_stats")

        # Return response
        return PostResponse(
            id=str(post.id),
            user=user_profile,
            content=post.content,
            image_url=post.image_url,
            tags=post.tags,
            post_type=post.post_type,
            created_at=post.created_at,
            likes_count=0,
            comments_count=0,
            saves_count=0,
            is_liked=False,
            is_saved=False
        )
        
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")


@router.post("/posts", response_model=PostResponse)
async def create_post(
    content: str = Form(...),
    post_type: str = Form("post"),
    is_anonymous: str = Form("false"),
    tags: List[str] = Form(default=[]),
    images: Optional[List[UploadFile]] = File(None),
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Create a new community post with optional image uploads"""

    # Debug logging for incoming request
    logger.info("=" * 60)
    logger.info("CREATE POST ENDPOINT CALLED (FormData)")
    logger.info(f"User: {current_user.email} (ID: {current_user.id})")
    logger.info(f"Content length: {len(content)} chars")
    logger.info(f"Images param type: {type(images)}")
    logger.info(f"Images param value: {images}")
    logger.info(f"Images is None: {images is None}")
    if images:
        logger.info(f"Number of images received: {len(images)}")
        for i, img in enumerate(images):
            if img and img.filename:
                logger.info(f"Image {i}: filename={img.filename}, content_type={img.content_type}")
            else:
                logger.info(f"Image {i}: empty or invalid")
    else:
        logger.info("No images in request (images is None or empty)")
    logger.info("=" * 60)

    # Check if user can post (premium only)
    if not SubscriptionService.can_post_community(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Community posting is a premium feature",
                "upgrade_prompt": "Upgrade to Premium to share your skincare journey and connect with the community!"
            }
        )

    try:
        # Parse is_anonymous from string to boolean
        is_anonymous_bool = is_anonymous.lower() == "true"

        # Log incoming form data
        logger.info(f"Creating post (FormData) - User: {current_user.id}, Content: '{content[:50]}...', Anonymous: {is_anonymous_bool}")

        # Parse tags if they come as a single string
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
        elif not tags:
            tags = []

        # Handle image upload if provided
        image_url = None

        if images and len(images) > 0:
            first_image = images[0]
            logger.info(f"Processing first image: filename={first_image.filename if first_image else 'None'}")

            # Check if the image has actual content (not just an empty upload field)
            if first_image and first_image.filename and first_image.filename.strip():
                try:
                    # Read image content
                    file_content = await first_image.read()
                    logger.info(f"Image file size: {len(file_content)} bytes")

                    # Only proceed if we have actual image data
                    if len(file_content) > 0:
                        try:
                            image_url = await s3_service.upload_community_image(
                                file_content,
                                first_image.filename,
                                f"community/{current_user.id}"
                            )
                            logger.info(f"✅ Image uploaded successfully to: {image_url}")

                            # Check if S3 was disabled (placeholder URL)
                            if image_url and image_url.startswith("s3-disabled://"):
                                logger.warning("⚠️ S3 is not configured - image upload skipped")
                                image_url = None  # Don't save placeholder URLs
                        except Exception as upload_error:
                            logger.error(f"❌ S3 upload error: {upload_error}")
                            logger.error(f"Error details: {str(upload_error)}")
                            # Continue without image rather than failing the entire post
                            image_url = None
                    else:
                        logger.warning("⚠️ Image file is empty (0 bytes)")
                except Exception as image_error:
                    logger.error(f"❌ Error reading image file: {image_error}")
                    image_url = None
            else:
                logger.info("ℹ️ No valid image filename provided")
        else:
            logger.info("ℹ️ No images provided in the request")

        # Create post document
        logger.info(f"Creating post document with image_url: {image_url}")
        post = CommunityPost(
            user_id=current_user.id,
            content=content,
            image_url=image_url,
            tags=tags,
            post_type=post_type,
            is_anonymous=is_anonymous_bool
        )

        # Insert into database, letting MongoDB generate the _id
        post_document = post.model_dump(by_alias=True, exclude_none=True)
        logger.info(f"Post document to insert: {post_document}")
        result = db.community_posts.insert_one(post_document)
        post.id = result.inserted_id

        logger.info(f"Post created successfully with ID: {post.id}, image_url: {image_url}")

        # Get user profile (handle anonymous)
        user_profile = get_user_profile(current_user.id, db, is_anonymous=post.is_anonymous)

        logger.info(f"User profile retrieved - Username: {user_profile.username}, Anonymous: {user_profile.is_anonymous}")

        # Invalidate cached community data
        cache_service.invalidate_prefix("community_posts")
        cache_service.invalidate_prefix("community_stats")

        # Return response
        return PostResponse(
            id=str(post.id),
            user=user_profile,
            content=post.content,
            image_url=post.image_url,
            tags=post.tags,
            post_type=post.post_type,
            created_at=post.created_at,
            likes_count=0,
            comments_count=0,
            saves_count=0,
            is_liked=False,
            is_saved=False
        )
        
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")


@router.get("/posts", response_model=PostListResponse)
async def get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    post_type: Optional[str] = None,
    tag: Optional[str] = None,
    trending: bool = False,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get community posts with filters"""
    cache_identifier = (
        f"skip={skip}|limit={limit}|type={post_type or 'all'}|"
        f"tag={tag or 'all'}|trending={'1' if trending else '0'}"
    )
    user_id_str = str(current_user.id)

    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Unable to parse datetime '{value}' from cache")
                return None

    try:
        cached_payload = cache_service.get("community_posts", cache_identifier)
        if cached_payload:
            post_responses = []
            for cached_post in cached_payload.get("posts", []):
                user_profile = UserProfile(**cached_post["user"])
                likes_user_ids = cached_post.get("likes_user_ids", [])
                saves_user_ids = cached_post.get("saves_user_ids", [])

                top_comments = []
                for cached_comment in cached_post.get("top_comments", []):
                    comment_user = UserProfile(**cached_comment["user"])
                    top_comments.append(CommentResponse(
                        id=cached_comment["id"],
                        post_id=cached_comment.get("post_id", cached_post["id"]),
                        user=comment_user,
                        content=cached_comment["content"],
                        parent_comment_id=cached_comment.get("parent_comment_id"),
                        replies_count=cached_comment.get("replies_count", 0),
                        likes_count=cached_comment.get("likes_count", 0),
                        is_liked=user_id_str in cached_comment.get("likes_user_ids", []),
                        created_at=_parse_datetime(cached_comment.get("created_at")) or datetime.utcnow(),
                        updated_at=_parse_datetime(cached_comment.get("updated_at")),
                        is_edited=cached_comment.get("is_edited", False)
                    ))

                post_responses.append(PostResponse(
                    id=cached_post["id"],
                    user=user_profile,
                    content=cached_post.get("content", ""),
                    image_url=cached_post.get("image_url"),
                    tags=cached_post.get("tags", []),
                    post_type=cached_post.get("post_type", "post"),
                    likes_count=cached_post.get("likes_count", 0),
                    comments_count=cached_post.get("comments_count", 0),
                    saves_count=cached_post.get("saves_count", 0),
                    is_liked=user_id_str in likes_user_ids,
                    is_saved=user_id_str in saves_user_ids,
                    created_at=_parse_datetime(cached_post.get("created_at")) or datetime.utcnow(),
                    updated_at=_parse_datetime(cached_post.get("updated_at")),
                    is_edited=cached_post.get("is_edited", False),
                    top_comments=top_comments
                ))

            logger.debug(f"Serving community posts from cache key {cache_identifier}")
            return PostListResponse(
                posts=post_responses,
                total=cached_payload.get("total", 0),
                skip=cached_payload.get("skip", skip),
                limit=cached_payload.get("limit", limit),
                has_more=cached_payload.get("has_more", False)
            )
    except Exception as cache_error:
        logger.warning(f"Failed to load community posts from cache: {cache_error}")

    try:
        # Build query
        query = {"is_active": True}
        if post_type:
            query["post_type"] = post_type
        if tag:
            query["tags"] = tag
        
        # Sort order
        if trending:
            # Sort by engagement (likes + comments) and recency
            sort = [("likes_count", -1), ("comments_count", -1), ("created_at", -1)]
        else:
            sort = [("created_at", -1)]
        
        # Get posts (convert cursor to list)
        posts = list(db.community_posts.find(query).sort(sort).skip(skip).limit(limit))
        total = db.community_posts.count_documents(query)
        
        # Transform posts
        post_responses = []
        cache_posts = []
        for post in posts:
            # Get user profile (handle anonymous)
            user_profile = get_user_profile(post["user_id"], db, is_anonymous=post.get("is_anonymous", False))
            
            # Get interactions
            interactions = get_post_interactions(post["_id"], current_user.id, db)
            
            # Get top 2 comments
            top_comments = []
            top_comments_cache = []
            comments = list(db.comments.find(
                {"post_id": post["_id"], "is_active": True}
            ).sort([("likes", -1), ("created_at", -1)]).limit(2))
            
            for comment in comments:
                comment_user = get_user_profile(comment["user_id"], db)
                comment_likes = comment.get("likes", [])
                is_comment_liked = current_user.id in comment_likes
                top_comments.append(CommentResponse(
                    id=str(comment["_id"]),
                    post_id=str(post["_id"]),
                    user=comment_user,
                    content=comment["content"],
                    parent_comment_id=str(comment.get("parent_comment_id")) if comment.get("parent_comment_id") else None,
                    replies_count=comment.get("replies_count", 0),
                    likes_count=len(comment_likes),
                    is_liked=is_comment_liked,
                    created_at=comment["created_at"],
                    updated_at=comment.get("updated_at"),
                    is_edited=comment.get("is_edited", False)
                ))
                top_comments_cache.append({
                    "id": str(comment["_id"]),
                    "post_id": str(post["_id"]),
                    "user": comment_user.model_dump(),
                    "content": comment["content"],
                    "parent_comment_id": str(comment.get("parent_comment_id")) if comment.get("parent_comment_id") else None,
                    "replies_count": comment.get("replies_count", 0),
                    "likes_count": len(comment_likes),
                    "likes_user_ids": [str(uid) for uid in comment_likes],
                    "created_at": comment["created_at"].isoformat(),
                    "updated_at": comment.get("updated_at").isoformat() if comment.get("updated_at") else None,
                    "is_edited": comment.get("is_edited", False)
                })
            
            # Log post data being returned
            logger.debug(f"Returning post {post['_id']}: username='{user_profile.username}', content='{post.get('content', '')[:50]}...', anonymous={post.get('is_anonymous', False)}")

            post_responses.append(PostResponse(
                id=str(post["_id"]),
                user=user_profile,
                content=post.get("content", ""),  # Ensure content is never None
                image_url=post.get("image_url"),
                tags=post.get("tags", []),
                post_type=post.get("post_type", "post"),
                likes_count=len(post.get("likes", [])),
                comments_count=post.get("comments_count", 0),
                saves_count=len(post.get("saves", [])),
                is_liked=interactions["is_liked"],
                is_saved=interactions["is_saved"],
                created_at=post["created_at"],
                updated_at=post.get("updated_at"),
                is_edited=post.get("is_edited", False),
                top_comments=top_comments
            ))

            cache_posts.append({
                "id": str(post["_id"]),
                "user": user_profile.model_dump(),
                "content": post.get("content", ""),
                "image_url": post.get("image_url"),
                "tags": post.get("tags", []),
                "post_type": post.get("post_type", "post"),
                "likes_count": len(post.get("likes", [])),
                "comments_count": post.get("comments_count", 0),
                "saves_count": len(post.get("saves", [])),
                "likes_user_ids": [str(uid) for uid in post.get("likes", [])],
                "saves_user_ids": [str(uid) for uid in post.get("saves", [])],
                "created_at": post["created_at"].isoformat(),
                "updated_at": post.get("updated_at").isoformat() if post.get("updated_at") else None,
                "is_edited": post.get("is_edited", False),
                "top_comments": top_comments_cache
            })
        
        cache_payload = {
            "posts": cache_posts,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total
        }
        cache_service.set("community_posts", cache_identifier, cache_payload, ttl_seconds=180)

        return PostListResponse(
            posts=post_responses,
            total=total,
            skip=skip,
            limit=limit,
            has_more=cache_payload["has_more"]
        )
        
    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts")


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get a single post by ID"""
    try:
        post = db.community_posts.find_one({"_id": ObjectId(post_id), "is_active": True})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Get user profile
        user_profile = get_user_profile(post["user_id"], db)
        
        # Get interactions
        interactions = get_post_interactions(post["_id"], current_user.id, db)
        
        # Get top comments
        top_comments = []
        comments = list(db.comments.find(
            {"post_id": post["_id"], "is_active": True}
        ).sort([("likes", -1), ("created_at", -1)]).limit(3))
        
        for comment in comments:
            comment_user = get_user_profile(comment["user_id"], db)
            top_comments.append(CommentResponse(
                id=str(comment["_id"]),
                post_id=str(post["_id"]),
                user=comment_user,
                content=comment["content"],
                likes_count=len(comment.get("likes", [])),
                is_liked=current_user.id in comment.get("likes", []),
                created_at=comment["created_at"],
                updated_at=comment.get("updated_at"),
                is_edited=comment.get("is_edited", False)
            ))
        
        return PostResponse(
            id=str(post["_id"]),
            user=user_profile,
            content=post["content"],
            image_url=post.get("image_url"),
            tags=post.get("tags", []),
            post_type=post["post_type"],
            likes_count=len(post.get("likes", [])),
            comments_count=post.get("comments_count", 0),
            saves_count=len(post.get("saves", [])),
            is_liked=interactions["is_liked"],
            is_saved=interactions["is_saved"],
            created_at=post["created_at"],
            updated_at=post.get("updated_at"),
            is_edited=post.get("is_edited", False),
            top_comments=top_comments
        )
        
    except Exception as e:
        logger.error(f"Error getting post: {e}")
        raise HTTPException(status_code=500, detail="Failed to get post")


@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    update_data: PostUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Update a post (only by creator)"""
    try:
        # Get post
        post = db.community_posts.find_one({"_id": ObjectId(post_id)})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Check ownership
        if post["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this post")
        
        # Update fields
        update_dict = {}
        if update_data.content is not None:
            update_dict["content"] = update_data.content
        if update_data.tags is not None:
            update_dict["tags"] = update_data.tags
        
        if update_dict:
            update_dict["updated_at"] = datetime.utcnow()
            update_dict["is_edited"] = True
            
            db.community_posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": update_dict}
            )
            cache_service.invalidate_prefix("community_posts")
            cache_service.invalidate_prefix("community_stats")
        
        # Return updated post
        return get_post(post_id, current_user, db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating post: {e}")
        raise HTTPException(status_code=500, detail="Failed to update post")


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Delete a post (soft delete)"""
    try:
        # Get post
        post = db.community_posts.find_one({"_id": ObjectId(post_id)})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Check ownership
        if post["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this post")
        
        # Soft delete
        db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        cache_service.invalidate_prefix("community_posts")
        cache_service.invalidate_prefix("community_stats")
        
        return {"message": "Post deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting post: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete post")


@router.post("/posts/{post_id}/like", response_model=LikeResponse)
async def toggle_like_post(
    post_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Like or unlike a post"""
    try:
        post = db.community_posts.find_one({"_id": ObjectId(post_id), "is_active": True})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        likes = post.get("likes", [])
        
        if current_user.id in likes:
            # Unlike
            likes.remove(current_user.id)
            is_liked = False
        else:
            # Like
            likes.append(current_user.id)
            is_liked = True
            
            # Track interaction
            db.post_interactions.insert_one({
                "user_id": current_user.id,
                "post_id": ObjectId(post_id),
                "interaction_type": "like",
                "created_at": datetime.utcnow()
            })
        
        # Update post
        db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"likes": likes}}
        )
        cache_service.invalidate_prefix("community_posts")
        
        return LikeResponse(
            success=True,
            likes_count=len(likes),
            is_liked=is_liked
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling like: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle like")


@router.post("/posts/{post_id}/save", response_model=SaveResponse)
async def toggle_save_post(
    post_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Save or unsave a post"""
    try:
        post = db.community_posts.find_one({"_id": ObjectId(post_id), "is_active": True})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        saves = post.get("saves", [])
        
        if current_user.id in saves:
            # Unsave
            saves.remove(current_user.id)
            is_saved = False
        else:
            # Save
            saves.append(current_user.id)
            is_saved = True
            
            # Track interaction
            db.post_interactions.insert_one({
                "user_id": current_user.id,
                "post_id": ObjectId(post_id),
                "interaction_type": "save",
                "created_at": datetime.utcnow()
            })
        
        # Update post
        db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"saves": saves}}
        )
        cache_service.invalidate_prefix("community_posts")
        
        return SaveResponse(
            success=True,
            saves_count=len(saves),
            is_saved=is_saved
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling save: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle save")


@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
async def create_comment(
    post_id: str,
    comment_data: CommentCreate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Create a comment on a post"""
    
    # Check if user can comment (premium only)
    if not SubscriptionService.can_post_community(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Commenting is a premium feature",
                "upgrade_prompt": "Upgrade to Premium to engage with the community!"
            }
        )
    
    try:
        # Verify post exists
        post = db.community_posts.find_one({"_id": ObjectId(post_id), "is_active": True})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Create comment
        comment = Comment(
            post_id=ObjectId(post_id),
            user_id=current_user.id,
            content=comment_data.content,
            parent_comment_id=ObjectId(comment_data.parent_comment_id) if comment_data.parent_comment_id else None
        )
        
        # Insert comment
        comment_document = comment.model_dump(by_alias=True, exclude_none=True)
        result = db.comments.insert_one(comment_document)
        comment.id = result.inserted_id
        
        # Update post comment count
        db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"comments_count": 1}}
        )
        
        # If reply, update parent comment's reply count
        if comment.parent_comment_id:
            db.comments.update_one(
                {"_id": comment.parent_comment_id},
                {"$inc": {"replies_count": 1}}
            )
        
        cache_service.invalidate_prefix("community_posts")

        # Get user profile
        user_profile = get_user_profile(current_user.id, db)
        
        return CommentResponse(
            id=str(comment.id),
            post_id=post_id,
            user=user_profile,
            content=comment.content,
            parent_comment_id=comment_data.parent_comment_id,
            likes_count=0,
            is_liked=False,
            created_at=comment.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating comment: {e}")
        raise HTTPException(status_code=500, detail="Failed to create comment")


@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_comments(
    post_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get comments for a post"""
    try:
        # Get top-level comments (no parent)
        comments = list(db.comments.find(
            {"post_id": ObjectId(post_id), "parent_comment_id": None, "is_active": True}
        ).sort("created_at", -1).skip(skip).limit(limit))
        
        comment_responses = []
        for comment in comments:
            # Get user profile
            user_profile = get_user_profile(comment["user_id"], db)
            
            # Get replies count
            replies_count = db.comments.count_documents({
                "parent_comment_id": comment["_id"],
                "is_active": True
            })
            
            comment_responses.append(CommentResponse(
                id=str(comment["_id"]),
                post_id=post_id,
                user=user_profile,
                content=comment["content"],
                replies_count=replies_count,
                likes_count=len(comment.get("likes", [])),
                is_liked=current_user.id in comment.get("likes", []),
                created_at=comment["created_at"],
                updated_at=comment.get("updated_at"),
                is_edited=comment.get("is_edited", False)
            ))
        
        return comment_responses
        
    except Exception as e:
        logger.error(f"Error getting comments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get comments")


@router.post("/comments/{comment_id}/like", response_model=LikeResponse)
async def toggle_like_comment(
    comment_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Like or unlike a comment"""
    try:
        comment = db.comments.find_one({"_id": ObjectId(comment_id), "is_active": True})
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        likes = comment.get("likes", [])
        
        if current_user.id in likes:
            # Unlike
            likes.remove(current_user.id)
            is_liked = False
        else:
            # Like
            likes.append(current_user.id)
            is_liked = True
        
        # Update comment
        db.comments.update_one(
            {"_id": ObjectId(comment_id)},
            {"$set": {"likes": likes}}
        )
        
        return LikeResponse(
            success=True,
            likes_count=len(likes),
            is_liked=is_liked
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling comment like: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle like")


@router.get("/stats", response_model=PostStats)
async def get_community_stats(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get community statistics"""
    try:
        cache_key = "global"
        cached_stats = cache_service.get("community_stats", cache_key)
        if cached_stats:
            logger.debug("Serving community stats from cache")
            return PostStats(**cached_stats)

        # Total posts
        total_posts = db.community_posts.count_documents({"is_active": True})
        
        # Posts today
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        posts_today = db.community_posts.count_documents({
            "is_active": True,
            "created_at": {"$gte": today}
        })
        
        # Trending tags (top 5)
        pipeline = [
            {"$match": {"is_active": True}},
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
            {"$project": {"tag": "$_id", "count": 1, "_id": 0}}
        ]
        trending_tags = list(db.community_posts.aggregate(pipeline))
        
        # Active users (posted in last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users_pipeline = [
            {"$match": {"is_active": True, "created_at": {"$gte": yesterday}}},
            {"$group": {"_id": "$user_id"}},
            {"$count": "count"}
        ]
        active_users_result = list(db.community_posts.aggregate(active_users_pipeline))
        active_users = active_users_result[0]["count"] if active_users_result else 0

        stats_payload = {
            "total_posts": total_posts,
            "posts_today": posts_today,
            "trending_tags": trending_tags,
            "active_users": active_users,
        }
        cache_service.set("community_stats", cache_key, stats_payload, ttl_seconds=180)
        
        return PostStats(**stats_payload)
        
    except Exception as e:
        logger.error(f"Error getting community stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


@router.get("/saved", response_model=PostListResponse)
async def get_saved_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get user's saved posts"""
    try:
        # Find posts where user is in saves array
        query = {"is_active": True, "saves": current_user.id}
        posts = list(db.community_posts.find(query).sort("created_at", -1).skip(skip).limit(limit))
        total = db.community_posts.count_documents(query)
        
        # Transform posts (similar to get_posts)
        post_responses = []
        for post in posts:
            user_profile = get_user_profile(post["user_id"], db)
            interactions = get_post_interactions(post["_id"], current_user.id, db)
            
            post_responses.append(PostResponse(
                id=str(post["_id"]),
                user=user_profile,
                content=post["content"],
                image_url=post.get("image_url"),
                tags=post.get("tags", []),
                post_type=post["post_type"],
                likes_count=len(post.get("likes", [])),
                comments_count=post.get("comments_count", 0),
                saves_count=len(post.get("saves", [])),
                is_liked=interactions["is_liked"],
                is_saved=True,  # Always true for saved posts
                created_at=post["created_at"],
                updated_at=post.get("updated_at"),
                is_edited=post.get("is_edited", False)
            ))
        
        return PostListResponse(
            posts=post_responses,
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + limit) < total
        )
        
    except Exception as e:
        logger.error(f"Error getting saved posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get saved posts")
