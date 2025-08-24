#!/usr/bin/env python3
"""
Initialize goal templates and achievement definitions in MongoDB
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import connect_to_mongo, get_database
from app.models.goal import GoalTemplate, Achievement


def create_goal_templates():
    """Create default goal templates"""
    connect_to_mongo()
    db = get_database()
    
    # Clear existing templates
    db.goal_templates.delete_many({})
    
    templates = [
        {
            "title": "Hydration Hero Challenge",
            "description": "Boost your skin's hydration levels through consistent skincare and lifestyle changes",
            "type": "parameter_improvement",
            "category": "hydration",
            "default_duration_days": 30,
            "default_improvement_target": 15.0,
            "difficulty_level": "moderate",
            "suitable_for_age_groups": ["18_24", "25_34", "35_44", "45_54", "55_plus"],
            "suitable_for_skin_types": ["dry", "normal", "combination"],
            "suitable_for_concerns": ["hydration", "dryness", "flakiness"],
            "milestone_templates": [
                {"percentage_trigger": 25, "title": "Hydration Starter", "description": "First week of consistent hydrating routine"},
                {"percentage_trigger": 50, "title": "Moisture Master", "description": "Noticeable improvement in skin plumpness"},
                {"percentage_trigger": 75, "title": "Dewy Devotee", "description": "Skin feels consistently hydrated"},
                {"percentage_trigger": 100, "title": "Hydration Hero", "description": "Target hydration level achieved!"}
            ],
            "tips": [
                "Drink at least 8 glasses of water daily",
                "Use a humidifier in dry environments",
                "Apply moisturizer on damp skin to lock in hydration",
                "Incorporate hyaluronic acid serums into your routine"
            ],
            "recommended_products": [
                {"category": "serum", "name": "Hyaluronic Acid Serum", "reasoning": "Draws moisture into skin"},
                {"category": "moisturizer", "name": "Ceramide Moisturizer", "reasoning": "Strengthens skin barrier"}
            ]
        },
        {
            "title": "Acne Control Mission",
            "description": "Clear your skin and prevent future breakouts with targeted treatments",
            "type": "parameter_improvement",
            "category": "acne",
            "default_duration_days": 45,
            "default_improvement_target": 20.0,
            "difficulty_level": "moderate",
            "suitable_for_age_groups": ["under_18", "18_24", "25_34"],
            "suitable_for_skin_types": ["oily", "combination"],
            "suitable_for_concerns": ["acne", "breakouts", "blackheads"],
            "milestone_templates": [
                {"percentage_trigger": 25, "title": "Purge Phase", "description": "Initial skin purging - stay consistent!"},
                {"percentage_trigger": 50, "title": "Clarity Improver", "description": "Active breakouts reducing"},
                {"percentage_trigger": 75, "title": "Smooth Operator", "description": "Skin texture improving noticeably"},
                {"percentage_trigger": 100, "title": "Clear Skin Champion", "description": "Target acne reduction achieved!"}
            ],
            "tips": [
                "Introduce actives slowly to avoid irritation",
                "Always use sunscreen when using acne treatments",
                "Avoid picking at blemishes",
                "Change pillowcases frequently"
            ],
            "recommended_products": [
                {"category": "cleanser", "name": "Salicylic Acid Cleanser", "reasoning": "Unclogs pores"},
                {"category": "treatment", "name": "Niacinamide Treatment", "reasoning": "Reduces inflammation"}
            ]
        },
        {
            "title": "Routine Consistency Master",
            "description": "Build lasting skincare habits by completing your routine consistently",
            "type": "routine_adherence",
            "category": "routine",
            "default_duration_days": 30,
            "default_improvement_target": 85.0,
            "difficulty_level": "easy",
            "suitable_for_age_groups": ["under_18", "18_24", "25_34", "35_44", "45_54", "55_plus"],
            "suitable_for_skin_types": ["dry", "oily", "normal", "combination", "sensitive"],
            "suitable_for_concerns": ["routine", "consistency", "habits"],
            "milestone_templates": [
                {"percentage_trigger": 25, "title": "Week One Warrior", "description": "7 days of consistent routine"},
                {"percentage_trigger": 50, "title": "Habit Former", "description": "Two weeks of dedication"},
                {"percentage_trigger": 75, "title": "Routine Rockstar", "description": "Three weeks of consistency"},
                {"percentage_trigger": 100, "title": "Consistency Champion", "description": "30 days of perfect routine adherence!"}
            ],
            "tips": [
                "Set specific times for your routine",
                "Keep products visible as reminders",
                "Start with a simple routine",
                "Track your progress daily"
            ]
        },
        {
            "title": "Anti-Aging Advocate",
            "description": "Reduce fine lines and improve skin firmness through targeted treatments",
            "type": "parameter_improvement",
            "category": "aging",
            "default_duration_days": 60,
            "default_improvement_target": 12.0,
            "difficulty_level": "challenging",
            "suitable_for_age_groups": ["35_44", "45_54", "55_plus"],
            "suitable_for_skin_types": ["dry", "normal", "combination"],
            "suitable_for_concerns": ["fine_lines_wrinkles", "firmness", "aging"],
            "milestone_templates": [
                {"percentage_trigger": 25, "title": "Prevention Starter", "description": "Beginning anti-aging routine"},
                {"percentage_trigger": 50, "title": "Firming Fighter", "description": "Skin texture beginning to improve"},
                {"percentage_trigger": 75, "title": "Youth Protector", "description": "Visible firmness improvement"},
                {"percentage_trigger": 100, "title": "Age-Defying Master", "description": "Significant anti-aging results achieved!"}
            ],
            "tips": [
                "Consistency is key with anti-aging ingredients",
                "Always use sunscreen during the day",
                "Introduce retinoids gradually",
                "Support with antioxidant serums"
            ],
            "recommended_products": [
                {"category": "serum", "name": "Vitamin C Serum", "reasoning": "Antioxidant protection"},
                {"category": "treatment", "name": "Retinol Treatment", "reasoning": "Stimulates collagen production"}
            ]
        }
    ]
    
    # Insert templates
    for template_data in templates:
        template = GoalTemplate(**template_data)
        db.goal_templates.insert_one(template.dict(by_alias=True))
    
    print(f"Created {len(templates)} goal templates")


def create_achievement_definitions():
    """Create default achievement definitions"""
    db = get_database()
    
    # Clear existing achievements
    db.achievements.delete_many({})
    
    achievements = [
        {
            "achievement_id": "first_goal_completed",
            "title": "Goal Getter",
            "description": "Complete your first goal",
            "icon": "trophy",
            "category": "goal",
            "tier": "bronze",
            "points": 100,
            "criteria": {"goals_completed": 1}
        },
        {
            "achievement_id": "hydration_hero",
            "title": "Hydration Hero",
            "description": "Achieve 85+ hydration score",
            "icon": "droplet",
            "category": "parameter",
            "tier": "silver",
            "points": 150,
            "criteria": {"parameter": "hydration", "min_score": 85}
        },
        {
            "achievement_id": "consistency_champion",
            "title": "Consistency Champion",
            "description": "Complete routines for 30 days straight",
            "icon": "calendar",
            "category": "routine",
            "tier": "gold",
            "points": 200,
            "criteria": {"routine_streak": 30}
        },
        {
            "achievement_id": "skin_transformation",
            "title": "Skin Transformation",
            "description": "Improve overall score by 20 points",
            "icon": "star",
            "category": "parameter",
            "tier": "platinum",
            "points": 500,
            "criteria": {"overall_improvement": 20}
        },
        {
            "achievement_id": "acne_warrior",
            "title": "Acne Warrior",
            "description": "Achieve 80+ acne score (clear skin)",
            "icon": "shield",
            "category": "parameter",
            "tier": "silver",
            "points": 175,
            "criteria": {"parameter": "acne", "min_score": 80}
        },
        {
            "achievement_id": "radiance_master",
            "title": "Radiance Master",
            "description": "Achieve 90+ radiance score",
            "icon": "sun",
            "category": "parameter",
            "tier": "gold",
            "points": 250,
            "criteria": {"parameter": "radiance", "min_score": 90}
        },
        {
            "achievement_id": "multi_goal_master",
            "title": "Multi-Goal Master",
            "description": "Complete 5 different goals",
            "icon": "target",
            "category": "goal",
            "tier": "gold",
            "points": 300,
            "criteria": {"goals_completed": 5}
        },
        {
            "achievement_id": "routine_veteran",
            "title": "Routine Veteran",
            "description": "Complete 100 routine sessions",
            "icon": "medal",
            "category": "routine",
            "tier": "platinum",
            "points": 400,
            "criteria": {"routines_completed": 100}
        },
        {
            "achievement_id": "early_bird",
            "title": "Early Bird",
            "description": "Complete morning routine 20 days in a row",
            "icon": "sunrise",
            "category": "routine",
            "tier": "bronze",
            "points": 125,
            "criteria": {"morning_routine_streak": 20}
        },
        {
            "achievement_id": "night_owl",
            "title": "Night Owl",
            "description": "Complete evening routine 20 days in a row",
            "icon": "moon",
            "category": "routine",
            "tier": "bronze",
            "points": 125,
            "criteria": {"evening_routine_streak": 20}
        }
    ]
    
    # Insert achievement definitions
    for achievement_data in achievements:
        achievement = Achievement(**achievement_data)
        db.achievements.insert_one(achievement.dict(by_alias=True))
    
    print(f"Created {len(achievements)} achievement definitions")


def main():
    """Main initialization function"""
    try:
        print("Initializing goal templates and achievements...")
        
        await create_goal_templates()
        await create_achievement_definitions()
        
        print("Goal initialization completed successfully!")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        raise


if __name__ == "__main__":
    main()