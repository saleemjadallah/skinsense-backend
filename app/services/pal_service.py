"""
Pal AI Service - The friendly AI mascot for SkinSense
Uses GPT-5 (ChatGPT) for personalized skincare guidance
"""

import openai
from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime, timedelta
from ..core.config import settings
from ..core.monitoring import track_ai_service, ai_service_tokens
from ..database import get_database
from ..models.user import UserModel
from bson import ObjectId

logger = logging.getLogger(__name__)

# Pal's core personality and guidelines
PAL_SYSTEM_PROMPT = """
You are Pal, the friendly and knowledgeable AI mascot for SkinSense AI, a beauty and wellness app that helps users understand and care for their skin. You appear as the adorable gradient droplet character with a smiling face that users see in the app.

## Your Core Identity:
- Name: Pal (the user's SkinSense pal supporting them in their skin journey)
- Personality: Warm, encouraging, knowledgeable yet approachable, like a supportive friend who happens to know a lot about skincare
- Tone: Conversational, positive, and empowering - never judgmental or medical
- You use simple language, avoiding complex medical terminology unless specifically asked

## Your Knowledge Scope - YOU CAN HELP WITH:
1. **Skincare Education**:
   - Explaining ingredients (what they do, benefits, potential interactions)
   - Skin types and how to identify them
   - Basic skin concerns (dryness, oiliness, sensitivity, combination skin)
   - Product categories and their purposes (cleansers, toners, serums, moisturizers, SPF)
   - Application techniques and layering orders
   - Morning vs. evening routine differences

2. **Product Guidance**:
   - How to read product labels
   - Understanding product compatibility with skin types
   - Explaining the user's SkinSense AI analysis results
   - General guidance on building routines
   - Seasonal skincare adjustments
   - Travel skincare tips

3. **Lifestyle & Wellness**:
   - How diet affects skin (general information only)
   - Importance of hydration
   - Sleep and skin health connection
   - Stress and skin relationship
   - Exercise benefits for skin
   - Environmental factors (pollution, weather)

4. **Beauty Techniques**:
   - Basic application tips
   - Tools and their uses (jade rollers, gua sha, etc.)
   - DIY spa day ideas (non-medical)
   - Makeup and skincare interaction

## STRICT BOUNDARIES - YOU CANNOT:
1. **Diagnose** any skin conditions (acne, rosacea, eczema, psoriasis, etc.)
2. **Prescribe** treatments or medications
3. **Interpret** medical symptoms or skin irregularities
4. **Replace** dermatologist consultations
5. **Discuss** topics unrelated to skin/beauty (politics, news, general chat)
6. **Provide** specific medical advice about skin diseases or conditions
7. **Recommend** prescription products or medical procedures

## Response Framework:

### For Valid Skincare Questions:
1. Acknowledge the question warmly
2. Provide helpful, accurate information
3. If relevant, reference their SkinSense AI data (skin type, concerns they've logged)
4. Suggest how they might use app features (scan product, track progress)
5. End with encouragement or a helpful tip

### For Medical/Diagnostic Questions:
"I understand you're concerned about [topic]. While I can share general skincare knowledge, I can't provide medical advice or diagnose skin conditions. For specific concerns about skin irregularities or medical conditions, it's best to consult with a dermatologist who can examine your skin properly. 

What I CAN help you with is general skincare education, product information, and routine building! Is there anything about daily skincare I can help with? 💧✨"

### For Off-Topic Questions:
"Oh! I'm flattered you'd ask, but I'm specifically designed to be your skincare companion! 🌟 I focus all my knowledge on helping you achieve your best skin. Is there anything about skincare, products, or your routine I can help you with today?"

## Important Disclaimers to Include:
- When discussing products: "Remember, everyone's skin is unique! What works for one person might not work for another."
- When giving routine advice: "This is general guidance for educational purposes. For personalized medical advice, consult a dermatologist."
- When discussing skin concerns: "I'm here to provide beauty and wellness information, not medical advice."

## Special Features Integration:
- Reference their streak: "Amazing job on your [streak] day streak! Consistency is the secret to great skin! 🎉"
- Mention their progress: "Based on your [score]% skin score, you're doing fantastic!"
- Suggest app features: "You could scan that product with our barcode scanner to see if it matches your skin type!"
- Reference their goals: "Since [goal] is one of your goals, let me tell you about..."

## Memory and Context:
- Remember the current conversation context
- Reference previous points in the same chat session
- Be aware of their SkinSense profile data (skin type, concerns, goals)
- Acknowledge their progress and encourage continuation

Always maintain a balance between being informative and keeping boundaries clear. You're a beauty and wellness guide, not a medical professional. Your goal is to educate, encourage, and empower users on their skincare journey while always directing medical concerns to appropriate professionals.
"""

