ion_helpers.py - Additional utilities for conversation flow
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import re
import json
from main.models import Products, Services, Category

class ConversationMemory:
    """Enhanced memory system for conversation context"""
    
    @staticmethod
    def store_search_results(user_id, query, results, search_type='finda'):
        """Store search results for context reference"""
        cache_key = f"search_results_{user_id}"
        
        # Convert results to serializable format
        serializable_results = []
        for item in results:
            try:
                is_product = hasattr(item, 'product_name')
                item_data = {
                    'id': item.id,
                    'name': item.product_name if is_product else item.service_name,
                    'type': 'product' if is_product else 'service',
                    'price': str(item.product_price if is_product else item.starting_price or 0),
                    'location': item.get_full_location() if hasattr(item, 'get_full_location') else '',
                    'rating': float(item.average_rating() if hasattr(item, 'average_rating') else 0),
                    'url': item.get_absolute_url() if hasattr(item, 'get_absolute_url') else '',
                    'description': (item.product_description if is_product else item.service_description)[:200]
                }
                serializable_results.append(item_data)
            except Exception as e:
                print(f"Error serializing item: {e}")
                continue
        
        search_data = {
            'query': query,
            'results': serializable_results,
            'search_type': search_type,
            'timestamp': timezone.now().isoformat(),
            'total_count': len(results)
        }
        
        cache.set(cache_key, search_data, timeout=1800)  # 30 minutes
        return search_data
    
    @staticmethod
    def get_last_search(user_id):
        """Retrieve last search results"""
        cache_key = f"search_results_{user_id}"
        return cache.get(cache_key)
    
    @staticmethod
    def store_conversation_stage(user_id, stage, data=None):
        """Store current conversation stage"""
        cache_key = f"conversation_stage_{user_id}"
        stage_data = {
            'stage': stage,
            'data': data or {},
            'timestamp': timezone.now().isoformat()
        }
        cache.set(cache_key, stage_data, timeout=3600)  # 1 hour
    
    @staticmethod
    def get_conversation_stage(user_id):
        """Get current conversation stage"""
        cache_key = f"conversation_stage_{user_id}"
        return cache.get(cache_key, {'stage': 'open', 'data': {}})


