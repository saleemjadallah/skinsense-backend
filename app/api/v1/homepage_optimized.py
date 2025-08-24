"""
Optimized homepage API endpoints with caching and parallel data fetching
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import asyncio
from datetime import datetime, timedelta
import logging

from app.database import get_database
from app.api.deps import get_current_active_user
from app.models.user import UserModel
from app.core.cache import cache_service
from app.services.routine_service import RoutineService
from app.services.goal_service import GoalService
from app.services.progress_service import ProgressService

# Initialize services
routine_service = RoutineService()
goal_service = GoalService()
progress_service = ProgressService()

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/homepage/data", response_model=Dict[str, Any])
async def get_homepage_data(
    current_user: UserModel = Depends(get_current_active_user),
    db=Depends(get_database)
):
    """
    Optimized endpoint to fetch all homepage data in a single request with caching
    """
    user_id = str(current_user.id)
    
    # Try to get cached data first (5 minute cache)
    cache_key = f"homepage:{user_id}"
    cached_data = cache_service.get("homepage", user_id)
    if cached_data:
        logger.info(f"Returning cached homepage data for user {user_id}")
        return cached_data
    
    try:
        # Fetch all data in parallel for better performance
        results = await asyncio.gather(
            get_routine_summary_async(user_id, db),
            get_goals_summary_async(user_id, db),
            get_progress_summary_async(user_id, db),
            get_achievements_summary_async(user_id, db),
            return_exceptions=True
        )
        
        # Process results with fallbacks for errors
        routine_data = results[0] if not isinstance(results[0], Exception) else get_default_routine_summary()
        goals_data = results[1] if not isinstance(results[1], Exception) else get_default_goals_summary()
        progress_data = results[2] if not isinstance(results[2], Exception) else get_default_progress_summary()
        achievements_data = results[3] if not isinstance(results[3], Exception) else get_default_achievements_summary()
        
        # Combine all data
        homepage_data = {
            "routines": routine_data,
            "goals": goals_data,
            "progress": progress_data,
            "achievements": achievements_data,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        # Cache the result for 5 minutes
        cache_service.set("homepage", user_id, homepage_data, ttl_seconds=300)
        
        return homepage_data
        
    except Exception as e:
        logger.error(f"Error fetching homepage data: {e}")
        # Return default data on error
        return {
            "routines": get_default_routine_summary(),
            "goals": get_default_goals_summary(),
            "progress": get_default_progress_summary(),
            "achievements": get_default_achievements_summary(),
            "last_updated": datetime.utcnow().isoformat()
        }

async def get_routine_summary_async(user_id: str, db) -> Dict[str, Any]:
    """Get routine summary with optimized query"""
    try:
        # Get today's routines efficiently
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Single aggregation pipeline for all routine data
        pipeline = [
            {"$match": {"user_id": user_id, "is_active": True}},
            {"$facet": {
                "routines": [
                    {"$sort": {"type": 1, "created_at": -1}},
                    {"$limit": 5}
                ],
                "counts": [
                    {"$group": {
                        "_id": "$type",
                        "count": {"$sum": 1}
                    }}
                ],
                "today_completions": [
                    {"$lookup": {
                        "from": "routine_completions",
                        "let": {"routine_id": "$_id"},
                        "pipeline": [
                            {"$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$routine_id", "$$routine_id"]},
                                        {"$gte": ["$completed_at", today_start]}
                                    ]
                                }
                            }}
                        ],
                        "as": "completions"
                    }},
                    {"$project": {
                        "routine_id": "$_id",
                        "completed": {"$gt": [{"$size": "$completions"}, 0]}
                    }}
                ]
            }}
        ]
        
        result = list(db.routines.aggregate(pipeline, maxTimeMS=3000))
        
        if result:
            data = result[0]
            routines = data.get("routines", [])
            completed_count = sum(1 for r in data.get("today_completions", []) if r.get("completed"))
            total_routines = len(routines)
            
            return {
                "total_routines": total_routines,
                "completed_today": completed_count,
                "completion_rate": (completed_count / total_routines * 100) if total_routines > 0 else 0,
                "active_routines": [
                    {
                        "id": str(r["_id"]),
                        "name": r.get("name", "Unnamed Routine"),
                        "type": r.get("type", "general"),
                        "steps_count": len(r.get("steps", []))
                    } for r in routines[:3]  # Only return top 3 for homepage
                ]
            }
        
        return get_default_routine_summary()
        
    except Exception as e:
        logger.error(f"Error getting routine summary: {e}")
        return get_default_routine_summary()

async def get_goals_summary_async(user_id: str, db) -> Dict[str, Any]:
    """Get goals summary with optimized query"""
    try:
        # Single aggregation for all goal stats
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$facet": {
                "active": [
                    {"$match": {"status": "active"}},
                    {"$sort": {"created_at": -1}},
                    {"$limit": 3}
                ],
                "stats": [
                    {"$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }}
                ]
            }}
        ]
        
        result = list(db.goals.aggregate(pipeline, maxTimeMS=3000))
        
        if result:
            data = result[0]
            active_goals = data.get("active", [])
            stats = {s["_id"]: s["count"] for s in data.get("stats", [])}
            
            return {
                "active_count": stats.get("active", 0),
                "completed_count": stats.get("completed", 0),
                "total_count": sum(stats.values()),
                "active_goals": [
                    {
                        "id": str(g["_id"]),
                        "title": g.get("title", "Unnamed Goal"),
                        "progress": g.get("current_value", 0),
                        "target": g.get("target_value", 100)
                    } for g in active_goals
                ]
            }
        
        return get_default_goals_summary()
        
    except Exception as e:
        logger.error(f"Error getting goals summary: {e}")
        return get_default_goals_summary()

async def get_progress_summary_async(user_id: str, db) -> Dict[str, Any]:
    """Get progress summary with optimized query"""
    try:
        # Get latest analysis with single query
        latest_analysis = db.skin_analyses.find_one(
            {"user_id": user_id},
            {"orbo_response": 1, "created_at": 1},
            sort=[("created_at", -1)]
        )
        
        if latest_analysis:
            metrics = latest_analysis.get("orbo_response", {})
            return {
                "overall_score": metrics.get("overall_skin_health_score", 0),
                "hydration": metrics.get("hydration", 0),
                "texture": metrics.get("smoothness", 0),
                "radiance": metrics.get("radiance", 0),
                "last_analysis": latest_analysis.get("created_at").isoformat() if latest_analysis.get("created_at") else None,
                "has_data": True
            }
        
        return get_default_progress_summary()
        
    except Exception as e:
        logger.error(f"Error getting progress summary: {e}")
        return get_default_progress_summary()

async def get_achievements_summary_async(user_id: str, db) -> Dict[str, Any]:
    """Get achievements summary with optimized query"""
    try:
        # Count achievements efficiently
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$unlocked",
                "count": {"$sum": 1}
            }}
        ]
        
        result = list(db.achievements.aggregate(pipeline, maxTimeMS=3000))
        stats = {r["_id"]: r["count"] for r in result}
        
        # Get streak from routine completions
        today = datetime.utcnow().date()
        streak = 0
        current_date = today
        
        while True:
            start = datetime.combine(current_date, datetime.min.time())
            end = start + timedelta(days=1)
            
            completion = db.routine_completions.find_one({
                "user_id": user_id,
                "completed_at": {"$gte": start, "$lt": end}
            })
            
            if completion:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return {
            "unlocked_count": stats.get(True, 0),
            "total_count": sum(stats.values()),
            "current_streak": streak,
            "points": stats.get(True, 0) * 10  # Simple points calculation
        }
        
    except Exception as e:
        logger.error(f"Error getting achievements summary: {e}")
        return get_default_achievements_summary()

def get_default_routine_summary() -> Dict[str, Any]:
    """Default routine summary when data unavailable"""
    return {
        "total_routines": 0,
        "completed_today": 0,
        "completion_rate": 0,
        "active_routines": []
    }

def get_default_goals_summary() -> Dict[str, Any]:
    """Default goals summary when data unavailable"""
    return {
        "active_count": 0,
        "completed_count": 0,
        "total_count": 0,
        "active_goals": []
    }

def get_default_progress_summary() -> Dict[str, Any]:
    """Default progress summary when data unavailable"""
    return {
        "overall_score": 0,
        "hydration": 0,
        "texture": 0,
        "radiance": 0,
        "last_analysis": None,
        "has_data": False
    }

def get_default_achievements_summary() -> Dict[str, Any]:
    """Default achievements summary when data unavailable"""
    return {
        "unlocked_count": 0,
        "total_count": 0,
        "current_streak": 0,
        "points": 0
    }