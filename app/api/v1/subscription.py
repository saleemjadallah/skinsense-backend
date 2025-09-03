from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.database import get_database
from app.api.deps import get_current_active_user
from app.models.user import UserModel
from app.services.subscription_service import SubscriptionService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status")
async def get_subscription_status(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
) -> Dict[str, Any]:
    """Get current subscription status and usage"""
    return SubscriptionService.get_subscription_status(current_user)

@router.post("/upgrade")
async def upgrade_to_premium(
    duration_days: int = 30,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
) -> Dict[str, Any]:
    """
    Upgrade user to premium subscription
    Note: In production, this would integrate with payment provider
    """
    # In production, verify payment first
    # For now, this is a mock upgrade endpoint
    
    # Upgrade user
    updated_user = SubscriptionService.upgrade_to_premium(current_user, duration_days)
    
    # Save to database
    db.users.update_one(
        {"_id": current_user.id},
        {"$set": {
            "subscription": updated_user.subscription.dict(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {
        "success": True,
        "message": f"Successfully upgraded to premium for {duration_days} days",
        "expires_at": updated_user.subscription.expires_at,
        "tier": "premium"
    }

@router.post("/downgrade")
async def downgrade_to_free(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
) -> Dict[str, Any]:
    """Downgrade user to free tier"""
    
    # Downgrade user
    updated_user = SubscriptionService.downgrade_to_free(current_user)
    
    # Save to database
    db.users.update_one(
        {"_id": current_user.id},
        {"$set": {
            "subscription": updated_user.subscription.dict(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {
        "success": True,
        "message": "Downgraded to free tier",
        "tier": "free"
    }

@router.get("/features")
async def get_feature_comparison() -> Dict[str, Any]:
    """Get feature comparison between free and premium tiers"""
    return {
        "free": SubscriptionService.FEATURES["free"],
        "premium": SubscriptionService.FEATURES["premium"],
        "pricing": {
            "free": 0,
            "premium": 9.99,
            "currency": "USD",
            "billing_period": "monthly"
        }
    }

@router.get("/usage/scans")
async def get_scan_usage(
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get current scan usage and limits"""
    return SubscriptionService.check_scan_limit(current_user)

@router.get("/usage/pal")
async def get_pal_usage(
    current_user: UserModel = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get current Pal AI usage and limits"""
    return SubscriptionService.check_pal_limit(current_user)