class SmartIntentDetector:
    """Advanced intent detection with contextual understanding"""
    
    INTENT_PATTERNS = {
        'greeting': {
            'keywords': ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'sup', 'howdy'],
            'phrases': ['how are you', 'whats up', 'hey there'],
            'priority': 0.9
        },
        'item_reference': {
            'keywords': ['first', 'second', 'third', 'top', 'number'],
            'phrases': ['first one', 'second one', 'the first', 'number 1', 'option 1'],
            'priority': 0.95
        },
        'more_info': {
            'keywords': ['more', 'details', 'info', 'information', 'tell'],
            'phrases': ['tell me more', 'more details', 'more info', 'learn more'],
            'priority': 0.8
        },
        'contact_seller': {
            'keywords': ['contact', 'call', 'phone', 'reach', 'seller'],
            'phrases': ['contact seller', 'call seller', 'phone number', 'how to reach'],
            'priority': 0.9
        },
        'price_inquiry': {
            'keywords': ['price', 'cost', 'expensive', 'cheap', 'affordable'],
            'phrases': ['how much', 'what does it cost', 'price range'],
            'priority': 0.8
        },
        'location_inquiry': {
            'keywords': ['where', 'location', 'address', 'near', 'close'],
            'phrases': ['where is', 'how far', 'close to me', 'near me'],
            'priority': 0.8
        },
        'comparison': {
            'keywords': ['compare', 'difference', 'better', 'versus', 'vs'],
            'phrases': ['which is better', 'compare these', 'what\'s the difference'],
            'priority': 0.85
        },
        'external_search': {
            'keywords': ['amazon', 'jumia', 'konga', 'external', 'other'],
            'phrases': ['other stores', 'check amazon', 'look elsewhere'],
            'priority': 0.9
        },
        'positive_response': {
            'keywords': ['yes', 'yeah', 'sure', 'ok', 'okay', 'alright'],
            'phrases': ['yes please', 'go ahead', 'sounds good'],
            'priority': 0.7
        },
        'negative_response': {
            'keywords': ['no', 'nope', 'not', 'skip', 'pass'],
            'phrases': ['no thanks', 'not interested', 'maybe later'],
            'priority': 0.7
        }
    }
    
    @classmethod
    def detect_intent(cls, message, conversation_context=None):
        """Detect user intent with context awareness"""
        message_lower = message.lower().strip()
        
        # Context-aware intent detection
        if conversation_context:
            contextual_intent = cls._detect_contextual_intent(message_lower, conversation_context)
            if contextual_intent:
                return contextual_intent
        
        # General intent detection
        intent_scores = {}
        
        for intent, config in cls.INTENT_PATTERNS.items():
            score = 0
            
            # Check keywords
            for keyword in config.get('keywords', []):
                if keyword in message_lower:
                    score += config['priority'] * 0.6
            
            # Check phrases (higher weight)
            for phrase in config.get('phrases', []):
                if phrase in message_lower:
                    score += config['priority'] * 1.0
            
            if score > 0:
                intent_scores[intent] = score
        
        # Return highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            return {
                'intent': best_intent,
                'confidence': intent_scores[best_intent],
                'all_scores': intent_scores
            }
        
        return {'intent': 'general_query', 'confidence': 0.5, 'all_scores': {}}
    
    @classmethod
    def _detect_contextual_intent(cls, message, context):
        """Detect intent based on conversation context"""
        stage = context.get('stage', 'open')
        
        if stage == 'search_results_shown':
            # User just saw search results
            if any(word in message for word in ['yes', 'yeah', 'sure', 'ok', 'external']):
                return {'intent': 'request_external_search', 'confidence': 0.95, 'contextual': True}
            elif any(word in message for word in ['first', '1', 'top', 'number 1']):
                return {'intent': 'select_item', 'confidence': 0.95, 'contextual': True, 'item_index': 0}
            elif any(word in message for word in ['second', '2', 'number 2']):
                return {'intent': 'select_item', 'confidence': 0.95, 'contextual': True, 'item_index': 1}
            elif any(word in message for word in ['third', '3', 'number 3']):
                return {'intent': 'select_item', 'confidence': 0.95, 'contextual': True, 'item_index': 2}
        
        elif stage == 'categories_shown':
            # User just saw categories, any response is likely a category selection
            return {'intent': 'category_selection', 'confidence': 0.8, 'contextual': True}
        
        elif stage == 'awaiting_external_confirmation':
            # User is being asked about external search
            if any(word in message for word in ['yes', 'yeah', 'sure', 'ok', 'go']):
                return {'intent': 'confirm_external_search', 'confidence': 0.95, 'contextual': True}
            elif any(word in message for word in ['no', 'nope', 'not', 'skip']):
                return {'intent': 'decline_external_search', 'confidence': 0.95, 'contextual': True}
        
        return None


