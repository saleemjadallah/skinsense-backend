from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Any
from datetime import datetime
from bson import ObjectId


class WeeklyMilestone(BaseModel):
    """Expected progress for each week of the plan"""
    week_number: int
    title: str
    description: str
    expected_improvements: Dict[str, float]  # parameter: expected score
    focus_areas: List[str]
    tips: List[str]


class PlanModel(BaseModel):
    """Main plan model for database - orchestrates existing routines and goals"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    user_id: ObjectId
    
    # Plan basics
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=500)
    plan_type: Literal[
        "hydration_boost", 
        "anti_aging", 
        "acne_control", 
        "brightening",
        "sensitivity_care",
        "texture_improvement",
        "custom"
    ]
    
    # Duration and progress
    duration_weeks: int = Field(..., ge=1, le=12)
    current_week: int = Field(default=1, ge=1)
    status: Literal["active", "paused", "completed", "cancelled"] = "active"
    
    # References to existing user data
    routine_ids: List[ObjectId] = Field(default_factory=list)  # User's existing routines
    goal_ids: List[ObjectId] = Field(default_factory=list)  # User's existing goals  
    base_analysis_id: Optional[ObjectId] = None  # Skin analysis used for creation
    
    # Personalization from user's actual data
    target_concerns: List[str] = Field(default_factory=list)  # From scores <80
    personalization_data: Dict[str, Any] = Field(default_factory=dict)
    # Contains: skin_type, age_group, initial_scores, focus_parameters, user_preferences
    
    # Progress tracking
    weekly_milestones: List[WeeklyMilestone] = Field(default_factory=list)
    effectiveness_predictions: Dict[str, float] = Field(default_factory=dict)
    # Predicted improvements for each skin parameter
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Additional metadata
    completion_rate: float = Field(default=0.0)  # Overall completion percentage
    adherence_score: float = Field(default=0.0)  # How well user follows the plan
    ai_insights: Optional[str] = None  # AI-generated insights about progress
    notes: Optional[str] = None
    
    def calculate_completion(self) -> float:
        """Calculate overall plan completion percentage"""
        if self.duration_weeks == 0:
            return 0.0
        return min(100.0, (self.current_week / self.duration_weeks) * 100)
    
    def is_week_complete(self) -> bool:
        """Check if current week is complete"""
        # This would check routine completions for the week
        return self.current_week > 1
    
    def get_current_milestone(self) -> Optional[WeeklyMilestone]:
        """Get the current week's milestone"""
        for milestone in self.weekly_milestones:
            if milestone.week_number == self.current_week:
                return milestone
        return None


class PlanProgress(BaseModel):
    """Track weekly progress for a plan"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    plan_id: ObjectId
    user_id: ObjectId
    week_number: int
    
    # Completion statistics
    completion_stats: Dict[str, Any] = Field(default_factory=dict)
    # Contains: routines_completed, routines_total, adherence_rate, days_active
    
    # Skin improvements (actual current scores)
    skin_improvements: Dict[str, float] = Field(default_factory=dict)
    # Maps parameter names to current scores
    
    # Milestone tracking
    milestone_achieved: bool = False
    milestone_notes: Optional[str] = None
    
    # User feedback
    user_mood: Optional[Literal["great", "good", "okay", "challenging"]] = None
    user_notes: Optional[str] = None
    
    # Timestamps
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    week_start_date: datetime
    week_end_date: datetime


class PlanTemplate(BaseModel):
    """Pre-built plan templates that can be personalized"""
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    name: str
    description: str
    plan_type: str
    duration_weeks: int
    
    # Target audience
    suitable_for_concerns: List[str]  # acne, dryness, aging, etc.
    suitable_for_skin_types: List[str]  # dry, oily, combination, etc.
    difficulty_level: Literal["beginner", "intermediate", "advanced"]
    
    # Template structure
    routine_requirements: List[Dict[str, Any]]  # What routines need to be created
    goal_templates: List[Dict[str, Any]]  # What goals to create
    weekly_structure: List[Dict[str, Any]]  # Week-by-week plan
    
    # Expected outcomes
    expected_improvements: Dict[str, float]
    success_criteria: List[str]
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    usage_count: int = Field(default=0)
    average_completion_rate: float = Field(default=0.0)
    user_rating: float = Field(default=0.0)