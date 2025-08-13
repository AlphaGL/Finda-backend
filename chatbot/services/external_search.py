# ai_chatbot/services/external_search.py (FIXED VERSION)
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from .serpapi_service import SerpAPIService
from ..utils import SearchHelper, CacheManager, PerformanceMonitor

logger = logging.getLogger(__name__)

class EnhancedExternalSearchService:
    """Enhanced external search service with SerpAPI integration"""
    
    def __init__(self):
        self.serpapi = SerpAPIService()
        self.cache_manager = CacheManager()
        self.search_helper = SearchHelper()
        self.performance_monitor = PerformanceMonitor()
    
    async def search(self, query: str, search_type: str = 'both', location_context: Dict = None, **kwargs) -> Dict[str, Any]:
        """
        Main search method that uses SerpAPI
        """
        try:
            self.performance_monitor.start_timer('external_search')
            logger.info(f"Starting external search for: '{query}' (type: {search_type})")
            
            # Extract location
            location = self._extract_location(location_context)
            logger.info(f"Using location: {location}")
            
            # Check cache first
            cache_key = f"{query}_{search_type}_{location}"
            try:
                cached_result = self.cache_manager.get_cached_search_results(cache_key)
                if cached_result:
                    logger.info(f"Returning cached external search results for: {query}")
                    return cached_result
            except Exception as cache_error:
                logger.warning(f"Cache error (continuing without cache): {cache_error}")
            
            # Perform search based on type
            result = await self._perform_search(query, search_type, location, kwargs)
            
            # Cache the results if successful (ignore cache errors)
            if result.get('success') and result.get('total_found', 0) > 0:
                try:
                    self.cache_manager.cache_search_results(cache_key, result, timeout=1800)  # 30 min cache
                    logger.info(f"Cached search results for: {query}")
                except Exception as cache_error:
                    logger.warning(f"Cache error (continuing without caching): {cache_error}")
            
            search_time = self.performance_monitor.end_timer('external_search')
            result['search_time'] = search_time
            
            logger.info(f"External search completed in {search_time:.2f}s. Found {result.get('total_found', 0)} results")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in external search: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_found': 0,
                'search_time': 0
            }
    
    async def _perform_search(self, query: str, search_type: str, location: str, kwargs) -> Dict[str, Any]:
        """Perform the actual search using SerpAPI"""
        try:
            if search_type == 'products':
                return await self._search_products_only(query, location, kwargs)
            elif search_type == 'services':
                return await self._search_services_only(query, location, kwargs)
            else:  # both
                return await self._search_both(query, location, kwargs)
                
        except Exception as e:
            logger.error(f"Error performing external search: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_found': 0
            }
    
    async def _search_products_only(self, query: str, location: str, kwargs) -> Dict[str, Any]:
        """Search for products only"""
        try:
            logger.info(f"Searching products only for: {query}")
            
            result = await self.serpapi.search_products(
                query=query,
                location=location,
                limit=kwargs.get('limit', 10),
                min_price=kwargs.get('min_price'),
                max_price=kwargs.get('max_price')
            )
            
            if result.get('success'):
                # Process and enrich results
                products = self._enrich_products(result.get('products', []))
                logger.info(f"Successfully enriched {len(products)} products")
                
                return {
                    'success': True,
                    'products': products,
                    'services': [],
                    'total_found': len(products),
                    'source': 'serpapi',
                    'search_type': 'products'
                }
            else:
                logger.warning(f"Product search failed: {result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Product search failed'),
                    'products': [],
                    'services': [],
                    'total_found': 0
                }
                
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_found': 0
            }
    
    async def _search_services_only(self, query: str, location: str, kwargs) -> Dict[str, Any]:
        """Search for services only"""
        try:
            logger.info(f"Searching services only for: {query}")
            
            result = await self.serpapi.search_local_services(
                query=query,
                location=location,
                limit=kwargs.get('limit', 10)
            )
            
            if result.get('success'):
                # Process and enrich results
                services = self._enrich_services(result.get('services', []))
                logger.info(f"Successfully enriched {len(services)} services")
                
                return {
                    'success': True,
                    'products': [],
                    'services': services,
                    'total_found': len(services),
                    'source': 'serpapi',
                    'search_type': 'services'
                }
            else:
                logger.warning(f"Service search failed: {result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Service search failed'),
                    'products': [],
                    'services': [],
                    'total_found': 0
                }
                
        except Exception as e:
            logger.error(f"Error searching services: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_found': 0
            }
    
    async def _search_both(self, query: str, location: str, kwargs) -> Dict[str, Any]:
        """Search for both products and services concurrently"""
        try:
            logger.info(f"Searching both products and services for: {query}")
            
            # Run both searches concurrently
            products_task = self.serpapi.search_products(
                query=query,
                location=location,
                limit=kwargs.get('limit', 10),
                min_price=kwargs.get('min_price'),
                max_price=kwargs.get('max_price')
            )
            
            services_task = self.serpapi.search_local_services(
                query=query,
                location=location,
                limit=kwargs.get('limit', 10)
            )
            
            products_result, services_result = await asyncio.gather(
                products_task, services_task, return_exceptions=True
            )
            
            # Process results
            products = []
            services = []
            errors = []
            
            # Process product results
            if isinstance(products_result, dict) and products_result.get('success'):
                products = self._enrich_products(products_result.get('products', []))
                logger.info(f"Successfully enriched {len(products)} products")
            elif isinstance(products_result, Exception):
                error_msg = f"Product search error: {str(products_result)}"
                errors.append(error_msg)
                logger.error(error_msg)
            else:
                error_msg = f"Product search failed: {products_result.get('error', 'Unknown error') if isinstance(products_result, dict) else 'Unknown error'}"
                errors.append(error_msg)
                logger.warning(error_msg)
            
            # Process service results
            if isinstance(services_result, dict) and services_result.get('success'):
                services = self._enrich_services(services_result.get('services', []))
                logger.info(f"Successfully enriched {len(services)} services")
            elif isinstance(services_result, Exception):
                error_msg = f"Service search error: {str(services_result)}"
                errors.append(error_msg)
                logger.error(error_msg)
            else:
                error_msg = f"Service search failed: {services_result.get('error', 'Unknown error') if isinstance(services_result, dict) else 'Unknown error'}"
                errors.append(error_msg)
                logger.warning(error_msg)
            
            total_found = len(products) + len(services)
            success = total_found > 0
            
            result = {
                'success': success,
                'products': products,
                'services': services,
                'total_found': total_found,
                'source': 'serpapi',
                'search_type': 'both'
            }
            
            if errors:
                result['warnings'] = errors
                logger.warning(f"Search completed with warnings: {errors}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching both products and services: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_found': 0
            }
    
    def _enrich_products(self, products: List[Dict]) -> List[Dict]:
        """Enrich product data with additional processing"""
        enriched_products = []
        
        for product in products:
            try:
                enriched_product = product.copy()
                
                # Ensure required fields with better defaults
                enriched_product.setdefault('name', enriched_product.get('title', 'Unknown Product'))
                enriched_product.setdefault('price', enriched_product.get('numeric_price', 0.0))
                enriched_product.setdefault('formatted_price', enriched_product.get('price', 'Price not available'))
                enriched_product.setdefault('currency', 'USD')
                enriched_product.setdefault('image', enriched_product.get('thumbnail', ''))
                enriched_product.setdefault('link', enriched_product.get('product_link', ''))
                enriched_product.setdefault('source', enriched_product.get('extracted_price', {}).get('online_seller', 'External Store'))
                enriched_product.setdefault('location', 'Online Store')
                enriched_product.setdefault('description', enriched_product.get('snippet', ''))
                enriched_product.setdefault('rating', {'average': 0, 'count': 0})
                
                # Clean up the name if it's from title
                if 'title' in enriched_product and enriched_product.get('name') == enriched_product.get('title'):
                    # Clean up title by removing common suffixes
                    title = enriched_product['title']
                    for suffix in [' - Amazon.com', ' | eBay', ' - Walmart.com']:
                        if title.endswith(suffix):
                            title = title[:-len(suffix)]
                    enriched_product['name'] = title
                
                # Ensure we have a valid link
                if not enriched_product['link'] or not enriched_product['link'].startswith('http'):
                    enriched_product['link'] = f"https://www.google.com/search?q={enriched_product['name'].replace(' ', '+')}"
                
                # Add relevance score
                enriched_product['relevance_score'] = enriched_product.get('confidence', 0.8)
                
                # Format additional info
                enriched_product['availability'] = enriched_product.get('availability', 'Check with seller')
                enriched_product['condition'] = enriched_product.get('condition', 'New')
                enriched_product['seller'] = {'name': enriched_product.get('source', 'External Store')}
                
                # Convert price to local currency if needed (rough conversion)
                if enriched_product.get('currency') == 'USD' and enriched_product.get('price', 0) > 0:
                    try:
                        price_val = float(str(enriched_product['price']).replace('$', '').replace(',', ''))
                        # Rough conversion to NGN (you might want to use a real currency API)
                        ngn_price = price_val * 750  # Approximate USD to NGN
                        enriched_product['price_ngn'] = ngn_price
                        enriched_product['formatted_price_ngn'] = f"₦{ngn_price:,.0f}"
                    except (ValueError, TypeError):
                        pass
                
                enriched_products.append(enriched_product)
                
            except Exception as e:
                logger.error(f"Error enriching product: {str(e)}")
                continue
        
        logger.info(f"Successfully enriched {len(enriched_products)} products")
        return enriched_products
    
    def _enrich_services(self, services: List[Dict]) -> List[Dict]:
        """Enrich service data with additional processing"""
        enriched_services = []
        
        for service in services:
            try:
                enriched_service = service.copy()
                
                # Ensure required fields
                enriched_service.setdefault('name', enriched_service.get('title', 'Unknown Service'))
                enriched_service.setdefault('description', enriched_service.get('snippet', 'Service provider'))
                enriched_service.setdefault('location', enriched_service.get('address', 'Location not available'))
                enriched_service.setdefault('phone', enriched_service.get('phone_number', ''))
                enriched_service.setdefault('website', enriched_service.get('website', ''))
                enriched_service.setdefault('link', enriched_service.get('website', enriched_service.get('gps_coordinates', {}).get('link', '')))
                
                # Format rating
                rating_info = {'average': 0, 'count': 0}
                if enriched_service.get('rating'):
                    try:
                        rating_info['average'] = float(enriched_service['rating'])
                    except (ValueError, TypeError):
                        pass
                if enriched_service.get('reviews'):
                    try:
                        rating_info['count'] = int(enriched_service['reviews'])
                    except (ValueError, TypeError):
                        pass
                enriched_service['rating'] = rating_info
                
                enriched_service.setdefault('price_range', 'Contact for pricing')
                enriched_service.setdefault('formatted_price', 'Contact for pricing')
                
                # Add relevance score
                enriched_service['relevance_score'] = enriched_service.get('confidence', 0.8)
                
                # Format provider information
                if 'provider' not in enriched_service:
                    enriched_service['provider'] = {
                        'name': enriched_service.get('name', 'Unknown'),
                        'rating': enriched_service.get('rating', {'average': 0, 'count': 0}),
                        'reviews': enriched_service.get('reviews', 0)
                    }
                
                # Format contact info
                contact_info = []
                if enriched_service.get('phone'):
                    contact_info.append(f"📞 {enriched_service['phone']}")
                if enriched_service.get('website'):
                    contact_info.append(f"🌐 {enriched_service['website']}")
                elif enriched_service.get('link'):
                    contact_info.append(f"🌐 {enriched_service['link']}")
                
                enriched_service['contact_info'] = contact_info
                
                # Add service category
                if enriched_service.get('categories'):
                    enriched_service['category'] = enriched_service['categories'][0] if enriched_service['categories'] else 'General Service'
                else:
                    enriched_service['category'] = 'General Service'
                
                enriched_services.append(enriched_service)
                
            except Exception as e:
                logger.error(f"Error enriching service: {str(e)}")
                continue
        
        logger.info(f"Successfully enriched {len(enriched_services)} services")
        return enriched_services
    
    def _extract_location(self, location_context: Dict = None) -> str:
        """Extract location string for search"""
        if not location_context:
            return "Lagos, Nigeria"
        
        # Build location string
        location_parts = []
        
        if location_context.get('city'):
            location_parts.append(location_context['city'])
        if location_context.get('state'):
            location_parts.append(location_context['state'])
        if location_context.get('country'):
            location_parts.append(location_context['country'])
        else:
            location_parts.append('Nigeria')  # Default country
        
        return ', '.join(location_parts) if location_parts else 'Lagos, Nigeria'
    
    def format_results_for_response(self, search_results: Dict) -> str:
        """Format search results for chatbot response"""
        try:
            if not search_results.get('success') or search_results.get('total_found', 0) == 0:
                return ""
            
            response_parts = []
            products = search_results.get('products', [])
            services = search_results.get('services', [])
            
            if products:
                response_parts.append(f"\n🛍️ External Products Found ({len(products)} results):\n")
                
                for i, product in enumerate(products[:5], 1):
                    price_display = product.get('formatted_price', 'Price not available')
                    if product.get('formatted_price_ngn'):
                        price_display += f" (≈{product['formatted_price_ngn']})"
                    
                    product_info = f"{i}. {product.get('name', 'Unknown Product')}\n"
                    product_info += f"   💰 Price: {price_display}\n"
                    product_info += f"   🏪 Store: {product.get('source', 'External Store')}\n"
                    product_info += f"   📍 Location: {product.get('location', 'Online')}\n"
                    
                    if product.get('rating', {}).get('average', 0) > 0:
                        stars = '⭐' * int(product['rating']['average'])
                        product_info += f"   {stars} ({product['rating']['average']}/5)\n"
                    
                    if product.get('link'):
                        product_info += f"   🔗 View Product: {product['link']}\n"
                    
                    response_parts.append(product_info + "\n")
            
            if services:
                response_parts.append(f"\n🏢 External Services Found ({len(services)} results):\n")
                
                for i, service in enumerate(services[:5], 1):
                    service_info = f"{i}. {service.get('name', 'Unknown Service')}\n"
                    service_info += f"   📋 Service: {service.get('description', 'Service provider')}\n"
                    service_info += f"   💰 Pricing: {service.get('formatted_price', 'Contact for pricing')}\n"
                    service_info += f"   📍 Location: {service.get('location', 'Location not available')}\n"
                    
                    if service.get('rating', {}).get('average', 0) > 0:
                        stars = '⭐' * int(service['rating']['average'])
                        reviews_count = service.get('rating', {}).get('count', 0)
                        service_info += f"   {stars} ({service['rating']['average']}/5) - {reviews_count} reviews\n"
                    
                    contact_info = service.get('contact_info', [])
                    if contact_info:
                        service_info += f"   📞 Contact: {' | '.join(contact_info)}\n"
                    
                    if service.get('link'):
                        service_info += f"   🔗 More Info: {service['link']}\n"
                    
                    response_parts.append(service_info + "\n")
            
            # Add helpful footer
            if response_parts:
                response_parts.append("\n💡 Note: These are external results. Click the links to visit the original sources for more details and to make purchases or contact service providers directly.")
            
            return ''.join(response_parts)
            
        except Exception as e:
            logger.error(f"Error formatting external search results: {str(e)}")
            return ""