# chatbot/services/serpapi_service.py - COMPLETE FIXED VERSION
import requests
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode
from django.conf import settings
import asyncio
import aiohttp
import re

logger = logging.getLogger(__name__)

class SerpAPIService:
    """
    Complete SerpAPI service for external product and service search
    Fixed to handle Nigeria location properly
    """
    
    def __init__(self):
        # Use your API key
        self.api_key = "7e724f18b98b7b44714da50a198ddc2ca5fe92b051a0cd51f129c3887a0893f6"
        self.base_url = "https://serpapi.com/search"
        self.timeout = 15
        self.max_results = 10
    
    async def search_products(self, query: str, location: str = "Nigeria", **kwargs) -> Dict[str, Any]:
        """
        Search for products using Google Shopping via SerpAPI
        FIXED: Removed problematic 'gl' parameter for Nigeria
        """
        try:
            logger.info(f"Searching products with SerpAPI: '{query}' in {location}")
            
            # Build search parameters - FIXED VERSION
            params = {
                'engine': 'google_shopping',
                'q': query,
                'location': location,
                'api_key': self.api_key,
                'num': kwargs.get('limit', self.max_results),
                'hl': 'en'
                # REMOVED: 'gl': 'ng' - This was causing the error
                # Google Shopping API doesn't support Nigeria as gl parameter
            }
            
            # Optional: Use supported country codes for broader search if needed
            # Uncomment one of these if you want to expand search to supported regions:
            # params['gl'] = 'us'  # United States
            # params['gl'] = 'uk'  # United Kingdom
            # params['gl'] = 'za'  # South Africa (closest supported African country)
            
            # Add price filters if provided
            if kwargs.get('min_price'):
                params['min_price'] = kwargs['min_price']
            if kwargs.get('max_price'):
                params['max_price'] = kwargs['max_price']
            
            # Add sorting if specified
            if kwargs.get('sort_by'):
                params['sort'] = kwargs['sort_by']  # 'price_low_to_high', 'price_high_to_low', 'rating'
            
            return await self._make_async_request(params, 'products')
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'total_found': 0,
                'query': query,
                'source': 'serpapi_shopping'
            }
    
    async def search_local_services(self, query: str, location: str = "Lagos, Nigeria", **kwargs) -> Dict[str, Any]:
        """
        Search for local services using Google Maps via SerpAPI
        """
        try:
            logger.info(f"Searching services with SerpAPI: '{query}' in {location}")
            
            # Build search parameters
            params = {
                'engine': 'google_maps',
                'q': query,
                'location': location,
                'api_key': self.api_key,
                'num': kwargs.get('limit', self.max_results),
                'hl': 'en'
                # Note: Google Maps API handles Nigeria location correctly
            }
            
            # Add radius filter if specified
            if kwargs.get('radius'):
                params['radius'] = kwargs['radius']
            
            return await self._make_async_request(params, 'services')
            
        except Exception as e:
            logger.error(f"Error searching services: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'services': [],
                'total_found': 0,
                'query': query,
                'source': 'serpapi_maps'
            }
    
    async def _make_async_request(self, params: Dict, result_type: str) -> Dict[str, Any]:
        """
        Make async request to SerpAPI with proper error handling
        """
        import time
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                url = f"{self.base_url}?{urlencode(params)}"
                logger.info(f"Making SerpAPI request to: {url[:100]}...")
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        search_time = time.time() - start_time
                        
                        logger.info(f"SerpAPI request successful in {search_time:.2f}s")
                        
                        # Check for API errors in response
                        if 'error' in data:
                            logger.error(f"SerpAPI returned error: {data['error']}")
                            return {
                                'success': False,
                                'error': data['error'],
                                result_type: [],
                                'total_found': 0
                            }
                        
                        if result_type == 'products':
                            return self._parse_shopping_results(data, search_time)
                        elif result_type == 'services':
                            return self._parse_maps_results(data, search_time)
                        else:
                            return {
                                'success': False, 
                                'error': 'Unknown result type',
                                result_type: [],
                                'total_found': 0
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"SerpAPI error {response.status}: {error_text}")
                        
                        # Handle specific error cases
                        if response.status == 400 and 'Unsupported' in error_text:
                            logger.warning("Retrying with fallback parameters...")
                            # Remove problematic parameters and retry
                            fallback_params = {k: v for k, v in params.items() if k not in ['gl']}
                            return await self._make_fallback_request(fallback_params, result_type)
                        
                        return {
                            'success': False,
                            'error': f'API request failed with status {response.status}: {error_text}',
                            result_type: [],
                            'total_found': 0
                        }
                        
        except asyncio.TimeoutError:
            logger.error("SerpAPI request timeout")
            return {
                'success': False,
                'error': 'Request timeout - please try again',
                result_type: [],
                'total_found': 0
            }
        except Exception as e:
            logger.error(f"SerpAPI request error: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}',
                result_type: [],
                'total_found': 0
            }
    
    async def _make_fallback_request(self, params: Dict, result_type: str) -> Dict[str, Any]:
        """
        Make a fallback request with simplified parameters
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                url = f"{self.base_url}?{urlencode(params)}"
                logger.info(f"Making fallback SerpAPI request to: {url[:100]}...")
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'error' in data:
                            return {
                                'success': False,
                                'error': data['error'],
                                result_type: [],
                                'total_found': 0
                            }
                        
                        if result_type == 'products':
                            return self._parse_shopping_results(data, 0)
                        elif result_type == 'services':
                            return self._parse_maps_results(data, 0)
                    
                    return {
                        'success': False,
                        'error': f'Fallback request also failed with status {response.status}',
                        result_type: [],
                        'total_found': 0
                    }
        except Exception as e:
            logger.error(f"Fallback request error: {str(e)}")
            return {
                'success': False,
                'error': f'Both primary and fallback requests failed: {str(e)}',
                result_type: [],
                'total_found': 0
            }
    
    def _parse_shopping_results(self, data: Dict, search_time: float) -> Dict[str, Any]:
        """
        Parse Google Shopping results from SerpAPI with complete data extraction
        """
        try:
            shopping_results = data.get('shopping_results', [])
            products = []
            
            logger.info(f"Parsing {len(shopping_results)} shopping results")
            
            if not shopping_results:
                logger.warning("No shopping results found in response")
                return {
                    'success': True,
                    'products': [],
                    'total_found': 0,
                    'search_time': search_time,
                    'query': data.get('search_parameters', {}).get('q', ''),
                    'source': 'serpapi_shopping'
                }
            
            for i, result in enumerate(shopping_results[:self.max_results]):
                try:
                    # Extract comprehensive product information
                    product = {
                        # Basic product info
                        'title': result.get('title', 'Unknown Product'),
                        'name': result.get('title', 'Unknown Product'),
                        'price': self._extract_numeric_price(result.get('price', '')),
                        'formatted_price': result.get('price', 'Price not available'),
                        'currency': self._extract_currency(result.get('price', '')),
                        
                        # Images and links
                        'image': result.get('thumbnail', ''),
                        'thumbnail': result.get('thumbnail', ''),
                        'link': result.get('link', ''),
                        'product_link': result.get('link', ''),
                        
                        # Seller information
                        'source': result.get('source', 'Unknown Store'),
                        'seller_name': result.get('source', 'Unknown Store'),
                        'seller_logo': result.get('source_icon', ''),
                        'store_name': result.get('source', 'Unknown Store'),
                        
                        # Product details
                        'description': result.get('snippet', ''),
                        'snippet': result.get('snippet', ''),
                        'rating': self._extract_rating(result.get('rating')),
                        'reviews_count': self._extract_reviews_count(result.get('reviews')),
                        'reviews': self._extract_reviews_count(result.get('reviews')),
                        
                        # Availability and shipping
                        'availability': result.get('delivery', 'Contact seller'),
                        'delivery': result.get('delivery', ''),
                        'shipping': result.get('shipping', ''),
                        'condition': result.get('condition', 'New'),
                        
                        # Pricing details
                        'original_price': result.get('original_price', ''),
                        'discount': result.get('discount', ''),
                        'sale_price': result.get('sale_price', ''),
                        
                        # Additional metadata
                        'position': i + 1,
                        'rank': i + 1,
                        'id': f"ext_product_{i}",
                        'result_type': 'external_product',
                        'confidence': 0.8,
                        'source_type': 'serpapi_shopping',
                        'extracted_at': search_time
                    }
                    
                    # Clean up and validate data
                    product = self._clean_product_data(product)
                    products.append(product)
                    
                except Exception as e:
                    logger.error(f"Error parsing product result {i}: {str(e)}")
                    continue
            
            logger.info(f"Successfully parsed {len(products)} products")
            
            return {
                'success': True,
                'products': products,
                'total_found': len(shopping_results),
                'search_time': search_time,
                'query': data.get('search_parameters', {}).get('q', ''),
                'location': data.get('search_parameters', {}).get('location', ''),
                'source': 'serpapi_shopping',
                'api_response_time': search_time
            }
            
        except Exception as e:
            logger.error(f"Error parsing shopping results: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse shopping results: {str(e)}',
                'products': [],
                'total_found': 0
            }
    
    def _parse_maps_results(self, data: Dict, search_time: float) -> Dict[str, Any]:
        """
        Parse Google Maps results from SerpAPI with complete data extraction
        """
        try:
            local_results = data.get('local_results', [])
            services = []
            
            logger.info(f"Parsing {len(local_results)} maps results")
            
            if not local_results:
                logger.warning("No local results found in response")
                return {
                    'success': True,
                    'services': [],
                    'total_found': 0,
                    'search_time': search_time,
                    'query': data.get('search_parameters', {}).get('q', ''),
                    'source': 'serpapi_maps'
                }
            
            for i, result in enumerate(local_results[:self.max_results]):
                try:
                    # Extract comprehensive service information
                    service = {
                        # Basic service info
                        'title': result.get('title', 'Unknown Service'),
                        'name': result.get('title', 'Unknown Service'),
                        'description': result.get('snippet', result.get('type', 'Service provider')),
                        'snippet': result.get('snippet', ''),
                        'type': result.get('type', 'Service'),
                        
                        # Location information
                        'address': result.get('address', 'Address not available'),
                        'location': result.get('address', 'Location not available'),
                        'coordinates': result.get('gps_coordinates', {}),
                        'gps_coordinates': result.get('gps_coordinates', {}),
                        
                        # Contact information
                        'phone': result.get('phone', ''),
                        'phone_number': result.get('phone', ''),
                        'website': result.get('website', ''),
                        
                        # Images and links
                        'image': result.get('thumbnail', ''),
                        'thumbnail': result.get('thumbnail', ''),
                        'link': result.get('website', ''),
                        
                        # Rating and reviews
                        'rating': self._extract_rating(result.get('rating')),
                        'reviews_count': self._extract_reviews_count(result.get('reviews')),
                        'reviews': self._extract_reviews_count(result.get('reviews')),
                        
                        # Business information
                        'hours': result.get('hours', {}),
                        'business_hours': result.get('hours', {}),
                        'price_range': result.get('price', 'Contact for pricing'),
                        'price': result.get('price', 'Contact for pricing'),
                        'formatted_price': result.get('price', 'Contact for pricing'),
                        
                        # Categories and classification
                        'categories': result.get('type', '').split(', ') if result.get('type') else ['Service'],
                        'category': result.get('type', 'Service'),
                        
                        # Additional details
                        'place_id': result.get('place_id', ''),
                        'service_options': result.get('service_options', {}),
                        'amenities': result.get('amenities', []),
                        
                        # Provider information structure
                        'provider': {
                            'name': result.get('title', 'Unknown'),
                            'rating': self._extract_rating(result.get('rating')),
                            'reviews': self._extract_reviews_count(result.get('reviews')),
                            'phone': result.get('phone', ''),
                            'website': result.get('website', ''),
                            'address': result.get('address', ''),
                            'coordinates': result.get('gps_coordinates', {})
                        },
                        
                        # Metadata
                        'position': i + 1,
                        'rank': i + 1,
                        'id': f"ext_service_{i}",
                        'result_type': 'external_service',
                        'confidence': 0.8,
                        'source_type': 'serpapi_maps',
                        'extracted_at': search_time
                    }
                    
                    # Clean up and validate data
                    service = self._clean_service_data(service)
                    services.append(service)
                    
                except Exception as e:
                    logger.error(f"Error parsing service result {i}: {str(e)}")
                    continue
            
            logger.info(f"Successfully parsed {len(services)} services")
            
            return {
                'success': True,
                'services': services,
                'total_found': len(local_results),
                'search_time': search_time,
                'query': data.get('search_parameters', {}).get('q', ''),
                'location': data.get('search_parameters', {}).get('location', ''),
                'source': 'serpapi_maps',
                'api_response_time': search_time
            }
            
        except Exception as e:
            logger.error(f"Error parsing maps results: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse maps results: {str(e)}',
                'services': [],
                'total_found': 0
            }
    
    def _clean_product_data(self, product: Dict) -> Dict:
        """Clean and validate product data"""
        try:
            # Clean title/name
            if product['title']:
                # Remove common e-commerce suffixes
                title = product['title']
                for suffix in [' - Amazon.com', ' | eBay', ' - Walmart.com', ' - Best Buy', ' - Target', ' - Shop']:
                    if title.endswith(suffix):
                        title = title[:-len(suffix)]
                product['title'] = title.strip()
                product['name'] = title.strip()
            
            # Validate and clean image URL
            if product.get('image') and not product['image'].startswith('http'):
                if product['image'].startswith('//'):
                    product['image'] = f"https:{product['image']}"
                else:
                    product['image'] = ''
            
            # Validate and clean product link
            if not product.get('link') or not product['link'].startswith('http'):
                product['link'] = ''
            
            # Ensure numeric price is valid
            if not isinstance(product.get('price'), (int, float)) or product['price'] < 0:
                product['price'] = 0.0
            
            return product
            
        except Exception as e:
            logger.error(f"Error cleaning product data: {str(e)}")
            return product
    
    def _clean_service_data(self, service: Dict) -> Dict:
        """Clean and validate service data"""
        try:
            # Clean phone number
            if service.get('phone'):
                phone = service['phone'].strip()
                # Basic phone number validation
                if phone and not phone.startswith('+'):
                    if phone.startswith('0'):
                        # Nigerian format, convert to international
                        phone = f"+234{phone[1:]}"
                service['phone'] = phone
                service['phone_number'] = phone
            
            # Validate and clean image URL
            if service.get('image') and not service['image'].startswith('http'):
                if service['image'].startswith('//'):
                    service['image'] = f"https:{service['image']}"
                else:
                    service['image'] = ''
            
            # Validate website URL
            if service.get('website') and not service['website'].startswith('http'):
                if service['website'].startswith('www.'):
                    service['website'] = f"https://{service['website']}"
                else:
                    service['website'] = ''
            
            # Ensure coordinates are valid
            coords = service.get('coordinates', {})
            if coords:
                try:
                    lat = float(coords.get('latitude', 0))
                    lng = float(coords.get('longitude', 0))
                    if lat == 0 and lng == 0:
                        service['coordinates'] = {}
                except (ValueError, TypeError):
                    service['coordinates'] = {}
            
            return service
            
        except Exception as e:
            logger.error(f"Error cleaning service data: {str(e)}")
            return service
    
    def _extract_numeric_price(self, price_str: str) -> float:
        """Extract numeric price from price string"""
        if not price_str:
            return 0.0
        
        try:
            # Remove currency symbols and extract numbers
            clean_price = re.sub(r'[^\d.,]', '', str(price_str))
            if clean_price:
                # Handle comma as thousands separator
                if ',' in clean_price and '.' in clean_price:
                    # Format like "1,234.56"
                    clean_price = clean_price.replace(',', '')
                elif ',' in clean_price:
                    # Could be thousands separator or decimal separator
                    parts = clean_price.split(',')
                    if len(parts) == 2 and len(parts[1]) <= 2:
                        # Likely decimal separator
                        clean_price = clean_price.replace(',', '.')
                    else:
                        # Likely thousands separator
                        clean_price = clean_price.replace(',', '')
                
                return float(clean_price)
        except (ValueError, TypeError):
            pass
        
        return 0.0
    
    def _extract_currency(self, price_str: str) -> str:
        """Extract currency from price string"""
        if not price_str:
            return 'USD'
        
        price_lower = str(price_str).lower()
        
        # Check for common currency indicators
        if '₦' in price_str or 'naira' in price_lower or 'ngn' in price_lower:
            return 'NGN'
        elif '$' in price_str or 'dollar' in price_lower or 'usd' in price_lower:
            return 'USD'
        elif '€' in price_str or 'euro' in price_lower or 'eur' in price_lower:
            return 'EUR'
        elif '£' in price_str or 'pound' in price_lower or 'gbp' in price_lower:
            return 'GBP'
        elif '¥' in price_str or 'yen' in price_lower or 'jpy' in price_lower:
            return 'JPY'
        
        return 'USD'  # Default to USD
    
    def _extract_rating(self, rating_data) -> Dict[str, Any]:
        """Extract and validate rating information"""
        rating_info = {'average': 0.0, 'count': 0}
        
        if not rating_data:
            return rating_info
        
        try:
            if isinstance(rating_data, (int, float)):
                rating_info['average'] = max(0.0, min(5.0, float(rating_data)))
            elif isinstance(rating_data, str):
                # Extract rating from string like "4.5 stars" or "4.5/5"
                rating_match = re.search(r'(\d+\.?\d*)', rating_data)
                if rating_match:
                    rating_val = float(rating_match.group(1))
                    rating_info['average'] = max(0.0, min(5.0, rating_val))
            elif isinstance(rating_data, dict):
                # Handle structured rating data
                if 'average' in rating_data:
                    rating_info['average'] = max(0.0, min(5.0, float(rating_data['average'])))
                if 'count' in rating_data:
                    rating_info['count'] = int(rating_data['count'])
        except (ValueError, TypeError):
            pass
        
        return rating_info
    
    def _extract_reviews_count(self, reviews_data) -> int:
        """Extract reviews count from various formats"""
        if not reviews_data:
            return 0
        
        try:
            if isinstance(reviews_data, int):
                return reviews_data
            elif isinstance(reviews_data, str):
                # Extract number from strings like "123 reviews" or "(45)"
                numbers = re.findall(r'\d+', reviews_data)
                if numbers:
                    return int(numbers[0])
            elif isinstance(reviews_data, dict) and 'count' in reviews_data:
                return int(reviews_data['count'])
        except (ValueError, TypeError):
            pass
        
        return 0
    
    def validate_api_key(self) -> bool:
        """Validate SerpAPI key with a simple test request"""
        try:
            params = {
                'engine': 'google',
                'q': 'test',
                'api_key': self.api_key,
                'num': 1
            }
            
            response = requests.get(self.base_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return 'error' not in data
            return False
            
        except Exception as e:
            logger.error(f"Error validating SerpAPI key: {str(e)}")
            return False
    
    def get_api_info(self) -> Dict[str, Any]:
        """Get API usage info and limits"""
        try:
            params = {
                'engine': 'google',
                'q': 'api info',
                'api_key': self.api_key,
                'num': 1
            }
            
            response = requests.get(self.base_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'valid': 'error' not in data,
                    'search_metadata': data.get('search_metadata', {}),
                    'api_key_valid': True
                }
            
            return {'valid': False, 'api_key_valid': False}
            
        except Exception as e:
            logger.error(f"Error getting API info: {str(e)}")
            return {'valid': False, 'error': str(e)}

# Export the service
__all__ = ['SerpAPIService']