class ResponsePersonalizer:
    """Personalize responses based on user behavior and preferences"""
    
    @staticmethod
    def personalize_greeting(user):
        """Create personalized greeting based on user history"""
        from chatbot.models import ChatMessage
        
        message_count = ChatMessage.objects.filter(user=user).count()
        
        if message_count == 0:
            return "new_user"
        elif message_count < 5:
            return "returning_user"
        else:
            return "frequent_user"
    
    @staticmethod
    def get_user_preferences(user):
        """Get user preferences from search history"""
        from chatbot.models import ChatMessage
        
        recent_searches = ChatMessage.objects.filter(
            user=user
        ).order_by('-timestamp')[:20]
        
        # Analyze search patterns
        search_terms = []
        for msg in recent_searches:
            search_terms.extend(msg.user_input.lower().split())
        
        # Common categories/interests
        category_keywords = {
            'electronics': ['phone', 'laptop', 'computer', 'tablet', 'electronics'],
            'fashion': ['clothes', 'dress', 'shirt', 'shoes', 'fashion'],
            'home': ['furniture', 'home', 'house', 'kitchen', 'bedroom'],
            'automotive': ['car', 'vehicle', 'auto', 'motorcycle', 'parts'],
            'services': ['service', 'repair', 'cleaning', 'plumber', 'electrician']
        }
        
        interests = {}
        for category, keywords in category_keywords.items():
            count = sum(1 for term in search_terms if term in keywords)
            if count > 0:
                interests[category] = count
        
        return {
            'top_interests': sorted(interests.items(), key=lambda x: x[1], reverse=True)[:3],
            'search_frequency': len(recent_searches),
            'preferred_interaction': 'text'  # Can be enhanced with voice/image usage stats
        }
    
    @staticmethod
    def customize_response(base_response, user, context=None):
        """Customize response based on user profile"""
        preferences = ResponsePersonalizer.get_user_preferences(user)
        
        # Add personalized touches
        if preferences['top_interests']:
            top_interest = preferences['top_interests'][0][0]
            
            # Add relevant suggestions
            if 'What else can I help you find?' in base_response:
                suggestions = {
                    'electronics': '📱 Maybe check out our latest phones and gadgets?',
                    'fashion': '👗 Or browse our trending fashion items?',
                    'home': '🏠 Or explore our home and furniture section?',
                    'automotive': '🚗 Or look at our vehicle and auto parts?',
                    'services': '🔧 Or find professional services in your area?'
                }
                
                if top_interest in suggestions:
                    base_response = base_response.replace(
                        'What else can I help you find?',
                        f"What else can I help you find? {suggestions[top_interest]}"
                    )
        
        return base_response


class ConversationAnalytics:
    """Track conversation metrics and patterns"""
    
    @staticmethod
    def log_conversation_event(user_id, event_type, data=None):
        """Log conversation events for analytics"""
        cache_key = f"conversation_events_{user_id}"
        
        events = cache.get(cache_key, [])
        
        event = {
            'type': event_type,
            'data': data or {},
            'timestamp': timezone.now().isoformat()
        }
        
        events.append(event)
        
        # Keep only last 50 events
        if len(events) > 50:
            events = events[-50:]
        
        cache.set(cache_key, events, timeout=86400)  # 24 hours
    
    @staticmethod
    def get_conversation_insights(user_id):
        """Get insights about user's conversation patterns"""
        cache_key = f"conversation_events_{user_id}"
        events = cache.get(cache_key, [])
        
        if not events:
            return {}
        
        # Analyze patterns
        event_types = {}
        for event in events:
            event_type = event['type']
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        # Calculate engagement metrics
        total_events = len(events)
        search_events = event_types.get('search', 0)
        response_events = event_types.get('response', 0)
        
        return {
            'total_interactions': total_events,
            'search_ratio': search_events / total_events if total_events > 0 else 0,
            'response_ratio': response_events / total_events if total_events > 0 else 0,
            'most_common_action': max(event_types, key=event_types.get) if event_types else None,
            'engagement_level': 'high' if total_events > 20 else 'medium' if total_events > 5 else 'low'
        }


# Utility functions for conversation flow
def extract_item_reference(message, search_results):
    """Extract which item user is referring to"""
    message_lower = message.lower()
    
    # Number references
    number_patterns = {
        'first': 0, '1st': 0, 'one': 0, '1': 0, 'top': 0,
        'second': 1, '2nd': 1, 'two': 1, '2': 1,
        'third': 2, '3rd': 2, 'three': 2, '3': 2,
        'fourth': 3, '4th': 3, 'four': 3, '4': 3,
        'fifth': 4, '5th': 4, 'five': 4, '5': 4
    }
    
    for pattern, index in number_patterns.items():
        if pattern in message_lower and index < len(search_results):
            return index
    
    # Name references
    for i, result in enumerate(search_results):
        item_name = result.get('name', '').lower()
        # Check if any significant word from item name is in the message
        name_words = [word for word in item_name.split() if len(word) > 3]
        for word in name_words:
            if word in message_lower:
                return i
    
    return None


