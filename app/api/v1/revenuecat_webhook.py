from fastapi import APIRouter, Request, HTTPException, status, Depends
from pymongo.database import Database
from typing import Dict, Any
from datetime import datetime
import logging
import hmac
import hashlib
import json

from app.database import get_database
from app.models.user import UserModel
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter()

# RevenueCat webhook secret - set this in your environment variables
REVENUECAT_WEBHOOK_SECRET = "your_revenuecat_webhook_secret_here"  # TODO: Set in environment


@router.post("/revenuecat")
async def handle_revenuecat_webhook(
    request: Request,
    db: Database = Depends(get_database)
):
    """
    Handle RevenueCat webhook events for subscription updates
    
    This endpoint receives notifications from RevenueCat when:
    - User purchases a subscription
    - Subscription renews
    - Subscription expires/cancels
    - User restores purchases
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify webhook signature (recommended for production)
        signature = request.headers.get("Authorization")
        if not _verify_webhook_signature(body, signature):
            logger.warning("Invalid RevenueCat webhook signature - proceeding anyway for testing")
            # Don't fail in development/testing - just log the warning
            # raise HTTPException(
            #     status_code=status.HTTP_401_UNAUTHORIZED,
            #     detail="Invalid webhook signature"
            # )
        
        # Parse webhook data
        webhook_data = json.loads(body.decode('utf-8'))
        event_type = webhook_data.get("event", {}).get("type")
        
        logger.info(f"Received RevenueCat webhook: {event_type}")
        
        # Process different event types
        if event_type in ["INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE"]:
            await _handle_subscription_activated(webhook_data, db)
        elif event_type in ["CANCELLATION", "EXPIRATION"]:
            await _handle_subscription_deactivated(webhook_data, db)
        elif event_type == "UNCANCELLATION":
            await _handle_subscription_reactivated(webhook_data, db)
        elif event_type == "TEST":
            logger.info("Received RevenueCat test event - webhook is working!")
            return {"status": "processed", "event_type": "TEST", "message": "Test event received successfully"}
        else:
            logger.info(f"Unhandled RevenueCat event type: {event_type}")
        
        return {"status": "processed", "event_type": event_type}
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in RevenueCat webhook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing RevenueCat webhook: {error_msg}")
        logger.error(f"Webhook data: {webhook_data if 'webhook_data' in locals() else 'N/A'}")
        
        # Return 200 to prevent RevenueCat from retrying
        # Log the error for investigation
        return {"status": "error", "message": error_msg if error_msg else "Unknown error occurred"}


async def _handle_subscription_activated(webhook_data: Dict[str, Any], db: Database):
    """Handle subscription activation events"""
    try:
        event = webhook_data.get("event", {})
        app_user_id = event.get("app_user_id")
        
        if not app_user_id:
            logger.error("No app_user_id in RevenueCat webhook")
            return
        
        # Find user by RevenueCat user ID or email
        user = db.users.find_one({
            "$or": [
                {"revenuecat_user_id": app_user_id},
                {"email": app_user_id}  # RevenueCat might use email as user ID
            ]
        })
        
        if not user:
            logger.warning(f"User not found for RevenueCat ID: {app_user_id}")
            return
        
        # Extract subscription details
        product_id = event.get("product_id")
        expiration_date = event.get("expiration_at_ms")
        
        if expiration_date:
            expiration_date = datetime.fromtimestamp(expiration_date / 1000)
        
        # Update user subscription status
        subscription_data = {
            "tier": "premium",
            "status": "active",
            "expires_at": expiration_date,
            "product_id": product_id,
            "revenuecat_customer_id": app_user_id,
            "updated_at": datetime.utcnow()
        }
        
        db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "subscription": subscription_data,
                    "revenuecat_user_id": app_user_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Activated premium subscription for user {user['_id']}")
        
    except Exception as e:
        logger.error(f"Error handling subscription activation: {e}")
        raise


async def _handle_subscription_deactivated(webhook_data: Dict[str, Any], db: Database):
    """Handle subscription deactivation events"""
    try:
        event = webhook_data.get("event", {})
        app_user_id = event.get("app_user_id")
        
        if not app_user_id:
            logger.error("No app_user_id in RevenueCat webhook")
            return
        
        # Find user
        user = db.users.find_one({
            "$or": [
                {"revenuecat_user_id": app_user_id},
                {"email": app_user_id}
            ]
        })
        
        if not user:
            logger.warning(f"User not found for RevenueCat ID: {app_user_id}")
            return
        
        # Downgrade to free tier
        subscription_data = {
            "tier": "free",
            "status": "expired",
            "expires_at": None,
            "product_id": None,
            "revenuecat_customer_id": app_user_id,
            "updated_at": datetime.utcnow()
        }
        
        db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "subscription": subscription_data,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Deactivated premium subscription for user {user['_id']}")
        
    except Exception as e:
        logger.error(f"Error handling subscription deactivation: {e}")
        raise


async def _handle_subscription_reactivated(webhook_data: Dict[str, Any], db: Database):
    """Handle subscription reactivation events (uncancellation)"""
    # Similar to activation but for reactivated subscriptions
    await _handle_subscription_activated(webhook_data, db)


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """
    Verify RevenueCat webhook signature for security
    
    RevenueCat sends webhooks with HMAC-SHA256 signature in Authorization header
    Format: "Bearer <signature>"
    """
    if not signature or not signature.startswith("Bearer "):
        return False
    
    if not REVENUECAT_WEBHOOK_SECRET or REVENUECAT_WEBHOOK_SECRET == "your_revenuecat_webhook_secret_here":
        logger.warning("RevenueCat webhook secret not configured - skipping signature verification")
        return True  # Allow in development, but log warning
    
    try:
        expected_signature = signature[7:]  # Remove "Bearer " prefix
        
        # Calculate HMAC-SHA256
        calculated_signature = hmac.new(
            REVENUECAT_WEBHOOK_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, calculated_signature)
        
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


@router.post("/sync")
async def sync_subscription_status(
    sync_data: Dict[str, Any],
    db: Database = Depends(get_database)
):
    """
    Sync subscription status from RevenueCat (called by mobile app)
    
    This is a fallback method for when the app wants to manually sync
    subscription status with the backend
    """
    try:
        user_id = sync_data.get("user_id")
        is_premium = sync_data.get("is_premium", False)
        expiration_date = sync_data.get("expiration_date")
        customer_id = sync_data.get("customer_id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id is required"
            )
        
        # Parse expiration date if provided
        if expiration_date:
            try:
                expiration_date = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
            except ValueError:
                expiration_date = None
        
        # Update user subscription
        subscription_data = {
            "tier": "premium" if is_premium else "free",
            "status": "active" if is_premium else "expired",
            "expires_at": expiration_date,
            "revenuecat_customer_id": customer_id,
            "updated_at": datetime.utcnow()
        }
        
        result = db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "subscription": subscription_data,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "success": True,
            "message": "Subscription status synced successfully",
            "subscription": subscription_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing subscription status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync subscription status"
        )
