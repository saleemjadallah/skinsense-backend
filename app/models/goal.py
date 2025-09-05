from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Any
from datetime import datetime
from bson import ObjectId


class Milestone(BaseModel):
    """Goal milestone"""
    milestone_id: str = Field(default_factory=lambda: str(ObjectId()))
    title: str
    description: Optional[str] = None
    target_value: Optional[float] = None  # For parameter-based milestones
    target_date: Optional[datetime] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    reward_message: Optional[str] = None
    percentage_trigger: Optional[int] = None  # e.g., 25, 50, 75, 100


class GoalModel(BaseModel):
    """Main goal model for database"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    user_id: ObjectId
    
    # Goal basics
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=500)
    type: Literal["parameter_improvement", "routine_adherence", "holistic", "custom"]
    category: Optional[str] = None  # hydration, acne, etc.
    
    # Target specifics
    target_parameter: Optional[str] = None  # One of our 10 parameters
    baseline_value: float = Field(default=0.0)
    target_value: float
    current_value: float = Field(default=0.0)
    improvement_target: Optional[float] = None  # Percentage or points improvement
    
    # Timeline
    start_date: datetime = Field(default_factory=datetime.utcnow)
    target_date: datetime
    duration_days: int
    
    # Progress tracking
    progress_percentage: float = Field(default=0.0)
    milestones: List[Milestone] = Field(default_factory=list)
    check_in_frequency: Literal["daily", "weekly", "biweekly"] = "weekly"
    last_check_in: Optional[datetime] = None
    
    # Integration
    linked_routine_id: Optional[ObjectId] = None
    linked_analysis_ids: List[ObjectId] = Field(default_factory=list)
    recommended_products: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Status
    status: Literal["active", "completed", "abandoned", "paused"] = "active"
    completed_at: Optional[datetime] = None
    abandoned_at: Optional[datetime] = None
    abandon_reason: Optional[str] = None
    
    # Gamification
    difficulty_level: Literal["easy", "moderate", "challenging"] = "moderate"
    reward_points: int = Field(default=100)
    achievement_unlocked: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # AI generation metadata
    ai_generated: bool = False
    generation_reason: Optional[str] = None  # Why AI suggested this goal
    confidence_score: Optional[float] = None  # AI confidence in achievability
    
    def calculate_progress(self) -> float:
        """Calculate progress percentage based on current value or time elapsed"""
        if self.type == "parameter_improvement":
            # If we have actual measurements, use value-based progress
            if self.current_value != self.baseline_value:
                if self.baseline_value == self.target_value:
                    return 100.0
                progress = (self.current_value - self.baseline_value) / (self.target_value - self.baseline_value) * 100
                return max(0, min(100, progress))
            else:
                # Fall back to time-based progress if no measurements yet
                # This gives users a sense of progress even without new scans
                days_elapsed = (datetime.utcnow() - self.start_date).days
                time_progress = (days_elapsed / self.duration_days) * 100 if self.duration_days > 0 else 0
                # Cap time-based progress at 50% to encourage actual measurements
                return min(50, time_progress)
        elif self.type == "routine_adherence":
            # For routine goals, progress is based on days completed
            days_elapsed = (datetime.utcnow() - self.start_date).days
            return min(100, (days_elapsed / self.duration_days) * 100)
        else:
            # For holistic or custom goals, check if we have time-based progress
            if self.progress_percentage > 0:
                return self.progress_percentage
            else:
                # Use time-based progress as fallback
                days_elapsed = (datetime.utcnow() - self.start_date).days
                time_progress = (days_elapsed / self.duration_days) * 100 if self.duration_days > 0 else 0
                return min(100, time_progress)
    
    def get_days_remaining(self) -> int:
        """Calculate days remaining to target date"""
        remaining = (self.target_date - datetime.utcnow()).days
        return max(0, remaining)
    
    def is_overdue(self) -> bool:
        """Check if goal is past target date"""
        return datetime.utcnow() > self.target_date and self.status == "active"
    
    def get_time_progress(self) -> float:
        """Calculate time-based progress percentage"""
        days_elapsed = (datetime.utcnow() - self.start_date).days
        if self.duration_days > 0:
            return min(100, (days_elapsed / self.duration_days) * 100)
        return 0.0
    
    def get_value_progress(self) -> float:
        """Calculate value-based progress percentage for parameter goals"""
        if self.type == "parameter_improvement":
            if self.baseline_value == self.target_value:
                return 100.0
            if self.current_value != self.baseline_value:
                progress = (self.current_value - self.baseline_value) / (self.target_value - self.baseline_value) * 100
                return max(0, min(100, progress))
        return 0.0


class GoalProgress(BaseModel):
    """Track progress updates for a goal"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    goal_id: ObjectId
    user_id: ObjectId
    
    # Progress data
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    parameter_value: Optional[float] = None  # For parameter goals
    routine_completed: Optional[bool] = None  # For routine goals
    notes: Optional[str] = None
    
    # Source of update
    source: Literal["manual", "analysis", "routine", "system"] = "manual"
    source_id: Optional[ObjectId] = None  # analysis_id or routine_completion_id


class Achievement(BaseModel):
    """User achievements"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    
    # Achievement definition
    achievement_id: str  # Unique identifier for the achievement type
    title: str
    description: str
    icon: str  # Icon identifier
    category: Literal["goal", "parameter", "routine", "streak", "special"]
    tier: Literal["bronze", "silver", "gold", "platinum"] = "bronze"
    
    # Unlock criteria
    criteria: Dict[str, Any]  # Flexible criteria definition
    points: int = Field(default=50)
    
    # User-specific data
    user_id: Optional[ObjectId] = None
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None
    progress: float = Field(default=0.0)  # Progress towards unlocking


class GoalTemplate(BaseModel):
    """Pre-defined goal templates"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    
    # Template info
    title: str
    description: str
    type: Literal["parameter_improvement", "routine_adherence", "holistic"]
    category: str  # hydration, acne, etc.
    
    # Default values
    default_duration_days: int
    default_improvement_target: float
    difficulty_level: Literal["easy", "moderate", "challenging"]
    
    # Target demographics
    suitable_for_age_groups: List[str] = Field(default_factory=list)
    suitable_for_skin_types: List[str] = Field(default_factory=list)
    suitable_for_concerns: List[str] = Field(default_factory=list)
    
    # Milestones template
    milestone_templates: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Success tips
    tips: List[str] = Field(default_factory=list)
    recommended_products: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Popularity
    usage_count: int = Field(default=0)
    success_rate: float = Field(default=0.0)