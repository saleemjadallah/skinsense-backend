import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo.database import Database
import numpy as np

from app.models.user import UserModel
from app.models.skin_analysis import SkinAnalysisModel, ORBOMetrics, ComparisonMetadata

logger = logging.getLogger(__name__)

class ProgressService:
    """Service for tracking and analyzing skin progress over time"""
    
    # Metric display names and descriptions
    METRIC_INFO = {
        "overall_skin_health_score": {
            "name": "Overall Health",
            "description": "Your skin's overall health score",
            "unit": "",
            "improvement_threshold": 3.0
        },
        "hydration": {
            "name": "Hydration",
            "description": "Skin moisture levels",
            "unit": "%",
            "improvement_threshold": 5.0
        },
        "smoothness": {
            "name": "Smoothness",
            "description": "Skin texture quality",
            "unit": "%",
            "improvement_threshold": 4.0
        },
        "radiance": {
            "name": "Radiance",
            "description": "Natural glow and brightness",
            "unit": "%",
            "improvement_threshold": 4.0
        },
        "dark_spots": {
            "name": "Dark Spots",
            "description": "Pigmentation uniformity",
            "unit": "%",
            "improvement_threshold": 5.0
        },
        "firmness": {
            "name": "Firmness",
            "description": "Skin elasticity",
            "unit": "%",
            "improvement_threshold": 3.0
        },
        "fine_lines_wrinkles": {
            "name": "Fine Lines",
            "description": "Aging signs",
            "unit": "%",
            "improvement_threshold": 3.0
        },
        "acne": {
            "name": "Acne",
            "description": "Blemish levels",
            "unit": "%",
            "improvement_threshold": 5.0
        },
        "dark_circles": {
            "name": "Dark Circles",
            "description": "Under-eye area",
            "unit": "%",
            "improvement_threshold": 5.0
        },
        "redness": {
            "name": "Redness",
            "description": "Irritation levels",
            "unit": "%",
            "improvement_threshold": 5.0
        }
    }
    
    def __init__(self):
        pass
    
    def calculate_metric_changes(
        self,
        current_analysis: Dict[str, Any],
        previous_analysis: Dict[str, Any]
    ) -> ComparisonMetadata:
        """Calculate changes between two analyses"""
        
        # Extract metrics from analyses
        current_metrics = self._extract_metrics(current_analysis)
        previous_metrics = self._extract_metrics(previous_analysis)
        
        improvements = {}
        declines = {}
        
        # Calculate changes for each metric
        for metric_key, current_value in current_metrics.items():
            if metric_key in previous_metrics:
                previous_value = previous_metrics[metric_key]
                if previous_value > 0:  # Avoid division by zero
                    change_percentage = ((current_value - previous_value) / previous_value) * 100
                    
                    # Determine if it's an improvement or decline
                    threshold = self.METRIC_INFO.get(metric_key, {}).get("improvement_threshold", 5.0)
                    
                    if change_percentage >= threshold:
                        improvements[metric_key] = round(change_percentage, 1)
                    elif change_percentage <= -threshold:
                        declines[metric_key] = round(abs(change_percentage), 1)
        
        # Calculate days between analyses
        current_date = current_analysis.get("created_at", datetime.utcnow())
        previous_date = previous_analysis.get("created_at", datetime.utcnow())
        days_since = (current_date - previous_date).days
        
        # Calculate overall improvement
        all_changes = list(improvements.values()) + [-d for d in declines.values()]
        overall_improvement = np.mean(all_changes) if all_changes else 0.0
        
        return ComparisonMetadata(
            previous_analysis_id=ObjectId(previous_analysis["_id"]),
            improvements=improvements,
            declines=declines,
            days_since_last_analysis=days_since,
            overall_improvement=round(overall_improvement, 1)
        )
    
    def get_trend_data(
        self,
        user_id: ObjectId,
        db: Database,
        metric_name: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get trend data for a specific metric over a time period"""

        start_date = datetime.utcnow() - timedelta(days=period_days)

        # Debug logging
        logger.info(f"[get_trend_data] Fetching for user_id: {user_id} (type: {type(user_id)}), metric: {metric_name}")

        # Fetch analyses within the period - check both ObjectId and string formats
        analyses = list(db.skin_analyses.find({
            "user_id": {"$in": [user_id, str(user_id)]},
            "status": {"$in": ["completed", "awaiting_ai"]},
            "created_at": {"$gte": start_date}
        }).sort("created_at", 1))

        logger.info(f"[get_trend_data] Found {len(analyses)} analyses for user")
        
        if not analyses:
            return {
                "metric": metric_name,
                "period_days": period_days,
                "data_points": [],
                "trend": "no_data",
                "average_value": 0,
                "improvement": 0
            }
        
        # Extract data points
        data_points = []
        for i, analysis in enumerate(analyses):
            metrics = self._extract_metrics(analysis)
            if i == 0:  # Log first analysis details for debugging
                logger.info(f"[get_trend_data] First analysis metrics extracted: {list(metrics.keys())}")
                logger.info(f"[get_trend_data] {metric_name} value: {metrics.get(metric_name, 'NOT FOUND')}")
            if metric_name in metrics:
                data_points.append({
                    "date": analysis["created_at"].isoformat(),
                    "value": metrics[metric_name],
                    "analysis_id": str(analysis["_id"])
                })
        
        if not data_points:
            return {
                "metric": metric_name,
                "period_days": period_days,
                "data_points": [],
                "trend": "no_data",
                "average_value": 0,
                "improvement": 0
            }
        
        # Calculate trend
        values = [dp["value"] for dp in data_points]
        trend = self._calculate_trend(values)
        
        # Calculate improvement
        improvement = 0
        if len(values) >= 2:
            improvement = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0
        
        result = {
            "metric": metric_name,
            "metric_info": self.METRIC_INFO.get(metric_name, {}),
            "period_days": period_days,
            "data_points": data_points,
            "trend": trend,
            "average_value": round(np.mean(values), 1),
            "improvement": round(improvement, 1),
            "min_value": round(min(values), 1),
            "max_value": round(max(values), 1),
            "latest_value": round(values[-1], 1) if values else 0
        }

        logger.info(f"[get_trend_data] Returning result with latest_value: {result['latest_value']}, data_points count: {len(data_points)}")

        return result
    
    def get_metric_history(
        self,
        user_id: ObjectId,
        db: Database,
        metric_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get historical values for a specific metric"""
        
        analyses = list(db.skin_analyses.find({
            "user_id": user_id,
            "status": {"$in": ["completed", "awaiting_ai"]}
        }).sort("created_at", -1).limit(limit))
        
        history = []
        for analysis in analyses:
            metrics = self._extract_metrics(analysis)
            if metric_name in metrics:
                history.append({
                    "analysis_id": str(analysis["_id"]),
                    "date": analysis["created_at"].isoformat(),
                    "value": metrics[metric_name],
                    "image_url": analysis.get("thumbnail_url", analysis.get("image_url"))
                })
        
        return history
    
    def generate_progress_summary(
        self,
        user_id: ObjectId,
        db: Database,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Generate comprehensive progress summary with AI insights"""
        
        # Get all analyses in period - check both user_id formats
        start_date = datetime.utcnow() - timedelta(days=period_days)
        analyses = list(db.skin_analyses.find({
            "user_id": {"$in": [user_id, str(user_id)]},
            "status": {"$in": ["completed", "awaiting_ai"]},
            "created_at": {"$gte": start_date}
        }).sort("created_at", 1))
        
        if len(analyses) < 2:
            return {
                "has_progress": False,
                "message": "Need at least 2 analyses to show progress",
                "analyses_count": len(analyses),
                "period_days": period_days
            }
        
        # Get latest and oldest analysis
        latest_analysis = analyses[-1]
        oldest_analysis = analyses[0]
        
        # Calculate overall progress
        latest_metrics = self._extract_metrics(latest_analysis)
        oldest_metrics = self._extract_metrics(oldest_analysis)
        
        # Identify top improvements and concerns
        improvements = []
        concerns = []
        
        for metric_key in latest_metrics:
            if metric_key in oldest_metrics:
                old_value = oldest_metrics[metric_key]
                new_value = latest_metrics[metric_key]
                if old_value > 0:
                    change = ((new_value - old_value) / old_value) * 100
                    
                    metric_data = {
                        "metric": metric_key,
                        "name": self.METRIC_INFO.get(metric_key, {}).get("name", metric_key),
                        "old_value": round(old_value, 1),
                        "new_value": round(new_value, 1),
                        "change": round(change, 1)
                    }
                    
                    if change >= 5:
                        improvements.append(metric_data)
                    elif change <= -5:
                        concerns.append(metric_data)
        
        # Sort by magnitude of change
        improvements.sort(key=lambda x: x["change"], reverse=True)
        concerns.sort(key=lambda x: abs(x["change"]), reverse=True)
        
        # Calculate consistency score
        consistency_score = self._calculate_consistency_score(analyses)
        
        return {
            "has_progress": True,
            "period_days": period_days,
            "analyses_count": len(analyses),
            "start_date": oldest_analysis["created_at"].isoformat(),
            "end_date": latest_analysis["created_at"].isoformat(),
            "top_improvements": improvements[:3],
            "areas_of_concern": concerns[:3],
            "consistency_score": consistency_score,
            "overall_trend": self._determine_overall_trend(improvements, concerns),
            "next_steps": self._generate_next_steps(improvements, concerns)
        }
    
    def _extract_metrics(self, analysis: Dict[str, Any]) -> Dict[str, float]:
        """Extract ORBO metrics from analysis data"""
        metrics = {}
        analysis_id = analysis.get('_id', 'unknown')

        # Try new ORBO structure first (proper nesting)
        if "orbo_response" in analysis and analysis["orbo_response"]:
            orbo_resp = analysis["orbo_response"]

            # Log structure for debugging
            if isinstance(orbo_resp, dict):
                has_metrics_key = "metrics" in orbo_resp
                logger.debug(f"[_extract_metrics] Analysis {analysis_id}: orbo_response has 'metrics' key: {has_metrics_key}")
                if has_metrics_key:
                    logger.debug(f"[_extract_metrics] Keys in metrics: {list(orbo_resp['metrics'].keys()) if isinstance(orbo_resp['metrics'], dict) else 'NOT A DICT'}")

            # Check if metrics are properly nested under 'metrics' key
            if isinstance(orbo_resp, dict) and "metrics" in orbo_resp:
                orbo_metrics = orbo_resp["metrics"]
                for key in self.METRIC_INFO.keys():
                    if key in orbo_metrics:
                        metrics[key] = float(orbo_metrics[key])

            # Fallback: Check if metrics are at the top level of orbo_response (wrong structure)
            elif isinstance(orbo_resp, dict):
                for key in self.METRIC_INFO.keys():
                    if key in orbo_resp:
                        metrics[key] = float(orbo_resp[key])
                if metrics:  # If we found metrics at wrong level
                    logger.warning(f"Found metrics at wrong level in analysis {analysis_id}")

        # Fallback to analysis_data
        elif "analysis_data" in analysis:
            for key in self.METRIC_INFO.keys():
                if key in analysis["analysis_data"]:
                    metrics[key] = float(analysis["analysis_data"][key])

        return metrics
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from a series of values"""
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple linear regression
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        # Determine trend based on slope
        if slope > 0.5:
            return "improving"
        elif slope < -0.5:
            return "declining"
        else:
            return "stable"
    
    def _calculate_consistency_score(self, analyses: List[Dict[str, Any]]) -> float:
        """Calculate how consistently user is tracking progress"""
        if len(analyses) < 2:
            return 0.0
        
        # Calculate average days between analyses
        intervals = []
        for i in range(1, len(analyses)):
            days = (analyses[i]["created_at"] - analyses[i-1]["created_at"]).days
            intervals.append(days)
        
        avg_interval = np.mean(intervals)
        
        # Score based on frequency (ideal is 7-14 days)
        if 7 <= avg_interval <= 14:
            return 100.0
        elif avg_interval < 7:
            return 80.0  # Too frequent
        elif avg_interval <= 21:
            return 70.0
        elif avg_interval <= 30:
            return 50.0
        else:
            return 30.0  # Too infrequent
    
    def _determine_overall_trend(
        self,
        improvements: List[Dict[str, Any]],
        concerns: List[Dict[str, Any]]
    ) -> str:
        """Determine overall skin health trend"""
        if not improvements and not concerns:
            return "stable"
        
        improvement_score = sum(i["change"] for i in improvements)
        concern_score = sum(abs(c["change"]) for c in concerns)
        
        if improvement_score > concern_score * 1.5:
            return "significant_improvement"
        elif improvement_score > concern_score:
            return "moderate_improvement"
        elif concern_score > improvement_score * 1.5:
            return "needs_attention"
        else:
            return "mixed_results"
    
    def _generate_next_steps(
        self,
        improvements: List[Dict[str, Any]],
        concerns: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable next steps based on progress"""
        next_steps = []
        
        # Celebrate improvements
        if improvements:
            top_improvement = improvements[0]["name"]
            next_steps.append(f"Continue your routine that improved {top_improvement}")
        
        # Address concerns
        if concerns:
            for concern in concerns[:2]:
                metric_name = concern["name"]
                if metric_name == "Hydration":
                    next_steps.append("Increase water intake and use hydrating products")
                elif metric_name == "Acne":
                    next_steps.append("Review your cleansing routine and avoid pore-clogging products")
                elif metric_name == "Dark Spots":
                    next_steps.append("Add vitamin C serum and ensure daily SPF use")
                elif metric_name == "Fine Lines":
                    next_steps.append("Consider adding retinol to your evening routine")
                elif metric_name == "Redness":
                    next_steps.append("Use gentle, fragrance-free products and avoid hot water")
        
        # General advice
        if len(next_steps) < 3:
            next_steps.append("Maintain consistent skincare routine")
            next_steps.append("Take progress photos weekly for better tracking")
        
        return next_steps[:3]

# Global service instance
progress_service = ProgressService()