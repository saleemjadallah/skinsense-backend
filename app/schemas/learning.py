from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ArticleCategoryEnum(str, Enum):
    """Article categories for learning content"""
    BASICS = "Basics"
    INGREDIENTS = "Ingredients"
    TECHNIQUES = "Techniques"
    TROUBLESHOOTING = "Troubleshooting"
    SCIENCE = "Science"
    TRENDS = "Trends"


class ArticleDifficultyEnum(str, Enum):
    """Difficulty levels for articles"""
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


class LearningArticleBase(BaseModel):
    """Base schema for learning articles"""
    topic: str = Field(..., description="Main topic of the article")
    category: ArticleCategoryEnum = Field(..., description="Article category")
    difficulty_level: ArticleDifficultyEnum = Field(
        ArticleDifficultyEnum.BEGINNER,
        description="Difficulty level"
    )
    title: str = Field(..., description="Article title")
    subtitle: str = Field(..., description="Brief description")
    content: str = Field(..., description="HTML formatted article content")
    key_takeaways: List[str] = Field(
        ..., 
        description="3-5 main points from the article"
    )
    pro_tips: List[str] = Field(
        ..., 
        description="2-3 expert tips"
    )
    related_topics: List[str] = Field(
        ..., 
        description="Related topics for further learning"
    )
    estimated_reading_time: int = Field(
        ..., 
        description="Estimated reading time in minutes",
        ge=1,
        le=30
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Relevant tags for search"
    )
    is_featured: bool = Field(
        default=False,
        description="Whether article is featured"
    )
    view_count: int = Field(
        default=0,
        description="Number of views",
        ge=0
    )
    like_count: int = Field(
        default=0,
        description="Number of likes",
        ge=0
    )
    is_published: bool = Field(
        default=True,
        description="Whether article is published"
    )


class LearningArticleCreate(LearningArticleBase):
    """Schema for creating a learning article"""
    pass


class LearningArticleUpdate(BaseModel):
    """Schema for updating a learning article"""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    content: Optional[str] = None
    key_takeaways: Optional[List[str]] = None
    pro_tips: Optional[List[str]] = None
    related_topics: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    is_published: Optional[bool] = None


class LearningArticleInDB(LearningArticleBase):
    """Schema for learning article in database"""
    id: str = Field(..., description="Article ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated_by: str = Field(
        default="openai",
        description="Generation source (openai, admin, etc.)"
    )
    author: Optional[str] = Field(
        None,
        description="Author name if manually created"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class LearningArticleResponse(LearningArticleInDB):
    """Schema for article API response"""
    is_new: bool = Field(
        default=False,
        description="Whether article is new (< 7 days old)"
    )
    is_trending: bool = Field(
        default=False,
        description="Whether article is trending"
    )
    user_has_liked: bool = Field(
        default=False,
        description="Whether current user has liked"
    )
    user_has_bookmarked: bool = Field(
        default=False,
        description="Whether current user has bookmarked"
    )
    completion_status: Optional[float] = Field(
        None,
        description="User's reading progress (0-1)",
        ge=0,
        le=1
    )


class ArticleGenerationRequest(BaseModel):
    """Request to generate a new article"""
    topic: str = Field(..., description="Article topic")
    category: ArticleCategoryEnum = Field(..., description="Article category")
    difficulty: ArticleDifficultyEnum = Field(
        ArticleDifficultyEnum.BEGINNER,
        description="Difficulty level"
    )
    target_audience: Optional[Dict[str, Any]] = Field(
        None,
        description="Target audience profile for personalization"
    )


class ArticleBatchGenerationRequest(BaseModel):
    """Request to generate multiple articles"""
    topics: List[Dict[str, str]] = Field(
        ...,
        description="List of topics with category and difficulty"
    )
    target_audience: Optional[Dict[str, Any]] = Field(
        None,
        description="Target audience profile"
    )


class ArticleInteraction(BaseModel):
    """Track user interactions with articles"""
    article_id: str = Field(..., description="Article ID")
    interaction_type: str = Field(
        ...,
        description="Type of interaction (view, like, bookmark, complete)"
    )
    progress: Optional[float] = Field(
        None,
        description="Reading progress for view interactions",
        ge=0,
        le=1
    )


class ArticleListResponse(BaseModel):
    """Response for article list"""
    articles: List[LearningArticleResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class UserLearningProgress(BaseModel):
    """Track user's overall learning progress"""
    user_id: str
    total_articles_read: int = 0
    total_reading_time: int = 0  # minutes
    articles_completed: List[str] = Field(default_factory=list)
    articles_bookmarked: List[str] = Field(default_factory=list)
    articles_liked: List[str] = Field(default_factory=list)
    learning_streak: int = 0
    last_read_date: Optional[datetime] = None
    category_progress: Dict[str, int] = Field(
        default_factory=dict,
        description="Articles read per category"
    )
    difficulty_progress: Dict[str, int] = Field(
        default_factory=dict,
        description="Articles read per difficulty"
    )


class LearningModule(BaseModel):
    """Learning module containing multiple related articles"""
    id: str
    title: str
    description: str
    category: ArticleCategoryEnum
    difficulty_level: ArticleDifficultyEnum
    article_ids: List[str]
    total_duration: int  # Total reading time in minutes
    is_completed: bool = False
    completion_percentage: float = Field(0.0, ge=0, le=100)
    icon: Optional[str] = None
    gradient_colors: Optional[List[str]] = None