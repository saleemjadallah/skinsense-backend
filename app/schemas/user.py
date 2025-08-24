from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional, List, Dict
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    # Optional human-friendly name collected at signup
    name: Optional[str] = None
    
    @field_validator('username')
    def username_alphanumeric(cls, v):
        assert v.replace('_', '').isalnum(), 'Username must be alphanumeric'
        assert len(v) >= 3, 'Username must be at least 3 characters'
        return v
    
    @field_validator('password')
    def password_strength(cls, v):
        assert len(v) >= 8, 'Password must be at least 8 characters'
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OnboardingPreferencesResponse(BaseModel):
    """Response schema for onboarding preferences"""
    gender: Optional[str] = None
    age_group: Optional[str] = None
    skin_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    is_completed: bool = False

class ProductPreferencesResponse(BaseModel):
    """Response schema for product preferences"""
    budget_range: Optional[str] = None
    ingredient_preferences: List[str] = []
    ingredient_blacklist: List[str] = []
    preferred_brands: List[str] = []
    preferred_categories: List[str] = []

class SkinProfileResponse(BaseModel):
    """Response schema for skin profile"""
    age_range: Optional[str] = None
    skin_type: Optional[str] = None
    skin_concerns: List[str] = []
    current_routine: List[str] = []
    goals: List[str] = []
    avatar_url: Optional[str] = None
    ai_detected_skin_type: Optional[str] = None
    ai_confidence_score: Optional[float] = None
    last_analysis_date: Optional[datetime] = None

class SubscriptionInfoResponse(BaseModel):
    """Response schema for subscription info"""
    tier: str = "basic"
    expires_at: Optional[datetime] = None
    is_active: bool = True

class PrivacySettingsResponse(BaseModel):
    """Response schema for privacy settings"""
    blur_face_in_photos: bool = True
    share_anonymous_data: bool = False
    email_notifications: bool = True
    push_notifications: bool = True
    data_retention_days: int = 365

class UserResponse(BaseModel):
    """Comprehensive user response including all profile data"""
    id: str
    email: str
    username: str
    name: Optional[str] = None
    onboarding: OnboardingPreferencesResponse
    profile: SkinProfileResponse
    product_preferences: ProductPreferencesResponse
    subscription: SubscriptionInfoResponse
    privacy_settings: PrivacySettingsResponse
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_verified: bool = False

class UserUpdate(BaseModel):
    """Schema for updating user account details"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None

class UserProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    age_range: Optional[str] = None
    skin_type: Optional[str] = None
    skin_concerns: Optional[List[str]] = None
    current_routine: Optional[List[str]] = None
    goals: Optional[List[str]] = None

class OnboardingPreferencesUpdate(BaseModel):
    """Schema for updating onboarding preferences"""
    gender: Optional[str] = None
    age_group: Optional[str] = None
    skin_type: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class AuthResponse(BaseModel):
    """Extended auth response with user data"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    is_new_user: bool = False

class PasswordReset(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class GoogleSignInRequest(BaseModel):
    """Request schema for Google sign-in"""
    id_token: str

class AppleSignInRequest(BaseModel):
    """Request schema for Apple sign-in"""
    identity_token: str
    user_identifier: str
    email: Optional[str] = None
    full_name: Optional[Dict[str, str]] = None

class VerifyOTPRequest(BaseModel):
    """Request schema for OTP verification"""
    email: EmailStr
    otp: str

class ResendOTPRequest(BaseModel):
    """Request schema for resending OTP"""
    email: EmailStr
    purpose: str = "verification"  # verification or reset
    
    @field_validator('purpose')
    def validate_purpose(cls, v):
        assert v in ["verification", "reset"], 'Purpose must be either "verification" or "reset"'
        return v

class ForgotPasswordRequest(BaseModel):
    """Request schema for forgot password"""
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    """Request schema for password reset"""
    email: EmailStr
    otp: str
    new_password: str
    
    @field_validator('new_password')
    def password_strength(cls, v):
        assert len(v) >= 8, 'Password must be at least 8 characters'
        return v