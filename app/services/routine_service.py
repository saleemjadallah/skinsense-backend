import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo.database import Database
from app.utils.date_utils import get_utc_now

# Old routine models disabled - using new PersonalizedRoutine model
# from app.models.routine import RoutineModel, RoutineStep, RoutineProduct, EffectivenessScores, RoutineCompletion
from app.models.user import UserModel
from app.schemas.routine import RoutineGenerateRequest
from app.database import get_database

logger = logging.getLogger(__name__)


class RoutineService:
    """Service for managing skincare routines"""
    
    def __init__(self):
        self.db = None
        self.openai_service = None
        
        # Define routine recommendations based on skin concerns
        self.concern_to_steps = {
            "hydration": [
                {"category": "toner", "product": "Hydrating Toner", "reasoning": "Preps skin for better absorption"},
                {"category": "serum", "product": "Hyaluronic Acid Serum", "reasoning": "Draws moisture into skin"},
                {"category": "moisturizer", "product": "Rich Moisturizer", "reasoning": "Seals in hydration"},
            ],
            "acne": [
                {"category": "cleanser", "product": "Salicylic Acid Cleanser", "reasoning": "Unclogs pores"},
                {"category": "treatment", "product": "BHA Treatment", "reasoning": "Exfoliates and prevents breakouts"},
                {"category": "moisturizer", "product": "Oil-Free Moisturizer", "reasoning": "Hydrates without clogging"},
            ],
            "dark_spots": [
                {"category": "serum", "product": "Vitamin C Serum", "reasoning": "Brightens and fades spots", "time": "morning"},
                {"category": "treatment", "product": "Niacinamide Treatment", "reasoning": "Evens skin tone"},
                {"category": "sunscreen", "product": "SPF 50 Sunscreen", "reasoning": "Prevents further darkening", "time": "morning"},
            ],
            "fine_lines_wrinkles": [
                {"category": "serum", "product": "Retinol Serum", "reasoning": "Stimulates collagen", "time": "evening"},
                {"category": "eye_cream", "product": "Peptide Eye Cream", "reasoning": "Targets fine lines"},
                {"category": "moisturizer", "product": "Anti-Aging Moisturizer", "reasoning": "Firms and hydrates"},
            ],
            "redness": [
                {"category": "cleanser", "product": "Gentle Cream Cleanser", "reasoning": "Non-irritating formula"},
                {"category": "serum", "product": "Centella Asiatica Serum", "reasoning": "Calms inflammation"},
                {"category": "moisturizer", "product": "Ceramide Moisturizer", "reasoning": "Repairs barrier"},
            ],
            "dark_circles": [
                {"category": "eye_cream", "product": "Caffeine Eye Cream", "reasoning": "Reduces puffiness"},
                {"category": "serum", "product": "Vitamin K Serum", "reasoning": "Improves circulation"},
            ],
            "radiance": [
                {"category": "exfoliant", "product": "AHA Toner", "reasoning": "Removes dead skin", "frequency": "weekly"},
                {"category": "serum", "product": "Vitamin C Serum", "reasoning": "Brightens complexion"},
                {"category": "face_oil", "product": "Rosehip Oil", "reasoning": "Adds healthy glow"},
            ],
            "firmness": [
                {"category": "serum", "product": "Peptide Serum", "reasoning": "Boosts collagen"},
                {"category": "treatment", "product": "Retinol Treatment", "reasoning": "Improves elasticity", "time": "evening"},
                {"category": "moisturizer", "product": "Firming Moisturizer", "reasoning": "Tightens and lifts"},
            ],
            "smoothness": [
                {"category": "exfoliant", "product": "BHA/AHA Treatment", "reasoning": "Smooths texture", "frequency": "biweekly"},
                {"category": "serum", "product": "Glycolic Acid Serum", "reasoning": "Refines skin surface"},
            ],
        }
    
    def initialize(self):
        """Initialize database connection and services"""
        if self.db is None:
            self.db = get_database()
        if self.openai_service is None:
            from app.services.openai_service import OpenAIService
            self.openai_service = OpenAIService()
    
    def generate_ai_routine(
        self,
        user_id: str,
        request: RoutineGenerateRequest
    ) -> List[Dict[str, Any]]:
        """Generate AI-powered routine based on skin analysis and preferences"""
        self.initialize()
        
        try:
            # Get user's latest skin analysis
            analysis = self.db.skin_analyses.find_one(
                {"user_id": ObjectId(user_id)},
                sort=[("created_at", -1)]
            )
            
            if not analysis:
                raise ValueError("No skin analysis found for user")
            
            # Extract analysis data
            analysis_data = analysis.get("orbo_response", {})
            
            # Get user profile
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            user_profile = user.get("profile", {}) if user else {}
            
            # Try to use OpenAI for advanced routine generation
            try:
                routine_steps = self._generate_ai_routine_steps(
                    analysis_data,
                    request,
                    user_profile
                )
            except Exception as e:
                logger.warning(f"OpenAI routine generation failed, using fallback: {e}")
                # Fallback to basic generation if OpenAI fails
                routine_steps = self._generate_routine_steps(
                    analysis_data,
                    request.focus_areas or [],
                    request.routine_type,
                    user_profile
                )
            
            # Create routine model (using new field names)
            routine = RoutineModel(
                user_id=ObjectId(user_id),
                name=f"AI Generated {request.routine_type.title()} Routine",
                type=request.routine_type,
                created_from="ai_generated",
                target_concerns=request.focus_areas or [],
                steps=routine_steps,
                based_on_analysis_id=ObjectId(analysis["_id"])
            )
            
            # Calculate effectiveness scores
            routine.effectiveness_scores = self._calculate_effectiveness_scores(
                routine_steps,
                analysis_data
            )
            
            # Prepare document for insertion - exclude None _id
            routine_doc = routine.dict(by_alias=True)
            # Remove _id if it's None to let MongoDB generate it
            if routine_doc.get("_id") is None:
                routine_doc.pop("_id", None)
            
            # Save to database
            result = self.db.routines.insert_one(routine_doc)
            routine.id = result.inserted_id
            
            # Return with the generated ID
            routine_doc["_id"] = str(result.inserted_id)
            return [routine_doc]
            
        except Exception as e:
            logger.error(f"Error generating AI routine: {str(e)}")
            raise
    
    def _generate_ai_routine_steps(
        self,
        analysis_data: Dict[str, Any],
        request: RoutineGenerateRequest,
        user_profile: Dict[str, Any]
    ) -> List[RoutineStep]:
        """Generate routine steps using OpenAI for personalized recommendations"""
        
        # Build prompt for OpenAI
        prompt = f"""
        Create a personalized {request.routine_type} skincare routine based on the following skin analysis:
        
        SKIN METRICS (0-100 scale, higher is better):
        - Overall Skin Health: {analysis_data.get('overall_skin_health_score', 'N/A')}
        - Hydration: {analysis_data.get('hydration', 'N/A')}
        - Smoothness: {analysis_data.get('smoothness', 'N/A')}
        - Radiance: {analysis_data.get('radiance', 'N/A')}
        - Dark Spots: {analysis_data.get('dark_spots', 'N/A')}
        - Firmness: {analysis_data.get('firmness', 'N/A')}
        - Fine Lines & Wrinkles: {analysis_data.get('fine_lines_wrinkles', 'N/A')}
        - Acne: {analysis_data.get('acne', 'N/A')}
        - Dark Circles: {analysis_data.get('dark_circles', 'N/A')}
        - Redness: {analysis_data.get('redness', 'N/A')}
        
        USER PROFILE:
        - Age Group: {user_profile.get('age_group', 'Not specified')}
        - Skin Type: {user_profile.get('skin_type', 'Not specified')}
        - Gender: {user_profile.get('gender', 'Not specified')}
        
        PREFERENCES:
        - Time Available: {request.time_available or 'Not specified'} minutes
        - Budget: {request.budget_preference or 'moderate'}
        - Include Devices: {request.include_devices}
        
        Focus on scores below 80 as priority concerns. Create a routine with 4-7 steps.
        
        IMPORTANT: Return ONLY valid JSON in this exact format:
        {{
            "steps": [
                {{
                    "order": 1,
                    "category": "cleanser|toner|essence|serum|treatment|eye_cream|moisturizer|face_oil|sunscreen|mask|exfoliant|spot_treatment",
                    "product_name": "Specific product name",
                    "brand": "Recommended brand (optional)",
                    "duration_seconds": 30,
                    "instructions": "How to apply",
                    "ai_reasoning": "Why this product helps their specific concerns"
                }}
            ]
        }}
        """
        
        try:
            # Use OpenAI to generate routine
            response = self.openai_service.generate_completion(
                prompt=prompt,
                system_message="You are a skincare expert creating personalized routines. Always respond with valid JSON only.",
                temperature=0.7,
                max_tokens=800
            )
            
            # Clean response if wrapped in markdown
            if response.startswith("```json"):
                response = response.replace("```json", "").replace("```", "").strip()
            elif response.startswith("```"):
                response = response.replace("```", "").strip()
            
            # Parse JSON response
            routine_data = json.loads(response)
            
            # Convert to RoutineStep objects
            steps = []
            for step_data in routine_data.get("steps", []):
                product = RoutineProduct(
                    name=step_data.get("product_name", "Unknown Product"),
                    brand=step_data.get("brand")
                )
                
                step = RoutineStep(
                    order=step_data.get("order", len(steps) + 1),
                    category=step_data.get("category", "treatment"),
                    product=product,
                    duration_seconds=step_data.get("duration_seconds", 30),
                    instructions=step_data.get("instructions", "Apply as directed"),
                    ai_reasoning=step_data.get("ai_reasoning", "AI recommended for your skin needs")
                )
                steps.append(step)
            
            return steps
            
        except Exception as e:
            logger.error(f"Error generating AI routine steps: {e}")
            raise
    
    def _generate_routine_steps(
        self,
        analysis_data: Dict[str, Any],
        focus_areas: List[str],
        routine_type: str,
        user_profile: Dict[str, Any]
    ) -> List[RoutineStep]:
        """Generate routine steps based on skin analysis and focus areas"""
        steps = []
        step_order = 1
        
        # Start with basic cleansing for all routines
        if routine_type in ["morning", "evening"]:
            steps.append(RoutineStep(
                order=step_order,
                category="cleanser",
                product=RoutineProduct(name="Gentle Cleanser"),
                duration_seconds=60,
                instructions="Massage gently in circular motions, rinse with lukewarm water",
                ai_reasoning="Essential step to remove impurities and prepare skin"
            ))
            step_order += 1
        
        # Add targeted treatments based on focus areas
        for focus in focus_areas:
            if focus in self.concern_to_steps:
                concern_steps = self.concern_to_steps[focus]
                for step_data in concern_steps:
                    # Skip if time-specific and doesn't match routine type
                    if step_data.get("time") and step_data["time"] != routine_type:
                        continue
                    
                    steps.append(RoutineStep(
                        order=step_order,
                        category=step_data["category"],
                        product=RoutineProduct(name=step_data["product"]),
                        duration_seconds=step_data.get("duration", 30),
                        instructions=step_data.get("instructions", "Apply evenly to face"),
                        ai_reasoning=step_data["reasoning"]
                    ))
                    step_order += 1
        
        # Add moisturizer for all routines
        if routine_type != "weekly":
            steps.append(RoutineStep(
                order=step_order,
                category="moisturizer",
                product=RoutineProduct(name="Daily Moisturizer"),
                duration_seconds=45,
                instructions="Apply evenly to face and neck",
                ai_reasoning="Locks in hydration and active ingredients"
            ))
            step_order += 1
        
        # Add sunscreen for morning routines
        if routine_type == "morning":
            steps.append(RoutineStep(
                order=step_order,
                category="sunscreen",
                product=RoutineProduct(name="SPF 30+ Sunscreen"),
                duration_seconds=30,
                instructions="Apply generously 15 minutes before sun exposure",
                ai_reasoning="Critical protection against UV damage and premature aging"
            ))
        
        return steps
    
    def _calculate_effectiveness_scores(
        self,
        steps: List[RoutineStep],
        analysis_data: Dict[str, Any]
    ) -> EffectivenessScores:
        """Calculate predicted effectiveness scores for the routine"""
        # Simple scoring based on step categories and current scores
        current_scores = {
            "hydration": analysis_data.get("hydration", 50),
            "smoothness": analysis_data.get("smoothness", 50),
            "radiance": analysis_data.get("radiance", 50),
            "acne": analysis_data.get("acne", 50),
            "redness": analysis_data.get("redness", 50),
            "dark_spots": analysis_data.get("dark_spots", 50),
            "fine_lines_wrinkles": analysis_data.get("fine_lines_wrinkles", 50),
            "firmness": analysis_data.get("firmness", 50),
            "dark_circles": analysis_data.get("dark_circles", 50),
            "overall_skin_health_score": analysis_data.get("overall_skin_health_score", 50)
        }
        
        # Calculate improvements based on routine steps
        improvements = {}
        for parameter in current_scores:
            base_improvement = 2.0  # Base improvement from routine consistency
            
            # Add improvements based on specific steps
            for step in steps:
                if step.category == "serum" and "hydration" in parameter:
                    base_improvement += 5.0
                elif step.category == "treatment" and "acne" in parameter:
                    base_improvement += 7.0
                elif step.category == "moisturizer":
                    base_improvement += 3.0
                elif step.category == "sunscreen" and any(x in parameter for x in ["spots", "lines", "firmness"]):
                    base_improvement += 4.0
            
            # Calculate predicted score (cap at 95)
            predicted_score = min(95, current_scores[parameter] + base_improvement)
            improvements[parameter] = predicted_score
        
        return EffectivenessScores(**improvements)
    
    def create_routine(
        self,
        user_id: str,
        routine_data: Dict[str, Any]
    ) -> RoutineModel:
        """Create a new routine"""
        self.initialize()
        
        # Add default created_from if not provided
        if 'created_from' not in routine_data:
            routine_data['created_from'] = 'manual'
        # Minimal scheduling defaults
        if 'schedule_time' not in routine_data or routine_data.get('schedule_time') is None:
            if routine_data.get('type') == 'morning':
                routine_data['schedule_time'] = 'morning'
            elif routine_data.get('type') == 'evening':
                routine_data['schedule_time'] = 'evening'
        if 'schedule_days' not in routine_data or not routine_data.get('schedule_days'):
            routine_data['schedule_days'] = [1, 2, 3, 4, 5, 6, 7]
        
        # Calculate total duration
        total_duration = sum(
            step.get('duration_seconds', 30) 
            for step in routine_data.get('steps', [])
        ) // 60  # Convert to minutes
        
        routine_data['total_duration_minutes'] = total_duration
        
        # Create routine model (without ID)
        routine = RoutineModel(
            user_id=ObjectId(user_id),
            **routine_data
        )
        
        # Convert to dict for MongoDB insertion
        routine_dict = routine.dict(by_alias=True, exclude={'id'})
        
        # Remove _id if it's None to let MongoDB generate it
        if '_id' in routine_dict and routine_dict['_id'] is None:
            del routine_dict['_id']
        
        # Insert into database
        result = self.db.routines.insert_one(routine_dict)
        
        # Set the ID on the model
        routine.id = result.inserted_id
        
        return routine
    
    def get_user_routines(
        self,
        user_id: str,
        routine_type: Optional[str] = None,
        is_active: Optional[bool] = True
    ) -> List[RoutineModel]:
        """Get user's routines"""
        self.initialize()
        
        query = {"user_id": ObjectId(user_id)}
        if routine_type:
            query["type"] = routine_type
        if is_active is not None:
            query["is_active"] = is_active
        
        cursor = self.db.routines.find(query).sort("created_at", -1)
        routines = []
        
        for routine_doc in cursor:
            # Ensure _id is properly set
            if '_id' not in routine_doc and 'id' in routine_doc:
                routine_doc['_id'] = routine_doc['id']
            routine = RoutineModel(**routine_doc)
            routines.append(routine)
        
        return routines
    
    def complete_routine(
        self,
        user_id: str,
        routine_id: str,
        completion_data: Dict[str, Any]
    ) -> RoutineCompletion:
        """Mark a routine as completed"""
        self.initialize()
        
        completion = RoutineCompletion(
            user_id=ObjectId(user_id),
            routine_id=ObjectId(routine_id),
            **completion_data
        )
        
        # Convert to dict and remove null _id before insertion
        completion_dict = completion.dict(by_alias=True, exclude={'id'})
        if '_id' in completion_dict and completion_dict['_id'] is None:
            del completion_dict['_id']
        
        # Save completion
        result = self.db.routine_completions.insert_one(completion_dict)
        completion.id = result.inserted_id
        
        # Get the routine to check last completion
        routine = self.db.routines.find_one({"_id": ObjectId(routine_id)})
        current_streak = routine.get("completion_streak", 0)
        last_completed = routine.get("last_completed")
        
        # Calculate streak
        now = get_utc_now()
        if last_completed:
            days_since_last = (now - last_completed).days
            if days_since_last <= 1:
                # Consecutive day, increment streak
                new_streak = current_streak + 1
            else:
                # Streak broken, reset to 1
                new_streak = 1
        else:
            # First completion
            new_streak = 1
        
        # Update routine completion stats
        self.db.routines.update_one(
            {"_id": ObjectId(routine_id)},
            {
                "$inc": {"completion_count": 1},
                "$set": {
                    "last_completed": now,
                    "completion_streak": new_streak
                }
            }
        )
        
        return completion
    
    def get_routine_insights(
        self,
        routine_id: ObjectId,
        db: Database,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get insights about routine effectiveness"""
        
        since_date = get_utc_now() - timedelta(days=days)
        
        # Get completions
        completions = list(db.routine_completions.find({
            "routine_id": routine_id,
            "completed_at": {"$gte": since_date}
        }))
        
        if not completions:
            return {
                "adherence_rate": 0,
                "average_completion_time": 0,
                "most_skipped_steps": [],
                "mood_distribution": {},
                "skin_feel_distribution": {}
            }
        
        # Calculate metrics
        total_days = days
        completion_days = len(set(c["completed_at"].date() for c in completions))
        adherence_rate = (completion_days / total_days) * 100
        
        # Average completion time
        times = [c["duration_minutes"] for c in completions if c.get("duration_minutes")]
        avg_time = sum(times) / len(times) if times else 0
        
        # Most skipped steps
        skipped_counts = {}
        for c in completions:
            for step in c.get("skipped_steps", []):
                skipped_counts[step] = skipped_counts.get(step, 0) + 1
        
        most_skipped = sorted(skipped_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Mood and skin feel distribution
        mood_dist = {}
        skin_feel_dist = {}
        
        for c in completions:
            if c.get("mood"):
                mood_dist[c["mood"]] = mood_dist.get(c["mood"], 0) + 1
            if c.get("skin_feel"):
                skin_feel_dist[c["skin_feel"]] = skin_feel_dist.get(c["skin_feel"], 0) + 1
        
        return {
            "adherence_rate": round(adherence_rate, 1),
            "average_completion_time": round(avg_time, 1),
            "most_skipped_steps": [{"step_order": s[0], "skip_count": s[1]} for s in most_skipped],
            "mood_distribution": mood_dist,
            "skin_feel_distribution": skin_feel_dist,
            "total_completions": len(completions)
        }


# Global instance
routine_service = RoutineService()