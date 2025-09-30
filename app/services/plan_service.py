import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from pymongo.database import Database

from app.models.plan import PlanModel, PlanProgress, WeeklyMilestone, PlanTemplate
# from app.models.routine import RoutineModel  # Disabled - old routine model
from app.models.goal import GoalModel
from app.models.user import UserModel
from app.schemas.plan import PlanCreateRequest, PlanUpdateRequest, PlanProgressUpdate
from app.database import get_database
from app.services.openai_service import OpenAIService
# from app.services.routine_service import RoutineService # Disabled - old routine service
from app.services.goal_service import GoalService
from app.utils.database_manager import DatabaseManager
from app.utils.datetime_util import DateTimeUtil

logger = logging.getLogger(__name__)


class PlanService:
    """Service for managing personalized skincare plans"""
    
    def __init__(self):
        # Use DatabaseManager for consistent connection handling
        self.db = None
        self._ensure_db_connection()
            
        self.openai_service = OpenAIService()
        # self.routine_service = RoutineService() # Disabled
        self.goal_service = GoalService()
    
    def _ensure_db_connection(self):
        """Ensure database connection is established"""
        if self.db is None:
            self.db = DatabaseManager.get_database()
        
        # Plan type configurations
        self.plan_configs = {
            "hydration_boost": {
                "name": "Hydration Revival Journey",
                "duration_weeks": 3,
                "focus_parameters": ["hydration", "smoothness", "radiance"],
                "description": "Intensive hydration program to restore skin moisture"
            },
            "anti_aging": {
                "name": "Age-Defying Transformation",
                "duration_weeks": 8,
                "focus_parameters": ["firmness", "fine_lines_wrinkles", "radiance"],
                "description": "Comprehensive anti-aging protocol for youthful skin"
            },
            "acne_control": {
                "name": "Clear Skin Breakthrough",
                "duration_weeks": 6,
                "focus_parameters": ["acne", "redness", "smoothness"],
                "description": "Targeted acne treatment and prevention plan"
            },
            "brightening": {
                "name": "Radiance Restoration",
                "duration_weeks": 4,
                "focus_parameters": ["radiance", "dark_spots", "overall_skin_health_score"],
                "description": "Brighten and even out skin tone"
            },
            "sensitivity_care": {
                "name": "Gentle Healing Protocol",
                "duration_weeks": 4,
                "focus_parameters": ["redness", "hydration", "smoothness"],
                "description": "Soothe and strengthen sensitive skin"
            },
            "texture_improvement": {
                "name": "Smooth Perfection Plan",
                "duration_weeks": 5,
                "focus_parameters": ["smoothness", "acne", "dark_spots"],
                "description": "Refine skin texture and minimize pores"
            },
            "custom": {
                "name": "Personalized Skincare Journey",
                "duration_weeks": 4,
                "focus_parameters": [],
                "description": "Custom plan tailored to your unique skin needs"
            }
        }
    
    def generate_ai_plan(
        self,
        user_id: str,
        plan_type: Optional[str] = None,
        custom_preferences: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate a personalized plan using AI based on user's data"""
        
        try:
            user_oid = ObjectId(user_id)
            
            # Get user's latest skin analysis
            analysis = self.db.skin_analyses.find_one(
                {"user_id": user_oid},
                sort=[("created_at", -1)]
            )
            
            if not analysis:
                raise ValueError("No skin analysis found. Please complete skin analysis first.")
            
            # Get user profile
            user = self.db.users.find_one({"_id": user_oid})
            if not user:
                raise ValueError("User not found")
            
            # Get user's existing routines
            existing_routines = list(self.db.routines.find({
                "user_id": user_oid,
                "is_active": True
            }))
            
            # Get user's active goals
            existing_goals = list(self.db.goals.find({
                "user_id": user_oid,
                "status": "active"
            }))
            
            # Extract skin scores
            skin_scores = analysis.get("orbo_response", {})
            
            # Identify concerns (scores < 80)
            concerns = []
            for param, score in skin_scores.items():
                if isinstance(score, (int, float)) and score < 80:
                    concerns.append({
                        "parameter": param,
                        "score": score,
                        "severity": "high" if score < 50 else "medium" if score < 70 else "low"
                    })
            
            # Sort concerns by severity
            concerns.sort(key=lambda x: x["score"])
            top_concerns = concerns[:3] if concerns else []
            
            # Determine plan type if not specified
            if not plan_type:
                plan_type = self._determine_plan_type(top_concerns)
            
            # Get plan configuration
            plan_config = self.plan_configs.get(plan_type, self.plan_configs["custom"])
            
            # Check if we need to create new routines or can reuse existing
            routine_ids = []
            if existing_routines:
                # Check if existing routines address the concerns
                for routine in existing_routines:
                    routine_concerns = routine.get("target_concerns", [])
                    if any(concern["parameter"] in routine_concerns for concern in top_concerns):
                        routine_ids.append(routine["_id"])
            
            # If no suitable routines, generate new ones
            if not routine_ids:
                logger.info("No suitable existing routines found, generating new ones")
                # This would trigger routine generation - simplified for now
                # In production, call routine_service.generate_ai_routine
                pass
            
            # Check goals
            goal_ids = []
            for goal in existing_goals:
                if goal.get("target_parameter") in [c["parameter"] for c in top_concerns]:
                    goal_ids.append(goal["_id"])
            
            # Generate weekly milestones using AI
            milestones = self._generate_weekly_milestones(
                plan_type=plan_type,
                duration_weeks=plan_config["duration_weeks"],
                concerns=top_concerns,
                skin_scores=skin_scores
            )
            
            # Create personalization data
            personalization_data = {
                "skin_type": user.get("skin_type", "unknown"),
                "age_group": user.get("age_group", "unknown"),
                "gender": user.get("gender", "unknown"),
                "initial_scores": skin_scores,
                "focus_parameters": [c["parameter"] for c in top_concerns[:3]],
                "severity_levels": {c["parameter"]: c["severity"] for c in top_concerns}
            }
            
            # Generate effectiveness predictions
            effectiveness_predictions = self._predict_effectiveness(
                plan_type=plan_type,
                duration_weeks=plan_config["duration_weeks"],
                initial_scores=skin_scores,
                concerns=top_concerns
            )
            
            # Create the plan
            plan = PlanModel(
                user_id=user_oid,
                name=plan_config["name"],
                description=plan_config["description"],
                plan_type=plan_type,
                duration_weeks=plan_config["duration_weeks"],
                routine_ids=routine_ids,
                goal_ids=goal_ids,
                base_analysis_id=analysis["_id"],
                target_concerns=[c["parameter"] for c in top_concerns],
                personalization_data=personalization_data,
                weekly_milestones=milestones,
                effectiveness_predictions=effectiveness_predictions,
                started_at=DateTimeUtil.now()
            )
            
            # Save to database
            plan_dict = plan.dict(by_alias=True, exclude={"id"})
            result = self.db.plans.insert_one(plan_dict)
            plan.id = result.inserted_id
            
            # Return the created plan
            return {
                "plan_id": str(result.inserted_id),
                "name": plan.name,
                "description": plan.description,
                "duration_weeks": plan.duration_weeks,
                "target_concerns": plan.target_concerns,
                "routine_count": len(routine_ids),
                "goal_count": len(goal_ids),
                "first_milestone": milestones[0].dict() if milestones else None,
                "effectiveness_predictions": effectiveness_predictions,
                "message": "Your personalized plan has been created!"
            }
            
        except Exception as e:
            logger.error(f"Error generating AI plan: {str(e)}")
            raise
    
    def _determine_plan_type(self, concerns: List[Dict]) -> str:
        """Determine best plan type based on user's concerns"""
        if not concerns:
            return "custom"
        
        # Map concerns to plan types
        concern_mapping = {
            "hydration": "hydration_boost",
            "acne": "acne_control",
            "fine_lines_wrinkles": "anti_aging",
            "firmness": "anti_aging",
            "dark_spots": "brightening",
            "radiance": "brightening",
            "redness": "sensitivity_care",
            "smoothness": "texture_improvement"
        }
        
        # Get the top concern
        top_concern = concerns[0]["parameter"] if concerns else None
        
        return concern_mapping.get(top_concern, "custom")
    
    def _generate_weekly_milestones(
        self,
        plan_type: str,
        duration_weeks: int,
        concerns: List[Dict],
        skin_scores: Dict
    ) -> List[WeeklyMilestone]:
        """Generate weekly milestones with expected progress"""
        
        milestones = []
        
        for week in range(1, duration_weeks + 1):
            # Calculate expected improvements
            progress_rate = week / duration_weeks
            expected_improvements = {}
            
            for concern in concerns[:3]:  # Focus on top 3 concerns
                param = concern["parameter"]
                current_score = concern["score"]
                # Gradual improvement curve
                improvement = min(20, (100 - current_score) * progress_rate * 0.6)
                expected_improvements[param] = current_score + improvement
            
            # Create milestone
            milestone = WeeklyMilestone(
                week_number=week,
                title=f"Week {week}: {self._get_week_theme(plan_type, week, duration_weeks)}",
                description=self._get_week_description(plan_type, week),
                expected_improvements=expected_improvements,
                focus_areas=[c["parameter"] for c in concerns[:2]],
                tips=self._get_week_tips(plan_type, week)
            )
            milestones.append(milestone)
        
        return milestones
    
    def _get_week_theme(self, plan_type: str, week: int, total_weeks: int) -> str:
        """Get theme for specific week"""
        if week == 1:
            return "Foundation & Assessment"
        elif week == total_weeks:
            return "Mastery & Maintenance"
        elif week <= total_weeks // 2:
            return "Building & Adjusting"
        else:
            return "Optimizing & Perfecting"
    
    def _get_week_description(self, plan_type: str, week: int) -> str:
        """Get description for specific week"""
        descriptions = {
            1: "Establish your routine and let your skin adjust to new products",
            2: "Monitor initial responses and maintain consistency",
            3: "Notice first visible improvements in hydration and texture",
            4: "Deeper changes begin as skin cell turnover completes"
        }
        return descriptions.get(week, f"Continue your journey with focus and consistency")
    
    def _get_week_tips(self, plan_type: str, week: int) -> List[str]:
        """Get tips for specific week"""
        base_tips = [
            "Take progress photos in consistent lighting",
            "Stay hydrated - aim for 8 glasses of water daily",
            "Be patient - skin improvements take time"
        ]
        
        if plan_type == "hydration_boost":
            base_tips.append("Use a humidifier at night for extra moisture")
        elif plan_type == "acne_control":
            base_tips.append("Avoid touching your face throughout the day")
        elif plan_type == "anti_aging":
            base_tips.append("Never skip sunscreen, even on cloudy days")
            
        return base_tips[:3]
    
    def _predict_effectiveness(
        self,
        plan_type: str,
        duration_weeks: int,
        initial_scores: Dict,
        concerns: List[Dict]
    ) -> Dict[str, float]:
        """Predict effectiveness for each parameter"""
        
        predictions = {}
        
        # Base improvement rates by plan type
        improvement_rates = {
            "hydration_boost": {"hydration": 0.7, "smoothness": 0.5, "radiance": 0.4},
            "anti_aging": {"firmness": 0.5, "fine_lines_wrinkles": 0.4, "radiance": 0.5},
            "acne_control": {"acne": 0.6, "redness": 0.5, "smoothness": 0.4},
            "brightening": {"radiance": 0.6, "dark_spots": 0.5, "overall_skin_health_score": 0.4},
            "sensitivity_care": {"redness": 0.6, "hydration": 0.5, "smoothness": 0.4},
            "texture_improvement": {"smoothness": 0.6, "acne": 0.4, "dark_spots": 0.3}
        }
        
        rates = improvement_rates.get(plan_type, {})
        
        for param, initial_score in initial_scores.items():
            if isinstance(initial_score, (int, float)):
                # Calculate potential improvement
                room_for_improvement = 100 - initial_score
                base_rate = rates.get(param, 0.3)  # Default 30% improvement
                
                # Adjust based on duration
                duration_factor = min(1.0, duration_weeks / 8)  # Max benefit at 8 weeks
                
                predicted_improvement = room_for_improvement * base_rate * duration_factor
                predictions[param] = min(100, initial_score + predicted_improvement)
        
        return predictions
    
    def get_user_plans(self, user_id: str, status: Optional[str] = None) -> List[Dict]:
        """Get all plans for a user with optimized performance"""
        
        self._ensure_db_connection()
        
        try:
            query = {"user_id": ObjectId(user_id)}
            if status:
                query["status"] = status
            
            # Use projection to only fetch needed fields for better performance
            projection = {
                "_id": 1,
                "name": 1,
                "description": 1,
                "plan_type": 1,
                "status": 1,
                "current_week": 1,
                "duration_weeks": 1,
                "routine_ids": 1,
                "goal_ids": 1,
                "target_concerns": 1,
                "created_at": 1,
                "started_at": 1
            }
            
            plans = list(self.db.plans.find(query, projection).sort("created_at", -1))
            
            result = []
            for plan in plans:
                # Count non-null IDs for better accuracy
                routine_count = len([rid for rid in plan.get("routine_ids", []) if rid is not None])
                goal_count = len([gid for gid in plan.get("goal_ids", []) if gid is not None])
                
                # Calculate completion rate more safely
                current_week = plan.get("current_week", 1)
                duration_weeks = plan.get("duration_weeks", 4)
                completion_rate = min(100, (current_week / duration_weeks) * 100) if duration_weeks > 0 else 0
                
                result.append({
                    "id": str(plan["_id"]),
                    "name": plan.get("name", "Unnamed Plan"),
                    "description": plan.get("description", ""),
                    "plan_type": plan.get("plan_type", "custom"),
                    "status": plan.get("status", "active"),
                    "current_week": current_week,
                    "duration_weeks": duration_weeks,
                    "completion_rate": completion_rate,
                    "routine_count": routine_count,
                    "goal_count": goal_count,
                    "target_concerns": plan.get("target_concerns", []),
                    "created_at": DateTimeUtil.format_iso(plan.get("created_at", DateTimeUtil.now())),
                    "started_at": plan.get("started_at").isoformat() if plan.get("started_at") else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_user_plans: {str(e)}")
            raise
    
    def get_plan_details(self, plan_id: str) -> Dict[str, Any]:
        """Get detailed plan information with optimized queries"""
        
        self._ensure_db_connection()
        
        try:
            # Validate plan_id first
            if not plan_id or plan_id == "None":
                raise ValueError("Invalid plan ID provided")
            
            # Use aggregation pipeline for better performance
            pipeline = [
                {"$match": {"_id": ObjectId(plan_id)}},
                {
                    "$lookup": {
                        "from": "routines",
                        "localField": "routine_ids",
                        "foreignField": "_id",
                        "as": "routines"
                    }
                },
                {
                    "$lookup": {
                        "from": "goals",
                        "localField": "goal_ids",
                        "foreignField": "_id",
                        "as": "goals"
                    }
                },
                {
                    "$lookup": {
                        "from": "plan_progress",
                        "let": {"plan_id": "$_id"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["$plan_id", "$$plan_id"]}}},
                            {"$sort": {"week_number": -1}},
                            {"$limit": 1}
                        ],
                        "as": "latest_progress"
                    }
                }
            ]
            
            result = list(self.db.plans.aggregate(pipeline))
            if not result:
                raise ValueError("Plan not found")
                
            plan = result[0]
            routines = plan.get("routines", [])
            goals = plan.get("goals", [])
            latest_progress = plan.get("latest_progress", [{}])[0] if plan.get("latest_progress") else None
            
            # Check if today is marked complete and count weekly progress in parallel
            today = DateTimeUtil.today_start()
            week_start, week_end = DateTimeUtil.current_week_range()
            
            # Use aggregation for daily progress stats
            daily_progress_pipeline = [
                {
                    "$match": {
                        "plan_id": ObjectId(plan_id),
                        "date": {"$gte": week_start, "$lte": week_end}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "days_completed": {"$sum": {"$cond": ["$completed", 1, 0]}},
                        "today_completed": {
                            "$max": {
                                "$cond": [
                                    {"$and": [{"$eq": ["$date", today]}, "$completed"]},
                                    True,
                                    False
                                ]
                            }
                        }
                    }
                }
            ]
            
            daily_stats = list(self.db.plan_daily_progress.aggregate(daily_progress_pipeline))
            if daily_stats:
                days_completed_this_week = daily_stats[0].get("days_completed", 0)
                today_completed = daily_stats[0].get("today_completed", False)
            else:
                days_completed_this_week = 0
                today_completed = False
        
            # Calculate current week stats with better performance
            current_week_stats = {
                "completion_rate": (days_completed_this_week / 7) * 100 if days_completed_this_week > 0 else 0,
                "routines_completed": sum(1 for r in routines if r.get("completion_count", 0) > 0),
                "goals_progress": sum(g.get("progress_percentage", 0) for g in goals) / len(goals) if goals else 0,
                "today_completed": today_completed,
                "days_completed_this_week": days_completed_this_week
            }
        except Exception as e:
            logger.error(f"Error in optimized get_plan_details: {str(e)}")
            # Fallback to original method if aggregation fails
            return self._get_plan_details_fallback(plan_id)
        
        return {
            "id": str(plan["_id"]),
            "user_id": str(plan["user_id"]) if plan.get("user_id") else None,
            "name": plan.get("name", "Unnamed Plan"),
            "description": plan.get("description", ""),
            "plan_type": plan.get("plan_type", "custom"),
            "status": plan.get("status", "active"),
            "current_week": plan.get("current_week", 1),
            "duration_weeks": plan.get("duration_weeks", 4),
            "started_at": DateTimeUtil.format_iso(plan.get("started_at", plan.get("created_at", DateTimeUtil.now()))),
            "target_concerns": plan.get("target_concerns", []),
            "personalization_data": plan.get("personalization_data", {}),
            "current_milestone": next(
                (m for m in plan.get("weekly_milestones", []) 
                 if m.get("week", m.get("week_number")) == plan.get("current_week", 1)),
                None
            ),
            "routines": [
                {
                    "id": str(r["_id"]),
                    "name": r.get("name", "Unnamed Routine"),
                    "type": r.get("type", "custom"),
                    "completion_count": r.get("completion_count", 0),
                    "completed_today": r.get("last_completed") and r.get("last_completed").date() == today.date()
                }
                for r in routines
            ],
            "goals": [
                {
                    "id": str(g["_id"]),
                    "title": g.get("title", "Unnamed Goal"),
                    "progress_percentage": g.get("progress_percentage", 0)
                }
                for g in goals
            ],
            "current_week_stats": current_week_stats,
            "effectiveness_predictions": plan.get("effectiveness_predictions", {}),
            "latest_progress": {
                "week_number": latest_progress.get("week_number", 1),
                "skin_improvements": latest_progress.get("skin_improvements", {}),
                "milestone_achieved": latest_progress.get("milestone_achieved", False)
            } if latest_progress else None
        }
    
    def _get_plan_details_fallback(self, plan_id: str) -> Dict[str, Any]:
        """Fallback method for getting plan details if aggregation fails"""
        
        plan = self.db.plans.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            raise ValueError("Plan not found")
        
        # Filter out None values from routine_ids and goal_ids
        routine_ids = [rid for rid in plan.get("routine_ids", []) if rid is not None]
        goal_ids = [gid for gid in plan.get("goal_ids", []) if gid is not None]
        
        # Get associated routines
        routines = []
        if routine_ids:
            routines = list(self.db.routines.find({
                "_id": {"$in": routine_ids}
            }))
        
        # Get associated goals
        goals = []
        if goal_ids:
            goals = list(self.db.goals.find({
                "_id": {"$in": goal_ids}
            }))
        
        # Get latest progress
        latest_progress = self.db.plan_progress.find_one(
            {"plan_id": ObjectId(plan_id)},
            sort=[("week_number", -1)]
        )
        
        # Check if today is marked complete
        today = DateTimeUtil.today_start()
        today_progress = self.db.plan_daily_progress.find_one({
            "plan_id": ObjectId(plan_id),
            "date": today
        })
        today_completed = today_progress.get("completed", False) if today_progress else False
        
        # Count completed days this week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        days_completed_this_week = self.db.plan_daily_progress.count_documents({
            "plan_id": ObjectId(plan_id),
            "date": {"$gte": week_start, "$lte": week_end},
            "completed": True
        })
        
        # Calculate current week stats
        current_week_stats = {
            "completion_rate": (days_completed_this_week / 7) * 100 if days_completed_this_week > 0 else 0,
            "routines_completed": sum(1 for r in routines if r.get("completion_count", 0) > 0),
            "goals_progress": sum(g.get("progress_percentage", 0) for g in goals) / len(goals) if goals else 0,
            "today_completed": today_completed,
            "days_completed_this_week": days_completed_this_week
        }
        
        return {
            "id": str(plan["_id"]),
            "user_id": str(plan["user_id"]) if plan.get("user_id") else None,
            "name": plan.get("name", "Unnamed Plan"),
            "description": plan.get("description", ""),
            "plan_type": plan.get("plan_type", "custom"),
            "status": plan.get("status", "active"),
            "current_week": plan.get("current_week", 1),
            "duration_weeks": plan.get("duration_weeks", 4),
            "started_at": DateTimeUtil.format_iso(plan.get("started_at", plan.get("created_at", DateTimeUtil.now()))),
            "target_concerns": plan.get("target_concerns", []),
            "personalization_data": plan.get("personalization_data", {}),
            "current_milestone": next(
                (m for m in plan.get("weekly_milestones", []) 
                 if m.get("week", m.get("week_number")) == plan.get("current_week", 1)),
                None
            ),
            "routines": [
                {
                    "id": str(r["_id"]),
                    "name": r.get("name", "Unnamed Routine"),
                    "type": r.get("type", "custom"),
                    "completion_count": r.get("completion_count", 0),
                    "completed_today": self.db.routine_completions.find_one({
                        "routine_id": r["_id"],
                        "user_id": plan["user_id"],
                        "completed_at": {"$gte": today, "$lt": today + timedelta(days=1)}
                    }) is not None
                }
                for r in routines
            ],
            "goals": [
                {
                    "id": str(g["_id"]),
                    "title": g.get("title", "Unnamed Goal"),
                    "progress_percentage": g.get("progress_percentage", 0)
                }
                for g in goals
            ],
            "current_week_stats": current_week_stats,
            "effectiveness_predictions": plan.get("effectiveness_predictions", {}),
            "latest_progress": {
                "week_number": latest_progress.get("week_number", 1),
                "skin_improvements": latest_progress.get("skin_improvements", {}),
                "milestone_achieved": latest_progress.get("milestone_achieved", False)
            } if latest_progress else None
        }
    
    def _calculate_week_stats(self, plan_id: str, week_number: int) -> Dict:
        """Calculate statistics for current week"""
        
        # Get plan
        plan = self.db.plans.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            return {}
        
        # Calculate week date range
        week_start, week_end = DateTimeUtil.current_week_range()
        
        # Count routine completions this week
        routine_completions = self.db.routine_completions.count_documents({
            "routine_id": {"$in": plan.get("routine_ids", [])},
            "completed_at": {"$gte": week_start, "$lte": week_end}
        })
        
        # Expected completions (assuming daily routines)
        expected_completions = len(plan.get("routine_ids", [])) * 7
        
        return {
            "routines_completed": routine_completions,
            "routines_expected": expected_completions,
            "completion_rate": (routine_completions / expected_completions * 100) if expected_completions > 0 else 0,
            "days_remaining": DateTimeUtil.days_until(week_end)
        }
    
    def update_plan_progress(
        self,
        plan_id: str,
        week_number: int,
        progress_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update weekly progress for a plan"""
        
        plan = self.db.plans.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            raise ValueError("Plan not found")
        
        # Create progress entry
        progress = PlanProgress(
            plan_id=ObjectId(plan_id),
            user_id=plan["user_id"],
            week_number=week_number,
            completion_stats=progress_data.get("completion_stats", {}),
            skin_improvements=progress_data.get("skin_improvements", {}),
            milestone_achieved=progress_data.get("milestone_achieved", False),
            user_mood=progress_data.get("user_mood"),
            user_notes=progress_data.get("user_notes"),
            week_start_date=DateTimeUtil.current_week_range()[0],
            week_end_date=DateTimeUtil.current_week_range()[1]
        )
        
        # Save progress
        progress_dict = progress.dict(by_alias=True)
        self.db.plan_progress.insert_one(progress_dict)
        
        # Update plan current week if milestone achieved
        if progress_data.get("milestone_achieved") and week_number == plan["current_week"]:
            self.db.plans.update_one(
                {"_id": ObjectId(plan_id)},
                {
                    "$set": {
                        "current_week": min(week_number + 1, plan["duration_weeks"]),
                        "last_activity": DateTimeUtil.now()
                    }
                }
            )
        
        return {"success": True, "message": "Progress updated successfully"}
    
    def complete_day(self, plan_id: str) -> Dict[str, Any]:
        """Mark today as complete for the plan"""
        
        plan = self.db.plans.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            raise ValueError("Plan not found")
        
        # Track daily completion - use datetime not date for MongoDB
        today = DateTimeUtil.today_start()
        
        # Create or update daily progress record
        daily_progress = {
            "plan_id": ObjectId(plan_id),
            "user_id": plan["user_id"],
            "date": today,
            "completed": True,
            "completed_at": DateTimeUtil.now(),
            "week_number": plan.get("current_week", 1)
        }
        
        # Upsert daily progress (update if exists, insert if not)
        self.db.plan_daily_progress.update_one(
            {
                "plan_id": ObjectId(plan_id),
                "date": today
            },
            {"$set": daily_progress},
            upsert=True
        )
        
        # Count completed days this week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        completed_days = self.db.plan_daily_progress.count_documents({
            "plan_id": ObjectId(plan_id),
            "date": {"$gte": week_start, "$lte": week_end},
            "completed": True
        })
        
        # Update plan's last activity
        self.db.plans.update_one(
            {"_id": ObjectId(plan_id)},
            {
                "$set": {
                    "last_activity": DateTimeUtil.now(),
                    "days_completed_this_week": completed_days
                }
            }
        )
        
        return {
            "success": True,
            "message": "Day marked as complete",
            "date": today.strftime("%Y-%m-%d"),
            "days_completed_this_week": completed_days,
            "current_week": plan.get("current_week", 1)
        }
    
    def complete_week(self, plan_id: str) -> Dict[str, Any]:
        """Mark current week as complete and advance to next"""
        
        plan = self.db.plans.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            raise ValueError("Plan not found")
        
        current_week = plan["current_week"]
        
        if current_week >= plan["duration_weeks"]:
            # Plan is complete
            self.db.plans.update_one(
                {"_id": ObjectId(plan_id)},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": DateTimeUtil.now(),
                        "last_activity": DateTimeUtil.now()
                    }
                }
            )
            return {"success": True, "message": "Congratulations! You've completed your plan!"}
        
        # Advance to next week
        self.db.plans.update_one(
            {"_id": ObjectId(plan_id)},
            {
                "$set": {
                    "current_week": current_week + 1,
                    "last_activity": datetime.utcnow()
                }
            }
        )
        
        return {
            "success": True,
            "message": f"Week {current_week} complete! Starting week {current_week + 1}"
        }
    
    def get_plan_insights(self, plan_id: str) -> Dict[str, Any]:
        """Generate AI insights about plan progress"""
        
        plan = self.db.plans.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            raise ValueError("Plan not found")
        
        # Get all progress entries
        progress_entries = list(self.db.plan_progress.find(
            {"plan_id": ObjectId(plan_id)}
        ).sort("week_number", 1))
        
        if not progress_entries:
            return {
                "insights": "Start completing your routines to see personalized insights!",
                "recommendations": []
            }
        
        # Use OpenAI to generate insights
        prompt = f"""
        Analyze this skincare plan progress and provide insights:
        
        Plan Type: {plan['plan_type']}
        Current Week: {plan['current_week']} of {plan['duration_weeks']}
        Target Concerns: {', '.join(plan.get('target_concerns', []))}
        
        Progress Data:
        {json.dumps([{
            'week': p['week_number'],
            'completion_rate': p.get('completion_stats', {}).get('adherence_rate', 0),
            'improvements': p.get('skin_improvements', {})
        } for p in progress_entries], indent=2)}
        
        Provide:
        1. Key observations about their progress
        2. Areas doing well
        3. Areas needing attention
        4. Specific recommendations for next week
        
        Keep response concise and actionable.
        """
        
        try:
            insights = self.openai_service.generate_completion(
                prompt=prompt,
                system_message="You are a skincare expert analyzing user progress.",
                temperature=0.7,
                max_tokens=400
            )
            
            return {
                "insights": insights,
                "current_week": plan["current_week"],
                "completion_percentage": (plan["current_week"] / plan["duration_weeks"]) * 100,
                "weeks_remaining": plan["duration_weeks"] - plan["current_week"]
            }
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return {
                "insights": "Keep up the great work! Consistency is key to achieving your skincare goals.",
                "recommendations": ["Continue with your daily routines", "Take weekly progress photos"]
            }