import openai
from typing import Dict, Any, List, Optional
import json
import logging
from app.core.config import settings
from app.core.monitoring import track_ai_service, ai_service_tokens

logger = logging.getLogger(__name__)

SKIN_EXPERT_SYSTEM_PROMPT = """
You are SkinSense AI, a knowledgeable and encouraging beauty and skincare expert. 
Your role is to provide SPECIFIC, ACTIONABLE feedback based on the exact skin analysis scores provided.

Key guidelines:
1. ALWAYS reference the specific metric scores in your feedback
2. Focus on metrics scoring below 80 - these are priority areas
3. Recommend SPECIFIC ingredients for each concern:
   - Low Hydration (<80): Hyaluronic acid, ceramides, glycerin
   - High Acne (<80 score): Salicylic acid, niacinamide, tea tree
   - Dark Spots (<80): Vitamin C, kojic acid, arbutin
   - Fine Lines (<80): Retinol, peptides, vitamin A
   - Redness (<80): Centella asiatica, green tea, aloe
   - Low Firmness (<80): Collagen peptides, vitamin E
4. Provide a morning AND evening routine with specific steps
5. Be encouraging but SPECIFIC - avoid generic advice
6. Your summary should mention the top 3 concerns by score
7. Each recommendation should target a specific low-scoring metric

IMPORTANT: You MUST respond with valid JSON only. Do not include any text before or after the JSON.

Structure your response as a JSON object with these fields:
{
  "summary": "Reference their ACTUAL scores and top 3 concerns",
  "recommendations": ["SPECIFIC tip for lowest score", "SPECIFIC tip for 2nd lowest", "SPECIFIC tip for 3rd lowest"],
  "routine_suggestions": "Morning: [specific steps]. Evening: [specific steps]",
  "encouragement": "Reference their specific scores and improvements",
  "next_steps": ["action for lowest scoring metric", "action for 2nd lowest"]
}
"""

