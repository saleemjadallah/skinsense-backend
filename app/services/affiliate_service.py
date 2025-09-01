"""
Affiliate Link Generation and Tracking Service
Automatically generates tracked affiliate links for all products
"""

import hashlib
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pymongo.database import Database
from bson import ObjectId
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class AffiliateService:
    """
    Service for generating and managing affiliate links across all retail partners
    """
    
    def __init__(self, db: Database):
        self.db = db
        
        # Affiliate partner configuration
        self.affiliate_config = {
            'amazon': {
                'tag': settings.AMAZON_ASSOCIATE_TAG if hasattr(settings, 'AMAZON_ASSOCIATE_TAG') else 'skinsense-20',
                'base_url': 'https://www.amazon.com/dp/',
                'tracking_params': {
                    'tag': 'skinsense-20',
                    'linkCode': 'as2',
                    'camp': '1789',
                    'creative': '9325'
                },
                'commission_rate': 0.03  # 3% default, varies by category
            },
            'sephora': {
                'partner_id': settings.SEPHORA_PARTNER_ID if hasattr(settings, 'SEPHORA_PARTNER_ID') else 'skinsense',
                'base_url': 'https://www.sephora.com/product/',
                'tracking_params': {
                    'om_mmc': 'aff-linkshare',
                    'c3ch': 'Affiliate',
                    'c3nid': 'skinsense'
                },
                'commission_rate': 0.05  # 5% average
            },
            'ulta': {
                'partner_id': settings.ULTA_PARTNER_ID if hasattr(settings, 'ULTA_PARTNER_ID') else 'skinsense',
                'base_url': 'https://www.ulta.com/p/',
                'tracking_params': {
                    'AID': '11557053',  # Affiliate ID
                    'PID': 'skinsense',
                    'CID': 'affiliate'
                },
                'commission_rate': 0.03  # 3-7% varies
            },
            'target': {
                'partner_id': settings.TARGET_PARTNER_ID if hasattr(settings, 'TARGET_PARTNER_ID') else 'skinsense',
                'base_url': 'https://www.target.com/p/',
                'tracking_params': {
                    'afid': 'skinsense',
                    'ref': 'tgt_adv_xasd0002'
                },
                'commission_rate': 0.01  # 1-8% varies
            },
            'iherb': {
                'partner_code': settings.IHERB_PARTNER_CODE if hasattr(settings, 'IHERB_PARTNER_CODE') else 'SKN2025',
                'base_url': 'https://www.iherb.com/',
                'tracking_params': {
                    'rcode': 'SKN2025',  # Rewards code
                    'utm_source': 'affiliate',
                    'utm_medium': 'skinsense'
                },
                'commission_rate': 0.05  # 5-10% varies
            },
            'dermstore': {
                'partner_id': settings.DERMSTORE_PARTNER_ID if hasattr(settings, 'DERMSTORE_PARTNER_ID') else 'skinsense',
                'base_url': 'https://www.dermstore.com/product/',
                'tracking_params': {
                    'utm_source': 'linkshare',
                    'utm_medium': 'affiliate',
                    'utm_campaign': 'skinsense',
                    'ranMID': '43058',
                    'ranEAID': 'skinsense'
                },
                'commission_rate': 0.05  # 5-15% varies
            },
            'cvs': {
                'base_url': 'https://www.cvs.com/shop/',
                'tracking_params': {
                    'WT.tsrc': 'affiliate',
                    'CID': 'aff:skinsense'
                },
                'commission_rate': 0.02  # 2% average
            },
            'walgreens': {
                'base_url': 'https://www.walgreens.com/store/',
                'tracking_params': {
                    'AID': 'skinsense',
                    'PID': '11246506'
                },
                'commission_rate': 0.03  # 3% average
            }
        }
    
    def generate_affiliate_link(
        self,
        product: Dict[str, Any],
        user_id: ObjectId,
        skin_analysis_id: Optional[ObjectId] = None
    ) -> Dict[str, str]:
        """
        Generate affiliate links for a product across all available retailers
        
        Args:
            product: Product data dictionary
            user_id: User ID for tracking
            skin_analysis_id: Optional skin analysis ID for attribution
            
        Returns:
            Dictionary with 'affiliate_link' and 'tracking_link'
        """
        retailer = product.get('retailer', '').lower()
        
        if retailer not in self.affiliate_config:
            # If retailer not in our affiliate network, return original URL
            return {
                'affiliate_link': product.get('url', ''),
                'tracking_link': self._create_internal_tracking_link(
                    product, user_id, skin_analysis_id
                )
            }
        
        # Generate unique tracking ID
        tracking_id = self._generate_tracking_id(user_id, product.get('id', ''))
        
        # Store tracking data
        self._store_tracking_data(
            tracking_id, user_id, product, skin_analysis_id, retailer
        )
        
        # Build affiliate link based on retailer
        affiliate_link = self._build_retailer_affiliate_link(
            retailer, product, tracking_id
        )
        
        # Create internal tracking link that redirects to affiliate link
        tracking_link = f"{settings.API_BASE_URL}/api/v1/track/product/{tracking_id}"
        
        return {
            'affiliate_link': affiliate_link,
            'tracking_link': tracking_link,
            'tracking_id': tracking_id,
            'estimated_commission': self._estimate_commission(product, retailer)
        }
    
    def _build_retailer_affiliate_link(
        self,
        retailer: str,
        product: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build retailer-specific affiliate link with proper parameters
        """
        config = self.affiliate_config[retailer]
        
        if retailer == 'amazon':
            return self._build_amazon_link(product, config, tracking_id)
        elif retailer == 'sephora':
            return self._build_sephora_link(product, config, tracking_id)
        elif retailer == 'ulta':
            return self._build_ulta_link(product, config, tracking_id)
        elif retailer == 'target':
            return self._build_target_link(product, config, tracking_id)
        elif retailer == 'iherb':
            return self._build_iherb_link(product, config, tracking_id)
        elif retailer == 'dermstore':
            return self._build_dermstore_link(product, config, tracking_id)
        else:
            # Generic affiliate link builder
            return self._build_generic_affiliate_link(product, config, tracking_id)
    
    def _build_amazon_link(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build Amazon Associate affiliate link
        
        Format: https://www.amazon.com/dp/ASIN/?tag=skinsense-20
        """
        asin = product.get('product_id', product.get('asin', ''))
        if not asin:
            return product.get('url', '')
        
        # Build base URL
        base_url = f"{config['base_url']}{asin}"
        
        # Add tracking parameters
        params = config['tracking_params'].copy()
        params['tag'] = config['tag']
        params['ascsubtag'] = tracking_id  # Custom tracking
        
        # Build final URL
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def _build_sephora_link(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build Sephora affiliate link through RewardStyle/ShopStyle
        
        Format: https://rstyle.me/+AFFILIATE_ID/product/PRODUCT_ID
        """
        product_id = product.get('product_id', '')
        original_url = product.get('url', '')
        
        if not product_id and original_url:
            # Extract product ID from URL
            import re
            match = re.search(r'P\d+', original_url)
            if match:
                product_id = match.group()
        
        if not product_id:
            return original_url
        
        # Build Sephora affiliate link
        base_url = f"{config['base_url']}{product_id}"
        params = config['tracking_params'].copy()
        params['clickid'] = tracking_id
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def _build_ulta_link(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build Ulta affiliate link through Commission Junction (CJ Affiliate)
        """
        product_id = product.get('product_id', '')
        original_url = product.get('url', '')
        
        if not original_url:
            return ''
        
        # CJ Affiliate deep link format
        cj_base = 'https://www.jdoqocy.com/click-'
        publisher_id = config['tracking_params']['AID']
        
        # Build tracking URL
        params = config['tracking_params'].copy()
        params['url'] = original_url
        params['sid'] = tracking_id  # Session ID for tracking
        
        # Create CJ tracking link
        tracking_url = f"{cj_base}{publisher_id}-{config['partner_id']}"
        query_string = urllib.parse.urlencode(params)
        
        return f"{tracking_url}?{query_string}"
    
    def _build_target_link(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build Target affiliate link through Target Partners
        """
        product_id = product.get('product_id', product.get('tcin', ''))
        
        if not product_id:
            return product.get('url', '')
        
        # Target affiliate URL format
        base_url = f"{config['base_url']}{product_id}"
        params = config['tracking_params'].copy()
        params['clkid'] = tracking_id
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def _build_iherb_link(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build iHerb affiliate link with rewards code
        """
        product_url = product.get('url', '')
        product_code = product.get('product_id', '')
        
        if not product_url and not product_code:
            return ''
        
        # iHerb URL format
        if product_code:
            base_url = f"{config['base_url']}{product_code}"
        else:
            base_url = product_url
        
        # Add rewards code and tracking
        params = config['tracking_params'].copy()
        params['clickid'] = tracking_id
        
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    def _build_dermstore_link(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build Dermstore affiliate link through Rakuten Advertising
        """
        product_id = product.get('product_id', '')
        original_url = product.get('url', '')
        
        if not original_url:
            return ''
        
        # Rakuten deep link format
        rakuten_base = 'https://click.linksynergy.com/deeplink'
        
        params = {
            'id': config['tracking_params']['ranEAID'],
            'mid': config['tracking_params']['ranMID'],
            'murl': urllib.parse.quote(original_url),
            'u1': tracking_id  # Custom tracking parameter
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{rakuten_base}?{query_string}"
    
    def _build_generic_affiliate_link(
        self,
        product: Dict[str, Any],
        config: Dict[str, Any],
        tracking_id: str
    ) -> str:
        """
        Build generic affiliate link for other retailers
        """
        original_url = product.get('url', '')
        
        if not original_url:
            return ''
        
        # Parse existing URL
        parsed_url = urllib.parse.urlparse(original_url)
        existing_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Add affiliate tracking parameters
        tracking_params = config.get('tracking_params', {}).copy()
        tracking_params['sid'] = tracking_id
        
        # Merge with existing parameters
        for key, value in tracking_params.items():
            existing_params[key] = [value]
        
        # Rebuild URL
        new_query = urllib.parse.urlencode(existing_params, doseq=True)
        new_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
        
        return new_url
    
    def _generate_tracking_id(self, user_id: ObjectId, product_id: str) -> str:
        """
        Generate unique tracking ID for click tracking
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        data = f"{user_id}_{product_id}_{timestamp}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def _create_internal_tracking_link(
        self,
        product: Dict[str, Any],
        user_id: ObjectId,
        skin_analysis_id: Optional[ObjectId]
    ) -> str:
        """
        Create internal tracking link for non-affiliate products
        """
        tracking_id = self._generate_tracking_id(user_id, product.get('id', ''))
        self._store_tracking_data(
            tracking_id, user_id, product, skin_analysis_id, 'direct'
        )
        # Use the configured base URL from settings
        return f"{settings.BASE_URL}/api/v1/track/product/{tracking_id}"
    
    def _store_tracking_data(
        self,
        tracking_id: str,
        user_id: ObjectId,
        product: Dict[str, Any],
        skin_analysis_id: Optional[ObjectId],
        retailer: str
    ):
        """
        Store tracking data for click analytics
        """
        try:
            self.db.click_tracking.insert_one({
                'tracking_id': tracking_id,
                'user_id': user_id,
                'product': product,
                'skin_analysis_id': skin_analysis_id,
                'retailer': retailer,
                'created_at': datetime.now(timezone.utc),
                'clicked': False,
                'converted': False,
                'commission_rate': self.affiliate_config.get(retailer, {}).get('commission_rate', 0)
            })
        except Exception as e:
            logger.error(f"Failed to store tracking data: {e}")
    
    def _estimate_commission(self, product: Dict[str, Any], retailer: str) -> Dict[str, float]:
        """
        Estimate commission earnings for a product
        """
        price = product.get('current_price', product.get('price', 0))
        if isinstance(price, str):
            # Extract numeric price from string like "$29.99"
            import re
            match = re.search(r'[\d.]+', price)
            price = float(match.group()) if match else 0
        
        commission_rate = self.affiliate_config.get(retailer, {}).get('commission_rate', 0)
        estimated_commission = price * commission_rate
        
        return {
            'commission_rate': commission_rate,
            'estimated_commission': round(estimated_commission, 2),
            'product_price': price
        }
    
    async def track_click(self, tracking_id: str) -> Optional[str]:
        """
        Track affiliate link click and return redirect URL
        """
        tracking_data = self.db.click_tracking.find_one({'tracking_id': tracking_id})
        
        if not tracking_data:
            return None
        
        # Update click status
        self.db.click_tracking.update_one(
            {'tracking_id': tracking_id},
            {
                '$set': {
                    'clicked': True,
                    'clicked_at': datetime.now(timezone.utc)
                }
            }
        )
        
        # Get the affiliate link to redirect to
        product = tracking_data['product']
        return product.get('affiliate_link', product.get('url', ''))
    
    async def track_conversion(
        self,
        tracking_id: str,
        order_value: float,
        order_id: Optional[str] = None
    ) -> bool:
        """
        Track successful conversion from affiliate link
        
        This would typically be called by a webhook from the affiliate network
        """
        tracking_data = self.db.click_tracking.find_one({'tracking_id': tracking_id})
        
        if not tracking_data:
            return False
        
        commission_rate = tracking_data.get('commission_rate', 0)
        commission_earned = order_value * commission_rate
        
        # Store conversion data
        self.db.conversions.insert_one({
            'tracking_id': tracking_id,
            'user_id': tracking_data['user_id'],
            'product': tracking_data['product'],
            'order_value': order_value,
            'order_id': order_id,
            'commission_rate': commission_rate,
            'commission_earned': commission_earned,
            'converted_at': datetime.now(timezone.utc),
            'retailer': tracking_data.get('retailer')
        })
        
        # Update tracking record
        self.db.click_tracking.update_one(
            {'tracking_id': tracking_id},
            {
                '$set': {
                    'converted': True,
                    'converted_at': datetime.now(timezone.utc),
                    'order_value': order_value,
                    'commission_earned': commission_earned
                }
            }
        )
        
        # Update user lifetime value
        self.db.users.update_one(
            {'_id': tracking_data['user_id']},
            {
                '$inc': {
                    'metrics.total_affiliate_purchases': 1,
                    'metrics.total_affiliate_value': order_value,
                    'metrics.total_commission_generated': commission_earned
                }
            }
        )
        
        return True
    
    def get_analytics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Get affiliate analytics for a date range
        """
        pipeline = [
            {
                '$match': {
                    'created_at': {'$gte': start_date, '$lte': end_date}
                }
            },
            {
                '$group': {
                    '_id': '$retailer',
                    'total_clicks': {'$sum': 1},
                    'unique_users': {'$addToSet': '$user_id'},
                    'conversions': {
                        '$sum': {'$cond': [{'$eq': ['$converted', True]}, 1, 0]}
                    },
                    'total_revenue': {'$sum': '$order_value'},
                    'total_commission': {'$sum': '$commission_earned'}
                }
            },
            {
                '$project': {
                    'retailer': '$_id',
                    'total_clicks': 1,
                    'unique_users': {'$size': '$unique_users'},
                    'conversions': 1,
                    'conversion_rate': {
                        '$multiply': [
                            {'$divide': ['$conversions', '$total_clicks']},
                            100
                        ]
                    },
                    'total_revenue': 1,
                    'total_commission': 1,
                    '_id': 0
                }
            }
        ]
        
        results = list(self.db.click_tracking.aggregate(pipeline))
        
        # Calculate totals
        totals = {
            'total_clicks': sum(r['total_clicks'] for r in results),
            'total_conversions': sum(r['conversions'] for r in results),
            'total_revenue': sum(r['total_revenue'] for r in results),
            'total_commission': sum(r['total_commission'] for r in results),
            'by_retailer': results
        }
        
        if totals['total_clicks'] > 0:
            totals['overall_conversion_rate'] = (
                totals['total_conversions'] / totals['total_clicks'] * 100
            )
        else:
            totals['overall_conversion_rate'] = 0
        
        return totals


# Global service instance
def get_affiliate_service(db: Database) -> AffiliateService:
    """Get affiliate service instance"""
    return AffiliateService(db)