# ai_chatbot/utils.py
import json
import logging
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from decimal import Decimal

from django.db import models
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Avg, Count, Sum
from django.core.exceptions import ValidationError

from .models import (
    ChatSession, ChatMessage, SearchQuery, SearchResult,
    UserFeedback, ChatAnalytics, BotConfiguration
)

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatSessionManager:
    """Manages chat sessions and related operations"""
    
    def __init__(self):
        self.session_timeout = getattr(settings, 'CHATBOT_SESSION_TIMEOUT', 3600)  # 1 hour
        self.max_sessions_per_user = getattr(settings, 'CHATBOT_MAX_SESSIONS_PER_USER', 10)
    
    def generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = str(int(datetime.now().timestamp()))
        random_part = str(uuid.uuid4())[:8]
        return f"chat_{timestamp}_{random_part}"
    
    async def create_session(
        self, 
        user: Optional[User] = None,
        ip_address: str = '',
        user_agent: str = '',
        device_info: Dict = None,
        location_context: Dict = None
    ) -> ChatSession:
        """Create new chat session"""
        try:
            session_data = {
                'session_id': self.generate_session_id(),
                'ip_address': ip_address,
                'user_agent': user_agent[:500] if user_agent else '',
                'device_info': device_info or {},
                'location_context': location_context or {},
                'status': 'active'
            }
            
            if user:
                session_data['user'] = user
                # Clean up old sessions for authenticated users
                await self._cleanup_old_sessions(user)
            
            session = await ChatSession.objects.acreate(**session_data)
            logger.info(f"Created new chat session: {session.session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating chat session: {str(e)}")
            raise
    
    async def get_session(self, session_id: str, user: Optional[User] = None) -> Optional[ChatSession]:
        """Get existing session"""
        try:
            query = Q(id=session_id) | Q(session_id=session_id)
            if user:
                query &= Q(user=user)
            
            session = await ChatSession.objects.select_related('user').aget(
                query, status='active'
            )
            
            # Update last activity
            session.last_activity = timezone.now()
            await session.asave(update_fields=['last_activity'])
            
            return session
            
        except ChatSession.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting chat session: {str(e)}")
            return None
    
    async def end_session(self, session_id: str) -> bool:
        """End chat session"""
        try:
            session = await ChatSession.objects.aget(
                Q(id=session_id) | Q(session_id=session_id)
            )
            session.status = 'ended'
            await session.asave(update_fields=['status'])
            logger.info(f"Ended chat session: {session.session_id}")
            return True
        except ChatSession.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error ending session: {str(e)}")
            return False
    
    async def _cleanup_old_sessions(self, user: User):
        """Clean up old sessions for user"""
        try:
            # Get user's sessions ordered by last activity
            sessions = ChatSession.objects.filter(user=user).order_by('-last_activity')
            
            # Keep only the most recent sessions
            old_sessions = sessions[self.max_sessions_per_user:]
            
            for session in old_sessions:
                session.status = 'ended'
            
            await ChatSession.objects.abulk_update(old_sessions, ['status'])
            
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {str(e)}")
    
    def is_session_expired(self, session: ChatSession) -> bool:
        """Check if session is expired"""
        if not session.last_activity:
            return False
        
        time_diff = timezone.now() - session.last_activity
        return time_diff.total_seconds() > self.session_timeout