class PalService:
    """
    Pal AI Service for personalized skincare chat assistance
    """
    
    def __init__(self):
        self.db = get_database()  # Initialize database immediately
        try:
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {e}")
            # Still allow service to initialize even if OpenAI fails
            self.client = None
        
        # Get collections from database
        self.chat_collection = self.db.pal_chats
        self.session_collection = self.db.pal_sessions
        
    @track_ai_service("openai", "pal_chat")
    def chat_with_pal(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a chat message with Pal
        
        Args:
            user_id: User's ID
            message: User's message to Pal
            session_id: Optional session ID for context continuity
            
        Returns:
            Dict containing Pal's response and metadata
        """
        try:
            # Check if OpenAI client is available
            if self.client is None:
                logger.error("OpenAI client not initialized")
                return self._get_fallback_response(message)
            
            # Get user context
            user_context = self._get_user_context(user_id)
            
            # Get conversation history if session exists
            conversation_history = []
            if session_id:
                conversation_history = self._get_session_history(session_id)
            else:
                # Create new session
                session_id = str(ObjectId())
                self._create_session(user_id, session_id)
            
            # Build messages for GPT-5
            messages = self._build_messages(
                message, 
                user_context, 
                conversation_history
            )
            
            # Track prompt tokens
            prompt_text = json.dumps(messages)
            prompt_tokens = len(prompt_text.split()) * 1.3
            ai_service_tokens.labels(service="openai", type="prompt").inc(int(prompt_tokens))
            
            # Call GPT-5 (using gpt-4-turbo as the latest available model)
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",  # Will be updated to gpt-5 when available
                messages=messages,
                temperature=0.8,
                max_tokens=500,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            # Track completion tokens
            if hasattr(response, 'usage'):
                ai_service_tokens.labels(service="openai", type="completion").inc(
                    response.usage.completion_tokens
                )
            
            pal_response = response.choices[0].message.content
            
            # Save chat to history
            self._save_chat_message(
                user_id=user_id,
                session_id=session_id,
                user_message=message,
                pal_response=pal_response
            )
            
            return {
                "response": pal_response,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "emotion": self._detect_emotion(pal_response),
                "suggestions": self._get_follow_up_suggestions(message, pal_response)
            }
            
        except Exception as e:
            logger.error(f"Pal chat error: {e}")
            return self._get_fallback_response(message)
    
    def _build_messages(
        self,
        message: str,
        user_context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Build messages array for GPT with context
        """
        messages = [
            {"role": "system", "content": PAL_SYSTEM_PROMPT}
        ]
        
        # Add user context as system message
        if user_context:
            context_message = self._format_user_context(user_context)
            messages.append({
                "role": "system", 
                "content": f"User Context:\n{context_message}"
            })
        
        # Add conversation history (last 10 messages)
        for chat in conversation_history[-10:]:
            messages.append({"role": "user", "content": chat.get("user_message", "")})
            messages.append({"role": "assistant", "content": chat.get("pal_response", "")})
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def _format_user_context(self, context: Dict[str, Any]) -> str:
        """
        Format user context for AI understanding
        """
        context_parts = []
        
        # User profile
        if "profile" in context:
            profile = context["profile"]
            context_parts.append(f"Skin Type: {profile.get('skin_type', 'Unknown')}")
            context_parts.append(f"Age Range: {profile.get('age_range', 'Unknown')}")
            context_parts.append(f"Gender: {profile.get('gender', 'Unknown')}")
            if profile.get('skin_concerns'):
                context_parts.append(f"Concerns: {', '.join(profile['skin_concerns'])}")
        
        # Latest skin analysis
        if "latest_analysis" in context:
            analysis = context["latest_analysis"]
            context_parts.append(f"\nLatest Skin Score: {analysis.get('overall_score', 0)}/100")
            
            # Add specific metrics if below 80
            for metric, score in analysis.get('metrics', {}).items():
                if score < 80:
                    context_parts.append(f"- {metric}: {score}/100 (needs attention)")
        
        # Current streak
        if "streak" in context:
            context_parts.append(f"\nCurrent Streak: {context['streak']} days")
        
        # Active goals
        if "goals" in context and context["goals"]:
            goal_names = [g.get('name', '') for g in context["goals"][:3]]
            context_parts.append(f"Active Goals: {', '.join(goal_names)}")
        
        # Recent routine completion
        if "routine_completion" in context:
            context_parts.append(f"Today's Routine: {context['routine_completion']}% complete")
        
        return "\n".join(context_parts)
    
    def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Gather user context for personalized responses
        """
        try:
            user = UserModel.get_by_id(user_id)
            if not user:
                return {}
            
            context = {
                "profile": {
                    "skin_type": user.profile.skin_type if user.profile else None,
                    "age_range": user.profile.age_range if user.profile else None,
                    "gender": user.profile.gender if user.profile else None,
                    "skin_concerns": user.profile.skin_concerns if user.profile else []
                }
            }
            
            # Get latest skin analysis
            analysis_collection = self.db.skin_analyses
            latest_analysis = analysis_collection.find_one(
                {"user_id": ObjectId(user_id)},
                sort=[("created_at", -1)]
            )
            
            if latest_analysis:
                context["latest_analysis"] = {
                    "overall_score": latest_analysis.get("overall_skin_health_score", 0),
                    "metrics": {
                        "hydration": latest_analysis.get("hydration", 0),
                        "smoothness": latest_analysis.get("smoothness", 0),
                        "radiance": latest_analysis.get("radiance", 0),
                        "acne": latest_analysis.get("acne", 0),
                        "dark_spots": latest_analysis.get("dark_spots", 0),
                        "firmness": latest_analysis.get("firmness", 0)
                    }
                }
            
            # Get streak data
            routine_collection = self.db.routine_completions
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            recent_completions = routine_collection.count_documents({
                "user_id": ObjectId(user_id),
                "completed_at": {"$gte": today - timedelta(days=7)}
            })
            context["streak"] = recent_completions
            
            # Get active goals
            goals_collection = self.db.goals
            active_goals = list(goals_collection.find(
                {"user_id": ObjectId(user_id), "status": "active"}
            ).limit(3))
            
            if active_goals:
                context["goals"] = [
                    {"name": g.get("name", ""), "target": g.get("target_value", 0)}
                    for g in active_goals
                ]
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return {}
    
    def _get_session_history(
        self, 
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session
        """
        try:
            chats = list(self.chat_collection.find(
                {"session_id": session_id}
            ).sort("timestamp", 1).limit(50))
            
            return chats
            
        except Exception as e:
            logger.error(f"Error getting session history: {e}")
            return []
    
    def _create_session(self, user_id: str, session_id: str):
        """
        Create a new chat session
        """
        try:
            self.session_collection.insert_one({
                "_id": ObjectId(session_id),
                "user_id": ObjectId(user_id),
                "created_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "message_count": 0
            })
        except Exception as e:
            logger.error(f"Error creating session: {e}")
    
    def _save_chat_message(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        pal_response: str
    ):
        """
        Save chat message to history
        """
        try:
            self.chat_collection.insert_one({
                "user_id": ObjectId(user_id),
                "session_id": session_id,
                "user_message": user_message,
                "pal_response": pal_response,
                "timestamp": datetime.utcnow(),
                "helpful": None  # For future feedback
            })
            
            # Update session activity
            self.session_collection.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {"last_activity": datetime.utcnow()},
                    "$inc": {"message_count": 1}
                }
            )
            
        except Exception as e:
            logger.error(f"Error saving chat message: {e}")
    
    def _detect_emotion(self, response: str) -> str:
        """
        Detect emotion from Pal's response for animation
        """
        response_lower = response.lower()
        
        if any(word in response_lower for word in ["great", "amazing", "fantastic", "excellent", "wonderful"]):
            return "happy"
        elif any(word in response_lower for word in ["hmm", "let me think", "interesting"]):
            return "thinking"
        elif any(word in response_lower for word in ["keep going", "you can do", "don't give up"]):
            return "encouraging"
        elif any(word in response_lower for word in ["concerned", "careful", "caution"]):
            return "concerned"
        else:
            return "neutral"
    
    def _get_follow_up_suggestions(
        self, 
        user_message: str, 
        pal_response: str
    ) -> List[str]:
        """
        Generate follow-up question suggestions
        """
        suggestions = []
        
        # Context-based suggestions
        if "ingredient" in user_message.lower():
            suggestions.append("What other ingredients work well with this?")
            suggestions.append("Are there any ingredients I should avoid?")
        elif "routine" in user_message.lower():
            suggestions.append("What order should I apply products?")
            suggestions.append("How long should I wait between steps?")
        elif "product" in user_message.lower():
            suggestions.append("How do I know if a product is working?")
            suggestions.append("When should I see results?")
        elif "skin type" in user_message.lower():
            suggestions.append("What products work best for my skin type?")
            suggestions.append("How can I balance my skin?")
        else:
            # Default suggestions
            suggestions = [
                "Tell me about my skin progress",
                "What's a good morning routine?",
                "How do I layer skincare products?",
                "What ingredients should I look for?"
            ]
        
        return suggestions[:3]  # Return top 3 suggestions
    
    def _get_fallback_response(self, message: str) -> Dict[str, Any]:
        """
        Fallback response when AI service fails
        """
        return {
            "response": "Hey there! 💧 I'm having a little trouble connecting right now, but I'm still here to help! While I get back online, remember that consistency is key in skincare. Keep up with your routine, and feel free to explore the app's other features like scanning products or checking your progress. I'll be back to answer your questions soon!",
            "session_id": str(ObjectId()),
            "timestamp": datetime.utcnow().isoformat(),
            "emotion": "neutral",
            "suggestions": [
                "Check my skin analysis",
                "View my routine",
                "Scan a product",
                "See my progress"
            ]
        }
    
    def get_conversation_starters(
        self, 
        user_id: str
    ) -> List[Dict[str, str]]:
        """
        Get personalized conversation starters
        """
        try:
            context = self._get_user_context(user_id)
            starters = []
            
            # Based on skin concerns
            if context.get("latest_analysis"):
                metrics = context["latest_analysis"].get("metrics", {})
                lowest_metric = min(metrics.items(), key=lambda x: x[1])
                if lowest_metric[1] < 80:
                    starters.append({
                        "text": f"How can I improve my {lowest_metric[0]}?",
                        "icon": "💧"
                    })
            
            # Based on time of day
            current_hour = datetime.now().hour
            if 5 <= current_hour < 12:
                starters.append({
                    "text": "What's a good morning routine for me?",
                    "icon": "☀️"
                })
            elif 18 <= current_hour <= 23:
                starters.append({
                    "text": "What should my evening routine include?",
                    "icon": "🌙"
                })
            
            # Based on streak
            if context.get("streak", 0) > 0:
                starters.append({
                    "text": "How's my skin progress looking?",
                    "icon": "📈"
                })
            
            # General helpful starters
            starters.extend([
                {"text": "What's niacinamide good for?", "icon": "🧪"},
                {"text": "How do I layer my skincare?", "icon": "📚"},
                {"text": "What ingredients should I avoid?", "icon": "⚠️"}
            ])
            
            return starters[:4]  # Return top 4 starters
            
        except Exception as e:
            logger.error(f"Error getting conversation starters: {e}")
            return [
                {"text": "Tell me about my skin type", "icon": "💧"},
                {"text": "What's a basic routine?", "icon": "📋"},
                {"text": "Explain retinol to me", "icon": "🧪"},
                {"text": "How often should I exfoliate?", "icon": "✨"}
            ]
    
    def clear_chat_history(self, user_id: str, session_id: Optional[str] = None):
        """
        Clear chat history for a user or specific session
        """
        try:
            if session_id:
                # Clear specific session
                self.chat_collection.delete_many({
                    "session_id": session_id,
                    "user_id": ObjectId(user_id)
                })
            else:
                # Clear all user's chat history
                self.chat_collection.delete_many({
                    "user_id": ObjectId(user_id)
                })
                
                # Also clear sessions
                self.session_collection.delete_many({
                    "user_id": ObjectId(user_id)
                })
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")
            return False

# Service is instantiated in each endpoint to ensure proper database connection
# No global instance needed - follows the pattern of other services like GoalService