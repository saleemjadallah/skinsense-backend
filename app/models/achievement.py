from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId


class AchievementCategory(str, Enum):
    JOURNEY_MILESTONES = "journey_milestones"
    ANALYSIS_PROGRESS = "analysis_progress"
    PRODUCT_DISCOVERY = "product_discovery"
    COMMUNITY_ENGAGEMENT = "community_engagement"


class AchievementDifficulty(str, Enum):
    STARTER = "starter"  # 10-20 points
    EASY = "easy"  # 25-50 points
    MEDIUM = "medium"  # 60-100 points
    HARD = "hard"  # 100+ points


class AchievementTriggerType(str, Enum):
    FIRST_ANALYSIS = "first_analysis"
    STREAK = "streak"
    PHOTO_COUNT = "photo_count"
    SCORE_IMPROVEMENT = "score_improvement"
    CONSECUTIVE_IMPROVEMENT = "consecutive_improvement"
    FIRST_GOAL = "first_goal"
    HYDRATION_MAINTENANCE = "hydration_maintenance"
    INGREDIENTS_LEARNED = "ingredients_learned"
    COMPLETE_ROUTINE = "complete_routine"
    TIPS_SHARED = "tips_shared"
    MEMBERS_HELPED = "members_helped"


class AchievementDefinition(BaseModel):
    """Static achievement definition"""
    achievement_id: str
    title: str
    description: str
    badge_path: str
    background_badge_path: str
    category: AchievementCategory
    difficulty: AchievementDifficulty
    points: int
    trigger_condition: Dict[str, Any]
    emoji: Optional[str] = None


class UserAchievement(BaseModel):
    """User's achievement progress"""
    user_id: str
    achievement_id: str
    progress: float = Field(default=0.0, ge=0.0, le=1.0)  # 0.0 to 1.0
    is_unlocked: bool = False
    unlocked_at: Optional[datetime] = None
    progress_data: Dict[str, Any] = Field(default_factory=dict)  # Store detailed progress info
    last_updated: datetime = Field(default_factory=datetime.now)
    verified: bool = False  # Backend verification status
    verified_at: Optional[datetime] = None


class AchievementProgress(BaseModel):
    """Progress update from client"""
    achievement_id: str
    progress: float
    progress_data: Dict[str, Any] = Field(default_factory=dict)
    client_timestamp: datetime


class AchievementSync(BaseModel):
    """Batch sync from client"""
    achievements: List[AchievementProgress]
    device_id: Optional[str] = None
    sync_timestamp: datetime = Field(default_factory=datetime.now)


class AchievementAction(BaseModel):
    """User action that might trigger achievement progress"""
    action_type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