class OpenAIService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    @track_ai_service("openai", "generate_feedback")
    def generate_skin_feedback(
        self,
        analysis_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        previous_analyses: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized AI feedback based on skin analysis
        """
        try:
            # Log what we received
            logger.info(f"OpenAI Service received analysis_data keys: {analysis_data.keys() if analysis_data else 'None'}")
            if 'metrics' in analysis_data:
                logger.info(f"Metrics found in analysis_data: {analysis_data['metrics'].keys()}")
                logger.info(f"Sample scores - Hydration: {analysis_data['metrics'].get('hydration')}, Acne: {analysis_data['metrics'].get('acne')}")
            else:
                logger.info(f"No 'metrics' key in analysis_data. Direct keys available: {list(analysis_data.keys())[:10]}")
                # Check if metrics are at top level
                if 'hydration' in analysis_data:
                    logger.info(f"Metrics at top level - Hydration: {analysis_data.get('hydration')}, Acne: {analysis_data.get('acne')}")
            
            prompt = self._build_feedback_prompt(
                analysis_data, 
                user_profile, 
                previous_analyses
            )
            logger.info(f"Generated prompt preview (first 500 chars): {prompt[:500]}")
            
            # Track prompt tokens (estimate)
            prompt_tokens = len(prompt.split()) * 1.3
            ai_service_tokens.labels(service="openai", type="prompt").inc(int(prompt_tokens))
            
            # Use GPT-4-turbo-preview for better quality
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": SKIN_EXPERT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
                # Note: response_format not supported by gpt-4-turbo-preview
            )
            
            # Track completion tokens
            if hasattr(response, 'usage'):
                ai_service_tokens.labels(service="openai", type="completion").inc(
                    response.usage.completion_tokens
                )
            
            feedback_text = response.choices[0].message.content
            
            # Clean the response if GPT-4 wrapped it in markdown code blocks
            if feedback_text.startswith("```json"):
                feedback_text = feedback_text.replace("```json", "").replace("```", "").strip()
            elif feedback_text.startswith("```"):
                feedback_text = feedback_text.replace("```", "").strip()
            
            feedback_data = json.loads(feedback_text)
            
            return self._validate_feedback_response(feedback_data)
            
        except Exception as e:
            logger.error(f"OpenAI feedback generation failed: {e}")
            return self._get_fallback_feedback()
    
    def _build_feedback_prompt(
        self,
        analysis_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        previous_analyses: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Build comprehensive prompt for AI feedback
        """
        prompt_parts = []
        
        # If caller passed full user object, drill into profile
        if "profile" in user_profile:
            user_profile = user_profile.get("profile", {}) or {}

        # Current analysis
        prompt_parts.append("CURRENT SKIN ANALYSIS:")
        prompt_parts.append(f"Skin Type: {analysis_data.get('skin_type', 'Unknown')}")
        prompt_parts.append(f"Concerns: {', '.join(analysis_data.get('concerns', []))}")
        
        # Extract our 10 key metrics (handle nested 'metrics' structure)
        metrics_source = analysis_data.get('metrics', analysis_data)
        prompt_parts.append("\nSKIN METRICS (0-100 scale):")
        metrics = {
            "Overall Skin Health": metrics_source.get('overall_skin_health_score', 0),
            "Hydration": metrics_source.get('hydration', 0),
            "Smoothness": metrics_source.get('smoothness', 0),
            "Radiance": metrics_source.get('radiance', 0),
            "Dark Spots": metrics_source.get('dark_spots', 0),
            "Firmness": metrics_source.get('firmness', 0),
            "Fine Lines & Wrinkles": metrics_source.get('fine_lines_wrinkles', 0),
            "Acne": metrics_source.get('acne', 0),
            "Dark Circles": metrics_source.get('dark_circles', 0),
            "Redness": metrics_source.get('redness', 0)
        }
        
        for metric_name, score in metrics.items():
            status = "⚠️ Needs attention" if score < 80 else "✅ Good"
            prompt_parts.append(f"- {metric_name}: {score}/100 {status}")
        
        # User profile
        prompt_parts.append("\nUSER PROFILE:")
        prompt_parts.append(f"Age Range: {user_profile.get('age_range', 'Not specified')}")
        prompt_parts.append(f"Skin Type: {user_profile.get('skin_type', 'Not specified')}")
        prompt_parts.append(f"Main Concerns: {', '.join(user_profile.get('skin_concerns', []))}")
        prompt_parts.append(f"Current Routine: {', '.join(user_profile.get('current_routine', []))}")
        prompt_parts.append(f"Goals: {', '.join(user_profile.get('goals', []))}")
        
        # Progress comparison if available
        if previous_analyses and len(previous_analyses) > 0:
            prompt_parts.append("\nPROGRESS COMPARISON:")
            latest_previous = previous_analyses[0].get('analysis_data', {})
            
            # Compare each metric
            for metric_name, current_score in metrics.items():
                metric_key = metric_name.lower().replace(' ', '_').replace('&', '').replace('__', '_')
                prev_score = latest_previous.get(metric_key, current_score)
                
                change = current_score - prev_score
                if change > 5:
                    prompt_parts.append(f"- {metric_name}: Improved by {change:.1f} points! 📈")
                elif change < -5:
                    prompt_parts.append(f"- {metric_name}: Decreased by {abs(change):.1f} points 📉")
                else:
                    prompt_parts.append(f"- {metric_name}: Maintained steady ➡️")
        
        # Add specific instructions for actionable feedback
        prompt_parts.append("\nIMPORTANT INSTRUCTIONS:")
        prompt_parts.append("1. Focus on the metrics that scored below 80 - these need immediate attention")
        prompt_parts.append("2. Be SPECIFIC about what ingredients and products to use for low-scoring areas")
        prompt_parts.append("3. Provide actionable steps, not generic advice")
        prompt_parts.append("4. Reference the actual scores in your feedback")
        prompt_parts.append("5. If hydration is below 80, recommend hyaluronic acid and ceramides")
        prompt_parts.append("6. If acne score is below 80, recommend salicylic acid or niacinamide")
        prompt_parts.append("7. If dark spots are below 80, recommend vitamin C or kojic acid")
        prompt_parts.append("8. If fine lines are below 80, recommend retinol or peptides")
        prompt_parts.append("\nPlease provide encouraging, personalized feedback that directly addresses their specific scores and needs.")
        
        return "\n".join(prompt_parts)
    
    def _validate_feedback_response(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean AI response
        """
        required_fields = ["summary", "recommendations", "routine_suggestions", "encouragement", "next_steps"]
        
        for field in required_fields:
            if field not in feedback_data:
                feedback_data[field] = self._get_default_value(field)
        
        # Ensure recommendations and next_steps are lists
        if not isinstance(feedback_data["recommendations"], list):
            feedback_data["recommendations"] = [feedback_data["recommendations"]]
        
        if not isinstance(feedback_data["next_steps"], list):
            feedback_data["next_steps"] = [feedback_data["next_steps"]]
        
        return feedback_data
    
    def _get_default_value(self, field: str) -> Any:
        """
        Get default values for missing fields
        """
        defaults = {
            "summary": "Your skin analysis is complete! Keep up the great work on your skincare journey.",
            "recommendations": ["Stay consistent with your routine", "Drink plenty of water", "Get adequate sleep"],
            "routine_suggestions": "Continue with your current routine and consider adding a gentle moisturizer.",
            "encouragement": "You're doing amazing! Every step counts in your skincare journey. <",
            "next_steps": ["Take another progress photo next week", "Track how your skin feels daily"]
        }
        return defaults.get(field, "")
    
    def _get_fallback_feedback(self) -> Dict[str, Any]:
        """
        Fallback feedback when AI service fails
        """
        return {
            "summary": "Your skin analysis has been completed successfully! While we process the detailed insights, remember that consistency is key in skincare.",
            "recommendations": [
                "Maintain a consistent daily routine",
                "Stay hydrated and get enough sleep",
                "Protect your skin with SPF during the day",
                "Be patient - skin improvements take time"
            ],
            "routine_suggestions": "Focus on the basics: gentle cleansing, moisturizing, and sun protection. Add new products gradually.",
            "encouragement": "Every skincare journey is unique, and you're taking great steps by tracking your progress! Keep it up! (",
            "next_steps": [
                "Continue taking weekly progress photos",
                "Note how your skin feels and looks daily",
                "Stay consistent with your current routine"
            ]
        }

    def generate_product_explanation(
        self, 
        product_data: Dict[str, Any], 
        user_skin_type: str
    ) -> str:
        """
        Generate user-friendly product explanations
        """
        try:
            prompt = f"""
            Explain this skincare product for someone with {user_skin_type} skin:
            
            Product: {product_data.get('name', 'Unknown Product')}
            Brand: {product_data.get('brand', 'Unknown Brand')}
            Category: {product_data.get('category', 'Unknown Category')}
            Key Ingredients: {', '.join([ing.get('name', '') for ing in product_data.get('ingredients', [])])}
            
            Provide a friendly, easy-to-understand explanation focusing on:
            1. What this product does
            2. How it would work for their skin type
            3. When to use it in their routine
            4. Any tips for best results
            
            Keep it conversational and helpful, max 150 words.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a friendly skincare expert who explains products in simple, encouraging terms."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Product explanation generation failed: {e}")
            return f"This {product_data.get('category', 'product')} from {product_data.get('brand', 'this brand')} can be a great addition to your {user_skin_type} skin routine. Check the ingredients to see if they match your skin goals!"
    
    def generate_completion(
        self,
        prompt: str,
        system_message: str = "You are a helpful assistant.",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate a general completion for any prompt
        """
        try:
            # Build the request
            request_params = {
                "model": "gpt-4-turbo-preview",  # Using stable model as per CLAUDE.md
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # Add response format if specified (for JSON responses)
            if response_format:
                request_params["response_format"] = response_format
            
            # Track prompt tokens (estimate)
            prompt_tokens = len((system_message + prompt).split()) * 1.3
            ai_service_tokens.labels(service="openai", type="prompt").inc(int(prompt_tokens))
            
            response = self.client.chat.completions.create(**request_params)
            
            # Track completion tokens
            if hasattr(response, 'usage'):
                ai_service_tokens.labels(service="openai", type="completion").inc(
                    response.usage.completion_tokens
                )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI completion generation failed: {e}")
            raise
    
    def generate_progress_summary(
        self,
        baseline_scores: Dict[str, float],
        latest_scores: Dict[str, float],
        improvement_scores: Dict[str, float]
    ) -> str:
        """
        Generate progress summary for comparison
        """
        try:
            overall_improvement = sum(improvement_scores.values()) / len(improvement_scores) if improvement_scores else 0
            
            if overall_improvement > 0:
                return f"Great progress! Your skin has shown an average improvement of {overall_improvement:.1f} points. Keep up the excellent work!"
            elif overall_improvement < 0:
                return "Your skin may be going through a transition period. This is normal! Stay consistent with your routine."
            else:
                return "Your skin is maintaining its condition well. Consistency is key!"
        except:
            return "Continue tracking your progress for personalized insights!"
    
    @track_ai_service("openai", "generate_learning_article")
    def generate_learning_article(
        self,
        topic: str,
        category: str,
        difficulty: str = "Beginner",
        target_audience: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate educational skincare article using OpenAI
        
        Args:
            topic: The main topic of the article
            category: Category (Basics, Ingredients, Techniques, Troubleshooting)
            difficulty: Difficulty level (Beginner, Intermediate, Advanced)
            target_audience: Optional user profile data for personalization
        
        Returns:
            Dict containing article data
        """
        try:
            # Build the prompt for article generation
            system_prompt = """
            You are SkinSense AI's educational content creator, specializing in evidence-based skincare education.
            Your role is to create engaging, informative, and scientifically accurate skincare articles.
            
            Guidelines:
            1. Use clear, accessible language appropriate for the difficulty level
            2. Include actionable tips and practical advice
            3. Base recommendations on scientific evidence
            4. Avoid medical claims - focus on beauty and wellness
            5. Be inclusive and consider diverse skin types and concerns
            6. Keep content positive and encouraging
            7. Include specific examples and real-world applications
            
            Structure your response as JSON with these fields:
            - title: Engaging article title
            - subtitle: Brief description (1 sentence)
            - content: Main article content with HTML formatting (use <p>, <h3>, <ul>, <li> tags)
            - key_takeaways: List of 3-5 main points
            - pro_tips: 2-3 expert tips
            - related_topics: 3-4 related topics for further learning
            - estimated_reading_time: Reading time in minutes
            - difficulty_level: Beginner/Intermediate/Advanced
            - tags: List of relevant tags
            """
            
            user_prompt = self._build_article_prompt(topic, category, difficulty, target_audience)
            
            # Track prompt tokens
            prompt_tokens = len(user_prompt.split()) * 1.3
            ai_service_tokens.labels(service="openai", type="prompt").inc(int(prompt_tokens))
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            # Track completion tokens
            if hasattr(response, 'usage'):
                ai_service_tokens.labels(service="openai", type="completion").inc(
                    response.usage.completion_tokens
                )
            
            article_text = response.choices[0].message.content
            article_data = json.loads(article_text)
            
            # Add metadata
            article_data['category'] = category
            article_data['generated_at'] = None  # Will be set by the service layer
            article_data['topic'] = topic
            
            return self._validate_article_response(article_data)
            
        except Exception as e:
            logger.error(f"Article generation failed: {e}")
            return self._get_fallback_article(topic, category, difficulty)
    
    def _build_article_prompt(
        self,
        topic: str,
        category: str,
        difficulty: str,
        target_audience: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build prompt for article generation
        """
        prompt_parts = []
        
        prompt_parts.append(f"Create an educational skincare article on the following topic:")
        prompt_parts.append(f"\nTOPIC: {topic}")
        prompt_parts.append(f"CATEGORY: {category}")
        prompt_parts.append(f"DIFFICULTY LEVEL: {difficulty}")
        
        if target_audience:
            prompt_parts.append("\nTARGET AUDIENCE PROFILE:")
            if 'age_range' in target_audience:
                prompt_parts.append(f"- Age Range: {target_audience['age_range']}")
            if 'skin_type' in target_audience:
                prompt_parts.append(f"- Skin Type: {target_audience['skin_type']}")
            if 'concerns' in target_audience:
                prompt_parts.append(f"- Main Concerns: {', '.join(target_audience['concerns'])}")
        
        prompt_parts.append("\nPlease create an engaging, informative article that:")
        prompt_parts.append("- Explains concepts clearly for the specified difficulty level")
        prompt_parts.append("- Includes practical, actionable advice")
        prompt_parts.append("- Uses real-world examples")
        prompt_parts.append("- Maintains a positive, encouraging tone")
        prompt_parts.append("- Is scientifically accurate but accessible")
        
        return "\n".join(prompt_parts)
    
    def _validate_article_response(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean article response
        """
        required_fields = [
            "title", "subtitle", "content", "key_takeaways", 
            "pro_tips", "related_topics", "estimated_reading_time",
            "difficulty_level", "tags"
        ]
        
        for field in required_fields:
            if field not in article_data:
                article_data[field] = self._get_article_default_value(field)
        
        # Ensure lists are lists
        list_fields = ["key_takeaways", "pro_tips", "related_topics", "tags"]
        for field in list_fields:
            if not isinstance(article_data[field], list):
                article_data[field] = [article_data[field]] if article_data[field] else []
        
        # Ensure reading time is an integer
        try:
            article_data["estimated_reading_time"] = int(article_data["estimated_reading_time"])
        except:
            article_data["estimated_reading_time"] = 5
        
        return article_data
    
    def _get_article_default_value(self, field: str) -> Any:
        """
        Get default values for missing article fields
        """
        defaults = {
            "title": "Skincare Essentials",
            "subtitle": "Everything you need to know about skincare basics",
            "content": "<p>This article is being generated. Please check back soon!</p>",
            "key_takeaways": ["Consistency is key", "Start simple", "Listen to your skin"],
            "pro_tips": ["Patch test new products", "Give products time to work"],
            "related_topics": ["Skin types", "Product ingredients", "Routine building"],
            "estimated_reading_time": 5,
            "difficulty_level": "Beginner",
            "tags": ["skincare", "basics", "education"]
        }
        return defaults.get(field, "")
    
    def _get_fallback_article(self, topic: str, category: str, difficulty: str) -> Dict[str, Any]:
        """
        Fallback article when generation fails
        """
        return {
            "title": f"Understanding {topic}",
            "subtitle": f"A {difficulty.lower()} guide to {topic.lower()} in skincare",
            "content": f"""
            <p>Welcome to our guide on {topic}! This article covers essential information 
            for anyone interested in improving their skincare knowledge.</p>
            
            <h3>What You'll Learn</h3>
            <p>In this article, we'll explore the fundamentals of {topic.lower()} and how 
            it relates to your skincare journey.</p>
            
            <h3>Key Concepts</h3>
            <ul>
                <li>Understanding the basics of {topic.lower()}</li>
                <li>How to apply this knowledge to your routine</li>
                <li>Common misconceptions and myths</li>
                <li>Expert recommendations and tips</li>
            </ul>
            
            <h3>Getting Started</h3>
            <p>The best way to begin is by understanding your skin type and specific needs. 
            Every skincare journey is unique!</p>
            """,
            "key_takeaways": [
                f"Understanding {topic.lower()} is essential for effective skincare",
                "Start with the basics and build gradually",
                "Consistency and patience are key to seeing results",
                "Always patch test new products or techniques"
            ],
            "pro_tips": [
                "Keep a skincare journal to track what works",
                "Don't introduce too many new things at once"
            ],
            "related_topics": [
                "Skin Types 101",
                "Building a Basic Routine",
                "Ingredient Spotlight"
            ],
            "estimated_reading_time": 5,
            "difficulty_level": difficulty,
            "tags": [category.lower(), "education", "skincare"],
            "category": category,
            "topic": topic
        }
    
    def generate_multiple_articles(
        self,
        topics: List[Dict[str, str]],
        target_audience: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple articles in batch
        
        Args:
            topics: List of dicts with 'topic', 'category', and 'difficulty'
            target_audience: Optional user profile for personalization
            
        Returns:
            List of generated articles
        """
        articles = []
        
        for topic_data in topics:
            try:
                article = self.generate_learning_article(
                    topic=topic_data['topic'],
                    category=topic_data['category'],
                    difficulty=topic_data.get('difficulty', 'Beginner'),
                    target_audience=target_audience
                )
                articles.append(article)
                
                # Add a small delay to avoid rate limiting
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to generate article for {topic_data['topic']}: {e}")
                # Add fallback article
                articles.append(
                    self._get_fallback_article(
                        topic_data['topic'],
                        topic_data['category'],
                        topic_data.get('difficulty', 'Beginner')
                    )
                )
        
        return articles

# Global instance
openai_service = OpenAIService()