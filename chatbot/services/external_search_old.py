# ai_chatbot/services/external_search.py - COMPLETE UPDATED VERSION
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from .serpapi_service import SerpAPIService
from ..utils import SearchHelper, CacheManager, PerformanceMonitor

logger = logging.getLogger(__name__)

class EnhancedExternalSearchService:
    """Enhanced external search service with SerpAPI integration and complete formatting"""
    
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
        """Enrich product data with additional processing and ensure all required fields"""
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
                    title = enriched_product['title']
                    # Remove common suffixes and clean up
                    for suffix in [' - Amazon.com', ' | eBay', ' - Walmart.com', ' - Best Buy', ' - Target']:
                        if title.endswith(suffix):
                            title = title[:-len(suffix)]
                    enriched_product['name'] = title
                
                # Ensure we have a valid link - THIS IS CRITICAL FOR YOUR REQUIREMENT
                if not enriched_product['link'] or not enriched_product['link'].startswith('http'):
                    # Create a comprehensive search link as fallback
                    search_query = enriched_product['name'].replace(' ', '+')
                    # Try different search approaches
                    if 'amazon' in enriched_product.get('source', '').lower():
                        enriched_product['link'] = f"https://www.amazon.com/s?k={search_query}"
                    elif 'ebay' in enriched_product.get('source', '').lower():
                        enriched_product['link'] = f"https://www.ebay.com/sch/i.html?_nkw={search_query}"
                    else:
                        # Generic Google Shopping search
                        enriched_product['link'] = f"https://www.google.com/search?tbm=shop&q={search_query}"
                    enriched_product['link_type'] = 'search'
                else:
                    enriched_product['link_type'] = 'direct'
                
                # Add relevance score
                enriched_product['relevance_score'] = enriched_product.get('confidence', 0.8)
                
                # Format additional info
                enriched_product['availability'] = enriched_product.get('availability', 'Check with seller')
                enriched_product['condition'] = enriched_product.get('condition', 'New')
                enriched_product['seller'] = {
                    'name': enriched_product.get('source', 'External Store'),
                    'link': enriched_product.get('link', '')
                }
                
                # Convert price to local currency if needed (rough conversion)
                if enriched_product.get('currency') == 'USD' and enriched_product.get('price', 0) > 0:
                    try:
                        price_val = float(str(enriched_product['price']).replace('$', '').replace(',', ''))
                        # Rough conversion to NGN
                        ngn_price = price_val * 750  # Approximate USD to NGN
                        enriched_product['price_ngn'] = ngn_price
                        enriched_product['formatted_price_ngn'] = f"₦{ngn_price:,.0f}"
                    except (ValueError, TypeError):
                        pass
                
                # Extract and clean image URL
                if enriched_product.get('image'):
                    image_url = enriched_product['image']
                    # Ensure image URL is valid
                    if not image_url.startswith('http'):
                        enriched_product['image'] = f"https:{image_url}" if image_url.startswith('//') else ''
                
                # Add shipping and delivery info
                enriched_product['shipping_info'] = enriched_product.get('shipping', '')
                enriched_product['delivery_info'] = enriched_product.get('delivery', '')
                
                enriched_products.append(enriched_product)
                
            except Exception as e:
                logger.error(f"Error enriching product: {str(e)}")
                continue
        
        logger.info(f"Successfully enriched {len(enriched_products)} products")
        return enriched_products
    
    def _enrich_services(self, services: List[Dict]) -> List[Dict]:
        """Enrich service data with additional processing and ensure all required fields"""
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
                
                # Format rating properly
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
                
                # Ensure we have a working link - THIS IS CRITICAL FOR YOUR REQUIREMENT
                if not enriched_service['link'] or not enriched_service['link'].startswith('http'):
                    # Create Google Maps search link as fallback
                    search_query = f"{enriched_service.get('name', '')} {enriched_service.get('location', '')}".strip()
                    if search_query:
                        search_query = search_query.replace(' ', '+')
                        enriched_service['link'] = f"https://www.google.com/maps/search/{search_query}"
                        enriched_service['link_type'] = 'maps'
                    else:
                        enriched_service['link'] = ''
                        enriched_service['link_type'] = 'none'
                else:
                    enriched_service['link_type'] = 'website'
                
                # Add relevance score
                enriched_service['relevance_score'] = enriched_service.get('confidence', 0.8)
                
                # Format provider information
                if 'provider' not in enriched_service:
                    enriched_service['provider'] = {
                        'name': enriched_service.get('name', 'Unknown'),
                        'rating': enriched_service.get('rating', {'average': 0, 'count': 0}),
                        'reviews': enriched_service.get('reviews', 0),
                        'phone': enriched_service.get('phone', ''),
                        'website': enriched_service.get('website', ''),
                        'address': enriched_service.get('location', '')
                    }
                
                # Format contact info with proper icons and formatting
                contact_info = []
                if enriched_service.get('phone'):
                    # Clean phone number
                    phone = enriched_service['phone'].strip()
                    if phone:
                        contact_info.append(f"📞 {phone}")
                
                if enriched_service.get('website') and enriched_service['website'].startswith('http'):
                    contact_info.append(f"🌐 {enriched_service['website']}")
                elif enriched_service.get('link') and enriched_service['link'].startswith('http'):
                    contact_info.append(f"🗺️ {enriched_service['link']}")
                
                enriched_service['contact_info'] = contact_info
                
                # Add service category
                if enriched_service.get('categories'):
                    enriched_service['category'] = enriched_service['categories'][0] if enriched_service['categories'] else 'General Service'
                else:
                    enriched_service['category'] = 'General Service'
                
                # Extract and clean image URL
                if enriched_service.get('image'):
                    image_url = enriched_service['image']
                    if not image_url.startswith('http'):
                        enriched_service['image'] = f"https:{image_url}" if image_url.startswith('//') else ''
                
                # Format business hours
                hours = enriched_service.get('hours', {})
                if isinstance(hours, dict) and hours:
                    # Format hours nicely
                    enriched_service['formatted_hours'] = self._format_business_hours(hours)
                elif isinstance(hours, str):
                    enriched_service['formatted_hours'] = hours
                else:
                    enriched_service['formatted_hours'] = 'Hours not available'
                
                enriched_services.append(enriched_service)
                
            except Exception as e:
                logger.error(f"Error enriching service: {str(e)}")
                continue
        
        logger.info(f"Successfully enriched {len(enriched_services)} services")
        return enriched_services
    
    def _format_business_hours(self, hours: Dict) -> str:
        """Format business hours dictionary into readable string"""
        try:
            if not hours:
                return 'Hours not available'
            
            # Common hour formatting
            if isinstance(hours, str):
                return hours
            
            # If it's a dictionary, try to format it
            formatted_hours = []
            for day, time in hours.items():
                if time:
                    formatted_hours.append(f"{day}: {time}")
            
            return '; '.join(formatted_hours) if formatted_hours else 'Hours not available'
            
        except Exception:
            return 'Hours not available'
    
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
    
    def format_external_results_enhanced(self, search_results: Dict) -> Dict[str, Any]:
        """
        Enhanced formatter that ensures all product/service info including links and images are properly displayed
        """
        try:
            if not search_results.get('success') or search_results.get('total_found', 0) == 0:
                return {
                    'formatted_response': "I couldn't find any external results for your search. Try searching with different keywords or check if the products/services are available in your area.",
                    'has_results': False
                }
            
            formatted_items = []
            products = search_results.get('products', [])
            services = search_results.get('services', [])
            
            # Format Products with Full Details
            if products:
                for i, product in enumerate(products[:8], 1):  # Show up to 8 products
                    product_card = {
                        'type': 'product',
                        'position': i,
                        'title': product.get('name', product.get('title', 'Unknown Product')),
                        'image': product.get('image', product.get('thumbnail', '')),
                        'price': product.get('formatted_price', 'Price not available'),
                        'price_ngn': product.get('formatted_price_ngn', ''),
                        'store': product.get('source', product.get('seller_name', 'Unknown Store')),
                        'link': product.get('link', ''),
                        'rating': product.get('rating', {'average': 0, 'count': 0}),
                        'description': product.get('description', product.get('snippet', '')),
                        'availability': product.get('availability', 'Check with seller'),
                        'condition': product.get('condition', 'New'),
                        'shipping': product.get('shipping_info', product.get('shipping', '')),
                        'reviews_count': product.get('reviews_count', 0),
                        'link_type': product.get('link_type', 'search')
                    }
                    
                    # Ensure we have a valid link
                    if not product_card['link'] or not product_card['link'].startswith('http'):
                        search_query = product_card['title'].replace(' ', '+')
                        product_card['link'] = f"https://www.google.com/search?tbm=shop&q={search_query}"
                        product_card['link_type'] = 'search'
                    
                    formatted_items.append(product_card)
            
            # Format Services with Full Details
            if services:
                for i, service in enumerate(services[:8], 1):  # Show up to 8 services
                    service_card = {
                        'type': 'service',
                        'position': i,
                        'title': service.get('name', service.get('title', 'Unknown Service')),
                        'image': service.get('image', service.get('thumbnail', '')),
                        'description': service.get('description', 'Service provider'),
                        'location': service.get('location', service.get('address', 'Location not available')),
                        'phone': service.get('phone', ''),
                        'website': service.get('website', service.get('link', '')),
                        'rating': service.get('rating', {'average': 0, 'count': 0}),
                        'reviews_count': service.get('reviews_count', 0),
                        'price_range': service.get('price_range', 'Contact for pricing'),
                        'categories': service.get('categories', []),
                        'hours': service.get('formatted_hours', service.get('hours', '')),
                        'coordinates': service.get('coordinates', {}),
                        'link_type': service.get('link_type', 'maps')
                    }
                    
                    # Ensure we have contact information
                    contact_methods = []
                    if service_card['phone']:
                        contact_methods.append(f"📞 {service_card['phone']}")
                    if service_card['website'] and service_card['website'].startswith('http'):
                        contact_methods.append(f"🌐 {service_card['website']}")
                    
                    service_card['contact_info'] = contact_methods
                    service_card['link'] = service_card['website']
                    
                    # If no website, create a Google Maps search link
                    if not service_card['link'] or not service_card['link'].startswith('http'):
                        search_query = f"{service_card['title']} {service_card['location']}".replace(' ', '+')
                        service_card['link'] = f"https://www.google.com/maps/search/{search_query}"
                        service_card['link_type'] = 'maps'
                    
                    formatted_items.append(service_card)
            
            # Generate the formatted text response
            response_text = self._generate_response_text(formatted_items, len(products), len(services))
            
            return {
                'formatted_response': response_text,
                'formatted_items': formatted_items,
                'has_results': True,
                'total_products': len(products),
                'total_services': len(services)
            }
            
        except Exception as e:
            logger.error(f"Error formatting enhanced external results: {str(e)}")
            return {
                'formatted_response': "Error formatting search results. Please try again.",
                'has_results': False
            }

    def _generate_response_text(self, formatted_items: List[Dict], product_count: int, service_count: int) -> str:
        """Generate the complete formatted text response with all details including links and images"""
        
        response_parts = ["🌍 **External Search Results Found!**\n"]
        
        if product_count > 0:
            response_parts.append(f"🛍️ **Products Found ({product_count} results):**\n")
        
        if service_count > 0:
            response_parts.append(f"🏪 **Services Found ({service_count} results):**\n")
        
        for item in formatted_items:
            if item['type'] == 'product':
                # Product formatting with all details
                response_parts.append(f"**{item['position']}. {item['title']}**")
                
                # Price information
                response_parts.append(f"💰 **Price:** {item['price']}")
                if item['price_ngn']:
                    response_parts.append(f"   💵 **Local Price:** ~{item['price_ngn']}")
                
                response_parts.append(f"🏪 **Store:** {item['store']}")
                response_parts.append(f"📦 **Condition:** {item['condition']}")
                
                # Rating and reviews
                if item['rating']['average'] > 0:
                    stars = '⭐' * min(int(item['rating']['average']), 5)
                    response_parts.append(f"⭐ **Rating:** {stars} ({item['rating']['average']:.1f}/5)")
                    if item['reviews_count'] > 0:
                        response_parts.append(f"   👥 **Reviews:** {item['reviews_count']} customer reviews")
                
                # Shipping information
                if item['shipping']:
                    response_parts.append(f"🚚 **Shipping:** {item['shipping']}")
                
                # Description
                if item['description'] and len(item['description'].strip()) > 10:
                    desc = item['description'][:120] + "..." if len(item['description']) > 120 else item['description']
                    response_parts.append(f"📝 **Description:** {desc}")
                
                # Image - Always include if available
                if item['image']:
                    response_parts.append(f"🖼️ **Product Image:** [View Image]({item['image']})")
                
                # Link - ALWAYS INCLUDE (this was your main requirement)
                if item['link']:
                    if item['link_type'] == 'direct':
                        response_parts.append(f"🔗 **[🛒 BUY NOW - VIEW PRODUCT]({item['link']})**")
                    else:
                        response_parts.append(f"🔍 **[🔎 SEARCH FOR THIS PRODUCT]({item['link']})**")
                
                # Availability
                if item['availability'] != 'Check with seller':
                    response_parts.append(f"✅ **Availability:** {item['availability']}")
                    
            elif item['type'] == 'service':
                # Service formatting with all details
                response_parts.append(f"**{item['position']}. {item['title']}**")
                response_parts.append(f"📍 **Location:** {item['location']}")
                response_parts.append(f"💼 **Service:** {item['description']}")
                response_parts.append(f"💰 **Pricing:** {item['price_range']}")
                
                # Rating and reviews
                if item['rating']['average'] > 0:
                    stars = '⭐' * min(int(item['rating']['average']), 5)
                    response_parts.append(f"⭐ **Rating:** {stars} ({item['rating']['average']:.1f}/5)")
                    if item['reviews_count'] > 0:
                        response_parts.append(f"   👥 **Reviews:** {item['reviews_count']} customer reviews")
                
                # Contact information - ALWAYS INCLUDE
                if item['contact_info']:
                    response_parts.append(f"📞 **Contact:** {' | '.join(item['contact_info'])}")
                
                # Business hours
                if item['hours'] and item['hours'] != 'Hours not available':
                    response_parts.append(f"🕒 **Hours:** {item['hours']}")
                
                # Categories
                if item['categories']:
                    categories = ', '.join(item['categories'][:3])  # Show max 3 categories
                    response_parts.append(f"🏷️ **Categories:** {categories}")
                
                # Image - Always include if available
                if item['image']:
                    response_parts.append(f"🖼️ **Service Image:** [View Image]({item['image']})")
                
                # Link - ALWAYS INCLUDE (this was your main requirement)
                if item['link']:
                    if item['link_type'] == 'website':
                        response_parts.append(f"🌐 **[🏪 VISIT WEBSITE]({item['link']})**")
                    elif item['link_type'] == 'maps':
                        response_parts.append(f"🗺️ **[📍 VIEW ON MAPS]({item['link']})**")
                    else:
                        response_parts.append(f"🔗 **[ℹ️ MORE INFO]({item['link']})**")
            
            response_parts.append("")  # Empty line between items
        
        # Add footer with helpful tips
        response_parts.append("💡 **How to Use These Results:**")
        response_parts.append("• **Click the links above** to visit the original sources")
        response_parts.append("• **Product links** take you directly to buy or search for the item")
        response_parts.append("• **Service links** connect you to their websites or Google Maps location")
        response_parts.append("• **Always verify prices and availability** with the seller directly")
        response_parts.append("• **Check ratings and reviews** before making decisions")
        
        # Add search tips
        if product_count > 0 and service_count > 0:
            response_parts.append("\n🔄 **Found both products and services** - choose based on whether you want to buy online or visit a physical store.")
        elif product_count > 0:
            response_parts.append("\n🛒 **Found products for online purchase** - click the buy links to proceed with purchase.")
        elif service_count > 0:
            response_parts.append("\n🏪 **Found local services** - contact them directly using the provided information.")
        
        return "\n".join(response_parts)
    
    def format_results_for_response(self, search_results: Dict) -> str:
        """
        Public method to format search results for chatbot response
        Compatible with your existing code
        """
        try:
            enhanced_format = self.format_external_results_enhanced(search_results)
            return enhanced_format.get('formatted_response', '')
        except Exception as e:
            logger.error(f"Error in format_results_for_response: {str(e)}")
            return ""
    
    def get_structured_results(self, search_results: Dict) -> Dict[str, Any]:
        """
        Get structured results for API responses or frontend processing
        """
        try:
            return self.format_external_results_enhanced(search_results)
        except Exception as e:
            logger.error(f"Error getting structured results: {str(e)}")
            return {
                'formatted_response': 'Error processing results',
                'has_results': False,
                'formatted_items': [],
                'total_products': 0,
                'total_services': 0
            }
    
    def generate_chat_response_with_external_search(self, query: str, search_results: Dict) -> Dict[str, Any]:
        """
        Main method to generate complete chat response with external search results
        Use this in your main chat response generation logic
        """
        try:
            if not search_results or not search_results.get('success'):
                return {
                    'success': False,
                    'response': 'I could not find any external results for your search. Please try different keywords or check your internet connection.',
                    'has_external_results': False,
                    'total_products': 0,
                    'total_services': 0
                }
            
            # Check if we have external results
            if search_results.get('total_found', 0) > 0:
                enhanced_format = self.format_external_results_enhanced(search_results)
                
                if enhanced_format['has_results']:
                    return {
                        'success': True,
                        'response': enhanced_format['formatted_response'],
                        'items': enhanced_format['formatted_items'],
                        'has_external_results': True,
                        'total_products': enhanced_format['total_products'],
                        'total_services': enhanced_format['total_services'],
                        'search_query': query,
                        'search_time': search_results.get('search_time', 0)
                    }
            
            # Fallback response
            return {
                'success': False,
                'response': f'I searched external sources but could not find any results for "{query}". Try using different keywords or check if the item/service is available in your area.',
                'has_external_results': False,
                'total_products': 0,
                'total_services': 0
            }
            
        except Exception as e:
            logger.error(f"Error generating chat response with external search: {str(e)}")
            return {
                'success': False,
                'response': 'There was an error processing your search results. Please try again.',
                'has_external_results': False,
                'total_products': 0,
                'total_services': 0
            }

# Export the main class
__all__ = ['EnhancedExternalSearchService']