# enhanced_conversation_manager.py - NEW FILE
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import json
import re

class ConversationContext:
    """Manages conversation state and context for natural flow"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.cache_key = f"conversation_context_{user_id}"
        self.context = self._load_context()
    
    def _load_context(self):
        """Load conversation context from cache"""
        context = cache.get(self.cache_key, {})
        default_context = {
            'last_action': None,
            'last_search_query': None,
            'last_search_results': [],
            'last_categories_shown': [],
            'pending_external_search': False,
            'conversation_stage': 'greeting',  # greeting, searching, browsing, comparing
            'user_preferences': {},
            'last_bot_question': None,
            'expecting_response_to': None,  # What the bot is waiting for
            'conversation_history': [],
            'last_update': timezone.now().isoformat()
        }
        
        # Merge with defaults
        for key, value in default_context.items():
            if key not in context:
                context[key] = value
        
        return context
    
    def save_context(self):
        """Save context to cache with 1 hour expiry"""
        self.context['last_update'] = timezone.now().isoformat()
        cache.set(self.cache_key, self.context, timeout=3600)
    
    def update_search_context(self, query, results):
        """Update context after a search"""
        self.context.update({
            'last_action': 'search',
            'last_search_query': query,
            'last_search_results': [
                {
                    'id': getattr(item, 'id', None),
                    'name': getattr(item, 'product_name', getattr(item, 'service_name', '')),
                    'type': 'product' if hasattr(item, 'product_name') else 'service',
                    'price': str(getattr(item, 'product_price', getattr(item, 'starting_price', 0))),
                    'location': item.get_full_location() if hasattr(item, 'get_full_location') else ''
                }
                for item in results[:5]  # Store top 5 results
            ],
            'conversation_stage': 'search_results_shown',
            'expecting_response_to': 'search_results',
            'last_bot_question': 'Would you like more details about any of these items, or should I search external stores?'
        })
        self.save_context()
    
    def update_categories_context(self, categories):
        """Update context after showing categories"""
        self.context.update({
            'last_action': 'show_categories',
            'last_categories_shown': [cat.name for cat in categories] if categories else [],
            'conversation_stage': 'browsing_categories',
            'expecting_response_to': 'category_selection',
            'last_bot_question': 'What category interests you?'
        })
        self.save_context()
    
    def set_external_search_pending(self, query):
        """Set context for pending external search"""
        self.context.update({
            'pending_external_search': True,
            'conversation_stage': 'awaiting_external_confirmation',
            'expecting_response_to': 'external_search_confirmation',
            'last_bot_question': f'Should I search external stores for "{query}"?'
        })
        self.save_context()
    
    def clear_expectations(self):
        """Clear pending expectations"""
        self.context.update({
            'expecting_response_to': None,
            'last_bot_question': None,
            'pending_external_search': False,
            'conversation_stage': 'open'
        })
        self.save_context()
    
    def add_to_history(self, user_input, bot_response):
        """Add exchange to conversation history"""
        if 'conversation_history' not in self.context:
            self.context['conversation_history'] = []
        
        self.context['conversation_history'].append({
            'user': user_input,
            'bot': bot_response[:200] + "..." if len(bot_response) > 200 else bot_response,
            'timestamp': timezone.now().isoformat()
        })
        
        # Keep only last 10 exchanges
        if len(self.context['conversation_history']) > 10:
            self.context['conversation_history'] = self.context['conversation_history'][-10:]
        
        self.save_context()


class NaturalLanguageProcessor:
    """Enhanced NLP for better conversation understanding"""
    
    @staticmethod
    def analyze_user_intent(message, conversation_context):
        """Analyze user intent considering conversation context"""
        message_lower = message.lower().strip()
        context = conversation_context.context
        
        # Handle contextual responses first
        if context.get('expecting_response_to'):
            return NaturalLanguageProcessor._handle_contextual_response(
                message_lower, context['expecting_response_to'], context
            )
        
        # Detect primary intents
        intent_patterns = {
            'greeting': {
                'patterns': ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'sup'],
                'confidence': 0.9
            },
            'thanks': {
                'patterns': ['thank', 'thanks', 'appreciate', 'grateful'],
                'confidence': 0.8
            },
            'search_request': {
                'patterns': ['looking for', 'need', 'want', 'find', 'search', 'buy', 'get'],
                'confidence': 0.7
            },
            'browse_request': {
                'patterns': ['browse', 'categories', 'explore', 'show me', 'what do you have'],
                'confidence': 0.8
            },
            'more_info_request': {
                'patterns': ['more info', 'tell me more', 'details', 'more about', 'first one', 'second one'],
                'confidence': 0.7
            },
            'comparison_request': {
                'patterns': ['compare', 'difference', 'which is better', 'vs', 'versus'],
                'confidence': 0.7
            },
            'external_request': {
                'patterns': ['external', 'amazon', 'jumia', 'other stores', 'outside finda'],
                'confidence': 0.9
            }
        }
        
        # Calculate intent scores
        intent_scores = {}
        for intent, config in intent_patterns.items():
            score = 0
            for pattern in config['patterns']:
                if pattern in message_lower:
                    score += config['confidence']
            intent_scores[intent] = score
        
        # Get highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            if intent_scores[best_intent] > 0.5:
                return {
                    'intent': best_intent,
                    'confidence': intent_scores[best_intent],
                    'context_aware': True
                }
        
        # Default to search if no clear intent
        return {
            'intent': 'search_request',
            'confidence': 0.5,
            'context_aware': False
        }
    
    @staticmethod
    def _handle_contextual_response(message, expecting, context):
        """Handle responses based on conversation context"""
        
        if expecting == 'search_results':
            # User is responding to search results
            if any(word in message for word in ['yes', 'yeah', 'sure', 'ok', 'external', 'other']):
                return {'intent': 'request_external_search', 'confidence': 0.9, 'context_aware': True}
            elif any(word in message for word in ['no', 'nope', 'not now', 'stay', 'finda']):
                return {'intent': 'decline_external_search', 'confidence': 0.9, 'context_aware': True}
            elif any(word in message for word in ['first', '1st', 'top', 'number 1']):
                return {'intent': 'item_selection', 'confidence': 0.9, 'context_aware': True, 'selection': 0}
            elif any(word in message for word in ['second', '2nd', 'number 2']):
                return {'intent': 'item_selection', 'confidence': 0.9, 'context_aware': True, 'selection': 1}
            elif any(word in message for word in ['more info', 'details', 'tell me more']):
                return {'intent': 'more_details_request', 'confidence': 0.9, 'context_aware': True}
        
        elif expecting == 'category_selection':
            # User is responding to category browsing
            categories = context.get('last_categories_shown', [])
            for i, category in enumerate(categories):
                if category.lower() in message:
                    return {
                        'intent': 'category_selected', 
                        'confidence': 0.9, 
                        'context_aware': True,
                        'selected_category': category
                    }
        
        elif expecting == 'external_search_confirmation':
            # User is responding to external search offer
            if any(word in message for word in ['yes', 'yeah', 'sure', 'ok', 'go ahead']):
                return {'intent': 'confirm_external_search', 'confidence': 0.9, 'context_aware': True}
            elif any(word in message for word in ['no', 'nope', 'not now', 'skip']):
                return {'intent': 'decline_external_search', 'confidence': 0.9, 'context_aware': True}
        
        # Fallback to general intent detection
        return {'intent': 'unclear_response', 'confidence': 0.3, 'context_aware': True}
    
    @staticmethod
    def extract_search_terms(message, context=None):
        """Extract meaningful search terms from user message"""
        # Remove common stop words and intent words
        stop_words = {
            'i', 'need', 'want', 'looking', 'for', 'a', 'an', 'the', 'some', 'any',
            'find', 'search', 'buy', 'get', 'show', 'me', 'can', 'you', 'help',
            'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        # Clean message
        cleaned = re.sub(r'[^\w\s]', ' ', message.lower())
        words = [word for word in cleaned.split() if word not in stop_words and len(word) > 2]
        
        return ' '.join(words) if words else message


class ConversationFlowManager:
    """Main manager for handling conversation flow"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.context = ConversationContext(user_id)
        self.nlp = NaturalLanguageProcessor()
    
    def process_message(self, user_message):
        """Process user message and determine appropriate response strategy"""
        
        # Analyze user intent with context
        intent_analysis = self.nlp.analyze_user_intent(user_message, self.context)
        
        response_strategy = {
            'intent': intent_analysis['intent'],
            'confidence': intent_analysis['confidence'],
            'context_aware': intent_analysis.get('context_aware', False),
            'action_required': self._determine_action(intent_analysis),
            'context_data': self.context.context,
            'search_terms': None,
            'selected_item': None
        }
        
        # Extract additional data based on intent
        if intent_analysis['intent'] in ['search_request']:
            response_strategy['search_terms'] = self.nlp.extract_search_terms(
                user_message, self.context.context
            )
        
        elif intent_analysis['intent'] == 'item_selection':
            selection_index = intent_analysis.get('selection', 0)
            results = self.context.context.get('last_search_results', [])
            if selection_index < len(results):
                response_strategy['selected_item'] = results[selection_index]
        
        elif intent_analysis['intent'] == 'category_selected':
            response_strategy['selected_category'] = intent_analysis.get('selected_category')
        
        return response_strategy
    
    def _determine_action(self, intent_analysis):
        """Determine what action should be taken based on intent"""
        
        action_map = {
            'greeting': 'send_welcome',
            'thanks': 'send_thanks_response',
            'search_request': 'perform_finda_search',
            'browse_request': 'show_categories',
            'request_external_search': 'perform_external_search',
            'decline_external_search': 'encourage_finda',
            'confirm_external_search': 'perform_external_search',
            'item_selection': 'show_item_details',
            'category_selected': 'search_category',
            'more_details_request': 'show_detailed_info',
            'comparison_request': 'compare_items',
            'unclear_response': 'ask_clarification'
        }
        
        return action_map.get(intent_analysis['intent'], 'ask_clarification')
    
    def update_after_search(self, query, results):
        """Update context after search operation"""
        self.context.update_search_context(query, results)
    
    def update_after_categories(self, categories):
        """Update context after showing categories"""
        self.context.update_categories_context(categories)
    
    def set_external_pending(self, query):
        """Set external search as pending"""
        self.context.set_external_search_pending(query)
    
    def clear_context(self):
        """Clear conversation expectations"""
        self.context.clear_expectations()
    
    def add_exchange(self, user_input, bot_response):
        """Add conversation exchange to history"""
        self.context.add_to_history(user_input, bot_response)


