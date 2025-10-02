from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import HTTPBearer
from pymongo.database import Database
from datetime import datetime, timedelta
from bson import ObjectId

from app.database import get_database
from app.schemas.user import (
    UserCreate, UserLogin, TokenResponse, UserResponse, AuthResponse,
    GoogleSignInRequest, AppleSignInRequest, VerifyOTPRequest,
    ResendOTPRequest, ForgotPasswordRequest, ResetPasswordRequest
)
from app.models.user import UserModel, SocialAuthProvider
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    create_verification_token,
    verify_email_token
)
from app.services.social_auth_service import social_auth_service
from app.services.email_service import email_service
from app.core.rate_limit import auth_rate_limit, strict_rate_limit
import secrets

router = APIRouter()
security = HTTPBearer()

@router.post("/register", response_model=AuthResponse)
@auth_rate_limit
async def register(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_database)
):
    """Register new user"""
    
    # Check if email already exists (usernames can be duplicate)
    existing_user = db.users.find_one({"email": user_data.email})
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    verification_token = create_verification_token(user_data.email)
    
    new_user = UserModel(
        email=user_data.email,
        username=user_data.username,
        name=user_data.name,
        password_hash=hashed_password,
        verification_token=verification_token,
        created_at=datetime.utcnow()
    )
    
    # Insert user
    result = db.users.insert_one(new_user.dict(by_alias=True))
    
    # Send verification OTP email
    background_tasks.add_task(
        email_service.send_otp_email_sync,
        user_data.email,
        user_data.username
    )
    
    # Create tokens
    user_id = str(result.inserted_id)
    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)
    
    # Build user response
    from app.schemas.user import OnboardingPreferencesResponse, SkinProfileResponse, ProductPreferencesResponse, SubscriptionInfoResponse, PrivacySettingsResponse
    
    user_response = UserResponse(
        id=user_id,
        email=new_user.email,
        username=new_user.username,
        name=new_user.name,
        onboarding=OnboardingPreferencesResponse(**new_user.onboarding.model_dump()),
        profile=SkinProfileResponse(**new_user.profile.model_dump()),
        product_preferences=ProductPreferencesResponse(**new_user.product_preferences.model_dump()),
        subscription=SubscriptionInfoResponse(**new_user.subscription.model_dump()),
        privacy_settings=PrivacySettingsResponse(**new_user.privacy_settings.model_dump()),
        created_at=new_user.created_at,
        last_login=None,
        is_active=new_user.is_active,
        is_verified=new_user.is_verified
    )
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=1800,
        user=user_response,
        is_new_user=True
    )

@router.post("/login", response_model=AuthResponse)
@auth_rate_limit
async def login(
    request: Request,
    user_credentials: UserLogin,
    db: Database = Depends(get_database)
):
    """User login"""
    
    # Import response models
    from app.schemas.user import OnboardingPreferencesResponse, SkinProfileResponse, ProductPreferencesResponse, SubscriptionInfoResponse, PrivacySettingsResponse
    
    # Find user
    user = db.users.find_one({"email": user_credentials.email})
    
    if not user or not verify_password(user_credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The password you entered is incorrect. Please try again or reset your password."
        )
    
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated"
        )
    
    # Update last login
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    # Create tokens
    user_id = str(user["_id"])
    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)
    
    # Build user response
    user_response = UserResponse(
        id=user_id,
        email=user["email"],
        username=user["username"],
        name=user.get("name"),
        onboarding=OnboardingPreferencesResponse(**user.get("onboarding", {})),
        profile=SkinProfileResponse(**user.get("profile", {})),
        product_preferences=ProductPreferencesResponse(**user.get("product_preferences", {})),
        subscription=SubscriptionInfoResponse(**user.get("subscription", {})),
        privacy_settings=PrivacySettingsResponse(**user.get("privacy_settings", {})),
        created_at=user.get("created_at", datetime.utcnow()),
        last_login=datetime.utcnow(),
        is_active=user.get("is_active", True),
        is_verified=user.get("is_verified", False)
    )
    
    # Check if user has completed onboarding
    is_new_user = not user.get("onboarding", {}).get("is_completed", False)
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=1800,
        user=user_response,
        is_new_user=is_new_user
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Database = Depends(get_database)
):
    """Refresh access token"""
    
    user_id = verify_token(refresh_token, token_type="refresh")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Verify user still exists and is active
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    access_token = create_access_token(subject=user_id)
    new_refresh_token = create_refresh_token(subject=user_id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=1800
    )

