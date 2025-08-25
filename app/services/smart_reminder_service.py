"""
Smart Reminder Service with AI generation and calendar integration
"""
import openai
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId
from collections import Counter

from app.core.config import settings
from app.database import db, get_database
from app.models.reminder import (
    SmartReminder, 
    ReminderContent,
    TriggerConditions,
    CalendarIntegration,
    PersonalizationContext,
    CalendarEvent,
    ReminderPreferences
)

logger = logging.getLogger(__name__)


class SmartReminderService:
    """Service for generating and managing smart reminders"""
    
    def __init__(self):
        print("="*50)
        print("[DEBUG] SmartReminderService __init__ called!")
        print("="*50)
        logger.info("[REMINDER SERVICE] Initializing SmartReminderService")
        try:
            if not settings.OPENAI_API_KEY:
                logger.warning("[REMINDER SERVICE] OPENAI_API_KEY is missing; AI generation will use fallback")
                self.openai_client = None
            else:
                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("[REMINDER SERVICE] OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"[REMINDER SERVICE] Failed to initialize OpenAI client: {str(e)}")
            self.openai_client = None
            
        # Access collections directly from the database object
        try:
            self.db = get_database()
            logger.info(f"[REMINDER SERVICE] Database connection established: {self.db.name}")
            
            self.reminders_collection = self.db["smart_reminders"]
            logger.info("[REMINDER SERVICE] Smart reminders collection initialized")
            
            self.calendar_collection = self.db["calendar_events"]
            logger.info("[REMINDER SERVICE] Calendar events collection initialized")
            
            self.preferences_collection = self.db["reminder_preferences"]
            logger.info("[REMINDER SERVICE] Preferences collection initialized")
            
            self.interactions_collection = self.db["reminder_interactions"]
            logger.info("[REMINDER SERVICE] Interactions collection initialized")
            
            logger.info("[REMINDER SERVICE] SmartReminderService initialized successfully")
        except Exception as e:
            logger.error(f"[REMINDER SERVICE] Failed to initialize database collections: {str(e)}")
            raise
        
    def generate_personalized_reminders(
        self, 
        user_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        include_calendar_sync: bool = True
    ) -> List[Dict[str, Any]]:
        """Generate AI-powered personalized reminders with optional calendar integration"""
        
        logger.info(f"[REMINDER SERVICE] Starting reminder generation for user: {user_id}")
        logger.debug(f"[REMINDER SERVICE] Context provided: {user_context}")
        logger.debug(f"[REMINDER SERVICE] Calendar sync enabled: {include_calendar_sync}")
        
        try:
            # Build comprehensive user context
            logger.info(f"[REMINDER SERVICE] Building user context for: {user_id}")
            context = self._build_user_context(user_id, user_context or {})
            logger.debug(f"[REMINDER SERVICE] Built context: {context}")
            
            # Get user preferences
            logger.info(f"[REMINDER SERVICE] Getting user preferences for: {user_id}")
            preferences = self._get_user_preferences(user_id)
            logger.debug(f"[REMINDER SERVICE] User preferences: {preferences}")
            
            # Check for existing recent reminders first
            print(f"[DEBUG] Checking for existing reminders for user: {user_id}")
            logger.info(f"[REMINDER SERVICE] Checking for existing reminders for: {user_id}")
            existing_reminders = self._get_existing_reminders(user_id)
            print(f"[DEBUG] Found {len(existing_reminders)} existing reminders")
            
            if existing_reminders:
                print(f"[DEBUG] Returning {len(existing_reminders)} existing reminders")
                logger.info(f"[REMINDER SERVICE] Found {len(existing_reminders)} existing reminders, returning them")
                return existing_reminders
            
            # No existing reminders, generate new ones
            print(f"[DEBUG] No existing reminders found, generating new ones with AI")
            logger.info(f"[REMINDER SERVICE] No recent reminders found, generating new ones")
            
            # Generate reminders using OpenAI
            logger.info(f"[REMINDER SERVICE] Generating reminders with AI for: {user_id}")
            reminders = self._generate_with_ai(context, preferences)
            logger.info(f"[REMINDER SERVICE] Generated {len(reminders)} reminders")
            logger.debug(f"[REMINDER SERVICE] Generated reminders: {reminders}")
            
            # Save reminders to database
            saved_reminders = []
            for i, reminder_data in enumerate(reminders):
                logger.debug(f"[REMINDER SERVICE] Saving reminder {i+1}/{len(reminders)}")
                reminder = self._save_reminder(user_id, reminder_data)
                
                # Auto-sync high-priority reminders to calendar if enabled
                if include_calendar_sync and preferences.get('calendar_auto_sync', True):
                    if reminder['priority'] >= 7:
                        logger.info(f"[REMINDER SERVICE] Syncing high-priority reminder to calendar")
                        calendar_event_id = self.sync_to_calendar(user_id, reminder)
                        reminder['calendar_event_id'] = calendar_event_id
                        reminder['calendar_synced'] = True
                
                saved_reminders.append(reminder)
            
            logger.info(f"[REMINDER SERVICE] Successfully generated {len(saved_reminders)} reminders for user: {user_id}")
            return saved_reminders
            
        except Exception as e:
            logger.error(f"[REMINDER SERVICE] Error generating personalized reminders: {str(e)}")
            logger.error(f"[REMINDER SERVICE] Error type: {type(e).__name__}")
            logger.error(f"[REMINDER SERVICE] Full traceback:", exc_info=True)
            logger.info(f"[REMINDER SERVICE] Returning fallback reminders for user: {user_id}")
            return self._get_fallback_reminders(user_id)
    
    def _build_user_context(self, user_id: str, additional_context: Dict) -> Dict:
        """Build comprehensive user context for reminder generation"""
        
        # Get user's latest skin analysis
        skin_analysis = self.db["skin_analyses"].find_one(
            {"$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id) if len(user_id) == 24 else user_id}]},
            sort=[("created_at", -1)]
        )
        
        # Calculate photo tracking metrics
        photo_stats = self._get_photo_tracking_stats(user_id)
        
        # Get active goals with detailed progress
        active_goals = list(self.db["goals"].find({
            "$and": [
                {"$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id) if len(user_id) == 24 else user_id}]},
                {"status": "active"}
            ]
        }))
        
        # Enhance goals with milestone detection
        enhanced_goals = []
        for goal in active_goals:
            progress = goal.get("current_progress", 0)
            enhanced_goal = {
                "title": goal.get("title"),
                "target_metric": goal.get("target_metric"),
                "current_progress": progress,
                "deadline": goal.get("target_date"),
                "is_near_milestone": progress >= 75 and progress < 100,
                "is_stalled": self._is_goal_stalled(goal),
                "days_until_deadline": self._calculate_days_until(goal.get("target_date"))
            }
            enhanced_goals.append(enhanced_goal)
        
        # Get routine completion stats with patterns
        routine_stats = self._get_enhanced_routine_stats(user_id)
        
        # Get achievement status
        achievement_stats = self._get_achievement_stats(user_id)
        
        # Get user profile
        user = self.db["users"].find_one({"_id": ObjectId(user_id)})
        
        # Get upcoming routines
        upcoming_routines = self._get_upcoming_routines(user_id)
        
        context = {
            "skin_metrics": skin_analysis.get("orbo_response", {}) if skin_analysis else {},
            "last_analysis_date": skin_analysis.get("created_at") if skin_analysis else None,
            "photo_stats": photo_stats,
            "goals": enhanced_goals,
            "routine_stats": routine_stats,
            "achievement_stats": achievement_stats,
            "upcoming_routines": upcoming_routines,
            "user_profile": {
                "age_group": user.get("profile", {}).get("age_range"),
                "skin_type": user.get("profile", {}).get("skin_type"),
                "concerns": user.get("profile", {}).get("concerns", [])
            },
            "time_of_day": datetime.now().strftime("%H:%M"),
            "day_of_week": datetime.now().strftime("%A"),
            "current_hour": datetime.now().hour,
            **additional_context
        }
        
        return context
    
    def _get_photo_tracking_stats(self, user_id: str) -> Dict:
        """Get photo and analysis tracking statistics"""
        
        # Get latest analysis
        latest = self.db["skin_analyses"].find_one(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        )
        
        # Calculate days since last photo
        days_since = None
        if latest:
            days_since = (datetime.utcnow() - latest["created_at"]).days
        
        # Get achievement data for streak
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get streak from achievements
        streak_data = self._calculate_photo_streak(user_id)
        
        # Get usual photo times
        recent_analyses = list(self.db["skin_analyses"].find(
            {"$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id) if len(user_id) == 24 else user_id}]},
            sort=[("created_at", -1)],
            limit=10
        ))
        
        usual_hours = []
        if recent_analyses:
            hours = [a["created_at"].hour for a in recent_analyses]
            # Find most common hour
            hour_counts = Counter(hours)
            usual_hours = [h for h, _ in hour_counts.most_common(2)]
        
        # Check if today has photo
        today_photo = self.db["skin_analyses"].find_one({
            "$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id) if len(user_id) == 24 else user_id}],
            "created_at": {
                "$gte": today_start,
                "$lt": today_start + timedelta(days=1)
            }
        })
        
        return {
            "days_since_last": days_since,
            "current_streak": streak_data["current"],
            "longest_streak": streak_data["longest"],
            "streak_at_risk": streak_data["at_risk"],
            "has_photo_today": today_photo is not None,
            "usual_photo_hours": usual_hours,
            "total_photos": self.db["skin_analyses"].count_documents({"user_id": user_id})
        }
    
    def _calculate_photo_streak(self, user_id: str) -> Dict:
        """Calculate photo streak from achievements"""
        
        user_oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get achievement records
        cursor = self.db["achievements"].find(
            {"user_id": user_oid, "photos_taken": {"$gt": 0}}
        ).sort("date", -1)
        
        days_with_photos = []
        for doc in cursor:
            if isinstance(doc.get("date"), datetime):
                days_with_photos.append(doc["date"])
        
        # Calculate current streak
        current_streak = 0
        expected = today_start
        
        for day in days_with_photos:
            day_normalized = day.replace(hour=0, minute=0, second=0, microsecond=0)
            if day_normalized == expected:
                current_streak += 1
                expected = expected - timedelta(days=1)
            elif day_normalized < expected:
                break
        
        # Check if streak is at risk (no photo today and streak > 0)
        today_has_photo = any(d.replace(hour=0, minute=0, second=0, microsecond=0) == today_start 
                              for d in days_with_photos)
        at_risk = current_streak > 0 and not today_has_photo
        
        # Calculate longest streak (simplified)
        longest_streak = max(current_streak, 7)  # Default to at least 7 or current
        
        return {
            "current": current_streak,
            "longest": longest_streak,
            "at_risk": at_risk
        }
    
    def _get_enhanced_routine_stats(self, user_id: str) -> Dict:
        """Get enhanced routine completion statistics with patterns"""
        
        # Get last 7 days of routine completions
        week_ago = datetime.utcnow() - timedelta(days=7)
        completions = list(self.db["routine_completions"].find({
            "$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id) if len(user_id) == 24 else user_id}],
            "completed_at": {"$gte": week_ago}
        }))
        
        # Calculate completion rates by type
        morning_completions = [c for c in completions if c.get("routine", {}).get("type") == "morning"]
        evening_completions = [c for c in completions if c.get("routine", {}).get("type") == "evening"]
        
        # Get active routines
        active_routines = list(self.db["routines"].find({
            "$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id) if len(user_id) == 24 else user_id}],
            "is_active": True
        }))
        
        morning_routine = next((r for r in active_routines if r["type"] == "morning"), None)
        evening_routine = next((r for r in active_routines if r["type"] == "evening"), None)
        
        # Calculate patterns
        morning_times = [c["completed_at"].hour for c in morning_completions if "completed_at" in c]
        evening_times = [c["completed_at"].hour for c in evening_completions if "completed_at" in c]
        
        usual_morning_hour = Counter(morning_times).most_common(1)[0][0] if morning_times else 8
        usual_evening_hour = Counter(evening_times).most_common(1)[0][0] if evening_times else 20
        
        # Check today's completions
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_completions = [c for c in completions 
                           if c["completed_at"] >= today_start]
        
        has_morning_today = any(c.get("routine", {}).get("type") == "morning" for c in today_completions)
        has_evening_today = any(c.get("routine", {}).get("type") == "evening" for c in today_completions)
        
        total_expected = 14  # Morning and evening for 7 days
        total_completed = len(completions)
        
        return {
            "completion_rate": (total_completed / total_expected * 100) if total_expected > 0 else 0,
            "current_streak": self._calculate_streak(completions),
            "most_missed": self._find_most_missed_routine(completions),
            "morning_completion_rate": (len(morning_completions) / 7 * 100) if morning_routine else 0,
            "evening_completion_rate": (len(evening_completions) / 7 * 100) if evening_routine else 0,
            "usual_morning_hour": usual_morning_hour,
            "usual_evening_hour": usual_evening_hour,
            "has_morning_today": has_morning_today,
            "has_evening_today": has_evening_today,
            "active_morning_routine": morning_routine is not None,
            "active_evening_routine": evening_routine is not None
        }
    
    def _get_achievement_stats(self, user_id: str) -> Dict:
        """Get achievement and badge statistics"""
        
        # Get user's current achievements
        user = self.db["users"].find_one({"_id": ObjectId(user_id)})
        current_achievements = user.get("achievements", {}) if user else {}
        
        # Define achievement thresholds
        achievement_thresholds = {
            "week_warrior": {"current": current_achievements.get("streak_7_days", False), "threshold": 7},
            "consistency_champion": {"current": current_achievements.get("streak_30_days", False), "threshold": 30},
            "hydration_hero": {"current": current_achievements.get("hydration_improved", False), "threshold": 80},
            "glow_getter": {"current": current_achievements.get("radiance_improved", False), "threshold": 75}
        }
        
        # Check which achievements are close
        close_to_unlock = []
        for name, data in achievement_thresholds.items():
            if not data["current"]:
                # Check progress towards achievement
                if name == "week_warrior":
                    streak = (self._get_photo_tracking_stats(user_id))["current_streak"]
                    if streak >= 5:
                        close_to_unlock.append({"name": name, "progress": streak, "needed": 7})
                elif name == "consistency_champion":
                    streak = (self._get_photo_tracking_stats(user_id))["current_streak"]
                    if streak >= 20:
                        close_to_unlock.append({"name": name, "progress": streak, "needed": 30})
        
        return {
            "total_unlocked": len([v for v in current_achievements.values() if v]),
            "close_to_unlock": close_to_unlock,
            "recent_unlock": None  # Could track this separately
        }
    
    def _get_upcoming_routines(self, user_id: str) -> List[Dict]:
        """Get upcoming routine times based on user preferences"""
        
        prefs = self._get_user_preferences(user_id)
        current_hour = datetime.now().hour
        upcoming = []
        
        # Parse routine times
        morning_hour = int(prefs.get("morning_routine_time", "08:00").split(":")[0])
        evening_hour = int(prefs.get("evening_routine_time", "20:00").split(":")[0])
        
        # Check morning routine
        if current_hour < morning_hour:
            upcoming.append({
                "type": "morning",
                "scheduled_hour": morning_hour,
                "minutes_until": (morning_hour - current_hour) * 60
            })
        
        # Check evening routine
        if current_hour < evening_hour:
            upcoming.append({
                "type": "evening",
                "scheduled_hour": evening_hour,
                "minutes_until": (evening_hour - current_hour) * 60
            })
        
        return upcoming
    
    def _is_goal_stalled(self, goal: Dict) -> bool:
        """Check if a goal has stalled (no progress in 7 days)"""
        
        last_update = goal.get("last_progress_update")
        if not last_update:
            created = goal.get("created_at")
            if created and (datetime.utcnow() - created).days > 7:
                return True
        elif (datetime.utcnow() - last_update).days > 7:
            return True
        return False
    
    def _calculate_days_until(self, target_date) -> Optional[int]:
        """Calculate days until a target date"""
        
        if not target_date:
            return None
        if isinstance(target_date, str):
            target_date = datetime.fromisoformat(target_date)
        return (target_date - datetime.utcnow()).days
    
    def _get_routine_stats(self, user_id: str) -> Dict:
        """Get routine completion statistics"""
        
        # Get last 7 days of routine completions
        week_ago = datetime.utcnow() - timedelta(days=7)
        completions = list(self.db["routine_completions"].find({
            "user_id": user_id,
            "completed_at": {"$gte": week_ago}
        }))
        
        total_expected = 14  # Morning and evening for 7 days
        total_completed = len(completions)
        
        return {
            "completion_rate": (total_completed / total_expected * 100) if total_expected > 0 else 0,
            "current_streak": self._calculate_streak(completions),
            "most_missed": self._find_most_missed_routine(completions)
        }
    
    def _generate_with_ai(self, context: Dict, preferences: Dict) -> List[Dict]:
        """Generate reminders using OpenAI GPT-4"""
        
        # Prepare photo tracking info
        photo_info = context.get('photo_stats', {})
        days_since = photo_info.get('days_since_last', 0)
        streak_info = f"Current streak: {photo_info.get('current_streak', 0)} days"
        if photo_info.get('streak_at_risk'):
            streak_info += " (AT RISK - no photo today!)"
        
        # Prepare goal info
        goal_alerts = []
        for goal in context.get('goals', []):
            if goal.get('is_near_milestone'):
                goal_alerts.append(f"- {goal['title']}: {goal['current_progress']}% complete (near milestone!)")
            elif goal.get('is_stalled'):
                goal_alerts.append(f"- {goal['title']}: STALLED at {goal['current_progress']}%")
        
        # Prepare routine info
        routine_info = context.get('routine_stats', {})
        routine_alerts = []
        if not routine_info.get('has_morning_today') and routine_info.get('active_morning_routine'):
            routine_alerts.append("Morning routine not completed today")
        if not routine_info.get('has_evening_today') and routine_info.get('active_evening_routine') and context.get('current_hour', 0) >= 18:
            routine_alerts.append("Evening routine pending")
        
        # Prepare achievement alerts
        achievement_info = context.get('achievement_stats', {})
        close_achievements = achievement_info.get('close_to_unlock', [])
        
        prompt = f"""
        Generate 5 highly personalized skincare reminders based on this REAL-TIME user data:
        
        PHOTO TRACKING STATUS:
        - Days since last photo: {days_since}
        - {streak_info}
        - Has photo today: {photo_info.get('has_photo_today', False)}
        - Total photos taken: {photo_info.get('total_photos', 0)}
        - Usual photo times: {photo_info.get('usual_photo_hours', [8, 20])}
        
        USER PROFILE:
        - Age Group: {context['user_profile']['age_group']}
        - Skin Type: {context['user_profile']['skin_type']}
        - Main Concerns: {', '.join(context['user_profile']['concerns'][:3]) if context['user_profile']['concerns'] else 'General skincare'}
        
        SKIN METRICS (0-100 scale, higher is better):
        - Hydration: {context['skin_metrics'].get('hydration', 'N/A')}
        - Smoothness: {context['skin_metrics'].get('smoothness', 'N/A')}
        - Radiance: {context['skin_metrics'].get('radiance', 'N/A')}
        - Dark Spots: {context['skin_metrics'].get('dark_spots', 'N/A')}
        - Firmness: {context['skin_metrics'].get('firmness', 'N/A')}
        - Acne: {context['skin_metrics'].get('acne', 'N/A')}
        
        GOAL ALERTS:
        {chr(10).join(goal_alerts) if goal_alerts else 'No urgent goal updates'}
        
        ROUTINE STATUS:
        - Morning completion rate: {routine_info.get('morning_completion_rate', 0):.0f}%
        - Evening completion rate: {routine_info.get('evening_completion_rate', 0):.0f}%
        - Routine streak: {routine_info.get('current_streak', 0)} days
        - ALERTS: {', '.join(routine_alerts) if routine_alerts else 'All routines on track'}
        - Usual morning time: {routine_info.get('usual_morning_hour', 8)}:00
        - Usual evening time: {routine_info.get('usual_evening_hour', 20)}:00
        
        ACHIEVEMENTS NEAR UNLOCK:
        {', '.join([f"{a['name']} ({a['progress']}/{a['needed']})" for a in close_achievements]) if close_achievements else 'None close to unlock'}
        
        CURRENT CONTEXT:
        - Time: {context['time_of_day']} (Hour: {context['current_hour']})
        - Day: {context['day_of_week']}
        - Weather: UV Index {context.get('weather', {}).get('uv_index', 5)}, Temp {context.get('weather', {}).get('temperature', 72)}°F
        
        UPCOMING ROUTINES:
        {json.dumps(context.get('upcoming_routines', []), indent=2)}
        
        USER PREFERENCES:
        - Morning Routine Time: {preferences.get('morning_routine_time', '08:00')}
        - Evening Routine Time: {preferences.get('evening_routine_time', '20:00')}
        - Max Daily Reminders: {preferences.get('max_daily_reminders', 5)}
        
        CRITICAL INSTRUCTIONS:
        Generate exactly 5 reminders with these PRIORITIES:
        
        1. HIGHEST PRIORITY (9-10):
           - Streak at risk (no photo today and streak > 0): "Don't break your X day streak!"
           - Routine time approaching (within 30 min): "Morning routine in X minutes"
           - Goal milestone reached: "You're 90% to clearer skin!"
        
        2. HIGH PRIORITY (7-8):
           - Daily photo reminder (if no photo today): "Time for your progress photo"
           - Missed routine recovery: "You missed morning routine yesterday"
           - Goal stalled: "Your hydration goal needs attention"
           - High UV protection: "UV index is X - apply SPF now!"
        
        3. MEDIUM PRIORITY (5-6):
           - Educational for lowest metrics
           - Achievement progress: "2 more days for Week Warrior badge!"
           - Product recommendations
        
        4. LOW PRIORITY (3-4):
           - Community engagement
           - General tips
        
        For each reminder, provide:
        - type: "action" | "knowledge" | "motivation" | "preventive"
        - category: "routine" | "goal" | "achievement" | "photo" | "education" | "community"
        - priority: 1-10 (based on urgency above)
        - title: Specific, personalized title using their data (max 50 chars)
        - message: Detailed message with their actual numbers/progress (max 150 chars)
        - action_text: Clear action button text
        - action_route: "/routine/morning" | "/routine/evening" | "/scan" | "/goals" | "/progress" | "/care-hub"
        - icon: sun | moon | camera | star | heart | shield | book | trophy | droplet
        - color: gradient_blue | gradient_red | gradient_green | gradient_purple | gradient_orange
        - scheduled_time: ISO datetime (schedule based on context and urgency)
        - recurrence: none | daily | weekly
        
        Return ONLY a valid JSON array of 5 reminder objects. No other text.
        """
        
        try:
            if not self.openai_client:
                logger.warning("[REMINDER SERVICE] OpenAI client not available; using fallback reminders data")
                return self._get_fallback_reminders_data()
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a skincare expert creating personalized reminders. Always respond with valid JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            # Parse and clean the response
            raw_response = response.choices[0].message.content
            
            # Remove markdown code blocks if present
            if raw_response.startswith("```json"):
                raw_response = raw_response.replace("```json", "").replace("```", "").strip()
            elif raw_response.startswith("```"):
                raw_response = raw_response.replace("```", "").strip()
            
            reminders = json.loads(raw_response)
            
            # Validate and enhance reminders
            return self._validate_and_enhance_reminders(reminders)
            
        except Exception as e:
            logger.error(f"Error generating AI reminders: {str(e)}")
            return self._get_fallback_reminders_data()
    
    def _save_reminder(self, user_id: str, reminder_data: Dict) -> Dict:
        """Save a reminder to the database"""
        
        reminder = {
            "user_id": user_id,
            "reminder_type": reminder_data.get("type", "action"),
            "category": reminder_data.get("category", "routine"),
            "priority": reminder_data.get("priority", 5),
            "content": {
                "title": reminder_data.get("title", "Skincare Reminder"),
                "message": reminder_data.get("message", "Time for your skincare routine!"),
                "action_text": reminder_data.get("action_text", "View"),
                "action_route": reminder_data.get("action_route", "/home"),
                "icon": reminder_data.get("icon", "star"),
                "color": reminder_data.get("color", "gradient_blue")
            },
            "trigger_conditions": {
                "time_based": datetime.fromisoformat(reminder_data.get("scheduled_time", datetime.now().isoformat()))
            },
            "calendar_integration": {
                "synced_to_calendar": False,
                "recurrence": {
                    "enabled": reminder_data.get("recurrence", "none") != "none",
                    "pattern": reminder_data.get("recurrence", "none")
                } if reminder_data.get("recurrence") != "none" else None
            },
            "status": "pending",
            "created_at": datetime.utcnow(),
            "scheduled_for": datetime.fromisoformat(reminder_data.get("scheduled_time", datetime.now().isoformat())),
            "expires_at": datetime.fromisoformat(reminder_data.get("scheduled_time", datetime.now().isoformat())) + timedelta(days=1)
        }
        
        result = self.reminders_collection.insert_one(reminder)
        reminder["_id"] = str(result.inserted_id)
        
        return reminder
    
    def sync_to_calendar(self, user_id: str, reminder: Dict) -> str:
        """Automatically create calendar event from reminder"""
        
        calendar_event = {
            "user_id": user_id,
            "title": reminder["content"]["title"],
            "description": reminder["content"]["message"],
            "event_type": "reminder",
            "start_time": reminder["scheduled_for"],
            "end_time": reminder["scheduled_for"] + timedelta(minutes=15),
            "reminder_linked": {
                "is_from_reminder": True,
                "reminder_id": str(reminder["_id"]),
                "auto_generated": True
            },
            "color": self._get_event_color(reminder["priority"]),
            "icon": reminder["content"]["icon"],
            "notifications": [
                {"time_before": 10, "sent": False}
            ],
            "status": "scheduled",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Add recurrence if specified
        if reminder.get("calendar_integration", {}).get("recurrence"):
            calendar_event["recurrence"] = reminder["calendar_integration"]["recurrence"]
        
        # Insert into calendar
        result = self.calendar_collection.insert_one(calendar_event)
        
        # Update reminder with calendar link
        self.reminders_collection.update_one(
            {"_id": ObjectId(reminder["_id"])},
            {"$set": {
                "calendar_integration.synced_to_calendar": True,
                "calendar_integration.calendar_event_id": str(result.inserted_id)
            }}
        )
        
        return str(result.inserted_id)
    
    def get_upcoming_reminders(
        self, 
        user_id: str, 
        limit: int = 5,
        min_priority: Optional[int] = None
    ) -> List[Dict]:
        """Get upcoming reminders for a user"""
        
        query = {
            "user_id": user_id,
            "status": "pending",
            "scheduled_for": {"$gte": datetime.utcnow()}
        }
        
        if min_priority:
            query["priority"] = {"$gte": min_priority}
        
        reminders = list(self.reminders_collection.find(
            query,
            sort=[("priority", -1), ("scheduled_for", 1)],
            limit=limit
        ))
        
        # Convert ObjectId to string
        for reminder in reminders:
            reminder["id"] = str(reminder.pop("_id"))
            if reminder.get("calendar_integration", {}).get("calendar_event_id"):
                reminder["calendar_synced"] = True
            else:
                reminder["calendar_synced"] = False
        
        return reminders
    
    def track_interaction(
        self, 
        reminder_id: str, 
        user_id: str,
        action: str,
        engagement_score: float = 0.5
    ) -> bool:
        """Track user interaction with a reminder"""
        
        interaction = {
            "user_id": user_id,
            "reminder_id": reminder_id,
            "action": action,
            "timestamp": datetime.utcnow(),
            "engagement_score": engagement_score
        }
        
        self.interactions_collection.insert_one(interaction)
        
        # Update reminder status
        status_map = {
            "clicked": "interacted",
            "dismissed": "dismissed",
            "snoozed": "snoozed",
            "completed": "completed"
        }
        
        if action in status_map:
            self.reminders_collection.update_one(
                {"_id": ObjectId(reminder_id)},
                {
                    "$set": {
                        "status": status_map[action],
                        "interacted_at": datetime.utcnow()
                    }
                }
            )
        
        return True
    
    def snooze_reminder(
        self, 
        reminder_id: str, 
        user_id: str,
        duration_minutes: int
    ) -> Dict:
        """Snooze a reminder and update calendar if synced"""
        
        new_time = datetime.utcnow() + timedelta(minutes=duration_minutes)
        
        # Update reminder
        self.reminders_collection.update_one(
            {"_id": ObjectId(reminder_id), "user_id": user_id},
            {
                "$set": {
                    "scheduled_for": new_time,
                    "status": "snoozed"
                }
            }
        )
        
        # Update calendar event if synced
        reminder = self.reminders_collection.find_one({"_id": ObjectId(reminder_id)})
        if reminder and reminder.get("calendar_integration", {}).get("calendar_event_id"):
            self.calendar_collection.update_one(
                {"_id": ObjectId(reminder["calendar_integration"]["calendar_event_id"])},
                {
                    "$set": {
                        "start_time": new_time,
                        "end_time": new_time + timedelta(minutes=15),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
        # Track interaction
        self.track_interaction(reminder_id, user_id, "snoozed", 0.3)
        
        return {"success": True, "new_time": new_time.isoformat()}
    
    def _get_user_preferences(self, user_id: str) -> Dict:
        """Get user's reminder preferences"""
        
        prefs = self.preferences_collection.find_one({"user_id": user_id})
        
        if not prefs:
            # Create default preferences
            default_prefs = {
                "user_id": user_id,
                "enabled": True,
                "calendar_auto_sync": True,
                "morning_routine_time": "08:00",
                "evening_routine_time": "20:00",
                "max_daily_reminders": 5,
                "min_priority_to_show": 3,
                "enabled_categories": [
                    "routine", "goal", "achievement", 
                    "product", "education", "community"
                ],
                "push_notifications": True,
                "email_notifications": False,
                "updated_at": datetime.utcnow()
            }
            self.preferences_collection.insert_one(default_prefs)
            return default_prefs
        
        return prefs
    
    def _get_event_color(self, priority: int) -> str:
        """Get calendar event color based on priority"""
        
        if priority >= 8:
            return "#E91E63"  # Magenta for high priority
        elif priority >= 6:
            return "#FF9800"  # Orange for medium-high
        elif priority >= 4:
            return "#4CAF50"  # Green for medium
        else:
            return "#9C27B0"  # Purple for low
    
    def _calculate_streak(self, completions: List[Dict]) -> int:
        """Calculate current streak from completions"""
        
        if not completions:
            return 0
        
        # Sort by date
        sorted_completions = sorted(completions, key=lambda x: x['completed_at'], reverse=True)
        
        streak = 0
        current_date = datetime.utcnow().date()
        
        for completion in sorted_completions:
            completion_date = completion['completed_at'].date()
            if completion_date == current_date or completion_date == current_date - timedelta(days=streak):
                streak += 1
                current_date = completion_date
            else:
                break
        
        return streak
    
    def _find_most_missed_routine(self, completions: List[Dict]) -> str:
        """Find which routine type is most often missed"""
        
        morning_count = sum(1 for c in completions if c.get('routine_type') == 'morning')
        evening_count = sum(1 for c in completions if c.get('routine_type') == 'evening')
        
        if morning_count < evening_count:
            return "morning"
        elif evening_count < morning_count:
            return "evening"
        else:
            return "both"
    
    def _validate_and_enhance_reminders(self, reminders: List[Dict]) -> List[Dict]:
        """Validate and enhance AI-generated reminders"""
        
        enhanced = []
        for reminder in reminders[:5]:  # Limit to 5 reminders
            # Ensure all required fields
            enhanced_reminder = {
                "type": reminder.get("type", "action"),
                "category": reminder.get("category", "routine"),
                "priority": min(10, max(1, reminder.get("priority", 5))),
                "title": reminder.get("title", "Skincare Reminder")[:50],
                "message": reminder.get("message", "Time for skincare!")[:150],
                "action_text": reminder.get("action_text", "View"),
                "action_route": reminder.get("action_route", "/home"),
                "icon": reminder.get("icon", "star"),
                "color": reminder.get("color", "gradient_blue"),
                "scheduled_time": reminder.get("scheduled_time", datetime.now().isoformat()),
                "recurrence": reminder.get("recurrence", "none")
            }
            enhanced.append(enhanced_reminder)
        
        return enhanced
    
    def _get_fallback_reminders_data(self) -> List[Dict]:
        """Get fallback reminders when AI generation fails"""
        
        now = datetime.now()
        return [
            {
                "type": "action",
                "category": "routine",
                "priority": 8,
                "title": "Morning Routine Time!",
                "message": "Start your day with a refreshing skincare routine",
                "action_text": "Start Routine",
                "action_route": "/routine/morning",
                "icon": "sun",
                "color": "gradient_blue",
                "scheduled_time": now.replace(hour=8, minute=0).isoformat(),
                "recurrence": "daily"
            },
            {
                "type": "knowledge",
                "category": "education",
                "priority": 5,
                "title": "Skincare Tip",
                "message": "Did you know? Hydration is key to healthy skin",
                "action_text": "Learn More",
                "action_route": "/care-hub/learn",
                "icon": "book",
                "color": "gradient_purple",
                "scheduled_time": (now + timedelta(hours=2)).isoformat(),
                "recurrence": "none"
            }
        ]
    
    def _get_fallback_reminders(self, user_id: str) -> List[Dict]:
        """Get fallback reminders with basic structure"""
        
        reminders_data = self._get_fallback_reminders_data()
        saved_reminders = []
        
        for data in reminders_data:
            reminder = {
                "user_id": user_id,
                "reminder_type": data["type"],
                "category": data["category"],
                "priority": data["priority"],
                "content": {
                    "title": data["title"],
                    "message": data["message"],
                    "action_text": data["action_text"],
                    "action_route": data["action_route"],
                    "icon": data["icon"],
                    "color": data["color"]
                },
                "scheduled_for": datetime.fromisoformat(data["scheduled_time"]),
                "status": "pending",
                "created_at": datetime.utcnow()
            }
            saved_reminders.append(reminder)
        
        return saved_reminders
    
    def _get_existing_reminders(self, user_id: str) -> List[Dict]:
        """Check for existing reminders for today that are still valid"""
        try:
            # Get today's date range in UTC
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            
            print(f"[DEBUG] Searching for reminders between {today} and {tomorrow}")
            print(f"[DEBUG] User ID: {user_id}")
            
            # Find reminders for today that are pending or scheduled for future
            query = {
                "user_id": {"$in": [user_id, ObjectId(user_id) if len(user_id) == 24 else user_id]},
                "scheduled_for": {
                    "$gte": today,
                    "$lt": tomorrow
                },
                "status": {"$in": ["pending", "snoozed"]}
            }
            print(f"[DEBUG] Query: {query}")
            
            existing = list(self.db["smart_reminders"].find(query))
            
            # If none found, also consider upcoming within next 24h
            if not existing:
                query_next = {
                    "user_id": {"$in": [user_id, ObjectId(user_id) if len(user_id) == 24 else user_id]},
                    "scheduled_for": {"$gte": tomorrow, "$lt": tomorrow + timedelta(days=1)},
                    "status": {"$in": ["pending", "snoozed"]}
                }
                existing = list(self.db["smart_reminders"].find(query_next))
            print(f"[DEBUG] Raw query result: {len(existing)} reminders")
            
            # Convert ObjectId to string for JSON serialization
            for reminder in existing:
                print(f"[DEBUG] Processing reminder: {reminder.get('content', {}).get('title', 'No title')}")
                reminder["id"] = str(reminder["_id"])
                del reminder["_id"]
            
            print(f"[DEBUG] Final result: {len(existing)} existing reminders for today")
            logger.info(f"[REMINDER SERVICE] Found {len(existing)} existing reminders for today")
            return existing
            
        except Exception as e:
            print(f"[DEBUG] Error in _get_existing_reminders: {e}")
            logger.error(f"[REMINDER SERVICE] Error getting existing reminders: {e}")
            return []