# Response generators for different conversation states
class ContextualResponseGenerator:
    """Generate contextually appropriate responses"""
    
    @staticmethod
    def generate_item_details_response(selected_item, context):
        """Generate detailed response about a selected item"""
        if not selected_item:
            return "I'm not sure which item you're referring to. Could you be more specific?"
        
        return f"""
🔍 **{selected_item['name']}** - Detailed Info:

💰 **Price:** {selected_item['price']}
📍 **Location:** {selected_item['location']}
📦 **Type:** {selected_item['type'].title()}

This is one of our top-rated items on Finda! Would you like:
• Contact details for the seller
• Similar items in this category  
• More photos and specifications
• Add to your favorites

Just let me know what interests you most!
"""
    
    @staticmethod
    def generate_clarification_response(context):
        """Generate response when user intent is unclear"""
        last_action = context.get('last_action')
        
        if last_action == 'search':
            return """
I want to make sure I help you properly! Are you looking to:

1️⃣ Get more details about the items I showed you
2️⃣ Search for something different  
3️⃣ Browse our categories
4️⃣ Check other stores like Amazon/Jumia

Just let me know what you'd prefer!
"""
        
        return """
I'd love to help you better! You can:

🔍 **Search** - Tell me what you're looking for
📂 **Browse** - Say "categories" to explore
💬 **Chat** - Ask me anything about Finda

What sounds good to you?
"""
    
    @staticmethod
    def generate_encouragement_response(context):
        """Generate encouraging response to stay on Finda"""
        return """
Perfect choice! Staying with Finda is always smart! 🛍️

✅ **Why Finda wins:**
• 🚚 Lightning-fast local delivery  
• 💬 Chat directly with sellers
• 🏠 Support Nigerian businesses
• 💯 No international shipping headaches
• 🔒 Secure local transactions

What else can I help you discover on our marketplace?
"""