from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class PlanCreateRequest(BaseModel):
    """Request to create a new plan"""
    plan_type: Optional[Literal[
        "hydration_boost", 
        "anti_aging", 
        "acne_control", 
        "brightening",
        "sensitivity_care",
        "texture_improvement",
        "custom"
    ]] = None
    custom_preferences: Optional[Dict[str, Any]] = None
    duration_weeks: Optional[int] = Field(None, ge=1, le=12)
    include_existing_routines: bool = True
    include_existing_goals: bool = True


class PlanUpdateRequest(BaseModel):
    """Request to update a plan"""
    status: Optional[Literal["active", "paused", "completed", "cancelled"]] = None
    notes: Optional[str] = None


class PlanProgressUpdate(BaseModel):
    """Update progress for a plan week"""
    week_number: int = Field(..., ge=1)
    completion_stats: Dict[str, Any] = Field(default_factory=dict)
    skin_improvements: Optional[Dict[str, float]] = None
    milestone_achieved: bool = False
    user_mood: Optional[Literal["great", "good", "okay", "challenging"]] = None
    user_notes: Optional[str] = None


class WeeklyMilestoneResponse(BaseModel):
    """Response for a weekly milestone"""
    week_number: int
    title: str
    description: str
    expected_improvements: Dict[str, float]
    focus_areas: List[str]
    tips: List[str]


class PlanResponse(BaseModel):
    """Response for a plan"""
    id: str
    name: str
    description: str
    plan_type: str
    status: str
    current_week: int
    duration_weeks: int
    completion_rate: float
    routine_count: int
    goal_count: int
    target_concerns: List[str]
    current_milestone: Optional[WeeklyMilestoneResponse] = None
    created_at: str
    started_at: Optional[str] = None


class PlanDetailResponse(BaseModel):
    """Detailed response for a plan"""
    id: str
    name: str
    description: str
    plan_type: str
    status: str
    current_week: int
    duration_weeks: int
    started_at: str
    target_concerns: List[str]
    personalization_data: Dict[str, Any]
    current_milestone: Optional[Dict[str, Any]] = None
    routines: List[Dict[str, Any]]
    goals: List[Dict[str, Any]]
    current_week_stats: Dict[str, Any]
    effectiveness_predictions: Dict[str, float]
    latest_progress: Optional[Dict[str, Any]] = None


class PlanListResponse(BaseModel):
    """Response for list of plans"""
    plans: List[PlanResponse]
    active_count: int
    completed_count: int


class PlanProgressResponse(BaseModel):
    """Response for plan progress"""
    plan_id: str
    week_number: int
    completion_stats: Dict[str, Any]
    skin_improvements: Dict[str, float]
    milestone_achieved: bool
    recorded_at: str


class PlanInsightsResponse(BaseModel):
    """Response for plan insights"""
    insights: str
    current_week: int
    completion_percentage: float
    weeks_remaining: int
    recommendations: Optional[List[str]] = None


class PlanTemplateResponse(BaseModel):
    """Response for a plan template"""
    id: str
    name: str
    description: str
    plan_type: str
    duration_weeks: int
    suitable_for_concerns: List[str]
    suitable_for_skin_types: List[str]
    difficulty_level: str
    expected_improvements: Dict[str, float]
    usage_count: int
    average_completion_rate: float
    user_rating: float


class CompleteWeekRequest(BaseModel):
    """Request to complete current week"""
    satisfaction_rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None