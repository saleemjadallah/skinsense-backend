from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Literal, Any
from datetime import datetime, timedelta


class MilestoneCreate(BaseModel):
    """Schema for creating a milestone"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    target_value: Optional[float] = None
    percentage_trigger: Optional[int] = Field(None, ge=1, le=100)
    reward_message: Optional[str] = None


class MilestoneResponse(BaseModel):
    """Response schema for milestone"""
    milestone_id: str
    title: str
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_date: Optional[datetime] = None
    completed: bool
    completed_at: Optional[datetime] = None
    reward_message: Optional[str] = None
    percentage_trigger: Optional[int] = None


class GoalCreate(BaseModel):
    """Schema for creating a new goal"""
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=500)
    type: Literal["parameter_improvement", "routine_adherence", "holistic", "custom"]
    category: Optional[str] = None
    
    # Target specifics
    target_parameter: Optional[str] = None
    target_value: float = Field(..., gt=0)
    improvement_target: Optional[float] = None
    
    # Timeline
    duration_days: int = Field(..., ge=7, le=365)  # 1 week to 1 year
    
    # Optional fields
    linked_routine_id: Optional[str] = None
    difficulty_level: Optional[Literal["easy", "moderate", "challenging"]] = "moderate"
    custom_milestones: Optional[List[MilestoneCreate]] = None
    
    @validator('target_parameter')
    def validate_target_parameter(cls, v, values):
        """Ensure parameter goals have valid target parameter"""
        if values.get('type') == 'parameter_improvement' and not v:
            raise ValueError('target_parameter is required for parameter improvement goals')
        
        valid_parameters = [
            'overall_skin_health_score', 'hydration', 'smoothness', 'radiance',
            'dark_spots', 'firmness', 'fine_lines_wrinkles', 'acne',
            'dark_circles', 'redness'
        ]
        
        if v and v not in valid_parameters:
            raise ValueError(f'target_parameter must be one of: {", ".join(valid_parameters)}')
        
        return v


class GoalGenerateRequest(BaseModel):
    """Request schema for AI goal generation"""
    analysis_id: Optional[str] = None  # Use latest if not provided
    goal_count: int = Field(default=3, ge=1, le=5)
    focus_areas: Optional[List[str]] = None  # Specific parameters to focus on
    difficulty_preference: Optional[Literal["easy", "moderate", "challenging"]] = None
    exclude_types: Optional[List[str]] = None  # Goal types to exclude


class GoalUpdate(BaseModel):
    """Schema for updating a goal"""
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    target_value: Optional[float] = Field(None, gt=0)
    target_date: Optional[datetime] = None
    status: Optional[Literal["active", "paused", "abandoned"]] = None
    abandon_reason: Optional[str] = Field(None, max_length=500)


class GoalProgressUpdate(BaseModel):
    """Schema for updating goal progress"""
    parameter_value: Optional[float] = None
    routine_completed: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('parameter_value', 'routine_completed')
    def at_least_one_value(cls, v, values):
        """Ensure at least one progress value is provided"""
        if v is None and values.get('routine_completed') is None:
            raise ValueError('Either parameter_value or routine_completed must be provided')
        return v


class GoalResponse(BaseModel):
    """Response schema for goal data"""
    id: str
    user_id: str
    title: str
    description: str
    type: str
    category: Optional[str] = None
    
    # Target info
    target_parameter: Optional[str] = None
    baseline_value: float
    target_value: float
    current_value: float
    improvement_target: Optional[float] = None
    
    # Timeline
    start_date: datetime
    target_date: datetime
    duration_days: int
    days_remaining: int
    is_overdue: bool
    
    # Progress
    progress_percentage: float
    milestones: List[MilestoneResponse]
    last_check_in: Optional[datetime] = None
    
    # Status
    status: str
    completed_at: Optional[datetime] = None
    
    # Metadata
    difficulty_level: str
    reward_points: int
    ai_generated: bool
    created_at: datetime
    updated_at: datetime


class GoalListResponse(BaseModel):
    """Response for listing goals"""
    goals: List[GoalResponse]
    total: int
    active_count: int
    completed_count: int
    abandoned_count: int


class GoalProgressResponse(BaseModel):
    """Response for goal progress data"""
    goal_id: str
    progress_history: List[Dict[str, Any]]
    current_streak: int
    best_streak: int
    average_daily_progress: float
    projected_completion_date: Optional[datetime] = None
    on_track: bool
    recommendations: List[str]


class GoalInsight(BaseModel):
    """Insights about goal performance"""
    goal_id: str
    success_probability: float  # 0-100%
    factors_helping: List[str]
    factors_hindering: List[str]
    recommended_actions: List[str]
    similar_users_success_rate: float


class AchievementResponse(BaseModel):
    """Response schema for achievement"""
    achievement_id: str
    title: str
    description: str
    icon: str
    category: str
    tier: str
    points: int
    unlocked: bool
    unlocked_at: Optional[datetime] = None
    progress: float


class AchievementListResponse(BaseModel):
    """Response for listing achievements"""
    achievements: List[AchievementResponse]
    total_unlocked: int
    total_points: int
    next_achievements: List[AchievementResponse]  # Closest to unlocking


class GoalTemplateResponse(BaseModel):
    """Response schema for goal template"""
    id: str
    title: str
    description: str
    type: str
    category: str
    default_duration_days: int
    default_improvement_target: float
    difficulty_level: str
    suitable_for_you: bool
    success_rate: float
    tips: List[str]