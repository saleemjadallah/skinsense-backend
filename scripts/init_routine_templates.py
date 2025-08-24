#!/usr/bin/env python3
"""
Initialize routine templates in MongoDB
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import connect_to_mongo, get_database
from app.models.routine import RoutineTemplate, RoutineStep, RoutineProduct


def create_routine_templates():
    """Create default routine templates"""
    connect_to_mongo()
    db = get_database()
    
    # Clear existing templates
    db.routine_templates.delete_many({})
    
    templates = [
        {
            "name": "Basic Morning Routine",
            "description": "Simple and effective morning skincare routine for all skin types",
            "type": "morning",
            "target_concerns": ["general", "maintenance"],
            "suitable_for_skin_types": ["normal", "combination", "dry", "oily"],
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product": {"name": "Gentle Morning Cleanser", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Gently massage onto damp face in circular motions, rinse with lukewarm water",
                    "ai_reasoning": "Removes overnight impurities and excess oils",
                    "frequency": "daily"
                },
                {
                    "order": 2,
                    "category": "serum",
                    "product": {"name": "Vitamin C Serum", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply 2-3 drops to clean face, pat gently until absorbed",
                    "ai_reasoning": "Provides antioxidant protection and brightening benefits",
                    "frequency": "daily"
                },
                {
                    "order": 3,
                    "category": "moisturizer",
                    "product": {"name": "Daily Moisturizer", "brand": "Recommended"},
                    "duration_seconds": 45,
                    "instructions": "Apply evenly to face and neck using upward motions",
                    "ai_reasoning": "Hydrates skin and creates a barrier for makeup",
                    "frequency": "daily"
                },
                {
                    "order": 4,
                    "category": "sunscreen",
                    "product": {"name": "Broad Spectrum SPF 30", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply generously 15 minutes before sun exposure",
                    "ai_reasoning": "Critical protection against UV damage and premature aging",
                    "frequency": "daily"
                }
            ],
            "difficulty_level": "beginner",
            "estimated_cost": "budget",
            "popularity_score": 4.5
        },
        {
            "name": "Hydrating Evening Routine",
            "description": "Intensive hydration routine for dry and dehydrated skin",
            "type": "evening",
            "target_concerns": ["hydration", "dryness"],
            "suitable_for_skin_types": ["dry", "normal", "sensitive"],
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product": {"name": "Cream Cleanser", "brand": "Recommended"},
                    "duration_seconds": 90,
                    "instructions": "Massage gently onto dry skin, add water to emulsify, rinse thoroughly",
                    "ai_reasoning": "Gentle cleansing without stripping natural oils",
                    "frequency": "daily"
                },
                {
                    "order": 2,
                    "category": "toner",
                    "product": {"name": "Hydrating Toner", "brand": "Recommended"},
                    "duration_seconds": 20,
                    "instructions": "Pat onto clean face with hands or cotton pad",
                    "ai_reasoning": "Preps skin for better product absorption",
                    "frequency": "daily"
                },
                {
                    "order": 3,
                    "category": "serum",
                    "product": {"name": "Hyaluronic Acid Serum", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply to slightly damp skin for maximum hydration",
                    "ai_reasoning": "Draws moisture into skin for intense hydration",
                    "frequency": "daily"
                },
                {
                    "order": 4,
                    "category": "face_oil",
                    "product": {"name": "Facial Oil Blend", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Warm 2-3 drops between palms, press gently onto face",
                    "ai_reasoning": "Seals in moisture and provides nourishing fatty acids",
                    "frequency": "daily"
                },
                {
                    "order": 5,
                    "category": "moisturizer",
                    "product": {"name": "Rich Night Moisturizer", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Apply in upward circular motions, extend to neck",
                    "ai_reasoning": "Locks in all previous layers and repairs overnight",
                    "frequency": "daily"
                }
            ],
            "difficulty_level": "intermediate",
            "estimated_cost": "moderate",
            "popularity_score": 4.2
        },
        {
            "name": "Acne-Fighting Routine",
            "description": "Targeted routine for acne-prone and oily skin",
            "type": "evening",
            "target_concerns": ["acne", "breakouts", "oily"],
            "suitable_for_skin_types": ["oily", "combination"],
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product": {"name": "Salicylic Acid Cleanser", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Massage gently, avoiding eye area, rinse thoroughly",
                    "ai_reasoning": "Unclogs pores and removes excess oil",
                    "frequency": "daily"
                },
                {
                    "order": 2,
                    "category": "treatment",
                    "product": {"name": "BHA Treatment 2%", "brand": "Recommended"},
                    "duration_seconds": 15,
                    "instructions": "Apply thin layer to affected areas, start 3x/week",
                    "ai_reasoning": "Exfoliates inside pores to prevent breakouts",
                    "frequency": "daily"
                },
                {
                    "order": 3,
                    "category": "serum",
                    "product": {"name": "Niacinamide Serum", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply 2-3 drops, avoiding direct contact with acids",
                    "ai_reasoning": "Reduces inflammation and controls oil production",
                    "frequency": "daily"
                },
                {
                    "order": 4,
                    "category": "moisturizer",
                    "product": {"name": "Oil-Free Moisturizer", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply light layer to avoid clogging pores",
                    "ai_reasoning": "Hydrates without adding excess oil",
                    "frequency": "daily"
                },
                {
                    "order": 5,
                    "category": "spot_treatment",
                    "product": {"name": "Benzoyl Peroxide Spot Treatment", "brand": "Recommended"},
                    "duration_seconds": 10,
                    "instructions": "Dab small amount on active breakouts only",
                    "ai_reasoning": "Kills acne bacteria and speeds healing",
                    "frequency": "as_needed"
                }
            ],
            "difficulty_level": "intermediate",
            "estimated_cost": "moderate",
            "popularity_score": 4.0
        },
        {
            "name": "Anti-Aging Power Routine",
            "description": "Advanced anti-aging routine with powerful actives",
            "type": "evening",
            "target_concerns": ["fine_lines_wrinkles", "firmness", "aging"],
            "suitable_for_skin_types": ["normal", "dry", "combination"],
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product": {"name": "Gentle Gel Cleanser", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Massage thoroughly to remove makeup and sunscreen",
                    "ai_reasoning": "Clean base essential for active ingredient penetration",
                    "frequency": "daily"
                },
                {
                    "order": 2,
                    "category": "treatment",
                    "product": {"name": "Retinol 0.5%", "brand": "Recommended"},
                    "duration_seconds": 20,
                    "instructions": "Apply pea-sized amount, start 2x/week, avoid eye area",
                    "ai_reasoning": "Stimulates collagen production and cell turnover",
                    "frequency": "daily"
                },
                {
                    "order": 3,
                    "category": "serum",
                    "product": {"name": "Peptide Serum", "brand": "Recommended"},
                    "duration_seconds": 45,
                    "instructions": "Layer after retinol has absorbed, focus on problem areas",
                    "ai_reasoning": "Supports skin repair and firmness",
                    "frequency": "daily"
                },
                {
                    "order": 4,
                    "category": "eye_cream",
                    "product": {"name": "Anti-Aging Eye Cream", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Gently pat around eye area with ring finger",
                    "ai_reasoning": "Targets delicate eye area concerns",
                    "frequency": "daily"
                },
                {
                    "order": 5,
                    "category": "moisturizer",
                    "product": {"name": "Collagen Boosting Moisturizer", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Apply generously to seal in active ingredients",
                    "ai_reasoning": "Provides deep hydration and supports skin barrier",
                    "frequency": "daily"
                }
            ],
            "difficulty_level": "advanced",
            "estimated_cost": "premium",
            "popularity_score": 4.3
        },
        {
            "name": "Sensitive Skin Soothing Routine",
            "description": "Gentle routine for sensitive and reactive skin",
            "type": "morning",
            "target_concerns": ["redness", "sensitivity", "irritation"],
            "suitable_for_skin_types": ["sensitive", "dry"],
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product": {"name": "Fragrance-Free Cream Cleanser", "brand": "Recommended"},
                    "duration_seconds": 45,
                    "instructions": "Use cool water, pat dry gently with soft towel",
                    "ai_reasoning": "Minimal irritation cleansing",
                    "frequency": "daily"
                },
                {
                    "order": 2,
                    "category": "serum",
                    "product": {"name": "Centella Asiatica Serum", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply with gentle patting motions",
                    "ai_reasoning": "Calms inflammation and reduces redness",
                    "frequency": "daily"
                },
                {
                    "order": 3,
                    "category": "moisturizer",
                    "product": {"name": "Barrier Repair Moisturizer", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Apply in thin layers, build up as needed",
                    "ai_reasoning": "Strengthens skin barrier function",
                    "frequency": "daily"
                },
                {
                    "order": 4,
                    "category": "sunscreen",
                    "product": {"name": "Mineral Sunscreen SPF 30", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Use mineral formula to avoid chemical irritation",
                    "ai_reasoning": "Gentle protection without sensitizing ingredients",
                    "frequency": "daily"
                }
            ],
            "difficulty_level": "beginner",
            "estimated_cost": "moderate",
            "popularity_score": 4.1
        },
        {
            "name": "Weekly Exfoliation Treatment",
            "description": "Deep exfoliation for smoother, brighter skin",
            "type": "weekly",
            "target_concerns": ["smoothness", "radiance", "texture"],
            "suitable_for_skin_types": ["normal", "oily", "combination"],
            "steps": [
                {
                    "order": 1,
                    "category": "cleanser",
                    "product": {"name": "Deep Cleansing Gel", "brand": "Recommended"},
                    "duration_seconds": 90,
                    "instructions": "Thorough cleanse to prepare skin for treatment",
                    "ai_reasoning": "Clean base for maximum exfoliation benefit",
                    "frequency": "weekly"
                },
                {
                    "order": 2,
                    "category": "exfoliant",
                    "product": {"name": "AHA/BHA Exfoliant", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply thin layer, avoid eye area, leave on for 10-15 minutes",
                    "ai_reasoning": "Removes dead skin cells and unclogs pores",
                    "frequency": "weekly"
                },
                {
                    "order": 3,
                    "category": "mask",
                    "product": {"name": "Hydrating Recovery Mask", "brand": "Recommended"},
                    "duration_seconds": 900,
                    "instructions": "Apply thick layer after exfoliant, leave 15 minutes",
                    "ai_reasoning": "Soothes and hydrates after exfoliation",
                    "frequency": "weekly"
                },
                {
                    "order": 4,
                    "category": "serum",
                    "product": {"name": "Antioxidant Serum", "brand": "Recommended"},
                    "duration_seconds": 30,
                    "instructions": "Apply to freshly exfoliated skin for better absorption",
                    "ai_reasoning": "Provides protective antioxidants",
                    "frequency": "weekly"
                },
                {
                    "order": 5,
                    "category": "moisturizer",
                    "product": {"name": "Intensive Repair Moisturizer", "brand": "Recommended"},
                    "duration_seconds": 60,
                    "instructions": "Apply generously to support skin recovery",
                    "ai_reasoning": "Deep hydration for post-exfoliation recovery",
                    "frequency": "weekly"
                }
            ],
            "difficulty_level": "intermediate",
            "estimated_cost": "moderate",
            "popularity_score": 3.8
        }
    ]
    
    # Insert templates
    for template_data in templates:
        # Convert steps to proper RoutineStep objects
        steps = []
        for step_data in template_data["steps"]:
            product_data = step_data.pop("product")
            product = RoutineProduct(**product_data)
            step = RoutineStep(product=product, **step_data)
            steps.append(step)
        
        template_data["steps"] = steps
        template = RoutineTemplate(**template_data)
        db.routine_templates.insert_one(template.dict(by_alias=True))
    
    print(f"Created {len(templates)} routine templates")


def main():
    """Main initialization function"""
    try:
        print("Initializing routine templates...")
        
        create_routine_templates()
        
        print("Routine initialization completed successfully!")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        raise


if __name__ == "__main__":
    main() 