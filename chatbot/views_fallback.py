# improved_utils.py - Completely refactored utility classes
from django.db.models import Q, Count, Avg, Case, When, IntegerField
from django.core.cache import cache
from django.utils import timezone
from main.models import Products, Services, Category
import re
import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class SmartSearchEngine:
    """
    Optimized search engine with proper database queries and caching
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def smart_search(self, query: str, limit: int = 5) -> Dict:
        """
        Perform intelligent search with relevance scoring and caching
        """
        if not query or len(query.strip()) < 2:
            return {'items': [], 'query': query, 'total_count': 0}
        
        clean_query = self._clean_search_query(query)
        cache_key = f"search:{hash(clean_query)}:{limit}"
        
        # Try cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for query: '{clean_query}'")
            return cached_result
        
        logger.info(f"Searching database for: '{clean_query}'")
        
        # Build optimized database queries
        search_results = self._execute_database_search(clean_query, limit)
        
        # Cache results
        cache.set(cache_key, search_results, self.cache_timeout)
        
        return search_results
    
    def _clean_search_query(self, query: str) -> str:
        """Clean and normalize search query"""
        # Remove special characters
        cleaned = re.sub(r'[^\w\s]', ' ', query)
        
        # Remove very common words that don't help with product search
        stop_words = {
            # Personal pronouns and basic words
            'i', 'me', 'my', 'you', 'your', 'we', 'us', 'our', 'they', 'them', 'their',
            'a', 'an', 'the', 'and', 'or', 'but', 'if', 'so', 'as', 'at', 'be', 'by', 'do', 'he', 'in', 'is', 'it', 'of', 'on', 'to', 'up',
            
            # Shopping/searching intent words
            'need', 'want', 'looking', 'search', 'find', 'buy', 'purchase', 'get', 'acquire', 'obtain', 'seeking', 'hunting',
            'shop', 'shopping', 'browse', 'browsing', 'check', 'checking', 'see', 'seeing', 'view', 'viewing',
            
            # Request/question words
            'show', 'help', 'please', 'can', 'could', 'would', 'should', 'will', 'where', 'what', 'how', 'when', 'why', 'who',
            'tell', 'give', 'provide', 'suggest', 'recommend', 'advise',
            
            # Quantity/quality descriptors (too generic)
            'some', 'any', 'many', 'much', 'few', 'little', 'more', 'most', 'less', 'least', 'all', 'every', 'each',
            'good', 'great', 'best', 'better', 'nice', 'fine', 'ok', 'okay', 'perfect', 'excellent', 'amazing',
            'bad', 'poor', 'worst', 'terrible', 'awful',
            
            # Commercial/business generic terms
            'product', 'products', 'item', 'items', 'thing', 'things', 'stuff', 'goods', 'merchandise',
            'service', 'services', 'business', 'company', 'store', 'shop', 'market', 'marketplace',
            'seller', 'vendor', 'supplier', 'dealer', 'retailer', 'provider',
            
            # Location/delivery terms (too generic without specifics)
            'near', 'nearby', 'close', 'around', 'local', 'here', 'there', 'deliver', 'delivery', 'shipping',
            
            # Price/cost terms (without specific amounts)
            'cheap', 'expensive', 'affordable', 'budget', 'cost', 'price', 'pricing', 'money', 'cash', 'pay', 'payment',
            
            # Time-related generic terms
            'now', 'today', 'tomorrow', 'yesterday', 'soon', 'later', 'before', 'after', 'during', 'while',
            'new', 'old', 'used', 'recent', 'latest', 'current', 'modern', 'vintage',
            
            # Platform/website terms
            'website', 'site', 'online', 'internet', 'web', 'digital', 'app', 'application', 'platform',
            
            # Generic actions
            'use', 'using', 'work', 'working', 'make', 'making', 'take', 'taking', 'put', 'putting',
            'go', 'going', 'come', 'coming', 'try', 'trying', 'test', 'testing',
            
            # Filler words and expressions
            'like', 'just', 'only', 'also', 'even', 'still', 'yet', 'already', 'really', 'very', 'quite', 'pretty',
            'maybe', 'perhaps', 'probably', 'definitely', 'certainly', 'surely', 'obviously',
            'actually', 'basically', 'generally', 'specifically', 'particularly', 'especially',
            
            # Comparative terms (without context)
            'than', 'then', 'same', 'different', 'similar', 'like', 'unlike', 'compare', 'comparison',
            
            # Question starters and conversation terms
            'hello', 'hi', 'hey', 'thanks', 'thank', 'please', 'sorry', 'excuse', 'welcome'
        }
            
        words = [word.lower() for word in cleaned.split() 
                if word.lower() not in stop_words and len(word) >= 2]
        
        return ' '.join(words) if words else query.strip()
    
    def _execute_database_search(self, query: str, limit: int) -> Dict:
        """
        Execute optimized database search with proper relevance scoring
        """
        query_words = query.split()
        
        # Build search filters for products
        product_filters = Q()
        service_filters = Q()
        
        for word in query_words:
            # Products search
            product_filters |= (
                Q(product_name__icontains=word) |
                Q(product_brand__icontains=word) |
                Q(category__name__icontains=word) |
                Q(tags__icontains=word) |
                Q(product_description__icontains=word)
            )
            
            # Services search  
            service_filters |= (
                Q(service_name__icontains=word) |
                Q(provider_name__icontains=word) |
                Q(category__name__icontains=word) |
                Q(tags__icontains=word) |
                Q(service_description__icontains=word)
            )
        
        # Execute queries with annotations for sorting
        products = Products.objects.filter(
            product_filters,
            product_status='published'
        ).select_related(
            'category', 'country', 'state', 'city'
        ).annotate(
            # Relevance scoring using database functions
            relevance_score=Case(
                # Exact name match
                When(product_name__iexact=query, then=1000),
                # Brand match
                When(product_brand__iexact=query, then=900),
                # Name contains query
                When(product_name__icontains=query, then=800),
                # Brand contains query
                When(product_brand__icontains=query, then=700),
                # Category match
                When(category__name__icontains=query, then=600),
                default=100,
                output_field=IntegerField()
            )
        ).order_by('-relevance_score', '-is_promoted', '-is_featured', '-created_at')
        
        services = Services.objects.filter(
            service_filters,
            service_status='published'
        ).select_related(
            'category', 'country', 'state', 'city'
        ).annotate(
            relevance_score=Case(
                When(service_name__iexact=query, then=1000),
                When(provider_name__iexact=query, then=900),
                When(service_name__icontains=query, then=800),
                When(provider_name__icontains=query, then=700),
                When(category__name__icontains=query, then=600),
                default=100,
                output_field=IntegerField()
            )
        ).order_by('-relevance_score', '-is_promoted', '-is_featured', '-created_at')
        
        # Combine and limit results
        combined_results = []
        
        # Add products with type annotation
        for product in products[:limit//2 + 1]:
            combined_results.append({
                'item': product,
                'type': 'product',
                'relevance': product.relevance_score
            })
        
        # Add services with type annotation
        for service in services[:limit//2 + 1]:
            combined_results.append({
                'item': service,
                'type': 'service', 
                'relevance': service.relevance_score
            })
        
        # Sort by relevance and limit
        combined_results.sort(key=lambda x: x['relevance'], reverse=True)
        final_results = combined_results[:limit]
        
        return {
            'items': [result['item'] for result in final_results],
            'query': query,
            'total_count': len(final_results),
            'product_count': len([r for r in final_results if r['type'] == 'product']),
            'service_count': len([r for r in final_results if r['type'] == 'service'])
        }
    
    def search_by_category(self, category_name: str, limit: int = 8) -> Dict:
        """Search products and services by category"""
        try:
            # Find category (case insensitive, cached)
            cache_key = f"category:{category_name.lower()}"
            category = cache.get(cache_key)
            
            if not category:
                category = Category.objects.filter(
                    Q(name__icontains=category_name) | Q(slug__icontains=category_name),
                    is_active=True
                ).first()
                if category:
                    cache.set(cache_key, category, 3600)  # Cache for 1 hour
            
            if not category:
                return {'items': [], 'category': category_name, 'total_count': 0}
            
            # Get items from category
            products = Products.objects.filter(
                category=category,
                product_status='published'
            ).select_related('country', 'state', 'city').order_by(
                '-is_promoted', '-is_featured', '-views_count', '-created_at'
            )[:limit//2]
            
            services = Services.objects.filter(
                category=category,
                service_status='published'
            ).select_related('country', 'state', 'city').order_by(
                '-is_promoted', '-is_featured', '-views_count', '-created_at'
            )[:limit//2]
            
            # Combine results
            all_items = list(products) + list(services)
            
            # Sort by business features and engagement
            all_items.sort(key=lambda obj: (
                getattr(obj, 'is_promoted', False),
                getattr(obj, 'is_featured', False),
                getattr(obj, 'views_count', 0),
                obj.created_at
            ), reverse=True)
            
            return {
                'items': all_items[:limit],
                'category': category.name,
                'total_count': len(all_items),
                'category_obj': category
            }
            
        except Exception as e:
            logger.error(f"Category search error: {e}")
            return {'items': [], 'category': category_name, 'total_count': 0}
    
    def search_by_image_analysis(self, analysis_text: str, limit: int = 4) -> Dict:
        """Search using AI image analysis results"""
        if not analysis_text:
            return {'items': [], 'query': '', 'total_count': 0}
        
        # Extract search terms from analysis
        search_terms = self._extract_search_terms_from_analysis(analysis_text)
        
        if search_terms:
            return self.smart_search(search_terms, limit)
        
        return {'items': [], 'query': analysis_text[:50], 'total_count': 0}
    
    def _extract_search_terms_from_analysis(self, analysis_text: str) -> str:
        """Extract relevant search terms from AI analysis"""
        # Priority product terms
        priority_terms = {
            'phone', 'iphone', 'samsung', 'android', 'smartphone',
            'laptop', 'computer', 'macbook', 'dell', 'hp', 'lenovo',
            'shoes', 'nike', 'adidas', 'sneakers', 'boots',
            'dress', 'shirt', 'jeans', 'clothes', 'fashion',
            'car', 'toyota', 'honda', 'vehicle', 'auto',
            'watch', 'jewelry', 'bag', 'furniture', 'chair'
        }
        
        # Extract words from analysis
        words = re.findall(r'\b[a-zA-Z]{3,}\b', analysis_text.lower())
        
        # Prioritize important terms
        important_terms = []
        for word in words:
            if word in priority_terms and word not in important_terms:
                important_terms.insert(0, word)
            elif word not in important_terms and len(word) > 3:
                important_terms.append(word)
        
        return ' '.join(important_terms[:3])


class ConversationManager:
    """
    Simplified conversation context management with better performance
    """
    
    def __init__(self):
        self.cache_timeout = 1800  # 30 minutes
    
    def get_context(self, user_id: int) -> Dict:
        """Get conversation context for user"""
        cache_key = f"conversation_context:{user_id}"
        context = cache.get(cache_key, {})
        
        # Default context structure
        default_context = {
            'stage': 'open',
            'last_action': None,
            'last_search_query': '',
            'last_search_results': [],
            'expecting_response': None,
            'conversation_count': 0,
            'last_update': timezone.now().isoformat()
        }
        
        # Merge with defaults
        for key, value in default_context.items():
            if key not in context:
                context[key] = value
        
        return context
    
    def update_context(self, user_id: int, user_input: str, 
                      bot_response: str, intent_result: Dict):
        """Update conversation context after interaction"""
        context = self.get_context(user_id)
        
        # Update based on intent
        intent = intent_result['intent']
        
        if intent == 'search_request':
            context.update({
                'stage': 'search_results_shown',
                'last_action': 'search',
                'last_search_query': user_input,
                'expecting_response': 'search_followup'
            })
        elif intent == 'category_browse':
            context.update({
                'stage': 'category_browsing',
                'last_action': 'browse_categories',
                'expecting_response': 'category_selection'
            })
        elif intent in ['thanks', 'greeting']:
            context.update({
                'stage': 'open',
                'last_action': intent,
                'expecting_response': None
            })
        
        context['conversation_count'] += 1
        context['last_update'] = timezone.now().isoformat()
        
        # Save to cache
        cache_key = f"conversation_context:{user_id}"
        cache.set(cache_key, context, self.cache_timeout)
    
    def analyze_intent(self, message: str, context: Dict) -> Dict:
        """Analyze user intent with context awareness"""
        message_lower = message.lower().strip()
        
        # Context-aware intent detection
        expecting = context.get('expecting_response')
        
        if expecting == 'search_followup':
            if any(word in message_lower for word in ['yes', 'yeah', 'sure', 'external']):
                return {'intent': 'external_search_request', 'confidence': 0.9}
            elif any(word in message_lower for word in ['first', '1', 'top']):
                return {'intent': 'item_selection', 'confidence': 0.9, 'selection_index': 0}
            elif any(word in message_lower for word in ['second', '2']):
                return {'intent': 'item_selection', 'confidence': 0.9, 'selection_index': 1}
            elif any(word in message_lower for word in ['more', 'details', 'info']):
                return {'intent': 'more_info_request', 'confidence': 0.9}
        
        elif expecting == 'category_selection':
            # User is selecting a category
            return {'intent': 'category_browse', 'confidence': 0.8}
        
        # General intent patterns
        intent_patterns = {
            'greeting': ['hi', 'hello', 'hey', 'good morning', 'good afternoon'],
            'thanks': ['thank', 'thanks', 'appreciate'],
            'search_request': ['looking for', 'need', 'want', 'find', 'search', 'buy'],
            'category_browse': ['categories', 'browse', 'explore', 'what do you have'],
            'external_search_request': ['amazon', 'jumia', 'external', 'other stores'],
            'more_info_request': ['more info', 'tell me more', 'details', 'more about']
        }
        
        # Score patterns
        best_intent = 'clarification_needed'
        best_score = 0
        
        for intent, patterns in intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in message_lower)
            if score > best_score:
                best_intent = intent
                best_score = score
        
        # If no clear intent and message looks like a search
        if best_score == 0 and len(message.strip()) > 2:
            best_intent = 'search_request'
            best_score = 0.6
        
        return {
            'intent': best_intent,
            'confidence': min(best_score / len(intent_patterns.get(best_intent, [''])), 1.0)
        }
    
    def extract_search_terms(self, message: str) -> str:
        """Extract clean search terms from user message"""
        # Remove intent words
        intent_words = {
            'i', 'need', 'want', 'looking', 'for', 'find', 'search', 
            'buy', 'get', 'show', 'me', 'can', 'you', 'help'
        }
        
        # Clean and filter
        cleaned = re.sub(r'[^\w\s]', ' ', message.lower())
        words = [word for word in cleaned.split() 
                if word not in intent_words and len(word) > 2]
        
        return ' '.join(words) if words else message.strip()


class ResponseFormatter:
    """
    Centralized response formatting with consistent styling
    """
    
    def format_search_results(self, search_results: Dict, query: str, 
                            context: Dict) -> str:
        """Format search results with consistent branding"""
        items = search_results['items']
        if not items:
            return self.format_no_results_response(query, context)
        
        response_lines = [
            f"🛍️ Great! Found {len(items)} amazing options on our platform for '{query}':\n"
        ]
        
        for i, item in enumerate(items[:5], 1):
            is_product = hasattr(item, 'product_name')
            
            if is_product:
                name = item.product_name
                price = item.get_formatted_price()
                discount = item.get_discount_percentage()
                discount_text = f" 🔥 {discount}% OFF!" if discount > 0 else ""
            else:
                name = item.service_name
                price = item.get_formatted_price_range()
                discount_text = ""
            
            location = item.get_full_location()
            rating = item.average_rating()
            rating_count = item.rating_count()
            
            # Format rating
            if rating > 0:
                stars = "⭐" * min(int(rating), 5)
                rating_text = f"{stars} {rating}/5 ({rating_count} reviews)"
            else:
                rating_text = "⭐ New listing"
            
            response_lines.append(
                f"{i}. {name}{discount_text}\n"
                f"   💰 {price}\n"
                f"   📍 {location}\n"
                f"   {rating_text}\n"
            )
        
        # Add interaction prompts
        response_lines.extend([
            "\n✨ Why choose Finda sellers?",
            "• 🚚 Faster delivery",
            "• 💬 Direct seller communication", 
            "• 🏠 Support Worldwide businesses",
            "• 💯 Verified seller ratings\n",
            "💬 What's next?",
            "• Say 'first one' or 'second one' for details",
            "• Ask 'tell me more' for additional info",
            "• Say 'yes' to also check external stores"
        ])
        
        return "\n".join(response_lines)
    
    def format_no_results_response(self, query: str, context: Dict) -> str:
        """Format response when no results found"""
        return f"""
