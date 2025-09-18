from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.database import Database
from datetime import datetime
from typing import Optional

from app.api.deps import get_db
from app.models.user import UserModel
from app.api.deps import get_current_active_user
from app.schemas.user import (
    UserCreate, UserResponse, UserUpdate, 
    OnboardingPreferencesUpdate, OnboardingPreferencesResponse
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/preferences", response_model=OnboardingPreferencesResponse)
async def save_user_preferences(
    preferences: OnboardingPreferencesUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_db)
):
    """Save user onboarding preferences"""
    try:
        # Update user's onboarding preferences
        update_data = {
            "onboarding.gender": preferences.gender,
            "onboarding.age_group": preferences.age_group,
            "onboarding.skin_type": preferences.skin_type,
            "onboarding.completed_at": datetime.utcnow(),
            "onboarding.is_completed": True,
            "updated_at": datetime.utcnow()
        }
        
        # Also update the legacy skin_type field for backward compatibility
        if preferences.skin_type:
            update_data["profile.skin_type"] = preferences.skin_type
        
        # Convert age_group to legacy age_range format
        if preferences.age_group:
            age_range_mapping = {
                "under_18": "Under 18",
                "18_24": "18-24",
                "25_34": "25-34", 
                "35_44": "35-44",
                "45_54": "45-54",
                "55_plus": "55+"
            }
            update_data["profile.age_range"] = age_range_mapping.get(preferences.age_group, preferences.age_group)
        
        result = db.users.update_one(
            {"_id": current_user.id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or no changes made"
            )
        
        # Return the saved preferences
        return OnboardingPreferencesResponse(
            gender=preferences.gender,
            age_group=preferences.age_group,
            skin_type=preferences.skin_type,
            is_completed=True,
            completed_at=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving preferences: {str(e)}"
        )

@router.get("/preferences", response_model=OnboardingPreferencesResponse)
async def get_user_preferences(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_db)
):
    """Get user onboarding preferences"""
    try:
        user_doc = db.users.find_one({"_id": current_user.id})
        
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        onboarding = user_doc.get("onboarding", {})
        
        return OnboardingPreferencesResponse(
            gender=onboarding.get("gender"),
            age_group=onboarding.get("age_group"),
            skin_type=onboarding.get("skin_type"),
            is_completed=onboarding.get("is_completed", False),
            completed_at=onboarding.get("completed_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving preferences: {str(e)}"
        )

@router.put("/preferences", response_model=OnboardingPreferencesResponse)
async def update_user_preferences(
    preferences: OnboardingPreferencesUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_db)
):
    """Update user onboarding preferences"""
    try:
        # Prepare update data (only update fields that are provided)
        update_data = {"updated_at": datetime.utcnow()}
        
        if preferences.gender is not None:
            update_data["onboarding.gender"] = preferences.gender
            
        if preferences.age_group is not None:
            update_data["onboarding.age_group"] = preferences.age_group
            # Update legacy age_range as well
            age_range_mapping = {
                "under_18": "Under 18",
                "18_24": "18-24",
                "25_34": "25-34",
                "35_44": "35-44",
                "45_54": "45-54",
                "55_plus": "55+"
            }
            update_data["profile.age_range"] = age_range_mapping.get(preferences.age_group, preferences.age_group)
            
        if preferences.skin_type is not None:
            update_data["onboarding.skin_type"] = preferences.skin_type
            # Update legacy skin_type as well
            update_data["profile.skin_type"] = preferences.skin_type
        
        result = db.users.update_one(
            {"_id": current_user.id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or no changes made"
            )
        
        # Get updated preferences to return
        user_doc = db.users.find_one({"_id": current_user.id})
        onboarding = user_doc.get("onboarding", {})
        
        return OnboardingPreferencesResponse(
            gender=onboarding.get("gender"),
            age_group=onboarding.get("age_group"),
            skin_type=onboarding.get("skin_type"),
            is_completed=onboarding.get("is_completed", False),
            completed_at=onboarding.get("completed_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating preferences: {str(e)}"
        )

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get complete user profile including onboarding preferences"""
    from app.schemas.user import OnboardingPreferencesResponse, SkinProfileResponse, ProductPreferencesResponse, SubscriptionInfoResponse, PrivacySettingsResponse
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        name=getattr(current_user, 'name', None),
        onboarding=OnboardingPreferencesResponse(**current_user.onboarding.model_dump()),
        profile=SkinProfileResponse(**current_user.profile.model_dump()),
        product_preferences=ProductPreferencesResponse(**current_user.product_preferences.model_dump()),
        subscription=SubscriptionInfoResponse(**current_user.subscription.model_dump()),
        privacy_settings=PrivacySettingsResponse(**current_user.privacy_settings.model_dump()),
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified
    )

@router.get("/me")
async def get_current_user_profile(
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get current user profile (alias for /profile)"""
    from app.schemas.user import OnboardingPreferencesResponse, SkinProfileResponse, ProductPreferencesResponse, SubscriptionInfoResponse, PrivacySettingsResponse
    
    # Check if onboarding is completed
    is_new_user = not current_user.onboarding.is_completed
    
    response_data = {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "name": getattr(current_user, 'name', None),
        "onboarding": OnboardingPreferencesResponse(**current_user.onboarding.model_dump()).model_dump(),
        "profile": SkinProfileResponse(**current_user.profile.model_dump()).model_dump(),
        "product_preferences": ProductPreferencesResponse(**current_user.product_preferences.model_dump()).model_dump(),
        "subscription": SubscriptionInfoResponse(**current_user.subscription.model_dump()).model_dump(),
        "privacy_settings": PrivacySettingsResponse(**current_user.privacy_settings.model_dump()).model_dump(),
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "isNewUser": is_new_user  # Add this flag for Flutter app
    }
    
    return response_data

@router.put("/me/onboarding", response_model=UserResponse)
async def update_user_onboarding(
    preferences: OnboardingPreferencesUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_db)
):
    """Update user onboarding preferences"""
    try:
        # Prepare update data
        update_data = {"updated_at": datetime.utcnow()}
        
        if preferences.gender is not None:
            update_data["onboarding.gender"] = preferences.gender
            
        if preferences.age_group is not None:
            update_data["onboarding.age_group"] = preferences.age_group
            # Update legacy age_range as well
            age_range_mapping = {
                "under_18": "Under 18",
                "18_24": "18-24",
                "25_34": "25-34",
                "35_44": "35-44",
                "45_54": "45-54",
                "55_plus": "55+"
            }
            update_data["profile.age_range"] = age_range_mapping.get(preferences.age_group, preferences.age_group)
            
        if preferences.skin_type is not None:
            update_data["onboarding.skin_type"] = preferences.skin_type
            # Update legacy skin_type as well
            update_data["profile.skin_type"] = preferences.skin_type
        
        # Mark onboarding as completed if all fields are set
        if preferences.gender and preferences.age_group and preferences.skin_type:
            update_data["onboarding.is_completed"] = True
            update_data["onboarding.completed_at"] = datetime.utcnow()
        
        result = db.users.update_one(
            {"_id": current_user.id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or no changes made"
            )
        
        # Get updated user
        updated_user = db.users.find_one({"_id": current_user.id})
        from app.schemas.user import OnboardingPreferencesResponse, SkinProfileResponse, ProductPreferencesResponse, SubscriptionInfoResponse, PrivacySettingsResponse
        
        return UserResponse(
            id=str(updated_user["_id"]),
            email=updated_user["email"],
            username=updated_user["username"],
            name=updated_user.get("name"),
            onboarding=OnboardingPreferencesResponse(**updated_user.get("onboarding", {})),
            profile=SkinProfileResponse(**updated_user.get("profile", {})),
            product_preferences=ProductPreferencesResponse(**updated_user.get("product_preferences", {})),
            subscription=SubscriptionInfoResponse(**updated_user.get("subscription", {})),
            privacy_settings=PrivacySettingsResponse(**updated_user.get("privacy_settings", {})),
            created_at=updated_user["created_at"],
            last_login=updated_user.get("last_login"),
            is_active=updated_user.get("is_active", True),
            is_verified=updated_user.get("is_verified", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating onboarding preferences: {str(e)}"
        )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_db)
):
    """Update current user account details"""
    try:
        update_data = {"updated_at": datetime.utcnow()}
        
        if user_update.username is not None:
            # Check if username is already taken
            existing = db.users.find_one({"username": user_update.username, "_id": {"$ne": current_user.id}})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            update_data["username"] = user_update.username
            
        if user_update.email is not None:
            # Check if email is already taken
            existing = db.users.find_one({"email": user_update.email, "_id": {"$ne": current_user.id}})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            update_data["email"] = user_update.email
            update_data["is_verified"] = False  # Reset verification status
        
        if user_update.name is not None:
            update_data["name"] = user_update.name
        
        if len(update_data) > 1:  # More than just updated_at
            db.users.update_one(
                {"_id": current_user.id},
                {"$set": update_data}
            )
        
        # Get updated user
        updated_user = db.users.find_one({"_id": current_user.id})
        return UserResponse(
            id=str(updated_user["_id"]),
            email=updated_user["email"],
            username=updated_user["username"],
            name=updated_user.get("name"),
            onboarding=updated_user.get("onboarding", {}),
            profile=updated_user.get("profile", {}),
            product_preferences=updated_user.get("product_preferences", {}),
            subscription=updated_user.get("subscription", {}),
            privacy_settings=updated_user.get("privacy_settings", {}),
            created_at=updated_user["created_at"],
            last_login=updated_user.get("last_login"),
            is_active=updated_user.get("is_active", True),
            is_verified=updated_user.get("is_verified", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )

@router.get("/stats")
async def get_user_stats(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_db)
):
    """Get user statistics"""
    try:
        # Count analyses
        total_analyses = db.skin_analyses.count_documents({"user_id": current_user.id})
        
        # Count this month's analyses
        from datetime import datetime, timedelta
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_analyses = db.skin_analyses.count_documents({
            "user_id": current_user.id,
            "created_at": {"$gte": start_of_month}
        })
        
        # Get latest analysis date
        latest_analysis = db.skin_analyses.find_one(
            {"user_id": current_user.id},
            sort=[("created_at", -1)]
        )
        
        # Count saved products
        saved_products = db.user_product_interactions.count_documents({
            "user_id": current_user.id,
            "interaction_type": "saved"
        })
        
        return {
            "total_analyses": total_analyses,
            "monthly_analyses": monthly_analyses,
            "analyses_remaining": 5 - monthly_analyses if current_user.subscription.tier == "basic" else "unlimited",
            "latest_analysis_date": latest_analysis["created_at"] if latest_analysis else None,
            "saved_products": saved_products,
            "subscription_tier": current_user.subscription.tier,
            "onboarding_completed": current_user.onboarding.is_completed,
            "member_since": current_user.created_at
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving stats: {str(e)}"
        )

@router.delete("/me")
async def delete_user_account(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_db)
):
    """Delete user account (soft delete)"""
    try:
        # Soft delete - just mark as inactive
        db.users.update_one(
            {"_id": current_user.id},
            {"$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }}
        )
        
        return {"message": "Account successfully deactivated"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting account: {str(e)}"
        )