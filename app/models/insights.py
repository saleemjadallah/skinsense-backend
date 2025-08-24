from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from bson import ObjectId
from .user import PyObjectId

class InsightContent(BaseModel):
    """Individual insight content"""
    title: str
    description: str
    icon: str  # CupertinoIcons name for Flutter
    category: Literal[
        "skin_trend",          # Trends in skin metrics
        "product_tip",         # Product usage tips
        "environmental",       # Weather/season related
        "habit_formation",     # Building good habits
        "ingredient_focus",    # Ingredient education
        "prevention",          # Preventive care tips
        "celebration",         # Achievements/milestones
        "recommendation"       # Personalized product/routine suggestions
    ]
    priority: Literal["high", "medium", "low"] = "medium"
    action_text: Optional[str] = None  # e.g., "View Products", "Check Progress"
    action_route: Optional[str] = None  # Flutter route to navigate
    metadata: Dict[str, Any] = {}  # Additional data for the insight

class PersonalizationFactors(BaseModel):
    """Factors used to personalize insights"""
    skin_type: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    current_season: str
    weather_condition: Optional[str] = None
    skin_concerns: List[str] = []
    recent_analysis_scores: Dict[str, float] = {}
    routine_completion_rate: float = 0.0
    days_since_last_analysis: Optional[int] = None
    active_goals: List[str] = []
    preferred_ingredients: List[str] = []
    avoided_ingredients: List[str] = []
    streak_days: int = 0
    improvement_areas: List[str] = []  # Areas with scores < 70
    celebration_triggers: List[str] = []  # Recent achievements

class DailyInsights(BaseModel):
    """Daily personalized insights for a user"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    
    # The three daily insights
    insights: List[InsightContent] = []
    
    # Personalization context
    personalization_factors: PersonalizationFactors
    
    # Metadata
    generated_for_date: datetime  # Changed from date to datetime for MongoDB compatibility
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime  # Usually 24 hours from creation
    
    # Tracking
    viewed: bool = False
    viewed_at: Optional[datetime] = None
    interactions: List[Dict[str, Any]] = []  # Track clicks, dismissals, etc.
    
    # Generation metadata
    generation_method: str = "ai_personalized"  # or "fallback", "manual"
    generation_version: str = "v1.0"
    
class InsightTemplate(BaseModel):
    """Reusable insight templates for common scenarios"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str}
    }
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    
    # Template info
    name: str
    title_template: str  # Can include {placeholders}
    description_template: str  # Can include {placeholders}
    icon: str
    category: str
    
    # Conditions for showing this template
    conditions: Dict[str, Any] = {}  # e.g., {"skin_type": ["dry", "sensitive"]}
    min_score_thresholds: Dict[str, float] = {}  # e.g., {"hydration": 60}
    max_score_thresholds: Dict[str, float] = {}  # e.g., {"acne": 30}
    season_restrictions: List[str] = []  # ["winter", "summer"]
    
    # Priority and frequency
    base_priority: str = "medium"
    cooldown_days: int = 7  # Don't show again for X days
    max_shows_per_month: int = 4
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    tags: List[str] = []

class UserInsightPreferences(BaseModel):
    """User preferences for insights"""
    preferred_categories: List[str] = []
    blocked_categories: List[str] = []
    insight_frequency: str = "daily"  # "daily", "weekly", "on_demand"
    preferred_time: Optional[str] = None  # "morning", "evening"
    language: str = "en"
    opt_out: bool = False