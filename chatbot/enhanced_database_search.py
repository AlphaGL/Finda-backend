# enhanced_database_search.py - WORLD-CLASS DATABASE SEARCH SYSTEM
from django.db.models import Q, F, Value, Case, When, IntegerField, Count, Avg
from django.db.models.functions import Lower, Coalesce
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from django.utils import timezone
from main.models import Products, Services, Category
import re
import logging
from datetime import timedelta
import json
from collections import defaultdict

logger = logging.getLogger(__name__)


class AdvancedSearchEngine:
    """
    WORLD-CLASS search engine with AI-powered relevance scoring
    """
    
    def __init__(self):
        self.search_cache_timeout = 300  # 5 minutes
        self.max_results_per_type = 10
        
    def search_products_and_services(self, query, filters=None, limit=8, user_location=None):
        """
        ENHANCED: Comprehensive search with multiple ranking factors
        """
        try:
            if not query or len(str(query).strip()) < 2:
                return {'products': [], 'services': [], 'total': 0, 'search_time': 0}
            
            start_time = timezone.now()
            clean_query = self.clean_and_enhance_query(query)
            
            logger.info(f"🔍 Enhanced search for: '{clean_query}' (original: '{query}')")
            
            # Check cache first
            cache_key = self.generate_cache_key(clean_query, filters, limit, user_location)
            cached_results = cache.get(cache_key)
            if cached_results:
                logger.info(f"✅ Cache hit for: '{clean_query}'")
                return cached_results
            
            # Initialize results
            results = {
                'products': [],
                'services': [],
                'total': 0,
                'search_time': 0,
                'query_analysis': self.analyze_query(clean_query),
                'suggestions': []
            }
            
            # Search products with advanced scoring
            products = self.search_products_advanced(clean_query, filters, limit//2, user_location)
            
            # Search services with advanced scoring  
            services = self.search_services_advanced(clean_query, filters, limit//2, user_location)
            
            # Combine and re-rank results
            all_items = []
            all_items.extend([(item, 'product') for item in products])
            all_items.extend([(item, 'service') for item in services])
            
            # Apply cross-category ranking
            ranked_items = self.apply_cross_category_ranking(all_items, clean_query, user_location)
            
            # Separate back into categories
            products_final = []
            services_final = []
            
            for item, item_type in ranked_items[:limit]:
                if item_type == 'product' and len(products_final) < limit//2 + 2:
                    products_final.append(item)
                elif item_type == 'service' and len(services_final) < limit//2 + 2:
                    services_final.append(item)
            
            results.update({
                'products': products_final,
                'services': services_final,
                'total': len(products_final) + len(services_final),
                'search_time': (timezone.now() - start_time).total_seconds(),
                'suggestions': self.generate_search_suggestions(clean_query, results['query_analysis'])
            })
            
            # Cache successful results
            if results['total'] > 0:
                cache.set(cache_key, results, timeout=self.search_cache_timeout)
            
            logger.info(f"✅ Search completed: {results['total']} results in {results['search_time']:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Enhanced search error: {str(e)}")
            return {'products': [], 'services': [], 'total': 0, 'search_time': 0}
    
    def search_products_advanced(self, query, filters, limit, user_location):
        """
        ENHANCED: Advanced product search with PostgreSQL full-text search
        """
        try:
            # Base queryset with optimizations
            queryset = Products.objects.select_related(
                'category', 'country', 'state', 'city', 'user'
            ).prefetch_related(
                'productimage_set', 'productreview_set'
            ).filter(
                product_status='published'
            )
            
            # Apply filters
            if filters:
                queryset = self.apply_filters(queryset, filters, 'product')
            
            # Build search components
            search_terms = self.extract_search_terms(query)
            
            # PostgreSQL full-text search (if available)
            try:
                search_vector = SearchVector('product_name', weight='A') + \
                               SearchVector('product_description', weight='B') + \
                               SearchVector('product_brand', weight='A') + \
                               SearchVector('tags', weight='C')
                
                search_query = SearchQuery(query)
                
                # Apply full-text search with ranking
                queryset = queryset.annotate(
                    search_rank=SearchRank(search_vector, search_query)
                ).filter(
                    search_rank__gt=0.1
                )
                
            except Exception as fts_error:
                logger.warning(f"Full-text search unavailable, falling back to ILIKE: {str(fts_error)}")
                # Fallback to ILIKE search
                search_conditions = Q()
                for term in search_terms:
                    search_conditions |= (
                        Q(product_name__icontains=term) |
                        Q(product_description__icontains=term) |
                        Q(product_brand__icontains=term) |
                        Q(tags__icontains=term) |
                        Q(category__name__icontains=term)
                    )
                
                queryset = queryset.filter(search_conditions)
                
                # Add manual ranking annotation
                queryset = queryset.annotate(
                    search_rank=Case(
                        When(product_name__iexact=query, then=Value(1.0)),
                        When(product_name__icontains=query, then=Value(0.8)),
                        When(product_brand__iexact=query, then=Value(0.9)),
                        When(product_brand__icontains=query, then=Value(0.7)),
                        default=Value(0.5),
                        output_field=models.FloatField()
                    )
                )
            
            # Add business logic annotations
            queryset = queryset.annotate(
                # Rating metrics
                avg_rating=Coalesce(Avg('productreview__rating'), Value(0.0)),
                review_count=Count('productreview', distinct=True),
                
                # Engagement metrics
                total_views=Coalesce(F('views_count'), Value(0)),
                total_favorites=Coalesce(F('favorites_count'), Value(0)),
                
                # Seller reputation
                seller_rating=Coalesce(Avg('user__seller_reviews__rating'), Value(0.0)),
                
                # Business priority score
                business_score=Case(
                    When(is_promoted=True, then=Value(100)),
                    When(is_featured=True, then=Value(50)),
                    When(user__is_verified=True, then=Value(25)),
                    default=Value(0)
                ),
                
                # Location relevance (if user location provided)
                location_score=self.calculate_location_score(user_location)
            )
            
            # Apply complex ordering
            queryset = queryset.order_by(
                '-business_score',
                '-search_rank',
                '-avg_rating',
                '-total_views',
                '-created_at'
            )
            
            # Get results with error handling
            products = []
            for product in queryset[:limit * 2]:  # Get extra for filtering
                try:
                    # Additional quality checks
                    if self.passes_quality_filter(product, query):
                        products.append(product)
                        if len(products) >= limit:
                            break
                except Exception as product_error:
                    logger.error(f"Product processing error: {str(product_error)}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Advanced product search error: {str(e)}")
            return []
    
    def search_services_advanced(self, query, filters, limit, user_location):
        """
        ENHANCED: Advanced service search with location priority
        """
        try:
            # Base queryset with optimizations
            queryset = Services.objects.select_related(
                'category', 'country', 'state', 'city', 'user'
            ).prefetch_related(
                'serviceimage_set', 'servicereview_set'
            ).filter(
                service_status='published'
            )
            
            # Apply filters
            if filters:
                queryset = self.apply_filters(queryset, filters, 'service')
            
            # Build search components
            search_terms = self.extract_search_terms(query)
            
            # PostgreSQL full-text search (if available)
            try:
                search_vector = SearchVector('service_name', weight='A') + \
                               SearchVector('service_description', weight='B') + \
                               SearchVector('tags', weight='C')
                
                search_query = SearchQuery(query)
                
                queryset = queryset.annotate(
                    search_rank=SearchRank(search_vector, search_query)
                ).filter(
                    search_rank__gt=0.1
                )
                
            except Exception as fts_error:
                logger.warning(f"Service full-text search unavailable: {str(fts_error)}")
                # Fallback to ILIKE search
                search_conditions = Q()
                for term in search_terms:
                    search_conditions |= (
                        Q(service_name__icontains=term) |
                        Q(service_description__icontains=term) |
                        Q(tags__icontains=term) |
                        Q(category__name__icontains=term)
                    )
                
                queryset = queryset.filter(search_conditions)
                
                # Add manual ranking
                queryset = queryset.annotate(
                    search_rank=Case(
                        When(service_name__iexact=query, then=Value(1.0)),
                        When(service_name__icontains=query, then=Value(0.8)),
                        default=Value(0.5),
                        output_field=models.FloatField()
                    )
                )
            
            # Add business logic annotations
            queryset = queryset.annotate(
                # Rating metrics
                avg_rating=Coalesce(Avg('servicereview__rating'), Value(0.0)),
                review_count=Count('servicereview', distinct=True),
                
                # Engagement metrics
                total_views=Coalesce(F('views_count'), Value(0)),
                total_contacts=Coalesce(F('contacts_count'), Value(0)),
                
                # Seller reputation
                seller_rating=Coalesce(Avg('user__seller_reviews__rating'), Value(0.0)),
                
                # Business priority score
                business_score=Case(
                    When(is_promoted=True, then=Value(100)),
                    When(is_featured=True, then=Value(50)),
                    When(user__is_verified=True, then=Value(25)),
                    default=Value(0)
                ),
                
                # Location relevance (higher for services)
                location_score=self.calculate_location_score(user_location, weight=2.0)
            )
            
            # Apply complex ordering (location more important for services)
            queryset = queryset.order_by(
                '-business_score',
                '-location_score',
                '-search_rank',
                '-avg_rating',
                '-total_contacts',
                '-created_at'
            )
            
            # Get results with quality filtering
            services = []
            for service in queryset[:limit * 2]:
                try:
                    if self.passes_quality_filter(service, query):
                        services.append(service)
                        if len(services) >= limit:
                            break
                except Exception as service_error:
                    logger.error(f"Service processing error: {str(service_error)}")
                    continue
            
            return services
            
        except Exception as e:
            logger.error(f"Advanced service search error: {str(e)}")
            return []
    
    def apply_cross_category_ranking(self, all_items, query, user_location):
        """
        ENHANCED: Apply unified ranking across products and services
        """
        try:
            scored_items = []
            
            for item, item_type in all_items:
                try:
                    score = self.calculate_unified_score(item, query, item_type, user_location)
                    scored_items.append((item, item_type, score))
                except Exception as scoring_error:
                    logger.error(f"Scoring error for {item_type}: {str(scoring_error)}")
                    continue
            
            # Sort by unified score
            scored_items.sort(key=lambda x: x[2], reverse=True)
            
            # Return items without scores
            return [(item, item_type) for item, item_type, score in scored_items]
            
        except Exception as e:
            logger.error(f"Cross-category ranking error: {str(e)}")
            return all_items
    
    def calculate_unified_score(self, item, query, item_type, user_location):
        """
        ENHANCED: Calculate unified relevance score across all factors
        """
        try:
            score = 0
            query_lower = query.lower()
            
            # Get item attributes safely
            if item_type == 'product':
                name = getattr(item, 'product_name', '').lower()
                description = getattr(item, 'product_description', '').lower()
                brand = getattr(item, 'product_brand', '').lower()
                price = getattr(item, 'product_price', 0)
            else:
                name = getattr(item, 'service_name', '').lower()
                description = getattr(item, 'service_description', '').lower()
                brand = ''
                price = getattr(item, 'starting_price', 0) or 0
            
            tags = getattr(item, 'tags', '').lower()
            category_name = getattr(item.category, 'name', '').lower() if hasattr(item, 'category') and item.category else ''
            
            # 1. Name relevance (highest priority)
            if query_lower == name:
                score += 1000  # Exact match
            elif query_lower in name:
                if name.startswith(query_lower):
                    score += 800  # Starts with query
                else:
                    score += 600  # Contains query
            
            # 2. Brand relevance (for products)
            if item_type == 'product' and brand:
                if query_lower == brand:
                    score += 900
                elif query_lower in brand:
                    score += 400
            
            # 3. Multi-word query analysis
            query_words = [word for word in query_lower.split() if len(word) >= 3]
            for word in query_words:
                if word in name:
                    score += 200 if name.startswith(word) else 100
                if brand and word in brand:
                    score += 150
                if word in category_name:
                    score += 80
                if word in tags:
                    score += 60
                if word in description:
                    score += 30
            
            # 4. Business quality factors
            try:
                # Ratings
                avg_rating = getattr(item, 'avg_rating', 0) or (
                    item.average_rating() if hasattr(item, 'average_rating') else 0
                )
                if avg_rating >= 4.5:
                    score += 100
                elif avg_rating >= 4.0:
                    score += 60
                elif avg_rating >= 3.5:
                    score += 30
                
                # Review count
                review_count = getattr(item, 'review_count', 0) or (
                    item.reviews_count() if hasattr(item, 'reviews_count') else 0
                )
                if review_count > 50:
                    score += 50
                elif review_count > 10:
                    score += 25
                elif review_count > 0:
                    score += 10
                
            except Exception as rating_error:
                logger.error(f"Rating calculation error: {str(rating_error)}")
            
            # 5. Business features
            try:
                if getattr(item, 'is_promoted', False):
                    score += 200  # Promoted items get high priority
                if getattr(item, 'is_featured', False):
                    score += 100
                if hasattr(item, 'user') and getattr(item.user, 'is_verified', False):
                    score += 50
            except Exception as feature_error:
                logger.error(f"Feature calculation error: {str(feature_error)}")
            
            # 6. Engagement metrics
            try:
                views = getattr(item, 'total_views', 0) or getattr(item, 'views_count', 0)
                if views > 1000:
                    score += 40
                elif views > 100:
                    score += 20
                elif views > 10:
                    score += 10
                
                # Service-specific: contact count
                if item_type == 'service':
                    contacts = getattr(item, 'total_contacts', 0) or getattr(item, 'contacts_count', 0)
                    if contacts > 50:
                        score += 30
                    elif contacts > 10:
                        score += 15
                
                # Product-specific: favorites
                if item_type == 'product':
                    favorites = getattr(item, 'total_favorites', 0) or getattr(item, 'favorites_count', 0)
                    if favorites > 20:
                        score += 25
                    elif favorites > 5:
                        score += 10
                        
            except Exception as engagement_error:
                logger.error(f"Engagement calculation error: {str(engagement_error)}")
            
            # 7. Location relevance
            try:
                if user_location:
                    location_bonus = self.calculate_location_bonus(item, user_location)
                    score += location_bonus
            except Exception as location_error:
                logger.error(f"Location calculation error: {str(location_error)}")
            
            # 8. Price competitiveness (if applicable)
            try:
                if price > 0:
                    # Find similar items for price comparison
                    price_bonus = self.calculate_price_competitiveness(item, price, item_type)
                    score += price_bonus
            except Exception as price_error:
                logger.error(f"Price calculation error: {str(price_error)}")
            
            # 9. Freshness factor
            try:
                created_at = getattr(item, 'created_at', None)
                if created_at:
                    days_old = (timezone.now() - created_at).days
                    if days_old < 7:
                        score += 20  # New listings bonus
                    elif days_old < 30:
                        score += 10
            except Exception as freshness_error:
                logger.error(f"Freshness calculation error: {str(freshness_error)}")
            
            # 10. Penalty for poor matches
            if score < 100:  # Low relevance
                # Check if there's any meaningful match
                has_match = any([
                    query_lower in name,
                    brand and query_lower in brand,
                    any(word in name for word in query_words),
                    query_lower in category_name
                ])
                
                if not has_match:
                    score = max(0, score // 10)  # Severe penalty
            
            return max(0, score)  # Ensure non-negative
            
        except Exception as e:
            logger.error(f"Unified score calculation error: {str(e)}")
            return 0
    
    def calculate_location_score(self, user_location, weight=1.0):
        """
        ENHANCED: Calculate location-based relevance score
        """
        try:
            if not user_location:
                return Value(0)
            
            # This would be implemented based on your location model structure
            # For now, return a placeholder
            return Value(10 * weight)  # Placeholder value
            
        except Exception as e:
            logger.error(f"Location score calculation error: {str(e)}")
            return Value(0)
    
    def calculate_location_bonus(self, item, user_location):
        """
        Calculate location proximity bonus
        """
        try:
            # Implement based on your location structure
            # This is a simplified version
            
            user_state = user_location.get('state', '').lower()
            user_city = user_location.get('city', '').lower()
            
            item_state = ''
            item_city = ''
            
            try:
                if hasattr(item, 'state') and item.state:
                    item_state = item.state.name.lower()
                if hasattr(item, 'city') and item.city:
                    item_city = item.city.name.lower()
            except:
                pass
            
            bonus = 0
            if item_city == user_city:
                bonus += 50  # Same city
            elif item_state == user_state:
                bonus += 25  # Same state
            
            return bonus
            
        except Exception as e:
            logger.error(f"Location bonus calculation error: {str(e)}")
            return 0
    
    def calculate_price_competitiveness(self, item, price, item_type):
        """
        Calculate price competitiveness bonus
        """
        try:
            # This would involve comparing with similar items
            # Simplified implementation for now
            
            if price <= 0:
                return 0
            
            # Get category average (cached)
            category = getattr(item, 'category', None)
            if not category:
                return 0
            
            cache_key = f"avg_price_{item_type}_{category.id}"
            avg_price = cache.get(cache_key)
            
            if avg_price is None:
                # Calculate average price for category
                if item_type == 'product':
                    avg_price = Products.objects.filter(
                        category=category,
                        product_status='published',
                        product_price__gt=0
                    ).aggregate(avg=Avg('product_price'))['avg'] or 0
                else:
                    avg_price = Services.objects.filter(
                        category=category,
                        service_status='published',
                        starting_price__gt=0
                    ).aggregate(avg=Avg('starting_price'))['avg'] or 0
                
                cache.set(cache_key, avg_price, timeout=3600)  # Cache for 1 hour
            
            if avg_price > 0:
                price_ratio = price / avg_price
                if price_ratio < 0.8:  # 20% below average
                    return 30
                elif price_ratio < 0.9:  # 10% below average
                    return 15
                elif price_ratio <= 1.1:  # Around average
                    return 5
            
            return 0
            
        except Exception as e:
            logger.error(f"Price competitiveness calculation error: {str(e)}")
            return 0
    
    def passes_quality_filter(self, item, query):
        """
        ENHANCED: Quality filter to ensure good results
        """
        try:
            # Basic quality checks
            is_product = hasattr(item, 'product_name')
            name = getattr(item, 'product_name' if is_product else 'service_name', '')
            
            # Must have a name
            if not name or len(name.strip()) < 3:
                return False
            
            # Must have description
            description = getattr(item, 'product_description' if is_product else 'service_description', '')
            if not description or len(description.strip()) < 10:
                return False
            
            # Must have some relevance to query
            query_lower = query.lower()
            name_lower = name.lower()
            
            # Check for minimum relevance
            has_relevance = (
                query_lower in name_lower or
                any(word in name_lower for word in query_lower.split() if len(word) >= 3) or
                query_lower in description.lower()
            )
            
            if not has_relevance:
                return False
            
            # Check for adult content or inappropriate material (if needed)
            # inappropriate_terms = ['adult', 'xxx', 'porn']  # Add as needed
            # if any(term in name_lower for term in inappropriate_terms):
            #     return False
            
            return True
            
        except Exception as e:
            logger.error(f"Quality filter error: {str(e)}")
            return True  # Default to allowing if error
    
    def apply_filters(self, queryset, filters, item_type):
        """
        ENHANCED: Apply user-specified filters
        """
        try:
            if not filters:
                return queryset
            
            # Price range filter
            min_price = filters.get('min_price')
            max_price = filters.get('max_price')
            
            if min_price is not None:
                price_field = 'product_price' if item_type == 'product' else 'starting_price'
                queryset = queryset.filter(**{f'{price_field}__gte': min_price})
            
            if max_price is not None:
                price_field = 'product_price' if item_type == 'product' else 'starting_price'
                queryset = queryset.filter(**{f'{price_field}__lte': max_price})
            
            # Category filter
            category_id = filters.get('category_id')
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            # Location filters
            country_id = filters.get('country_id')
            if country_id:
                queryset = queryset.filter(country_id=country_id)
            
            state_id = filters.get('state_id')
            if state_id:
                queryset = queryset.filter(state_id=state_id)
            
            city_id = filters.get('city_id')
            if city_id:
                queryset = queryset.filter(city_id=city_id)
            
            # Rating filter
            min_rating = filters.get('min_rating')
            if min_rating:
                review_field = 'productreview' if item_type == 'product' else 'servicereview'
                queryset = queryset.annotate(
                    avg_rating_filter=Avg(f'{review_field}__rating')
                ).filter(avg_rating_filter__gte=min_rating)
            
            # Business type filters
            if filters.get('promoted_only'):
                queryset = queryset.filter(is_promoted=True)
            
            if filters.get('featured_only'):
                queryset = queryset.filter(is_featured=True)
            
            if filters.get('verified_sellers_only'):
                queryset = queryset.filter(user__is_verified=True)
            
            return queryset
            
        except Exception as e:
            logger.error(f"Filter application error: {str(e)}")
            return queryset
    
    def clean_and_enhance_query(self, query):
        """
        ENHANCED: Clean and enhance search query
        """
        try:
            if not query:
                return ""
            
            # Basic cleaning
            cleaned = re.sub(r'[^\w\s]', ' ', str(query))
            cleaned = ' '.join(cleaned.split()).lower().strip()
            
            # Remove stop words but keep important ones
            stop_words = {
                'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
                'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers',
                'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
                'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
                'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does',
                'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until',
                'while', 'of', 'at', 'by', 'for', 'with', 'through', 'during', 'before', 'after',
                'above', 'below', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
                'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
                'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
                'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will',
                'just', 'don', 'should', 'now'
            }
            
            # Keep action words that are meaningful for search
            action_words = {
                'buy', 'sell', 'find', 'search', 'looking', 'need', 'want', 'get', 'purchase'
            }
            
            words = cleaned.split()
            meaningful_words = []
            
            for word in words:
                if len(word) >= 2 and (word not in stop_words or word in action_words):
                    meaningful_words.append(word)
            
            # If all words were removed, use original
            if not meaningful_words:
                return cleaned
            
            enhanced_query = ' '.join(meaningful_words)
            
            # Add query expansions for common terms
            expansions = {
                'phone': 'phone smartphone mobile',
                'laptop': 'laptop computer notebook',
                'car': 'car vehicle automobile',
                'dress': 'dress clothing apparel',
                'shoes': 'shoes footwear sneakers',
                'repair': 'repair fix service maintenance'
            }
            
            for term, expansion in expansions.items():
                if term in enhanced_query:
                    enhanced_query = enhanced_query.replace(term, expansion)
            
            return enhanced_query[:100]  # Limit length
            
        except Exception as e:
            logger.error(f"Query enhancement error: {str(e)}")
            return str(query)[:100]
    
    def extract_search_terms(self, query):
        """
        ENHANCED: Extract meaningful search terms
        """
        try:
            words = query.lower().split()
            # Return words that are at least 2 characters
            return [word for word in words if len(word) >= 2]
        except Exception as e:
            logger.error(f"Search terms extraction error: {str(e)}")
            return [query.lower()]
    
    def analyze_query(self, query):
        """
        ENHANCED: Analyze query for insights and improvements
        """
        try:
            analysis = {
                'query_type': 'general',
                'intent': 'search',
                'brand_mentioned': None,
                'category_suggested': None,
                'price_range_suggested': None,
                'location_mentioned': None
            }
            
            query_lower = query.lower()
            
            # Detect query type
            if any(word in query_lower for word in ['service', 'repair', 'fix', 'plumber', 'electrician']):
                analysis['query_type'] = 'service'
            elif any(word in query_lower for word in ['product', 'buy', 'purchase', 'sell']):
                analysis['query_type'] = 'product'
            
            # Detect brands
            common_brands = [
                'apple', 'samsung', 'nike', 'adidas', 'toyota', 'honda', 'sony', 'lg',
                'dell', 'hp', 'lenovo', 'microsoft', 'google', 'amazon', 'jumia'
            ]
            
            for brand in common_brands:
                if brand in query_lower:
                    analysis['brand_mentioned'] = brand.title()
                    break
            
            # Suggest category based on keywords
            category_keywords = {
                'Electronics': ['phone', 'laptop', 'computer', 'tablet', 'tv', 'camera'],
                'Fashion': ['dress', 'shirt', 'shoes', 'bag', 'watch', 'clothes'],
                'Automotive': ['car', 'vehicle', 'motorcycle', 'parts', 'tire'],
                'Home & Garden': ['furniture', 'bed', 'table', 'chair', 'garden'],
                'Services': ['repair', 'cleaning', 'plumber', 'electrician', 'painter']
            }
            
            for category, keywords in category_keywords.items():
                if any(keyword in query_lower for keyword in keywords):
                    analysis['category_suggested'] = category
                    break
            
            # Detect price-related queries
            if any(word in query_lower for word in ['cheap', 'affordable', 'budget', 'expensive', 'premium']):
                if any(word in query_lower for word in ['cheap', 'affordable', 'budget']):
                    analysis['price_range_suggested'] = 'low'
                else:
                    analysis['price_range_suggested'] = 'high'
            
            return analysis
            
        except Exception as e:
            logger.error(f"Query analysis error: {str(e)}")
            return {'query_type': 'general', 'intent': 'search'}
    
    def generate_search_suggestions(self, query, analysis):
        """
        ENHANCED: Generate helpful search suggestions
        """
        try:
            suggestions = []
            
            # Category-based suggestions
            if analysis.get('category_suggested'):
                suggestions.append(f"Browse all {analysis['category_suggested']} items")
            
            # Brand-based suggestions
            if analysis.get('brand_mentioned'):
                suggestions.append(f"All {analysis['brand_mentioned']} products")
            
            # Query refinement suggestions
            query_words = query.split()
            if len(query_words) > 1:
                # Suggest individual words
                for word in query_words:
                    if len(word) > 3:
                        suggestions.append(f"Search for '{word}' only")
            
            # Popular related searches (would be based on analytics)
            related_terms = {
                'phone': ['smartphone', 'mobile phone', 'iPhone', 'Samsung'],
                'laptop': ['computer', 'notebook', 'MacBook', 'gaming laptop'],
                'shoes': ['sneakers', 'boots', 'sandals', 'Nike shoes'],
                'car': ['vehicle', 'automobile', 'Toyota', 'Honda']
            }
            
            for term, related in related_terms.items():
                if term in query.lower():
                    suggestions.extend(related[:2])  # Add top 2 related terms
            
            # Remove duplicates and limit
            unique_suggestions = []
            for suggestion in suggestions:
                if suggestion not in unique_suggestions and suggestion.lower() != query.lower():
                    unique_suggestions.append(suggestion)
            
            return unique_suggestions[:5]  # Top 5 suggestions
            
        except Exception as e:
            logger.error(f"Search suggestions error: {str(e)}")
            return []
    
    def generate_cache_key(self, query, filters, limit, user_location):
        """
        Generate cache key for search results
        """
        try:
            key_parts = [
                'search',
                query[:50],  # Limit query length
                str(limit),
                json.dumps(filters or {}, sort_keys=True),
                json.dumps(user_location or {}, sort_keys=True)
            ]
            
            cache_key = '_'.join(key_parts)
            # Clean key for cache compatibility
            cache_key = re.sub(r'[^\w\-_]', '_', cache_key)
            return cache_key[:200]  # Limit key length
            
        except Exception as e:
            logger.error(f"Cache key generation error: {str(e)}")
            return f"search_{hash(query)}_{limit}"


class CategorySearchEngine:
    """
    ENHANCED: Specialized engine for category-based searches
    """
    
    def search_by_category(self, category_name, limit=8, filters=None):
        """
        ENHANCED: Search within specific category
        """
        try:
            logger.info(f"🗂️ Category search: '{category_name}'")
            
            # Find category
            category = Category.objects.filter(
                Q(name__iexact=category_name) | 
                Q(slug__iexact=category_name) |
                Q(name__icontains=category_name),
                is_active=True
            ).first()
            
            if not category:
                return {'products': [], 'services': [], 'total': 0, 'category': None}
            
            # Search within category
            products = Products.objects.filter(
                category=category,
                product_status='published'
            ).select_related('user', 'country', 'state', 'city')
            
            services = Services.objects.filter(
                category=category,
                service_status='published'
            ).select_related('user', 'country', 'state', 'city')
            
            # Apply filters if provided
            if filters:
                products = self.apply_category_filters(products, filters, 'product')
                services = self.apply_category_filters(services, filters, 'service')
            
            # Add ranking annotations
            products = products.annotate(
                avg_rating=Coalesce(Avg('productreview__rating'), Value(0.0)),
                business_score=Case(
                    When(is_promoted=True, then=Value(100)),
                    When(is_featured=True, then=Value(50)),
                    default=Value(0)
                )
            ).order_by('-business_score', '-avg_rating', '-views_count', '-created_at')
            
            services = services.annotate(
                avg_rating=Coalesce(Avg('servicereview__rating'), Value(0.0)),
                business_score=Case(
                    When(is_promoted=True, then=Value(100)),
                    When(is_featured=True, then=Value(50)),
                    default=Value(0)
                )
            ).order_by('-business_score', '-avg_rating', '-contacts_count', '-created_at')
            
            # Get results
            products_list = list(products[:limit//2 + 2])
            services_list = list(services[:limit//2 + 2])
            
            return {
                'products': products_list,
                'services': services_list,
                'total': len(products_list) + len(services_list),
                'category': category
            }
            
        except Exception as e:
            logger.error(f"Category search error: {str(e)}")
            return {'products': [], 'services': [], 'total': 0, 'category': None}
    
    def apply_category_filters(self, queryset, filters, item_type):
        """
        Apply filters within category search
        """
        try:
            # Price range
            min_price = filters.get('min_price')
            max_price = filters.get('max_price')
            
            if min_price is not None:
                price_field = 'product_price' if item_type == 'product' else 'starting_price'
                queryset = queryset.filter(**{f'{price_field}__gte': min_price})
            
            if max_price is not None:
                price_field = 'product_price' if item_type == 'product' else 'starting_price'
                queryset = queryset.filter(**{f'{price_field}__lte': max_price})
            
            # Location
            if filters.get('state_id'):
                queryset = queryset.filter(state_id=filters['state_id'])
            
            if filters.get('city_id'):
                queryset = queryset.filter(city_id=filters['city_id'])
            
            return queryset
            
        except Exception as e:
            logger.error(f"Category filter error: {str(e)}")
            return queryset


# Main functions for views
def enhanced_search_database(query, filters=None, limit=8, user_location=None):
    """
    ENHANCED: Main search function with advanced features
    """
    try:
        search_engine = AdvancedSearchEngine()
        results = search_engine.search_products_and_services(
            query, filters, limit, user_location
        )
        
        # Combine products and services for unified result
        combined_results = []
        combined_results.extend(results['products'])
        combined_results.extend(results['services'])
        
        return combined_results
        
    except Exception as e:
        logger.error(f"Enhanced database search error: {str(e)}")
        return []


def search_by_category_enhanced(category_name, limit=8, filters=None):
    """
    ENHANCED: Category search with advanced features
    """
    try:
        category_engine = CategorySearchEngine()
        results = category_engine.search_by_category(category_name, limit, filters)
        
        # Combine for backward compatibility
        combined_results = []
        combined_results.extend(results['products'])
        combined_results.extend(results['services'])
        
        return combined_results
        
    except Exception as e:
        logger.error(f"Enhanced category search error: {str(e)}")
        return []


# Export functions
__all__ = [
    'AdvancedSearchEngine',
    'CategorySearchEngine', 
    'enhanced_search_database',
    'search_by_category_enhanced'
]