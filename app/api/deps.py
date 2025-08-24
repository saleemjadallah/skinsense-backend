from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo.database import Database
from bson import ObjectId

from app.database import get_database
from app.core.security import verify_token
from app.models.user import UserModel

security = HTTPBearer()

def get_db() -> Database:
    return get_database()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Database = Depends(get_db)
) -> UserModel:
    import logging
    logger = logging.getLogger(__name__)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Log token for debugging (only first 20 chars)
    token_preview = credentials.credentials[:20] if len(credentials.credentials) > 20 else credentials.credentials
    logger.info(f"Verifying token: {token_preview}...")
    
    user_id = verify_token(credentials.credentials)
    if user_id is None:
        logger.error("Token verification failed - invalid or expired token")
        raise credentials_exception
    
    user_data = db.users.find_one({"_id": ObjectId(user_id)})
    if user_data is None:
        raise credentials_exception
    
    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return UserModel(**user_data)

async def get_current_active_user(
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def require_subscription(min_tier: str = "plus"):
    async def subscription_dependency(
        current_user: UserModel = Depends(get_current_active_user)
    ) -> UserModel:
        tier_levels = {"basic": 0, "plus": 1, "pro": 2}
        user_tier_level = tier_levels.get(current_user.subscription.tier, 0)
        min_tier_level = tier_levels.get(min_tier, 1)
        
        if user_tier_level < min_tier_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Subscription tier '{min_tier}' or higher required"
            )
        
        return current_user
    
    return subscription_dependency

async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Database = Depends(get_db)
) -> Optional[UserModel]:
    """Get current user if authenticated, return None otherwise"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.replace("Bearer ", "")
        user_id = verify_token(token)
        if user_id is None:
            return None
        
        user_data = db.users.find_one({"_id": ObjectId(user_id)})
        if user_data is None:
            return None
        
        return UserModel(**user_data)
    except Exception:
        return None

async def require_admin(
    current_user: UserModel = Depends(get_current_active_user)
) -> UserModel:
    """Verify that the current user has admin role"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user