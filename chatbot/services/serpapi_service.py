# ai_chatbot/services/serpapi_service.py
import requests
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode
from django.conf import settings
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

class SerpAPIService:
    """Service to search products and services using SerpAPI"""
    
    def __init__(self):
        self.api_key = "7e724f18b98b7b44714da50a198ddc2ca5fe92b051a0cd51f129c3887a0893f6"
        self.base_url = "https://serpapi.com/search"
        self.timeout = 10
        self.max_results = 10
    
    async def search_products(self, query: str, location: str = "Nigeria", **kwargs) -> Dict[str, Any]:
        """Search for products using Google Shopping"""
        try:
            # Build search parameters
            params = {
                'engine': 'google_shopping',
                'q': query,
                'location': location,
                'api_key': self.api_key,
                'num': kwargs.get('limit', self.max_results),
                'hl': 'en'
            }
            
            # Add optional filters
            if kwargs.get('min_price'):
                params['min_price'] = kwargs['min_price']
            if kwargs.get('max_price'):
                params['max_price'] = kwargs['max_price']
            
            return await self._make_async_request(params, 'products')
            
        except Exception as e:
            logger.error(f"Error searching products with SerpAPI: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'total_found': 0
            }
    
    async def search_local_services(self, query: str, location: str = "Lagos, Nigeria", **kwargs) -> Dict[str, Any]:
        """Search for local services using Google Local"""
        try:
            # Build search parameters for local services
            params = {
                'engine': 'google_maps',
                'q': query,
                'location': location,
                'api_key': self.api_key,
                'num': kwargs.get('limit', self.max_results),
                'hl': 'en'
            }
            
            return await self._make_async_request(params, 'services')
            
        except Exception as e:
            logger.error(f"Error searching services with SerpAPI: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'services': [],
                'total_found': 0
            }
    
    async def search_general(self, query: str, location: str = "Nigeria", **kwargs) -> Dict[str, Any]:
        """General search that can find both products and services"""
        try:
            # Try products first
            products_result = await self.search_products(query, location, **kwargs)
            
            # Try services if products are limited
            services_result = await self.search_local_services(query, location, **kwargs)
            
            total_results = len(products_result.get('products', [])) + len(services_result.get('services', []))
            
            return {
                'success': True,
                'query': query,
                'location': location,
                'products': products_result.get('products', []),
                'services': services_result.get('services', []),
                'total_found': total_results,
                'search_time': max(
                    products_result.get('search_time', 0),
                    services_result.get('search_time', 0)
                )
            }
            
        except Exception as e:
            logger.error(f"Error in general search: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_found': 0
            }
    
    async def _make_async_request(self, params: Dict, result_type: str) -> Dict[str, Any]:
        """Make async request to SerpAPI"""
        import time
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                url = f"{self.base_url}?{urlencode(params)}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        search_time = time.time() - start_time
                        
                        if result_type == 'products':
                            return self._parse_shopping_results(data, search_time)
                        elif result_type == 'services':
                            return self._parse_local_results(data, search_time)
                        else:
                            return {'success': False, 'error': 'Unknown result type'}
                    else:
                        error_text = await response.text()
                        logger.error(f"SerpAPI error {response.status}: {error_text}")
                        return {
                            'success': False,
                            'error': f'API request failed with status {response.status}',
                            result_type: [],
                            'total_found': 0
                        }
                        
        except asyncio.TimeoutError:
            logger.error("SerpAPI request timeout")
            return {
                'success': False,
                'error': 'Request timeout',
                result_type: [],
                'total_found': 0
            }
        except Exception as e:
            logger.error(f"SerpAPI request error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                result_type: [],
                'total_found': 0
            }
    
    def _parse_shopping_results(self, data: Dict, search_time: float) -> Dict[str, Any]:
        """Parse Google Shopping results"""
        try:
            shopping_results = data.get('shopping_results', [])
            products = []
            
            for result in shopping_results[:self.max_results]:
                product = {
                    'id': result.get('product_id', f"ext_{hash(result.get('title', ''))}"),
                    'name': result.get('title', 'Unknown Product'),
                    'price': self._extract_price(result.get('price')),
                    'formatted_price': result.get('price', 'Price not available'),
                    'currency': self._extract_currency(result.get('price', '')),
                    'image': result.get('thumbnail', ''),
                    'source': result.get('source', 'Unknown Store'),
                    'link': result.get('link', ''),
                    'rating': self._extract_rating(result.get('rating')),
                    'reviews_count': result.get('reviews', 0),
                    'description': result.get('snippet', ''),
                    'availability': result.get('delivery', 'Contact seller'),
                    'location': 'Online Store',  # Most shopping results are online
                    'result_type': 'external_product',
                    'confidence': 0.8,
                    'source_type': 'serpapi_shopping'
                }
                
                # Add shipping info if available
                if result.get('shipping'):
                    product['shipping'] = result['shipping']
                
                products.append(product)
            
            return {
                'success': True,
                'products': products,
                'total_found': len(shopping_results),
                'search_time': search_time,
                'source': 'serpapi_shopping'
            }
            
        except Exception as e:
            logger.error(f"Error parsing shopping results: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse results: {str(e)}',
                'products': [],
                'total_found': 0
            }
    
    def _parse_local_results(self, data: Dict, search_time: float) -> Dict[str, Any]:
        """Parse Google Local/Maps results"""
        try:
            local_results = data.get('local_results', [])
            services = []
            
            for result in local_results[:self.max_results]:
                service = {
                    'id': result.get('place_id', f"ext_{hash(result.get('title', ''))}"),
                    'name': result.get('title', 'Unknown Service'),
                    'description': result.get('snippet', result.get('type', 'Service provider')),
                    'rating': self._extract_rating(result.get('rating')),
                    'reviews_count': result.get('reviews', 0),
                    'address': result.get('address', 'Address not available'),
                    'location': result.get('address', 'Location not available'),
                    'phone': result.get('phone', ''),
                    'website': result.get('website', ''),
                    'link': result.get('website', ''),
                    'hours': result.get('hours', {}),
                    'price_range': result.get('price', 'Contact for pricing'),
                    'formatted_price': result.get('price', 'Contact for pricing'),
                    'image': result.get('thumbnail', ''),
                    'categories': result.get('type', '').split(', ') if result.get('type') else [],
                    'result_type': 'external_service',
                    'confidence': 0.8,
                    'source_type': 'serpapi_local',
                    'provider': {
                        'name': result.get('title', 'Unknown'),
                        'rating': self._extract_rating(result.get('rating')),
                        'reviews': result.get('reviews', 0)
                    }
                }
                
                # Add coordinates if available
                if result.get('gps_coordinates'):
                    service['coordinates'] = result['gps_coordinates']
                
                services.append(service)
            
            return {
                'success': True,
                'services': services,
                'total_found': len(local_results),
                'search_time': search_time,
                'source': 'serpapi_local'
            }
            
        except Exception as e:
            logger.error(f"Error parsing local results: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse results: {str(e)}',
                'services': [],
                'total_found': 0
            }
    
    def _extract_price(self, price_str: str) -> float:
        """Extract numeric price from price string"""
        if not price_str:
            return 0.0
        
        try:
            import re
            # Remove currency symbols and extract numbers
            price_match = re.search(r'[\d,]+\.?\d*', str(price_str).replace(',', ''))
            if price_match:
                return float(price_match.group())
        except Exception:
            pass
        
        return 0.0
    
    def _extract_currency(self, price_str: str) -> str:
        """Extract currency from price string"""
        if not price_str:
            return 'USD'  # Default
        
        price_lower = str(price_str).lower()
        if '₦' in price_str or 'naira' in price_lower:
            return 'NGN'
        elif '$' in price_str or 'dollar' in price_lower:
            return 'USD'
        elif '€' in price_str or 'euro' in price_lower:
            return 'EUR'
        elif '£' in price_str or 'pound' in price_lower:
            return 'GBP'
        
        return 'USD'  # Default
    
    def _extract_rating(self, rating_data) -> Dict[str, Any]:
        """Extract rating information"""
        if not rating_data:
            return {'average': 0, 'count': 0}
        
        try:
            if isinstance(rating_data, (int, float)):
                return {'average': float(rating_data), 'count': 0}
            elif isinstance(rating_data, str):
                import re
                rating_match = re.search(r'(\d+\.?\d*)', rating_data)
                if rating_match:
                    return {'average': float(rating_match.group(1)), 'count': 0}
        except Exception:
            pass
        
        return {'average': 0, 'count': 0}
    
    def validate_api_key(self) -> bool:
        """Validate SerpAPI key"""
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
    
    async def get_search_suggestions(self, query: str) -> List[str]:
        """Get search suggestions from SerpAPI"""
        try:
            params = {
                'engine': 'google_autocomplete',
                'q': query,
                'api_key': self.api_key
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                url = f"{self.base_url}?{urlencode(params)}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        suggestions = data.get('suggestions', [])
                        return [s.get('value', '') for s in suggestions[:10]]
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting search suggestions: {str(e)}")
            return []