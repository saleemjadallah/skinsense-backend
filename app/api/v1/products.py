from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
# Temporarily disabled due to deployment issues
# import cv2
# import numpy as np
# from pyzbar import pyzbar
import base64

from app.database import get_database
from app.api.deps import get_current_active_user, require_subscription
from app.models.user import UserModel
from app.models.product import ProductModel, ProductReview, Ingredient, SkinCompatibility
from app.schemas.product import (
    ProductResponse, 
    ProductDetail,
    ProductScanRequest,
    ProductReviewCreate,
    ProductMatchResponse
)
from app.services.openai_service import openai_service

router = APIRouter()

@router.post("/scan-barcode")
async def scan_product_barcode(
    scan_request: ProductScanRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Scan product barcode"""
    
    try:
        # Decode base64 image
        if scan_request.image_data.startswith('data:image/'):
            header, encoded = scan_request.image_data.split(',', 1)
            image_bytes = base64.b64decode(encoded)
        else:
            image_bytes = base64.b64decode(scan_request.image_data)
        
        # Convert to OpenCV format
        # Temporarily disabled - barcode scanning needs cv2 and pyzbar
        # nparr = np.frombuffer(image_bytes, np.uint8)
        # image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Scan for barcodes
        # barcodes = pyzbar.decode(image)
        barcodes = []  # Temporary placeholder
        
        if not barcodes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No barcode found in image"
            )
        
        barcode_data = barcodes[0].data.decode('utf-8')
        
        # Look up product in database
        product = db.products.find_one({"barcode": barcode_data})
        
        if not product:
            # Product not found, return barcode for manual lookup
            return {
                "barcode": barcode_data,
                "product_found": False,
                "message": "Product not in our database yet. We'll add it soon!"
            }
        
        # Calculate compatibility score for user
        compatibility_score = await calculate_product_compatibility(
            product, 
            current_user,
            db
        )
        
        return ProductMatchResponse(
            barcode=barcode_data,
            product_found=True,
            product=ProductDetail(**product),
            compatibility_score=compatibility_score,
            match_reasons=await generate_match_reasons(product, current_user)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Barcode scanning failed: {str(e)}"
        )

async def calculate_product_compatibility(
    product: dict,
    user: UserModel,
    db: Database
) -> float:
    """Calculate how well a product matches user's skin type and concerns"""
    
    score = 0.0
    user_skin_type = user.profile.skin_type
    
    if user_skin_type and product.get("skin_type_compatibility"):
        compat = product["skin_type_compatibility"].get(user_skin_type, 0.0)
        score = compat * 100
    
    # Additional logic for matching ingredients to concerns
    # This is simplified - you'd want more sophisticated matching
    
    return min(score, 100.0)

async def generate_match_reasons(
    product: dict,
    user: UserModel
) -> List[str]:
    """Generate reasons why product matches user"""
    
    reasons = []
    
    if user.profile.skin_type:
        reasons.append(f"Suitable for {user.profile.skin_type} skin")
    
    # Add more matching logic here
    
    return reasons

@router.get("/recommendations", response_model=List[ProductResponse])
async def get_product_recommendations(
    category: Optional[str] = None,
    current_user: UserModel = Depends(get_current_active_user),
    db: Database = Depends(get_database)
):
    """Get personalized product recommendations"""
    
    # Build query based on user profile
    query = {}
    if category:
        query["category"] = category
    
    # Find products matching user's skin type
    if current_user.profile.skin_type:
        query[f"skin_type_compatibility.{current_user.profile.skin_type}"] = {"$gte": 0.7}
    
    products = list(db.products.find(query).limit(10))
    
    return [
        ProductResponse(
            id=str(product["_id"]),
            name=product["name"],
            brand=product["brand"],
            category=product["category"],
            image_url=product.get("image_url"),
            community_rating=product.get("community_rating", 0.0),
            total_reviews=product.get("total_reviews", 0)
        )
        for product in products
    ]