# Achievement definitions (matching frontend)
ACHIEVEMENT_DEFINITIONS = [
    # Journey Milestones
    AchievementDefinition(
        achievement_id="first_glow",
        title="First Glow",
        description="Complete your first skin analysis",
        badge_path="assets/Achievement badges/First Glow.png",
        background_badge_path="assets/Achievement badges/with bg/First Glow bg.png",
        category=AchievementCategory.JOURNEY_MILESTONES,
        difficulty=AchievementDifficulty.STARTER,
        points=10,
        trigger_condition={"type": "first_analysis"},
        emoji="⭐"
    ),
    AchievementDefinition(
        achievement_id="week_warrior",
        title="Week Warrior",
        description="7-day streak of daily check-ins",
        badge_path="assets/Achievement badges/Week Warrior.png",
        background_badge_path="assets/Achievement badges/with bg/Week Warrior bg.png",
        category=AchievementCategory.JOURNEY_MILESTONES,
        difficulty=AchievementDifficulty.EASY,
        points=25,
        trigger_condition={"type": "streak", "days": 7},
        emoji="🗓️"
    ),
    AchievementDefinition(
        achievement_id="consistency_ruler",
        title="Consistency King/Queen",
        description="30-day streak of routine maintained",
        badge_path="assets/Achievement badges/Consistency King-Queen.png",
        background_badge_path="assets/Achievement badges/with bg/Consistency King-Queen bg.png",
        category=AchievementCategory.JOURNEY_MILESTONES,
        difficulty=AchievementDifficulty.MEDIUM,
        points=100,
        trigger_condition={"type": "streak", "days": 30},
        emoji="👑"
    ),
    
    # Analysis & Progress
    AchievementDefinition(
        achievement_id="progress_pioneer",
        title="Progress Pioneer",
        description="Upload 10 progress photos",
        badge_path="assets/Achievement badges/Progress Pioneer.png",
        background_badge_path="assets/Achievement badges/with bg/Progress Pioneer bg.png",
        category=AchievementCategory.ANALYSIS_PROGRESS,
        difficulty=AchievementDifficulty.EASY,
        points=50,
        trigger_condition={"type": "photo_count", "count": 10},
        emoji="📈"
    ),
    AchievementDefinition(
        achievement_id="glow_up",
        title="Glow Up",
        description="Achieve 10+ point improvement in skin score",
        badge_path="assets/Achievement badges/Glow Up.png",
        background_badge_path="assets/Achievement badges/with bg/Glow up bg.png",
        category=AchievementCategory.ANALYSIS_PROGRESS,
        difficulty=AchievementDifficulty.MEDIUM,
        points=75,
        trigger_condition={"type": "score_improvement", "points": 10},
        emoji="🌟"
    ),
    AchievementDefinition(
        achievement_id="steady_improver",
        title="Steady Improver",
        description="Show improvement for 4 weeks straight",
        badge_path="assets/Achievement badges/Steady Improver.png",
        background_badge_path="assets/Achievement badges/with bg/ Steady Improver bg.png",
        category=AchievementCategory.ANALYSIS_PROGRESS,
        difficulty=AchievementDifficulty.MEDIUM,
        points=80,
        trigger_condition={"type": "consecutive_improvement", "weeks": 4},
        emoji="📊"
    ),
    AchievementDefinition(
        achievement_id="baseline_boss",
        title="Baseline Boss",
        description="Set your first goal",
        badge_path="assets/Achievement badges/Baseline Boss.png",
        background_badge_path="assets/Achievement badges/with bg/Baseline Boss bg.png",
        category=AchievementCategory.ANALYSIS_PROGRESS,
        difficulty=AchievementDifficulty.STARTER,
        points=15,
        trigger_condition={"type": "first_goal"},
        emoji="🎯"
    ),
    AchievementDefinition(
        achievement_id="hydration_hero",
        title="Hydration Hero",
        description="Maintain optimal hydration levels for 2 weeks",
        badge_path="assets/Achievement badges/Hydration Hero.png",
        background_badge_path="assets/Achievement badges/with bg/Hydration Hero bg.png",
        category=AchievementCategory.ANALYSIS_PROGRESS,
        difficulty=AchievementDifficulty.MEDIUM,
        points=70,
        trigger_condition={"type": "hydration_maintenance", "days": 14},
        emoji="💧"
    ),
    
    # Product Discovery
    AchievementDefinition(
        achievement_id="ingredient_inspector",
        title="Ingredient Inspector",
        description="Learn about 25 different ingredients",
        badge_path="assets/Achievement badges/Ingredient Inspector.png",
        background_badge_path="assets/Achievement badges/with bg/Ingredient Inspector bg.png",
        category=AchievementCategory.PRODUCT_DISCOVERY,
        difficulty=AchievementDifficulty.MEDIUM,
        points=60,
        trigger_condition={"type": "ingredients_learned", "count": 25},
        emoji="🔍"
    ),
    AchievementDefinition(
        achievement_id="routine_revolutionary",
        title="Routine Revolutionary",
        description="Build your first complete AM/PM routine",
        badge_path="assets/Achievement badges/Routine Revolutionary.png",
        background_badge_path="assets/Achievement badges/with bg/Routine Revolutionary bg.png",
        category=AchievementCategory.PRODUCT_DISCOVERY,
        difficulty=AchievementDifficulty.EASY,
        points=40,
        trigger_condition={"type": "complete_routine"},
        emoji="🔄"
    ),
    
    # Community Engagement
    AchievementDefinition(
        achievement_id="knowledge_sharer",
        title="Knowledge Sharer",
        description="Share 5 tips with the community",
        badge_path="assets/Achievement badges/Knowledge Sharer.png",
        background_badge_path="assets/Achievement badges/with bg/Knowledge Sharer bg.png",
        category=AchievementCategory.COMMUNITY_ENGAGEMENT,
        difficulty=AchievementDifficulty.EASY,
        points=45,
        trigger_condition={"type": "tips_shared", "count": 5},
        emoji="📚"
    ),
    AchievementDefinition(
        achievement_id="helpful_heart",
        title="Helpful Heart",
        description="Help 10 community members",
        badge_path="assets/Achievement badges/Helpful Heart.png",
        background_badge_path="assets/Achievement badges/with bg/Helpful Heart bg.png",
        category=AchievementCategory.COMMUNITY_ENGAGEMENT,
        difficulty=AchievementDifficulty.MEDIUM,
        points=85,
        trigger_condition={"type": "members_helped", "count": 10},
        emoji="❤️"
    ),
]


def get_achievement_definition(achievement_id: str) -> Optional[AchievementDefinition]:
    """Get achievement definition by ID"""
    for achievement in ACHIEVEMENT_DEFINITIONS:
        if achievement.achievement_id == achievement_id:
            return achievement
    return None


def get_achievements_by_category(category: AchievementCategory) -> List[AchievementDefinition]:
    """Get all achievements in a category"""
    return [a for a in ACHIEVEMENT_DEFINITIONS if a.category == category]