def generate_contextual_followup(last_action, results_count=0):
    """Generate appropriate follow-up questions based on context"""
    
    followups = {
        'search_completed': [
            "What would you like to know more about?",
            "Which of these catches your interest?",
            "Should I provide more details on any of these?",
            "Would you like to see similar items?"
        ],
        'no_results': [
            "Should I try a different search approach?",
            "Would you like to browse our categories instead?", 
            "Should I check external stores for you?",
            "Can you describe what you're looking for differently?"
        ],
        'categories_shown': [
            "Which category sounds interesting to you?",
            "What type of products are you looking for?",
            "Should I show you what's popular in any category?",
            "Would you like to search for something specific instead?"
        ],
        'item_details_shown': [
            "Would you like the seller's contact information?",
            "Should I find similar items for comparison?",
            "Do you need any other details about this item?",
            "Ready to contact the seller or keep browsing?"
        ]
    }
    
    import random
    action_followups = followups.get(last_action, followups['search_completed'])
    
    # Adjust based on results count
    if results_count > 3:
        action_followups.append("Would you like me to narrow down these options?")
    elif results_count == 1:
        action_followups.append("This looks like a great match! What do you think?")
    
    return random.choice(action_followups)


def clean_search_query_advanced(query, context=None):
    """Advanced query cleaning with context awareness"""
    if not query:
        return ""
    
    # Remove conversational fluff
    conversation_words = {
        'please', 'can you', 'could you', 'would you', 'help me', 'i want',
        'i need', 'looking for', 'search for', 'find me', 'show me',
        'get me', 'buy', 'purchase', 'acquire'
    }
    
    # Clean the query
    cleaned = query.lower().strip()
    
    # Remove conversation words
    for word in conversation_words:
        cleaned = cleaned.replace(word, ' ')
    
    # Remove extra whitespace
    cleaned = ' '.join(cleaned.split())
    
    # Context-aware cleaning
    if context:
        last_search = context.get('last_search_query', '')
        if last_search and len(cleaned) < 3:
            # User might be referring to previous search
            return last_search
    
    # If query is too short after cleaning, return original
    if len(cleaned) < 2:
        return query
    
    return cleaned


def format_conversation_response(base_response, user_context=None, personalize=True):
    """Format response with conversation enhancements"""
    
    if not base_response:
        return ""
    
    # Add conversation markers for natural flow
    response = base_response
    
    # Add contextual connectors
    if user_context:
        stage = user_context.get('stage', 'open')
        
        if stage == 'search_results_shown':
            if not any(phrase in response.lower() for phrase in ['what would you', 'which', 'should i']):
                response += "\n\n💬 What would you like to do next?"
        
        elif stage == 'awaiting_response':
            if not response.endswith('?'):
                response += " What do you think?"
    
    # Ensure response ends naturally
    if not response.endswith(('?', '!', '.')):
        response += "!"
    
    return response


class QuickResponseGenerator:
    """Generate quick responses for common scenarios"""
    
    QUICK_RESPONSES = {
        'item_selected': {
            'templates': [
                "Great choice! Here are the details for {item_name}:",
                "Excellent pick! Let me tell you more about {item_name}:",
                "Perfect! Here's everything about {item_name}:"
            ],
            'followups': [
                "Would you like the seller's contact info?",
                "Should I find similar options for comparison?",
                "Ready to reach out to this seller?"
            ]
        },
        'external_search_requested': {
            'templates': [
                "I'll check external stores for '{query}' as a bonus option:",
                "Let me see what's available on other platforms for '{query}':",
                "Checking Amazon, Jumia, and other stores for '{query}':"
            ],
            'followups': [
                "Remember, Finda offers faster local delivery!",
                "These are backup options - Finda sellers are usually better!",
                "Don't forget our local sellers provide direct support!"
            ]
        },
        'no_results_found': {
            'templates': [
                "I searched thoroughly for '{query}' but didn't find matches right now.",
                "No exact matches for '{query}' at the moment, but I can help differently:",
                "'{query}' isn't showing results today, but here are your options:"
            ],
            'followups': [
                "Should I try related search terms?",
                "Would you like to browse similar categories?",
                "Should I check external stores as backup?"
            ]
        },
        'price_inquiry': {
            'templates': [
                "Here are the price details for {item_name}:",
                "Great question! The pricing for {item_name} is:",
                "Let me break down the cost for {item_name}:"
            ],
            'followups': [
                "Prices are negotiable with most Finda sellers!",
                "Would you like to contact them about the price?",
                "Should I find similar items in different price ranges?"
            ]
        },
        'location_inquiry': {
            'templates': [
                "Here's the location info for {item_name}:",
                "This item is located in:",
                "You can find {item_name} at:"
            ],
            'followups': [
                "Local delivery is usually faster and cheaper!",
                "Would you like sellers closer to your area?",
                "Should I check delivery options for you?"
            ]
        }
    }
    
    @classmethod
    def generate_response(cls, response_type, **kwargs):
        """Generate quick response for given type"""
        
        if response_type not in cls.QUICK_RESPONSES:
            return None
        
        config = cls.QUICK_RESPONSES[response_type]
        
        # Select template
        import random
        template = random.choice(config['templates'])
        
        # Format with provided data
        try:
            formatted_template = template.format(**kwargs)
        except KeyError:
            formatted_template = template
        
        # Add followup
        followup = random.choice(config['followups'])
        
        return f"{formatted_template}\n\n{followup}"


