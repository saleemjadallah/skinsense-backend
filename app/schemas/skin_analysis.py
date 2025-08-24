from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List
from datetime import datetime

class SkinAnalysisCreate(BaseModel):
    image_data: str  # Base64 encoded image
    is_baseline: bool = False
    tags: List[str] = []
    
    @validator('image_data')
    def validate_image_data(cls, v):
        # Basic validation for base64 image
        if not v.startswith('data:image/'):
            raise ValueError('Invalid image format')
        return v

class SkinAnalysisResponse(BaseModel):
    id: str
    user_id: str
    image_url: str
    thumbnail_url: Optional[str]
    analysis_complete: bool
    created_at: datetime
    is_baseline: bool

class SkinAnalysisDetail(BaseModel):
    id: str
    user_id: str
    image_url: str
    thumbnail_url: Optional[str]
    analysis_data: Dict[str, Any]
    ai_feedback: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime
    is_baseline: bool
    tags: List[str]

class ProgressComparisonRequest(BaseModel):
    current_analysis_id: str
    previous_analysis_id: str

class ProgressComparisonResponse(BaseModel):
    baseline_analysis: Optional[SkinAnalysisDetail]
    latest_analysis: Optional[SkinAnalysisDetail]
    improvement_scores: Dict[str, float]
    progress_summary: str
    recommendations: List[str]