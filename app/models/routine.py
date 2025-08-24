from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal
from datetime import datetime
from bson import ObjectId


class RoutineProduct(BaseModel):
    """Product used in a routine step"""
    name: str
    brand: Optional[str] = None
    product_id: Optional[str] = None  # Reference to products collection
    image_url: Optional[str] = None


class RoutineStep(BaseModel):
    """Individual step in a skincare routine"""
    order: int = Field(..., ge=1, le=20)
    category: Literal[
        "cleanser", "toner", "essence", "serum", "treatment", 
        "eye_cream", "moisturizer", "face_oil", "sunscreen", 
        "mask", "exfoliant", "spot_treatment", "other"
    ]
    product: Optional[RoutineProduct] = None
    duration_seconds: int = Field(default=30, ge=10, le=600)
    instructions: Optional[str] = None
    ai_reasoning: Optional[str] = None  # Why AI recommended this
    is_optional: bool = False
    frequency: Literal["daily", "weekly", "biweekly", "as_needed"] = "daily"


class EffectivenessScores(BaseModel):
    """Predicted effectiveness for skin parameters"""
    overall_skin_health_score: Optional[float] = None
    hydration: Optional[float] = None
    smoothness: Optional[float] = None
    radiance: Optional[float] = None
    dark_spots: Optional[float] = None
    firmness: Optional[float] = None
    fine_lines_wrinkles: Optional[float] = None
    acne: Optional[float] = None
    dark_circles: Optional[float] = None
    redness: Optional[float] = None


class RoutineModel(BaseModel):
    """Main routine model for database"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    user_id: ObjectId
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal["morning", "evening", "weekly", "treatment"]
    created_from: Literal["ai_generated", "template", "manual", "hybrid"]
    
    # Target concerns based on low scores (<80)
    target_concerns: List[str] = Field(default_factory=list)
    
    # Routine steps
    steps: List[RoutineStep] = Field(..., min_items=1, max_items=15)
    
    # Timing and tracking
    total_duration_minutes: int = Field(default=0)
    last_completed: Optional[datetime] = None
    completion_count: int = Field(default=0)
    completion_streak: int = Field(default=0)
    # Minimal scheduling
    schedule_time: Optional[Literal["morning", "afternoon", "evening"]] = None
    schedule_days: List[int] = Field(default_factory=lambda: [1,2,3,4,5,6,7])  # 1=Mon .. 7=Sun
    
    # AI predictions and metadata
    effectiveness_scores: Optional[EffectivenessScores] = None
    based_on_analysis_id: Optional[ObjectId] = None  # Link to skin analysis
    
    # Status and dates
    is_active: bool = Field(default=True)
    is_favorite: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Additional metadata
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    def calculate_total_duration(self) -> int:
        """Calculate total routine duration in minutes"""
        total_seconds = sum(step.duration_seconds for step in self.steps if step.frequency == "daily")
        return round(total_seconds / 60)
    
    def get_daily_steps(self) -> List[RoutineStep]:
        """Get only daily steps"""
        return [step for step in self.steps if step.frequency == "daily"]
    
    def dict(self, *args, **kwargs):
        """Override dict to calculate duration"""
        data = super().dict(*args, **kwargs)
        data['total_duration_minutes'] = self.calculate_total_duration()
        return data


class RoutineCompletion(BaseModel):
    """Track routine completions"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    user_id: ObjectId
    routine_id: ObjectId
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    duration_minutes: Optional[int] = None
    steps_completed: List[int] = Field(default_factory=list)  # Step orders completed
    skipped_steps: List[int] = Field(default_factory=list)  # Step orders skipped
    notes: Optional[str] = None
    mood: Optional[Literal["great", "good", "okay", "bad"]] = None
    skin_feel: Optional[Literal["hydrated", "dry", "oily", "irritated", "normal"]] = None


class RoutineTemplate(BaseModel):
    """Pre-built routine templates"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    name: str
    description: str
    type: Literal["morning", "evening", "weekly", "treatment"]
    target_concerns: List[str]
    suitable_for_skin_types: List[str]  # dry, oily, combination, sensitive, normal
    steps: List[RoutineStep]
    difficulty_level: Literal["beginner", "intermediate", "advanced"]
    estimated_cost: Literal["budget", "moderate", "premium"]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    popularity_score: float = Field(default=0.0)  # Based on usage