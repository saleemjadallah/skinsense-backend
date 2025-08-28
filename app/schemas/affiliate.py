"""
Pydantic schemas for affiliate tracking
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId


class AffiliateClickRequest(BaseModel):
    """Request schema for tracking affiliate clicks"""
    product_id: str
    retailer: str
    product_name: Optional[str] = None
    product_price: Optional[float] = None
    skin_analysis_id: Optional[str] = None
    source: Optional[str] = Field(default="app", description="Where the click originated")


class ConversionWebhook(BaseModel):
    """Generic webhook schema for conversion tracking"""
    tracking_id: Optional[str] = None
    order_value: float
    order_id: Optional[str] = None
    commission_amount: Optional[float] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class RetailerAnalytics(BaseModel):
    """Analytics data for a specific retailer"""
    retailer: str
    total_clicks: int
    unique_users: int
    conversions: int
    conversion_rate: float
    total_revenue: float
    total_commission: float


class AffiliateAnalyticsResponse(BaseModel):
    """Response schema for affiliate analytics"""
    total_clicks: int
    total_conversions: int
    total_revenue: float
    total_commission: float
    overall_conversion_rate: float
    by_retailer: List[RetailerAnalytics]
    date_range: Optional[Dict[str, datetime]] = None


class AffiliateProductResponse(BaseModel):
    """Product with affiliate links"""
    id: str
    name: str
    brand: str
    category: str
    current_price: float
    original_price: Optional[float] = None
    
    # Affiliate data
    affiliate_link: str
    tracking_link: str
    tracking_id: str
    estimated_commission: Optional[Dict[str, float]] = None
    
    # Product details
    retailer: str
    match_score: Optional[float] = Field(None, description="Compatibility score 0-100")
    key_ingredients: Optional[List[str]] = None
    availability: Optional[Dict[str, List[str]]] = None
    
    # Metadata
    source: str = Field(default="perplexity_search")
    generated_at: datetime = Field(default_factory=datetime.utcnow)