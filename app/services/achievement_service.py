from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.collection import Collection
from bson import ObjectId
import logging

from ..models.achievement import (
    UserAchievement, AchievementDefinition, AchievementProgress,
    AchievementSync, AchievementAction, ACHIEVEMENT_DEFINITIONS,
    get_achievement_definition, AchievementTriggerType
)
from ..database import get_database

logger = logging.getLogger(__name__)


class AchievementService:
    def __init__(self):
        self.db = get_database()
        self.achievements_collection: Collection = self.db.user_achievements
        self.achievement_actions_collection: Collection = self.db.achievement_actions
        self.achievement_sync_collection: Collection = self.db.achievement_sync
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create MongoDB indexes for achievement collections"""
        # User achievements indexes
        self.achievements_collection.create_index([("user_id", 1), ("achievement_id", 1)], unique=True)
        self.achievements_collection.create_index("user_id")
        self.achievements_collection.create_index("is_unlocked")
        self.achievements_collection.create_index("verified")
        
        # Achievement actions indexes
        self.achievement_actions_collection.create_index("user_id")
        self.achievement_actions_collection.create_index("action_type")
        self.achievement_actions_collection.create_index("timestamp")
        
        # Sync collection indexes
        self.achievement_sync_collection.create_index("user_id")
        self.achievement_sync_collection.create_index("sync_timestamp")
    
    def _get_user_query_format(self, user_id: str, db, collection_name: str):
        """Determine if the collection uses ObjectId or string format for user_id"""
        try:
            user_oid = ObjectId(user_id)
        except:
            logger.error(f"Invalid user_id format: {user_id}")
            # Try as string if ObjectId conversion fails
            return user_id
        
        collection = db[collection_name]
        
        # Check both formats and use whichever has data
        # CRITICAL FIX: Check both formats properly
        oid_count = collection.count_documents({"user_id": user_oid})
        str_count = collection.count_documents({"user_id": user_id})
        
        logger.info(f"User ID format check for {collection_name}: ObjectId={oid_count}, string={str_count}")
        
        # Return the format that has data, prefer ObjectId if both have data
        if oid_count > 0:
            return user_oid
        elif str_count > 0:
            return user_id
        else:
            # CRITICAL: For collections that might have mixed formats,
            # check if we should default to the user collection format
            user_in_db = db.users.find_one({"_id": user_oid})
            if user_in_db:
                # User exists, so other collections should use ObjectId too
                return user_oid
            else:
                # Fallback to string
                return user_id
    
    def initialize_user_achievements(self, user_id: str) -> List[Dict[str, Any]]:
        """Initialize all achievements for a new user"""
        # Always convert to ObjectId for consistency
        try:
            user_oid = ObjectId(user_id)
        except:
            logger.error(f"Invalid user_id format: {user_id}")
            raise ValueError(f"Invalid user_id format: {user_id}")
        
        user_achievements = []
        
        for achievement_def in ACHIEVEMENT_DEFINITIONS:
            user_achievement = UserAchievement(
                user_id=str(user_oid),  # Convert ObjectId to string for Pydantic model
                achievement_id=achievement_def.achievement_id,
                progress=0.0,
                is_unlocked=False,
                progress_data={},
                verified=False
            )
            
            # Prepare data for database (with ObjectId)
            db_data = user_achievement.dict()
            db_data["user_id"] = user_oid  # Store as ObjectId in DB
            
            # Insert or update
            self.achievements_collection.update_one(
                {
                    "user_id": user_oid,  # Use ObjectId
                    "achievement_id": achievement_def.achievement_id
                },
                {"$setOnInsert": db_data},
                upsert=True
            )
            
            # Merge with definition for response (user_id already as string from Pydantic model)
            merged = {**achievement_def.dict(), **user_achievement.dict()}
            user_achievements.append(merged)
        
        logger.info(f"Initialized {len(user_achievements)} achievements for user {user_id}")
        return user_achievements
    
    def get_user_achievements(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all achievements for a user with their progress"""
        # Always convert to ObjectId for consistency
        try:
            user_oid = ObjectId(user_id)
        except:
            logger.error(f"Invalid user_id format: {user_id}")
            raise ValueError(f"Invalid user_id format: {user_id}")
        
        # CRITICAL FIX: Check for achievements with BOTH ObjectId and string formats
        # Some users may have achievements stored with string user_id due to past bugs
        user_progress_oid = list(self.achievements_collection.find({"user_id": user_oid}))
        user_progress_str = list(self.achievements_collection.find({"user_id": user_id}))
        
        # Use whichever has data, prefer ObjectId format
        user_progress = user_progress_oid if user_progress_oid else user_progress_str
        
        logger.info(f"Get achievements - User {user_id}: ObjectId format={len(user_progress_oid)}, string format={len(user_progress_str)}")
        
        # If no achievements found in either format, initialize them
        if not user_progress:
            logger.info(f"No achievements found for user {user_id}, initializing...")
            return self.initialize_user_achievements(user_id)
        
        # MIGRATION FIX: If achievements exist with string format, migrate to ObjectId
        if user_progress_str and not user_progress_oid:
            logger.warning(f"Migrating achievements from string to ObjectId format for user {user_id}")
            for achievement in user_progress_str:
                self.achievements_collection.update_one(
                    {"_id": achievement["_id"]},
                    {"$set": {"user_id": user_oid}}
                )
            # Re-fetch with ObjectId
            user_progress = list(self.achievements_collection.find({"user_id": user_oid}))
        
        # Merge with definitions
        achievements = []
        for achievement_def in ACHIEVEMENT_DEFINITIONS:
            # Find user's progress for this achievement
            progress = next(
                (p for p in user_progress if p["achievement_id"] == achievement_def.achievement_id),
                None
            )
            
            if progress:
                # CRITICAL FIX: Convert ObjectId to string before merging
                progress_clean = progress.copy()
                progress_clean.pop("_id", None)  # Remove MongoDB _id
                if isinstance(progress_clean.get("user_id"), ObjectId):
                    progress_clean["user_id"] = str(progress_clean["user_id"])
                
                # Merge definition with progress
                merged = {**achievement_def.dict(), **progress_clean}
                achievements.append(merged)
            else:
                # User doesn't have this achievement yet, create it
                new_achievement = UserAchievement(
                    user_id=str(user_oid),  # Convert ObjectId to string for Pydantic model
                    achievement_id=achievement_def.achievement_id,
                    progress=0.0,
                    is_unlocked=False,
                    progress_data={},
                    verified=False
                )
                
                # Store in database with ObjectId
                db_data = new_achievement.dict()
                db_data["user_id"] = user_oid  # Store as ObjectId in DB
                self.achievements_collection.insert_one(db_data)
                
                # Return with string user_id
                merged = {**achievement_def.dict(), **new_achievement.dict()}
                achievements.append(merged)
        
        return achievements
    
    def update_achievement_progress(
        self, 
        user_id: str, 
        achievement_id: str, 
        progress: float,
        progress_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Update achievement progress for a user"""
        # Always convert to ObjectId for consistency
        try:
            user_oid = ObjectId(user_id)
        except:
            logger.error(f"Invalid user_id format: {user_id}")
            raise ValueError(f"Invalid user_id format: {user_id}")
        
        # Validate achievement exists
        achievement_def = get_achievement_definition(achievement_id)
        if not achievement_def:
            logger.error(f"Achievement {achievement_id} not found")
            return None
        
        # Ensure progress is between 0 and 1
        progress = max(0.0, min(1.0, progress))
        
        # Check if achievement should be unlocked
        is_unlocked = progress >= 1.0
        unlock_time = datetime.now() if is_unlocked else None
        
        # Update in database
        update_data = {
            "$set": {
                "progress": progress,
                "is_unlocked": is_unlocked,
                "last_updated": datetime.now()
            }
        }
        
        if is_unlocked and unlock_time:
            update_data["$set"]["unlocked_at"] = unlock_time
        
        if progress_data:
            update_data["$set"]["progress_data"] = progress_data
        
        result = self.achievements_collection.find_one_and_update(
            {"user_id": user_oid, "achievement_id": achievement_id},  # Use ObjectId
            update_data,
            upsert=True,
            return_document=True
        )
        
        if result:
            # CRITICAL FIX: Convert ObjectId to string before merging
            result_clean = result.copy()
            result_clean.pop("_id", None)  # Remove MongoDB _id
            if isinstance(result_clean.get("user_id"), ObjectId):
                result_clean["user_id"] = str(result_clean["user_id"])
            
            # Merge with definition
            merged = {**achievement_def.dict(), **result_clean}
            
            logger.info(f"Updated achievement {achievement_id} for user {user_id}: progress={progress}, unlocked={is_unlocked}")
            return merged
        
        return None
    
    def track_user_action(self, user_id: str, action: AchievementAction) -> List[Dict[str, Any]]:
        """Track a user action and update related achievements"""
        # Always convert to ObjectId for consistency
        try:
            user_oid = ObjectId(user_id)
        except:
            logger.error(f"Invalid user_id format: {user_id}")
            raise ValueError(f"Invalid user_id format: {user_id}")
        
        # Store the action
        self.achievement_actions_collection.insert_one({
            "user_id": user_oid,  # Use ObjectId
            **action.dict()
        })
        
        updated_achievements = []
        
        # Check which achievements this action affects
        if action.action_type == "skin_analysis_completed":
            # Count actual analyses from the skin_analyses collection
            # This ensures we count ALL analyses, not just ones tracked after achievements were added
            from ..database import get_database
            db = get_database()
            from bson import ObjectId
            
            # CRITICAL FIX: Check BOTH formats to ensure we count all analyses
            try:
                user_oid = ObjectId(user_id)
                analysis_count_oid = db.skin_analyses.count_documents({"user_id": user_oid})
                analysis_count_str = db.skin_analyses.count_documents({"user_id": user_id})
                analysis_count = max(analysis_count_oid, analysis_count_str)
            except:
                analysis_count = db.skin_analyses.count_documents({"user_id": user_id})
            
            logger.info(f"User {user_id} has {analysis_count} total analyses")
            
            # First analysis achievement
            if analysis_count == 1:
                achievement = self.update_achievement_progress(user_id, "first_glow", 1.0)
                if achievement:
                    updated_achievements.append(achievement)
            
            # Progress Pioneer (10 photos)
            if analysis_count <= 10:
                progress = min(1.0, analysis_count / 10.0)
                achievement = self.update_achievement_progress(
                    user_id, "progress_pioneer", progress,
                    {"photo_count": analysis_count}
                )
                if achievement:
                    updated_achievements.append(achievement)
        
        elif action.action_type == "daily_checkin":
            streak_days = action.data.get("streak_days", 0)
            
            # Week Warrior (7 days)
            if streak_days <= 7:
                progress = min(1.0, streak_days / 7.0)
                achievement = self.update_achievement_progress(
                    user_id, "week_warrior", progress,
                    {"streak_days": streak_days}
                )
                if achievement:
                    updated_achievements.append(achievement)
            
            # Consistency King/Queen (30 days)
            if streak_days <= 30:
                progress = min(1.0, streak_days / 30.0)
                achievement = self.update_achievement_progress(
                    user_id, "consistency_ruler", progress,
                    {"streak_days": streak_days}
                )
                if achievement:
                    updated_achievements.append(achievement)
        
        elif action.action_type == "goal_created":
            # First goal achievement
            goal_count = self.achievement_actions_collection.count_documents({
                "user_id": user_oid,  # Use ObjectId
                "action_type": "goal_created"
            })
            
            if goal_count == 1:
                achievement = self.update_achievement_progress(user_id, "baseline_boss", 1.0)
                if achievement:
                    updated_achievements.append(achievement)
        
        elif action.action_type == "routine_created":
            # Check if user has both AM and PM routines
            has_am = action.data.get("has_morning", False)
            has_pm = action.data.get("has_evening", False)
            
            if has_am and has_pm:
                achievement = self.update_achievement_progress(
                    user_id, "routine_revolutionary", 1.0,
                    {"has_am_pm": True}
                )
                if achievement:
                    updated_achievements.append(achievement)
        
        elif action.action_type == "skin_score_improved":
            improvement = action.data.get("improvement", 0)
            
            # Glow Up (10+ point improvement)
            if improvement >= 10:
                achievement = self.update_achievement_progress(
                    user_id, "glow_up", 1.0,
                    {"improvement": improvement}
                )
                if achievement:
                    updated_achievements.append(achievement)
            elif improvement > 0:
                progress = min(1.0, improvement / 10.0)
                achievement = self.update_achievement_progress(
                    user_id, "glow_up", progress,
                    {"improvement": improvement}
                )
                if achievement:
                    updated_achievements.append(achievement)
        
        elif action.action_type == "ingredient_viewed":
            # Count unique ingredients viewed
            # CRITICAL FIX: Use ObjectId for consistency with achievement_actions collection
            unique_ingredients = self.achievement_actions_collection.distinct(
                "data.ingredient_name",
                {"user_id": user_oid, "action_type": "ingredient_viewed"}
            )
            count = len(unique_ingredients)
            
            if count <= 25:
                progress = min(1.0, count / 25.0)
                achievement = self.update_achievement_progress(
                    user_id, "ingredient_inspector", progress,
                    {"ingredients_learned": count}
                )
                if achievement:
                    updated_achievements.append(achievement)
        
        elif action.action_type == "tip_shared":
            # CRITICAL FIX: Use ObjectId for consistency with achievement_actions collection
            tip_count = self.achievement_actions_collection.count_documents({
                "user_id": user_oid,
                "action_type": "tip_shared"
            })
            
            if tip_count <= 5:
                progress = min(1.0, tip_count / 5.0)
                achievement = self.update_achievement_progress(
                    user_id, "knowledge_sharer", progress,
                    {"tips_shared": tip_count}
                )
                if achievement:
                    updated_achievements.append(achievement)
        
        elif action.action_type == "member_helped":
            # CRITICAL FIX: Use ObjectId for consistency with achievement_actions collection
            help_count = self.achievement_actions_collection.count_documents({
                "user_id": user_oid,
                "action_type": "member_helped"
            })
            
            if help_count <= 10:
                progress = min(1.0, help_count / 10.0)
                achievement = self.update_achievement_progress(
                    user_id, "helpful_heart", progress,
                    {"members_helped": help_count}
                )
                if achievement:
                    updated_achievements.append(achievement)
        
        # CRITICAL FIX: Ensure all achievements have ObjectIds converted to strings
        clean_achievements = []
        for achievement in updated_achievements:
            if achievement:
                achievement_clean = achievement.copy()
                if isinstance(achievement_clean.get("user_id"), ObjectId):
                    achievement_clean["user_id"] = str(achievement_clean["user_id"])
                clean_achievements.append(achievement_clean)
        
        return clean_achievements
    
    def sync_achievements(self, user_id: str, sync_data: AchievementSync) -> Dict[str, Any]:
        """Sync achievements from client and verify them"""
        # Store sync data for verification
        sync_record = {
            "user_id": user_id,
            **sync_data.dict()
        }
        self.achievement_sync_collection.insert_one(sync_record)
        
        updated = []
        verified = []
        rejected = []
        
        for achievement_progress in sync_data.achievements:
            # Get current server state
            current = self.achievements_collection.find_one({
                "user_id": user_id,
                "achievement_id": achievement_progress.achievement_id
            })
            
            # Verify the progress is legitimate
            is_valid = self._verify_achievement_progress(
                user_id, 
                achievement_progress.achievement_id,
                achievement_progress.progress,
                achievement_progress.progress_data
            )
            
            if is_valid:
                # Accept the client's progress
                result = self.update_achievement_progress(
                    user_id,
                    achievement_progress.achievement_id,
                    achievement_progress.progress,
                    achievement_progress.progress_data
                )
                
                if result:
                    # CRITICAL FIX: Convert ObjectId to string
                    result_clean = result.copy()
                    if isinstance(result_clean.get("user_id"), ObjectId):
                        result_clean["user_id"] = str(result_clean["user_id"])
                    updated.append(result_clean)
                    
                    # Mark as verified if completed
                    if achievement_progress.progress >= 1.0:
                        self.achievements_collection.update_one(
                            {
                                "user_id": user_id,
                                "achievement_id": achievement_progress.achievement_id
                            },
                            {
                                "$set": {
                                    "verified": True,
                                    "verified_at": datetime.now()
                                }
                            }
                        )
                        verified.append(achievement_progress.achievement_id)
            else:
                # Reject suspicious progress
                rejected.append({
                    "achievement_id": achievement_progress.achievement_id,
                    "client_progress": achievement_progress.progress,
                    "server_progress": current.get("progress", 0) if current else 0,
                    "reason": "Failed verification"
                })
                
                logger.warning(f"Rejected achievement progress for user {user_id}: {achievement_progress.achievement_id}")
        
        return {
            "synced_at": datetime.now(),
            "updated_count": len(updated),
            "verified_count": len(verified),
            "rejected_count": len(rejected),
            "updated_achievements": updated,
            "verified_achievements": verified,
            "rejected_achievements": rejected
        }
    
    def _verify_achievement_progress(
        self,
        user_id: str,
        achievement_id: str,
        reported_progress: float,
        progress_data: Dict[str, Any]
    ) -> bool:
        """Verify that reported achievement progress is legitimate"""
        # Get achievement definition
        achievement_def = get_achievement_definition(achievement_id)
        if not achievement_def:
            return False
        
        trigger_type = achievement_def.trigger_condition.get("type")
        
        # Verify based on trigger type
        if trigger_type == "first_analysis":
            # Check if user has analysis records
            from ..database import get_database
            db = get_database()
            # CRITICAL FIX: Use correct user_id format for verification
            user_query = self._get_user_query_format(user_id, db, "skin_analyses")
            analysis_count = db.skin_analyses.count_documents({"user_id": user_query})
            return analysis_count > 0 and reported_progress <= 1.0
        
        elif trigger_type == "streak":
            # Verify streak is reasonable (not jumping too much)
            current = self.achievements_collection.find_one({
                "user_id": user_id,
                "achievement_id": achievement_id
            })
            
            if current:
                current_streak = current.get("progress_data", {}).get("streak_days", 0)
                reported_streak = progress_data.get("streak_days", 0)
                
                # Allow up to 7 days jump (for weekly sync)
                if reported_streak - current_streak > 7:
                    return False
            
            return True
        
        elif trigger_type == "photo_count":
            # Verify photo count matches analysis records
            from ..database import get_database
            db = get_database()
            # CRITICAL FIX: Use correct user_id format for verification
            user_query = self._get_user_query_format(user_id, db, "skin_analyses")
            analysis_count = db.skin_analyses.count_documents({"user_id": user_query})
            reported_count = progress_data.get("photo_count", 0)
            
            # Allow some discrepancy (client might count differently)
            return abs(analysis_count - reported_count) <= 2
        
        # For other types, check that progress isn't jumping unreasonably
        current = self.achievements_collection.find_one({
            "user_id": user_id,
            "achievement_id": achievement_id
        })
        
        if current:
            current_progress = current.get("progress", 0)
            # Don't allow progress to decrease or jump more than 50% in one sync
            if reported_progress < current_progress or reported_progress - current_progress > 0.5:
                return False
        
        return True
    
    def get_achievement_stats(self, user_id: str) -> Dict[str, Any]:
        """Get achievement statistics for a user"""
        achievements = self.get_user_achievements(user_id)
        
        total = len(achievements)
        unlocked = len([a for a in achievements if a.get("is_unlocked", False)])
        verified = len([a for a in achievements if a.get("verified", False)])
        total_points = sum(a.get("points", 0) for a in achievements if a.get("is_unlocked", False))
        
        # Category breakdown
        categories = {}
        for achievement in achievements:
            category = achievement.get("category", "unknown")
            if category not in categories:
                categories[category] = {"total": 0, "unlocked": 0}
            categories[category]["total"] += 1
            if achievement.get("is_unlocked", False):
                categories[category]["unlocked"] += 1
        
        # CRITICAL FIX: Clean recent unlocks to ensure ObjectId serialization
        recent_unlocks = []
        for achievement in [a for a in achievements if a.get("is_unlocked", False)][:3]:
            achievement_clean = achievement.copy()
            if isinstance(achievement_clean.get("user_id"), ObjectId):
                achievement_clean["user_id"] = str(achievement_clean["user_id"])
            recent_unlocks.append(achievement_clean)

        return {
            "total_achievements": total,
            "unlocked_achievements": unlocked,
            "verified_achievements": verified,
            "completion_percentage": round((unlocked / total * 100) if total > 0 else 0, 1),
            "total_points": total_points,
            "categories": categories,
            "recent_unlocks": recent_unlocks
        }
    
    def verify_all_user_achievements(self, user_id: str) -> Dict[str, Any]:
        """Manually verify all of a user's achievements (admin function)"""
        achievements = self.achievements_collection.find({"user_id": user_id})
        
        verified_count = 0
        for achievement in achievements:
            if achievement.get("is_unlocked") and not achievement.get("verified"):
                # Verify the achievement
                is_valid = self._verify_achievement_progress(
                    user_id,
                    achievement["achievement_id"],
                    achievement.get("progress", 0),
                    achievement.get("progress_data", {})
                )
                
                if is_valid:
                    self.achievements_collection.update_one(
                        {"_id": achievement["_id"]},
                        {
                            "$set": {
                                "verified": True,
                                "verified_at": datetime.now()
                            }
                        }
                    )
                    verified_count += 1
        
        return {
            "user_id": user_id,
            "verified_count": verified_count,
            "verified_at": datetime.now()
        }
    
    def sync_achievements_from_existing_data(self, user_id: str) -> Dict[str, Any]:
        """Sync achievements based on existing user data (analyses, routines, etc.)"""
        from ..database import get_database
        from bson import ObjectId
        
        db = get_database()
        updated_achievements = []
        
        # CRITICAL FIX: Ensure user_id is properly handled
        try:
            user_obj_id = ObjectId(user_id)
        except:
            logger.warning(f"Could not convert user_id to ObjectId: {user_id}")
            user_obj_id = user_id
        
        # Check skin analyses for First Glow and Progress Pioneer
        # CRITICAL FIX: Check BOTH ObjectId and string formats to catch all analyses
        analysis_count_oid = db.skin_analyses.count_documents({"user_id": user_obj_id})
        analysis_count_str = db.skin_analyses.count_documents({"user_id": user_id})
        analysis_count = max(analysis_count_oid, analysis_count_str)
        
        logger.info(f"Sync check - User {user_id} analyses: ObjectId={analysis_count_oid}, string={analysis_count_str}, total={analysis_count}")
        
        if analysis_count > 0:
            # First Glow achievement - ALWAYS unlock if user has any analysis
            achievement = self.update_achievement_progress(
                user_id, "first_glow", 1.0,
                {"analysis_count": analysis_count, "sync_source": "retroactive"}
            )
            if achievement:
                updated_achievements.append(achievement)
                logger.info(f"Synced First Glow achievement for user {user_id} with {analysis_count} analyses")
        
        # Progress Pioneer (10 photos)
        if analysis_count > 0:
            progress = min(1.0, analysis_count / 10.0)
            achievement = self.update_achievement_progress(
                user_id, "progress_pioneer", progress,
                {"photo_count": analysis_count}
            )
            if achievement:
                updated_achievements.append(achievement)
                logger.info(f"Synced Progress Pioneer achievement for user {user_id}: {analysis_count} photos")
        
        # Check for goals (Baseline Boss)
        # CRITICAL FIX: Check BOTH formats for goals
        goal_count_oid = db.goals.count_documents({"user_id": user_obj_id})
        goal_count_str = db.goals.count_documents({"user_id": user_id})
        goal_count = max(goal_count_oid, goal_count_str)
        
        logger.info(f"Sync check - User {user_id} goals: ObjectId={goal_count_oid}, string={goal_count_str}, total={goal_count}")
        if goal_count > 0:
            achievement = self.update_achievement_progress(
                user_id, "baseline_boss", 1.0,
                {"goal_count": goal_count}
            )
            if achievement:
                updated_achievements.append(achievement)
                logger.info(f"Synced Baseline Boss achievement for user {user_id}")
        
        # Check for routines (Routine Revolutionary)
        # CRITICAL FIX: Check BOTH formats for routines
        routines_oid = list(db.routines.find({"user_id": user_obj_id}))
        routines_str = list(db.routines.find({"user_id": user_id}))
        routines = routines_oid if routines_oid else routines_str
        
        logger.info(f"Sync check - User {user_id} routines: ObjectId={len(routines_oid)}, string={len(routines_str)}, total={len(routines)}")
        has_morning = any(r.get("type") == "morning" for r in routines)
        has_evening = any(r.get("type") == "evening" for r in routines)
        
        if has_morning and has_evening:
            achievement = self.update_achievement_progress(
                user_id, "routine_revolutionary", 1.0,
                {"has_am_pm": True}
            )
            if achievement:
                updated_achievements.append(achievement)
                logger.info(f"Synced Routine Revolutionary achievement for user {user_id}")
        
        # CRITICAL FIX: Ensure all achievements have ObjectIds converted to strings
        clean_achievements = []
        for achievement in updated_achievements:
            if achievement:
                achievement_clean = achievement.copy()
                if isinstance(achievement_clean.get("user_id"), ObjectId):
                    achievement_clean["user_id"] = str(achievement_clean["user_id"])
                clean_achievements.append(achievement_clean)

        return {
            "user_id": user_id,
            "synced_achievements": len(clean_achievements),
            "achievements": clean_achievements,
            "analysis_count": analysis_count,
            "goal_count": goal_count,
            "routine_count": len(routines),
            "synced_at": datetime.now()
        }