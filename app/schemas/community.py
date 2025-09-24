from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class PostCreate(BaseModel):
    """Schema for creating a new post"""
    content: str = Field(..., min_length=1, max_length=2000)
    image_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list, max_items=5)
    post_type: str = Field(default="post", min_length=1, max_length=32)
    is_anonymous: bool = Field(default=False)

    @field_validator("post_type", mode="before")
    @classmethod
    def normalize_post_type(cls, value: Optional[str]) -> str:
        """Normalize the post type while staying backward compatible"""
        default_type = "post"
        allowed_types = {
            "post",
            "question",
            "general",
            "advice",
            "milestone",
            "progress",
            "transformation",
        }

        if value is None:
            return default_type

        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return default_type
            return normalized if normalized in allowed_types else default_type

        raise ValueError("Invalid post type value")


class PostUpdate(BaseModel):
    """Schema for updating a post"""
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    tags: Optional[List[str]] = Field(None, max_items=5)


class CommentCreate(BaseModel):
    """Schema for creating a comment"""
    content: str = Field(..., min_length=1, max_length=500)
    parent_comment_id: Optional[str] = None  # For nested comments


class CommentUpdate(BaseModel):
    """Schema for updating a comment"""
    content: str = Field(..., min_length=1, max_length=500)


class UserProfile(BaseModel):
    """User profile info for posts/comments"""
    id: str
    username: str
    profile_image: Optional[str] = None
    is_expert: bool = False
    expert_title: Optional[str] = None
    is_anonymous: bool = False


class CommentResponse(BaseModel):
    """Comment response schema"""
    id: str
    post_id: str
    user: UserProfile
    content: str
    parent_comment_id: Optional[str] = None
    replies_count: int = 0
    likes_count: int = 0
    is_liked: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_edited: bool = False
    

class PostResponse(BaseModel):
    """Post response schema"""
    id: str
    user: UserProfile
    content: str
    image_url: Optional[str] = None
    tags: List[str]
    post_type: str
    likes_count: int = 0
    comments_count: int = 0
    saves_count: int = 0
    is_liked: bool = False
    is_saved: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_edited: bool = False
    # Top comments preview
    top_comments: List[CommentResponse] = Field(default_factory=list)


class PostListResponse(BaseModel):
    """Response for post list queries"""
    posts: List[PostResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


class LikeResponse(BaseModel):
    """Response for like/unlike actions"""
    success: bool
    likes_count: int
    is_liked: bool


class SaveResponse(BaseModel):
    """Response for save/unsave actions"""
    success: bool
    saves_count: int
    is_saved: bool


class PostStats(BaseModel):
    """Community post statistics"""
    total_posts: int
    posts_today: int
    trending_tags: List[dict]  # [{tag: str, count: int}]
    active_users: int


class ExpertInfo(BaseModel):
    """Expert information"""
    user_id: str
    name: str
    title: str
    specialty: str
    rating: float
    answers_count: int
    is_available: bool
    profile_image: Optional[str] = None