class ChatAnalyticsManager:
    """Manages analytics and metrics for the chatbot"""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
    
    async def record_interaction(self, analytics_data: Dict[str, Any]):
        """Record user interaction for analytics"""
        try:
            today = timezone.now().date()
            
            # Get or create today's analytics record
            analytics, created = await ChatAnalytics.objects.aget_or_create(
                date=today,
                defaults={
                    'total_sessions': 0,
                    'total_messages': 0,
                    'unique_users': 0,
                    'anonymous_users': 0,
                    'total_searches': 0,
                    'successful_searches': 0,
                    'average_response_time': 0.0,
                    'positive_feedback': 0,
                    'negative_feedback': 0,
                    'average_rating': 0.0
                }
            )
            
            # Update metrics
            if analytics_data.get('new_session'):
                analytics.total_sessions += 1
                if analytics_data.get('user_id'):
                    analytics.unique_users += 1
                else:
                    analytics.anonymous_users += 1
            
            if analytics_data.get('new_message'):
                analytics.total_messages += 1
            
            if analytics_data.get('search_performed'):
                analytics.total_searches += 1
                if analytics_data.get('search_successful'):
                    analytics.successful_searches += 1
            
            # Update response time (rolling average)
            if analytics_data.get('response_time'):
                current_avg = analytics.average_response_time
                new_time = analytics_data['response_time']
                analytics.average_response_time = (current_avg + new_time) / 2
            
            await analytics.asave()
            
        except Exception as e:
            logger.error(f"Error recording interaction: {str(e)}")
    
    async def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """Get daily statistics for the last N days"""
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            analytics = ChatAnalytics.objects.filter(
                date__range=[start_date, end_date]
            ).order_by('-date')
            
            stats = []
            async for record in analytics:
                stats.append({
                    'date': record.date.isoformat(),
                    'sessions': record.total_sessions,
                    'messages': record.total_messages,
                    'users': record.unique_users + record.anonymous_users,
                    'searches': record.total_searches,
                    'avg_response_time': record.average_response_time,
                    'satisfaction_rate': self._calculate_satisfaction_rate(record)
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting daily stats: {str(e)}")
            return []
    
    def _calculate_satisfaction_rate(self, analytics: ChatAnalytics) -> float:
        """Calculate satisfaction rate from feedback"""
        total_feedback = analytics.positive_feedback + analytics.negative_feedback
        if total_feedback == 0:
            return 0.0
        return (analytics.positive_feedback / total_feedback) * 100

class MessageProcessor:
    """Enhanced message processor with better intent detection for product searches"""
    
    def __init__(self):
        # Product search keywords - enhanced list
        self.product_keywords = [
            'iphone', 'samsung', 'phone', 'smartphone', 'mobile', 'cell phone',
            'laptop', 'computer', 'desktop', 'tablet', 'ipad',
            'tv', 'television', 'smart tv', 'led tv',
            'camera', 'digital camera', 'webcam',
            'headphones', 'earbuds', 'airpods', 'speaker', 'bluetooth speaker',
            'watch', 'smartwatch', 'apple watch',
            'gaming', 'console', 'xbox', 'playstation', 'nintendo',
            'macbook', 'windows laptop', 'chromebook',
            'android', 'ios',
            'keyboard', 'mouse', 'monitor', 'screen',
            'printer', 'scanner', 'router', 'modem',
            'charger', 'cable', 'usb cable', 'power bank',
            'case', 'phone case', 'laptop bag',
            'memory card', 'usb drive', 'hard drive', 'ssd',
            'graphics card', 'processor', 'cpu', 'ram', 'motherboard'
        ]
        
        # Purchase intent keywords
        self.purchase_keywords = [
            'buy', 'purchase', 'get', 'need', 'want', 'looking for', 'find', 'shop',
            'order', 'price', 'cost', 'how much', 'cheap', 'expensive', 'affordable',
            'deal', 'offer', 'discount', 'sale', 'store', 'market', 'vendor',
            'sell', 'selling', 'available', 'stock'
        ]
        
        # Service keywords
        self.service_keywords = [
            'repair', 'fix', 'service', 'maintenance', 'installation', 'setup',
            'delivery', 'shipping', 'support', 'help', 'assistance', 'consultation',
            'training', 'tutorial', 'guide', 'advice', 'recommendation'
        ]
    
    def extract_intent(self, message: str) -> Dict[str, Any]:
        """
        Extract intent from user message with improved product detection
        """
        try:
            message_lower = message.lower().strip()
            logger.info(f"Extracting intent from: '{message_lower}'")
            
            # Initialize result
            result = {
                'primary_intent': 'general_query',
                'all_intents': [],
                'confidence': 0.3,
                'entities': []
            }
            
            # Check for direct product matches
            product_matches = [keyword for keyword in self.product_keywords if keyword in message_lower]
            purchase_matches = [keyword for keyword in self.purchase_keywords if keyword in message_lower]
            service_matches = [keyword for keyword in self.service_keywords if keyword in message_lower]
            
            # Calculate scores
            product_score = len(product_matches) * 1.0
            purchase_score = len(purchase_matches) * 0.8
            service_score = len(service_matches) * 0.9
            
            # Special handling for specific product models like "iPhone 15"
            if any(brand in message_lower for brand in ['iphone', 'samsung', 'macbook', 'ipad']):
                product_score += 2.0  # Boost score for specific brand mentions
            
            # Check for model numbers or versions
            import re
            if re.search(r'\b\w+\s+\d+\b', message_lower):  # Pattern like "iPhone 15", "Galaxy S23"
                product_score += 1.5
            
            logger.info(f"Intent scores - Product: {product_score} (matches: {product_matches}), Purchase: {purchase_score}, Service: {service_score}")
            
            # Determine primary intent
            max_score = max(product_score, purchase_score, service_score)
            
            if product_score >= 1.0 or (product_score > 0 and purchase_score > 0):
                result['primary_intent'] = 'product_search'
                result['confidence'] = min(0.95, 0.6 + (product_score * 0.1))
            elif service_score == max_score and service_score > 0:
                result['primary_intent'] = 'service_request'
                result['confidence'] = min(0.9, 0.5 + (service_score * 0.1))
            elif purchase_score > 0:
                result['primary_intent'] = 'product_search'  # Assume product search for purchase intent
                result['confidence'] = min(0.8, 0.4 + (purchase_score * 0.1))
            else:
                # For short queries that might be product names, assume product search
                if len(message_lower.split()) <= 3 and not any(word in message_lower for word in ['how', 'what', 'why', 'when', 'where', 'hello', 'hi']):
                    result['primary_intent'] = 'product_search'
                    result['confidence'] = 0.7
            
            # Extract entities
            entities = []
            
            # Add product entities
            for match in product_matches:
                entities.append({
                    'type': 'product',
                    'value': match,
                    'confidence': 0.9
                })
            
            # Add purchase intent entities
            for match in purchase_matches:
                entities.append({
                    'type': 'purchase_intent',
                    'value': match,
                    'confidence': 0.8
                })
            
            result['entities'] = entities
            
            logger.info(f"Final intent result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting intent: {str(e)}")
            return {
                'primary_intent': 'product_search',  # Default to product search on error
                'all_intents': [],
                'confidence': 0.6,
                'entities': []
            }
class SearchHelper:
    """Helper functions for search operations"""
    
    @staticmethod
    def build_search_filters(query: str, context: Dict = None) -> Dict[str, Any]:
        """Build search filters from query and context"""
        filters = {
            'query': query.strip(),
            'categories': [],
            'price_range': None,
            'location': None,
            'condition': None,
            'brand': None
        }
        
        query_lower = query.lower()
        
        # Extract category hints
        category_keywords = {
            'electronics': ['phone', 'laptop', 'computer', 'tablet', 'tv', 'camera'],
            'fashion': ['clothes', 'dress', 'shirt', 'shoes', 'bag', 'fashion'],
            'home': ['furniture', 'kitchen', 'bedroom', 'living room', 'decoration'],
            'automotive': ['car', 'vehicle', 'auto', 'motorcycle', 'spare parts'],
            'services': ['cleaning', 'repair', 'maintenance', 'delivery', 'installation']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                filters['categories'].append(category)
        
        # Extract price hints
        if 'cheap' in query_lower or 'budget' in query_lower:
            filters['price_range'] = {'max': 50000}  # NGN
        elif 'expensive' in query_lower or 'premium' in query_lower:
            filters['price_range'] = {'min': 100000}  # NGN
        
        # Extract condition hints
        if 'new' in query_lower:
            filters['condition'] = 'new'
        elif 'used' in query_lower or 'second hand' in query_lower:
            filters['condition'] = 'used'
        
        # Add context filters
        if context:
            if context.get('location_context'):
                filters['location'] = context['location_context']
            
            if context.get('user_preferences', {}).get('preferred_brands'):
                filters['brand'] = context['user_preferences']['preferred_brands']
        
        return filters
    
    @staticmethod
    def calculate_relevance_score(item: Dict, query: str, filters: Dict = None) -> float:
        """Calculate relevance score for search result"""
        score = 0.0
        query_words = query.lower().split()
        
        # Title match (40% weight)
        title = item.get('name', '').lower()
        title_matches = sum(1 for word in query_words if word in title)
        title_score = (title_matches / len(query_words)) * 0.4 if query_words else 0
        score += title_score
        
        # Description match (30% weight)
        description = item.get('description', '').lower()
        desc_matches = sum(1 for word in query_words if word in description)
        desc_score = (desc_matches / len(query_words)) * 0.3 if query_words else 0
        score += desc_score
        
        # Category match (20% weight)
        if filters and filters.get('categories'):
            item_category = item.get('category', {}).get('name', '').lower()
            for filter_cat in filters['categories']:
                if filter_cat.lower() in item_category:
                    score += 0.2
                    break
        
        # Rating boost (10% weight)
        rating = item.get('rating', {}).get('average', 0)
        if rating > 0:
            score += (rating / 5.0) * 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    @staticmethod
    def format_search_results(results: List[Dict], query: str, result_type: str = 'product') -> Dict[str, Any]:
        """Format search results for response"""
        formatted_results = {
            'query': query,
            'result_type': result_type,
            'total_found': len(results),
            'results': []
        }
        
        for result in results:
            formatted_result = {
                'id': result.get('id'),
                'title': result.get('name', 'Unknown'),
                'description': result.get('description', ''),
                'price': result.get('formatted_price', 'Price not available'),
                'image': result.get('image'),
                'location': result.get('location', {}).get('full_location', 'Unknown'),
                'rating': result.get('rating', {}),
                'url': result.get('url', ''),
                'relevance_score': result.get('relevance_score', 0)
            }
            
            if result_type == 'service':
                formatted_result.update({
                    'provider': result.get('provider', {}).get('name', 'Unknown'),
                    'price_type': result.get('price_type', 'Fixed')
                })
            else:
                formatted_result.update({
                    'seller': result.get('seller', {}).get('name', 'Unknown'),
                    'condition': result.get('condition', 'Unknown')
                })
            
            formatted_results['results'].append(formatted_result)
        
        # Sort by relevance score
        formatted_results['results'].sort(
            key=lambda x: x['relevance_score'], 
            reverse=True
        )
        
        return formatted_results


class CacheManager:
    """Manages caching for the chatbot"""
    
    def __init__(self):
        self.default_timeout = 1800  # 30 minutes
        self.prefix = 'chatbot:'
    
    def get_cache_key(self, key_type: str, identifier: str, **kwargs) -> str:
        """Generate cache key"""
        key_parts = [self.prefix, key_type, identifier]
        
        # Add additional parameters
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{v}")
        
        # Create hash of the key if it's too long
        key_str = ':'.join(str(part) for part in key_parts)
        if len(key_str) > 200:
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            return f"{self.prefix}{key_type}:{key_hash}"
        
        return key_str
    
    def cache_search_results(self, query: str, results: Dict, timeout: int = None) -> bool:
        """Cache search results"""
        try:
            cache_key = self.get_cache_key('search', query)
            cache.set(cache_key, results, timeout or self.default_timeout)
            return True
        except Exception as e:
            logger.error(f"Error caching search results: {str(e)}")
            return False
    
    def get_cached_search_results(self, query: str) -> Optional[Dict]:
        """Get cached search results"""
        try:
            cache_key = self.get_cache_key('search', query)
            return cache.get(cache_key)
        except Exception as e:
            logger.error(f"Error getting cached search results: {str(e)}")
            return None
    
    def cache_ai_response(self, prompt_hash: str, response: Dict, timeout: int = None) -> bool:
        """Cache AI response"""
        try:
            cache_key = self.get_cache_key('ai_response', prompt_hash)
            cache.set(cache_key, response, timeout or self.default_timeout)
            return True
        except Exception as e:
            logger.error(f"Error caching AI response: {str(e)}")
            return False
    
    def get_cached_ai_response(self, prompt_hash: str) -> Optional[Dict]:
        """Get cached AI response"""
        try:
            cache_key = self.get_cache_key('ai_response', prompt_hash)
            return cache.get(cache_key)
        except Exception as e:
            logger.error(f"Error getting cached AI response: {str(e)}")
            return None
    
    def invalidate_cache(self, key_pattern: str) -> bool:
        """Invalidate cache by pattern"""
        try:
            # This is a simplified version - implement based on your cache backend
            cache.delete_pattern(f"{self.prefix}{key_pattern}*")
            return True
        except Exception as e:
            logger.error(f"Error invalidating cache: {str(e)}")
            return False


class ConfigurationManager:
    """Manages bot configuration"""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self.config_cache = {}
    
    def get_config(self, key: str, default: Any = None, use_cache: bool = True) -> Any:
        """Get configuration value"""
        if use_cache and key in self.config_cache:
            return self.config_cache[key]
        
        try:
            config = BotConfiguration.objects.get(key=key, is_active=True)
            value = config.value
            
            if use_cache:
                self.config_cache[key] = value
            
            return value
            
        except BotConfiguration.DoesNotExist:
            return default
        except Exception as e:
            logger.error(f"Error getting configuration {key}: {str(e)}")
            return default
    
    def set_config(self, key: str, value: Any, description: str = '') -> bool:
        """Set configuration value"""
        try:
            BotConfiguration.set_config(key, value, description)
            
            # Update cache
            self.config_cache[key] = value
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting configuration {key}: {str(e)}")
            return False
    
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all active configurations"""
        try:
            configs = BotConfiguration.objects.filter(is_active=True)
            return {config.key: config.value for config in configs}
        except Exception as e:
            logger.error(f"Error getting all configurations: {str(e)}")
            return {}


class SecurityUtils:
    """Security utilities for the chatbot"""
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input"""
        if not text:
            return ''
        
        # Remove potentially harmful characters
        import re
        # Allow alphanumeric, spaces, and common punctuation
        sanitized = re.sub(r'[^\w\s\.\,\!\?\-\"\'\(\)\[\]\{\}]', '', text)
        
        # Limit length
        return sanitized[:2000]
    
    @staticmethod
    def validate_file_upload(file, allowed_types: List[str], max_size_mb: int = 10) -> Dict[str, Any]:
        """Validate uploaded file"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'file_info': {}
        }
        
        if not file:
            validation_result['is_valid'] = False
            validation_result['errors'].append('No file provided')
            return validation_result
        
        # Check file type
        if file.content_type not in allowed_types:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f'Invalid file type: {file.content_type}')
        
        # Check file size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file.size > max_size_bytes:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f'File too large: {file.size} bytes (max: {max_size_bytes})')
        
        # Get file info
        validation_result['file_info'] = {
            'name': file.name,
            'size': file.size,
            'content_type': file.content_type
        }
        
        return validation_result
    
    @staticmethod
    def rate_limit_check(identifier: str, limit: int = 60, window: int = 3600) -> Dict[str, Any]:
        """Check rate limit for identifier"""
        cache_key = f"rate_limit:{identifier}"
        
        try:
            current_count = cache.get(cache_key, 0)
            
            if current_count >= limit:
                return {
                    'allowed': False,
                    'current_count': current_count,
                    'limit': limit,
                    'window': window
                }
            
            # Increment counter
            cache.set(cache_key, current_count + 1, window)
            
            return {
                'allowed': True,
                'current_count': current_count + 1,
                'limit': limit,
                'window': window
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return {'allowed': True, 'current_count': 0, 'limit': limit, 'window': window}


class ResponseFormatter:
    """Formats responses for different output types"""
    
    @staticmethod
    def format_product_list(products: List[Dict], max_items: int = 5) -> str:
        """Format product list for text response"""
        if not products:
            return "No products found."
        
        formatted_text = f"Found {len(products)} product(s):\n\n"
        
        for i, product in enumerate(products[:max_items], 1):
            formatted_text += f"{i}. **{product.get('name', 'Unknown Product')}**\n"
            formatted_text += f"   💰 Price: {product.get('formatted_price', 'N/A')}\n"
            formatted_text += f"   📍 Location: {product.get('location', {}).get('full_location', 'N/A')}\n"
            
            if product.get('rating', {}).get('average'):
                stars = '⭐' * int(product['rating']['average'])
                formatted_text += f"   {stars} ({product['rating']['average']}/5)\n"
            
            if product.get('description'):
                desc = product['description'][:100] + '...' if len(product['description']) > 100 else product['description']
                formatted_text += f"   📝 {desc}\n"
            
            formatted_text += "\n"
        
        if len(products) > max_items:
            formatted_text += f"... and {len(products) - max_items} more items.\n"
        
        return formatted_text
    
    @staticmethod
    def format_service_list(services: List[Dict], max_items: int = 5) -> str:
        """Format service list for text response"""
        if not services:
            return "No services found."
        
        formatted_text = f"Found {len(services)} service(s):\n\n"
        
        for i, service in enumerate(services[:max_items], 1):
            formatted_text += f"{i}. **{service.get('name', 'Unknown Service')}**\n"
            formatted_text += f"   💼 Provider: {service.get('provider', {}).get('name', 'N/A')}\n"
            formatted_text += f"   💰 Price: {service.get('price_range', 'Contact for pricing')}\n"
            formatted_text += f"   📍 Location: {service.get('location', {}).get('full_location', 'N/A')}\n"
            
            if service.get('rating', {}).get('average'):
                stars = '⭐' * int(service['rating']['average'])
                formatted_text += f"   {stars} ({service['rating']['average']}/5)\n"
            
            if service.get('description'):
                desc = service['description'][:100] + '...' if len(service['description']) > 100 else service['description']
                formatted_text += f"   📝 {desc}\n"
            
            formatted_text += "\n"
        
        if len(services) > max_items:
            formatted_text += f"... and {len(services) - max_items} more services.\n"
        
        return formatted_text
    
    @staticmethod
    def format_error_message(error_type: str, details: str = '') -> str:
        """Format error message for user"""
        error_messages = {
            'search_failed': "I couldn't perform the search right now. Please try again in a moment.",
            'no_results': "I couldn't find any results for your search. Try different keywords or check the spelling.",
            'api_error': "I'm having trouble connecting to external services. Please try again later.",
            'validation_error': f"There was an issue with your request: {details}",
            'rate_limit': "You're sending requests too quickly. Please wait a moment and try again.",
            'file_error': f"There was an issue with your file: {details}",
            'generic': "Something went wrong. Please try again or contact support if the issue persists."
        }
        
        return error_messages.get(error_type, error_messages['generic'])


# Utility functions
def hash_prompt(prompt: str) -> str:
    """Create hash of prompt for caching"""
    return hashlib.md5(prompt.encode('utf-8')).hexdigest()


def extract_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """Extract location from IP address (placeholder)"""
    # This is a placeholder - integrate with a real geolocation service
    return {
        'country': 'Nigeria',
        'state': 'Unknown',
        'city': 'Unknown',
        'timezone': 'Africa/Lagos',
        'currency': 'NGN'
    }


def format_price(amount: Union[int, float, Decimal], currency: str = 'NGN') -> str:
    """Format price with currency"""
    try:
        if currency == 'NGN':
            symbol = '₦'
        elif currency == 'USD':
            symbol = '$'
        elif currency == 'EUR':
            symbol = '€'
        elif currency == 'GBP':
            symbol = '£'
        else:
            symbol = currency + ' '
        
        # Format with thousands separators
        if isinstance(amount, (int, float)):
            formatted_amount = f"{amount:,.2f}"
        else:  # Decimal
            formatted_amount = f"{float(amount):,.2f}"
        
        return f"{symbol}{formatted_amount}"
        
    except Exception as e:
        logger.error(f"Error formatting price: {str(e)}")
        return f"{currency} {amount}"


def parse_price_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Parse price information from text"""
    import re
    
    # Price patterns
    patterns = [
        (r'₦\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', 'NGN'),
        (r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', 'USD'),
        (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*naira', 'NGN'),
        (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*dollars?', 'USD'),
    ]
    
    for pattern, currency in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
                return {
                    'amount': amount,
                    'currency': currency,
                    'formatted': format_price(amount, currency),
                    'original_text': match.group(0)
                }
            except ValueError:
                continue
    
    return None


def clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ''
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove special characters but keep basic punctuation
    import re
    text = re.sub(r'[^\w\s\.\,\!\?\-\"\'\(\)]', '', text)
    
    return text.strip()


def generate_session_token() -> str:
    """Generate secure session token"""
    import secrets
    return secrets.token_urlsafe(32)


def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def get_user_timezone(location_context: Dict = None) -> str:
    """Get user timezone from location context"""
    if location_context and location_context.get('timezone'):
        return location_context['timezone']
    
    # Default to Nigerian timezone
    return 'Africa/Lagos'


def format_datetime_for_user(dt: datetime, timezone_str: str = None) -> str:
    """Format datetime for user display"""
    try:
        if timezone_str:
            import pytz
            user_tz = pytz.timezone(timezone_str)
            dt = dt.astimezone(user_tz)
        
        # Format as "Today 3:45 PM" or "Yesterday 10:30 AM" or "Dec 15, 2023 2:15 PM"
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        
        if dt.date() == now.date():
            return dt.strftime("Today %I:%M %p")
        elif dt.date() == (now - timedelta(days=1)).date():
            return dt.strftime("Yesterday %I:%M %p")
        else:
            return dt.strftime("%b %d, %Y %I:%M %p")
            
    except Exception as e:
        logger.error(f"Error formatting datetime: {str(e)}")
        return dt.strftime("%Y-%m-%d %H:%M")


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers"""
    from math import radians, cos, sin, asin, sqrt
    
    # Haversine formula
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r


class ErrorHandler:
    """Centralized error handling for the chatbot"""
    
    @staticmethod
    def handle_exception(e: Exception, context: str = '') -> Dict[str, Any]:
        """Handle exceptions and return standardized error response"""
        error_type = type(e).__name__
        error_message = str(e)
        
        logger.error(f"Error in {context}: {error_type}: {error_message}")
        
        # Map exception types to user-friendly messages
        user_messages = {
            'ValidationError': 'Please check your input and try again.',
            'PermissionError': 'You don\'t have permission to perform this action.',
            'FileNotFoundError': 'The requested file was not found.',
            'ConnectionError': 'Unable to connect to external services. Please try again later.',
            'TimeoutError': 'The request timed out. Please try again.',
            'ValueError': 'Invalid input provided. Please check your data.',
            'KeyError': 'Missing required information. Please provide complete details.',
        }
        
        user_message = user_messages.get(error_type, 
            'An unexpected error occurred. Please try again or contact support.')
        
        return {
            'success': False,
            'error_type': error_type,
            'error_message': error_message,
            'user_message': user_message,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }


class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_search_query(query: str) -> Dict[str, Any]:
        """Validate search query"""
        result = {'is_valid': True, 'errors': [], 'warnings': []}
        
        if not query or not query.strip():
            result['is_valid'] = False
            result['errors'].append('Search query cannot be empty')
            return result
        
        if len(query) > 200:
            result['warnings'].append('Search query is very long, consider shortening it')
        
        if len(query) < 2:
            result['warnings'].append('Search query is very short, consider adding more details')
        
        # Check for potential SQL injection or XSS
        dangerous_patterns = ['<script', 'javascript:', 'SELECT ', 'DROP ', 'DELETE ']
        for pattern in dangerous_patterns:
            if pattern.lower() in query.lower():
                result['is_valid'] = False
                result['errors'].append('Query contains potentially harmful content')
                break
        
        return result
    
    @staticmethod
    def validate_location_data(location: Dict) -> Dict[str, Any]:
        """Validate location data"""
        result = {'is_valid': True, 'errors': []}
        
        required_fields = ['latitude', 'longitude']
        for field in required_fields:
            if field not in location:
                result['is_valid'] = False
                result['errors'].append(f'Missing required field: {field}')
        
        # Validate coordinate ranges
        if 'latitude' in location:
            lat = location['latitude']
            if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
                result['is_valid'] = False
                result['errors'].append('Invalid latitude value')
        
        if 'longitude' in location:
            lon = location['longitude']
            if not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
                result['is_valid'] = False
                result['errors'].append('Invalid longitude value')
        
        return result


class PerformanceMonitor:
    """Monitor chatbot performance"""
    
    def __init__(self):
        self.start_time = None
        self.metrics = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        self.start_time = datetime.now()
        self.metrics[operation] = {'start_time': self.start_time}
    
    def end_timer(self, operation: str) -> float:
        """End timing and return duration"""
        if operation not in self.metrics:
            return 0.0
        
        end_time = datetime.now()
        start_time = self.metrics[operation]['start_time']
        duration = (end_time - start_time).total_seconds()
        
        self.metrics[operation].update({
            'end_time': end_time,
            'duration': duration
        })
        
        return duration
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics"""
        return self.metrics.copy()
    
    @staticmethod
    def log_performance(operation: str, duration: float, additional_info: Dict = None):
        """Log performance metrics"""
        log_data = {
            'operation': operation,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }
        
        if additional_info:
            log_data.update(additional_info)
        
        logger.info(f"Performance: {operation} took {duration:.3f}s", extra=log_data)


# Database utilities
async def get_or_create_async(model_class, defaults=None, **kwargs):
    """Async version of get_or_create"""
    try:
        instance = await model_class.objects.aget(**kwargs)
        return instance, False
    except model_class.DoesNotExist:
        create_kwargs = kwargs.copy()
        if defaults:
            create_kwargs.update(defaults)
        instance = await model_class.objects.acreate(**create_kwargs)
        return instance, True


async def bulk_create_async(model_class, objects_list, batch_size=100):
    """Async bulk create with batching"""
    try:
        total_created = 0
        for i in range(0, len(objects_list), batch_size):
            batch = objects_list[i:i + batch_size]
            await model_class.objects.abulk_create(batch, ignore_conflicts=True)
            total_created += len(batch)
        
        return total_created
    except Exception as e:
        logger.error(f"Error in bulk create: {str(e)}")
        return 0


# Context managers
class TimedOperation:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        logger.debug(f"Starting operation: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        self.duration = (end_time - self.start_time).total_seconds()
        
        if exc_type is None:
            logger.debug(f"Completed operation: {self.operation_name} in {self.duration:.3f}s")
        else:
            logger.error(f"Operation failed: {self.operation_name} after {self.duration:.3f}s")
        
        # Log performance
        PerformanceMonitor.log_performance(self.operation_name, self.duration)


# Decorator utilities
def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Async retry decorator"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}")
            
            raise last_exception
        
        return wrapper
    return decorator


def log_function_call(include_args: bool = False):
    """Decorator to log function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            log_msg = f"Calling function: {func_name}"
            
            if include_args:
                log_msg += f" with args={args}, kwargs={kwargs}"
            
            logger.debug(log_msg)
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Function {func_name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"Function {func_name} failed: {str(e)}")
                raise
        
        return wrapper
    return decorator


# Constants and configuration
DEFAULT_SEARCH_RESULTS_LIMIT = 10
DEFAULT_CONVERSATION_HISTORY_LIMIT = 20
DEFAULT_CACHE_TIMEOUT = 1800  # 30 minutes
MAX_MESSAGE_LENGTH = 2000
MAX_FILE_SIZE_MB = 10
SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
SUPPORTED_AUDIO_TYPES = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm']

# Nigerian-specific data
NIGERIAN_STATES = [
    'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue',
    'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu',
    'Federal Capital Territory', 'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano',
    'Katsina', 'Kebbi', 'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger',
    'Ogun', 'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba',
    'Yobe', 'Zamfara'
]

MAJOR_NIGERIAN_CITIES = [
    'Lagos', 'Abuja', 'Kano', 'Ibadan', 'Port Harcourt', 'Benin City',
    'Maiduguri', 'Zaria', 'Aba', 'Jos', 'Ilorin', 'Oyo', 'Enugu',
    'Abeokuta', 'Kaduna', 'Warri', 'Sokoto', 'Ogbomoso', 'Akure', 'Osogbo'
]

# Export all utilities
__all__ = [
    'ChatSessionManager', 'ChatAnalyticsManager', 'MessageProcessor',
    'SearchHelper', 'CacheManager', 'ConfigurationManager', 'SecurityUtils',
    'ResponseFormatter', 'ErrorHandler', 'DataValidator', 'PerformanceMonitor',
    'TimedOperation', 'async_retry', 'log_function_call',
    'hash_prompt', 'extract_location_from_ip', 'format_price', 'parse_price_from_text',
    'clean_text', 'generate_session_token', 'validate_email', 'get_user_timezone',
    'format_datetime_for_user', 'calculate_distance', 'get_or_create_async',
    'bulk_create_async'
]