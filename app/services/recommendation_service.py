"""
Unified AI Recommendation Service
Orchestrates Haut.ai, OpenAI, and Perplexity services for complete analysis
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo.database import Database
from bson import ObjectId
import logging

from app.models.user import UserModel
from app.models.skin_analysis import SkinAnalysisModel
# from app.services.haut_ai_service import haut_ai_service  # Using ORBO instead
from app.services.openai_service import openai_service
from app.services.perplexity_service import perplexity_service
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

class UnifiedRecommendationService:
    """
    Orchestrates all AI services to provide comprehensive skin analysis and recommendations
    """
    
    def __init__(self):
        # self.haut_ai = haut_ai_service  # Using ORBO instead
        self.openai = openai_service
        self.perplexity = perplexity_service
    
    async def complete_ai_pipeline(
        self,
        user: UserModel,
        image_url: str,
        user_location: Dict[str, str],
        db: Database,
        analysis_id: Optional[ObjectId] = None
    ) -> Dict[str, Any]:
        """
        Execute complete AI analysis pipeline:
        1. ORBO skin analysis (handled elsewhere)
        2. OpenAI feedback generation
        3. Perplexity product recommendations
        """
        try:
            # Step 1: Skin Analysis with ORBO (this should be provided as parameter or fetched from DB)
            logger.info(f"Starting complete AI pipeline for user {user.id}")
            # skin_analysis = await self.haut_ai.analyze_skin(image_url)  # REMOVED - using ORBO instead
            
            # For now, fetch the latest analysis from database or use provided analysis_id
            if analysis_id:
                analysis_doc = self._get_analysis_by_id(analysis_id, db)
                skin_analysis = analysis_doc.get("orbo_response", {}) if analysis_doc else {}
            else:
                latest_analysis = self._get_latest_analysis(user.id, db)
                skin_analysis = latest_analysis.get("orbo_response", {}) if latest_analysis else {}
            
            if not skin_analysis:
                logger.error(f"No skin analysis data found for user {user.id}")
                return self._create_fallback_response(user, Exception("No analysis data available"))
            
            # Step 2: Generate AI feedback concurrently with product search
            ai_feedback_task = asyncio.create_task(
                self.openai.generate_skin_feedback(skin_analysis, user)
            )
            
            # Get recommendation limit based on subscription
            recommendation_limit = SubscriptionService.get_recommendation_limit(user)
            
            product_recommendations_task = asyncio.create_task(
                self.perplexity.get_personalized_recommendations(
                    user=user,
                    skin_analysis=skin_analysis,
                    user_location=user_location,
                    db=db,
                    limit=recommendation_limit
                )
            )
            
            # Wait for both tasks to complete
            ai_feedback, product_recommendations = await asyncio.gather(
                ai_feedback_task,
                product_recommendations_task
            )
            
            # Step 3: Get previous analyses for progress tracking
            previous_analyses = self._get_recent_analyses(user.id, db, limit=3)
            
            # Step 4: Generate progress insights if we have history
            progress_insights = None
            if previous_analyses:
                progress_insights = await self.openai.generate_progress_comparison(
                    current_analysis=skin_analysis,
                    previous_analyses=previous_analyses,
                    user=user
                )
            
            # Step 5: Compile complete results
            is_premium = SubscriptionService.is_premium(user)
            complete_results = {
                "analysis_id": str(analysis_id) if analysis_id else None,
                "skin_analysis": skin_analysis,
                "ai_feedback": ai_feedback,
                "progress_insights": progress_insights,
                "product_recommendations": product_recommendations,
                "subscription_tier": "premium" if is_premium else "free",
                "recommendation_limit": recommendation_limit,
                "analysis_summary": self._generate_analysis_summary(skin_analysis),
                "generated_at": datetime.utcnow().isoformat(),
                "pipeline_version": "2.0"
            }
            
            logger.info(f"Complete AI pipeline successful for user {user.id}")
            return complete_results
            
        except Exception as e:
            logger.error(f"AI pipeline failed: {e}")
            return self._create_fallback_response(user, e)

    async def get_recommendations_for_analysis(
        self,
        analysis_id: str,
        user: UserModel,
        user_location: Dict[str, str],
        db: Database,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Wrapper used by the ORBO SDK endpoint to fetch product recommendations
        for a specific analysis. This normalizes the analysis payload so the
        downstream recommendation service accepts it regardless of storage shape.
        """
        try:
            oid = ObjectId(analysis_id) if not isinstance(analysis_id, ObjectId) else analysis_id
            analysis_doc = db.skin_analyses.find_one({"_id": oid, "user_id": user.id})
            if not analysis_doc:
                logger.warning(f"Analysis {analysis_id} not found for user {user.id}")
                return {
                    "recommendations": [],
                    "routine_suggestions": {},
                    "shopping_list": {},
                    "error": "Analysis not found",
                }

            # Normalize the payload expected by the Perplexity service.
            # If the document already contains `orbo_response`, wrap it under
            # a top-level key so `get_personalized_recommendations` can read it.
            if analysis_doc.get("orbo_response"):
                skin_analysis_payload: Dict[str, Any] = {
                    "orbo_response": analysis_doc["orbo_response"]
                }
            else:
                # Fall back to any legacy `analysis_data` shape
                skin_analysis_payload = analysis_doc.get("analysis_data", {})

            raw = await self.perplexity.get_personalized_recommendations(
                user=user,
                skin_analysis=skin_analysis_payload,
                user_location=user_location,
                db=db,
                limit=limit,
            )

            # Normalize keys expected by API layer
            return {
                **raw,
                "products": raw.get("recommendations", []),
                "routine": raw.get("routine_suggestions", {}),
            }
        except Exception as exc:
            logger.error(f"get_recommendations_for_analysis failed: {exc}")
            return await self._get_fallback_recommendations(user, {})
    
    async def get_quick_recommendations(
        self,
        user: UserModel,
        user_location: Dict[str, str],
        db: Database,
        skin_type_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get quick product recommendations without full skin analysis
        Uses user's profile data or last analysis
        """
        try:
            # Get user's most recent analysis or use profile data
            latest_analysis = self._get_latest_analysis(user.id, db)
            
            if latest_analysis and latest_analysis.get("orbo_response"):
                skin_analysis = latest_analysis["orbo_response"]
            else:
                # Create minimal analysis from user profile
                skin_analysis = {
                    "skin_type": skin_type_override or user.profile.skin_type or "combination",
                    "concerns": user.profile.skin_concerns or ["hydration", "texture"],
                    "scores": {
                        "overall_skin_health": 7.5,
                        "hydration": 7.0,
                        "texture": 7.0,
                        "tone_evenness": 7.5,
                        "clarity": 7.5
                    }
                }
            
            # Get product recommendations
            recommendations_result = await self.perplexity.get_personalized_recommendations(
                user=user,
                skin_analysis=skin_analysis,
                user_location=user_location,
                db=db,
                limit=5
            )
            
            # Flatten the structure - recommendations_result already contains the full structure
            return {
                **recommendations_result,  # Spread all fields from Perplexity response
                "based_on": "latest_analysis" if latest_analysis else "user_profile",
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Quick recommendations failed: {e}")
            return {
                "recommendations": [],
                "error": "Unable to generate recommendations",
                "generated_at": datetime.utcnow().isoformat()
            }
    
    async def analyze_product_compatibility(
        self,
        user: UserModel,
        product_info: Dict[str, Any],
        db: Database
    ) -> Dict[str, Any]:
        """
        Analyze if a specific product is compatible with user's skin
        """
        try:
            # Get user's latest skin analysis
            latest_analysis = self._get_latest_analysis(user.id, db)
            
            if not latest_analysis:
                return {
                    "compatible": True,
                    "confidence": "low",
                    "reason": "No skin analysis available for personalized assessment"
                }
            
            # Use OpenAI to analyze compatibility
            compatibility_analysis = await self.openai.analyze_product_compatibility(
                product_info=product_info,
                skin_analysis=latest_analysis.get("orbo_response", {}),
                user=user
            )
            
            return compatibility_analysis
            
        except Exception as e:
            logger.error(f"Product compatibility analysis failed: {e}")
            return {
                "compatible": True,
                "confidence": "low", 
                "error": str(e)
            }
    
    async def generate_routine_plan(
        self,
        user: UserModel,
        products: List[Dict[str, Any]],
        goals: List[str],
        db: Database
    ) -> Dict[str, Any]:
        """
        Generate a personalized skincare routine plan
        """
        try:
            # Get user's skin analysis
            latest_analysis = self._get_latest_analysis(user.id, db)
            
            # Generate routine using OpenAI
            routine_plan = await self.openai.generate_routine_plan(
                products=products,
                goals=goals,
                skin_analysis=latest_analysis.get("orbo_response", {}) if latest_analysis else {},
                user=user
            )
            
            return routine_plan
            
        except Exception as e:
            logger.error(f"Routine plan generation failed: {e}")
            return self._create_basic_routine(products)
    
    async def get_progress_insights(
        self,
        user: UserModel,
        db: Database,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get detailed progress insights over time
        """
        try:
            # Get analyses from the specified period
            analyses = self._get_analyses_in_period(user.id, db, period_days)
            
            if len(analyses) < 2:
                return {
                    "has_progress": False,
                    "message": "Need at least 2 analyses to show progress",
                    "analyses_count": len(analyses)
                }
            
            # Generate comprehensive progress report
            progress_report = await self.openai.generate_detailed_progress_report(
                analyses=analyses,
                user=user
            )
            
            return progress_report
            
        except Exception as e:
            logger.error(f"Progress insights generation failed: {e}")
            return {
                "has_progress": False,
                "error": str(e)
            }
    
    # Helper methods
    def _get_latest_analysis(
        self,
        user_id: ObjectId,
        db: Database
    ) -> Optional[Dict[str, Any]]:
        """Get user's most recent skin analysis"""
        # Include both completed AND awaiting_ai statuses
        # awaiting_ai means ORBO analysis is done but AI feedback is pending
        return db.skin_analyses.find_one(
            {
                "user_id": {"$in": [user_id, str(user_id)]},
                "$or": [
                    {"status": {"$in": ["completed", "awaiting_ai"]}},
                    {"status": "pending", "orbo_response": {"$exists": True, "$ne": None}}
                ]
            },
            sort=[("created_at", -1)]
        )
    
    def _get_recent_analyses(
        self,
        user_id: ObjectId,
        db: Database,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get user's recent skin analyses"""
        # Include both completed AND awaiting_ai statuses
        cursor = db.skin_analyses.find(
            {
                "user_id": {"$in": [user_id, str(user_id)]},
                "$or": [
                    {"status": {"$in": ["completed", "awaiting_ai"]}},
                    {"status": "pending", "orbo_response": {"$exists": True, "$ne": None}}
                ]
            }
        ).sort("created_at", -1).limit(limit)

        return list(cursor)
    
    def _get_analyses_in_period(
        self,
        user_id: ObjectId,
        db: Database,
        period_days: int
    ) -> List[Dict[str, Any]]:
        """Get analyses within specified period"""
        from datetime import datetime, timedelta

        start_date = datetime.utcnow() - timedelta(days=period_days)

        # Include both completed AND awaiting_ai statuses
        # awaiting_ai means ORBO analysis is done but AI feedback is pending
        cursor = db.skin_analyses.find({
            "user_id": {"$in": [user_id, str(user_id)]},
            "created_at": {"$gte": start_date},
            "$or": [
                {"status": {"$in": ["completed", "awaiting_ai"]}},
                {"status": "pending", "orbo_response": {"$exists": True, "$ne": None}}
            ]
        }).sort("created_at", 1)

        return list(cursor)
    
    def _get_analysis_by_id(
        self,
        analysis_id: ObjectId,
        db: Database
    ) -> Optional[Dict[str, Any]]:
        """Get analysis by ID"""
        return db.skin_analyses.find_one({"_id": analysis_id})
    
    def _generate_analysis_summary(self, skin_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of the skin analysis"""
        scores = skin_analysis.get("scores", {})
        concerns = skin_analysis.get("concerns", [])
        
        # Calculate overall score
        score_values = [v for v in scores.values() if isinstance(v, (int, float))]
        overall_score = sum(score_values) / len(score_values) if score_values else 7.5
        
        # Determine skin condition
        if overall_score >= 8.5:
            condition = "excellent"
        elif overall_score >= 7.5:
            condition = "good"
        elif overall_score >= 6.5:
            condition = "fair"
        else:
            condition = "needs attention"
        
        return {
            "overall_score": round(overall_score, 1),
            "condition": condition,
            "top_concerns": concerns[:3] if concerns else [],
            "strengths": [k for k, v in scores.items() if v >= 8.0],
            "areas_for_improvement": [k for k, v in scores.items() if v < 7.0]
        }
    
    def _create_fallback_response(self, user: UserModel, error: Exception) -> Dict[str, Any]:
        """Create fallback response when pipeline fails"""
        return {
            "error": "Analysis pipeline temporarily unavailable",
            "fallback": True,
            "recommendations": {
                "message": "We're having trouble completing your analysis. Please try again in a few moments.",
                "basic_tips": [
                    "Continue with your regular skincare routine",
                    "Stay hydrated",
                    "Use SPF daily",
                    "Cleanse gently twice daily"
                ]
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _create_basic_routine(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create basic routine structure when AI fails"""
        return {
            "morning_routine": [
                {"step": 1, "action": "Cleanse", "product": next((p for p in products if p.get("category") == "cleanser"), None)},
                {"step": 2, "action": "Treat", "product": next((p for p in products if p.get("category") == "serum"), None)},
                {"step": 3, "action": "Moisturize", "product": next((p for p in products if p.get("category") == "moisturizer"), None)},
                {"step": 4, "action": "Protect", "product": next((p for p in products if p.get("category") == "sunscreen"), None)}
            ],
            "evening_routine": [
                {"step": 1, "action": "Cleanse", "product": next((p for p in products if p.get("category") == "cleanser"), None)},
                {"step": 2, "action": "Treat", "product": next((p for p in products if p.get("category") in ["serum", "treatment"]), None)},
                {"step": 3, "action": "Moisturize", "product": next((p for p in products if p.get("category") == "moisturizer"), None)}
            ],
            "weekly_additions": [
                {"frequency": "2-3x per week", "action": "Exfoliate", "timing": "Evening, after cleansing"},
                {"frequency": "1-2x per week", "action": "Face mask", "timing": "After cleansing, before serums"}
            ]
        }

# Global service instance
recommendation_service = UnifiedRecommendationService()