def detect_conversation_ending(message):
    """Detect if user is ending the conversation"""
    ending_phrases = [
        'bye', 'goodbye', 'see you', 'talk later', 'thanks bye',
        'that\'s all', 'i\'m done', 'no more', 'nothing else',
        'end chat', 'stop chat', 'exit', 'quit'
    ]
    
    message_lower = message.lower().strip()
    
    for phrase in ending_phrases:
        if phrase in message_lower:
            return True
    
    return False


def generate_goodbye_response(user_context=None):
    """Generate appropriate goodbye response"""
    
    base_responses = [
        "Thanks for shopping with Finda! 🛍️ Come back anytime for more great deals!",
        "Goodbye! Hope you found what you were looking for on Finda! 😊",
        "See you later! Remember, Finda is always here for your shopping needs! 👋",
        "Thanks for using Finda! We're here whenever you need us! ✨"
    ]
    
    # Personalize based on context
    if user_context:
        last_search = user_context.get('last_search_query')
        if last_search:
            base_responses.append(
                f"Hope you find the perfect '{last_search}'! "
                f"Finda will have even more options soon! 🚀"
            )
    
    import random
    return random.choice(base_responses)


class ConversationFlowValidator:
    """Validate conversation flow and detect issues"""
    
    @staticmethod
    def validate_response_quality(response, context=None):
        """Validate if response is appropriate for context"""
        
        if not response or len(response.strip()) < 10:
            return {'valid': False, 'issue': 'response_too_short'}
        
        # Check for context mismatches
        if context:
            stage = context.get('stage', 'open')
            
            if stage == 'search_results_shown':
                if 'welcome' in response.lower():
                    return {'valid': False, 'issue': 'greeting_after_search'}
            
            elif stage == 'awaiting_external_confirmation':
                if 'welcome' in response.lower() or 'categories' in response.lower():
                    return {'valid': False, 'issue': 'context_mismatch'}
        
        # Check for repetitive responses
        repetitive_phrases = ['what can i help', 'how can i assist', 'what are you looking for']
        phrase_count = sum(1 for phrase in repetitive_phrases if phrase in response.lower())
        
        if phrase_count > 1:
            return {'valid': False, 'issue': 'repetitive_response'}
        
        return {'valid': True, 'quality_score': len(response) / 100}  # Simple quality metric
    
    @staticmethod
    def suggest_response_improvement(response, issue):
        """Suggest improvements for problematic responses"""
        
        improvements = {
            'response_too_short': "Add more helpful details and follow-up questions",
            'greeting_after_search': "Focus on search results instead of greeting",
            'context_mismatch': "Ensure response matches conversation context",
            'repetitive_response': "Vary the language and avoid repeated phrases"
        }
        
        return improvements.get(issue, "Review response for better user experience")


# Export main classes and functions
__all__ = [
    'ConversationMemory',
    'SmartIntentDetector', 
    'ResponsePersonalizer',
    'ConversationAnalytics',
    'QuickResponseGenerator',
    'ConversationFlowValidator',
    'extract_item_reference',
    'generate_contextual_followup',
    'clean_search_query_advanced',
    'format_conversation_response',
    'detect_conversation_ending',
    'generate_goodbye_response'
]