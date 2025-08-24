from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Literal
from datetime import datetime


class RoutineProductCreate(BaseModel):
    """Schema for creating a product in routine step"""
    name: str = Field(..., min_length=1, max_length=200)
    brand: Optional[str] = Field(None, max_length=100)
    product_id: Optional[str] = None
    image_url: Optional[str] = None


class RoutineStepCreate(BaseModel):
    """Schema for creating a routine step"""
    order: int = Field(..., ge=1, le=20)
    category: Literal[
        "cleanser", "toner", "essence", "serum", "treatment", 
        "eye_cream", "moisturizer", "face_oil", "sunscreen", 
        "mask", "exfoliant", "spot_treatment", "other"
    ]
    product: Optional[RoutineProductCreate] = None
    duration_seconds: int = Field(default=30, ge=10, le=600)
    instructions: Optional[str] = Field(None, max_length=500)
    is_optional: bool = False
    frequency: Literal["daily", "weekly", "biweekly", "as_needed"] = "daily"


class RoutineCreate(BaseModel):
    """Schema for creating a new routine"""
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal["morning", "evening", "weekly", "treatment"]
    steps: List[RoutineStepCreate] = Field(..., min_items=1, max_items=15)
    notes: Optional[str] = Field(None, max_length=1000)
    tags: List[str] = Field(default_factory=list, max_items=10)
    
    @validator('steps')
    def validate_step_orders(cls, steps):
        """Ensure step orders are unique and sequential"""
        orders = [step.order for step in steps]
        if len(orders) != len(set(orders)):
            raise ValueError("Step orders must be unique")
        return steps


class RoutineUpdate(BaseModel):
    """Schema for updating a routine"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    steps: Optional[List[RoutineStepCreate]] = Field(None, min_items=1, max_items=15)
    is_active: Optional[bool] = None
    is_favorite: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = Field(None, max_items=10)
    # Minimal scheduling
    schedule_time: Optional[Literal["morning", "afternoon", "evening"]] = None
    schedule_days: Optional[List[int]] = None  # 1=Mon .. 7=Sun


class RoutineGenerateRequest(BaseModel):
    """Request schema for AI routine generation"""
    routine_type: Literal["morning", "evening"] = Field("morning", alias="type")  # Accept both field names
    skin_analysis_id: Optional[str] = Field(None, alias="analysis_id")  # Accept both field names
    focus_areas: Optional[List[str]] = Field(None, alias="concerns_override")  # Accept both field names
    time_available: Optional[int] = Field(None, ge=5, le=60)  # Minutes available
    budget_preference: Optional[Literal["budget", "moderate", "premium"]] = "moderate"
    include_devices: bool = False  # Include device-based treatments
    # Additional fields from Flutter
    preferred_brands: Optional[List[str]] = None
    excluded_ingredients: Optional[List[str]] = None
    use_latest_analysis: bool = True
    link_to_goals: bool = True
    
    class Config:
        populate_by_name = True  # Allow both field names


class RoutineResponse(BaseModel):
    """Response schema for routine data"""
    id: str = Field(alias="_id")
    user_id: str
    name: str
    type: Literal["morning", "evening", "weekly", "treatment"]
    created_from: Literal["ai_generated", "template", "manual", "hybrid"]
    target_concerns: List[str]
    steps: List[Dict]  # Full step data
    total_duration_minutes: int
    last_completed: Optional[datetime] = None
    completion_count: int
    completion_streak: int
    effectiveness_scores: Optional[Dict[str, float]] = None
    based_on_analysis_id: Optional[str] = None  # Added to match Flutter
    is_active: bool
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None
    tags: List[str]
    ai_confidence_score: Optional[float] = None  # Added to match Flutter
    estimated_monthly_cost: Optional[float] = None  # Added to match Flutter
    
    class Config:
        populate_by_name = True  # Allow both 'id' and '_id' for setting
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class RoutineListResponse(BaseModel):
    """Response for listing routines"""
    routines: List[RoutineResponse]
    total: int
    active_count: int
    favorite_count: int


class RoutineCompleteRequest(BaseModel):
    """Request to mark routine as complete"""
    duration_minutes: Optional[int] = None
    steps_completed: List[int] = Field(default_factory=list)
    skipped_steps: List[int] = Field(default_factory=list)
    notes: Optional[str] = Field(None, max_length=500)
    mood: Optional[Literal["great", "good", "okay", "bad"]] = None
    skin_feel: Optional[Literal["hydrated", "dry", "oily", "irritated", "normal"]] = None


class RoutineCompletionResponse(BaseModel):
    """Response after completing a routine"""
    id: str
    routine_id: str
    completed_at: datetime
    new_streak: int
    total_completions: int
    message: str


class RoutineAnalysisInsight(BaseModel):
    """Insights about routine effectiveness"""
    routine_id: str
    adherence_rate: float  # Percentage of days completed
    average_completion_time: int  # Minutes
    most_skipped_steps: List[str]
    skin_improvements: Dict[str, float]  # Parameter: improvement percentage
    recommended_adjustments: List[str]


class RoutineTemplateResponse(BaseModel):
    """Response schema for routine templates"""
    id: str = Field(alias="_id")
    name: str
    description: str
    type: Literal["morning", "evening", "weekly", "treatment"]
    target_concerns: List[str]
    suitable_for_skin_types: List[str] = Field(serialization_alias="skin_types")  # Send as skin_types to Flutter
    steps: List[Dict]
    difficulty_level: Literal["beginner", "intermediate", "advanced"]
    estimated_cost: Literal["budget", "moderate", "premium"]
    popularity_score: float
    time_estimate_minutes: int  # Added to match Flutter model
    # Optional fields expected by Flutter
    is_featured: bool = False
    usage_count: int = 0
    average_rating: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True  # Allow both 'id' and '_id' for setting


class RoutineDuplicateRequest(BaseModel):
    """Request to duplicate a routine"""
    new_name: str = Field(..., min_length=1, max_length=100)
    make_active: bool = True