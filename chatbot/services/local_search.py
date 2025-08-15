# chatbot/services/local_search.py - FIXED VERSION WITH BETTER SEARCH LOGIC
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from django.db.models import Q, Count, Avg, Case, When, Value, CharField, F
from django.db.models.functions import Lower
from django.core.cache import cache
import logging
from asgiref.sync import sync_to_async

# Import your actual models - UPDATE THESE IMPORTS BASED ON YOUR PROJECT STRUCTURE
from main.models import Products, Services, Category, Country, State, City

logger = logging.getLogger(__name__)

class LocalSearchService:
    """
    Local database search service for products and services
    Searches your internal database first before falling back to external sources
    """
    
    def __init__(self):
        self.max_results = 10
        self.cache_timeout = 300  # 5 minutes
    
    async def search(self, query: str, search_type: str = 'both', filters: dict = None, location_context: dict = None) -> Dict[str, Any]:
        """
        Main async search method
        """
        try:
            logger.info(f"Starting local search for: '{query}' (type: {search_type})")
            
            # Use sync_to_async for Django ORM calls
            result = await sync_to_async(self._search_sync)(query, search_type, filters or {}, location_context)
            
            logger.info(f"Local search completed: found {result.get('total_results', 0)} results")
            return result
            
        except Exception as e:
            logger.error(f"Error in local search: {str(e)}")
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
        try:
            processed_query = self._preprocess_query(query)
            
            results = {
                'success': True,
                'query': query,
                'processed_query': processed_query,
                'products': [],
                'services': [],
                'total_results': 0,
                'search_type': search_type
            }
            
            # Search products if requested
            if search_type in ['products', 'both']:
                results['products'] = self._search_products(processed_query, filters, location_context)
            
            # Search services if requested  
            if search_type in ['services', 'both']:
                results['services'] = self._search_services(processed_query, filters, location_context)
            
            # Calculate total results
            results['total_results'] = len(results['products']) + len(results['services'])
            
            logger.info(f"Local search found {results['total_results']} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in local search sync: {str(e)}")
            return {
                'success': False,
                'query': query,
                'error': str(e),
                'products': [],
                'services': [],
                'total_results': 0,
                'search_type': search_type
            }
    
    def _search_products(self, query: str, filters: Dict, location_context: Dict = None) -> List[Dict]:
        """Search products in local database with IMPROVED LOGIC"""
        try:
            # Base queryset - only published/active products
            queryset = Products.objects.filter(
                product_status='published'  # Adjust field name if different
            ).select_related(
                'category', 'country', 'state', 'city', 'user'
            )
            
            # Apply text search if query provided
            if query:
                search_q = self._build_improved_product_search_query(query)
                if search_q:
                    queryset = queryset.filter(search_q)
                else:
                    # If no valid search terms, return empty
                    return []
            
            # Apply additional filters
            queryset = self._apply_product_filters(queryset, filters)
            
            # Apply location context if provided
            if location_context:
                queryset = self._apply_location_filter(queryset, location_context)
            
            # Order by relevance (you can customize this)
            queryset = queryset.order_by('-created_at')
            
            # Limit results
            queryset = queryset[:self.max_results]
            
            # Format products for response
            products = []
            for product in queryset:
                product_data = self._format_product_data(product)
                products.append(product_data)
            
            logger.info(f"Found {len(products)} products for query: {query}")
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []
    
    def _search_services(self, query: str, filters: Dict, location_context: Dict = None) -> List[Dict]:
        """Search services in local database with IMPROVED LOGIC"""
        try:
            # Base queryset - only published/active services
            queryset = Services.objects.filter(
                service_status='published'  # Adjust field name if different
            ).select_related(
                'category', 'country', 'state', 'city', 'user'
            )
            
            # Apply text search if query provided
            if query:
                search_q = self._build_improved_service_search_query(query)
                if search_q:
                    queryset = queryset.filter(search_q)
                else:
                    # If no valid search terms, return empty
                    return []
            
            # Apply additional filters
            queryset = self._apply_service_filters(queryset, filters)
            
            # Apply location context if provided
            if location_context:
                queryset = self._apply_location_filter(queryset, location_context)
            
            # Order by relevance
            queryset = queryset.order_by('-created_at')
            
            # Limit results
            queryset = queryset[:self.max_results]
            
            # Format services for response
            services = []
            for service in queryset:
                service_data = self._format_service_data(service)
                services.append(service_data)
            
            logger.info(f"Found {len(services)} services for query: {query}")
            return services
            
        except Exception as e:
            logger.error(f"Error searching services: {str(e)}")
            return []
    
    def _build_improved_product_search_query(self, query: str) -> Optional[Q]:
        """
        IMPROVED: Build search query for products using AND logic instead of OR
        This will make searches more specific and relevant
        """
        search_terms = self._extract_search_terms(query)
        if not search_terms:
            return None
        
        # For each term, it must appear in at least one field (AND logic between terms)
        final_q = Q()
        
        for term in search_terms:
            # This term must appear in at least one of these fields
            term_q = (
                Q(product_name__icontains=term) |
                Q(product_description__icontains=term)
            )
            
            # Add more fields if they exist in your model
            if hasattr(Products, 'product_brand'):
                term_q |= Q(product_brand__icontains=term)
            if hasattr(Products, 'tags'):
                term_q |= Q(tags__icontains=term)
            
            # Search in category name
            term_q |= Q(category__name__icontains=term)
            
            # AND this term requirement with previous terms
            if not final_q:
                final_q = term_q
            else:
                final_q = final_q & term_q
        
        logger.info(f"Built product search query for terms: {search_terms}")
        return final_q
    
    def _build_improved_service_search_query(self, query: str) -> Optional[Q]:
        """
        IMPROVED: Build search query for services using AND logic instead of OR
        """
        search_terms = self._extract_search_terms(query)
        if not search_terms:
            return None
        
        # For each term, it must appear in at least one field (AND logic between terms)
        final_q = Q()
        
        for term in search_terms:
            # This term must appear in at least one of these fields
            term_q = (
                Q(service_name__icontains=term) |
                Q(service_description__icontains=term)
            )
            
            # Add more fields if they exist in your model
            if hasattr(Services, 'provider_name'):
                term_q |= Q(provider_name__icontains=term)
            if hasattr(Services, 'provider_expertise'):
                term_q |= Q(provider_expertise__icontains=term)
            if hasattr(Services, 'tags'):
                term_q |= Q(tags__icontains=term)
            
            # Search in category name
            term_q |= Q(category__name__icontains=term)
            
            # AND this term requirement with previous terms
            if not final_q:
                final_q = term_q
            else:
                final_q = final_q & term_q
        
        logger.info(f"Built service search query for terms: {search_terms}")
        return final_q
    
    # Keep all your existing formatting methods unchanged...
    def _format_product_data(self, product) -> Dict:
        """Format product data according to your requirements"""
        try:
            # Get image URL
            image_url = None
            if hasattr(product, 'featured_image') and product.featured_image:
                image_url = product.featured_image.url if hasattr(product.featured_image, 'url') else str(product.featured_image)
            
            # Format price
            price = float(product.product_price) if product.product_price else 0.0
            formatted_price = f"₦{price:,.2f}" if price > 0 else "Price on request"
            
            # Get original price if available
            original_price = getattr(product, 'original_price', None)
            if original_price:
                original_price = float(original_price)
            
            return {
                'product_name': product.product_name,
                'product_description': product.product_description[:300] + "..." if product.product_description and len(product.product_description) > 300 else (product.product_description or ""),
                'featured_image': image_url,
                'product_price': formatted_price,
                'original_price': f"₦{original_price:,.2f}" if original_price else None,
                'currency': 'NGN',  # Adjust based on your system
                'is_negotiable': getattr(product, 'is_negotiable', False),
                'country': product.country.name if product.country else 'Nigeria',
                'state': product.state.name if product.state else '',
                'city': product.city.name if product.city else '',
                'address_details': getattr(product, 'address_details', ''),
                'provider_email': product.user.email if product.user else '',
                'provider_whatsapp': getattr(product, 'provider_whatsapp', ''),
                
                # Additional fields for internal use
                'name': product.product_name,  # For compatibility
                'description': product.product_description or '',
                'location': {
                    'city': product.city.name if product.city else '',
                    'state': product.state.name if product.state else '',
                    'country': product.country.name if product.country else 'Nigeria',
                    'full_location': f"{product.city.name if product.city else ''}, {product.state.name if product.state else ''}"
                },
                'seller': {
                    'name': f"{product.user.first_name} {product.user.last_name}" if product.user else "Unknown",
                    'email': product.user.email if product.user else '',
                    'phone': getattr(product, 'provider_whatsapp', ''),
                },
                'id': product.id,
                'type': 'product'
            }
            
        except Exception as e:
            logger.error(f"Error formatting product data: {str(e)}")
            return {
                'product_name': getattr(product, 'product_name', 'Unknown Product'),
                'product_description': '',
                'featured_image': None,
                'product_price': 'Price not available',
                'original_price': None,
                'currency': 'NGN',
                'is_negotiable': False,
                'country': 'Nigeria',
                'state': '',
                'city': '',
                'address_details': '',
                'provider_email': '',
                'provider_whatsapp': '',
                'type': 'product'
            }
    
    def _format_service_data(self, service) -> Dict:
        """Format service data according to your requirements"""
        try:
            # Get image URL
            image_url = None
            if hasattr(service, 'featured_image') and service.featured_image:
                image_url = service.featured_image.url if hasattr(service.featured_image, 'url') else str(service.featured_image)
            
            return {
                'service_name': service.service_name,
                'service_description': service.service_description[:300] + "..." if service.service_description and len(service.service_description) > 300 else (service.service_description or ""),
                'featured_image': image_url,
                'country': service.country.name if service.country else 'Nigeria',
                'state': service.state.name if service.state else '',
                'city': service.city.name if service.city else '',
                'serves_remote': getattr(service, 'serves_remote', False),
                'provider_name': getattr(service, 'provider_name', service.user.get_full_name() if service.user else 'Unknown'),
                'provider_expertise': getattr(service, 'provider_expertise', ''),
                'provider_experience': getattr(service, 'provider_experience', ''),
                'provider_languages': getattr(service, 'provider_languages', ''),
                'provider_email': service.user.email if service.user else '',
                
                # Additional fields for internal use
                'name': service.service_name,  # For compatibility
                'description': service.service_description or '',
                'location': {
                    'city': service.city.name if service.city else '',
                    'state': service.state.name if service.state else '',
                    'country': service.country.name if service.country else 'Nigeria',
                    'full_location': f"{service.city.name if service.city else ''}, {service.state.name if service.state else ''}"
                },
                'provider': {
                    'name': getattr(service, 'provider_name', service.user.get_full_name() if service.user else 'Unknown'),
                    'expertise': getattr(service, 'provider_expertise', ''),
                    'experience': getattr(service, 'provider_experience', ''),
                    'email': service.user.email if service.user else '',
                },
                'formatted_price': 'Contact for pricing',  # You can customize this
                'id': service.id,
                'type': 'service'
            }
            
        except Exception as e:
            logger.error(f"Error formatting service data: {str(e)}")
            return {
                'service_name': getattr(service, 'service_name', 'Unknown Service'),
                'service_description': '',
                'featured_image': None,
                'country': 'Nigeria',
                'state': '',
                'city': '',
                'serves_remote': False,
                'provider_name': 'Unknown',
                'provider_expertise': '',
                'provider_experience': '',
                'provider_languages': '',
                'provider_email': '',
                'type': 'service'
            }
    
    def _apply_product_filters(self, queryset, filters: Dict):
        """Apply additional filters to product queryset"""
        if filters.get('category'):
            queryset = queryset.filter(category__name__icontains=filters['category'])
        
        if filters.get('location'):
            location = filters['location']
            if isinstance(location, dict):
                if location.get('city'):
                    queryset = queryset.filter(city__name__icontains=location['city'])
                elif location.get('state'):
                    queryset = queryset.filter(state__name__icontains=location['state'])
        
        if filters.get('min_price'):
            queryset = queryset.filter(product_price__gte=filters['min_price'])
        
        if filters.get('max_price'):
            queryset = queryset.filter(product_price__lte=filters['max_price'])
        
        return queryset
    
    def _apply_service_filters(self, queryset, filters: Dict):
        """Apply additional filters to service queryset"""
        if filters.get('category'):
            queryset = queryset.filter(category__name__icontains=filters['category'])
        
        if filters.get('location'):
            location = filters['location']
            if isinstance(location, dict):
                if location.get('city'):
                    queryset = queryset.filter(city__name__icontains=location['city'])
                elif location.get('state'):
                    queryset = queryset.filter(state__name__icontains=location['state'])
        
        return queryset
    
    def _apply_location_filter(self, queryset, location_context: Dict):
        """Apply location filter based on context"""
        try:
            if location_context.get('city'):
                queryset = queryset.filter(city__name__icontains=location_context['city'])
            elif location_context.get('state'):
                queryset = queryset.filter(state__name__icontains=location_context['state'])
            elif location_context.get('country'):
                queryset = queryset.filter(country__name__icontains=location_context['country'])
            
            return queryset
        except Exception as e:
            logger.error(f"Error applying location filter: {str(e)}")
            return queryset
    
    def _preprocess_query(self, query: str) -> str:
        """Clean and preprocess the search query"""
        if not query:
            return ""
        
        # Convert to lowercase and strip
        query = query.lower().strip()
        
        # Remove common stop words but keep product-specific terms
        stop_words = ['i', 'want', 'need', 'looking', 'for', 'find', 'buy', 'purchase', 'get', 'show', 'me']
        words = query.split()
        filtered_words = [word for word in words if word not in stop_words or len(words) <= 2]
        query = ' '.join(filtered_words) if filtered_words else query
        
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
        
        # Remove very short terms (less than 2 characters) unless it's a single term
        if len(terms) > 1:
            terms = [term for term in terms if len(term) >= 2]
        
        # Keep only meaningful terms for product search
        meaningful_terms = []
        for term in terms:
            # Keep numbers (like "16", "64gb", etc.)
            # Keep brand names, model names, etc.
            if term.isdigit() or len(term) >= 2:
                meaningful_terms.append(term)
        
        logger.info(f"Extracted search terms: {meaningful_terms} from query: {query}")
        return meaningful_terms