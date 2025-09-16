import httpx
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from pymongo.database import Database
from bson import ObjectId
import logging
import re

from app.core.config import settings
from app.models.user import UserModel
# from app.services.affiliate_service import get_affiliate_service  # Removed - keeping it simple

logger = logging.getLogger(__name__)

class PerplexityRecommendationService:
    """
    Service for generating personalized product recommendations using Perplexity AI
    Updated: 2025-09-04 - Simplified URL generation, removed affiliate complexity
    
    ORBO Skin Analysis Metrics (10 metrics, each scored 0-100):
    1. overall_skin_health_score - Overall skin health and condition
    2. hydration - Skin moisture levels
    3. smoothness - Texture quality and smoothness
    4. radiance - Natural glow and luminosity  
    5. dark_spots - Pigmentation uniformity (100 = no dark spots)
    6. firmness - Skin elasticity and tightness
    7. fine_lines_wrinkles - Signs of aging (100 = no wrinkles)
    8. acne - Blemish/breakout levels (100 = clear skin)
    9. dark_circles - Under-eye area condition (100 = no dark circles)
    10. redness - Sensitivity/irritation levels (100 = no redness)
    
    All metrics are normalized where 100 is the best possible score.
    Metrics below 70 are considered areas needing attention.
    """
    
    def __init__(self):
        # Use longer timeout for more reliable responses
        self.client = httpx.AsyncClient(timeout=60.0)
        self.api_key = settings.PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/chat/completions"
        
        # Log API key status
        if self.api_key:
            logger.info(f"Perplexity API key configured: {self.api_key[:10]}...")
        else:
            logger.warning("Perplexity API key not configured!")
        
        # Cache settings
        self.cache_ttl_hours = 24
        self.max_cached_products_per_user = 50
        
        # Rate limiting settings (from your successful config)
        self.requests_per_minute = 20
        self.delay_between_requests = 2  # seconds
        self.last_request_time = None
    
    async def get_personalized_recommendations(
        self,
        user: UserModel,
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str],
        db: Database,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Generate personalized product recommendations using Perplexity + smart caching
        """
        logger.info(f"Getting personalized recommendations for user {user.id}")
        logger.info(f"User location: {user_location}")
        logger.info(f"Skin analysis keys: {skin_analysis.keys() if skin_analysis else 'None'}")
        
        try:
            # Initialize affiliate service
            # affiliate_service = get_affiliate_service(db)  # Removed - keeping it simple
            
            # Step 1: Check user's cached favorites first
            cached_recommendations = await self._get_cached_recommendations(
                user, skin_analysis, db, limit=3
            )
            
            # Step 2: Get fresh Perplexity recommendations
            fresh_limit = limit - len(cached_recommendations)
            fresh_recommendations = []
            
            if fresh_limit > 0:
                if self.api_key:
                    logger.info(f"Calling Perplexity API for {fresh_limit} fresh recommendations")
                    fresh_recommendations = await self._get_perplexity_recommendations(
                        skin_analysis, user, user_location, limit=fresh_limit
                    )
                    
                    # Cache successful recommendations
                    if fresh_recommendations:
                        logger.info(f"Got {len(fresh_recommendations)} fresh recommendations from Perplexity")
                        await self._cache_recommendations(user.id, fresh_recommendations, skin_analysis, db)
                    else:
                        logger.warning("Perplexity returned empty recommendations")
                else:
                    logger.warning("Perplexity API key not configured - using fallback products")
            
            # Step 3: Combine and format results
            all_recommendations = cached_recommendations + fresh_recommendations
            
            # Ensure all products have required fields
            validated_recommendations = []
            for product in all_recommendations:
                # Ensure required fields exist
                if 'name' not in product or not product['name']:
                    product['name'] = 'Unknown Product'
                if 'brand' not in product or not product['brand']:
                    product['brand'] = 'Unknown Brand'
                if 'category' not in product or not product['category']:
                    product['category'] = 'skincare'
                
                validated_recommendations.append(product)
            
            all_recommendations = validated_recommendations
            
            # If no recommendations from either source, return empty
            if not all_recommendations:
                logger.error("CRITICAL: No recommendations from cache or Perplexity API")
                # Return empty list to test actual API functionality
                return {
                    "recommendations": [],
                    "routine_suggestions": {},
                    "shopping_list": {},
                    "source_mix": {
                        "cached_favorites": len(cached_recommendations),
                        "fresh_search": len(fresh_recommendations),
                        "total": 0
                    },
                    "error": "No product recommendations available. Please try again later.",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "location": user_location
                }
            
            # Step 4: Enhance products with URLs and images (simplified, no affiliate)
            for i, product in enumerate(all_recommendations):
                # Generate image URL if not present
                if not product.get('imageUrl') and not product.get('image_url'):
                    product['imageUrl'] = self._generate_product_image_url(product)
                
                # Generate a simple product URL for Shop Now button
                generated_url = self._generate_product_url(product)
                
                # Set URLs in camelCase for Flutter frontend compatibility
                if not product.get('productUrl'):
                    product['productUrl'] = generated_url
                
                if not product.get('affiliateLink'):
                    product['affiliateLink'] = generated_url
                    
                if not product.get('trackingLink'):
                    product['trackingLink'] = generated_url
                
                # Also keep snake_case for backward compatibility
                product['product_url'] = generated_url
                product['affiliate_link'] = generated_url
                
                # --- PRICE NORMALIZATION: always provide priceRange and currentPrice ---
                try:
                    # Normalize priceRange (prefer existing camelCase; fallback to snake_case or 'price' text)
                    if not product.get('priceRange') or not isinstance(product.get('priceRange'), str):
                        fallback_range = product.get('price_range') or product.get('price')
                        if isinstance(fallback_range, (int, float)):
                            product['priceRange'] = f"${int(fallback_range)}"
                        elif isinstance(fallback_range, str) and fallback_range.strip():
                            product['priceRange'] = fallback_range.strip()
                        else:
                            # Last resort default so UI never sees null
                            product['priceRange'] = "$15-30"
                    
                    # Normalize currentPrice (number). Use existing numeric, or parse from price strings/ranges
                    if product.get('currentPrice') is None:
                        raw_numeric = product.get('current_price')
                        if isinstance(raw_numeric, (int, float)):
                            product['currentPrice'] = float(raw_numeric)
                        elif isinstance(raw_numeric, str):
                            m = re.search(r'[\d.]+', raw_numeric)
                            if m:
                                try:
                                    product['currentPrice'] = float(m.group())
                                except Exception:
                                    pass
                        # Parse from priceRange if still missing
                        if product.get('currentPrice') is None:
                            rng = product.get('priceRange') or product.get('price_range') or product.get('price') or ''
                            if isinstance(rng, (int, float)):
                                product['currentPrice'] = float(rng)
                            elif isinstance(rng, str):
                                m2 = re.search(r'\$([\d.]+)', rng) or re.search(r'[\d.]+', rng)
                                if m2:
                                    try:
                                        product['currentPrice'] = float(m2.group(1) if m2.lastindex else m2.group(0))
                                    except Exception:
                                        pass
                except Exception:
                    # Never let price normalization break the response
                    if not product.get('priceRange'):
                        product['priceRange'] = "$15-30"

                # Ensure retailer is set
                if not product.get('retailer') and product.get('availability'):
                    # Try to detect retailer from availability data
                    online_stores = product.get('availability', {}).get('online_stores', [])
                    local_stores = product.get('availability', {}).get('local_stores', [])
                    
                    if local_stores:
                        product['retailer'] = local_stores[0]
                    elif online_stores:
                        product['retailer'] = online_stores[0].replace('.com', '')
                    else:
                        product['retailer'] = 'Online'
                
                # Debug logging for first product
                if i == 0:
                    logger.info(f"[PRODUCT DEBUG] First product after enhancement:")
                    logger.info(f"  - name: {product.get('name')}")
                    logger.info(f"  - brand: {product.get('brand')}")
                    logger.info(f"  - retailer: {product.get('retailer')}")
                    logger.info(f"  - productUrl: {product.get('productUrl')}")
                    logger.info(f"  - affiliateLink: {product.get('affiliateLink')}")
                    logger.info(f"  - trackingLink: {product.get('trackingLink')}")
                    logger.info(f"  - imageUrl: {product.get('imageUrl', '')[:50]}...")
            
            # Step 5: Build complete response
            return {
                "recommendations": all_recommendations[:limit],
                "routine_suggestions": self._build_routine_from_products(all_recommendations),
                "shopping_list": self._generate_shopping_list(all_recommendations),
                "source_mix": {
                    "cached_favorites": len(cached_recommendations),
                    "fresh_search": len(fresh_recommendations),
                    "total": len(all_recommendations)
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "location": user_location
            }
            
        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}", exc_info=True)
            # Return error instead of fallback
            return {
                "recommendations": [],
                "routine_suggestions": {},
                "shopping_list": {},
                "error": str(e),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "location": user_location
            }
    
    async def _get_perplexity_recommendations(
        self,
        skin_analysis: Dict[str, Any],
        user: UserModel,
        user_location: Dict[str, str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get fresh product recommendations from Perplexity API with retry logic and rate limiting
        """
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                if self.last_request_time:
                    time_since_last = datetime.now(timezone.utc) - self.last_request_time
                    if time_since_last.total_seconds() < self.delay_between_requests:
                        await asyncio.sleep(self.delay_between_requests - time_since_last.total_seconds())
                
                self.last_request_time = datetime.now(timezone.utc)
                
                # Build search query
                query = self._build_perplexity_query(skin_analysis, user, user_location, limit)
                
                # Make Perplexity API call with timeout
                response = await self.client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "sonar",  # Using Perplexity's search model (verified working)
                        "messages": [
                            {
                                "role": "system",
                                "content": self._get_system_prompt()
                            },
                            {
                                "role": "user", 
                                "content": query
                            }
                        ],
                        "max_tokens": 2000,  # Optimized for product recommendations
                        "temperature": 0.3,  # Lower for more consistent product results
                        "return_citations": True,
                        "return_related_questions": False
                    }
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Log the raw response for debugging
                logger.info(f"Perplexity API response status: {response.status_code}")
                logger.debug(f"Perplexity API raw response: {json.dumps(result, default=str)[:500]}...")
                
                # Validate response
                if not result.get("choices") or not result["choices"][0].get("message"):
                    logger.error(f"Invalid Perplexity response structure: {result.keys()}")
                    raise ValueError("Invalid response format from Perplexity API")
                
                # Parse and structure the response
                recommendations = self._parse_perplexity_response(
                    result, skin_analysis, user_location
                )
                
                if recommendations:
                    logger.info(f"Successfully retrieved {len(recommendations)} recommendations from Perplexity")
                    return recommendations
                else:
                    logger.warning("No recommendations parsed from Perplexity response")
                
            except httpx.TimeoutException as e:
                logger.warning(f"Perplexity API timeout (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text if hasattr(e.response, 'text') else str(e)
                logger.error(f"Perplexity API HTTP error (attempt {attempt + 1}/{max_retries}): {e.response.status_code}")
                logger.error(f"Perplexity error response: {error_detail}")
                if e.response.status_code in [429, 503] and attempt < max_retries - 1:
                    # Rate limit or service unavailable - retry
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    break
            except Exception as e:
                logger.error(f"Perplexity API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    break
        
        return []
    
    def _build_perplexity_query(
        self,
        skin_analysis: Dict[str, Any],
        user: UserModel,
        user_location: Dict[str, str],
        limit: int
    ) -> str:
        """
        Build comprehensive search query for Perplexity using the detailed prompt template
        """
        # Extract skin analysis scores from ORBO response
        # The structure is: skin_analysis -> orbo_response -> metrics
        orbo_data = skin_analysis.get("orbo_response", {})
        metrics = orbo_data.get("metrics", {})
        
        # If metrics not found, try direct access (for backwards compatibility)
        if not metrics and "metrics" in skin_analysis:
            metrics = skin_analysis.get("metrics", {})
        
        # Log what we found for debugging
        logger.info(f"ORBO metrics found: {metrics.keys() if metrics else 'No metrics found'}")
        
        # Map all 10 ORBO metrics directly - these are the actual metrics from ORBO
        # All scores are already in 0-100 format where 100 is best
        overall_score = metrics.get("overall_skin_health_score", 70)  # Metric 1: Overall skin health
        hydration_score = metrics.get("hydration", 70)                # Metric 2: Hydration level
        smoothness_score = metrics.get("smoothness", 70)              # Metric 3: Skin smoothness/texture
        radiance_score = metrics.get("radiance", 70)                  # Metric 4: Skin radiance/glow
        dark_spots_score = metrics.get("dark_spots", 70)              # Metric 5: Dark spots/pigmentation (100=no spots)
        firmness_score = metrics.get("firmness", 70)                  # Metric 6: Skin firmness/elasticity
        wrinkles_score = metrics.get("fine_lines_wrinkles", 70)       # Metric 7: Fine lines & wrinkles (100=no wrinkles)
        acne_score = metrics.get("acne", 70)                          # Metric 8: Acne/blemishes (100=clear skin)
        dark_circles_score = metrics.get("dark_circles", 70)          # Metric 9: Dark circles (100=no dark circles)
        redness_score = metrics.get("redness", 70)                    # Metric 10: Redness/sensitivity (100=no redness)
        
        # Extract required ingredients from ORBO analysis
        required_ingredients = orbo_data.get("recommended_ingredients", [])
        if not required_ingredients:
            # Build ingredient list based on metrics
            required_ingredients = self._determine_required_ingredients(metrics, skin_analysis)
        
        # User profile data - get from onboarding preferences
        age_range = self._format_age_range(user.onboarding.age_group) if user.onboarding else "25-34"
        skin_type = user.onboarding.skin_type if user.onboarding else skin_analysis.get("skin_type", "normal")
        gender = user.onboarding.gender if user.onboarding else "prefer_not_to_say"
        
        # Location and preferences
        city = user_location.get('city', 'Unknown City')
        state = user_location.get('state', 'Unknown State')
        user_location_str = f"{city}, {state}"
        
        # TODO: Get these from user preferences
        shopping_preference = "both"
        preferred_retailers = "Sephora, Ulta, Target, Amazon"
        local_climate = self._determine_climate(state)
        current_season = self._get_current_season()
        
        # Add more specific location context to the search
        zip_code = user_location.get('zip_code', '')
        
        # Determine main skin concerns based on lowest scores
        concerns_list = []
        if hydration_score < 70:
            concerns_list.append("dryness")
        if acne_score < 70:
            concerns_list.append("acne")
        if dark_spots_score < 70:
            concerns_list.append("hyperpigmentation")
        if wrinkles_score < 70:
            concerns_list.append("anti-aging")
        if redness_score < 70:
            concerns_list.append("sensitivity")
        
        if not concerns_list:
            concerns_list = ["general skincare maintenance"]
        
        concerns_str = " and ".join(concerns_list[:2])  # Focus on top 2 concerns
        
        # Create a simple, focused query similar to the successful example
        query = f"""List some {concerns_str} skincare products that can be purchased in {zip_code} area ({city}, {state}) with buy links, prices, description and online store availability in a table.

Focus on products for {skin_type} skin type, {age_range} age range.

User's skin analysis shows:

- Hydration: {hydration_score}/100
- Acne/Blemishes: {acne_score}/100  
- Dark spots: {dark_spots_score}/100
- Fine lines: {wrinkles_score}/100
- Redness: {redness_score}/100

Recommended ingredients: {', '.join(required_ingredients[:5]) if required_ingredients else 'Niacinamide, Hyaluronic Acid, Retinol, Vitamin C, Ceramides'}

Here is a table listing skincare products with the following columns:
| Product Name | Price | Description | Online Store Link | Store Availability |

Provide 5-7 specific products that:
1. Are currently available for purchase online with ACTUAL product links
2. Include exact prices (e.g., $24.00, $35.99)
3. Ship to {zip_code} or available in {city} stores
4. Match the user's {skin_type} skin type and {concerns_str} concerns
5. Include a mix of price points from drugstore to premium

IMPORTANT: Include REAL product URLs that can be clicked to purchase. For example:
- Sephora.com/product-name-here
- Ulta.com/specific-product
- Target.com/product-link
- Amazon.com/dp/product-id

Do NOT use placeholder links. Research actual products available now.
- Only recommend products that are actually available in the user's location
- Include a mix of price points unless budget is very restricted
- Prioritize products containing the required ingredients from the skin analysis
- Consider local climate and seasonal factors
- Provide specific retailer names and locations
- Include both immediate-action and long-term products
- Be sensitive to the user's experience level with skincare
- Mention any potential purging or adjustment periods
- Include gentle alternatives for sensitive skin types

Focus on finding {limit} highly-rated products that are currently in stock and match the skin analysis results."""
        
        return query
    
    def _get_system_prompt(self) -> str:
        """
        System prompt for Perplexity to ensure consistent, structured responses
        """
        return """You are SkinSense AI's intelligent beauty advisor, specialized in providing personalized skincare product recommendations based on comprehensive ORBO AI skin analysis data with 10 key metrics. Your role is to bridge the gap between professional skin analysis results and actionable, purchase-ready product recommendations.

SKIN ANALYSIS EXPERTISE:
You will receive 10 ORBO skin metrics (each scored 0-100, where 100 is best):
1. Overall Skin Health Score - General skin condition
2. Hydration - Moisture levels in the skin
3. Smoothness - Texture quality and smoothness
4. Radiance - Natural glow and luminosity
5. Dark Spots - Pigmentation uniformity (100 = no spots)
6. Firmness - Skin elasticity and tightness
7. Fine Lines & Wrinkles - Aging signs (100 = no wrinkles)
8. Acne - Blemish levels (100 = clear skin)
9. Dark Circles - Under-eye area condition (100 = no circles)
10. Redness - Sensitivity and irritation (100 = no redness)

RECOMMENDATION PRIORITIES:
- Focus on metrics scoring below 70/100 as priority concerns
- Match products to address the lowest-scoring metrics first
- Recommend ingredients scientifically proven for each specific metric
- Consider interactions between different skin concerns

IMPORTANT GUIDELINES:
"""
    
    def _parse_perplexity_response(
        self,
        response: Dict[str, Any],
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Parse Perplexity response into structured product recommendations
        """
        try:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = response.get("citations", [])
            
            # Log the raw content for debugging
            logger.info(f"[PERPLEXITY DEBUG] Raw content first 500 chars: {content[:500]}")
            
            # Extract structured sections from the response
            recommendations = self._extract_structured_products(
                content, skin_analysis, user_location, citations
            )
            
            logger.info(f"[PERPLEXITY DEBUG] Extracted {len(recommendations)} products")
            if recommendations:
                logger.info(f"[PERPLEXITY DEBUG] First product: {json.dumps(recommendations[0], default=str)[:300]}")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to parse Perplexity response: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _extract_structured_products(
        self,
        content: str,
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str],
        citations: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured product data from Perplexity's comprehensive response
        """
        products = []
        
        # Parse the structured response sections
        sections = self._parse_response_sections(content)
        
        # Extract products from the PRODUCT RECOMMENDATIONS section
        if sections.get("product_recommendations"):
            products_text = sections["product_recommendations"]
            products = self._parse_product_entries(products_text, skin_analysis)
        
        # If structured parsing fails, fall back to simple parsing
        if not products:
            products = self._extract_products_from_text_simple(
                content, skin_analysis, user_location, citations
            )
        
        # If all parsing fails, use fallback products
        if not products:
            products = self._create_fallback_products(skin_analysis, user_location)
        
        return products[:7]  # Return up to 7 products
    
    def _parse_response_sections(self, content: str) -> Dict[str, str]:
        """
        Parse the response into structured sections based on the prompt template
        """
        sections = {}
        current_section = None
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            # Check for section headers
            if "**PRIORITY ANALYSIS**" in line:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "priority_analysis"
                current_content = []
            elif "**PRODUCT RECOMMENDATIONS**" in line:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "product_recommendations"
                current_content = []
            elif "**ROUTINE RECOMMENDATIONS**" in line:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "routine_recommendations"
                current_content = []
            elif "**LOCAL AVAILABILITY**" in line:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "local_availability"
                current_content = []
            elif "**BUDGET OPTIMIZATION**" in line:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "budget_optimization"
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # Add the last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _parse_product_entries(self, products_text: str, skin_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse individual product entries from the recommendations section
        """
        products = []
        
        # Split by product entries (usually separated by double newlines or numbered)
        product_blocks = re.split(r'\n\s*\n', products_text)
        
        for block in product_blocks:
            if not block.strip():
                continue
            
            product = self._extract_product_details(block, skin_analysis)
            if product.get("name"):
                products.append(product)
        
        return products
    
    def _extract_product_details(self, block: str, skin_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract detailed product information from a product block
        """
        product = {}
        
        # Extract product name and brand
        name_match = re.search(r'\*\*Product Name & Brand\*\*:?\s*(.+)', block, re.IGNORECASE)
        if name_match:
            product['name'] = name_match.group(1).strip()
            product['brand'] = self._extract_brand(product['name'])
        
        # Extract key ingredients
        ingredients_match = re.search(r'\*\*Key Active Ingredients\*\*:?\s*(.+)', block, re.IGNORECASE)
        if ingredients_match:
            ingredients_text = ingredients_match.group(1).strip()
            product['key_ingredients'] = [ing.strip() for ing in re.split(r'[,;]', ingredients_text)]
        
        # Extract price range
        price_match = re.search(r'\*\*Price Range\*\*:?\s*(.+)', block, re.IGNORECASE)
        if price_match:
            product['price_range'] = price_match.group(1).strip()
        
        # Extract why it's recommended
        why_match = re.search(r'\*\*Why It\'s Recommended\*\*:?\s*(.+)', block, re.IGNORECASE)
        if why_match:
            product['match_reasoning'] = why_match.group(1).strip()
        
        # Extract usage instructions
        usage_match = re.search(r'\*\*Usage Instructions\*\*:?\s*(.+)', block, re.IGNORECASE)
        if usage_match:
            product['usage_instructions'] = usage_match.group(1).strip()
        
        # Extract where to buy
        where_match = re.search(r'\*\*Where to Buy Locally\*\*:?\s*(.+)', block, re.IGNORECASE)
        if where_match:
            stores_text = where_match.group(1).strip()
            product['availability'] = {
                'local_stores': self._extract_stores_from_text(stores_text, local=True),
                'online_stores': self._extract_stores_from_text(stores_text, local=False)
            }
        
        # Add metadata
        if product.get("name"):
            product['id'] = f"perplexity_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{hash(product['name']) % 10000}"
            product['category'] = self._guess_category(product['name'])
            product['compatibility_score'] = self._estimate_compatibility_score(product, skin_analysis)
            product['source'] = "perplexity_search"
            product['search_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        return product
    
    def _extract_stores_from_text(self, text: str, local: bool = True) -> List[str]:
        """
        Extract store names from text
        """
        stores = []
        
        if local:
            # Local physical stores
            local_stores = ['CVS', 'Target', 'Walgreens', 'Walmart', 'Ulta', 'Sephora', 'Rite Aid']
            for store in local_stores:
                if store.lower() in text.lower():
                    stores.append(store)
        else:
            # Online stores
            online_keywords = ['amazon', 'sephora.com', 'ulta.com', 'target.com', '.com', 'online']
            if any(keyword in text.lower() for keyword in online_keywords):
                if 'amazon' in text.lower():
                    stores.append('Amazon')
                if 'sephora' in text.lower():
                    stores.append('Sephora.com')
                if 'ulta' in text.lower():
                    stores.append('Ulta.com')
                if 'target' in text.lower():
                    stores.append('Target.com')
        
        return list(set(stores))[:3]
    
    def _extract_products_from_text_simple(
        self,
        content: str,
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str],
        citations: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Simple fallback parser for less structured responses
        """
        products = []
        
        logger.info(f"[PERPLEXITY DEBUG] Starting simple extraction, content has pipes: {'|' in content}, has asterisks: {'**' in content}")
        
        # First, try to parse if content has pipe separators (common format)
        if '|' in content:
            logger.info("[PERPLEXITY DEBUG] Attempting pipe-separated format parsing")
            products = self._parse_pipe_separated_format(content, skin_analysis)
            if products:
                logger.info(f"[PERPLEXITY DEBUG] Successfully parsed {len(products)} products from pipe format")
                return products
        
        # Simple pattern matching to find product mentions
        lines = content.split('\n')
        current_product = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for product names (usually contain brand names)
            if any(brand in line.lower() for brand in ['cerave', 'neutrogena', 'olay', 'the ordinary', 'paula', 'la roche', 'cetaphil', 'aveeno']):
                if current_product:
                    products.append(self._format_product_recommendation(current_product, skin_analysis))
                    current_product = {}
                
                # Clean up the name if it contains markdown or pipes
                clean_name = line.replace('**', '').replace('*', '').strip()
                if '|' in clean_name:
                    # Split by pipe and take the first meaningful part
                    parts = [p.strip() for p in clean_name.split('|') if p.strip()]
                    if parts:
                        # If first part is just a category, use the second part as name
                        if len(parts) > 1 and any(cat in parts[0].lower() for cat in ['cleanser', 'moisturizer', 'serum', 'sunscreen', 'treatment']):
                            clean_name = parts[1]
                        else:
                            clean_name = parts[0]
                
                current_product['raw_text'] = line
                current_product['name'] = clean_name
            
            elif '$' in line:
                current_product['price_info'] = line
            
            elif any(store in line.lower() for store in ['amazon', 'sephora', 'ulta', 'target', 'cvs', 'walgreens']):
                if 'availability' not in current_product:
                    current_product['availability'] = []
                current_product['availability'].append(line)
        
        # Add the last product
        if current_product:
            products.append(self._format_product_recommendation(current_product, skin_analysis))
        
        logger.info(f"[PERPLEXITY DEBUG] Simple extraction found {len(products)} products")
        return products
    
    def _extract_retailer_from_url(self, url: str) -> str:
        """Extract retailer name from URL"""
        if not url:
            return None
            
        url_lower = url.lower()
        if 'paulaschoice' in url_lower:
            return "Paula's Choice"
        elif 'sephora' in url_lower:
            return 'Sephora'
        elif 'ulta' in url_lower:
            return 'Ulta'
        elif 'amazon' in url_lower:
            return 'Amazon'
        elif 'target' in url_lower:
            return 'Target'
        elif 'cvs' in url_lower:
            return 'CVS'
        elif 'walgreens' in url_lower:
            return 'Walgreens'
        elif 'walmart' in url_lower:
            return 'Walmart'
        else:
            # Try to extract domain name
            domain_match = re.search(r'(?:https?://)?(?:www\.)?([^/.]+)', url)
            if domain_match:
                return domain_match.group(1).capitalize()
        return None
    
    def _extract_url_from_text(self, text: str) -> str:
        """Extract URL from text that might contain markdown or plain URLs"""
        if not text:
            return None
            
        # Try different URL patterns
        url_patterns = [
            r'\[([^\]]+)\]\(([^\)]+)\)',  # Markdown link [text](url)
            r'(https?://[^\s\)]+)',  # Plain URL starting with http
            r'(www\.[^\s\)]+)',  # URL starting with www
            r'([a-zA-Z0-9\-]+\.com[^\s\)]*)'  # Domain.com pattern
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) > 1:
                    # Markdown link - return the URL part
                    return match.group(2)
                else:
                    # Plain URL
                    url = match.group(1)
                    # Add https:// if missing
                    if not url.startswith('http'):
                        url = 'https://' + url
                    return url
        
        return None
    
    def _parse_pipe_separated_format(self, content: str, skin_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse content that appears to be in pipe-separated table format
        Example: | Product Name | Price | Description | Online Store Link | Store Availability |
        """
        products = []
        
        # Split by newlines to get individual product lines
        lines = content.split('\n')
        
        for line in lines:
            if not line.strip() or not '|' in line:
                continue
            
            # Remove markdown formatting
            line = line.replace('**', '').strip()
            
            # Split by pipe separator
            parts = [p.strip() for p in line.split('|') if p.strip()]
            
            # Skip header rows and separator rows
            if len(parts) > 0:
                first_col = parts[0].strip()
                first_col_lower = first_col.lower()
                
                # Skip header rows
                if any(header in first_col_lower for header in ['product name', 'product', 'item', 'name']):
                    logger.info(f"[PERPLEXITY DEBUG] Skipping header row: {first_col}")
                    continue
                
                # Skip separator rows (rows with only dashes, equals, or underscores)
                if all(c in ['-', '=', '_', ' '] for c in first_col):
                    logger.info(f"[PERPLEXITY DEBUG] Skipping separator row: {first_col[:20]}...")
                    continue
                
                # Skip empty or too short names
                if len(first_col) < 3:
                    logger.info(f"[PERPLEXITY DEBUG] Skipping invalid row with short name: {first_col}")
                    continue
            
            # Expecting format: Product Name | Price | Description | Online Store Link | Store Availability
            if len(parts) >= 3:
                product = {}
                
                # Parse based on table columns
                if parts[0]:  # Product name
                    product['name'] = parts[0].strip()
                    product['brand'] = self._extract_brand(parts[0])
                
                if len(parts) > 1:  # Price column
                    price_text = parts[1].strip()
                    if '$' in price_text:
                        product['price'] = price_text
                        # Extract numeric price
                        price_match = re.search(r'\$([\d.]+)', price_text)
                        if price_match:
                            product['current_price'] = float(price_match.group(1))
                    else:
                        # Sometimes price might be in a different format or missing
                        product['price'] = price_text if price_text and price_text.lower() != 'price' else None
                
                if len(parts) > 2:  # Description column
                    desc_text = parts[2].strip()
                    # Check if this looks like a URL (sometimes URLs appear in description column)
                    if 'http' in desc_text or '.com' in desc_text:
                        # This is likely a URL, not a description
                        product['affiliate_link'] = self._extract_url_from_text(desc_text)
                        product['description'] = None  # No real description
                    else:
                        product['description'] = desc_text
                        # Try to extract key ingredients from description
                        product['key_ingredients'] = self._extract_ingredients_from_text(desc_text)
                
                if len(parts) > 3:  # Online Store Link column
                    link_text = parts[3].strip()
                    # Only process if we haven't already found a URL in description column
                    if 'affiliate_link' not in product:
                        extracted_url = self._extract_url_from_text(link_text)
                        if extracted_url:
                            product['affiliate_link'] = extracted_url
                            # Extract retailer name from URL or link text
                            if 'paulaschoice' in extracted_url.lower():
                                product['retailer'] = "Paula's Choice"
                            elif 'sephora' in extracted_url.lower():
                                product['retailer'] = 'Sephora'
                            elif 'ulta' in extracted_url.lower():
                                product['retailer'] = 'Ulta'
                            elif 'amazon' in extracted_url.lower():
                                product['retailer'] = 'Amazon'
                            elif 'target' in extracted_url.lower():
                                product['retailer'] = 'Target'
                            else:
                                # Try to extract from markdown link text
                                md_match = re.search(r'\[([^\]]+)\]', link_text)
                                if md_match:
                                    product['retailer'] = md_match.group(1)
                        elif link_text and link_text.lower() not in ['online store link', 'link', 'url']:
                            # If no URL but has text, it might be store name
                            product['retailer'] = link_text
                
                if len(parts) > 4:  # Store Availability column
                    availability_text = parts[4].strip()
                    local_stores = []
                    online_stores = []
                    
                    # Parse store availability
                    store_names = ['Sephora', 'Ulta', 'Target', 'CVS', 'Walgreens', 'Walmart', 'Amazon', "Paula's Choice"]
                    for store in store_names:
                        if store.lower() in availability_text.lower():
                            if 'online' in availability_text.lower() or '.com' in availability_text.lower():
                                online_stores.append(store)
                            elif 'store' in availability_text.lower() or 'location' in availability_text.lower():
                                local_stores.append(store)
                            else:
                                # Default to online if not specified
                                online_stores.append(store)
                    
                    # If we have a retailer from the URL, ensure it's in online stores
                    if product.get('retailer') and product['retailer'] not in online_stores:
                        online_stores.append(product['retailer'])
                    
                    product['availability'] = {
                        'local_stores': local_stores,
                        'online_stores': online_stores,
                        'location_note': availability_text if availability_text and availability_text.lower() != 'store availability' else None
                    }
                
                
                if len(parts) > 4:  # Timeline
                    product['expected_results'] = parts[4]
                
                if len(parts) > 5:  # Where to buy
                    stores_text = parts[5]
                    product['availability'] = {
                        'local_stores': self._extract_stores_from_text(stores_text, local=True),
                        'online_stores': self._extract_stores_from_text(stores_text, local=False)
                    }
                    # Generate better product search URLs if no direct link found
                    if not product.get('affiliate_link'):
                        product_name = product.get('name', '')
                        brand = product.get('brand', '')
                        search_query = f"{brand} {product_name}".strip().replace(' ', '+')
                        
                        if 'amazon' in stores_text.lower():
                            product['affiliate_link'] = f'https://www.amazon.com/s?k={search_query}'
                        elif 'sephora' in stores_text.lower():
                            product['affiliate_link'] = f'https://www.sephora.com/search?keyword={search_query}'
                        elif 'ulta' in stores_text.lower():
                            product['affiliate_link'] = f'https://www.ulta.com/search?q={search_query}'
                        elif 'target' in stores_text.lower():
                            product['affiliate_link'] = f'https://www.target.com/s?searchTerm={search_query}'
                        elif 'cvs' in stores_text.lower():
                            product['affiliate_link'] = f'https://www.cvs.com/search?searchTerm={search_query}'
                        else:
                            # Default to Amazon search if no specific store mentioned
                            product['affiliate_link'] = f'https://www.amazon.com/s?k={search_query}'
                
                if len(parts) > 6:  # Price
                    product['price_range'] = self._extract_price_range(parts[6])
                
                if len(parts) > 7:  # Usage instructions
                    product['usage_instructions'] = parts[7]
                
                # Validate product has required fields before adding
                if product.get('name') and not any(header in product['name'].lower() for header in ['product name', 'description', 'price', 'store']):
                    # Add metadata
                    product['id'] = f"perplexity_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{hash(product.get('name', '')) % 10000}"
                    product['compatibility_score'] = self._estimate_compatibility_score(product, skin_analysis)
                    product['source'] = 'perplexity_search'
                    product['search_timestamp'] = datetime.now(timezone.utc).isoformat()
                    
                    products.append(product)
                else:
                    logger.info(f"[PERPLEXITY DEBUG] Skipping invalid product: {product.get('name', 'Unknown')}")
        
        return products
    
    def _format_product_recommendation(
        self,
        raw_product: Dict[str, Any],
        skin_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format parsed product into standardized recommendation structure
        """
        # Extract current price if available
        current_price = raw_product.get('current_price')
        price_str = raw_product.get('price', '')
        
        # Try to extract price from price string if current_price is not set
        if not current_price and price_str and '$' in price_str:
            price_match = re.search(r'\$([\d.]+)', price_str)
            if price_match:
                try:
                    current_price = float(price_match.group(1))
                except ValueError:
                    pass
        
        # If still no price, try to parse from price_range
        if not current_price and raw_product.get('price_range'):
            price_range_str = raw_product.get('price_range', '')
            if '$' in price_range_str:
                # Try to get the first price from range
                price_match = re.search(r'\$([\d.]+)', price_range_str)
                if price_match:
                    try:
                        current_price = float(price_match.group(1))
                    except ValueError:
                        pass
        
        # Format the product with all available data - ensure required fields are never null
        product_name = raw_product.get('name', 'Unknown Product')
        
        # Ensure we have a proper description (not a URL)
        description = raw_product.get('description')
        if description and ('http' in description or '.com' in description):
            # If description contains URL, it's not a real description
            description = f"High-quality skincare product targeting specific skin concerns"
        
        # Generate URL once
        generated_url = self._generate_product_url(raw_product)
        
        formatted = {
            "id": f"perplexity_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{hash(product_name) % 10000}",
            "name": product_name,
            "brand": raw_product.get('brand') or self._extract_brand(product_name) or 'Unknown Brand',
            "category": raw_product.get('category') or self._guess_category(product_name) or 'skincare',
            "description": description,
            "imageUrl": raw_product.get('image_url') or self._generate_product_image_url(raw_product),
            "currentPrice": current_price,
            "priceRange": price_str or raw_product.get('price_range') or "$15-30",  # Always provide a price range
            "availability": raw_product.get('availability') or {
                "local_stores": self._extract_local_stores(raw_product.get('availability', [])),
                "online_stores": self._extract_online_stores(raw_product.get('availability', []))
            },
            "matchReasoning": raw_product.get('match_reasoning') or self._generate_match_reasoning(raw_product, skin_analysis),
            "compatibilityScore": raw_product.get('compatibility_score') or self._estimate_compatibility_score(raw_product, skin_analysis),
            "usageInstructions": raw_product.get('usage_instructions') or self._generate_usage_instructions(raw_product),
            "keyIngredients": raw_product.get('key_ingredients') or self._extract_key_ingredients(raw_product),
            # Use camelCase for Flutter frontend compatibility
            "affiliateLink": raw_product.get('affiliate_link') or generated_url,
            "productUrl": generated_url,  
            "trackingLink": raw_product.get('tracking_link') or generated_url,
            "retailer": raw_product.get('retailer') or self._extract_retailer_from_url(raw_product.get('affiliate_link')),
            "source": "perplexity_search",
            "searchTimestamp": datetime.now(timezone.utc).isoformat(),
            "inStock": True,  # Assume in stock if returned by search
            "raw_data": raw_product
        }
        
        # Only include non-None values but ensure required fields are always present
        cleaned = {k: v for k, v in formatted.items() if v is not None}
        
        # Ensure required fields are ALWAYS present
        if 'name' not in cleaned:
            cleaned['name'] = 'Unknown Product'
        if 'brand' not in cleaned:
            cleaned['brand'] = 'Unknown Brand'
        if 'category' not in cleaned:
            cleaned['category'] = 'skincare'
        
        # Log the product for debugging
        logger.info(f"[PERPLEXITY DEBUG] Formatted product: name={cleaned.get('name')}, currentPrice={cleaned.get('currentPrice')}, priceRange={cleaned.get('priceRange')}")
        
        return cleaned
    
    async def _get_cached_recommendations(
        self,
        user: UserModel,
        skin_analysis: Dict[str, Any],
        db: Database,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get cached product recommendations from user's favorites
        """
        try:
            # Find user's successful product interactions
            cached_products = list(db.user_product_interactions.find({
                "user_id": user.id,
                "interaction_type": {"$in": ["liked", "saved", "purchased"]},
                "created_at": {
                    "$gte": datetime.now(timezone.utc) - timedelta(hours=self.cache_ttl_hours)
                }
            }).sort("created_at", -1).limit(limit))
            
            # Filter cached products that match current skin analysis
            relevant_cached = []
            for cached in cached_products:
                if self._is_product_relevant(cached.get("product_data", {}), skin_analysis):
                    product = cached["product_data"]
                    product["source"] = "user_favorites"
                    product["last_interaction"] = cached["created_at"].isoformat()
                    relevant_cached.append(product)
            
            return relevant_cached
            
        except Exception as e:
            logger.error(f"Failed to get cached recommendations: {e}")
            return []
    
    async def _cache_recommendations(
        self,
        user_id: ObjectId,
        recommendations: List[Dict[str, Any]],
        skin_analysis: Dict[str, Any],
        db: Database
    ):
        """
        Cache successful recommendations for future use
        """
        try:
            cache_data = {
                "user_id": user_id,
                "recommendations": recommendations,
                "skin_analysis_summary": {
                    "skin_type": skin_analysis.get("skin_type"),
                    "concerns": skin_analysis.get("concerns", []),
                    "scores": skin_analysis.get("scores", {})
                },
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=self.cache_ttl_hours)
            }
            
            db.recommendation_cache.insert_one(cache_data)
            
            # Clean up old cache entries
            db.recommendation_cache.delete_many({
                "user_id": user_id,
                "expires_at": {"$lt": datetime.now(timezone.utc)}
            })
            
        except Exception as e:
            logger.error(f"Failed to cache recommendations: {e}")
    
    async def track_product_interaction(
        self,
        user_id: ObjectId,
        product_data: Dict[str, Any],
        interaction_type: str,
        db: Database,
        skin_analysis_id: Optional[ObjectId] = None
    ):
        """
        Track user interactions with recommended products for future caching
        """
        try:
            interaction_data = {
                "user_id": user_id,
                "product_data": product_data,
                "interaction_type": interaction_type,  # "viewed", "liked", "saved", "purchased"
                "skin_analysis_id": skin_analysis_id,
                "created_at": datetime.now(timezone.utc)
            }
            
            db.user_product_interactions.insert_one(interaction_data)
            
            # If this is a positive interaction, boost this product for future recommendations
            if interaction_type in ["liked", "saved", "purchased"]:
                await self._boost_product_score(user_id, product_data, db)
                
        except Exception as e:
            logger.error(f"Failed to track product interaction: {e}")
    
    def _create_fallback_products(
        self,
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Create location-aware fallback recommendations when Perplexity search fails
        """
        skin_type = skin_analysis.get("skin_type", "combination")
        concerns = skin_analysis.get("concerns", ["hydration"])
        
        # Get location details for customization
        city = user_location.get('city', 'your area')
        state = user_location.get('state', 'US')
        zip_code = user_location.get('zip_code', '')
        
        # Customize store availability based on region
        local_stores = self._get_regional_stores(state)
        
        fallback_products = [
            {
                "id": "fallback_001",
                "name": "CeraVe Hydrating Cleanser",
                "brand": "CeraVe",
                "category": "cleanser",
                "price_range": "$12-16",
                "availability": {
                    "local_stores": local_stores,
                    "online_stores": ["Amazon", "Target.com", "CVS.com"],
                    "location_note": f"Available in most stores near {city}, {state}"
                },
                "match_reasoning": f"Gentle cleanser perfect for {skin_type} skin, contains ceramides for hydration",
                "compatibility_score": 8.5,
                "source": "fallback_database",
                "key_ingredients": ["Ceramides", "Hyaluronic Acid"],
                "usage_instructions": "Apply to damp skin, massage gently, rinse with lukewarm water. Use morning and evening."
            },
            {
                "id": "fallback_002", 
                "name": "The Ordinary Niacinamide 10% + Zinc 1%",
                "brand": "The Ordinary",
                "category": "serum",
                "price_range": "$6-8",
                "availability": {
                    "local_stores": [store for store in ["Ulta", "Sephora"] if store in local_stores or "Ulta" in local_stores],
                    "online_stores": ["Amazon", "Ulta.com", "Sephora.com"],
                    "location_note": f"Check availability at beauty stores in {city}"
                },
                "match_reasoning": f"Addresses pore concerns common in {skin_type} skin, budget-friendly option",
                "compatibility_score": 8.2,
                "source": "fallback_database",
                "key_ingredients": ["Niacinamide", "Zinc"],
                "usage_instructions": "Apply 2-3 drops to clean skin before moisturizer. Start with evening use."
            },
            {
                "id": "fallback_003",
                "name": "Neutrogena Hydro Boost Gel-Cream",
                "brand": "Neutrogena",
                "category": "moisturizer",
                "price_range": "$15-20",
                "availability": {
                    "local_stores": local_stores,
                    "online_stores": ["Amazon", "Target.com", "Walmart.com"],
                    "location_note": f"Widely available in {city}, {state}"
                },
                "match_reasoning": f"Lightweight hydration ideal for {skin_type} skin, non-comedogenic formula",
                "compatibility_score": 8.0,
                "source": "fallback_database",
                "key_ingredients": ["Hyaluronic Acid", "Glycerin"],
                "usage_instructions": "Apply to clean skin as the last step of your routine. Use morning and evening."
            },
            {
                "id": "fallback_004",
                "name": "La Roche-Posay Anthelios SPF 60",
                "brand": "La Roche-Posay",
                "category": "sunscreen",
                "price_range": "$20-25",
                "availability": {
                    "local_stores": [store for store in local_stores if store in ["CVS", "Walgreens", "Ulta"]],
                    "online_stores": ["Amazon", "CVS.com", "LaRoche-Posay.com"],
                    "location_note": f"Available at pharmacies in {city}, {state}"
                },
                "match_reasoning": "Essential daily sun protection, lightweight formula suitable for all skin types",
                "compatibility_score": 9.0,
                "source": "fallback_database",
                "key_ingredients": ["Avobenzone", "Homosalate", "Octisalate"],
                "usage_instructions": "Apply generously 15 minutes before sun exposure. Reapply every 2 hours."
            }
        ]
        
        return fallback_products[:3]
    
    # Helper methods for parsing and formatting
    def _generate_product_image_url(self, product: Dict[str, Any]) -> str:
        """
        Generate a placeholder product image URL based on brand/category
        Uses Lorem Picsum for placeholder images with deterministic seeds
        """
        # If we already have an image URL, return it
        if product.get('image_url'):
            return product['image_url']
        
        # Generate a deterministic seed based on product name + brand
        import hashlib
        seed_text = f"{product.get('brand', '')}_{product.get('name', '')}"
        seed = int(hashlib.md5(seed_text.encode()).hexdigest()[:6], 16) % 1000
        
        # Use Lorem Picsum with seed for consistent images
        return f"https://picsum.photos/seed/{seed}/400/400"
    
    def _generate_product_url(self, product: Dict[str, Any]) -> str:
        """
        Generate a product URL for Shop Now button
        Priority: affiliate_link > tracking_link > retailer website > search URL
        """
        # Check if we have an affiliate link
        if product.get('affiliate_link'):
            return product['affiliate_link']
        
        # Check if we have a tracking link
        if product.get('tracking_link'):
            return product['tracking_link']
        
        # Generate URL based on retailer
        retailer = product.get('retailer', '').lower()
        product_name = product.get('name', '').replace(' ', '+')
        brand = product.get('brand', '').replace(' ', '+')
        
        if 'amazon' in retailer:
            return f"https://www.amazon.com/s?k={brand}+{product_name}"
        elif 'sephora' in retailer:
            return f"https://www.sephora.com/search?keyword={brand}%20{product_name}"
        elif 'ulta' in retailer:
            return f"https://www.ulta.com/search?q={brand}+{product_name}"
        elif 'target' in retailer:
            return f"https://www.target.com/s?searchTerm={brand}+{product_name}"
        elif 'dermalogica' in retailer:
            return "https://www.dermalogica.com"
        elif 'ordinary' in retailer or 'deciem' in retailer:
            return "https://theordinary.com"
        elif 'cerave' in retailer:
            return f"https://www.cerave.com/search?q={product_name}"
        elif retailer:
            # Try to construct a URL from retailer name
            retailer_clean = retailer.replace(' ', '').replace('.com', '')
            return f"https://www.{retailer_clean}.com"
        else:
            # Default to Google search
            return f"https://www.google.com/search?q={brand}+{product_name}+buy"
    
    def _extract_brand(self, product_name: str) -> str:
        """Extract brand name from product text"""
        common_brands = ['CeraVe', 'Neutrogena', 'Olay', 'The Ordinary', 'Paula\'s Choice', 
                        'Clinique', 'Cetaphil', 'La Roche-Posay', 'Aveeno', 'Differin']
        
        for brand in common_brands:
            if brand.lower() in product_name.lower():
                return brand
        
        # Try to extract first word as brand
        words = product_name.split()
        return words[0] if words else "Unknown Brand"
    
    def _guess_category(self, product_name: str) -> str:
        """Guess product category from name"""
        name_lower = product_name.lower()
        
        if any(word in name_lower for word in ['cleanser', 'wash', 'foam']):
            return 'cleanser'
        elif any(word in name_lower for word in ['serum', 'treatment']):
            return 'serum' 
        elif any(word in name_lower for word in ['moisturizer', 'cream', 'lotion']):
            return 'moisturizer'
        elif any(word in name_lower for word in ['sunscreen', 'spf', 'sun']):
            return 'sunscreen'
        elif any(word in name_lower for word in ['toner', 'essence']):
            return 'toner'
        else:
            return 'treatment'
    
    def _extract_ingredients_from_text(self, text: str) -> List[str]:
        """Extract ingredient names from description text"""
        ingredients = []
        # Common skincare ingredients to look for
        common_ingredients = [
            'Niacinamide', 'Hyaluronic Acid', 'Retinol', 'Vitamin C', 'Ceramides',
            'Salicylic Acid', 'Glycolic Acid', 'Peptides', 'Caffeine', 'Zinc',
            'Vitamin E', 'Squalane', 'Glycerin', 'AHA', 'BHA', 'PHA',
            'Benzoyl Peroxide', 'Adapalene', 'Azelaic Acid', 'Kojic Acid'
        ]
        
        text_lower = text.lower()
        for ingredient in common_ingredients:
            if ingredient.lower() in text_lower:
                ingredients.append(ingredient)
        
        return ingredients[:5]  # Return top 5 ingredients found
    
    def _extract_price_range(self, price_text: str) -> str:
        """Extract price range from text"""
        if '$' in price_text:
            return price_text
        return "$15-30"  # Default range
    
    def _extract_local_stores(self, availability: List[str]) -> List[str]:
        """Extract local store information"""
        local_stores = []
        store_names = ['CVS', 'Target', 'Walgreens', 'Walmart', 'Ulta', 'Sephora']
        
        for line in availability:
            for store in store_names:
                if store.lower() in line.lower() and 'online' not in line.lower():
                    local_stores.append(store)
        
        return list(set(local_stores))[:3]  # Unique stores, max 3
    
    def _extract_online_stores(self, availability: List[str]) -> List[str]:
        """Extract online store information"""
        online_stores = []
        online_keywords = ['amazon', '.com', 'online', 'website']
        
        for line in availability:
            if any(keyword in line.lower() for keyword in online_keywords):
                if 'amazon' in line.lower():
                    online_stores.append('Amazon')
                elif 'sephora' in line.lower():
                    online_stores.append('Sephora.com')
                elif 'ulta' in line.lower():
                    online_stores.append('Ulta.com')
                elif 'target' in line.lower():
                    online_stores.append('Target.com')
        
        return list(set(online_stores))[:3]  # Unique stores, max 3
    
    def _generate_match_reasoning(self, product: Dict[str, Any], skin_analysis: Dict[str, Any]) -> str:
        """Generate why this product matches the user's skin analysis"""
        skin_type = skin_analysis.get("skin_type", "your skin type")
        concerns = skin_analysis.get("concerns", [])
        
        if concerns:
            return f"Great for {skin_type} skin, specifically targets {concerns[0]} concerns"
        else:
            return f"Perfect daily essential for {skin_type} skin"
    
    def _estimate_compatibility_score(self, product: Dict[str, Any], skin_analysis: Dict[str, Any]) -> float:
        """Estimate compatibility score based on analysis"""
        base_score = 7.5
        
        # Boost score if product seems to match concerns
        concerns = skin_analysis.get("concerns", [])
        product_text = str(product.get("name", "")).lower() + str(product.get("raw_text", "")).lower()
        
        for concern in concerns:
            if concern.lower() in product_text:
                base_score += 0.5
        
        return min(10.0, base_score)
    
    def _generate_usage_instructions(self, product: Dict[str, Any]) -> str:
        """Generate basic usage instructions"""
        category = self._guess_category(product.get('name', ''))
        
        instructions = {
            "cleanser": "Apply to damp skin, massage gently, rinse with lukewarm water. Use morning and evening.",
            "serum": "Apply 2-3 drops to clean skin before moisturizer. Start with evening use.",
            "moisturizer": "Apply to clean skin as the last step of your routine. Use morning and evening.", 
            "sunscreen": "Apply generously 15 minutes before sun exposure. Reapply every 2 hours.",
            "toner": "Apply to clean skin with cotton pad or gentle patting motions.",
            "treatment": "Follow package instructions for best results."
        }
        
        return instructions.get(category, "Follow package instructions for best results.")
    
    def _extract_key_ingredients(self, product: Dict[str, Any]) -> List[str]:
        """Extract key ingredients from product text"""
        # This would be more sophisticated in production
        common_ingredients = ['niacinamide', 'hyaluronic acid', 'ceramides', 'retinol', 
                            'vitamin c', 'salicylic acid', 'glycolic acid', 'peptides']
        
        product_text = str(product.get("name", "")).lower() + str(product.get("raw_text", "")).lower()
        found_ingredients = [ing.title() for ing in common_ingredients if ing in product_text]
        
        return found_ingredients[:3] if found_ingredients else ["See product details"]
    
    def _is_product_relevant(self, product: Dict[str, Any], skin_analysis: Dict[str, Any]) -> bool:
        """Check if cached product is still relevant to current skin analysis"""
        # Simple relevance check - in production, this would be more sophisticated
        return True  # For now, assume all cached products are relevant
    
    async def _boost_product_score(self, user_id: Any, product_data: Dict[str, Any], db: Database):
        """Boost product score for future recommendations"""
        # This is a placeholder - implement scoring logic as needed
        pass
    
    def _build_routine_from_products(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build AM/PM routine suggestions from recommended products"""
        routine = {"morning": [], "evening": []}
        
        # Sort products by typical routine order
        order = {"cleanser": 1, "toner": 2, "serum": 3, "moisturizer": 4, "sunscreen": 5}
        
        for product in products:
            category = product.get("category", "treatment")
            step = {
                "product": product["name"],
                "category": category,
                "step_order": order.get(category, 6),
                "instructions": product.get("usage_instructions", "")
            }
            
            if category == "sunscreen":
                routine["morning"].append(step)
            elif category in ["cleanser", "moisturizer"]:
                routine["morning"].append(step)
                routine["evening"].append(step)
            else:
                # Serums and treatments primarily in evening
                routine["evening"].append(step)
        
        # Sort by step order
        routine["morning"].sort(key=lambda x: x["step_order"])
        routine["evening"].sort(key=lambda x: x["step_order"])
        
        return routine
    
    def _generate_shopping_list(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate prioritized shopping list with cost estimates"""
        essential_categories = ["cleanser", "moisturizer", "sunscreen"]
        treatment_categories = ["serum", "treatment", "toner"]
        
        shopping_list = {
            "immediate_priorities": [],
            "next_additions": [],
            "total_estimated_cost": "$0-0"
        }
        
        total_min = 0
        total_max = 0
        
        for product in products:
            category = product.get("category", "")
            price_range = product.get("price_range", "$15-25")
            
            # Extract price numbers
            prices = re.findall(r'\$(\d+)', price_range)
            if len(prices) >= 2:
                min_price, max_price = int(prices[0]), int(prices[1])
            elif len(prices) == 1:
                min_price = max_price = int(prices[0])
            else:
                min_price, max_price = 15, 25
            
            total_min += min_price
            total_max += max_price
            
            item = {
                "product": product["name"],
                "category": category,
                "price_range": price_range,
                "where_to_buy": product.get("availability", {}).get("online_stores", []),
                "priority_reason": f"Essential {category}" if category in essential_categories else f"Targets specific concerns"
            }
            
            if category in essential_categories:
                shopping_list["immediate_priorities"].append(item)
            else:
                shopping_list["next_additions"].append(item)
        
        shopping_list["total_estimated_cost"] = f"${total_min}-{total_max}"
        
        return shopping_list
    
    async def _get_fallback_recommendations(
        self, 
        user: UserModel, 
        skin_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback recommendations when all systems fail"""
        fallback_products = self._create_fallback_products(skin_analysis, {"city": "Any City", "state": "Any State"})
        
        return {
            "recommendations": fallback_products,
            "routine_suggestions": self._build_routine_from_products(fallback_products),
            "shopping_list": self._generate_shopping_list(fallback_products),
            "source_mix": {"fallback": len(fallback_products)},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Using fallback recommendations due to service unavailability"
        }

    def _determine_required_ingredients(self, metrics: Dict[str, Any], skin_analysis: Dict[str, Any]) -> List[str]:
        """
        Determine required ingredients based on all 10 ORBO skin metrics
        Prioritize ingredients for metrics scoring below 70/100
        """
        ingredients = []
        concerns = skin_analysis.get("concerns", [])
        
        # Metric 1: Overall Skin Health (below 70 needs comprehensive care)
        if metrics.get("overall_skin_health_score", 100) < 70:
            ingredients.extend(["Niacinamide", "Ceramides", "Peptides"])
        
        # Metric 2: Hydration (below 70 needs moisture boost)
        if metrics.get("hydration", 100) < 70 or "dryness" in concerns:
            ingredients.extend(["Hyaluronic Acid", "Ceramides", "Glycerin", "Squalane"])
        
        # Metric 3: Smoothness/Texture (below 70 needs exfoliation)
        if metrics.get("smoothness", 100) < 70:
            ingredients.extend(["AHA (Glycolic/Lactic Acid)", "BHA (Salicylic Acid)", "Retinol", "Niacinamide"])
        
        # Metric 4: Radiance/Glow (below 70 needs brightening)
        if metrics.get("radiance", 100) < 70:
            ingredients.extend(["Vitamin C", "Niacinamide", "Alpha Arbutin", "Licorice Root Extract"])
        
        # Metric 5: Dark Spots/Pigmentation (below 70 needs spot treatment)
        if metrics.get("dark_spots", 100) < 70 or "hyperpigmentation" in concerns:
            ingredients.extend(["Vitamin C", "Kojic Acid", "Alpha Arbutin", "Tranexamic Acid", "Azelaic Acid"])
        
        # Metric 6: Firmness/Elasticity (below 70 needs firming)
        if metrics.get("firmness", 100) < 70:
            ingredients.extend(["Retinol", "Peptides", "Vitamin C", "Collagen-boosting Peptides", "Bakuchiol"])
        
        # Metric 7: Fine Lines & Wrinkles (below 70 needs anti-aging)
        if metrics.get("fine_lines_wrinkles", 100) < 70:
            ingredients.extend(["Retinol/Retinoids", "Peptides", "Vitamin C", "Hyaluronic Acid", "Bakuchiol"])
        
        # Metric 8: Acne/Blemishes (below 70 needs acne treatment)
        if metrics.get("acne", 100) < 70 or "acne" in concerns:
            ingredients.extend(["Salicylic Acid", "Benzoyl Peroxide", "Niacinamide", "Tea Tree Oil", "Azelaic Acid"])
        
        # Metric 9: Dark Circles (below 70 needs under-eye care)
        if metrics.get("dark_circles", 100) < 70:
            ingredients.extend(["Caffeine", "Vitamin K", "Retinol", "Peptides", "Vitamin C", "Niacinamide"])
        
        # Metric 10: Redness/Sensitivity (below 70 needs calming)
        if metrics.get("redness", 100) < 70 or "sensitivity" in concerns:
            ingredients.extend(["Centella Asiatica", "Allantoin", "Oat Extract", "Ceramides", "Green Tea Extract", "Chamomile"])
        
        # Remove duplicates and prioritize by frequency
        from collections import Counter
        ingredient_counts = Counter(ingredients)
        # Sort by frequency (most recommended first)
        sorted_ingredients = [ing for ing, _ in ingredient_counts.most_common()]
        
        return sorted_ingredients[:10]  # Return top 10 most relevant ingredients
    
    def _format_age_range(self, age_range: str) -> str:
        """
        Format age range from database format to human-readable format
        """
        age_mapping = {
            "under_18": "Under 18",
            "18_24": "18-24",
            "25_34": "25-34", 
            "35_44": "35-44",
            "45_54": "45-54",
            "55_plus": "55+"
        }
        return age_mapping.get(age_range, "25-34")
    
    def _get_regional_stores(self, state: str) -> List[str]:
        """
        Get common stores based on region/state
        """
        # Common nationwide stores
        base_stores = ["CVS", "Walgreens", "Target"]
        
        # Regional variations
        state_upper = state.upper()[:2] if state else ""
        
        # West Coast
        if state_upper in ["CA", "WA", "OR", "NV", "AZ"]:
            return base_stores + ["Ulta", "Sephora", "Rite Aid", "Trader Joe's"]
        # Northeast
        elif state_upper in ["NY", "NJ", "CT", "MA", "PA", "MD"]:
            return base_stores + ["Duane Reade", "Ulta", "Sephora", "Wegmans"]
        # Southeast
        elif state_upper in ["FL", "GA", "SC", "NC", "TN", "AL", "MS", "LA"]:
            return base_stores + ["Publix", "Ulta", "Sally Beauty", "Walmart"]
        # Midwest
        elif state_upper in ["IL", "MI", "OH", "IN", "WI", "MN", "IA"]:
            return base_stores + ["Meijer", "Kroger", "Ulta", "Walmart"]
        # Texas
        elif state_upper == "TX":
            return base_stores + ["H-E-B", "Ulta", "Sephora", "Sally Beauty"]
        # Mountain/Central
        elif state_upper in ["CO", "UT", "MT", "WY", "ID", "NM"]:
            return base_stores + ["King Soopers", "Smith's", "Walmart", "Ulta"]
        # Default
        else:
            return base_stores + ["Walmart", "Ulta", "Amazon Fresh"]
    
    def _determine_climate(self, state: str) -> str:
        """
        Determine climate based on state
        """
        # Simplified climate mapping - in production, use more sophisticated data
        tropical_states = ["FL", "HI", "PR", "VI", "GU"]
        dry_states = ["AZ", "NV", "NM", "UT", "CO"]
        cold_states = ["AK", "ME", "VT", "NH", "MN", "WI", "MI", "ND", "SD", "MT"]
        humid_states = ["LA", "MS", "AL", "GA", "SC", "NC", "TN", "AR"]
        
        state_abbr = state.upper()[:2]
        
        if state_abbr in tropical_states:
            return "Tropical/Hot and Humid"
        elif state_abbr in dry_states:
            return "Dry/Arid"
        elif state_abbr in cold_states:
            return "Cold/Continental"
        elif state_abbr in humid_states:
            return "Humid Subtropical"
        else:
            return "Temperate"
    
    def _get_current_season(self) -> str:
        """
        Get current season based on date
        """
        month = datetime.now(timezone.utc).month
        
        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        else:
            return "Fall"

# Global service instance
perplexity_service = PerplexityRecommendationService()