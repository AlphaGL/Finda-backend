# chatbot/services/serpapi_service.py - UPDATED VERSION
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
    Enhanced SerpAPI service for external product and service search
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
        """
        try:
            logger.info(f"Searching products with SerpAPI: '{query}' in {location}")
            
            # Build search parameters
            params = {
                'engine': 'google_shopping',
                'q': query,
                'location': location,
                'api_key': self.api_key,
                'num': kwargs.get('limit', self.max_results),
                'hl': 'en',
                'gl': 'ng'  # Nigeria
            }
            
            # Add price filters if provided
            if kwargs.get('min_price'):
                params['min_price'] = kwargs['min_price']
            if kwargs.get('max_price'):
                params['max_price'] = kwargs['max_price']
            
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
            }
            
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
        Make async request to SerpAPI
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
        """
        Parse Google Shopping results from SerpAPI
        """
        try:
            shopping_results = data.get('shopping_results', [])
            products = []
            
            logger.info(f"Parsing {len(shopping_results)} shopping results")
            
            for i, result in enumerate(shopping_results[:self.max_results]):
                try:
                    # Extract product information
                    product = {
                        # Required fields for your format
                        'title': result.get('title', 'Unknown Product'),
                        'price': self._extract_numeric_price(result.get('price', '')),
                        'image': result.get('thumbnail', ''),
                        'seller_name': result.get('source', 'Unknown Store'),
                        'seller_logo': result.get('source_icon', ''),  # If available
                        'link': result.get('link', ''),
                        
                        # Additional fields
                        'name': result.get('title', 'Unknown Product'),
                        'formatted_price': result.get('price', 'Price not available'),
                        'currency': self._extract_currency(result.get('price', '')),
                        'source': result.get('source', 'Unknown Store'),
                        'rating': self._extract_rating(result.get('rating')),
                        'reviews_count': result.get('reviews', 0),
                        'description': result.get('snippet', ''),
                        'availability': result.get('delivery', 'Contact seller'),
                        'shipping': result.get('shipping', ''),
                        
                        # Metadata
                        'id': f"ext_product_{i}",
                        'result_type': 'external_product',
                        'confidence': 0.8,
                        'source_type': 'serpapi_shopping',
                        'position': i + 1
                    }
                    
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
    
    def _parse_maps_results(self, data: Dict, search_time: float) -> Dict[str, Any]:
        """
        Parse Google Maps results from SerpAPI
        """
        try:
            local_results = data.get('local_results', [])
            services = []
            
            logger.info(f"Parsing {len(local_results)} maps results")
            
            for i, result in enumerate(local_results[:self.max_results]):
                try:
                    # Extract service information
                    service = {
                        # Required fields for your format
                        'title': result.get('title', 'Unknown Service'),
                        'price': 'Contact for pricing',  # Maps usually doesn't have prices
                        'image': result.get('thumbnail', ''),
                        'seller_name': result.get('title', 'Unknown Provider'),
                        'seller_logo': '',  # Usually not available in maps
                        'link': result.get('website', ''),
                        
                        # Additional fields
                        'name': result.get('title', 'Unknown Service'),
                        'description': result.get('snippet', result.get('type', 'Service provider')),
                        'rating': self._extract_rating(result.get('rating')),
                        'reviews_count': result.get('reviews', 0),
                        'address': result.get('address', 'Address not available'),
                        'location': result.get('address', 'Location not available'),
                        'phone': result.get('phone', ''),
                        'website': result.get('website', ''),
                        'hours': result.get('hours', {}),
                        'price_range': result.get('price', 'Contact for pricing'),
                        'formatted_price': result.get('price', 'Contact for pricing'),
                        'categories': result.get('type', '').split(', ') if result.get('type') else [],
                        
                        # Provider information
                        'provider': {
                            'name': result.get('title', 'Unknown'),
                            'rating': self._extract_rating(result.get('rating')),
                            'reviews': result.get('reviews', 0),
                            'phone': result.get('phone', ''),
                            'website': result.get('website', ''),
                            'address': result.get('address', '')
                        },
                        
                        # Metadata
                        'id': f"ext_service_{i}",
                        'result_type': 'external_service',
                        'confidence': 0.8,
                        'source_type': 'serpapi_maps',
                        'position': i + 1
                    }
                    
                    # Add coordinates if available
                    if result.get('gps_coordinates'):
                        service['coordinates'] = result['gps_coordinates']
                    
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
                'source': 'serpapi_maps'
            }
            
        except Exception as e:
            logger.error(f"Error parsing maps results: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to parse results: {str(e)}',
                'services': [],
                'total_found': 0
            }
    
    def _extract_numeric_price(self, price_str: str) -> float:
        """Extract numeric price from price string"""
        if not price_str:
            return 0.0
        
        try:
            # Remove currency symbols and commas, extract numbers
            price_match = re.search(r'[\d,]+\.?\d*', str(price_str).replace(',', ''))
            if price_match:
                return float(price_match.group().replace(',', ''))
        except Exception:
            pass
        
        return 0.0
    
    def _extract_currency(self, price_str: str) -> str:
        """Extract currency from price string"""
        if not price_str:
            return 'USD'
        
        price_lower = str(price_str).lower()
        if '₦' in price_str or 'naira' in price_lower or 'ngn' in price_lower:
            return 'NGN'
        elif '$' in price_str or 'dollar' in price_lower or 'usd' in price_lower:
            return 'USD'
        elif '€' in price_str or 'euro' in price_lower:
            return 'EUR'
        elif '£' in price_str or 'pound' in price_lower:
            return 'GBP'
        
        return 'USD'  # Default
    
    def _extract_rating(self, rating_data) -> Dict[str, Any]:
        """Extract rating information"""
        if not rating_data:
            return {'average': 0.0, 'count': 0}
        
        try:
            if isinstance(rating_data, (int, float)):
                return {'average': float(rating_data), 'count': 0}
            elif isinstance(rating_data, str):
                rating_match = re.search(r'(\d+\.?\d*)', rating_data)
                if rating_match:
                    return {'average': float(rating_match.group(1)), 'count': 0}
        except Exception:
            pass
        
        return {'average': 0.0, 'count': 0}
    
    def format_results_for_response(self, results: Dict) -> str:
        """
        Format external search results for display in chatbot response
        """
        try:
            formatted_parts = []
            
            # Format products if available
            products = results.get('products', [])
            if products:
                formatted_parts.append("🛍️ **External Products Found:**\n")
                
                for i, product in enumerate(products[:5], 1):  # Limit to top 5
                    formatted_parts.append(f"**{i}. {product['name']}**")
                    formatted_parts.append(f"💰 Price: {product['formatted_price']}")
                    formatted_parts.append(f"🏪 Store: {product['source']}")
                    
                    if product.get('rating', {}).get('average', 0) > 0:
                        rating = product['rating']['average']
                        formatted_parts.append(f"⭐ Rating: {rating:.1f}/5")
                    
                    if product.get('link'):
                        formatted_parts.append(f"🔗 [View Product]({product['link']})")
                    
                    formatted_parts.append("")  # Empty line
            
            # Format services if available
            services = results.get('services', [])
            if services:
                formatted_parts.append("🔧 **External Services Found:**\n")
                
                for i, service in enumerate(services[:3], 1):  # Limit to top 3
                    formatted_parts.append(f"**{i}. {service['name']}**")
                    formatted_parts.append(f"📍 Location: {service['location']}")
                    formatted_parts.append(f"💼 Service: {service['formatted_price']}")
                    
                    if service.get('phone'):
                        formatted_parts.append(f"📞 Phone: {service['phone']}")
                    
                    if service.get('rating', {}).get('average', 0) > 0:
                        rating = service['rating']['average']
                        formatted_parts.append(f"⭐ Rating: {rating:.1f}/5")
                    
                    if service.get('website'):
                        formatted_parts.append(f"🌐 [Visit Website]({service['website']})")
                    
                    formatted_parts.append("")  # Empty line
            
            result = "\n".join(formatted_parts)
            logger.info(f"Formatted external results: {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Error formatting results: {str(e)}")
            return ""
    
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

# Export the service
__all__ = ['SerpAPIService']