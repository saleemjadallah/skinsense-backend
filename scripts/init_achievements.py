#!/usr/bin/env python3
"""
Initialize achievements for all existing users.
Run this script after deploying the achievement system to set up achievements for existing users.

Usage:
    python scripts/init_achievements.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from pymongo import MongoClient
from app.models.achievement import ACHIEVEMENT_DEFINITIONS, UserAchievement
from app.services.achievement_service import AchievementService
from app.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_achievements_for_all_users():
    """Initialize achievements for all existing users"""
    try:
        # Connect to MongoDB
        client = MongoClient(settings.MONGODB_URL)
        db_name = settings.MONGODB_URL.split("/")[-1].split("?")[0]
        db = client[db_name]
        
        # Initialize achievement service
        achievement_service = AchievementService()
        
        # Get all users
        users = list(db.users.find({}))
        logger.info(f"Found {len(users)} users to initialize achievements for")
        
        initialized_count = 0
        skipped_count = 0
        error_count = 0
        
        for user in users:
            user_id = str(user["_id"])
            
            try:
                # Check if user already has achievements
                existing = db.user_achievements.find_one({"user_id": user_id})
                
                if existing:
                    logger.info(f"User {user_id} already has achievements, skipping")
                    skipped_count += 1
                    continue
                
                # Initialize achievements for this user
                achievements = achievement_service.initialize_user_achievements(user_id)
                logger.info(f"Initialized {len(achievements)} achievements for user {user_id}")
                initialized_count += 1
                
                # Check if we should grant any achievements based on existing data
                check_existing_data_for_achievements(db, user_id, achievement_service)
                
            except Exception as e:
                logger.error(f"Error initializing achievements for user {user_id}: {str(e)}")
                error_count += 1
        
        logger.info(f"Achievement initialization complete:")
        logger.info(f"  - Initialized: {initialized_count}")
        logger.info(f"  - Skipped: {skipped_count}")
        logger.info(f"  - Errors: {error_count}")
        
    except Exception as e:
        logger.error(f"Error initializing achievements: {str(e)}")
        sys.exit(1)


def check_existing_data_for_achievements(db, user_id: str, achievement_service: AchievementService):
    """Check existing user data and grant appropriate achievements"""
    try:
        # Check for First Glow (first analysis)
        analyses = list(db.skin_analyses.find({"user_id": user_id}))
        if analyses:
            logger.info(f"User {user_id} has {len(analyses)} analyses, granting First Glow")
            achievement_service.update_achievement_progress(user_id, "first_glow", 1.0)
            
            # Update Progress Pioneer based on analysis count
            if len(analyses) >= 10:
                achievement_service.update_achievement_progress(
                    user_id, "progress_pioneer", 1.0,
                    {"photo_count": len(analyses)}
                )
            else:
                progress = len(analyses) / 10.0
                achievement_service.update_achievement_progress(
                    user_id, "progress_pioneer", progress,
                    {"photo_count": len(analyses)}
                )
        
        # Check for Baseline Boss (first goal)
        goals = list(db.goals.find({"user_id": user_id}))
        if goals:
            logger.info(f"User {user_id} has {len(goals)} goals, granting Baseline Boss")
            achievement_service.update_achievement_progress(user_id, "baseline_boss", 1.0)
        
        # Check for Routine Revolutionary (AM/PM routines)
        routines = list(db.routines.find({"user_id": user_id}))
        has_morning = any(r.get("type") == "morning" for r in routines)
        has_evening = any(r.get("type") == "evening" for r in routines)
        
        if has_morning and has_evening:
            logger.info(f"User {user_id} has AM/PM routines, granting Routine Revolutionary")
            achievement_service.update_achievement_progress(
                user_id, "routine_revolutionary", 1.0,
                {"has_am_pm": True}
            )
        
        # Check for skin score improvement (Glow Up)
        if len(analyses) >= 2:
            # Sort by date
            analyses.sort(key=lambda x: x.get("created_at", datetime.min))
            
            first_score = analyses[0].get("orbo_response", {}).get("overall_skin_health_score", 0)
            last_score = analyses[-1].get("orbo_response", {}).get("overall_skin_health_score", 0)
            
            if last_score > first_score:
                improvement = last_score - first_score
                if improvement >= 10:
                    logger.info(f"User {user_id} has {improvement} point improvement, granting Glow Up")
                    achievement_service.update_achievement_progress(
                        user_id, "glow_up", 1.0,
                        {"improvement": improvement}
                    )
                else:
                    progress = min(1.0, improvement / 10.0)
                    achievement_service.update_achievement_progress(
                        user_id, "glow_up", progress,
                        {"improvement": improvement}
                    )
        
        # Note: Streak-based achievements would need daily check-in data
        # Community achievements would need community interaction data
        
    except Exception as e:
        logger.error(f"Error checking existing data for user {user_id}: {str(e)}")


def create_indexes():
    """Create necessary indexes for achievement collections"""
    try:
        client = MongoClient(settings.MONGODB_URL)
        db_name = settings.MONGODB_URL.split("/")[-1].split("?")[0]
        db = client[db_name]
        
        # Create indexes for user_achievements
        db.user_achievements.create_index([("user_id", 1), ("achievement_id", 1)], unique=True)
        db.user_achievements.create_index("user_id")
        db.user_achievements.create_index("is_unlocked")
        db.user_achievements.create_index("verified")
        
        # Create indexes for achievement_actions
        db.achievement_actions.create_index("user_id")
        db.achievement_actions.create_index("action_type")
        db.achievement_actions.create_index("timestamp")
        
        # Create indexes for achievement_sync
        db.achievement_sync.create_index("user_id")
        db.achievement_sync.create_index("sync_timestamp")
        
        # Create indexes for daily_checkins (for streak tracking)
        db.daily_checkins.create_index([("user_id", 1), ("date", 1)], unique=True)
        db.daily_checkins.create_index("user_id")
        db.daily_checkins.create_index("date")
        
        logger.info("Successfully created all achievement-related indexes")
        
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")
        sys.exit(1)


def show_achievement_stats():
    """Show statistics about achievements in the database"""
    try:
        client = MongoClient(settings.MONGODB_URL)
        db_name = settings.MONGODB_URL.split("/")[-1].split("?")[0]
        db = client[db_name]
        
        total_users = db.users.count_documents({})
        users_with_achievements = db.user_achievements.distinct("user_id")
        total_achievements = db.user_achievements.count_documents({})
        unlocked_achievements = db.user_achievements.count_documents({"is_unlocked": True})
        verified_achievements = db.user_achievements.count_documents({"verified": True})
        
        print("\n" + "="*50)
        print("ACHIEVEMENT SYSTEM STATISTICS")
        print("="*50)
        print(f"Total Users: {total_users}")
        print(f"Users with Achievements: {len(users_with_achievements)}")
        print(f"Total Achievement Records: {total_achievements}")
        print(f"Unlocked Achievements: {unlocked_achievements}")
        print(f"Verified Achievements: {verified_achievements}")
        print(f"Available Achievement Types: {len(ACHIEVEMENT_DEFINITIONS)}")
        
        # Show achievement breakdown
        print("\nAchievement Breakdown:")
        for achievement_def in ACHIEVEMENT_DEFINITIONS:
            unlocked = db.user_achievements.count_documents({
                "achievement_id": achievement_def.achievement_id,
                "is_unlocked": True
            })
            total = db.user_achievements.count_documents({
                "achievement_id": achievement_def.achievement_id
            })
            
            percentage = (unlocked / total * 100) if total > 0 else 0
            print(f"  - {achievement_def.title}: {unlocked}/{total} unlocked ({percentage:.1f}%)")
        
        print("="*50 + "\n")
        
    except Exception as e:
        logger.error(f"Error showing stats: {str(e)}")


if __name__ == "__main__":
    print("SkinSense Achievement System Initialization")
    print("=" * 50)
    
    # Create indexes first
    print("\n1. Creating database indexes...")
    create_indexes()
    
    # Initialize achievements for all users
    print("\n2. Initializing achievements for all users...")
    initialize_achievements_for_all_users()
    
    # Show statistics
    print("\n3. Achievement statistics:")
    show_achievement_stats()
    
    print("\nInitialization complete!")