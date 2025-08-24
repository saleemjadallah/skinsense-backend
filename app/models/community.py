from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from bson import ObjectId


class CommunityPost(BaseModel):
    """Community post model"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(None, alias="_id")
    user_id: ObjectId
    content: str
    image_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    post_type: str = "post"  # post, question, transformation
    is_anonymous: bool = False  # Anonymous posting flag
    
    # Engagement metrics
    likes: List[ObjectId] = Field(default_factory=list)  # User IDs who liked
    saves: List[ObjectId] = Field(default_factory=list)  # User IDs who saved
    comments_count: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    is_edited: bool = False
    
    # Moderation
    is_active: bool = True
    is_reported: bool = False
    report_count: int = 0


class Comment(BaseModel):
    """Comment model"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(None, alias="_id")
    post_id: ObjectId
    user_id: ObjectId
    content: str
    parent_comment_id: Optional[ObjectId] = None  # For nested comments
    
    # Engagement
    likes: List[ObjectId] = Field(default_factory=list)
    replies_count: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    is_edited: bool = False
    
    # Moderation
    is_active: bool = True
    is_reported: bool = False


class PostInteraction(BaseModel):
    """Track user interactions with posts"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(None, alias="_id")
    user_id: ObjectId
    post_id: ObjectId
    interaction_type: str  # view, like, save, share, report
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExpertProfile(BaseModel):
    """Expert profile for community"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(None, alias="_id")
    user_id: ObjectId
    title: str  # e.g., "Dermatologist", "Licensed Esthetician"
    specialty: str  # e.g., "Acne & Aging", "Sensitive Skin"
    credentials: List[str] = Field(default_factory=list)
    
    # Stats
    rating: float = 0.0
    total_ratings: int = 0
    answers_count: int = 0
    helpful_votes: int = 0
    
    # Availability
    is_available: bool = True
    consultation_fee: Optional[float] = None
    
    # Verification
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    verification_documents: List[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None