🔍 I searched Finda thoroughly for '{query}' but didn't find exact matches right now.

Here's how I can help:

1️⃣ Try different keywords
   • Maybe 'phone' instead of 'smartphone'
   • Or 'repair service' instead of 'technician'

2️⃣ Browse our categories
   • Say 'categories' to see popular sections
   • Discover similar items you might like

3️⃣ Search external stores
   • Amazon, Jumia, Konga as backup options

4️⃣ Get search alerts (Coming soon!)
   • Be notified when '{query}' arrives on Finda

What would you prefer? Say 'categories' to browse or 'external' for other stores!
"""
    
    def format_categories(self, categories) -> str:
        """Format categories for browsing"""
        if not categories:
            return "No categories available right now."
        
        response_lines = ["🛍️ Browse Finda's Popular Categories:\n"]
        
        for cat in categories:
            item_count = getattr(cat, 'item_count', 0)
            emoji = cat.icon or "📦"
            response_lines.append(f"{emoji} {cat.name} ({item_count} items)")
        
        response_lines.extend([
            "\n💡 How to search:",
            "• Type any category name above",
            "• Search for specific items (e.g., 'iPhone', 'plumber')",
            "• Send photos of items you want",
            "• Use voice messages",
            "\nWhat interests you today?"
        ])
        
        return "\n".join(response_lines)
    
    def format_category_results(self, results: Dict, category_name: str) -> str:
        """Format category search results"""
        items = results.get('items', [])
        
        if not items:
            return f"No items found in {category_name} category right now. Try browsing other categories!"
        
        response_lines = [
            f"🛍️ {category_name.title()} Category - {len(items)} great options:\n"
        ]
        
        for i, item in enumerate(items[:6], 1):
            is_product = hasattr(item, 'product_name')
            name = item.product_name if is_product else item.service_name
            price = item.get_formatted_price() if is_product else item.get_formatted_price_range()
            location = item.get_full_location()
            rating = item.average_rating()
            
            stars = "⭐" * min(int(rating), 5) if rating > 0 else "⭐ New"
            
            response_lines.append(
                f"{i}. {name}\n"
                f"   💰 {price} | 📍 {location}\n"
                f"   {stars}\n"
            )
        
        response_lines.extend([
            "💬 What interests you?",
            "• Pick a number for details (e.g., 'first one')",
            "• Ask for 'more options' in this category", 
            "• Search for something specific"
        ])
        
        return "\n".join(response_lines)
    
    def format_item_details(self, item_data: Dict, context: Dict) -> str:
        """Format detailed item information"""
        if not item_data:
            return "I'm not sure which item you're referring to. Could you be more specific?"
        
        return f"""
