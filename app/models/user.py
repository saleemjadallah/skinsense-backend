from pydantic import BaseModel, EmailStr, Field, GetJsonSchemaHandler
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue
from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Any
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_plain_validator_function(cls.validate)
    
    @classmethod
    def validate(cls, v: Any, _: Any) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")
    
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema.update(type="string")
        return json_schema

class OnboardingPreferences(BaseModel):
    """Onboarding preferences collected during user setup"""
    gender: Optional[str] = None  # "female", "male", "other", "prefer_not_to_say"
    age_group: Optional[str] = None  # "under_18", "18_24", "25_34", "35_44", "45_54", "55_plus"
    skin_type: Optional[str] = None  # "dry", "oily", "normal", "combination", "sensitive"
    completed_at: Optional[datetime] = None
    is_completed: bool = False

class ProductPreferences(BaseModel):
    """User preferences for product recommendations"""
    budget_range: Optional[str] = None  # "budget", "mid_range", "luxury"
    ingredient_preferences: List[str] = []  # ["retinol", "vitamin_c", "hyaluronic_acid"]
    ingredient_blacklist: List[str] = []  # ["fragrance", "sulfates", "parabens"]
    preferred_brands: List[str] = []
    preferred_categories: List[str] = []  # ["cleanser", "moisturizer", "serum"]

class SkinProfile(BaseModel):
    # Legacy fields (keeping for backward compatibility)
    age_range: Optional[str] = None  # "18-25", "26-35", etc.
    skin_type: Optional[str] = None  # "oily", "dry", "combination", "sensitive"
    skin_concerns: List[str] = []  # ["acne", "hyperpigmentation", "dryness"]
    current_routine: List[str] = []  # Product categories they use
    goals: List[str] = []  # ["clear_skin", "anti_aging", "hydration"]
    avatar_url: Optional[str] = None
    
    # AI-enhanced fields
    ai_detected_skin_type: Optional[str] = None  # AI-refined skin type from analysis
    ai_confidence_score: Optional[float] = None  # Confidence in AI detection
    last_analysis_date: Optional[datetime] = None

class SubscriptionInfo(BaseModel):
    tier: str = "basic"  # "basic", "plus", "pro"
    expires_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    is_active: bool = True

class PrivacySettings(BaseModel):
    blur_face_in_photos: bool = True
    share_anonymous_data: bool = False
    email_notifications: bool = True
    push_notifications: bool = True
    data_retention_days: int = 365

class SocialAuthProvider(BaseModel):
    """Social authentication provider information"""
    provider: str  # "google" or "apple"
    provider_user_id: str  # User ID from the provider
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None  # Profile picture URL
    linked_at: datetime = Field(default_factory=datetime.utcnow)

class UserModel(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {ObjectId: str}
    }
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    email: EmailStr
    username: str
    # Optional human-friendly display name
    name: Optional[str] = None
    password_hash: Optional[str] = None  # Optional for social auth users
    
    # Onboarding data
    onboarding: OnboardingPreferences = Field(default_factory=OnboardingPreferences)
    
    # Enhanced profile
    profile: SkinProfile = Field(default_factory=SkinProfile)
    product_preferences: ProductPreferences = Field(default_factory=ProductPreferences)
    
    # Subscription and settings
    subscription: SubscriptionInfo = Field(default_factory=SubscriptionInfo)
    privacy_settings: PrivacySettings = Field(default_factory=PrivacySettings)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    # Account status
    is_active: bool = True
    is_verified: bool = False
    verification_token: Optional[str] = None
    is_admin: bool = False
    
    # Social auth providers
    social_providers: List[SocialAuthProvider] = []
    

# Helper schemas for API endpoints
class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences from onboarding"""
    gender: Optional[str] = None
    age_group: Optional[str] = None
    skin_type: Optional[str] = None

class UserPreferencesResponse(BaseModel):
    """Response schema for user preferences"""
    gender: Optional[str] = None
    age_group: Optional[str] = None
    skin_type: Optional[str] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None