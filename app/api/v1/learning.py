from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging

from app.api.deps import get_current_user, get_current_user_optional
from app.schemas.user import UserResponse
from app.schemas.learning import (
    LearningArticleResponse,
    ArticleGenerationRequest,
    ArticleBatchGenerationRequest,
    ArticleInteraction,
    ArticleListResponse,
    UserLearningProgress,
    ArticleCategoryEnum,
    ArticleDifficultyEnum
)
from app.services.learning_service import learning_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=LearningArticleResponse)
async def generate_article(
    request: ArticleGenerationRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generate a single educational article using AI
    
    - **topic**: The main topic of the article
    - **category**: Article category (Basics, Ingredients, etc.)
    - **difficulty**: Difficulty level (Beginner, Intermediate, Advanced)
    - **target_audience**: Optional user profile for personalization
    """
    try:
        # Use current user's profile as target audience if not provided
        if not request.target_audience:
            target_audience = {
                "age_range": getattr(current_user, "age_range", None),
                "skin_type": getattr(current_user, "skin_type", None),
                "concerns": getattr(current_user, "skin_concerns", [])
            }
        else:
            target_audience = request.target_audience
        
        article = await learning_service.generate_article(
            request=request,
            target_audience=target_audience
        )
        
        return article
        
    except Exception as e:
        logger.error(f"Failed to generate article: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate article")


@router.post("/generate-batch", response_model=List[LearningArticleResponse])
async def generate_multiple_articles(
    request: ArticleBatchGenerationRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generate multiple educational articles in batch
    
    - **topics**: List of topics with category and difficulty
    - **target_audience**: Optional user profile for personalization
    """
    try:
        # Admin only endpoint
        if not getattr(current_user, "is_admin", False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        articles = await learning_service.generate_multiple_articles(request)
        return articles
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate articles: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate articles")


@router.post("/generate-defaults", response_model=List[LearningArticleResponse])
async def generate_default_articles(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generate default set of educational articles (Admin only)
    """
    try:
        # Admin only endpoint
        if not getattr(current_user, "is_admin", False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get default topics
        default_topics = await learning_service.get_default_articles()
        
        # Generate articles
        request = ArticleBatchGenerationRequest(topics=default_topics)
        articles = await learning_service.generate_multiple_articles(request)
        
        return articles
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate default articles: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate articles")


@router.get("/", response_model=ArticleListResponse)
async def get_articles(
    category: Optional[ArticleCategoryEnum] = None,
    difficulty: Optional[ArticleDifficultyEnum] = None,
    is_featured: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Get educational articles with filtering and pagination
    
    - **category**: Filter by category
    - **difficulty**: Filter by difficulty level
    - **is_featured**: Show only featured articles
    - **search**: Search in title, subtitle, and tags
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 10, max: 50)
    """
    try:
        user_id = str(current_user.id) if current_user else None
        
        result = await learning_service.get_articles(
            user_id=user_id,
            category=category,
            difficulty=difficulty,
            is_featured=is_featured,
            search=search,
            page=page,
            limit=limit
        )
        
        return ArticleListResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get articles: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve articles")


@router.get("/featured", response_model=List[LearningArticleResponse])
async def get_featured_articles(
    limit: int = Query(5, ge=1, le=10)
):
    """
    Get featured articles for homepage
    
    - **limit**: Number of articles to return (default: 5, max: 10)
    """
    try:
        articles = await learning_service.get_featured_articles(limit=limit)
        return articles
        
    except Exception as e:
        logger.error(f"Failed to get featured articles: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve articles")


@router.get("/progress", response_model=UserLearningProgress)
async def get_user_progress(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current user's learning progress
    """
    try:
        progress = await learning_service.get_user_progress(str(current_user.id))
        return progress
        
    except Exception as e:
        logger.error(f"Failed to get user progress: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve progress")


@router.get("/{article_id}", response_model=LearningArticleResponse)
async def get_article(
    article_id: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Get a single article by ID
    
    - **article_id**: The article ID to retrieve
    """
    try:
        user_id = str(current_user.id) if current_user else None
        
        article = await learning_service.get_article_by_id(
            article_id=article_id,
            user_id=user_id
        )
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return article
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get article: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve article")


@router.post("/{article_id}/interact")
async def track_article_interaction(
    article_id: str,
    interaction: ArticleInteraction,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Track user interaction with an article
    
    - **article_id**: The article ID
    - **interaction_type**: Type of interaction (view, like, bookmark, complete)
    - **progress**: Reading progress for view interactions (0-1)
    """
    try:
        # Validate article ID matches
        if article_id != interaction.article_id:
            raise HTTPException(status_code=400, detail="Article ID mismatch")
        
        await learning_service.track_interaction(
            user_id=str(current_user.id),
            article_id=article_id,
            interaction_type=interaction.interaction_type,
            progress=interaction.progress
        )
        
        return {"message": "Interaction tracked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to track interaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to track interaction")


@router.post("/{article_id}/like")
async def like_article(
    article_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Like an article
    """
    try:
        await learning_service.track_interaction(
            user_id=str(current_user.id),
            article_id=article_id,
            interaction_type="like"
        )
        
        return {"message": "Article liked successfully"}
        
    except Exception as e:
        logger.error(f"Failed to like article: {e}")
        raise HTTPException(status_code=500, detail="Failed to like article")


@router.post("/{article_id}/bookmark")
async def bookmark_article(
    article_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Bookmark an article
    """
    try:
        await learning_service.track_interaction(
            user_id=str(current_user.id),
            article_id=article_id,
            interaction_type="bookmark"
        )
        
        return {"message": "Article bookmarked successfully"}
        
    except Exception as e:
        logger.error(f"Failed to bookmark article: {e}")
        raise HTTPException(status_code=500, detail="Failed to bookmark article")


@router.post("/{article_id}/complete")
async def complete_article(
    article_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Mark an article as completed
    """
    try:
        await learning_service.track_interaction(
            user_id=str(current_user.id),
            article_id=article_id,
            interaction_type="complete",
            progress=1.0
        )
        
        return {"message": "Article marked as completed"}
        
    except Exception as e:
        logger.error(f"Failed to complete article: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete article")