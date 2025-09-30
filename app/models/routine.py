from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(str)
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


class RoutineStep(BaseModel):
    step_number: int
    product_category: str  # "cleanser", "serum", "moisturizer", etc.
    product_recommendation_id: Optional[PyObjectId] = None
    product_name: Optional[str] = None
    instructions: str
    duration_minutes: int
    key_benefits: List[str] = []
    technique_tips: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class PersonalizedRoutine(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    routine_type: str  # "morning", "evening", "weekly_treatment"
    routine_name: str
    description: str
    generated_from: Dict[str, Any]  # Stores source data for transparency
    steps: List[RoutineStep]
    total_duration_minutes: int
    difficulty_level: str  # "beginner", "intermediate", "advanced"
    skin_concerns_addressed: List[str] = []
    weather_adapted: bool = False
    current_weather_context: Optional[Dict[str, Any]] = None

    # AI generation metadata
    ai_reasoning: str  # Why this routine was generated
    confidence_score: float = 0.0
    alternative_suggestions: List[str] = []

    # Engagement tracking
    times_used: int = 0
    last_used: Optional[datetime] = None
    user_rating: Optional[float] = None
    user_feedback: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_favorite: bool = False
    is_active: bool = True

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class RoutineTemplate(BaseModel):
    """Store successful routines as templates for future generation"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    base_routine: PersonalizedRoutine
    success_metrics: Dict[str, float]  # skin_score_improvement, user_rating, etc.
    user_profile_match: Dict[str, Any]  # What user characteristics this worked for
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}