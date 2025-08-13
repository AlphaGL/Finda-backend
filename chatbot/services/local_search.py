# ai_chatbot/services/local_search.py - FIXED VERSION
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from django.db.models import Q, Count, Avg, Case, When, Value, CharField, F
from django.db.models.functions import Lower
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from fuzzywuzzy import fuzz, process
import logging
from asgiref.sync import sync_to_async

# Import your models - adjust the import path based on your project structure
from main.models import Products, Services, Category, Country, State, City

logger = logging.getLogger(__name__)

class LocalSearchService:
    """
    Advanced local database search service for products and services
    """
    
    def __init__(self):
        self.max_results = 20
        self.cache_timeout = 300  # 5 minutes
        
        # Search weights for different fields
        self.product_search_weights = {
            'product_name': 1.0,
            'product_description': 0.7,
            'product_brand': 0.8,
            'tags': 0.6,
            'category__name': 0.5
        }
        
        self.service_search_weights = {
            'service_name': 1.0,
            'service_description': 0.7,
            'provider_name': 0.8,
            'provider_expertise': 0.6,
            'tags': 0.6,
            'category__name': 0.5
        }
    
    async def search(self, query: str, search_type: str = 'both', filters: dict = None, location_context: dict = None) -> Dict[str, Any]:
        """
        Main async search method that searches both products and services
        
        Args:
            query: Search query string
            search_type: 'products', 'services', or 'both'
            filters: Additional filters (category, location, price_range, etc.)
            location_context: Location context from user
        
        Returns:
            Dict containing products, services, and metadata
        """
        try:
            logger.info(f"Starting local search for: '{query}' (type: {search_type})")
            
            # Use sync_to_async to run the synchronous search method
            result = await sync_to_async(self._search_sync)(query, search_type, filters or {}, location_context)
            
            logger.info(f"Local search completed: {result.get('success', False)}, found {result.get('total_results', 0)} results")
            return result
            
        except Exception as e:
            logger.error(f"Error in async local search: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_results': 0,
                'query': query,
                'search_type': search_type
            }
    
    def _search_sync(self, query: str, search_type: str, filters: Dict, location_context: Dict = None) -> Dict[str, Any]:
        """
        Synchronous search method that handles Django ORM calls
        """
        cache_key = self._generate_cache_key(query, search_type, filters)
        cached_result = cache.get(cache_key)
        
        if cached_result:
            logger.info(f"Returning cached results for query: {query}")
            return cached_result
        
        try:
            # Process the query
            processed_query = self._preprocess_query(query)
            intent = self._detect_intent(query, filters)
            
            results = {
                'success': True,
                'query': query,
                'processed_query': processed_query,
                'intent': intent,
                'products': [],
                'services': [],
                'categories': [],
                'locations': [],
                'total_results': 0,
                'search_metadata': {},
                'search_type': search_type
            }
            
            # Determine what to search based on search_type parameter
            if search_type in ['products', 'both']:
                results['products'] = self._search_products(processed_query, filters, intent, location_context)
            
            if search_type in ['services', 'both']:
                results['services'] = self._search_services(processed_query, filters, intent, location_context)
            
            # Search categories if query seems category-related
            if intent.get('category_search', False):
                results['categories'] = self._search_categories(processed_query)
            
            # Search locations if query contains location terms
            if intent.get('location_search', False):
                results['locations'] = self._search_locations(processed_query)
            
            # Calculate total results
            results['total_results'] = len(results['products']) + len(results['services'])
            
            # Add search metadata
            results['search_metadata'] = {
                'filters_applied': filters,
                'confidence_score': self._calculate_confidence_score(results),
                'suggestions': self._generate_suggestions(query, results)
            }
            
            # Cache the results
            if results['total_results'] > 0:
                cache.set(cache_key, results, self.cache_timeout)
            
            logger.info(f"Search completed: {results['total_results']} results for '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Error in local search for '{query}': {str(e)}")
            return {
                'success': False,
                'query': query,
                'error': str(e),
                'products': [],
                'services': [],
                'total_results': 0,
                'search_type': search_type
            }
    
    def _search_products(self, query: str, filters: Dict, intent: Dict, location_context: Dict = None) -> List[Dict]:
        """Search products in the local database"""
        try:
            # Base queryset - only published products
            queryset = Products.objects.filter(
                product_status='published'
            ).select_related(
                'category', 'country', 'state', 'city', 'user'
            )
            
            # Apply text search
            if query:
                search_q = self._build_product_search_query(query)
                queryset = queryset.filter(search_q)
            
            # Apply filters
            queryset = self._apply_product_filters(queryset, filters)
            
            # Apply location context if provided
            if location_context:
                queryset = self._apply_location_filter(queryset, location_context, 'product')
            
            # Apply intent-based filtering
            if intent.get('price_range'):
                min_price, max_price = intent['price_range']
                if min_price:
                    queryset = queryset.filter(product_price__gte=min_price)
                if max_price:
                    queryset = queryset.filter(product_price__lte=max_price)
            
            if intent.get('condition'):
                queryset = queryset.filter(product_condition=intent['condition'])
            
            # Ranking and ordering
            queryset = self._rank_products(queryset, query, intent)
            
            # Limit results
            queryset = queryset[:self.max_results]
            
            # Convert to dict format
            products = []
            for product in queryset:
                product_data = self._format_product_data(product)
                products.append(product_data)
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []
    
    def _search_services(self, query: str, filters: Dict, intent: Dict, location_context: Dict = None) -> List[Dict]:
        """Search services in the local database"""
        try:
            # Base queryset - only published services
            queryset = Services.objects.filter(
                service_status='published'
            ).select_related(
                'category', 'country', 'state', 'city', 'user'
            )
            
            # Apply text search
            if query:
                search_q = self._build_service_search_query(query)
                queryset = queryset.filter(search_q)
            
            # Apply filters
            queryset = self._apply_service_filters(queryset, filters)
            
            # Apply location context if provided
            if location_context:
                queryset = self._apply_location_filter(queryset, location_context, 'service')
            
            # Apply intent-based filtering
            if intent.get('price_range'):
                min_price, max_price = intent['price_range']
                if min_price and queryset.filter(starting_price__isnull=False).exists():
                    queryset = queryset.filter(starting_price__gte=min_price)
                if max_price and queryset.filter(max_price__isnull=False).exists():
                    queryset = queryset.filter(max_price__lte=max_price)
            
            if intent.get('experience_level'):
                queryset = queryset.filter(provider_experience=intent['experience_level'])
            
            if intent.get('remote_service'):
                queryset = queryset.filter(serves_remote=True)
            
            # Ranking and ordering
            queryset = self._rank_services(queryset, query, intent)
            
            # Limit results
            queryset = queryset[:self.max_results]
            
            # Convert to dict format
            services = []
            for service in queryset:
                service_data = self._format_service_data(service)
                services.append(service_data)
            
            return services
            
        except Exception as e:
            logger.error(f"Error searching services: {str(e)}")
            return []
    
    def _format_product_data(self, product) -> Dict:
        """Format product data for response"""
        try:
            return {
                'id': product.id,
                'name': product.product_name,
                'description': product.product_description[:200] + "..." if product.product_description and len(product.product_description) > 200 else (product.product_description or ""),
                'price': float(product.product_price) if product.product_price else 0.0,
                'formatted_price': f"₦{product.product_price:,.2f}" if product.product_price else "Price not available",
                'currency': getattr(product, 'currency', 'NGN'),
                'image': product.featured_image.url if hasattr(product, 'featured_image') and product.featured_image else None,
                'condition': getattr(product, 'product_condition', 'new'),
                'brand': getattr(product, 'product_brand', ''),
                'location': {
                    'city': product.city.name if product.city else '',
                    'state': product.state.name if product.state else '',
                    'country': product.country.name if product.country else '',
                    'full_location': f"{product.city.name if product.city else ''}, {product.state.name if product.state else ''}"
                },
                'category': {
                    'name': product.category.name if product.category else '',
                    'slug': getattr(product.category, 'slug', '') if product.category else ''
                },
                'seller': {
                    'name': f"{product.user.first_name} {product.user.last_name}" if product.user else "Unknown",
                    'phone': getattr(product, 'provider_phone', ''),
                    'email': getattr(product, 'provider_email', ''),
                    'is_verified': getattr(product.user, 'is_verified', False) if product.user else False
                },
                'rating': {
                    'average': 0.0,  # You can implement this method in your model
                    'count': 0
                },
                'stats': {
                    'views': getattr(product, 'views_count', 0),
                    'favorites': getattr(product, 'favorites_count', 0)
                },
                'features': {
                    'is_promoted': getattr(product, 'is_promoted', False),
                    'is_featured': getattr(product, 'is_featured', False),
                    'is_negotiable': getattr(product, 'is_negotiable', False)
                },
                'url': f"/products/{product.id}/",  # Adjust based on your URL structure
                'created_at': product.created_at.isoformat() if hasattr(product, 'created_at') else '',
                'type': 'product'
            }
        except Exception as e:
            logger.error(f"Error formatting product data: {str(e)}")
            return {
                'id': getattr(product, 'id', 0),
                'name': getattr(product, 'product_name', 'Unknown Product'),
                'description': '',
                'price': 0.0,
                'formatted_price': 'Price not available',
                'type': 'product'
            }
    
    def _format_service_data(self, service) -> Dict:
        """Format service data for response"""
        try:
            return {
                'id': service.id,
                'name': service.service_name,
                'description': service.service_description[:200] + "..." if service.service_description and len(service.service_description) > 200 else (service.service_description or ""),
                'price_range': getattr(service, 'price_range', 'Contact for pricing'),
                'formatted_price': 'Contact for pricing',  # You can implement price formatting
                'currency': getattr(service, 'currency', 'NGN'),
                'image': service.featured_image.url if hasattr(service, 'featured_image') and service.featured_image else None,
                'location': {
                    'city': service.city.name if service.city else '',
                    'state': service.state.name if service.state else '',
                    'country': service.country.name if service.country else '',
                    'full_location': f"{service.city.name if service.city else ''}, {service.state.name if service.state else ''}",
                    'serves_remote': getattr(service, 'serves_remote', False),
                    'service_radius': getattr(service, 'service_radius', 0)
                },
                'category': {
                    'name': service.category.name if service.category else '',
                    'slug': getattr(service.category, 'slug', '') if service.category else ''
                },
                'provider': {
                    'name': getattr(service, 'provider_name', service.user.get_full_name() if service.user else 'Unknown'),
                    'title': getattr(service, 'provider_title', ''),
                    'bio': getattr(service, 'provider_bio', ''),
                    'experience': getattr(service, 'provider_experience', ''),
                    'expertise': getattr(service, 'provider_expertise', ''),
                    'phone': getattr(service, 'provider_phone', ''),
                    'email': getattr(service, 'provider_email', ''),
                    'website': getattr(service, 'provider_website', ''),
                    'is_verified': getattr(service, 'is_verified', False)
                },
                'rating': {
                    'average': 0.0,  # You can implement this method in your model
                    'count': 0
                },
                'stats': {
                    'views': getattr(service, 'views_count', 0),
                    'contacts': getattr(service, 'contacts_count', 0)
                },
                'features': {
                    'is_promoted': getattr(service, 'is_promoted', False),
                    'is_featured': getattr(service, 'is_featured', False),
                    'is_verified': getattr(service, 'is_verified', False),
                    'response_time': getattr(service, 'response_time', ''),
                    'availability': getattr(service, 'availability', '')
                },
                'url': f"/services/{service.id}/",  # Adjust based on your URL structure
                'created_at': service.created_at.isoformat() if hasattr(service, 'created_at') else '',
                'type': 'service'
            }
        except Exception as e:
            logger.error(f"Error formatting service data: {str(e)}")
            return {
                'id': getattr(service, 'id', 0),
                'name': getattr(service, 'service_name', 'Unknown Service'),
                'description': '',
                'formatted_price': 'Contact for pricing',
                'type': 'service'
            }
    
    def _apply_location_filter(self, queryset, location_context: Dict, item_type: str):
        """Apply location filter based on context"""
        try:
            if location_context.get('city'):
                city_name = location_context['city']
                queryset = queryset.filter(city__name__icontains=city_name)
            elif location_context.get('state'):
                state_name = location_context['state']
                queryset = queryset.filter(state__name__icontains=state_name)
            elif location_context.get('country'):
                country_name = location_context['country']
                queryset = queryset.filter(country__name__icontains=country_name)
            
            return queryset
        except Exception as e:
            logger.error(f"Error applying location filter: {str(e)}")
            return queryset
    
    # ... [Keep all the other existing methods from the original file]
    
    def _build_product_search_query(self, query: str) -> Q:
        """Build complex search query for products"""
        search_terms = self._extract_search_terms(query)
        
        q_objects = Q()
        
        for term in search_terms:
            term_q = (
                Q(product_name__icontains=term) |
                Q(product_description__icontains=term) |
                Q(product_brand__icontains=term)
            )
            # Add more fields as they exist in your model
            if hasattr(Products, 'product_model'):
                term_q |= Q(product_model__icontains=term)
            if hasattr(Products, 'tags'):
                term_q |= Q(tags__icontains=term)
            
            term_q |= Q(category__name__icontains=term)
            q_objects |= term_q
        
        return q_objects
    
    def _build_service_search_query(self, query: str) -> Q:
        """Build complex search query for services"""
        search_terms = self._extract_search_terms(query)
        
        q_objects = Q()
        
        for term in search_terms:
            term_q = (
                Q(service_name__icontains=term) |
                Q(service_description__icontains=term)
            )
            
            # Add more fields as they exist in your model
            if hasattr(Services, 'provider_name'):
                term_q |= Q(provider_name__icontains=term)
            if hasattr(Services, 'provider_expertise'):
                term_q |= Q(provider_expertise__icontains=term)
            if hasattr(Services, 'tags'):
                term_q |= Q(tags__icontains=term)
            
            term_q |= Q(category__name__icontains=term)
            q_objects |= term_q
        
        return q_objects
    
    def _apply_product_filters(self, queryset, filters: Dict):
        """Apply filters to product queryset"""
        if filters.get('category_id'):
            queryset = queryset.filter(category_id=filters['category_id'])
        elif filters.get('category_slug'):
            queryset = queryset.filter(category__slug=filters['category_slug'])
        
        if filters.get('country_id'):
            queryset = queryset.filter(country_id=filters['country_id'])
        
        if filters.get('state_id'):
            queryset = queryset.filter(state_id=filters['state_id'])
        
        if filters.get('city_id'):
            queryset = queryset.filter(city_id=filters['city_id'])
        
        if filters.get('min_price'):
            queryset = queryset.filter(product_price__gte=filters['min_price'])
        
        if filters.get('max_price'):
            queryset = queryset.filter(product_price__lte=filters['max_price'])
        
        return queryset
    
    def _apply_service_filters(self, queryset, filters: Dict):
        """Apply filters to service queryset"""
        if filters.get('category_id'):
            queryset = queryset.filter(category_id=filters['category_id'])
        elif filters.get('category_slug'):
            queryset = queryset.filter(category__slug=filters['category_slug'])
        
        if filters.get('country_id'):
            queryset = queryset.filter(country_id=filters['country_id'])
        
        if filters.get('state_id'):
            queryset = queryset.filter(state_id=filters['state_id'])
        
        if filters.get('city_id'):
            queryset = queryset.filter(city_id=filters['city_id'])
        
        return queryset
    
    def _rank_products(self, queryset, query: str, intent: Dict):
        """Apply ranking to products based on relevance"""
        return queryset.order_by('-created_at')  # Simple ordering for now
    
    def _rank_services(self, queryset, query: str, intent: Dict):
        """Apply ranking to services based on relevance"""
        return queryset.order_by('-created_at')  # Simple ordering for now
    
    def _search_categories(self, query: str) -> List[Dict]:
        """Search categories"""
        try:
            categories = Category.objects.filter(
                Q(name__icontains=query),
                is_active=True
            )[:10]
            
            return [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'slug': getattr(cat, 'slug', ''),
                    'description': getattr(cat, 'description', ''),
                    'type': getattr(cat, 'category_type', 'general')
                }
                for cat in categories
            ]
        except Exception as e:
            logger.error(f"Error searching categories: {str(e)}")
            return []
    
    def _search_locations(self, query: str) -> List[Dict]:
        """Search locations (countries, states, cities)"""
        try:
            results = []
            
            # Search cities
            cities = City.objects.filter(
                Q(name__icontains=query),
                is_active=True
            ).select_related('state', 'country')[:10]
            
            for city in cities:
                results.append({
                    'type': 'city',
                    'id': city.id,
                    'name': city.name,
                    'state': city.state.name if city.state else '',
                    'country': city.country.name if city.country else ''
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching locations: {str(e)}")
            return []
    
    def _preprocess_query(self, query: str) -> str:
        """Clean and preprocess the search query"""
        if not query:
            return ""
        
        # Convert to lowercase and strip whitespace
        query = query.lower().strip()
        
        # Remove special characters but keep alphanumeric and spaces
        query = re.sub(r'[^\w\s]', ' ', query)
        
        # Remove extra whitespace
        query = re.sub(r'\s+', ' ', query)
        
        return query
    
    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract individual search terms from query"""
        if not query:
            return []
        
        # Split by whitespace and filter out empty strings
        terms = [term.strip() for term in query.split() if term.strip()]
        
        # Remove very short terms (less than 2 characters)
        terms = [term for term in terms if len(term) >= 2]
        
        return terms
    
    def _detect_intent(self, query: str, filters: Dict) -> Dict:
        """Detect user intent from query and filters"""
        intent = {
            'search_type': 'both',
            'category_search': False,
            'location_search': False,
            'price_range': None,
            'condition': None
        }
        
        if not query:
            return intent
        
        query_lower = query.lower()
        
        # Detect search type
        product_keywords = ['buy', 'purchase', 'product', 'item', 'sell', 'selling', 'price', 'cost', 'phone', 'laptop', 'computer']
        service_keywords = ['service', 'hire', 'book', 'appointment', 'professional', 'expert', 'help']
        
        product_score = sum(1 for keyword in product_keywords if keyword in query_lower)
        service_score = sum(1 for keyword in service_keywords if keyword in query_lower)
        
        if product_score > service_score:
            intent['search_type'] = 'products'
        elif service_score > product_score:
            intent['search_type'] = 'services'
        
        return intent
    
    def _calculate_confidence_score(self, results: Dict) -> float:
        """Calculate confidence score based on search results"""
        total_results = results['total_results']
        
        if total_results == 0:
            return 0.0
        elif total_results <= 5:
            return 0.9
        elif total_results <= 20:
            return 0.8
        else:
            return 0.7
    
    def _generate_suggestions(self, query: str, results: Dict) -> List[str]:
        """Generate search suggestions based on results"""
        suggestions = []
        
        if results['total_results'] == 0:
            suggestions.extend([
                "Try using different keywords",
                "Check your spelling",
                "Try searching in a different location"
            ])
        
        return suggestions[:3]
    
    def _generate_cache_key(self, query: str, search_type: str, filters: Dict) -> str:
        """Generate cache key for the search"""
        import hashlib
        
        # Create a string representation of the search parameters
        search_params = f"{query}_{search_type}_{json.dumps(filters, sort_keys=True)}"
        
        # Create hash
        cache_key = hashlib.md5(search_params.encode()).hexdigest()
        
        return f"local_search_{cache_key}"
    
    def get_popular_searches(self, limit: int = 10) -> List[Dict]:
        """Get popular search terms"""
        try:
            # This would typically come from your SearchHistory model
            # For now, returning some sample data
            return [
                {'term': 'smartphones', 'count': 150},
                {'term': 'laptops', 'count': 120},
                {'term': 'web design', 'count': 80},
                {'term': 'cleaning service', 'count': 70},
                {'term': 'cars', 'count': 65}
            ][:limit]
        except Exception as e:
            logger.error(f"Error getting popular searches: {str(e)}")
            return []
    
    def get_trending_categories(self, limit: int = 10) -> List[Dict]:
        """Get trending categories"""
        try:
            categories = Category.objects.annotate(
                product_count=Count('products', filter=Q(products__product_status='published')),
                service_count=Count('services', filter=Q(services__service_status='published'))
            ).filter(
                Q(product_count__gt=0) | Q(service_count__gt=0),
                is_active=True
            ).order_by('-product_count', '-service_count')[:limit]
            
            return [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'slug': cat.slug,
                    'icon': cat.icon,
                    'product_count': cat.product_count,
                    'service_count': cat.service_count,
                    'total_count': cat.product_count + cat.service_count
                }
                for cat in categories
            ]
        except Exception as e:
            logger.error(f"Error getting trending categories: {str(e)}")
            return []