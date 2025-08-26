"""
Personalized Insights Generation Service
Generates 3 daily insights based on user data, avoiding overlap with existing features
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from bson import ObjectId
import random
import openai
import json
from ..utils.date_utils import get_utc_now, should_regenerate_content, calculate_expiry_time
from ..models.insights import (
    DailyInsights, InsightContent, PersonalizationFactors, InsightTemplate
)
from ..models.user import UserModel
from ..models.skin_analysis import SkinAnalysisModel
from ..models.routine import RoutineModel, RoutineCompletion
from ..models.goal import GoalModel, GoalProgress
from ..database import db, get_database
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

class InsightsService:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.db = None  # Will be initialized on first use
        
        # Define insight categories that don't overlap with existing features
        self.non_overlapping_categories = [
            "skin_trend",       # Unique trend analysis
            "environmental",    # Weather/season specific
            "ingredient_focus", # Educational about ingredients
            "prevention",       # Preventive care tips
            "product_tip"       # How to use products better
        ]
    
    def _ensure_db(self):
        """Ensure database connection is initialized"""
        if self.db is None:
            self.db = get_database()
            if self.db is None:
                from ..database import db as database_instance
                self.db = database_instance.database
    
    def generate_daily_insights(self, user_id: str) -> DailyInsights:
        """Generate 3 personalized insights for a user"""
        try:
            logger.info(f"[INSIGHTS_SERVICE] Generating daily insights for user: {user_id}")
            self._ensure_db()
            
            # Check if insights already exist for today
            existing = self._get_today_insights(user_id)
            if existing:
                logger.info(f"[INSIGHTS_SERVICE] Found existing insights for user {user_id}")
                return existing
            
            # Gather user context
            user_data = self._gather_user_context(user_id)
            if not user_data:
                logger.error(f"Could not gather context for user {user_id}")
                return self._generate_fallback_insights(user_id)
            
            # Generate personalized insights
            insights = self._generate_ai_insights(user_data)
            
            # Save to database
            daily_insights = self._save_insights(user_id, insights, user_data)
            
            return daily_insights
            
        except Exception as e:
            logger.error(f"Error generating insights for user {user_id}: {str(e)}")
            return self._generate_fallback_insights(user_id)
    
    def _get_today_insights(self, user_id: str) -> Optional[DailyInsights]:
        """Check if insights already exist for today"""
        self._ensure_db()
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        
        existing = self.db.daily_insights.find_one({
            "user_id": ObjectId(user_id),
            "generated_for_date": start_of_day,  # Use datetime instead of date
            "expires_at": {"$gt": get_utc_now()}
        })
        
        if existing:
            # Check if insights are stale and should be regenerated
            created_at = existing.get('created_at', existing.get('generated_for_date'))
            if should_regenerate_content(created_at, 'insight'):
                logger.info(f"Insights for user {user_id} are stale, will regenerate")
                # Delete stale insights
                self.db.daily_insights.delete_one({"_id": existing["_id"]})
                return None
            
            return DailyInsights(**existing)
        return None
    
    def _gather_user_context(self, user_id: str) -> Dict[str, Any]:
        """Gather comprehensive user context for personalization"""
        self._ensure_db()
        user_oid = ObjectId(user_id)
        
        # Get user profile
        user = self.db.users.find_one({"_id": user_oid})
        if not user:
            return None
        
        # Get latest skin analysis
        latest_analysis = self.db.skin_analyses.find_one(
            {"user_id": user_oid, "status": "completed"},
            sort=[("created_at", -1)]
        )
        
        # Get routine completion rate (last 7 days)
        week_ago = get_utc_now() - timedelta(days=7)
        routine_completions = self.db.routine_completions.count_documents({
            "user_id": user_oid,
            "completed_at": {"$gte": week_ago}
        })
        active_routines = self.db.routines.count_documents({
            "user_id": user_oid,
            "is_active": True
        })
        completion_rate = (routine_completions / (active_routines * 7)) if active_routines > 0 else 0
        
        # Get active goals
        active_goals = list(self.db.goals.find({
            "user_id": user_oid,
            "status": "active"
        }))
        
        # Get recent achievements
        recent_achievements = list(self.db.goal_progress.find({
            "user_id": user_oid,
            "achieved_at": {"$gte": week_ago}
        }).limit(5))
        
        # Calculate improvement areas
        improvement_areas = []
        if latest_analysis and "orbo_response" in latest_analysis:
            metrics = latest_analysis["orbo_response"].get("metrics", {})
            for metric, value in metrics.items():
                if value < 70 and metric != "overall_skin_health_score":
                    improvement_areas.append(metric)
        
        # Calculate streak
        streak = self._calculate_streak(user_oid)
        
        # Get season based on current date
        season = self._get_current_season()
        
        return {
            "user": user,
            "latest_analysis": latest_analysis,
            "completion_rate": completion_rate,
            "active_goals": active_goals,
            "recent_achievements": recent_achievements,
            "improvement_areas": improvement_areas,
            "streak": streak,
            "season": season
        }
    
    def _calculate_streak(self, user_oid: ObjectId) -> int:
        """Calculate user's current streak"""
        self._ensure_db()
        # Look for consecutive days with routine completions
        streak = 0
        current_date = date.today()
        
        for i in range(30):  # Check last 30 days max
            check_date = current_date - timedelta(days=i)
            start = datetime.combine(check_date, datetime.min.time())
            end = datetime.combine(check_date, datetime.max.time())
            
            completion = self.db.routine_completions.find_one({
                "user_id": user_oid,
                "completed_at": {"$gte": start, "$lte": end}
            })
            
            if completion:
                streak += 1
            else:
                if i > 0:  # Don't break on today if no completion yet
                    break
        
        return streak
    
    def _get_current_season(self) -> str:
        """Get current season based on date"""
        month = get_utc_now().month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"
    
    def _generate_ai_insights(self, user_data: Dict[str, Any]) -> List[InsightContent]:
        """Generate insights using OpenAI"""
        
        # Prepare context for AI
        user = user_data["user"]
        analysis = user_data.get("latest_analysis", {})
        
        # Extract key metrics
        metrics = {}
        if analysis and "orbo_response" in analysis:
            metrics = analysis["orbo_response"].get("metrics", {})
        
        prompt = f"""
        Generate 3 personalized skincare insights for a user with the following profile:
        
        User Profile:
        - Age Group: {user.get("onboarding", {}).get("age_group", "unknown")}
        - Gender: {user.get("onboarding", {}).get("gender", "unknown")}
        - Skin Type: {user.get("onboarding", {}).get("skin_type", "unknown")}
        - Current Season: {user_data["season"]}
        - Routine Completion Rate: {user_data["completion_rate"]:.1%}
        - Current Streak: {user_data["streak"]} days
        
        Latest Skin Metrics (0-100 scale):
        {json.dumps(metrics, indent=2) if metrics else "No recent analysis"}
        
        Areas Needing Improvement (scores < 70):
        {", ".join(user_data["improvement_areas"]) if user_data["improvement_areas"] else "None identified"}
        
        IMPORTANT RULES:
        1. DO NOT create insights about goals, routines, or progress tracking (these have dedicated pages)
        2. DO NOT mention specific routine steps or goal achievements
        3. FOCUS on: environmental factors, ingredient education, product application tips, seasonal advice, prevention tips
        4. Make insights specific and actionable
        5. Use encouraging, positive language
        
        Return exactly 3 insights in JSON format:
        {{
            "insights": [
                {{
                    "title": "Short, catchy title",
                    "description": "Detailed, personalized description (2-3 sentences)",
                    "category": "one of: skin_trend, environmental, ingredient_focus, prevention, product_tip",
                    "icon": "CupertinoIcons icon name (e.g., sun_max_fill, drop_fill, sparkles)",
                    "priority": "high/medium/low based on relevance",
                    "action_text": "Optional action button text",
                    "action_route": "Optional Flutter route (e.g., /products, /analysis)"
                }}
            ]
        }}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",  # Using GPT-4 Turbo which is stable
                messages=[
                    {"role": "system", "content": "You are a skincare expert providing personalized insights. Always respond with valid JSON."},
                    {"role": "user", "content": prompt + "\n\nIMPORTANT: Return only valid JSON, no other text."}
                ],
                temperature=0.7,
                max_tokens=800  # Standard parameter
            )
            
            # Log the response for debugging
            raw_response = response.choices[0].message.content
            logger.info(f"OpenAI response: {raw_response[:200]}")
            
            # Clean up the response - remove markdown code blocks if present
            if raw_response.startswith("```json"):
                raw_response = raw_response.replace("```json", "").replace("```", "").strip()
            elif raw_response.startswith("```"):
                raw_response = raw_response.replace("```", "").strip()
            
            insights_data = json.loads(raw_response)
            insights = []
            
            for insight_data in insights_data.get("insights", []):
                insights.append(InsightContent(**insight_data))
            
            # Ensure we have exactly 3 insights
            while len(insights) < 3:
                insights.append(self._get_fallback_insight(user_data))
            
            return insights[:3]
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing AI response as JSON: {str(e)}")
            logger.error(f"Raw response: {response.choices[0].message.content if 'response' in locals() else 'No response'}")
            return self._get_fallback_insights_list(user_data)
        except Exception as e:
            logger.error(f"Error generating AI insights: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._get_fallback_insights_list(user_data)
    
    def _get_fallback_insight(self, user_data: Dict[str, Any]) -> InsightContent:
        """Get a single fallback insight"""
        season = user_data.get("season", "spring")
        skin_type = user_data.get("user", {}).get("onboarding", {}).get("skin_type", "normal")
        
        fallback_insights = [
            InsightContent(
                title="Hydration Timing Matters",
                description="Apply your moisturizer within 3 minutes of cleansing while your skin is still damp. This helps lock in moisture more effectively.",
                icon="drop_fill",
                category="product_tip",
                priority="medium"
            ),
            InsightContent(
                title=f"{season.title()} Skin Protection",
                description=f"The {season} weather can affect your skin. Consider adjusting your routine with lighter or heavier products based on humidity levels.",
                icon="cloud_sun_fill",
                category="environmental",
                priority="medium"
            ),
            InsightContent(
                title="Ingredient Spotlight: Niacinamide",
                description="This vitamin B3 derivative helps regulate oil production, minimize pores, and even out skin tone. Look for 5-10% concentrations.",
                icon="sparkles",
                category="ingredient_focus",
                priority="low"
            ),
            InsightContent(
                title="Prevention is Key",
                description="Protecting your skin barrier is easier than repairing it. Always remove makeup before bed and avoid over-exfoliating.",
                icon="shield_fill",
                category="prevention",
                priority="medium"
            )
        ]
        
        return random.choice(fallback_insights)
    
    def _get_fallback_insights_list(self, user_data: Dict[str, Any]) -> List[InsightContent]:
        """Get a list of 3 fallback insights"""
        insights = []
        for _ in range(3):
            insights.append(self._get_fallback_insight(user_data))
        return insights
    
    def _generate_fallback_insights(self, user_id: str) -> DailyInsights:
        """Generate generic fallback insights when personalization fails"""
        insights = [
            InsightContent(
                title="Stay Consistent",
                description="Skincare results take time. Most products need 4-6 weeks of consistent use to show visible improvements.",
                icon="clock_fill",
                category="habit_formation",
                priority="high"
            ),
            InsightContent(
                title="Layer Products Correctly",
                description="Apply skincare from thinnest to thickest consistency: toner, serum, moisturizer, then sunscreen in the morning.",
                icon="square_stack_3d_up_fill",
                category="product_tip",
                priority="medium"
            ),
            InsightContent(
                title="Don't Forget Your Neck",
                description="Extend your skincare routine to your neck and décolletage. These areas show signs of aging too!",
                icon="person_fill",
                category="prevention",
                priority="low"
            )
        ]
        
        factors = PersonalizationFactors(
            current_season=self._get_current_season()
        )
        
        return self._save_insights(user_id, insights, {"season": factors.current_season})
    
    def _save_insights(
        self, 
        user_id: str, 
        insights: List[InsightContent], 
        user_data: Dict[str, Any]
    ) -> DailyInsights:
        """Save insights to database"""
        self._ensure_db()
        
        # Build personalization factors
        factors = PersonalizationFactors(
            skin_type=user_data.get("user", {}).get("onboarding", {}).get("skin_type"),
            age_group=user_data.get("user", {}).get("onboarding", {}).get("age_group"),
            gender=user_data.get("user", {}).get("onboarding", {}).get("gender"),
            current_season=user_data.get("season", self._get_current_season()),
            routine_completion_rate=user_data.get("completion_rate", 0),
            streak_days=user_data.get("streak", 0),
            improvement_areas=user_data.get("improvement_areas", [])
        )
        
        # Add skin concerns and scores if available
        if user_data.get("latest_analysis"):
            analysis = user_data["latest_analysis"]
            if "orbo_response" in analysis:
                factors.recent_analysis_scores = analysis["orbo_response"].get("metrics", {})
                factors.skin_concerns = analysis["orbo_response"].get("concerns", [])
        
        # Create daily insights document
        today = date.today()
        daily_insights = DailyInsights(
            user_id=ObjectId(user_id),
            insights=insights,
            personalization_factors=factors,
            generated_for_date=datetime.combine(today, datetime.min.time()),  # Convert date to datetime
            expires_at=calculate_expiry_time('insight'),
            generation_method="ai_personalized" if user_data else "fallback"
        )
        
        # Save to database
        result = self.db.daily_insights.insert_one(daily_insights.model_dump(by_alias=True))
        daily_insights.id = result.inserted_id
        
        return daily_insights
    
    def mark_insights_viewed(self, user_id: str, insights_id: str):
        """Mark insights as viewed"""
        self._ensure_db()
        self.db.daily_insights.update_one(
            {"_id": ObjectId(insights_id), "user_id": ObjectId(user_id)},
            {
                "$set": {
                    "viewed": True,
                    "viewed_at": get_utc_now()
                }
            }
        )
    
    def track_insight_interaction(
        self, 
        user_id: str, 
        insights_id: str, 
        interaction_type: str,
        insight_index: int
    ):
        """Track user interaction with an insight"""
        self._ensure_db()
        self.db.daily_insights.update_one(
            {"_id": ObjectId(insights_id), "user_id": ObjectId(user_id)},
            {
                "$push": {
                    "interactions": {
                        "type": interaction_type,  # "clicked", "dismissed", "shared"
                        "insight_index": insight_index,
                        "timestamp": get_utc_now()
                    }
                }
            }
        )

# Singleton instance - Initialize lazily to avoid startup issues
_insights_service = None

def get_insights_service():
    global _insights_service
    if _insights_service is None:
        _insights_service = InsightsService()
    return _insights_service

# Don't instantiate at module level to avoid startup issues