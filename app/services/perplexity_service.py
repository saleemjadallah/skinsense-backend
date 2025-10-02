"""
Perplexity Search API Service for Product Recommendations
Updated: 2025-10-01 - Added hybrid product image extraction with og:image and UI Avatars

This service uses Perplexity's Search API to find real, purchasable skincare products
based on ORBO AI skin analysis with 10 key metrics (0-100 scores).
"""

import asyncio
import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import aiohttp
from bson import ObjectId
from bs4 import BeautifulSoup
from perplexity import AsyncPerplexity
from pymongo.database import Database

from app.core.config import settings
from app.models.user import UserModel

logger = logging.getLogger(__name__)


class PerplexityRecommendationService:
    """
    Production-ready service for generating personalized product recommendations
    using Perplexity Search API with multi-query support and smart caching.

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
    """

    def __init__(self):
        self.api_key = settings.PERPLEXITY_API_KEY

        # Log API key status
        if self.api_key:
            logger.info(f"Perplexity Search API configured: {self.api_key[:10]}...")
        else:
            logger.warning("Perplexity API key not configured!")

        # Cache settings
        self.cache_ttl_hours = 24
        self.max_cached_products_per_user = 50

        # Rate limiting settings
        self.requests_per_minute = 20
        self.max_concurrent_searches = 5
        self.delay_between_batches = 1.0

        # Search settings
        self.max_results_per_query = 10  # Increased from 5 to get more results per query
        self.max_tokens_per_page = 1024  # Balance between detail and speed
        self.min_products_to_return = 6  # Minimum products to return

        # Image extraction settings
        self.image_cache_ttl_hours = 168  # Cache images for 1 week
        self.image_fetch_timeout = 5  # Timeout for fetching product pages (seconds)
        self.max_concurrent_image_fetches = 3  # Limit concurrent image extractions

    async def get_personalized_recommendations(
        self,
        user: UserModel,
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str],
        db: Database,
        limit: int = 7
    ) -> Dict[str, Any]:
        """
        Generate personalized product recommendations using Perplexity Search API
        with multi-query support for better coverage and reliability.
        """
        logger.info(f"Getting personalized recommendations for user {user.id}")
        logger.info(f"User location: {user_location}")

        try:
            # Step 1: DISABLED - Skip cached favorites to prioritize fresh Search API results
            # The user_product_interactions cache was causing duplicates
            cached_recommendations = []

            # Step 2: Get fresh recommendations from Perplexity Search API
            fresh_limit = limit
            fresh_recommendations = []

            if self.api_key:
                logger.info(f"Calling Perplexity Search API for {fresh_limit} fresh recommendations")
                fresh_recommendations = await self._search_products_multi_query(
                    skin_analysis, user, user_location, limit=fresh_limit
                )

                # Cache successful recommendations
                if fresh_recommendations:
                    logger.info(f"Got {len(fresh_recommendations)} fresh recommendations from Search API")
                    await self._cache_recommendations(user.id, fresh_recommendations, skin_analysis, db)
                else:
                    logger.warning("Search API returned empty recommendations")

            # Step 3: Combine results
            all_recommendations = cached_recommendations + fresh_recommendations

            logger.info(f"[RECOMMENDATIONS] Cached: {len(cached_recommendations)}, Fresh: {len(fresh_recommendations)}, Total: {len(all_recommendations)}")

            # Step 4: Validate and enhance products
            validated_recommendations = []
            for product in all_recommendations:
                # Ensure required fields
                if 'name' not in product or not product['name']:
                    product['name'] = 'Unknown Product'
                if 'brand' not in product or not product['brand']:
                    product['brand'] = self._extract_brand(product.get('name', ''))
                if 'category' not in product or not product['category']:
                    product['category'] = self._guess_category(product.get('name', ''))

                # Normalize pricing
                self._normalize_pricing(product)

                # Ensure URLs
                self._ensure_product_urls(product)

                validated_recommendations.append(product)

            # Step 4.5: Enhance product images in parallel (async)
            validated_recommendations = await self._enhance_product_images(
                validated_recommendations, db
            )

            # Step 5: Fallback if no recommendations
            if not validated_recommendations:
                logger.error("No recommendations from cache or Search API - using fallback")
                validated_recommendations = self._create_fallback_products(skin_analysis, user_location)

            # Step 6: Build complete response
            logger.info(f"[FINAL] Returning {len(validated_recommendations[:limit])} products to user")
            logger.info(f"[FINAL] Product names: {[p.get('name', 'Unknown')[:40] for p in validated_recommendations[:limit]]}")

            return {
                "recommendations": validated_recommendations[:limit],
                "routine_suggestions": self._build_routine_from_products(validated_recommendations),
                "shopping_list": self._generate_shopping_list(validated_recommendations),
                "source_mix": {
                    "cached_favorites": len(cached_recommendations),
                    "fresh_search": len(fresh_recommendations),
                    "total": len(validated_recommendations)
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "location": user_location,
                "api_version": "search_api_v1"
            }

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}", exc_info=True)
            # Return fallback with error info
            fallback = self._create_fallback_products(skin_analysis, user_location)
            return {
                "recommendations": fallback,
                "routine_suggestions": self._build_routine_from_products(fallback),
                "shopping_list": self._generate_shopping_list(fallback),
                "error": str(e),
                "source_mix": {"fallback": len(fallback)},
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "location": user_location
            }

    async def _search_products_multi_query(
        self,
        skin_analysis: Dict[str, Any],
        user: UserModel,
        user_location: Dict[str, str],
        limit: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Use Perplexity Search API with multi-query support to find products
        for different skin concerns in parallel.
        """
        try:
            # Build concern-specific queries
            queries = self._build_multi_queries(skin_analysis, user, user_location)

            if not queries:
                logger.warning("No search queries generated")
                return []

            logger.info(f"[SEARCH API] Executing {len(queries)} parallel searches")
            logger.info(f"[SEARCH API] Queries: {queries}")

            # Execute searches with async client
            async with AsyncPerplexity(api_key=self.api_key) as client:
                # Use multi-query search (up to 5 queries per request)
                search = await client.search.create(
                    query=queries[:5],  # Max 5 queries per request
                    max_results=self.max_results_per_query,
                    max_tokens_per_page=self.max_tokens_per_page,
                    country="US"  # US region for product availability
                )

                # Parse results from all queries
                all_products = []

                logger.info(f"[SEARCH API] Raw search.results type: {type(search.results)}")
                logger.info(f"[SEARCH API] Raw search.results length: {len(search.results) if hasattr(search.results, '__len__') else 'N/A'}")

                # Handle multi-query results (array of result arrays)
                if isinstance(search.results, list) and len(search.results) > 0:
                    if isinstance(search.results[0], list):
                        # Multi-query format: [[results for query 1], [results for query 2], ...]
                        for query_idx, query_results in enumerate(search.results):
                            logger.info(f"Processing {len(query_results)} results for query {query_idx + 1}")
                            for result in query_results:
                                product = self._parse_search_result(result, skin_analysis, user_location)
                                if product:
                                    all_products.append(product)
                    else:
                        # Single query format: [result1, result2, ...]
                        logger.info(f"Processing {len(search.results)} results from single query")
                        for result in search.results:
                            product = self._parse_search_result(result, skin_analysis, user_location)
                            if product:
                                all_products.append(product)

                # Deduplicate by product URL
                unique_products = self._deduplicate_products(all_products)

                logger.info(f"[SEARCH API] Found {len(unique_products)} unique products from {len(all_products)} total results")
                logger.info(f"[SEARCH API] Product names: {[p.get('name', 'Unknown')[:50] for p in unique_products[:10]]}")

                return unique_products[:limit]

        except Exception as e:
            logger.error(f"Multi-query search failed: {e}", exc_info=True)
            return []

    def _build_multi_queries(
        self,
        skin_analysis: Dict[str, Any],
        user: UserModel,
        user_location: Dict[str, str]
    ) -> List[str]:
        """
        Build multiple targeted search queries based on skin metrics.
        Each query focuses on a specific concern for better product matches.
        """
        # Extract metrics
        orbo_data = skin_analysis.get("orbo_response", {})
        metrics = orbo_data.get("metrics", {})

        if not metrics and "metrics" in skin_analysis:
            metrics = skin_analysis.get("metrics", {})

        # User context
        skin_type = user.onboarding.skin_type if user.onboarding else "normal"
        age_range = self._format_age_range(user.onboarding.age_group) if user.onboarding else "25-34"
        zip_code = user_location.get('zip_code', '')
        city = user_location.get('city', 'US')

        queries = []

        # Build concern-specific queries (max 5 for multi-query API)
        # Priority 1: Hydration (most common concern)
        if metrics.get("hydration", 100) < 75:
            queries.append(
                f"best hydrating serum moisturizer for {skin_type} skin available in {zip_code} {city} with price and buy link"
            )

        # Priority 2: Acne/Blemishes
        if metrics.get("acne", 100) < 75:
            queries.append(
                f"effective acne treatment salicylic acid products for {skin_type} skin near {zip_code} with price"
            )

        # Priority 3: Dark Spots/Pigmentation
        if metrics.get("dark_spots", 100) < 75:
            queries.append(
                f"vitamin C serum dark spot corrector for {age_range} age group available {city} with price"
            )

        # Priority 4: Anti-aging (wrinkles/firmness)
        if metrics.get("fine_lines_wrinkles", 100) < 75 or metrics.get("firmness", 100) < 75:
            queries.append(
                f"retinol anti-aging serum peptides for {age_range} near {zip_code} with buy link"
            )

        # Priority 5: Redness/Sensitivity
        if metrics.get("redness", 100) < 75:
            queries.append(
                f"calming centella sensitive skin products for {skin_type} available {city} with price"
            )

        # Always add general routine essentials to ensure variety (even if no concerns)
        if len(queries) < 3:
            queries.append(
                f"best skincare routine essentials for {skin_type} skin {age_range} available {zip_code} with prices"
            )

        # Add cleanser query if we still don't have enough
        if len(queries) < 3:
            queries.append(
                f"gentle facial cleanser for {skin_type} skin available in {city} with price"
            )

        # Add moisturizer query for more variety
        if len(queries) < 4:
            queries.append(
                f"best daily moisturizer for {skin_type} skin {age_range} near {zip_code} with buy link"
            )

        logger.info(f"Built {len(queries)} targeted search queries")
        return queries[:5]  # Max 5 queries for API limit

    def _parse_search_result(
        self,
        result: Any,
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single search result into a structured product recommendation.

        Search result structure:
        - result.title: Page title (often contains product name)
        - result.url: Direct URL to product page
        - result.snippet: Description/content excerpt
        - result.date: Publication/update date (optional)
        """
        try:
            # Extract product information from search result
            title = getattr(result, 'title', '')
            url = getattr(result, 'url', '')
            snippet = getattr(result, 'snippet', '')

            if not title or not url:
                logger.debug("Skipping result with missing title or URL")
                return None

            # Extract product name and brand from title
            product_name = self._clean_product_name(title)
            brand = self._extract_brand(title)

            # Extract price from snippet
            price_info = self._extract_price_from_text(snippet)

            # Determine category
            category = self._guess_category(title + " " + snippet)

            # Extract key ingredients
            ingredients = self._extract_ingredients_from_text(snippet)

            # Extract retailer from URL
            retailer = self._extract_retailer_from_url(url)

            # Build product object
            product = {
                "id": f"search_{hash(url) % 100000}",
                "name": product_name,
                "brand": brand,
                "category": category,
                "description": snippet[:200] if snippet else f"High-quality {category} for your skin concerns",
                "productUrl": url,
                "affiliateLink": url,
                "trackingLink": url,
                "retailer": retailer,
                "currentPrice": price_info.get("numeric_price"),
                "priceRange": price_info.get("price_text", "$15-30"),
                "keyIngredients": ingredients,
                "availability": {
                    "online_stores": [retailer] if retailer else ["Online"],
                    "location_note": f"Available online, ships to {user_location.get('city', 'your area')}"
                },
                "matchReasoning": self._generate_match_reasoning_from_metrics(
                    product_name, skin_analysis
                ),
                "compatibilityScore": self._estimate_compatibility_score(
                    {"name": product_name, "description": snippet}, skin_analysis
                ),
                "usageInstructions": self._generate_usage_instructions({"name": product_name, "category": category}),
                "source": "perplexity_search_api",
                "searchTimestamp": datetime.now(timezone.utc).isoformat(),
                "inStock": True,
                "searchResult": {
                    "title": title,
                    "url": url,
                    "snippet": snippet[:100] + "..." if len(snippet) > 100 else snippet
                }
            }

            return product

        except Exception as e:
            logger.error(f"Failed to parse search result: {e}")
            return None

    def _clean_product_name(self, title: str) -> str:
        """Clean and extract product name from search result title"""
        # Remove common suffixes
        title = re.sub(r'\s*[-–|]\s*(Amazon|Sephora|Ulta|Target|CVS|Walgreens).*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*[-–|]\s*Buy.*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*[-–|]\s*Shop.*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*[-–|]\s*\$\d+.*$', '', title, flags=re.IGNORECASE)

        # Remove extra whitespace
        title = ' '.join(title.split())

        return title.strip()

    def _extract_price_from_text(self, text: str) -> Dict[str, Any]:
        """Extract price information from text"""
        price_info = {
            "price_text": None,
            "numeric_price": None
        }

        # Look for price patterns
        price_patterns = [
            r'\$(\d+\.?\d*)\s*-\s*\$(\d+\.?\d*)',  # $20-$30
            r'\$(\d+\.?\d*)',  # $25.99
        ]

        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 2:
                    # Price range
                    price_info["price_text"] = f"${match.group(1)}-${match.group(2)}"
                    price_info["numeric_price"] = float(match.group(1))
                else:
                    # Single price
                    price_info["price_text"] = f"${match.group(1)}"
                    price_info["numeric_price"] = float(match.group(1))
                break

        return price_info

    def _deduplicate_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate products based on URL and name similarity"""
        seen_urls = set()
        seen_names = set()
        unique_products = []

        for product in products:
            url = product.get('productUrl', '')
            name = product.get('name', '').lower()

            # Skip if we've seen this URL
            if url and url in seen_urls:
                continue

            # Skip if we've seen a very similar name
            name_key = re.sub(r'[^a-z0-9]', '', name)[:30]  # First 30 alphanumeric chars
            if name_key and name_key in seen_names:
                continue

            seen_urls.add(url)
            seen_names.add(name_key)
            unique_products.append(product)

        return unique_products

    def _normalize_pricing(self, product: Dict[str, Any]):
        """Ensure product has valid pricing fields"""
        # Normalize priceRange
        if not product.get('priceRange'):
            fallback = product.get('price_range') or product.get('price')
            if isinstance(fallback, (int, float)):
                product['priceRange'] = f"${int(fallback)}"
            elif isinstance(fallback, str) and fallback.strip():
                product['priceRange'] = fallback.strip()
            else:
                product['priceRange'] = "$15-30"

        # Normalize currentPrice
        if product.get('currentPrice') is None:
            raw_numeric = product.get('current_price')
            if isinstance(raw_numeric, (int, float)):
                product['currentPrice'] = float(raw_numeric)
            else:
                # Try to parse from priceRange
                price_range = product.get('priceRange', '')
                match = re.search(r'\$?([\d.]+)', price_range)
                if match:
                    try:
                        product['currentPrice'] = float(match.group(1))
                    except:
                        pass

    def _ensure_product_urls(self, product: Dict[str, Any]):
        """Ensure product has all required URL fields"""
        # Generate URL if missing
        if not product.get('productUrl'):
            product['productUrl'] = self._generate_product_url(product)

        # Set affiliate and tracking links
        url = product['productUrl']
        if not product.get('affiliateLink'):
            product['affiliateLink'] = url
        if not product.get('trackingLink'):
            product['trackingLink'] = url

    def _generate_match_reasoning_from_metrics(
        self,
        product_name: str,
        skin_analysis: Dict[str, Any]
    ) -> str:
        """Generate match reasoning based on skin metrics and product"""
        metrics = skin_analysis.get("orbo_response", {}).get("metrics", {})
        if not metrics:
            metrics = skin_analysis.get("metrics", {})

        product_lower = product_name.lower()
        reasons = []

        # Check what concerns this product addresses
        if metrics.get("hydration", 100) < 75 and any(word in product_lower for word in ['hydrat', 'moistur', 'hyaluronic']):
            reasons.append("addresses hydration needs")

        if metrics.get("acne", 100) < 75 and any(word in product_lower for word in ['acne', 'salicylic', 'bha', 'clear']):
            reasons.append("targets acne concerns")

        if metrics.get("dark_spots", 100) < 75 and any(word in product_lower for word in ['vitamin c', 'bright', 'dark spot', 'pigment']):
            reasons.append("helps with dark spots")

        if metrics.get("fine_lines_wrinkles", 100) < 75 and any(word in product_lower for word in ['retinol', 'anti-aging', 'wrinkle', 'peptide']):
            reasons.append("reduces signs of aging")

        if metrics.get("redness", 100) < 75 and any(word in product_lower for word in ['calm', 'sooth', 'centella', 'sensitive']):
            reasons.append("calms sensitive skin")

        if reasons:
            return "Recommended because it " + " and ".join(reasons)

        return "Well-suited for your skin type and concerns"

    # Caching methods
    async def _get_cached_recommendations(
        self,
        user: UserModel,
        skin_analysis: Dict[str, Any],
        db: Database,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get cached product recommendations from user's favorites"""
        try:
            cached_products = list(db.user_product_interactions.find({
                "user_id": user.id,
                "interaction_type": {"$in": ["liked", "saved", "purchased"]},
                "created_at": {
                    "$gte": datetime.now(timezone.utc) - timedelta(hours=self.cache_ttl_hours)
                }
            }).sort("created_at", -1).limit(limit))

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
        """Cache successful recommendations for future use"""
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
        """Track user interactions with recommended products"""
        try:
            interaction_data = {
                "user_id": user_id,
                "product_data": product_data,
                "interaction_type": interaction_type,
                "skin_analysis_id": skin_analysis_id,
                "created_at": datetime.now(timezone.utc)
            }

            db.user_product_interactions.insert_one(interaction_data)

        except Exception as e:
            logger.error(f"Failed to track product interaction: {e}")

    # Helper methods
    def _extract_brand(self, text: str) -> str:
        """Extract brand name from text"""
        common_brands = [
            'CeraVe', 'Neutrogena', 'Olay', 'The Ordinary', "Paula's Choice",
            'Clinique', 'Cetaphil', 'La Roche-Posay', 'Aveeno', 'Differin',
            'Skinceuticals', 'Drunk Elephant', 'Dermalogica', 'Kiehl\'s',
            'Fresh', 'Origins', 'Tatcha', 'Sunday Riley', 'Glow Recipe'
        ]

        text_lower = text.lower()
        for brand in common_brands:
            if brand.lower() in text_lower:
                return brand

        # Extract first capitalized word as potential brand
        words = text.split()
        for word in words:
            if word and word[0].isupper() and len(word) > 2:
                return word

        return "Premium Brand"

    def _guess_category(self, text: str) -> str:
        """Guess product category from text"""
        text_lower = text.lower()

        if any(word in text_lower for word in ['cleanser', 'wash', 'foam', 'gel cleanser']):
            return 'cleanser'
        elif any(word in text_lower for word in ['serum', 'treatment serum']):
            return 'serum'
        elif any(word in text_lower for word in ['moisturizer', 'cream', 'lotion', 'hydrator']):
            return 'moisturizer'
        elif any(word in text_lower for word in ['sunscreen', 'spf', 'sun protection']):
            return 'sunscreen'
        elif any(word in text_lower for word in ['toner', 'essence']):
            return 'toner'
        elif any(word in text_lower for word in ['mask', 'masque']):
            return 'mask'
        elif any(word in text_lower for word in ['eye cream', 'eye serum']):
            return 'eye_care'
        else:
            return 'treatment'

    def _extract_ingredients_from_text(self, text: str) -> List[str]:
        """Extract ingredient names from text"""
        common_ingredients = [
            'Niacinamide', 'Hyaluronic Acid', 'Retinol', 'Vitamin C', 'Ceramides',
            'Salicylic Acid', 'Glycolic Acid', 'Peptides', 'Caffeine', 'Zinc',
            'Vitamin E', 'Squalane', 'Glycerin', 'AHA', 'BHA', 'PHA',
            'Benzoyl Peroxide', 'Adapalene', 'Azelaic Acid', 'Kojic Acid',
            'Centella Asiatica', 'Allantoin', 'Bakuchiol', 'Alpha Arbutin'
        ]

        text_lower = text.lower()
        found = [ing for ing in common_ingredients if ing.lower() in text_lower]

        return found[:5]

    def _extract_retailer_from_url(self, url: str) -> str:
        """Extract retailer name from URL"""
        if not url:
            return "Online"

        url_lower = url.lower()
        retailers = {
            'sephora': 'Sephora',
            'ulta': 'Ulta',
            'amazon': 'Amazon',
            'target': 'Target',
            'cvs': 'CVS',
            'walgreens': 'Walgreens',
            'walmart': 'Walmart',
            'dermstore': 'Dermstore',
            'beautylish': 'Beautylish',
            'cultbeauty': 'Cult Beauty',
            'nordstrom': 'Nordstrom',
            'bluemercury': 'Bluemercury'
        }

        for key, name in retailers.items():
            if key in url_lower:
                return name

        # Extract domain
        domain_match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', url)
        if domain_match:
            domain = domain_match.group(1).replace('.com', '').replace('.', ' ').title()
            return domain

        return "Online"

    def _generate_product_url(self, product: Dict[str, Any]) -> str:
        """Generate product URL"""
        if product.get('productUrl'):
            return product['productUrl']

        # Generate search URL based on retailer
        retailer = product.get('retailer', '').lower()
        name = product.get('name', '').replace(' ', '+')
        brand = product.get('brand', '').replace(' ', '+')

        url_templates = {
            'amazon': f"https://www.amazon.com/s?k={brand}+{name}",
            'sephora': f"https://www.sephora.com/search?keyword={brand}%20{name}",
            'ulta': f"https://www.ulta.com/search?q={brand}+{name}",
            'target': f"https://www.target.com/s?searchTerm={brand}+{name}",
        }

        for key, url in url_templates.items():
            if key in retailer:
                return url

        return f"https://www.google.com/search?q={brand}+{name}+buy"

    async def _enhance_product_images(
        self,
        products: List[Dict[str, Any]],
        db: Database
    ) -> List[Dict[str, Any]]:
        """
        Enhance product images using hybrid approach:
        1. Check cache for existing image URL
        2. Try to extract og:image from product URL
        3. Fallback to UI Avatars with category-based colors

        Args:
            products: List of product dictionaries
            db: Database connection for caching

        Returns:
            Products with imageUrl field populated
        """
        try:
            # Process images in parallel with concurrency limit
            semaphore = asyncio.Semaphore(self.max_concurrent_image_fetches)

            async def process_product_image(product: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    product['imageUrl'] = await self._get_product_image(product, db)
                    return product

            # Process all products concurrently
            enhanced_products = await asyncio.gather(
                *[process_product_image(p) for p in products],
                return_exceptions=True
            )

            # Filter out any exceptions and ensure all have images
            result = []
            for item in enhanced_products:
                if isinstance(item, Exception):
                    logger.error(f"Failed to enhance product image: {item}")
                    continue
                if not item.get('imageUrl'):
                    item['imageUrl'] = self._generate_ui_avatar_url(item)
                result.append(item)

            return result

        except Exception as e:
            logger.error(f"Image enhancement batch failed: {e}", exc_info=True)
            # Fallback: add UI Avatars to all products
            for product in products:
                if not product.get('imageUrl'):
                    product['imageUrl'] = self._generate_ui_avatar_url(product)
            return products

    async def _get_product_image(
        self,
        product: Dict[str, Any],
        db: Database
    ) -> str:
        """
        Get product image URL using hybrid approach with caching.

        Priority:
        1. Check MongoDB cache (synchronous PyMongo)
        2. Extract og:image from product URL (async aiohttp)
        3. Fallback to UI Avatars (synchronous)

        Args:
            product: Product dictionary with productUrl
            db: Database connection (PyMongo)

        Returns:
            Image URL string
        """
        product_url = product.get('productUrl', '')

        # Step 1: Check cache (synchronous PyMongo call)
        if product_url:
            cached_image = self._get_cached_product_image(product_url, db)
            if cached_image:
                logger.debug(f"Using cached image for {product.get('name', 'unknown')}")
                return cached_image

        # Step 2: Try to extract og:image from product URL (async)
        if product_url and self._is_valid_product_url(product_url):
            extracted_image = await self._extract_og_image(product_url)
            if extracted_image:
                logger.info(f"Extracted og:image for {product.get('name', 'unknown')}")
                # Cache the extracted image (synchronous PyMongo call)
                self._cache_product_image(product_url, extracted_image, db)
                return extracted_image

        # Step 3: Fallback to UI Avatars (synchronous)
        ui_avatar_url = self._generate_ui_avatar_url(product)
        logger.debug(f"Using UI Avatar for {product.get('name', 'unknown')}")
        return ui_avatar_url

    def _get_cached_product_image(
        self,
        product_url: str,
        db: Database
    ) -> Optional[str]:
        """
        Retrieve cached product image URL from MongoDB (synchronous).

        Args:
            product_url: Product page URL
            db: Database connection (PyMongo)

        Returns:
            Cached image URL or None
        """
        try:
            cache_entry = db.product_image_cache.find_one({
                "product_url": product_url,
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })

            if cache_entry:
                return cache_entry.get("image_url")

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve cached image: {e}")
            return None

    def _cache_product_image(
        self,
        product_url: str,
        image_url: str,
        db: Database
    ):
        """
        Cache product image URL in MongoDB with TTL (synchronous).

        Args:
            product_url: Product page URL
            image_url: Extracted image URL
            db: Database connection (PyMongo)
        """
        try:
            cache_entry = {
                "product_url": product_url,
                "image_url": image_url,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=self.image_cache_ttl_hours)
            }

            # Upsert to avoid duplicates
            db.product_image_cache.update_one(
                {"product_url": product_url},
                {"$set": cache_entry},
                upsert=True
            )

            logger.debug(f"Cached image URL for {product_url}")

        except Exception as e:
            logger.error(f"Failed to cache product image: {e}")

    async def _extract_og_image(self, url: str) -> Optional[str]:
        """
        Extract Open Graph image from product page.

        Args:
            url: Product page URL

        Returns:
            og:image URL or None
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.image_fetch_timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    },
                    allow_redirects=True
                ) as response:

                    if response.status != 200:
                        logger.warning(f"Failed to fetch product page: {url} (status: {response.status})")
                        return None

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Try multiple Open Graph image meta tags
                    og_image_tags = [
                        soup.find('meta', property='og:image'),
                        soup.find('meta', property='og:image:url'),
                        soup.find('meta', property='og:image:secure_url'),
                        soup.find('meta', name='twitter:image'),
                        soup.find('meta', itemprop='image'),
                    ]

                    for tag in og_image_tags:
                        if tag and tag.get('content'):
                            image_url = tag.get('content')

                            # Validate image URL
                            if self._is_valid_image_url(image_url):
                                logger.info(f"Extracted image from {url}: {image_url[:100]}")
                                return image_url

                    logger.warning(f"No valid og:image found for {url}")
                    return None

        except asyncio.TimeoutError:
            logger.warning(f"Timeout extracting image from {url}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract og:image from {url}: {e}")
            return None

    def _is_valid_product_url(self, url: str) -> bool:
        """
        Validate that URL is a real product page (not a search URL).

        Args:
            url: URL to validate

        Returns:
            True if valid product URL
        """
        if not url or len(url) < 10:
            return False

        # Skip generic search URLs
        skip_patterns = [
            '/search',
            '/s?',
            'google.com/search',
            '/results',
        ]

        return not any(pattern in url.lower() for pattern in skip_patterns)

    def _is_valid_image_url(self, url: str) -> bool:
        """
        Validate that URL points to an actual image.

        Args:
            url: Image URL to validate

        Returns:
            True if valid image URL
        """
        if not url or len(url) < 10:
            return False

        # Check for common image extensions or CDN patterns
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif',
            'cloudinary.com',
            'cloudfront.net',
            'shopify.com',
            'sephora.com',
            'ulta.com',
            'target.com',
            'amazon.com',
        ]

        url_lower = url.lower()
        return any(pattern in url_lower for pattern in valid_patterns)

    def _generate_ui_avatar_url(self, product: Dict[str, Any]) -> str:
        """
        Generate UI Avatars URL with category-based brand colors.

        This creates professional-looking placeholder images with:
        - Brand initials or single letter
        - Category-specific background colors
        - Consistent, deterministic output

        Args:
            product: Product dictionary with brand, name, category

        Returns:
            UI Avatars URL
        """
        brand = product.get('brand', product.get('name', 'Product'))
        category = product.get('category', 'treatment')

        # Get category-specific color
        bg_color = self._get_category_color(category)

        # URL encode brand name
        name_param = quote(brand)

        # Build UI Avatars URL with SkinSense branding
        return (
            f"https://ui-avatars.com/api/"
            f"?name={name_param}"
            f"&size=400"
            f"&background={bg_color}"
            f"&color=fff"
            f"&bold=true"
            f"&rounded=true"
            f"&format=png"
        )

    def _get_category_color(self, category: str) -> str:
        """
        Get SkinSense brand color based on product category.

        Args:
            category: Product category

        Returns:
            Hex color code (without #)
        """
        # SkinSense brand color palette
        category_colors = {
            'cleanser': '4ECDC4',      # Teal - Fresh, clean
            'serum': '6B73FF',         # Neural blue - Advanced, tech
            'moisturizer': 'FF6B9D',   # Aurora pink - Hydrating, nurturing
            'sunscreen': 'FFB347',     # Sun orange - Protection
            'toner': '95E1D3',         # Mint - Refreshing
            'mask': '9C27B0',          # Purple - Premium, treatment
            'eye_care': 'FF8A80',      # Coral - Gentle, delicate
            'treatment': 'E91E63',     # Primary magenta - Core brand
        }

        return category_colors.get(category, 'E91E63')  # Default to primary magenta

    def _estimate_compatibility_score(self, product: Dict[str, Any], skin_analysis: Dict[str, Any]) -> float:
        """Estimate compatibility score"""
        base_score = 7.5

        concerns = skin_analysis.get("concerns", [])
        product_text = str(product.get("name", "")).lower() + str(product.get("description", "")).lower()

        for concern in concerns:
            if concern.lower() in product_text:
                base_score += 0.5

        return min(10.0, base_score)

    def _generate_usage_instructions(self, product: Dict[str, Any]) -> str:
        """Generate usage instructions"""
        category = product.get('category', '')

        instructions = {
            "cleanser": "Apply to damp skin, massage gently, rinse with lukewarm water. Use morning and evening.",
            "serum": "Apply 2-3 drops to clean skin before moisturizer. Start with evening use.",
            "moisturizer": "Apply to clean skin as the last step of your routine. Use morning and evening.",
            "sunscreen": "Apply generously 15 minutes before sun exposure. Reapply every 2 hours.",
            "toner": "Apply to clean skin with cotton pad or gentle patting motions.",
            "mask": "Apply to clean skin, leave for recommended time, rinse thoroughly.",
            "eye_care": "Gently pat around eye area using ring finger. Use morning and/or evening.",
            "treatment": "Follow package instructions for best results."
        }

        return instructions.get(category, "Follow package instructions for best results.")

    def _is_product_relevant(self, product: Dict[str, Any], skin_analysis: Dict[str, Any]) -> bool:
        """Check if cached product is still relevant"""
        return True  # Simple implementation

    def _build_routine_from_products(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build AM/PM routine suggestions"""
        routine = {"morning": [], "evening": []}
        order = {"cleanser": 1, "toner": 2, "serum": 3, "eye_care": 4, "moisturizer": 5, "sunscreen": 6}

        for product in products:
            category = product.get("category", "treatment")
            step = {
                "product": product["name"],
                "category": category,
                "step_order": order.get(category, 7),
                "instructions": product.get("usageInstructions", "")
            }

            if category == "sunscreen":
                routine["morning"].append(step)
            elif category in ["cleanser", "moisturizer", "eye_care"]:
                routine["morning"].append(step)
                routine["evening"].append(step)
            else:
                routine["evening"].append(step)

        routine["morning"].sort(key=lambda x: x["step_order"])
        routine["evening"].sort(key=lambda x: x["step_order"])

        return routine

    def _generate_shopping_list(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate prioritized shopping list"""
        essential_categories = ["cleanser", "moisturizer", "sunscreen"]

        shopping_list = {
            "immediate_priorities": [],
            "next_additions": [],
            "total_estimated_cost": "$0-0"
        }

        total_min = 0
        total_max = 0

        for product in products:
            category = product.get("category", "")
            price_range = product.get("priceRange", "$15-25")

            prices = re.findall(r'\$?(\d+)', price_range)
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
                "direct_link": product.get("productUrl", "")
            }

            if category in essential_categories:
                shopping_list["immediate_priorities"].append(item)
            else:
                shopping_list["next_additions"].append(item)

        shopping_list["total_estimated_cost"] = f"${total_min}-{total_max}"

        return shopping_list

    def _create_fallback_products(
        self,
        skin_analysis: Dict[str, Any],
        user_location: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Create fallback recommendations when API fails"""
        city = user_location.get('city', 'your area')
        state = user_location.get('state', 'US')

        fallback = [
            {
                "id": "fallback_001",
                "name": "CeraVe Hydrating Facial Cleanser",
                "brand": "CeraVe",
                "category": "cleanser",
                "priceRange": "$12-16",
                "currentPrice": 14.0,
                "productUrl": "https://www.amazon.com/s?k=CeraVe+Hydrating+Facial+Cleanser",
                "affiliateLink": "https://www.amazon.com/s?k=CeraVe+Hydrating+Facial+Cleanser",
                "retailer": "Amazon",
                "description": "Gentle, non-foaming cleanser with ceramides and hyaluronic acid",
                "keyIngredients": ["Ceramides", "Hyaluronic Acid"],
                "matchReasoning": "Gentle cleanser suitable for all skin types",
                "compatibilityScore": 8.5,
                "usageInstructions": "Apply to damp skin, massage gently, rinse with lukewarm water.",
                "source": "fallback_database",
                "imageUrl": "https://picsum.photos/seed/cerave/400/400",
                "availability": {
                    "online_stores": ["Amazon", "Target", "CVS"],
                    "location_note": f"Available in {city}, {state}"
                }
            },
            {
                "id": "fallback_002",
                "name": "The Ordinary Niacinamide 10% + Zinc 1%",
                "brand": "The Ordinary",
                "category": "serum",
                "priceRange": "$6-8",
                "currentPrice": 6.0,
                "productUrl": "https://www.sephora.com/search?keyword=The%20Ordinary%20Niacinamide",
                "affiliateLink": "https://www.sephora.com/search?keyword=The%20Ordinary%20Niacinamide",
                "retailer": "Sephora",
                "description": "High-strength vitamin and mineral blemish formula",
                "keyIngredients": ["Niacinamide", "Zinc"],
                "matchReasoning": "Addresses pore concerns and texture",
                "compatibilityScore": 8.2,
                "usageInstructions": "Apply 2-3 drops to clean skin before moisturizer.",
                "source": "fallback_database",
                "imageUrl": "https://picsum.photos/seed/ordinary/400/400",
                "availability": {
                    "online_stores": ["Sephora", "Ulta", "Amazon"],
                    "location_note": f"Available in {city}, {state}"
                }
            },
            {
                "id": "fallback_003",
                "name": "Neutrogena Hydro Boost Water Gel",
                "brand": "Neutrogena",
                "category": "moisturizer",
                "priceRange": "$15-20",
                "currentPrice": 17.0,
                "productUrl": "https://www.target.com/s?searchTerm=Neutrogena+Hydro+Boost",
                "affiliateLink": "https://www.target.com/s?searchTerm=Neutrogena+Hydro+Boost",
                "retailer": "Target",
                "description": "Lightweight gel moisturizer with hyaluronic acid",
                "keyIngredients": ["Hyaluronic Acid", "Glycerin"],
                "matchReasoning": "Provides lightweight hydration",
                "compatibilityScore": 8.0,
                "usageInstructions": "Apply to clean skin morning and evening.",
                "source": "fallback_database",
                "imageUrl": "https://picsum.photos/seed/neutrogena/400/400",
                "availability": {
                    "online_stores": ["Target", "Amazon", "Walmart"],
                    "location_note": f"Available in {city}, {state}"
                }
            }
        ]

        return fallback

    def _format_age_range(self, age_group: str) -> str:
        """Format age range"""
        mapping = {
            "under_18": "Under 18",
            "18_24": "18-24",
            "25_34": "25-34",
            "35_44": "35-44",
            "45_54": "45-54",
            "55_plus": "55+"
        }
        return mapping.get(age_group, "25-34")


# Global service instance
perplexity_service = PerplexityRecommendationService()