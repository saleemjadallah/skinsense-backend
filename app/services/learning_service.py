import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId

from app.database import get_database
from app.schemas.learning import (
    LearningArticleCreate,
    LearningArticleUpdate,
    LearningArticleInDB,
    LearningArticleResponse,
    ArticleGenerationRequest,
    ArticleBatchGenerationRequest,
    ArticleInteraction,
    UserLearningProgress,
    ArticleCategoryEnum,
    ArticleDifficultyEnum
)
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class LearningService:
    """Service for managing learning content and educational articles"""
    
    def __init__(self):
        self._db = None
        self._collection = None
        self._interactions_collection = None
        self._progress_collection = None
        self._indexes_created = False
    
    @property
    def db(self):
        """Lazy database connection"""
        if self._db is None:
            self._db = get_database()
        return self._db
    
    @property
    def collection(self):
        """Lazy collection access"""
        if self._collection is None:
            self._collection = self.db.learning_articles
            if not self._indexes_created:
                self._create_indexes()
        return self._collection
    
    @property
    def interactions_collection(self):
        """Lazy interactions collection access"""
        if self._interactions_collection is None:
            self._interactions_collection = self.db.article_interactions
        return self._interactions_collection
    
    @property
    def progress_collection(self):
        """Lazy progress collection access"""
        if self._progress_collection is None:
            self._progress_collection = self.db.user_learning_progress
        return self._progress_collection
    
    def _create_indexes(self):
        """Create necessary database indexes"""
        try:
            # Article indexes
            self.collection.create_index("category")
            self.collection.create_index("difficulty_level")
            self.collection.create_index("tags")
            self.collection.create_index("is_published")
            self.collection.create_index("is_featured")
            self.collection.create_index([("created_at", -1)])
            self.collection.create_index([("view_count", -1)])
            
            # Interaction indexes
            self.interactions_collection.create_index([("user_id", 1), ("article_id", 1)])
            self.interactions_collection.create_index("created_at")
            
            # Progress indexes
            self.progress_collection.create_index("user_id", unique=True)
            
            self._indexes_created = True
        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")
    
    async def generate_article(
        self,
        request: ArticleGenerationRequest,
        target_audience: Optional[Dict[str, Any]] = None
    ) -> LearningArticleResponse:
        """Generate a single educational article using OpenAI"""
        try:
            # Generate article using OpenAI
            article_data = await openai_service.generate_learning_article(
                topic=request.topic,
                category=request.category,
                difficulty=request.difficulty,
                target_audience=target_audience or request.target_audience
            )
            
            # Create article document
            article_doc = {
                **article_data,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "generated_by": "openai",
                "view_count": 0,
                "like_count": 0,
                "is_published": True,
                "is_featured": False
            }
            
            # Insert into database
            result = self.collection.insert_one(article_doc)
            article_doc["_id"] = result.inserted_id
            
            return self._format_article_response(article_doc)
            
        except Exception as e:
            logger.error(f"Failed to generate article: {e}")
            raise
    
    async def generate_multiple_articles(
        self,
        request: ArticleBatchGenerationRequest
    ) -> List[LearningArticleResponse]:
        """Generate multiple articles in batch"""
        try:
            # Generate articles using OpenAI
            articles_data = await openai_service.generate_multiple_articles(
                topics=request.topics,
                target_audience=request.target_audience
            )
            
            # Create article documents
            article_docs = []
            for article_data in articles_data:
                article_doc = {
                    **article_data,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "generated_by": "openai",
                    "view_count": 0,
                    "like_count": 0,
                    "is_published": True,
                    "is_featured": False
                }
                article_docs.append(article_doc)
            
            # Bulk insert
            if article_docs:
                result = self.collection.insert_many(article_docs)
                
                # Add IDs to documents
                for i, doc in enumerate(article_docs):
                    doc["_id"] = result.inserted_ids[i]
            
            return [self._format_article_response(doc) for doc in article_docs]
            
        except Exception as e:
            logger.error(f"Failed to generate multiple articles: {e}")
            raise
    
    async def get_articles(
        self,
        user_id: Optional[str] = None,
        category: Optional[ArticleCategoryEnum] = None,
        difficulty: Optional[ArticleDifficultyEnum] = None,
        is_featured: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get articles with filtering and pagination"""
        try:
            # Build query
            query = {"is_published": True}
            
            if category:
                query["category"] = category
            
            if difficulty:
                query["difficulty_level"] = difficulty
            
            if is_featured is not None:
                query["is_featured"] = is_featured
            
            if search:
                query["$or"] = [
                    {"title": {"$regex": search, "$options": "i"}},
                    {"subtitle": {"$regex": search, "$options": "i"}},
                    {"tags": {"$in": [search.lower()]}}
                ]
            
            # Get total count
            total = self.collection.count_documents(query)
            
            # Get articles with pagination
            skip = (page - 1) * limit
            articles = list(
                self.collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            
            # Format responses with user-specific data
            formatted_articles = []
            for article in articles:
                formatted = self._format_article_response(article, user_id)
                formatted_articles.append(formatted)
            
            return {
                "articles": formatted_articles,
                "total": total,
                "page": page,
                "limit": limit,
                "has_more": skip + limit < total
            }
            
        except Exception as e:
            logger.error(f"Failed to get articles: {e}")
            raise
    
    async def get_article_by_id(
        self,
        article_id: str,
        user_id: Optional[str] = None
    ) -> Optional[LearningArticleResponse]:
        """Get a single article by ID"""
        try:
            article = self.collection.find_one({
                "_id": ObjectId(article_id),
                "is_published": True
            })
            
            if not article:
                return None
            
            # Increment view count
            self.collection.update_one(
                {"_id": ObjectId(article_id)},
                {"$inc": {"view_count": 1}}
            )
            
            # Track view interaction if user is logged in
            if user_id:
                await self.track_interaction(
                    user_id=user_id,
                    article_id=article_id,
                    interaction_type="view"
                )
            
            return self._format_article_response(article, user_id)
            
        except Exception as e:
            logger.error(f"Failed to get article: {e}")
            raise
    
    async def update_article(
        self,
        article_id: str,
        update: LearningArticleUpdate
    ) -> Optional[LearningArticleResponse]:
        """Update an article"""
        try:
            update_data = update.dict(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()
            
            result = self.collection.find_one_and_update(
                {"_id": ObjectId(article_id)},
                {"$set": update_data},
                return_document=True
            )
            
            if not result:
                return None
            
            return self._format_article_response(result)
            
        except Exception as e:
            logger.error(f"Failed to update article: {e}")
            raise
    
    async def track_interaction(
        self,
        user_id: str,
        article_id: str,
        interaction_type: str,
        progress: Optional[float] = None
    ) -> None:
        """Track user interaction with article"""
        try:
            interaction = {
                "user_id": user_id,
                "article_id": article_id,
                "interaction_type": interaction_type,
                "created_at": datetime.utcnow()
            }
            
            if progress is not None:
                interaction["progress"] = progress
            
            # Insert interaction
            self.interactions_collection.insert_one(interaction)
            
            # Update counts based on interaction type
            if interaction_type == "like":
                self.collection.update_one(
                    {"_id": ObjectId(article_id)},
                    {"$inc": {"like_count": 1}}
                )
            
            # Update user progress
            await self._update_user_progress(user_id, article_id, interaction_type)
            
        except Exception as e:
            logger.error(f"Failed to track interaction: {e}")
    
    async def get_featured_articles(
        self,
        limit: int = 5
    ) -> List[LearningArticleResponse]:
        """Get featured articles for homepage"""
        try:
            articles = list(
                self.collection.find({
                    "is_published": True,
                    "is_featured": True
                })
                .sort("created_at", -1)
                .limit(limit)
            )
            
            return [self._format_article_response(article) for article in articles]
            
        except Exception as e:
            logger.error(f"Failed to get featured articles: {e}")
            return []
    
    async def get_user_progress(self, user_id: str) -> UserLearningProgress:
        """Get user's learning progress"""
        try:
            progress = self.progress_collection.find_one({"user_id": user_id})
            
            if not progress:
                # Create new progress record
                progress = {
                    "user_id": user_id,
                    "total_articles_read": 0,
                    "total_reading_time": 0,
                    "articles_completed": [],
                    "articles_bookmarked": [],
                    "articles_liked": [],
                    "learning_streak": 0,
                    "last_read_date": None,
                    "category_progress": {},
                    "difficulty_progress": {}
                }
                self.progress_collection.insert_one(progress)
            
            return UserLearningProgress(**progress)
            
        except Exception as e:
            logger.error(f"Failed to get user progress: {e}")
            raise
    
    def _format_article_response(
        self,
        article: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> LearningArticleResponse:
        """Format article for API response"""
        # Convert ObjectId to string
        article["id"] = str(article.pop("_id"))
        
        # Check if article is new (< 7 days old)
        is_new = (datetime.utcnow() - article["created_at"]).days < 7
        
        # Check if article is trending (high view count in last 7 days)
        is_trending = article.get("view_count", 0) > 100
        
        # Get user-specific data if user_id provided
        user_has_liked = False
        user_has_bookmarked = False
        completion_status = None
        
        if user_id:
            # Check if user has liked
            liked = self.interactions_collection.find_one({
                "user_id": user_id,
                "article_id": article["id"],
                "interaction_type": "like"
            })
            user_has_liked = liked is not None
            
            # Check if user has bookmarked
            bookmarked = self.interactions_collection.find_one({
                "user_id": user_id,
                "article_id": article["id"],
                "interaction_type": "bookmark"
            })
            user_has_bookmarked = bookmarked is not None
            
            # Get reading progress
            progress = self.interactions_collection.find_one({
                "user_id": user_id,
                "article_id": article["id"],
                "interaction_type": "view"
            }, sort=[("created_at", -1)])
            
            if progress and "progress" in progress:
                completion_status = progress["progress"]
        
        return LearningArticleResponse(
            **article,
            is_new=is_new,
            is_trending=is_trending,
            user_has_liked=user_has_liked,
            user_has_bookmarked=user_has_bookmarked,
            completion_status=completion_status
        )
    
    async def _update_user_progress(
        self,
        user_id: str,
        article_id: str,
        interaction_type: str
    ) -> None:
        """Update user's learning progress"""
        try:
            update_ops = {}
            
            if interaction_type == "complete":
                update_ops["$addToSet"] = {"articles_completed": article_id}
                update_ops["$inc"] = {"total_articles_read": 1}
                
                # Update last read date for streak calculation
                update_ops["$set"] = {"last_read_date": datetime.utcnow()}
                
            elif interaction_type == "bookmark":
                update_ops["$addToSet"] = {"articles_bookmarked": article_id}
                
            elif interaction_type == "like":
                update_ops["$addToSet"] = {"articles_liked": article_id}
            
            if update_ops:
                self.progress_collection.update_one(
                    {"user_id": user_id},
                    update_ops,
                    upsert=True
                )
                
        except Exception as e:
            logger.error(f"Failed to update user progress: {e}")
    
    async def get_default_articles(self) -> List[Dict[str, str]]:
        """Get default article topics for initial generation"""
        return [
            {
                "topic": "Understanding Your Skin Type",
                "category": "Basics",
                "difficulty": "Beginner"
            },
            {
                "topic": "The Science Behind Retinoids",
                "category": "Ingredients",
                "difficulty": "Intermediate"
            },
            {
                "topic": "Building Your First Skincare Routine",
                "category": "Basics",
                "difficulty": "Beginner"
            },
            {
                "topic": "Dealing with Hormonal Acne",
                "category": "Troubleshooting",
                "difficulty": "Intermediate"
            },
            {
                "topic": "The Art of Double Cleansing",
                "category": "Techniques",
                "difficulty": "Beginner"
            }
        ]


# Global instance
learning_service = LearningService()