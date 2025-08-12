# ai_chatbot/services/local_search.py
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from django.db.models import Q, Count, Avg, Case, When, Value, CharField, F
from django.db.models.functions import Lower
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from fuzzywuzzy import fuzz, process
import logging

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
    
    def search(self, query: str, **filters) -> Dict[str, Any]:
        """
        Main search method that searches both products and services
        
        Args:
            query: Search query string
            **filters: Additional filters (category, location, price_range, etc.)
        
        Returns:
            Dict containing products, services, and metadata
        """
        cache_key = self._generate_cache_key(query, filters)
        cached_result = cache.get(cache_key)
        
        if cached_result:
            logger.info(f"Returning cached results for query: {query}")
            return cached_result
        
        try:
            # Process the query
            processed_query = self._preprocess_query(query)
            intent = self._detect_intent(query, filters)
            
            results = {
                'query': query,
                'processed_query': processed_query,
                'intent': intent,
                'products': [],
                'services': [],
                'categories': [],
                'locations': [],
                'total_results': 0,
                'search_metadata': {}
            }
            
            # Determine what to search based on intent
            if intent['search_type'] in ['product', 'both']:
                results['products'] = self._search_products(processed_query, filters, intent)
            
            if intent['search_type'] in ['service', 'both']:
                results['services'] = self._search_services(processed_query, filters, intent)
            
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
                'search_duration': 0,  # Will be calculated by the caller
                'filters_applied': filters,
                'confidence_score': self._calculate_confidence_score(results),
                'suggestions': self._generate_suggestions(query, results)
            }
            
            # Cache the results
            cache.set(cache_key, results, self.cache_timeout)
            
            logger.info(f"Search completed: {results['total_results']} results for '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Error in local search for '{query}': {str(e)}")
            return {
                'query': query,
                'error': str(e),
                'products': [],
                'services': [],
                'total_results': 0
            }
    
    def _search_products(self, query: str, filters: Dict, intent: Dict) -> List[Dict]:
        """Search products in the local database"""
        try:
            # Base queryset - only published products
            queryset = Products.objects.filter(
                product_status='published'
            ).select_related(
                'category', 'country', 'state', 'city', 'user'
            ).prefetch_related('product_ratings')
            
            # Apply text search
            if query:
                search_q = self._build_product_search_query(query)
                queryset = queryset.filter(search_q)
            
            # Apply filters
            queryset = self._apply_product_filters(queryset, filters)
            
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
                product_data = {
                    'id': product.id,
                    'name': product.product_name,
                    'description': product.product_description[:200] + "..." if len(product.product_description) > 200 else product.product_description,
                    'price': float(product.product_price),
                    'formatted_price': product.get_formatted_price(),
                    'currency': product.currency,
                    'image': product.featured_image.url if product.featured_image else None,
                    'condition': product.get_product_condition_display(),
                    'brand': product.product_brand,
                    'location': {
                        'city': product.city.name,
                        'state': product.state.name,
                        'country': product.country.name,
                        'full_location': product.get_full_location()
                    },
                    'category': {
                        'name': product.category.name,
                        'slug': product.category.slug
                    },
                    'seller': {
                        'name': f"{product.user.first_name} {product.user.last_name}",
                        'phone': product.provider_phone,
                        'email': product.provider_email,
                        'is_verified': hasattr(product.user, 'is_verified') and product.user.is_verified
                    },
                    'rating': {
                        'average': product.average_rating(),
                        'count': product.rating_count()
                    },
                    'stats': {
                        'views': product.views_count,
                        'favorites': product.favorites_count
                    },
                    'features': {
                        'is_promoted': product.is_promoted,
                        'is_featured': product.is_featured,
                        'is_negotiable': product.is_negotiable
                    },
                    'url': product.get_absolute_url(),
                    'created_at': product.created_at.isoformat(),
                    'type': 'product'
                }
                products.append(product_data)
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []
    
    def _search_services(self, query: str, filters: Dict, intent: Dict) -> List[Dict]:
        """Search services in the local database"""
        try:
            # Base queryset - only published services
            queryset = Services.objects.filter(
                service_status='published'
            ).select_related(
                'category', 'country', 'state', 'city', 'user'
            ).prefetch_related('service_ratings')
            
            # Apply text search
            if query:
                search_q = self._build_service_search_query(query)
                queryset = queryset.filter(search_q)
            
            # Apply filters
            queryset = self._apply_service_filters(queryset, filters)
            
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
                service_data = {
                    'id': service.id,
                    'name': service.service_name,
                    'description': service.service_description[:200] + "..." if len(service.service_description) > 200 else service.service_description,
                    'price_range': service.get_formatted_price_range(),
                    'price_type': service.get_price_type_display(),
                    'currency': service.currency,
                    'image': service.featured_image.url if service.featured_image else None,
                    'location': {
                        'city': service.city.name,
                        'state': service.state.name,
                        'country': service.country.name,
                        'full_location': service.get_full_location(),
                        'serves_remote': service.serves_remote,
                        'service_radius': service.service_radius
                    },
                    'category': {
                        'name': service.category.name,
                        'slug': service.category.slug
                    },
                    'provider': {
                        'name': service.provider_name,
                        'title': service.provider_title,
                        'bio': service.provider_bio[:150] + "..." if service.provider_bio and len(service.provider_bio) > 150 else service.provider_bio,
                        'experience': service.get_provider_experience_display(),
                        'expertise': service.provider_expertise[:100] + "..." if len(service.provider_expertise) > 100 else service.provider_expertise,
                        'phone': service.provider_phone,
                        'email': service.provider_email,
                        'website': service.provider_website,
                        'is_verified': service.is_verified
                    },
                    'rating': {
                        'average': service.average_rating(),
                        'count': service.rating_count()
                    },
                    'stats': {
                        'views': service.views_count,
                        'contacts': service.contacts_count
                    },
                    'features': {
                        'is_promoted': service.is_promoted,
                        'is_featured': service.is_featured,
                        'is_verified': service.is_verified,
                        'response_time': service.response_time,
                        'availability': service.availability
                    },
                    'url': service.get_absolute_url(),
                    'created_at': service.created_at.isoformat(),
                    'type': 'service'
                }
                services.append(service_data)
            
            return services
            
        except Exception as e:
            logger.error(f"Error searching services: {str(e)}")
            return []
    
    def _build_product_search_query(self, query: str) -> Q:
        """Build complex search query for products"""
        search_terms = self._extract_search_terms(query)
        
        q_objects = Q()
        
        for term in search_terms:
            term_q = (
                Q(product_name__icontains=term) |
                Q(product_description__icontains=term) |
                Q(product_brand__icontains=term) |
                Q(product_model__icontains=term) |
                Q(tags__icontains=term) |
                Q(category__name__icontains=term)
            )
            q_objects |= term_q
        
        return q_objects
    
    def _build_service_search_query(self, query: str) -> Q:
        """Build complex search query for services"""
        search_terms = self._extract_search_terms(query)
        
        q_objects = Q()
        
        for term in search_terms:
            term_q = (
                Q(service_name__icontains=term) |
                Q(service_description__icontains=term) |
                Q(provider_name__icontains=term) |
                Q(provider_expertise__icontains=term) |
                Q(tags__icontains=term) |
                Q(category__name__icontains=term)
            )
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
        
        if filters.get('condition'):
            queryset = queryset.filter(product_condition=filters['condition'])
        
        if filters.get('is_negotiable') is not None:
            queryset = queryset.filter(is_negotiable=filters['is_negotiable'])
        
        if filters.get('brand'):
            queryset = queryset.filter(product_brand__icontains=filters['brand'])
        
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
        
        if filters.get('min_price'):
            queryset = queryset.filter(starting_price__gte=filters['min_price'])
        
        if filters.get('max_price'):
            queryset = queryset.filter(
                Q(max_price__lte=filters['max_price']) |
                Q(starting_price__lte=filters['max_price'])
            )
        
        if filters.get('experience_level'):
            queryset = queryset.filter(provider_experience=filters['experience_level'])
        
        if filters.get('serves_remote') is not None:
            queryset = queryset.filter(serves_remote=filters['serves_remote'])
        
        if filters.get('is_verified') is not None:
            queryset = queryset.filter(is_verified=filters['is_verified'])
        
        return queryset
    
    def _rank_products(self, queryset, query: str, intent: Dict):
        """Apply ranking to products based on relevance"""
        # Basic ordering: promoted > featured > newest
        return queryset.order_by(
            '-is_promoted',
            '-is_featured', 
            '-created_at'
        )
    
    def _rank_services(self, queryset, query: str, intent: Dict):
        """Apply ranking to services based on relevance"""
        # Basic ordering: promoted > featured > verified > newest
        return queryset.order_by(
            '-is_promoted',
            '-is_featured',
            '-is_verified',
            '-created_at'
        )
    
    def _search_categories(self, query: str) -> List[Dict]:
        """Search categories"""
        try:
            categories = Category.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query),
                is_active=True
            )[:10]
            
            return [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'slug': cat.slug,
                    'description': cat.description,
                    'type': cat.category_type,
                    'parent': cat.parent.name if cat.parent else None,
                    'icon': cat.icon,
                    'product_count': cat.products.filter(product_status='published').count(),
                    'service_count': cat.services.filter(service_status='published').count()
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
            
            # Search countries
            countries = Country.objects.filter(
                Q(name__icontains=query),
                is_active=True
            )[:5]
            
            for country in countries:
                results.append({
                    'type': 'country',
                    'id': country.id,
                    'name': country.name,
                    'code': country.code,
                    'flag': country.flag_emoji
                })
            
            # Search states
            states = State.objects.filter(
                Q(name__icontains=query),
                is_active=True
            ).select_related('country')[:5]
            
            for state in states:
                results.append({
                    'type': 'state',
                    'id': state.id,
                    'name': state.name,
                    'country': state.country.name,
                    'full_name': f"{state.name}, {state.country.name}"
                })
            
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
                    'state': city.state.name,
                    'country': city.country.name,
                    'full_name': city.get_full_address()
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
            'search_type': 'both',  # product, service, both
            'category_search': False,
            'location_search': False,
            'price_range': None,
            'condition': None,
            'experience_level': None,
            'remote_service': False
        }
        
        if not query:
            return intent
        
        query_lower = query.lower()
        
        # Detect search type
        product_keywords = ['buy', 'purchase', 'product', 'item', 'sell', 'selling', 'price', 'cost']
        service_keywords = ['service', 'hire', 'book', 'appointment', 'professional', 'expert', 'help']
        
        product_score = sum(1 for keyword in product_keywords if keyword in query_lower)
        service_score = sum(1 for keyword in service_keywords if keyword in query_lower)
        
        if product_score > service_score:
            intent['search_type'] = 'product'
        elif service_score > product_score:
            intent['search_type'] = 'service'
        
        # Detect category search
        if any(word in query_lower for word in ['category', 'categories', 'type', 'kind']):
            intent['category_search'] = True
        
        # Detect location search
        if any(word in query_lower for word in ['in', 'at', 'near', 'location', 'city', 'state', 'country']):
            intent['location_search'] = True
        
        # Detect price-related queries
        price_pattern = r'(\$|\₦|naira|dollar|under|below|above|between)\s*(\d+)'
        price_matches = re.findall(price_pattern, query_lower)
        if price_matches:
            # Extract price information
            # This is a simplified version - you can make it more sophisticated
            pass
        
        # Detect condition for products
        if 'new' in query_lower:
            intent['condition'] = 'new'
        elif any(word in query_lower for word in ['used', 'second hand', 'secondhand']):
            intent['condition'] = 'used'
        
        # Detect remote service intent
        if any(word in query_lower for word in ['remote', 'online', 'virtual', 'anywhere']):
            intent['remote_service'] = True
        
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
            # No results - suggest alternatives
            suggestions.append("Try using different keywords")
            suggestions.append("Check your spelling")
            suggestions.append("Try searching in a different location")
            suggestions.append("Browse categories to find what you're looking for")
        elif results['total_results'] < 5:
            # Few results - suggest ways to get more
            suggestions.append("Try broader search terms")
            suggestions.append("Remove location filters to see more results")
        
        return suggestions[:3]  # Limit to 3 suggestions
    
    def _generate_cache_key(self, query: str, filters: Dict) -> str:
        """Generate cache key for the search"""
        import hashlib
        
        # Create a string representation of the search parameters
        search_params = f"{query}_{json.dumps(filters, sort_keys=True)}"
        
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