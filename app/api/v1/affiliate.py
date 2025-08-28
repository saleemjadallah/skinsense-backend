"""
Affiliate tracking API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import RedirectResponse
from pymongo.database import Database
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.api.deps import get_current_active_user
from app.models.user import UserModel
from app.services.affiliate_service import get_affiliate_service
from app.schemas.affiliate import (
    AffiliateClickRequest,
    ConversionWebhook,
    AffiliateAnalyticsResponse
)

router = APIRouter()


@router.get("/track/product/{tracking_id}")
async def track_product_click(
    tracking_id: str,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_database)
):
    """
    Track product click and redirect to affiliate link
    
    This endpoint is called when a user clicks on a product from the app.
    It tracks the click and redirects to the actual affiliate link.
    """
    affiliate_service = get_affiliate_service(db)
    
    # Get the redirect URL
    redirect_url = await affiliate_service.track_click(tracking_id)
    
    if not redirect_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid tracking link"
        )
    
    # Return redirect response
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/affiliate-click")
async def track_affiliate_click(
    click_data: AffiliateClickRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Track affiliate link click from the app
    
    This is called directly from the app when a user clicks "Shop Now"
    """
    affiliate_service = get_affiliate_service(db)
    
    # Generate tracking ID
    tracking_id = affiliate_service._generate_tracking_id(
        current_user.id,
        click_data.product_id
    )
    
    # Store tracking data
    affiliate_service._store_tracking_data(
        tracking_id,
        current_user.id,
        click_data.dict(),
        click_data.skin_analysis_id,
        click_data.retailer
    )
    
    return {
        "tracking_id": tracking_id,
        "message": "Click tracked successfully"
    }


@router.post("/conversion-webhook/{retailer}")
async def handle_conversion_webhook(
    retailer: str,
    webhook_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_database)
):
    """
    Handle conversion webhooks from affiliate networks
    
    Each affiliate network has its own webhook format, so we handle them separately
    """
    affiliate_service = get_affiliate_service(db)
    
    try:
        # Parse webhook based on retailer
        if retailer == "amazon":
            tracking_id = webhook_data.get("subid") or webhook_data.get("ascsubtag")
            order_value = float(webhook_data.get("commission_amount", 0))
            order_id = webhook_data.get("order_id")
            
        elif retailer == "sephora":
            tracking_id = webhook_data.get("clickid")
            order_value = float(webhook_data.get("sale_amount", 0))
            order_id = webhook_data.get("order_number")
            
        elif retailer == "ulta":
            tracking_id = webhook_data.get("sid")
            order_value = float(webhook_data.get("order_total", 0))
            order_id = webhook_data.get("order_id")
            
        elif retailer == "target":
            tracking_id = webhook_data.get("clkid")
            order_value = float(webhook_data.get("order_value", 0))
            order_id = webhook_data.get("transaction_id")
            
        elif retailer == "iherb":
            tracking_id = webhook_data.get("clickid")
            order_value = float(webhook_data.get("order_amount", 0))
            order_id = webhook_data.get("order_number")
            
        elif retailer == "dermstore":
            tracking_id = webhook_data.get("u1")
            order_value = float(webhook_data.get("sale_amount", 0))
            order_id = webhook_data.get("order_id")
            
        else:
            raise ValueError(f"Unknown retailer: {retailer}")
        
        if not tracking_id:
            raise ValueError("No tracking ID found in webhook")
        
        # Track the conversion
        success = await affiliate_service.track_conversion(
            tracking_id,
            order_value,
            order_id
        )
        
        if success:
            # Log successful conversion
            logger.info(f"Conversion tracked: {retailer} - ${order_value} - {tracking_id}")
            
            return {"status": "success", "tracking_id": tracking_id}
        else:
            raise ValueError("Failed to track conversion")
            
    except Exception as e:
        logger.error(f"Conversion webhook error ({retailer}): {e}")
        logger.error(f"Webhook data: {webhook_data}")
        
        # Return success to prevent webhook retries
        # but log the error for investigation
        return {"status": "received", "error": str(e)}


@router.get("/affiliate-analytics", response_model=AffiliateAnalyticsResponse)
async def get_affiliate_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Get affiliate analytics for the current user or admin
    
    Admins can see all analytics, users can see their own
    """
    # Default to last 30 days if no dates provided
    if not end_date:
        end_date = datetime.now(timezone.utc)
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    affiliate_service = get_affiliate_service(db)
    
    # Get analytics
    analytics = affiliate_service.get_analytics(start_date, end_date)
    
    # If user is not admin, filter to their own data
    if not current_user.is_admin:
        # Filter analytics to user's own clicks/conversions
        user_filter = {"user_id": current_user.id}
        # This would need to be implemented in the service
        # For now, return limited data
        analytics = {
            "message": "User-specific analytics coming soon",
            "total_clicks": 0,
            "total_conversions": 0,
            "total_revenue": 0,
            "total_commission": 0
        }
    
    return analytics


@router.get("/my-earnings")
async def get_user_earnings(
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Get the current user's affiliate earnings (if applicable)
    
    This could be used for influencer programs or referral bonuses
    """
    # Get user's total generated commission
    user_data = db.users.find_one({"_id": current_user.id})
    
    metrics = user_data.get("metrics", {})
    
    return {
        "total_purchases": metrics.get("total_affiliate_purchases", 0),
        "total_value": metrics.get("total_affiliate_value", 0),
        "total_commission_generated": metrics.get("total_commission_generated", 0),
        "message": "Thank you for using SkinSense AI!"
    }


@router.post("/test-conversion")
async def test_conversion_tracking(
    tracking_id: str,
    order_value: float = 99.99,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """
    Test endpoint for conversion tracking (development only)
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoint only available in debug mode"
        )
    
    affiliate_service = get_affiliate_service(db)
    
    success = await affiliate_service.track_conversion(
        tracking_id,
        order_value,
        f"TEST-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )
    
    return {
        "success": success,
        "tracking_id": tracking_id,
        "order_value": order_value,
        "commission_earned": order_value * 0.05  # Assuming 5% commission
    }