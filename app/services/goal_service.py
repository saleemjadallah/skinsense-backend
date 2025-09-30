from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import json
from collections import defaultdict

from ..models.goal import GoalModel, Milestone, GoalProgress, Achievement, GoalTemplate
from ..models.user import UserModel
from ..models.skin_analysis import SkinAnalysisModel
# from ..models.routine import RoutineModel  # Disabled - old routine model
from ..schemas.goal import (
    GoalCreate, GoalUpdate, GoalProgressUpdate,
    GoalResponse, GoalListResponse, GoalProgressResponse,
    GoalInsight, AchievementResponse, GoalTemplateResponse,
    GoalGenerateRequest, MilestoneResponse
)
from ..database import get_database
from .openai_service import OpenAIService
# from .routine_service import RoutineService # Disabled - old routine service

logger = logging.getLogger(__name__)


class GoalService:
    """Service for managing user goals and achievements"""
    
    def __init__(self):
        self.db = get_database()  # Initialize database immediately
        self.openai_service = OpenAIService()
        self._routine_service = None
        
        # Define our 10 skin parameters with scoring thresholds
        self.skin_parameters = {
            "overall_skin_health_score": {"display_name": "Overall Skin Health", "category": "general"},
            "hydration": {"display_name": "Hydration", "category": "hydration"},
            "smoothness": {"display_name": "Smoothness", "category": "texture"},
            "radiance": {"display_name": "Radiance", "category": "brightness"},
            "dark_spots": {"display_name": "Dark Spots", "category": "pigmentation"},
            "firmness": {"display_name": "Firmness", "category": "aging"},
            "fine_lines_wrinkles": {"display_name": "Fine Lines & Wrinkles", "category": "aging"},
            "acne": {"display_name": "Acne", "category": "acne"},
            "dark_circles": {"display_name": "Dark Circles", "category": "undereye"},
            "redness": {"display_name": "Redness", "category": "sensitivity"}
        }
        
        # Achievement definitions
        self.achievement_definitions = [
            # Journey Milestones
            {
                "achievement_id": "first_glow",
                "title": "First Glow",
                "description": "Complete your first skin analysis",
                "icon": "sparkles",
                "category": "special",
                "tier": "bronze",
                "points": 50,
                "criteria": {"analyses_completed": 1}
            },
            {
                "achievement_id": "baseline_boss",
                "title": "Baseline Boss",
                "description": "Set your baseline and first goal",
                "icon": "flag",
                "category": "goal",
                "tier": "bronze",
                "points": 75,
                "criteria": {"baseline_set": True, "first_goal": True}
            },
            {
                "achievement_id": "progress_pioneer",
                "title": "Progress Pioneer",
                "description": "Upload 10 progress photos",
                "icon": "camera",
                "category": "special",
                "tier": "silver",
                "points": 100,
                "criteria": {"progress_photos": 10}
            },
            
            # Consistency Achievements
            {
                "achievement_id": "week_warrior",
                "title": "Week Warrior",
                "description": "7-day streak of daily check-ins",
                "icon": "fire",
                "category": "streak",
                "tier": "bronze",
                "points": 100,
                "criteria": {"check_in_streak": 7}
            },
            {
                "achievement_id": "consistency_queen_king",
                "title": "Consistency Queen/King",
                "description": "30-day streak maintained",
                "icon": "crown",
                "category": "streak",
                "tier": "gold",
                "points": 300,
                "criteria": {"check_in_streak": 30}
            },
            {
                "achievement_id": "hydration_hero",
                "title": "Hydration Hero",
                "description": "Maintain optimal hydration score for 2 weeks",
                "icon": "droplet",
                "category": "parameter",
                "tier": "silver",
                "points": 150,
                "criteria": {"parameter": "hydration", "min_score": 85, "duration_days": 14}
            },
            
            # Improvement Achievements
            {
                "achievement_id": "steady_improver",
                "title": "Steady Improver",
                "description": "Show improvement for 4 weeks straight",
                "icon": "trending_up",
                "category": "parameter",
                "tier": "silver",
                "points": 200,
                "criteria": {"improvement_weeks": 4}
            },
            {
                "achievement_id": "glow_up",
                "title": "Glow Up",
                "description": "Achieve 10+ point improvement in skin score",
                "icon": "star",
                "category": "parameter",
                "tier": "gold",
                "points": 250,
                "criteria": {"overall_improvement": 10}
            },
            
            # Learning & Routine
            {
                "achievement_id": "routine_revolutionary",
                "title": "Routine Revolutionary",
                "description": "Build your first complete AM/PM routine",
                "icon": "clock",
                "category": "routine",
                "tier": "bronze",
                "points": 100,
                "criteria": {"complete_routine": True}
            },
            {
                "achievement_id": "ingredient_inspector",
                "title": "Ingredient Inspector",
                "description": "Learn about 25 different ingredients",
                "icon": "science",
                "category": "special",
                "tier": "silver",
                "points": 150,
                "criteria": {"ingredients_learned": 25}
            },
            
            # Community Engagement
            {
                "achievement_id": "helpful_heart",
                "title": "Helpful Heart",
                "description": "Receive 50 likes on your posts/reviews",
                "icon": "heart",
                "category": "special",
                "tier": "silver",
                "points": 150,
                "criteria": {"likes_received": 50}
            },
            {
                "achievement_id": "knowledge_sharer",
                "title": "Knowledge Sharer",
                "description": "Create 10 helpful posts or tips",
                "icon": "lightbulb",
                "category": "special",
                "tier": "bronze",
                "points": 100,
                "criteria": {"posts_created": 10}
            },
            
            # Additional existing achievement
            {
                "achievement_id": "first_goal_completed",
                "title": "Goal Getter",
                "description": "Complete your first goal",
                "icon": "trophy",
                "category": "goal",
                "tier": "bronze",
                "points": 100,
                "criteria": {"goals_completed": 1}
            }
        ]
    
    def initialize(self):
        """Initialize database connection"""
        if self.db is None:
            self.db = get_database()
    
    @property
    def routine_service(self):
        """Lazy loading of routine service to avoid circular imports"""
        if self._routine_service is None:
            from .routine_service import RoutineService
            self._routine_service = RoutineService()
        return self._routine_service
    
    def generate_goals(
        self,
        user_id: str,
        request: GoalGenerateRequest
    ) -> List[GoalResponse]:
        """Generate AI-powered goals based on skin analysis"""
        logger.info(f"=== Starting goal generation for user {user_id} ===")
        logger.info(f"Request params: analysis_id={request.analysis_id}, goal_count={request.goal_count}")
        logger.info(f"Focus areas: {request.focus_areas}, difficulty: {request.difficulty_preference}")
        
        self.initialize()
        
        try:
            # Always convert user_id to ObjectId for consistency
            try:
                user_oid = ObjectId(user_id)
                logger.info(f"Successfully converted user_id to ObjectId: {user_oid}")
            except:
                # If it fails, user_id might already be an ObjectId or invalid
                logger.error(f"Could not convert user_id '{user_id}' to ObjectId")
                raise ValueError(f"Invalid user_id format: {user_id}")
            
            # Get user's latest skin analysis
            logger.info("Searching for skin analysis...")
            if request.analysis_id:
                # Use ObjectId format for user_id
                analysis = self.db.skin_analyses.find_one({
                    "_id": ObjectId(request.analysis_id),
                    "user_id": user_oid
                })
            else:
                # Get most recent analysis - use ObjectId format
                analysis = self.db.skin_analyses.find_one(
                    {"user_id": user_oid},
                    sort=[("created_at", -1)]
                )
            
            if not analysis:
                # Log for debugging
                logger.error(f"No skin analysis found for user {user_id}")
                
                # Check what's actually in the database for debugging
                count_oid = self.db.skin_analyses.count_documents({"user_id": user_oid})
                logger.error(f"Debug: Found {count_oid} analyses with ObjectId({user_id})")
                
                # Check total count in database
                total_count = self.db.skin_analyses.count_documents({})
                logger.error(f"Total skin analyses in database: {total_count}")
                
                raise ValueError("No skin analysis found for user. Please complete a skin analysis first.")
            
            logger.info(f"Found skin analysis: {analysis.get('_id')}")
            
            # Extract scores and identify areas needing improvement
            analysis_data = analysis.get("orbo_response", {})
            logger.info(f"Analysis data keys: {list(analysis_data.keys())}")
            
            problem_areas = self._identify_problem_areas(analysis_data)
            logger.info(f"Identified {len(problem_areas)} problem areas: {problem_areas[:3]}")
            
            # Get user preferences - try both formats
            logger.info("Fetching user profile...")
            user = self.db.users.find_one({
                "$or": [
                    {"_id": user_oid},  # ObjectId format
                    {"_id": user_id}     # String format
                ]
            })
            
            user_profile = user.get("profile", {}) if user else {}
            logger.info(f"User profile: age_group={user_profile.get('age_group')}, skin_type={user_profile.get('skin_type')}, gender={user_profile.get('gender')}")
            
            # Generate goals using AI
            logger.info("Calling OpenAI to generate goals...")
            goals = self._generate_ai_goals(
                problem_areas,
                user_profile,
                request.goal_count,
                request.focus_areas,
                request.difficulty_preference,
                request.exclude_types
            )
            logger.info(f"OpenAI returned {len(goals)} goals")
            
            # Create goals in database
            logger.info("Creating goals in database...")
            created_goals = []
            for i, goal_data in enumerate(goals):
                logger.info(f"Creating goal {i+1}: {goal_data.title}")
                try:
                    goal = self.create_goal(user_id, goal_data)
                    created_goals.append(goal)
                    logger.info(f"✓ Successfully created goal {i+1}")
                except Exception as e:
                    logger.error(f"❌ Failed to create goal {i+1}: {str(e)}")
                    # Continue with other goals even if one fails
                    continue
            
            logger.info(f"=== Goal generation complete. Created {len(created_goals)} goals ===")
            
            # If no goals were created successfully, raise an error
            if not created_goals:
                logger.error("No goals were successfully created!")
                raise Exception("Failed to create any goals in database")
            
            return created_goals
            
        except Exception as e:
            logger.error(f"Error generating goals: {str(e)}")
            raise
    
    def _identify_problem_areas(
        self,
        analysis_data: Dict[str, Any]
    ) -> List[Tuple[str, float, str]]:
        """Identify skin parameters that need improvement (scores < 80)"""
        problem_areas = []
        
        # Handle different ORBO response structures
        metrics = {}
        
        # Structure 1: data.output_score array (actual ORBO format)
        if 'data' in analysis_data and 'output_score' in analysis_data['data']:
            logger.info("Found ORBO format: data.output_score array")
            # Convert array to dict for easier access
            for item in analysis_data['data']['output_score']:
                concern = item.get('concern', '')
                score = item.get('score', 0)
                
                # Map ORBO concern names to our parameter names
                concern_mapping = {
                    'skin_health': 'overall_skin_health_score',
                    'hydration': 'hydration',
                    'acne': 'acne',
                    'smoothness': 'smoothness',
                    'radiance': 'radiance',
                    'dark_spots': 'dark_spots',
                    'firmness': 'firmness',
                    'fine_lines': 'fine_lines_wrinkles',
                    'wrinkles': 'fine_lines_wrinkles',
                    'dark_circles': 'dark_circles',
                    'redness': 'redness'
                }
                
                if concern in concern_mapping:
                    metrics[concern_mapping[concern]] = score
        
        # Structure 2: metrics nested object
        elif 'metrics' in analysis_data:
            logger.info("Found metrics nested structure")
            metrics = analysis_data['metrics']
        
        # Structure 3: flat structure with direct parameter names
        else:
            logger.info("Found flat structure")
            metrics = analysis_data
        
        logger.info(f"Parsed metrics: {metrics}")
        
        # Now check each parameter
        for param, info in self.skin_parameters.items():
            score = metrics.get(param, 0)
            if score < 80:  # Target threshold
                problem_areas.append((param, score, info["category"]))
        
        # If no problem areas found with our parameters, but we have some scores
        # Create generic problem areas based on what we found
        if not problem_areas and metrics:
            logger.info("No standard problem areas found, creating generic ones from available metrics")
            for param, score in metrics.items():
                if score < 80:
                    # Try to map to our categories
                    category = "general"
                    for our_param, our_info in self.skin_parameters.items():
                        if param in our_param or our_param in param:
                            category = our_info["category"]
                            break
                    problem_areas.append((param, score, category))
        
        # Sort by score (worst first)
        problem_areas.sort(key=lambda x: x[1])
        logger.info(f"Final problem areas: {problem_areas}")
        return problem_areas
    
    def _generate_ai_goals(
        self,
        problem_areas: List[Tuple[str, float, str]],
        user_profile: Dict[str, Any],
        goal_count: int,
        focus_areas: Optional[List[str]],
        difficulty_preference: Optional[str],
        exclude_types: Optional[List[str]]
    ) -> List[GoalCreate]:
        """Generate goals using OpenAI based on problem areas"""
        logger.info("=== _generate_ai_goals started ===")
        logger.info(f"Goal count requested: {goal_count}")
        logger.info(f"Focus areas: {focus_areas}")
        logger.info(f"Difficulty: {difficulty_preference}")
        
        # Prepare context for AI
        context = {
            "problem_areas": [
                {
                    "parameter": self.skin_parameters[area[0]]["display_name"],
                    "current_score": area[1],
                    "category": area[2]
                }
                for area in problem_areas
            ],
            "user_profile": {
                "age_group": user_profile.get("age_group", "unknown"),
                "skin_type": user_profile.get("skin_type", "unknown"),
                "gender": user_profile.get("gender", "unknown")
            },
            "preferences": {
                "goal_count": goal_count,
                "focus_areas": focus_areas or [],
                "difficulty": difficulty_preference or "moderate",
                "exclude_types": exclude_types or []
            }
        }
        
        prompt = f"""
        Based on the following skin analysis results and user profile, generate {goal_count} personalized goals.
        
        Problem Areas (scores below 80):
        {json.dumps(context['problem_areas'], indent=2)}
        
        User Profile:
        {json.dumps(context['user_profile'], indent=2)}
        
        Requirements:
        1. Create realistic, achievable goals
        2. Mix different goal types (parameter improvement, routine adherence, holistic)
        3. Consider the user's age group and skin type
        4. Set appropriate timelines (14-90 days based on goal type)
        5. Include specific, measurable targets
        6. Prioritize the worst-scoring parameters
        {f"7. Focus on these areas: {', '.join(focus_areas)}" if focus_areas else ""}
        {f"8. Difficulty preference: {difficulty_preference}" if difficulty_preference else ""}
        {f"9. Exclude these goal types: {', '.join(exclude_types)}" if exclude_types else ""}
        
        Return a JSON object with a "goals" array:
        {{
            "goals": [
                {{
                    "title": "Clear, motivating goal title",
                    "description": "Detailed description of what to achieve",
                    "type": "parameter_improvement|routine_adherence|holistic",
                    "target_parameter": "parameter_name or null",
                    "target_value": 85,
                    "improvement_target": 10,
                    "duration_days": 30,
                    "difficulty_level": "easy|moderate|challenging",
                    "category": "category_name",
                    "generation_reason": "Why this goal was suggested"
                }}
            ]
        }}
        """
        
        # Get AI response with JSON format
        logger.info("Calling OpenAI API...")
        logger.info(f"Prompt length: {len(prompt)} characters")
        
        try:
            ai_response = self.openai_service.generate_completion(
                prompt,
                system_message="You are a skincare expert creating personalized goals. Always respond with valid JSON.",
                response_format={"type": "json_object"}
            )
            logger.info(f"OpenAI API responded successfully. Response length: {len(ai_response)} characters")
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            logger.error(f"Falling back to template-based goals")
            return self._generate_template_goals(problem_areas, goal_count, focus_areas)
        
        try:
            response_json = json.loads(ai_response)
            logger.info(f"Successfully parsed JSON response")
            
            # Extract goals array from response
            if isinstance(response_json, dict) and "goals" in response_json:
                goals_data = response_json["goals"]
            elif isinstance(response_json, list):
                goals_data = response_json
            else:
                # Try to extract any list from the response
                goals_data = []
                for value in response_json.values():
                    if isinstance(value, list):
                        goals_data = value
                        break
            
            # Convert to GoalCreate objects
            goals = []
            for goal_data in goals_data[:goal_count]:
                try:
                    # Map parameter names correctly
                    if goal_data.get("target_parameter"):
                        # Find the correct parameter key
                        for param_key, param_info in self.skin_parameters.items():
                            if (
                                param_info["display_name"].lower()
                                == goal_data["target_parameter"].lower()
                            ):
                                goal_data["target_parameter"] = param_key
                                break

                    # Ensure target_value is set - use a default if not provided
                    target_value = goal_data.get("target_value")
                    if target_value is None or target_value <= 0:
                        # Default target values based on goal type
                        if goal_data["type"] == "parameter_improvement":
                            # For parameter improvement, aim for 85 or current + improvement
                            improvement = goal_data.get("improvement_target", 10)
                            # Find current score if we have it
                            current_score = 70  # Default baseline
                            for param, score, _ in problem_areas:
                                if param == goal_data.get("target_parameter"):
                                    current_score = score
                                    break
                            target_value = min(current_score + improvement, 95)
                        elif goal_data["type"] == "routine_adherence":
                            target_value = 85  # 85% adherence rate
                        else:
                            target_value = 80  # Generic default

                    # Also validate type field
                    valid_types = [
                        "parameter_improvement",
                        "routine_adherence",
                        "holistic",
                        "custom",
                    ]
                    goal_type = goal_data.get("type", "parameter_improvement")
                    if goal_type not in valid_types:
                        # Try to fix common mistakes
                        lower_type = goal_type.lower()
                        if "parameter" in lower_type or "improvement" in lower_type:
                            goal_type = "parameter_improvement"
                        elif "routine" in lower_type:
                            goal_type = "routine_adherence"
                        elif "holistic" in lower_type:
                            goal_type = "holistic"
                        else:
                            goal_type = "custom"

                    goal = GoalCreate(
                        title=goal_data["title"],
                        description=goal_data["description"],
                        type=goal_type,
                        target_parameter=goal_data.get("target_parameter"),
                        target_value=target_value,
                        improvement_target=goal_data.get("improvement_target"),
                        duration_days=goal_data.get("duration_days", 30),  # Default 30 days if not provided
                        difficulty_level=goal_data.get("difficulty_level", "moderate"),
                        category=goal_data.get("category"),
                    )
                    goals.append(goal)
                except Exception as e:
                    logger.error(
                        f"Error creating goal from data {goal_data}: {str(e)}"
                    )
                    # Skip this goal and continue with others
                    continue
            
            # If we didn't get enough goals, supplement with template goals
            if len(goals) < goal_count:
                logger.warning(f"Only got {len(goals)} goals from AI, needed {goal_count}. Supplementing with templates.")
                template_goals = self._generate_template_goals(problem_areas, goal_count - len(goals), focus_areas)
                goals.extend(template_goals)
            
            return goals
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI response: {ai_response}")
            # Fallback to template-based goals
            return self._generate_template_goals(problem_areas, goal_count, focus_areas)
        except Exception as e:
            logger.error(f"Unexpected error parsing AI response: {str(e)}")
            # Fallback to template-based goals
            return self._generate_template_goals(problem_areas, goal_count, focus_areas)
    
    def _generate_template_goals(
        self,
        problem_areas: List[Tuple[str, float, str]],
        goal_count: int,
        focus_areas: Optional[List[str]] = None
    ) -> List[GoalCreate]:
        """Fallback template-based goal generation"""
        goals = []
        
        # If focus areas are provided, prioritize them
        if focus_areas:
            # Reorder problem_areas to prioritize focus areas
            prioritized_areas = []
            remaining_areas = []
            
            for area in problem_areas:
                param_name = area[0]
                if param_name in focus_areas:
                    prioritized_areas.append(area)
                else:
                    remaining_areas.append(area)
            
            # Combine with focus areas first
            problem_areas = prioritized_areas + remaining_areas
        
        # Pre-defined goal templates for each parameter
        templates = {
            "hydration": {
                "title": "Hydration Boost Challenge",
                "description": "Increase your skin's hydration level through consistent care",
                "duration_days": 30,
                "improvement_target": 15
            },
            "smoothness": {
                "title": "Smooth Skin Journey",
                "description": "Improve skin texture and achieve smoother complexion",
                "duration_days": 45,
                "improvement_target": 12
            },
            "radiance": {
                "title": "Glow Up Goal",
                "description": "Enhance your skin's natural radiance and brightness",
                "duration_days": 30,
                "improvement_target": 10
            },
            "acne": {
                "title": "Clear Skin Mission",
                "description": "Reduce acne and achieve clearer, healthier skin",
                "duration_days": 60,
                "improvement_target": 20
            },
            "dark_spots": {
                "title": "Even Tone Target",
                "description": "Reduce dark spots and achieve more even skin tone",
                "duration_days": 90,
                "improvement_target": 15
            },
            "fine_lines_wrinkles": {
                "title": "Anti-Aging Focus",
                "description": "Minimize fine lines and improve skin firmness",
                "duration_days": 60,
                "improvement_target": 10
            },
            "redness": {
                "title": "Calm & Soothe",
                "description": "Reduce redness and sensitivity for calmer skin",
                "duration_days": 30,
                "improvement_target": 15
            },
            "dark_circles": {
                "title": "Bright Eyes Goal",
                "description": "Reduce under-eye darkness and puffiness",
                "duration_days": 45,
                "improvement_target": 12
            },
            "firmness": {
                "title": "Firm & Lift",
                "description": "Improve skin elasticity and firmness",
                "duration_days": 60,
                "improvement_target": 10
            }
        }
        
        # Generate goals for worst-scoring parameters
        for i, (param, score, category) in enumerate(problem_areas[:goal_count]):
            if param in templates:
                template = templates[param]
                goal = GoalCreate(
                    title=template["title"],
                    description=template["description"],
                    type="parameter_improvement",
                    target_parameter=param,
                    target_value=min(score + template["improvement_target"], 95),
                    improvement_target=template["improvement_target"],
                    duration_days=template["duration_days"],
                    difficulty_level="moderate" if template["improvement_target"] <= 15 else "challenging",
                    category=category
                )
                goals.append(goal)
        
        # Add a routine adherence goal if needed
        if len(goals) < goal_count:
            goals.append(GoalCreate(
                title="Routine Consistency Master",
                description="Complete your skincare routine consistently for better results",
                type="routine_adherence",
                target_value=85,  # 85% completion rate
                duration_days=30,
                difficulty_level="moderate",
                category="routine"
            ))
        
        return goals[:goal_count]
    
    def create_goal(
        self,
        user_id: str,
        goal_data: GoalCreate
    ) -> GoalResponse:
        """Create a new goal for a user"""
        logger.info(f"=== Creating goal for user {user_id} ===")
        logger.info(f"Goal title: {goal_data.title}")
        logger.info(f"Goal type: {goal_data.type}")
        
        self.initialize()
        
        try:
            # Always convert user_id to ObjectId for consistency
            try:
                user_oid = ObjectId(user_id)
            except:
                logger.error(f"Could not convert user_id '{user_id}' to ObjectId")
                raise ValueError(f"Invalid user_id format: {user_id}")
            
            # Get baseline value if parameter goal
            baseline_value = 0.0
            if goal_data.type == "parameter_improvement" and goal_data.target_parameter:
                # Get latest analysis - use ObjectId
                analysis = self.db.skin_analyses.find_one(
                    {"user_id": user_oid},
                    sort=[("created_at", -1)]
                )
                    
                if analysis:
                    baseline_value = analysis.get("orbo_response", {}).get(
                        goal_data.target_parameter, 0.0
                    )
            
            # Calculate target date
            target_date = datetime.utcnow() + timedelta(days=goal_data.duration_days)
            
            # Create milestones
            milestones = self._create_milestones(
                goal_data.type,
                goal_data.duration_days,
                baseline_value,
                goal_data.target_value,
                goal_data.custom_milestones
            )
            
            # Determine reward points based on difficulty
            reward_points = {
                "easy": 50,
                "moderate": 100,
                "challenging": 200
            }.get(goal_data.difficulty_level, 100)
            
            # Create goal model - always use ObjectId for consistency
            goal = GoalModel(
                user_id=user_oid,
                title=goal_data.title,
                description=goal_data.description,
                type=goal_data.type,
                category=goal_data.category,
                target_parameter=goal_data.target_parameter,
                baseline_value=baseline_value,
                target_value=goal_data.target_value,
                current_value=baseline_value,
                improvement_target=goal_data.improvement_target,
                target_date=target_date,
                duration_days=goal_data.duration_days,
                milestones=milestones,
                difficulty_level=goal_data.difficulty_level,
                reward_points=reward_points,
                linked_routine_id=ObjectId(goal_data.linked_routine_id) if goal_data.linked_routine_id else None,
                ai_generated=hasattr(goal_data, 'generation_reason'),
                generation_reason=getattr(goal_data, 'generation_reason', None)
            )
            
            # Save to database (exclude None _id to let MongoDB generate it)
            goal_dict = goal.dict(by_alias=True)
            if goal_dict.get('_id') is None:
                goal_dict.pop('_id', None)
            
            # IMPORTANT: Keep user_id as ObjectId for database consistency
            # The dict() method converts ObjectId to string, so we need to convert it back
            goal_dict['user_id'] = user_oid
            
            logger.info(f"Saving goal to database...")
            logger.info(f"Goal dict keys: {list(goal_dict.keys())}")
            logger.info(f"User ID in goal: {goal_dict.get('user_id')} (type: {type(goal_dict.get('user_id')).__name__})")
            
            try:
                result = self.db.goals.insert_one(goal_dict)
                goal.id = result.inserted_id
                logger.info(f"✓ Goal saved successfully with ID: {result.inserted_id}")
                
                # Verify the goal was saved correctly
                saved_goal = self.db.goals.find_one({"_id": result.inserted_id})
                if saved_goal:
                    logger.info(f"✓ Verification: Goal found in DB with user_id: {saved_goal.get('user_id')} (type: {type(saved_goal.get('user_id')).__name__})")
                else:
                    logger.error(f"❌ Verification failed: Goal not found after saving!")
                    
            except Exception as db_error:
                logger.error(f"❌ Database save failed: {str(db_error)}")
                logger.error(f"Goal dict: {json.dumps(str(goal_dict)[:500])}")
                raise
            
            # Create AI-powered routine if requested
            if goal_data.linked_routine_id is None and goal_data.type == "parameter_improvement":
                routine = self._create_linked_routine(user_id, goal)
                if routine:
                    self.db.goals.update_one(
                        {"_id": goal.id},
                        {"$set": {"linked_routine_id": routine["_id"]}}
                    )
                    goal.linked_routine_id = routine["_id"]
            
            logger.info("Converting goal to response...")
            try:
                response = self._goal_to_response(goal)
                logger.info(f"✓ Goal response created successfully")
                return response
            except Exception as conv_error:
                logger.error(f"❌ Failed to convert goal to response: {str(conv_error)}")
                raise
            
        except Exception as e:
            logger.error(f"Error creating goal: {str(e)}")
            raise
    
    def _create_milestones(
        self,
        goal_type: str,
        duration_days: int,
        baseline_value: float,
        target_value: float,
        custom_milestones: Optional[List[Any]] = None
    ) -> List[Milestone]:
        """Create milestones for a goal"""
        milestones = []
        
        if custom_milestones:
            # Use custom milestones if provided
            for cm in custom_milestones:
                milestone = Milestone(
                    title=cm.title,
                    description=cm.description,
                    target_value=cm.target_value,
                    percentage_trigger=cm.percentage_trigger,
                    reward_message=cm.reward_message
                )
                milestones.append(milestone)
        else:
            # Generate standard milestones
            percentages = [25, 50, 75, 100]
            
            for percentage in percentages:
                if goal_type == "parameter_improvement":
                    improvement_needed = target_value - baseline_value
                    milestone_value = baseline_value + (improvement_needed * percentage / 100)
                    title = f"{percentage}% Improvement Achieved"
                    reward_message = self._get_milestone_reward_message(percentage)
                else:
                    # For other goal types
                    days_milestone = int(duration_days * percentage / 100)
                    title = f"{percentage}% Complete - Day {days_milestone}"
                    milestone_value = percentage
                    reward_message = self._get_milestone_reward_message(percentage)
                
                milestone = Milestone(
                    title=title,
                    description=f"Reach {percentage}% of your goal",
                    target_value=milestone_value,
                    percentage_trigger=percentage,
                    reward_message=reward_message
                )
                milestones.append(milestone)
        
        return milestones
    
    def _get_milestone_reward_message(self, percentage: int) -> str:
        """Get motivational message for milestone completion"""
        messages = {
            25: "Great start! You're making progress! 💪",
            50: "Halfway there! Keep up the amazing work! 🌟",
            75: "Almost there! Your dedication is paying off! 🎯",
            100: "Congratulations! You've achieved your goal! 🎉"
        }
        return messages.get(percentage, "Well done!")
    
    def _create_linked_routine(
        self,
        user_id: str,
        goal: GoalModel
    ) -> Optional[Dict[str, Any]]:
        """Create a routine linked to a parameter improvement goal"""
        if goal.type != "parameter_improvement" or not goal.target_parameter:
            return None
        
        try:
            # Map parameter to routine focus
            focus_mapping = {
                "hydration": "hydration",
                "acne": "acne_control",
                "dark_spots": "brightening",
                "fine_lines_wrinkles": "anti_aging",
                "redness": "soothing",
                "smoothness": "exfoliation",
                "firmness": "firming",
                "radiance": "radiance",
                "dark_circles": "eye_care"
            }
            
            focus = focus_mapping.get(goal.target_parameter, "general")
            
            # Generate routine using routine service
            from ..schemas.routine import RoutineGenerateRequest
            request = RoutineGenerateRequest(
                routine_type="treatment",
                focus_areas=[focus],
                duration_preference="moderate"
            )
            
            routines = self.routine_service.generate_ai_routine(
                user_id,
                request
            )
            
            if routines:
                # Link the routine name to the goal
                routine = routines[0]
                self.routine_service.db.routines.update_one(
                    {"_id": routine["_id"]},
                    {"$set": {"name": f"{goal.title} Routine"}}
                )
                return routine
            
        except Exception as e:
            logger.error(f"Error creating linked routine: {str(e)}")
        
        return None
    
    def get_user_goals(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        skip: int = 0
    ) -> GoalListResponse:
        """Get all goals for a user"""
        logger.info(f"=== get_user_goals called with user_id: {user_id} (type: {type(user_id).__name__}) ===")
        self.initialize()
        
        try:
            # Always convert user_id to ObjectId for consistency
            try:
                user_oid = ObjectId(user_id)
                logger.info(f"Converted user_id to ObjectId: {user_oid}")
            except Exception as e:
                logger.error(f"Could not convert user_id '{user_id}' to ObjectId: {str(e)}")
                raise ValueError(f"Invalid user_id format: {user_id}")
            
            # Build query - only use ObjectId since we save as ObjectId
            query = {"user_id": user_oid}
            if status:
                query["status"] = status
            
            logger.info(f"Querying goals with: user_id={user_oid} (type: {type(user_oid).__name__}), status={status}")
            
            # First, let's check what user_ids exist in the goals collection
            sample_goals = list(self.db.goals.find({}).limit(5))
            if sample_goals:
                logger.info(f"Sample goals in DB:")
                for sg in sample_goals:
                    logger.info(f"  - Goal ID: {sg.get('_id')}, User ID: {sg.get('user_id')} (type: {type(sg.get('user_id')).__name__})")
            
            # Get goals (PyMongo is synchronous)
            goals = list(self.db.goals.find(query).sort("created_at", -1).skip(skip).limit(limit))
            logger.info(f"Query returned {len(goals)} goals for user {user_oid}")
            
            # Get counts by status
            pipeline = [
                {"$match": {"user_id": user_oid}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]
            status_counts = list(self.db.goals.aggregate(pipeline))
            
            counts = {
                "active": 0,
                "completed": 0,
                "abandoned": 0
            }
            for item in status_counts:
                if item["_id"] in counts:
                    counts[item["_id"]] = item["count"]
            
            # Convert to responses
            goal_responses = []
            for goal_data in goals:
                goal = GoalModel(**goal_data)
                goal_responses.append(self._goal_to_response(goal))
            
            return GoalListResponse(
                goals=goal_responses,
                total=len(goal_responses),
                active_count=counts["active"],
                completed_count=counts["completed"],
                abandoned_count=counts["abandoned"]
            )
            
        except Exception as e:
            logger.error(f"Error getting user goals: {str(e)}")
            raise
    
    def get_goal(
        self,
        user_id: str,
        goal_id: str
    ) -> GoalResponse:
        """Get a specific goal"""
        self.initialize()
        
        try:
            goal_data = self.db.goals.find_one({
                "_id": ObjectId(goal_id),
                "user_id": ObjectId(user_id)
            })
            
            if not goal_data:
                raise ValueError("Goal not found")
            
            goal = GoalModel(**goal_data)
            return self._goal_to_response(goal)
            
        except Exception as e:
            logger.error(f"Error getting goal: {str(e)}")
            raise
    
    def update_goal(
        self,
        user_id: str,
        goal_id: str,
        update_data: GoalUpdate
    ) -> GoalResponse:
        """Update a goal"""
        self.initialize()
        
        try:
            # Get current goal
            goal_data = self.db.goals.find_one({
                "_id": ObjectId(goal_id),
                "user_id": ObjectId(user_id)
            })
            
            if not goal_data:
                raise ValueError("Goal not found")
            
            # Prepare update
            update_dict = update_data.dict(exclude_unset=True)
            
            # Handle status changes
            if "status" in update_dict:
                if update_dict["status"] == "abandoned":
                    update_dict["abandoned_at"] = datetime.utcnow()
                elif update_dict["status"] == "completed":
                    update_dict["completed_at"] = datetime.utcnow()
                    # Check for achievement unlock
                    self._check_achievements(user_id, "goal_completed")
            
            update_dict["updated_at"] = datetime.utcnow()
            
            # Update in database
            self.db.goals.update_one(
                {"_id": ObjectId(goal_id)},
                {"$set": update_dict}
            )
            
            # Get updated goal
            updated_goal_data = self.db.goals.find_one({"_id": ObjectId(goal_id)})
            goal = GoalModel(**updated_goal_data)
            
            return self._goal_to_response(goal)
            
        except Exception as e:
            logger.error(f"Error updating goal: {str(e)}")
            raise
    
    def update_goal_progress(
        self,
        user_id: str,
        goal_id: str,
        progress_data: GoalProgressUpdate
    ) -> GoalResponse:
        """Update progress for a goal"""
        self.initialize()
        
        try:
            # Get current goal
            goal_data = self.db.goals.find_one({
                "_id": ObjectId(goal_id),
                "user_id": ObjectId(user_id)
            })
            
            if not goal_data:
                raise ValueError("Goal not found")
            
            goal = GoalModel(**goal_data)
            
            # Create progress record
            progress = GoalProgress(
                goal_id=ObjectId(goal_id),
                user_id=ObjectId(user_id),
                parameter_value=progress_data.parameter_value,
                routine_completed=progress_data.routine_completed,
                notes=progress_data.notes,
                source="manual"
            )
            
            self.db.goal_progress.insert_one(progress.dict(by_alias=True))
            
            # Update current value and progress
            update_dict = {
                "last_check_in": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if progress_data.parameter_value is not None:
                update_dict["current_value"] = progress_data.parameter_value
                # Calculate new progress percentage
                goal.current_value = progress_data.parameter_value
                update_dict["progress_percentage"] = goal.calculate_progress()
            
            # Check milestone completion
            milestones_updated = False
            for milestone in goal.milestones:
                if not milestone.completed:
                    if goal.type == "parameter_improvement" and milestone.target_value:
                        if goal.current_value >= milestone.target_value:
                            milestone.completed = True
                            milestone.completed_at = datetime.utcnow()
                            milestones_updated = True
                            # TODO: Send notification for milestone completion
                    elif milestone.percentage_trigger:
                        if goal.progress_percentage >= milestone.percentage_trigger:
                            milestone.completed = True
                            milestone.completed_at = datetime.utcnow()
                            milestones_updated = True
            
            if milestones_updated:
                update_dict["milestones"] = [m.dict() for m in goal.milestones]
            
            # Check if goal is completed
            if goal.progress_percentage >= 100 and goal.status == "active":
                update_dict["status"] = "completed"
                update_dict["completed_at"] = datetime.utcnow()
                self._check_achievements(user_id, "goal_completed")
            
            # Update goal
            self.db.goals.update_one(
                {"_id": ObjectId(goal_id)},
                {"$set": update_dict}
            )
            
            # Get updated goal
            updated_goal_data = self.db.goals.find_one({"_id": ObjectId(goal_id)})
            updated_goal = GoalModel(**updated_goal_data)
            
            return self._goal_to_response(updated_goal)
            
        except Exception as e:
            logger.error(f"Error updating goal progress: {str(e)}")
            raise
    
    def get_goal_progress(
        self,
        user_id: str,
        goal_id: str
    ) -> GoalProgressResponse:
        """Get detailed progress history for a goal"""
        self.initialize()
        
        try:
            # Verify goal ownership
            goal = self.db.goals.find_one({
                "_id": ObjectId(goal_id),
                "user_id": ObjectId(user_id)
            })
            
            if not goal:
                raise ValueError("Goal not found")
            
            # Get progress history (PyMongo is synchronous)
            progress_records = list(self.db.goal_progress.find({
                "goal_id": ObjectId(goal_id)
            }).sort("recorded_at", -1).limit(100))
            
            # Calculate statistics
            progress_history = []
            values = []
            
            for record in progress_records:
                progress_history.append({
                    "date": record["recorded_at"],
                    "value": record.get("parameter_value"),
                    "routine_completed": record.get("routine_completed"),
                    "notes": record.get("notes")
                })
                if record.get("parameter_value") is not None:
                    values.append(record["parameter_value"])
            
            # Calculate streaks (for routine goals)
            current_streak = 0
            best_streak = 0
            if goal["type"] == "routine_adherence":
                streak = 0
                for record in sorted(progress_records, key=lambda x: x["recorded_at"]):
                    if record.get("routine_completed"):
                        streak += 1
                        best_streak = max(best_streak, streak)
                    else:
                        streak = 0
                current_streak = streak
            
            # Calculate average daily progress
            avg_daily_progress = 0.0
            if values and len(values) > 1:
                days_elapsed = (progress_records[0]["recorded_at"] - progress_records[-1]["recorded_at"]).days
                if days_elapsed > 0:
                    total_progress = values[0] - values[-1]
                    avg_daily_progress = total_progress / days_elapsed
            
            # Project completion date
            projected_completion = None
            if avg_daily_progress > 0 and goal["current_value"] < goal["target_value"]:
                days_needed = (goal["target_value"] - goal["current_value"]) / avg_daily_progress
                projected_completion = datetime.utcnow() + timedelta(days=int(days_needed))
            
            # Determine if on track
            on_track = True
            if projected_completion and projected_completion > goal["target_date"]:
                on_track = False
            
            # Generate recommendations
            recommendations = self._generate_progress_recommendations(
                goal, on_track, avg_daily_progress
            )
            
            return GoalProgressResponse(
                goal_id=goal_id,
                progress_history=progress_history,
                current_streak=current_streak,
                best_streak=best_streak,
                average_daily_progress=avg_daily_progress,
                projected_completion_date=projected_completion,
                on_track=on_track,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error getting goal progress: {str(e)}")
            raise
    
    def _generate_progress_recommendations(
        self,
        goal: Dict[str, Any],
        on_track: bool,
        avg_daily_progress: float
    ) -> List[str]:
        """Generate personalized recommendations based on progress"""
        recommendations = []
        
        if not on_track:
            if goal["type"] == "parameter_improvement":
                recommendations.append("Consider adjusting your routine for better results")
                recommendations.append("Try adding a targeted treatment product")
                recommendations.append("Book a consultation with a skincare professional")
            elif goal["type"] == "routine_adherence":
                recommendations.append("Set reminders for your routine times")
                recommendations.append("Simplify your routine if it's too complex")
                recommendations.append("Keep products visible as a reminder")
        else:
            recommendations.append("Great progress! Keep up your current routine")
            if avg_daily_progress > 0:
                recommendations.append(f"At this rate, you'll reach your goal on time!")
        
        # Add parameter-specific recommendations
        if goal.get("target_parameter"):
            param_recommendations = {
                "hydration": [
                    "Drink more water throughout the day",
                    "Use a hydrating serum with hyaluronic acid",
                    "Apply moisturizer to damp skin"
                ],
                "acne": [
                    "Consider adding salicylic acid to your routine",
                    "Avoid touching your face during the day",
                    "Change pillowcases more frequently"
                ],
                "dark_spots": [
                    "Apply SPF 30+ sunscreen daily",
                    "Try vitamin C serum in the morning",
                    "Consider niacinamide for evening routine"
                ]
            }
            
            if goal["target_parameter"] in param_recommendations:
                recommendations.extend(param_recommendations[goal["target_parameter"]][:2])
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    def get_goal_insights(
        self,
        user_id: str,
        goal_id: str
    ) -> GoalInsight:
        """Get AI-powered insights for a goal"""
        self.initialize()
        
        try:
            # Get goal and progress data
            goal = self.db.goals.find_one({
                "_id": ObjectId(goal_id),
                "user_id": ObjectId(user_id)
            })
            
            if not goal:
                raise ValueError("Goal not found")
            
            # Get progress history
            progress_records = list(self.db.goal_progress.find({
                "goal_id": ObjectId(goal_id)
            }).sort("recorded_at", -1).limit(30))
            
            # Calculate success probability based on progress
            success_probability = self._calculate_success_probability(
                goal, progress_records
            )
            
            # Identify helping and hindering factors
            factors_helping = []
            factors_hindering = []
            
            # Analyze progress pattern
            if progress_records:
                # Check consistency
                days_since_last = (datetime.utcnow() - progress_records[0]["recorded_at"]).days
                if days_since_last <= 3:
                    factors_helping.append("Regular progress tracking")
                else:
                    factors_hindering.append("Irregular progress updates")
                
                # Check improvement rate
                if len(progress_records) > 5:
                    recent_values = [r.get("parameter_value", 0) for r in progress_records[:5] if r.get("parameter_value")]
                    if recent_values and all(recent_values[i] >= recent_values[i+1] for i in range(len(recent_values)-1)):
                        factors_helping.append("Consistent improvement trend")
                    else:
                        factors_hindering.append("Inconsistent progress")
            
            # Check linked routine completion
            if goal.get("linked_routine_id"):
                routine_completions = self.db.routine_completions.count_documents({
                    "routine_id": goal["linked_routine_id"],
                    "user_id": ObjectId(user_id),
                    "completed_at": {"$gte": datetime.utcnow() - timedelta(days=7)}
                })
                
                if routine_completions >= 5:
                    factors_helping.append("Strong routine adherence")
                else:
                    factors_hindering.append("Low routine adherence")
            
            # Generate recommended actions
            recommended_actions = self._generate_recommended_actions(
                goal, factors_helping, factors_hindering
            )
            
            # Get similar users' success rate
            similar_success_rate = self._get_similar_users_success_rate(goal)
            
            return GoalInsight(
                goal_id=goal_id,
                success_probability=success_probability,
                factors_helping=factors_helping,
                factors_hindering=factors_hindering,
                recommended_actions=recommended_actions,
                similar_users_success_rate=similar_success_rate
            )
            
        except Exception as e:
            logger.error(f"Error getting goal insights: {str(e)}")
            raise
    
    def _calculate_success_probability(
        self,
        goal: Dict[str, Any],
        progress_records: List[Dict[str, Any]]
    ) -> float:
        """Calculate probability of goal success"""
        base_probability = 50.0
        
        # Adjust based on progress
        if goal["progress_percentage"] > 0:
            days_elapsed = (datetime.utcnow() - goal["start_date"]).days
            days_total = goal["duration_days"]
            
            if days_elapsed > 0:
                expected_progress = (days_elapsed / days_total) * 100
                actual_progress = goal["progress_percentage"]
                
                if actual_progress >= expected_progress:
                    base_probability += min(30, (actual_progress - expected_progress))
                else:
                    base_probability -= min(30, (expected_progress - actual_progress))
        
        # Adjust based on engagement
        if progress_records:
            recent_updates = len([r for r in progress_records if 
                (datetime.utcnow() - r["recorded_at"]).days <= 7])
            base_probability += min(20, recent_updates * 5)
        
        return max(0, min(100, base_probability))
    
    def _generate_recommended_actions(
        self,
        goal: Dict[str, Any],
        factors_helping: List[str],
        factors_hindering: List[str]
    ) -> List[str]:
        """Generate AI-powered recommended actions"""
        
        prompt = f"""
        Based on this goal progress analysis, suggest 3-4 specific actions:
        
        Goal: {goal['title']}
        Type: {goal['type']}
        Progress: {goal['progress_percentage']}%
        Days Remaining: {goal.get('days_remaining', 0)}
        
        Positive Factors: {', '.join(factors_helping) if factors_helping else 'None identified'}
        Challenges: {', '.join(factors_hindering) if factors_hindering else 'None identified'}
        
        Provide actionable, specific recommendations that address the challenges
        and leverage the positive factors. Format as a JSON array of strings.
        """
        
        try:
            ai_response = self.openai_service.generate_completion(
                prompt,
                system_message="You are a goal achievement coach providing specific, actionable advice."
            )
            
            actions = json.loads(ai_response)
            return actions[:4]
        except:
            # Fallback recommendations
            return [
                "Review and adjust your daily routine",
                "Set specific reminders for goal-related activities",
                "Track progress more frequently",
                "Consider breaking down the goal into smaller tasks"
            ]
    
    def _get_similar_users_success_rate(
        self,
        goal: Dict[str, Any]
    ) -> float:
        """Get success rate of similar users with similar goals"""
        # For now, return a mock value
        # In production, this would query completed goals with similar parameters
        return 72.5
    
    def get_user_achievements(
        self,
        user_id: str
    ) -> List[AchievementResponse]:
        """Get all achievements for a user"""
        self.initialize()
        
        try:
            # Convert user_id to ObjectId
            try:
                user_oid = ObjectId(user_id)
            except:
                logger.error(f"Could not convert user_id '{user_id}' to ObjectId")
                raise ValueError(f"Invalid user_id format: {user_id}")
            
            # Get user's achievement progress (check both formats for backward compatibility)
            user_achievements = list(self.db.achievements.find({
                "$or": [{"user_id": user_oid}, {"user_id": user_id}]
            }))
            
            # Create a map of unlocked achievements
            unlocked_map = {a["achievement_id"]: a for a in user_achievements}
            
            # Build response with all achievements
            achievement_responses = []
            for definition in self.achievement_definitions:
                achievement = AchievementResponse(
                    achievement_id=definition["achievement_id"],
                    title=definition["title"],
                    description=definition["description"],
                    icon=definition["icon"],
                    category=definition["category"],
                    tier=definition["tier"],
                    points=definition["points"],
                    unlocked=definition["achievement_id"] in unlocked_map,
                    unlocked_at=unlocked_map.get(definition["achievement_id"], {}).get("unlocked_at"),
                    progress=unlocked_map.get(definition["achievement_id"], {}).get("progress", 0.0)
                )
                achievement_responses.append(achievement)
            
            return achievement_responses
            
        except Exception as e:
            logger.error(f"Error getting user achievements: {str(e)}")
            raise
    
    def _check_achievements(
        self,
        user_id: str,
        trigger: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Check and unlock achievements based on trigger"""
        try:
            # Check each achievement definition
            for definition in self.achievement_definitions:
                criteria = definition["criteria"]
                
                # Skip if already unlocked
                existing = self.db.achievements.find_one({
                    "user_id": ObjectId(user_id),
                    "achievement_id": definition["achievement_id"],
                    "unlocked": True
                })
                if existing:
                    continue
                
                # Check criteria based on trigger
                unlocked = False
                progress = 0.0
                
                if trigger == "goal_completed" and criteria.get("goals_completed"):
                    completed_count = self.db.goals.count_documents({
                        "user_id": ObjectId(user_id),
                        "status": "completed"
                    })
                    if completed_count >= criteria["goals_completed"]:
                        unlocked = True
                    progress = min(100, (completed_count / criteria["goals_completed"]) * 100)
                
                elif trigger == "parameter_update" and context:
                    if criteria.get("parameter") == context.get("parameter"):
                        if context.get("value", 0) >= criteria.get("min_score", 0):
                            unlocked = True
                        progress = min(100, (context.get("value", 0) / criteria.get("min_score", 100)) * 100)
                
                elif trigger == "routine_streak" and criteria.get("routine_streak"):
                    # This would check routine completion streak
                    # Implementation depends on routine tracking
                    pass
                
                # Save achievement progress
                if unlocked or progress > 0:
                    achievement = Achievement(
                        achievement_id=definition["achievement_id"],
                        title=definition["title"],
                        description=definition["description"],
                        icon=definition["icon"],
                        category=definition["category"],
                        tier=definition["tier"],
                        criteria=criteria,
                        points=definition["points"],
                        user_id=ObjectId(user_id),
                        unlocked=unlocked,
                        unlocked_at=datetime.utcnow() if unlocked else None,
                        progress=progress
                    )
                    
                    self.db.achievements.update_one(
                        {
                            "user_id": ObjectId(user_id),
                            "achievement_id": definition["achievement_id"]
                        },
                        {"$set": achievement.dict(by_alias=True, exclude={"id"})},
                        upsert=True
                    )
                    
                    if unlocked:
                        # TODO: Send notification for achievement unlock
                        logger.info(f"Achievement unlocked: {definition['title']} for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error checking achievements: {str(e)}")
    
    def get_goal_templates(
        self,
        user_id: str
    ) -> List[GoalTemplateResponse]:
        """Get recommended goal templates for user"""
        self.initialize()
        
        try:
            # Get user profile
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            user_profile = user.get("profile", {})
            
            # Get all templates
            templates = list(self.db.goal_templates.find({}))
            
            # Score and filter templates
            template_responses = []
            for template in templates:
                # Check suitability
                suitable = self._is_template_suitable(template, user_profile)
                
                template_responses.append(GoalTemplateResponse(
                    id=str(template["_id"]),
                    title=template["title"],
                    description=template["description"],
                    type=template["type"],
                    category=template["category"],
                    default_duration_days=template["default_duration_days"],
                    default_improvement_target=template["default_improvement_target"],
                    difficulty_level=template["difficulty_level"],
                    suitable_for_you=suitable,
                    success_rate=template.get("success_rate", 0.0),
                    tips=template.get("tips", [])
                ))
            
            # Sort by suitability and success rate
            template_responses.sort(
                key=lambda x: (x.suitable_for_you, x.success_rate),
                reverse=True
            )
            
            return template_responses
            
        except Exception as e:
            logger.error(f"Error getting goal templates: {str(e)}")
            raise
    
    def _is_template_suitable(
        self,
        template: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> bool:
        """Check if template is suitable for user"""
        suitable_age = True
        suitable_skin = True
        
        # Check age group
        if template.get("suitable_for_age_groups"):
            user_age = user_profile.get("age_group", "").replace("_", "-")
            suitable_age = user_age in template["suitable_for_age_groups"]
        
        # Check skin type
        if template.get("suitable_for_skin_types"):
            suitable_skin = user_profile.get("skin_type", "") in template["suitable_for_skin_types"]
        
        return suitable_age and suitable_skin
    
    def _goal_to_response(self, goal: GoalModel) -> GoalResponse:
        """Convert goal model to response schema"""
        return GoalResponse(
            id=str(goal.id),
            user_id=str(goal.user_id),
            title=goal.title,
            description=goal.description,
            type=goal.type,
            category=goal.category,
            target_parameter=goal.target_parameter,
            baseline_value=goal.baseline_value,
            target_value=goal.target_value,
            current_value=goal.current_value,
            improvement_target=goal.improvement_target,
            start_date=goal.start_date,
            target_date=goal.target_date,
            duration_days=goal.duration_days,
            days_remaining=goal.get_days_remaining(),
            is_overdue=goal.is_overdue(),
            progress_percentage=goal.calculate_progress(),
            milestones=[self._milestone_to_response(m) for m in goal.milestones],
            last_check_in=goal.last_check_in,
            status=goal.status,
            completed_at=goal.completed_at,
            difficulty_level=goal.difficulty_level,
            reward_points=goal.reward_points,
            ai_generated=goal.ai_generated,
            created_at=goal.created_at,
            updated_at=goal.updated_at
        )
    
    def _milestone_to_response(self, milestone: Milestone) -> MilestoneResponse:
        """Convert milestone model to response schema"""
        return MilestoneResponse(
            milestone_id=milestone.milestone_id,
            title=milestone.title,
            description=milestone.description,
            target_value=milestone.target_value,
            target_date=milestone.target_date,
            completed=milestone.completed,
            completed_at=milestone.completed_at,
            reward_message=milestone.reward_message,
            percentage_trigger=milestone.percentage_trigger
        )
