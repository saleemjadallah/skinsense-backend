import openai
from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime
from bson import ObjectId

from app.core.config import settings
from app.models.routine import PersonalizedRoutine, RoutineStep


logger = logging.getLogger(__name__)

ROUTINE_GENERATION_SYSTEM_PROMPT = """
You are SkinSense AI's expert skincare routine architect. Your role is to create
personalized, scientifically-grounded skincare routines based on comprehensive user data.

Key Guidelines:
1. Base recommendations on actual skin analysis metrics (0-100 scale for each parameter)
2. Consider weather conditions (UV index, temperature, humidity)
3. Factor in user's lifestyle, budget, and experience level
4. Address specific skin concerns identified in analysis
5. Create realistic, achievable routines (morning: 5-8 min, evening: 8-12 min)
6. Prioritize products the user already owns when possible
7. Explain the "why" behind each step
8. Use encouraging, empowering language
9. Never make medical claims - focus on beauty and wellness
10. Adapt difficulty based on user's skincare experience level

Return responses in valid JSON format ONLY.
"""


class RoutineGeneratorService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_personalized_routine(
        self,
        user: Dict[str, Any],
        latest_analysis: Dict[str, Any],
        routine_type: str,  # "morning", "evening", "weekly_treatment"
        weather_data: Optional[Dict[str, Any]] = None,
        user_products: Optional[List[Dict[str, Any]]] = None,
        force_regenerate: bool = False,
    ) -> PersonalizedRoutine:
        """
        Generate a fully personalized routine using OpenAI API
        """

        try:
            # Build comprehensive context for AI
            context = self._build_generation_context(
                user, latest_analysis, routine_type, weather_data, user_products
            )

            # Generate routine using OpenAI
            routine_data = self._call_openai_api(context, routine_type)

            # Validate and structure the routine
            personalized_routine = self._structure_routine(
                routine_data, user, context, routine_type, latest_analysis
            )

            return personalized_routine

        except Exception as e:
            logger.error(f"Routine generation failed: {e}")
            # Return safe fallback routine
            return self._get_fallback_routine(user, routine_type)

    def _build_generation_context(
        self,
        user: Dict[str, Any],
        analysis: Dict[str, Any],
        routine_type: str,
        weather_data: Optional[Dict[str, Any]],
        user_products: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Build comprehensive context from all available data sources
        """

        # Extract skin metrics from latest analysis
        orbo_response = analysis.get("orbo_response", {})
        skin_metrics = {
            "overall_skin_health_score": orbo_response.get("overall_skin_health_score", 50),
            "hydration": orbo_response.get("hydration", 50),
            "smoothness": orbo_response.get("smoothness", 50),
            "radiance": orbo_response.get("radiance", 50),
            "dark_spots": orbo_response.get("dark_spots", 50),
            "firmness": orbo_response.get("firmness", 50),
            "fine_lines_wrinkles": orbo_response.get("fine_lines_wrinkles", 50),
            "acne": orbo_response.get("acne", 50),
            "dark_circles": orbo_response.get("dark_circles", 50),
            "redness": orbo_response.get("redness", 50),
        }

        # Identify primary concerns (scores below 60)
        primary_concerns = [k for k, v in skin_metrics.items() if v < 60 and k != "overall_skin_health_score"][:3]

        # User profile information
        profile = user.get("profile", {})
        user_profile = {
            "age_range": profile.get("age_range", "25-34"),
            "skin_type": profile.get("skin_type", "normal"),
            "skin_concerns": profile.get("skin_concerns", []),
            "goals": profile.get("goals", []),
            "experience_level": self._determine_experience_level(user),
        }

        # Skin analysis metrics
        skin_analysis = {
            **skin_metrics,
            "primary_concerns": primary_concerns,
            "analysis_date": analysis.get("created_at", datetime.utcnow()).isoformat() if isinstance(analysis.get("created_at"), datetime) else str(analysis.get("created_at", "")),
        }

        # Weather context (if available)
        weather_context = None
        if weather_data:
            weather_context = {
                "temperature_f": weather_data.get("temperature", 70),
                "uv_index": weather_data.get("uv_index", 3),
                "humidity_percent": weather_data.get("humidity", 50),
                "conditions": weather_data.get("conditions", "clear"),
                "season": self._get_season(),
                "recommendations": self._get_weather_based_recommendations(weather_data),
            }

        # User's product inventory
        product_inventory = []
        if user_products:
            for product in user_products[:10]:  # Limit to top 10
                product_inventory.append(
                    {
                        "name": product.get("name", "Unknown"),
                        "brand": product.get("brand", ""),
                        "category": product.get("category", ""),
                        "key_ingredients": product.get("key_ingredients", [])[:5],
                    }
                )

        return {
            "user_profile": user_profile,
            "skin_analysis": skin_analysis,
            "weather_context": weather_context,
            "product_inventory": product_inventory,
            "routine_type": routine_type,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _call_openai_api(
        self, context: Dict[str, Any], routine_type: str
    ) -> Dict[str, Any]:
        """
        Call OpenAI API to generate routine (synchronous)
        """

        user_prompt = self._build_user_prompt(context, routine_type)

        response = self.client.chat.completions.create(
            model="gpt-4o",  # or "gpt-4o-mini" for cost savings
            messages=[
                {"role": "system", "content": ROUTINE_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        routine_json = response.choices[0].message.content
        routine_data = json.loads(routine_json)

        return routine_data

    def _build_user_prompt(
        self, context: Dict[str, Any], routine_type: str
    ) -> str:
        """
        Build detailed prompt for OpenAI
        """

        skin_analysis = context["skin_analysis"]
        user_profile = context["user_profile"]
        weather = context.get("weather_context", {})
        products = context.get("product_inventory", [])

        prompt = f"""
Generate a personalized {routine_type} skincare routine based on the following data:

USER PROFILE:
- Age Range: {user_profile['age_range']}
- Skin Type: {user_profile['skin_type']}
- Experience Level: {user_profile['experience_level']}
- Primary Goals: {', '.join(user_profile['goals']) if user_profile['goals'] else 'General skincare'}
- Known Concerns: {', '.join(user_profile['skin_concerns']) if user_profile['skin_concerns'] else 'None specified'}

LATEST SKIN ANALYSIS (Scored 0-100, higher is better):
- Overall Health: {skin_analysis['overall_skin_health_score']}/100
- Hydration: {skin_analysis['hydration']}/100
- Smoothness: {skin_analysis['smoothness']}/100
- Radiance: {skin_analysis['radiance']}/100
- Dark Spots: {skin_analysis['dark_spots']}/100 (higher is better)
- Firmness: {skin_analysis['firmness']}/100
- Fine Lines & Wrinkles: {skin_analysis['fine_lines_wrinkles']}/100 (higher means fewer lines)
- Acne: {skin_analysis['acne']}/100 (higher is better - less acne)
- Dark Circles: {skin_analysis['dark_circles']}/100 (higher is better)
- Redness: {skin_analysis['redness']}/100 (higher is better - less redness)
- Top Concerns: {', '.join(skin_analysis['primary_concerns']) if skin_analysis['primary_concerns'] else 'None identified'}

"""

        if weather:
            prompt += f"""
CURRENT WEATHER CONDITIONS:
- Temperature: {weather['temperature_f']}°F
- UV Index: {weather['uv_index']} ({self._get_uv_severity(weather['uv_index'])})
- Humidity: {weather['humidity_percent']}%
- Conditions: {weather['conditions']}
- Season: {weather['season']}
- Weather Recommendations: {', '.join(weather['recommendations'])}

"""

        if products:
            prompt += f"""
USER'S PRODUCT INVENTORY (Top products):
"""
            for i, product in enumerate(products[:5], 1):
                prompt += f"{i}. {product['name']} by {product['brand']} ({product['category']})\n"
                if product['key_ingredients']:
                    prompt += f"   Key Ingredients: {', '.join(product['key_ingredients'])}\n"

        prompt += f"""

ROUTINE REQUIREMENTS:
- Type: {routine_type.upper()} routine
- Target Duration: {"5-8 minutes" if routine_type == "morning" else "8-12 minutes" if routine_type == "evening" else "15-20 minutes"}
- Steps: {"4-5 steps" if routine_type == "morning" else "5-7 steps" if routine_type == "evening" else "3-5 steps"}
- Difficulty: {user_profile['experience_level']}

RESPONSE FORMAT (JSON):
{{
  "routine_name": "descriptive name (e.g., 'Hydration Boost Morning')",
  "description": "1-2 sentence overview of routine purpose and benefits",
  "difficulty_level": "beginner|intermediate|advanced",
  "total_duration_minutes": <number>,
  "skin_concerns_addressed": ["concern1", "concern2"],
  "ai_reasoning": "Explain why you created this specific routine based on the data",
  "steps": [
    {{
      "step_number": 1,
      "product_category": "cleanser|toner|serum|moisturizer|sunscreen|treatment|mask",
      "product_name": "specific product name if from inventory, or generic category",
      "instructions": "Clear, actionable instructions (2-3 sentences)",
      "duration_minutes": <number>,
      "key_benefits": ["benefit1", "benefit2", "benefit3"],
      "technique_tips": "Pro tip for application or technique"
    }}
  ],
  "alternative_suggestions": [
    "suggestion 1 for different approach",
    "suggestion 2 for budget option"
  ],
  "confidence_score": <0.0-1.0>
}}

IMPORTANT:
1. Prioritize addressing the LOWEST scoring metrics from skin analysis
2. If UV index >3, MUST include SPF step for morning routines
3. If hydration <60, emphasize hydrating products
4. If smoothness <60, focus on gentle exfoliation and smoothing
5. Use products from user's inventory when suitable
6. Keep it simple for beginners, more advanced for experienced users
7. Be specific about application techniques
8. Focus on achievable, realistic routines
9. NEVER make medical claims - use beauty/wellness language only
10. Explain the science simply but accurately

Generate the routine now:
"""

        return prompt

    def _structure_routine(
        self,
        routine_data: Dict[str, Any],
        user: Dict[str, Any],
        context: Dict[str, Any],
        routine_type: str,
        latest_analysis: Dict[str, Any],
    ) -> PersonalizedRoutine:
        """
        Convert OpenAI response to PersonalizedRoutine model
        """

        steps = []
        for step_data in routine_data.get("steps", []):
            step = RoutineStep(
                step_number=step_data["step_number"],
                product_category=step_data["product_category"],
                product_name=step_data.get("product_name"),
                instructions=step_data["instructions"],
                duration_minutes=step_data["duration_minutes"],
                key_benefits=step_data.get("key_benefits", []),
                technique_tips=step_data.get("technique_tips"),
            )
            steps.append(step)

        # Convert ObjectIds to strings for Pydantic v2 compatibility
        user_id = user.get("_id")
        if isinstance(user_id, ObjectId):
            user_id = str(user_id)
        analysis_id = latest_analysis.get("_id")
        if isinstance(analysis_id, ObjectId):
            analysis_id = str(analysis_id)

        routine = PersonalizedRoutine(
            user_id=user_id,
            routine_type=routine_type,
            routine_name=routine_data["routine_name"],
            description=routine_data["description"],
            generated_from={
                "skin_analysis_id": str(analysis_id),
                "user_profile_snapshot": context["user_profile"],
                "weather_data": context.get("weather_context"),
                "generation_timestamp": context["timestamp"],
            },
            steps=steps,
            total_duration_minutes=routine_data["total_duration_minutes"],
            difficulty_level=routine_data["difficulty_level"],
            skin_concerns_addressed=routine_data.get("skin_concerns_addressed", []),
            weather_adapted=bool(context.get("weather_context")),
            current_weather_context=context.get("weather_context"),
            ai_reasoning=routine_data["ai_reasoning"],
            confidence_score=routine_data.get("confidence_score", 0.85),
            alternative_suggestions=routine_data.get("alternative_suggestions", []),
        )

        return routine

    def _determine_experience_level(self, user: Dict[str, Any]) -> str:
        """Determine user's skincare experience level"""
        # Simple heuristic - can be improved with user history
        profile = user.get("profile", {})
        routine_count = len(profile.get("current_routine", []))

        if routine_count <= 2:
            return "beginner"
        elif routine_count <= 5:
            return "intermediate"
        else:
            return "advanced"

    def _get_season(self) -> str:
        """Determine current season"""
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"

    def _get_weather_based_recommendations(
        self, weather_data: Dict[str, Any]
    ) -> List[str]:
        """Generate weather-specific recommendations"""
        recommendations = []

        uv = weather_data.get("uv_index", 0)
        if uv >= 6:
            recommendations.append("High UV - SPF 50+ essential")
        elif uv >= 3:
            recommendations.append("Moderate UV - Use SPF 30+")

        humidity = weather_data.get("humidity", 50)
        if humidity < 30:
            recommendations.append("Low humidity - Extra hydration needed")
        elif humidity > 70:
            recommendations.append("High humidity - Lightweight products preferred")

        temp = weather_data.get("temperature", 70)
        if temp < 40:
            recommendations.append("Cold weather - Barrier protection important")
        elif temp > 85:
            recommendations.append("Hot weather - Oil-free, breathable products")

        return recommendations

    def _get_uv_severity(self, uv_index: int) -> str:
        """Convert UV index to severity level"""
        if uv_index >= 8:
            return "Very High"
        elif uv_index >= 6:
            return "High"
        elif uv_index >= 3:
            return "Moderate"
        else:
            return "Low"

    def _get_fallback_routine(
        self, user: Dict[str, Any], routine_type: str
    ) -> PersonalizedRoutine:
        """Return safe fallback routine if AI generation fails"""
        # Convert user_id to string for Pydantic v2 compatibility
        user_id = user.get("_id")
        if isinstance(user_id, ObjectId):
            user_id = str(user_id)
        profile = user.get("profile", {})

        # Simple fallback routine based on routine type
        if routine_type == "morning":
            steps = [
                RoutineStep(
                    step_number=1,
                    product_category="cleanser",
                    product_name="Gentle Cleanser",
                    instructions="Wet face with lukewarm water. Massage cleanser in circular motions for 30 seconds. Rinse thoroughly.",
                    duration_minutes=2,
                    key_benefits=["Removes overnight oils", "Prepares skin", "Gentle cleansing"],
                    technique_tips="Use gentle circular motions, avoid hot water",
                ),
                RoutineStep(
                    step_number=2,
                    product_category="moisturizer",
                    product_name="Daily Moisturizer",
                    instructions="Apply a nickel-sized amount to damp skin. Gently pat and press into skin.",
                    duration_minutes=2,
                    key_benefits=["Hydrates skin", "Locks in moisture", "Creates barrier"],
                    technique_tips="Apply to slightly damp skin for better absorption",
                ),
                RoutineStep(
                    step_number=3,
                    product_category="sunscreen",
                    product_name="SPF 30+ Sunscreen",
                    instructions="Apply generously to all exposed areas. Reapply every 2 hours if outdoors.",
                    duration_minutes=2,
                    key_benefits=["UV protection", "Prevents aging", "Protects skin barrier"],
                    technique_tips="Don't forget neck and ears",
                ),
            ]
            routine_name = "Essential Morning Routine"
            description = "A simple, effective morning routine to cleanse, hydrate, and protect your skin."
        else:
            steps = [
                RoutineStep(
                    step_number=1,
                    product_category="cleanser",
                    product_name="Gentle Cleanser",
                    instructions="Remove makeup if worn. Massage cleanser for 60 seconds, focusing on oily areas.",
                    duration_minutes=3,
                    key_benefits=["Deep cleansing", "Removes impurities", "Refreshes skin"],
                    technique_tips="Double cleanse if you wore sunscreen or makeup",
                ),
                RoutineStep(
                    step_number=2,
                    product_category="serum",
                    product_name="Hydrating Serum",
                    instructions="Apply 2-3 drops to clean skin. Gently press into skin.",
                    duration_minutes=2,
                    key_benefits=["Deep hydration", "Targets concerns", "Prepares for moisturizer"],
                    technique_tips="Pat gently rather than rubbing",
                ),
                RoutineStep(
                    step_number=3,
                    product_category="moisturizer",
                    product_name="Night Cream",
                    instructions="Apply moisturizer while serum is still slightly damp. Use upward strokes.",
                    duration_minutes=2,
                    key_benefits=["Overnight hydration", "Skin repair", "Locks in treatment"],
                    technique_tips="Use upward and outward motions",
                ),
            ]
            routine_name = "Essential Evening Routine"
            description = "A calming evening routine to cleanse, treat, and nourish your skin overnight."

        return PersonalizedRoutine(
            user_id=user_id,
            routine_type=routine_type,
            routine_name=routine_name,
            description=description,
            generated_from={
                "fallback": True,
                "reason": "AI generation unavailable",
                "timestamp": datetime.utcnow().isoformat(),
            },
            steps=steps,
            total_duration_minutes=sum(s.duration_minutes for s in steps),
            difficulty_level="beginner",
            skin_concerns_addressed=profile.get("skin_concerns", [])[:2],
            weather_adapted=False,
            ai_reasoning="This is a basic routine designed to work for most skin types. For personalized recommendations, please ensure your skin analysis is up to date.",
            confidence_score=0.7,
            alternative_suggestions=[
                "Consider adding a toner after cleansing for better product absorption",
                "Add a targeted treatment serum based on your specific concerns",
            ],
        )


# Global instance
routine_generator_service = RoutineGeneratorService()