@router.post("/verify-email")
async def verify_email(
    token: str,
    db: Database = Depends(get_database)
):
    """Verify user email"""
    
    email = verify_email_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Update user verification status
    result = db.users.update_one(
        {"email": email},
        {
            "$set": {"is_verified": True},
            "$unset": {"verification_token": ""}
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "Email verified successfully"}

@router.post("/logout")
async def logout():
    """User logout (client should discard tokens)"""
    return {"message": "Logged out successfully"}

@router.post("/google", response_model=AuthResponse)
async def google_sign_in(
    request: GoogleSignInRequest,
    db: Database = Depends(get_database)
):
    """Sign in with Google"""
    
    # Import response models
    from app.schemas.user import OnboardingPreferencesResponse, SkinProfileResponse, ProductPreferencesResponse, SubscriptionInfoResponse, PrivacySettingsResponse
    
    # Verify Google token
    google_user = await social_auth_service.verify_google_token(request.id_token)
    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    
    # Check if user exists with this email or Google ID
    existing_user = db.users.find_one({
        "$or": [
            {"email": google_user["email"]},
            {"social_providers.provider_user_id": google_user["provider_user_id"]}
        ]
    })
    
    is_new_user = False
    
    if existing_user:
        # Update last login
        db.users.update_one(
            {"_id": existing_user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        # Check if Google provider is already linked
        google_linked = any(
            p.get("provider") == "google" and p.get("provider_user_id") == google_user["provider_user_id"]
            for p in existing_user.get("social_providers", [])
        )
        
        if not google_linked:
            # Link Google account
            provider = SocialAuthProvider(
                provider="google",
                provider_user_id=google_user["provider_user_id"],
                email=google_user["email"],
                name=google_user.get("name"),
                picture=google_user.get("picture")
            )
            db.users.update_one(
                {"_id": existing_user["_id"]},
                {"$push": {"social_providers": provider.model_dump()}}
            )
        
        user_id = str(existing_user["_id"])
        
    else:
        # Create new user
        is_new_user = True
        
        # Generate username from email or name (duplicates allowed)
        username = google_user.get("name", google_user["email"].split("@")[0])
        username = username.lower().replace(" ", "_")
        
        # Create new user
        new_user = UserModel(
            email=google_user["email"],
            username=username,
            is_verified=google_user.get("email_verified", False),
            social_providers=[
                SocialAuthProvider(
                    provider="google",
                    provider_user_id=google_user["provider_user_id"],
                    email=google_user["email"],
                    name=google_user.get("name"),
                    picture=google_user.get("picture")
                )
            ]
        )
        
        # Update profile with Google data
        if google_user.get("picture"):
            new_user.profile.avatar_url = google_user["picture"]
        
        # Insert user
        result = db.users.insert_one(new_user.dict(by_alias=True))
        user_id = str(result.inserted_id)
        existing_user = new_user.model_dump()
        existing_user["_id"] = result.inserted_id
    
    # Create tokens
    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)
    
    # Build user response
    user_response = UserResponse(
        id=user_id,
        email=existing_user["email"],
        username=existing_user["username"],
        onboarding=OnboardingPreferencesResponse(**existing_user.get("onboarding", {})),
        profile=SkinProfileResponse(**existing_user.get("profile", {})),
        product_preferences=ProductPreferencesResponse(**existing_user.get("product_preferences", {})),
        subscription=SubscriptionInfoResponse(**existing_user.get("subscription", {})),
        privacy_settings=PrivacySettingsResponse(**existing_user.get("privacy_settings", {})),
        created_at=existing_user.get("created_at", datetime.utcnow()),
        last_login=datetime.utcnow(),
        is_active=existing_user.get("is_active", True),
        is_verified=existing_user.get("is_verified", False)
    )
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=1800,
        user=user_response,
        is_new_user=is_new_user
    )

@router.post("/apple", response_model=AuthResponse)
async def apple_sign_in(
    request: AppleSignInRequest,
    db: Database = Depends(get_database)
):
    """Sign in with Apple"""
    
    # Import response models
    from app.schemas.user import OnboardingPreferencesResponse, SkinProfileResponse, ProductPreferencesResponse, SubscriptionInfoResponse, PrivacySettingsResponse
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Verify Apple token
        apple_user = await social_auth_service.verify_apple_token(
            request.identity_token,
            request.user_identifier,
            request.email,
            request.full_name
        )
        
        if not apple_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Apple token"
            )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error during Apple Sign In: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing Apple Sign In: {str(e)}"
        )
    
    # Check if user exists with this Apple ID
    existing_user = db.users.find_one({
        "social_providers.provider_user_id": apple_user["provider_user_id"]
    })
    
    is_new_user = False
    
    if existing_user:
        # Update last login
        db.users.update_one(
            {"_id": existing_user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        user_id = str(existing_user["_id"])
        
    else:
        # For Apple, also check by email if provided
        if apple_user.get("email"):
            existing_user = db.users.find_one({"email": apple_user["email"]})
            
            if existing_user:
                # Link Apple account to existing user
                provider = SocialAuthProvider(
                    provider="apple",
                    provider_user_id=apple_user["provider_user_id"],
                    email=apple_user.get("email"),
                    name=apple_user.get("name")
                )
                db.users.update_one(
                    {"_id": existing_user["_id"]},
                    {
                        "$push": {"social_providers": provider.model_dump()},
                        "$set": {"last_login": datetime.utcnow()}
                    }
                )
                user_id = str(existing_user["_id"])
            else:
                # Create new user
                is_new_user = True
                
                # Generate unique username
                base_username = ""
                if apple_user.get("name"):
                    base_username = apple_user["name"].lower().replace(" ", "_")
                elif apple_user.get("email"):
                    base_username = apple_user["email"].split("@")[0]
                else:
                    base_username = f"user_{secrets.token_hex(4)}"
                
                # Ensure username is unique
                username = base_username
                counter = 1
                while db.users.find_one({"username": username}):
                    username = f"{base_username}_{counter}"
                    counter += 1
                    if counter > 100:  # Safety limit
                        username = f"{base_username}_{secrets.token_hex(4)}"
                        break
                
                
                # Create new user
                new_user = UserModel(
                    email=apple_user.get("email", f"{apple_user['provider_user_id']}@privaterelay.appleid.com"),
                    username=username,
                    is_verified=apple_user.get("email_verified", False),
                    social_providers=[
                        SocialAuthProvider(
                            provider="apple",
                            provider_user_id=apple_user["provider_user_id"],
                            email=apple_user.get("email"),
                            name=apple_user.get("name")
                        )
                    ]
                )
                
                # Insert user
                result = db.users.insert_one(new_user.dict(by_alias=True))
                user_id = str(result.inserted_id)
                existing_user = new_user.model_dump()
                existing_user["_id"] = result.inserted_id
        else:
            # No email and no existing user - create new user with Apple ID only
            is_new_user = True
            
            # Generate unique username
            username = f"user_{secrets.token_hex(4)}"
            while db.users.find_one({"username": username}):
                username = f"user_{secrets.token_hex(4)}"
            
            new_user = UserModel(
                email=f"{apple_user['provider_user_id']}@privaterelay.appleid.com",
                username=username,
                is_verified=False,
                social_providers=[
                    SocialAuthProvider(
                        provider="apple",
                        provider_user_id=apple_user["provider_user_id"]
                    )
                ]
            )
            
            result = db.users.insert_one(new_user.dict(by_alias=True))
            user_id = str(result.inserted_id)
            existing_user = new_user.model_dump()
            existing_user["_id"] = result.inserted_id
    
    # Create tokens
    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)
    
    # Build user response
    user_response = UserResponse(
        id=user_id,
        email=existing_user["email"],
        username=existing_user["username"],
        onboarding=OnboardingPreferencesResponse(**existing_user.get("onboarding", {})),
        profile=SkinProfileResponse(**existing_user.get("profile", {})),
        product_preferences=ProductPreferencesResponse(**existing_user.get("product_preferences", {})),
        subscription=SubscriptionInfoResponse(**existing_user.get("subscription", {})),
        privacy_settings=PrivacySettingsResponse(**existing_user.get("privacy_settings", {})),
        created_at=existing_user.get("created_at", datetime.utcnow()),
        last_login=datetime.utcnow(),
        is_active=existing_user.get("is_active", True),
        is_verified=existing_user.get("is_verified", False)
    )
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=1800,
        user=user_response,
        is_new_user=is_new_user
    )


