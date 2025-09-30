from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


class RoutineGenerateRequest(BaseModel):
    routine_type: str  # "morning", "evening", "weekly_treatment"
    include_user_products: bool = True
    weather_data: Optional[Dict[str, Any]] = None
    force_regenerate: bool = False

    @validator("routine_type")
    def validate_routine_type(cls, v):
        allowed_types = ["morning", "evening", "weekly_treatment"]
        if v not in allowed_types:
            raise ValueError(f"Routine type must be one of {allowed_types}")
        return v


class RoutineStepResponse(BaseModel):
    step_number: int
    product_category: str
    product_name: Optional[str]
    instructions: str
    duration_minutes: int
    key_benefits: List[str]
    technique_tips: Optional[str]


class RoutineResponse(BaseModel):
    id: str
    routine_type: str
    routine_name: str
    description: str
    total_duration_minutes: int
    difficulty_level: str
    skin_concerns_addressed: List[str]
    weather_adapted: bool
    times_used: int
    user_rating: Optional[float]
    is_favorite: bool
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class RoutineDetailResponse(RoutineResponse):
    steps: List[RoutineStepResponse]
    ai_reasoning: str
    confidence_score: float
    alternative_suggestions: List[str]
    current_weather_context: Optional[Dict[str, Any]]
    generated_from: Dict[str, Any]
    last_used: Optional[datetime]


class RoutineUpdateRequest(BaseModel):
    routine_name: Optional[str] = None
    is_favorite: Optional[bool] = None
    user_rating: Optional[float] = None
    user_feedback: Optional[str] = None


class RoutineRatingRequest(BaseModel):
    rating: float = Field(..., ge=1.0, le=5.0)
    feedback: Optional[str] = Field(None, max_length=1000)


class RoutineListResponse(BaseModel):
    routines: List[RoutineResponse]
    total: int