from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from bson import ObjectId
from .user import PyObjectId

class Ingredient(BaseModel):
    name: str
    purpose: str  # "hydration", "barrier_repair", "anti_aging"
    concern_match: List[str] = []  # Which skin concerns it helps
    concentration: Optional[str] = None
    safety_rating: Optional[float] = None

class SkinCompatibility(BaseModel):
    oily: float = 0.0
    dry: float = 0.0
    combination: float = 0.0
    sensitive: float = 0.0
    overall_score: float = 0.0

class ProductModel(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    name: str
    brand: str
    category: str  # "cleanser", "moisturizer", "serum", etc.
    description: Optional[str] = None
    ingredients: List[Ingredient] = []
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    price_range: Optional[str] = None
    where_to_buy: List[str] = []
    community_rating: float = 0.0
    total_reviews: int = 0
    skin_type_compatibility: SkinCompatibility = Field(default_factory=SkinCompatibility)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_verified: bool = False

class ProductReview(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str, datetime: lambda v: v.isoformat()}
    }
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    product_id: PyObjectId
    rating: float  # 1-5 stars
    review_text: Optional[str] = None
    skin_type: Optional[str] = None
    would_recommend: bool = True
    verified_purchase: bool = False
    helpful_votes: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)