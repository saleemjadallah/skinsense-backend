from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime

class ProductResponse(BaseModel):
    id: str
    name: str
    brand: str
    category: str
    image_url: Optional[str]
    community_rating: float
    total_reviews: int

class ProductDetail(BaseModel):
    id: str
    name: str
    brand: str
    category: str
    description: Optional[str]
    ingredients: List[Dict[str, Any]]
    barcode: Optional[str]
    image_url: Optional[str]
    price_range: Optional[str]
    where_to_buy: List[str]
    community_rating: float
    total_reviews: int
    skin_type_compatibility: Dict[str, float]
    created_at: datetime
    is_verified: bool

class ProductScanRequest(BaseModel):
    image_data: str  # Base64 encoded barcode image

class ProductReviewCreate(BaseModel):
    rating: float  # 1-5 stars
    review_text: Optional[str] = None
    skin_type: Optional[str] = None
    would_recommend: bool = True

class ProductMatchResponse(BaseModel):
    barcode: str
    product_found: bool
    product: Optional[ProductDetail] = None
    compatibility_score: Optional[float] = None
    match_reasons: Optional[List[str]] = None
    message: Optional[str] = None