🔍 {item_data.get('name', 'Item')} - Detailed Info:

💰 Price: {item_data.get('price', 'Contact seller')}
📍 Location: {item_data.get('location', 'Not specified')}
📦 Type: {item_data.get('type', 'Item').title()}

This is one of our top-rated items on Finda!

What would you like to do?
• Get seller contact information
• Find similar items for comparison
• Add to your favorites
• Get more photos and specifications

Just let me know what interests you most!
"""
    
    def format_detailed_info(self, results: List, query: str) -> str:
        """Format detailed information about search results"""
        if not results:
            return "I'd love to provide more details! What specifically would you like to know more about?"
        
        response_lines = [f"📋 Detailed Info for your '{query}' search:\n"]
        
        for i, item in enumerate(results[:3], 1):
            response_lines.append(
                f"{i}. {item.get('name', 'Item')}\n"
                f"   💰 Price: {item.get('price', 'Contact seller')}\n"
                f"   📍 Location: {item.get('location', 'Not specified')}\n"
                f"   📦 Type: {item.get('type', 'Item').title()}\n"
            )
        
        response_lines.extend([
            "💬 Want to know more?",
            "• Say 'contact seller' for any item",
            "• Ask 'compare these items'", 
            "• Request 'similar items'",
            "• Get 'seller ratings and reviews'"
        ])
        
        return "\n".join(response_lines)
    
    def format_image_search_results(self, search_results: Dict, 
                                  analysis: str, user_query: str) -> str:
        """Format image search results"""
        items = search_results['items']
        
        response_lines = [
            "📸 Excellent! Based on your image, I found these on Finda:\n",
            f"🤖 I can see: {analysis[:150]}...\n"
        ]
        
        for i, item in enumerate(items[:4], 1):
            is_product = hasattr(item, 'product_name')
            name = item.product_name if is_product else item.service_name
            price = item.get_formatted_price() if is_product else item.get_formatted_price_range()
            location = item.get_full_location()
            rating = item.average_rating()
            
            stars = "⭐" * min(int(rating), 5) if rating > 0 else "⭐ New"
            
            response_lines.append(
                f"{i}. {name}\n"
                f"   💰 {price}\n"
                f"   📍 {location}\n"
                f"   {stars}\n"
            )
        
        response_lines.extend([
            "✨ These are from verified Finda sellers!",
            "\n💬 What would you like to do?",
            "• Say 'first one' for details about any item",
            "• Ask 'tell me more' for additional information",
            "• Say 'yes' to also check external stores",
            "• Upload another image to search"
        ])
        
        return "\n".join(response_lines)


class ErrorHandler:
    """
    Centralized error handling with logging and user-friendly messages
    """
    
    def handle_chat_error(self, error: Exception, user_id: int) -> Dict:
        """Handle chat-related errors with appropriate responses"""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Log the error
        logger.error(f"Chat error for user {user_id}: {error_type} - {error_message}")
        
        # Determine error type and response
        if 'database' in error_message.lower() or 'connection' in error_message.lower():
            return {
                'type': 'database_error',
                'message': (
                    "I'm having trouble accessing our product database right now. 🔧\n\n"
                    "Please try again in a moment. I'll be ready to help you find "
                    "amazing deals on Finda shortly!"
                ),
                'status': 503
            }
        
        elif 'timeout' in error_message.lower():
            return {
                'type': 'timeout_error',
                'message': (
                    "That took longer than expected! ⏰\n\n"
                    "Could you please try your search again? "
                    "I'm here to help you find what you need on Finda."
                ),
                'status': 408
            }
        
        elif 'api' in error_message.lower() or 'gemini' in error_message.lower():
            return {
                'type': 'ai_service_error',
                'message': (
                    "My AI assistant is taking a short break. 🤖\n\n"
                    "But I can still help you search Finda's marketplace! "
                    "What are you looking for?"
                ),
                'status': 503
            }
        
        else:
            # General error
            return {
                'type': 'general_error',
                'message': (
                    "Something unexpected happened, but don't worry! 🛠️\n\n"
                    "I'm still here to help you find amazing products and services "
                    "on Finda. What are you looking for?"
                ),
                'status': 500
            }


class PerformanceMonitor:
    """
    Simple performance monitoring for optimization
    """
    
    def __init__(self):
        self.request_times = {}
    
    def start_request(self, user_id: int, request_type: str):
        """Start timing a request"""
        self.request_times[f"{user_id}:{request_type}"] = timezone.now()
    
    def end_request(self, user_id: int, request_type: str, success: bool):
        """End timing and log performance"""
        key = f"{user_id}:{request_type}"
        start_time = self.request_times.get(key)
        
        if start_time:
            duration = (timezone.now() - start_time).total_seconds()
            
            # Log slow requests
            if duration > 5.0:
                logger.warning(f"Slow {request_type} request for user {user_id}: {duration:.2f}s")
            elif duration > 10.0:
                logger.error(f"Very slow {request_type} request for user {user_id}: {duration:.2f}s")
            
            # Clean up
            del self.request_times[key]
            
            # Cache performance stats
            cache_key = f"perf_stats:{request_type}"
            stats = cache.get(cache_key, {'total': 0, 'success': 0, 'avg_time': 0})
            
            stats['total'] += 1
            if success:
                stats['success'] += 1
            
            # Update average time
            stats['avg_time'] = (stats['avg_time'] + duration) / 2
            
            cache.set(cache_key, stats, 3600)  # Cache for 1 hour