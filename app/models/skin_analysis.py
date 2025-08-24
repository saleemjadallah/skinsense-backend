from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId
from .user import PyObjectId

class ORBOMetrics(BaseModel):
    """ORBO AI skin analysis metrics (0-100 scale)"""
    overall_skin_health_score: float = 0.0
    hydration: float = 0.0
    smoothness: float = 0.0
    radiance: float = 0.0
    dark_spots: float = 0.0
    firmness: float = 0.0
    fine_lines_wrinkles: float = 0.0
    acne: float = 0.0
    dark_circles: float = 0.0
    redness: float = 0.0

class ORBOResponse(BaseModel):
    """Complete ORBO AI response structure"""
    metrics: ORBOMetrics = Field(default_factory=ORBOMetrics)
    skin_type: Optional[str] = None  # "oily", "dry", "combination", etc.
    concerns: List[str] = []  # ["acne", "wrinkles", "dark_spots", etc.]
    confidence: float = 0.0
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_response: Dict[str, Any] = {}  # Store complete API response for debugging

class HautAIResponse(BaseModel):
    """Legacy Haut.AI response - kept for compatibility"""
    skin_type: Optional[str] = None
    concerns: List[str] = []
    scores: Dict[str, float] = {}  # hydration, texture, tone_evenness, etc.
    confidence: float = 0.0
    raw_response: Dict[str, Any] = {}

class AIFeedback(BaseModel):
    summary: str
    recommendations: List[str] = []
    routine_suggestions: str
    progress_notes: Optional[str] = None
    encouragement: str
    next_steps: List[str] = []

class ImageMetadata(BaseModel):
    lighting_conditions: Optional[str] = None  # "natural", "artificial", "mixed"
    image_quality_score: float = 0.0
    face_detected: bool = False
    image_resolution: Optional[str] = None
    file_size_mb: float = 0.0
    analysis_version: str = "v1.0"

class ComparisonMetadata(BaseModel):
    """Metadata for tracking improvements between analyses"""
    previous_analysis_id: Optional[PyObjectId] = None
    improvements: Dict[str, float] = {}  # metric_name: percentage_change
    declines: Dict[str, float] = {}  # metric_name: percentage_change
    days_since_last_analysis: Optional[int] = None
    overall_improvement: float = 0.0  # Average improvement across all metrics

class SkinAnalysisModel(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    image_url: str
    thumbnail_url: Optional[str] = None
    
    # Analysis results - flexible to support both current and future structure
    analysis_data: Dict[str, Any] = {}  # Backward compatibility
    orbo_response: Optional[ORBOResponse] = None  # New ORBO structure
    haut_ai_response: Optional[HautAIResponse] = None  # Legacy support
    
    # AI insights and feedback
    ai_feedback: Optional[AIFeedback] = None
    
    # Metadata
    metadata: ImageMetadata = Field(default_factory=ImageMetadata)
    comparison_metadata: Optional[ComparisonMetadata] = None
    
    # Timestamps and flags
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    analysis_completed_at: Optional[datetime] = None
    
    # User preferences
    is_baseline: bool = False
    is_public: bool = False  # For community sharing
    tags: List[str] = []
    
    # Analysis status
    status: str = "pending"  # pending, processing, completed, failed
    error_message: Optional[str] = None