"""
Routine templates for different skin types and concerns
These can be loaded into the routine_templates collection
"""

from datetime import datetime
from app.models.routine import RoutineStep, RoutineProduct

ROUTINE_TEMPLATES = [
    {
        "name": "Hydration Boost Morning",
        "description": "Intensive hydration routine for dry, dehydrated skin",
        "type": "morning",
        "target_concerns": ["hydration", "smoothness"],
        "suitable_for_skin_types": ["dry", "normal"],
        "difficulty_level": "beginner",
        "estimated_cost": "moderate",
        "steps": [
            {
                "order": 1,
                "category": "cleanser",
                "product": {
                    "name": "Gentle Cream Cleanser",
                    "brand": "CeraVe"
                },
                "duration_seconds": 60,
                "instructions": "Massage gently with lukewarm water",
                "frequency": "daily"
            },
            {
                "order": 2,
                "category": "toner",
                "product": {
                    "name": "Hydrating Toner",
                    "brand": "Laneige"
                },
                "duration_seconds": 30,
                "instructions": "Pat into skin with hands",
                "frequency": "daily"
            },
            {
                "order": 3,
                "category": "serum",
                "product": {
                    "name": "Hyaluronic Acid Serum",
                    "brand": "The Ordinary"
                },
                "duration_seconds": 30,
                "instructions": "Apply to damp skin for best results",
                "frequency": "daily"
            },
            {
                "order": 4,
                "category": "moisturizer",
                "product": {
                    "name": "Rich Moisturizing Cream",
                    "brand": "Cetaphil"
                },
                "duration_seconds": 30,
                "instructions": "Apply generously to face and neck",
                "frequency": "daily"
            },
            {
                "order": 5,
                "category": "sunscreen",
                "product": {
                    "name": "Hydrating SPF 50",
                    "brand": "La Roche-Posay"
                },
                "duration_seconds": 30,
                "instructions": "Apply 15 minutes before sun exposure",
                "frequency": "daily"
            }
        ]
    },
    {
        "name": "Clear Skin Evening",
        "description": "Acne-fighting routine for clearer skin",
        "type": "evening",
        "target_concerns": ["acne", "redness"],
        "suitable_for_skin_types": ["oily", "combination"],
        "difficulty_level": "intermediate",
        "estimated_cost": "moderate",
        "steps": [
            {
                "order": 1,
                "category": "cleanser",
                "product": {
                    "name": "Salicylic Acid Cleanser",
                    "brand": "CeraVe"
                },
                "duration_seconds": 60,
                "instructions": "Focus on T-zone and problem areas",
                "frequency": "daily"
            },
            {
                "order": 2,
                "category": "treatment",
                "product": {
                    "name": "BHA Liquid Exfoliant",
                    "brand": "Paula's Choice"
                },
                "duration_seconds": 30,
                "instructions": "Apply with cotton pad, avoid eye area",
                "frequency": "daily"
            },
            {
                "order": 3,
                "category": "serum",
                "product": {
                    "name": "Niacinamide 10% + Zinc",
                    "brand": "The Ordinary"
                },
                "duration_seconds": 30,
                "instructions": "Apply to clean skin",
                "frequency": "daily"
            },
            {
                "order": 4,
                "category": "spot_treatment",
                "product": {
                    "name": "Benzoyl Peroxide Gel",
                    "brand": "La Roche-Posay"
                },
                "duration_seconds": 20,
                "instructions": "Apply only to active breakouts",
                "frequency": "as_needed"
            },
            {
                "order": 5,
                "category": "moisturizer",
                "product": {
                    "name": "Oil-Free Moisturizer",
                    "brand": "Neutrogena"
                },
                "duration_seconds": 30,
                "instructions": "Use a light layer",
                "frequency": "daily"
            }
        ]
    },
    {
        "name": "Anti-Aging Power",
        "description": "Advanced routine targeting fine lines and firmness",
        "type": "evening",
        "target_concerns": ["fine_lines_wrinkles", "firmness", "dark_spots"],
        "suitable_for_skin_types": ["normal", "dry", "combination"],
        "difficulty_level": "advanced",
        "estimated_cost": "premium",
        "steps": [
            {
                "order": 1,
                "category": "cleanser",
                "product": {
                    "name": "Gentle Foaming Cleanser",
                    "brand": "Cetaphil"
                },
                "duration_seconds": 60,
                "instructions": "Remove all makeup and sunscreen",
                "frequency": "daily"
            },
            {
                "order": 2,
                "category": "exfoliant",
                "product": {
                    "name": "Glycolic Acid Toner",
                    "brand": "Pixi"
                },
                "duration_seconds": 30,
                "instructions": "Use 3x per week, build tolerance",
                "frequency": "weekly"
            },
            {
                "order": 3,
                "category": "serum",
                "product": {
                    "name": "Retinol 0.5% in Squalane",
                    "brand": "The Ordinary"
                },
                "duration_seconds": 30,
                "instructions": "Start 2x/week, increase gradually",
                "frequency": "daily"
            },
            {
                "order": 4,
                "category": "eye_cream",
                "product": {
                    "name": "Peptide Eye Cream",
                    "brand": "CeraVe"
                },
                "duration_seconds": 20,
                "instructions": "Pat gently around orbital bone",
                "frequency": "daily"
            },
            {
                "order": 5,
                "category": "moisturizer",
                "product": {
                    "name": "Anti-Aging Night Cream",
                    "brand": "Olay"
                },
                "duration_seconds": 30,
                "instructions": "Apply upward strokes",
                "frequency": "daily"
            },
            {
                "order": 6,
                "category": "face_oil",
                "product": {
                    "name": "Rosehip Seed Oil",
                    "brand": "The Ordinary"
                },
                "duration_seconds": 20,
                "instructions": "3-5 drops, press into skin",
                "frequency": "daily"
            }
        ]
    },
    {
        "name": "Sensitive Skin Basics",
        "description": "Gentle routine for reactive, sensitive skin",
        "type": "morning",
        "target_concerns": ["redness", "sensitivity"],
        "suitable_for_skin_types": ["sensitive", "dry"],
        "difficulty_level": "beginner",
        "estimated_cost": "budget",
        "steps": [
            {
                "order": 1,
                "category": "cleanser",
                "product": {
                    "name": "Gentle Cleanser",
                    "brand": "Vanicream"
                },
                "duration_seconds": 45,
                "instructions": "Use cool water, avoid rubbing",
                "frequency": "daily"
            },
            {
                "order": 2,
                "category": "serum",
                "product": {
                    "name": "Centella Asiatica Serum",
                    "brand": "PURITO"
                },
                "duration_seconds": 30,
                "instructions": "Pat gently, don't rub",
                "frequency": "daily"
            },
            {
                "order": 3,
                "category": "moisturizer",
                "product": {
                    "name": "Daily Moisturizing Lotion",
                    "brand": "CeraVe"
                },
                "duration_seconds": 30,
                "instructions": "Apply to damp skin",
                "frequency": "daily"
            },
            {
                "order": 4,
                "category": "sunscreen",
                "product": {
                    "name": "Mineral Sunscreen SPF 30",
                    "brand": "EltaMD"
                },
                "duration_seconds": 30,
                "instructions": "Physical sunscreen for sensitive skin",
                "frequency": "daily"
            }
        ]
    },
    {
        "name": "Brightening Glow",
        "description": "Routine for radiant skin and even tone",
        "type": "morning",
        "target_concerns": ["radiance", "dark_spots"],
        "suitable_for_skin_types": ["all"],
        "difficulty_level": "intermediate",
        "estimated_cost": "moderate",
        "steps": [
            {
                "order": 1,
                "category": "cleanser",
                "product": {
                    "name": "Vitamin C Cleanser",
                    "brand": "CeraVe"
                },
                "duration_seconds": 60,
                "instructions": "Massage for full minute",
                "frequency": "daily"
            },
            {
                "order": 2,
                "category": "toner",
                "product": {
                    "name": "Brightening Toner",
                    "brand": "Klairs"
                },
                "duration_seconds": 30,
                "instructions": "Layer if needed for extra hydration",
                "frequency": "daily"
            },
            {
                "order": 3,
                "category": "serum",
                "product": {
                    "name": "Vitamin C Serum 20%",
                    "brand": "Mad Hippie"
                },
                "duration_seconds": 30,
                "instructions": "Apply to clean, dry skin",
                "frequency": "daily"
            },
            {
                "order": 4,
                "category": "treatment",
                "product": {
                    "name": "Alpha Arbutin 2%",
                    "brand": "The Ordinary"
                },
                "duration_seconds": 20,
                "instructions": "Target dark spots directly",
                "frequency": "daily"
            },
            {
                "order": 5,
                "category": "moisturizer",
                "product": {
                    "name": "Brightening Moisturizer",
                    "brand": "Ole Henriksen"
                },
                "duration_seconds": 30,
                "instructions": "Don't forget neck and chest",
                "frequency": "daily"
            },
            {
                "order": 6,
                "category": "sunscreen",
                "product": {
                    "name": "Anthelios SPF 60",
                    "brand": "La Roche-Posay"
                },
                "duration_seconds": 30,
                "instructions": "High SPF to prevent dark spots",
                "frequency": "daily"
            }
        ]
    }
]


def get_template_insert_data():
    """Convert templates to database-ready format"""
    templates = []
    for template in ROUTINE_TEMPLATES:
        template_copy = template.copy()
        template_copy["created_at"] = datetime.utcnow()
        template_copy["popularity_score"] = 0.0
        templates.append(template_copy)
    return templates