@router.post("/verify-otp")
async def verify_otp_endpoint(
    request: VerifyOTPRequest,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_database)
):
    """Verify OTP code and mark email as verified"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Verifying OTP for email: {request.email}")
        
        # Verify OTP
        otp_valid = email_service.verify_otp(request.email, request.otp, "verification")
        logger.info(f"OTP verification result: {otp_valid}")
        
        if not otp_valid:
            logger.warning(f"Invalid OTP attempt for {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP"
            )
        
        # Mark user as verified
        logger.info(f"Marking user {request.email} as verified")
        result = db.users.update_one(
            {"email": request.email},
            {"$set": {"is_verified": True, "verification_token": None}}
        )
        
        if result.matched_count == 0:
            logger.error(f"User not found for email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User {request.email} marked as verified. Modified count: {result.modified_count}")
        
        # Get user for welcome email
        user = db.users.find_one({"email": request.email})
        
        if user:
            # Send welcome email
            username = user.get("username", request.email.split("@")[0])
            logger.info(f"Scheduling welcome email for {username}")
            background_tasks.add_task(
                email_service.send_welcome_email_sync,
                request.email,
                username
            )
        
        return {"message": "Email verified successfully", "verified": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP verification error for {request.email}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying OTP: {str(e)}"
        )


@router.post("/resend-otp")
async def resend_otp(
    request: ResendOTPRequest,
    db: Database = Depends(get_database)
):
    """Resend OTP code"""
    
    # Find user
    user = db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Send appropriate OTP
    if request.purpose == "verification":
        await email_service.send_otp_email(request.email, user["username"])
    elif request.purpose == "reset":
        await email_service.send_password_reset_email(request.email, user["username"])
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid purpose. Must be 'verification' or 'reset'"
        )
    
    return {"message": f"OTP sent to {request.email}"}


@router.post("/forgot-password")
@strict_rate_limit
async def forgot_password(
    req: Request,
    request: ForgotPasswordRequest,
    db: Database = Depends(get_database)
):
    """Send password reset OTP"""
    
    # Find user
    user = db.users.find_one({"email": request.email})
    if not user:
        # Don't reveal if user exists
        return {"message": "If the email exists, a reset code will be sent"}
    
    # Send password reset OTP
    await email_service.send_password_reset_email(request.email, user["username"])
    
    return {"message": "If the email exists, a reset code will be sent"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Database = Depends(get_database)
):
    """Reset password using OTP"""
    
    # Verify OTP
    if not email_service.verify_otp(request.email, request.otp, "reset"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Hash new password
    hashed_password = get_password_hash(request.new_password)
    
    # Update password
    result = db.users.update_one(
        {"email": request.email},
        {"$set": {"password_hash": hashed_password}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "Password reset successfully"}
