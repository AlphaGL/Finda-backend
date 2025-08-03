# enhanced_conversation_manager.py - FULLY ENHANCED & BUG-FIXED VERSION
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import json
import re
import logging

logger = logging.getLogger(__name__)

class ConversationContext:
    """
    ENHANCED: Manages conversation state and context with robust error handling
    """
    
    def __init__(self, user_id):
        self.user_id = str(user_id)  # Ensure string for cache key
        self.cache_key = f"conversation_context_{self.user_id}"
        self.context = self._load_context()
    
    def _load_context(self):
        """Load conversation context from cache with error handling"""
        try:
            context = cache.get(self.cache_key, {})
            default_context = {
                'last_action': None,
                'last_search_query': None,
                'last_search_results': [],
                'last_categories_shown': [],
                'pending_external_search': False,
                'conversation_stage': 'greeting',  
                'user_preferences': {},
                'last_bot_question': None,
                'expecting_response_to': None,
                'conversation_history': [],
                'last_update': timezone.now().isoformat(),
                'session_start': timezone.now().isoformat(),
                'interaction_count': 0
            }
            
            # Merge with defaults safely
            for key, value in default_context.items():
                if key not in context:
                    context[key] = value
            
            # Validate context data types
            context = self._validate_context(context)
            
            return context
            
        except Exception as e:
            logger.error(f"Context load error for user {self.user_id}: {str(e)}")
            return self._get_default_context()
    
    def _validate_context(self, context):
        """Validate and clean context data"""
        try:
            # Ensure required fields are proper types
            if not isinstance(context.get('last_search_results', []), list):
                context['last_search_results'] = []
            
            if not isinstance(context.get('last_categories_shown', []), list):
                context['last_categories_shown'] = []
            
            if not isinstance(context.get('conversation_history', []), list):
                context['conversation_history'] = []
            
            if not isinstance(context.get('user_preferences', {}), dict):
                context['user_preferences'] = {}
            
            # Limit history size to prevent bloat
            if len(context['conversation_history']) > 10:
                context['conversation_history'] = context['conversation_history'][-10:]
            
            # Limit search results size
            if len(context['last_search_results']) > 10:
                context['last_search_results'] = context['last_search_results'][:10]
            
            return context
            
        except Exception as e:
            logger.error(f"Context validation error: {str(e)}")
            return self._get_default_context()
    
    def _get_default_context(self):
        """Get safe default context"""
        return {
            'last_action': None,
            'last_search_query': None,
            'last_search_results': [],
            'last_categories_shown': [],
            'pending_external_search': False,
            'conversation_stage': 'greeting',
            'user_preferences': {},
            'last_bot_question': None,
            'expecting_response_to': None,
            'conversation_history': [],
            'last_update': timezone.now().isoformat(),
            'session_start': timezone.now().isoformat(),
            'interaction_count': 0
        }
    
    def save_context(self):
        """Save context to cache with error handling"""
        try:
            self.context['last_update'] = timezone.now().isoformat()
            self.context['interaction_count'] = self.context.get('interaction_count', 0) + 1
            
            # Validate before saving
            self.context = self._validate_context(self.context)
            
            cache.set(self.cache_key, self.context, timeout=3600)  # 1 hour
            
        except Exception as e:
            logger.error(f"Context save error for user {self.user_id}: {str(e)}")
    
    def update_search_context(self, query, results):
        """Update context after a search with robust handling"""
        try:
            # Safely serialize results
            serialized_results = []
            for item in results[:5]:  # Limit to top 5
                try:
                    is_product = hasattr(item, 'product_name')
                    
                    item_data = {
                        'id': getattr(item, 'id', None),
                        'name': (getattr(item, 'product_name', None) or 
                                getattr(item, 'service_name', 'Unknown')),
                        'type': 'product' if is_product else 'service',
                        'price': str(getattr(item, 'product_price', 
                                          getattr(item, 'starting_price', 0))),
                        'location': (item.get_full_location() 
                                   if hasattr(item, 'get_full_location') 
                                   else 'Location available')
                    }
                    serialized_results.append(item_data)
                    
                except Exception as item_error:
                    logger.error(f"Error serializing search result: {str(item_error)}")
                    continue
            
            self.context.update({
                'last_action': 'search',
                'last_search_query': str(query)[:200],  # Limit query length
                'last_search_results': serialized_results,
                'conversation_stage': 'search_results_shown',
                'expecting_response_to': 'search_results',
                'last_bot_question': 'Would you like more details about any of these items?'
            })
            
            self.save_context()
            
        except Exception as e:
            logger.error(f"Search context update error: {str(e)}")
    
    def update_after_categories(self, categories):
        """Update context after showing categories"""
        try:
            category_names = []
            for cat in categories:
                try:
                    category_names.append(str(cat.name))
                except:
                    continue
            
            self.context.update({
                'last_action': 'show_categories',
                'last_categories_shown': category_names[:20],  # Limit categories
                'conversation_stage': 'browsing_categories',
                'expecting_response_to': 'category_selection',
                'last_bot_question': 'What category interests you?'
            })
            
            self.save_context()
            
        except Exception as e:
            logger.error(f"Categories context update error: {str(e)}")
    
    def set_external_search_pending(self, query):
        """Set context for pending external search"""
        try:
            self.context.update({
                'pending_external_search': True,
                'conversation_stage': 'awaiting_external_confirmation',
                'expecting_response_to': 'external_search_confirmation',
                'last_bot_question': f'Should I search external stores for "{str(query)[:100]}"?'
            })
            
            self.save_context()
            
        except Exception as e:
            logger.error(f"External search pending error: {str(e)}")
    
    def clear_expectations(self):
        """Clear pending expectations"""
        try:
            self.context.update({
                'expecting_response_to': None,
                'last_bot_question': None,
                'pending_external_search': False,
                'conversation_stage': 'open'
            })
            
            self.save_context()
            
        except Exception as e:
            logger.error(f"Clear expectations error: {str(e)}")
    
    def add_to_history(self, user_input, bot_response):
        """Add exchange to conversation history"""
        try:
            if 'conversation_history' not in self.context:
                self.context['conversation_history'] = []
            
            # Truncate long messages
            user_input_short = str(user_input)[:200]
            bot_response_short = str(bot_response)[:300]
            
            self.context['conversation_history'].append({
                'user': user_input_short,
                'bot': bot_response_short,
                'timestamp': timezone.now().isoformat()
            })
            
            # Keep only last 10 exchanges
            if len(self.context['conversation_history']) > 10:
                self.context['conversation_history'] = self.context['conversation_history'][-10:]
            
            self.save_context()
            
        except Exception as e:
            logger.error(f"History update error: {str(e)}")
    
    def get_conversation_summary(self):
        """Get summary of conversation for analytics"""
        try:
            return {
                'total_interactions': self.context.get('interaction_count', 0),
                'conversation_stage': self.context.get('conversation_stage', 'unknown'),
                'last_search_query': self.context.get('last_search_query', ''),
                'results_shown': len(self.context.get('last_search_results', [])),
                'session_duration_minutes': self._calculate_session_duration()
            }
        except Exception as e:
            logger.error(f"Summary generation error: {str(e)}")
            return {}
    
    def _calculate_session_duration(self):
        """Calculate session duration in minutes"""
        try:
            start_time = timezone.datetime.fromisoformat(
                self.context.get('session_start', timezone.now().isoformat())
            )
            duration = timezone.now() - start_time
            return round(duration.total_seconds() / 60, 1)
        except:
            return 0


class NaturalLanguageProcessor:
    """
    ENHANCED: Advanced NLP with better conversation understanding
    """
    
    @staticmethod
    def analyze_user_intent(message, conversation_context):
        """Analyze user intent with comprehensive error handling"""
        try:
            if not message or len(message.strip()) < 1:
                return {
                    'intent': 'unclear_response',
                    'confidence': 0.1,
                    'context_aware': False
                }
            
            message_lower = message.lower().strip()
            context = conversation_context.context
            
            # Handle contextual responses first
            if context.get('expecting_response_to'):
                contextual_result = NaturalLanguageProcessor._handle_contextual_response(
                    message_lower, context['expecting_response_to'], context
                )
                if contextual_result:
                    return contextual_result
            
            # Enhanced intent patterns with confidence scoring
            intent_patterns = {
                'greeting': {
                    'patterns': ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'sup', 'howdy'],
                    'phrases': ['how are you', 'whats up', 'hey there'],
                    'confidence': 0.9
                },
                'thanks': {
                    'patterns': ['thank', 'thanks', 'appreciate', 'grateful', 'thx'],
                    'phrases': ['thank you', 'thanks a lot', 'much appreciated'],
                    'confidence': 0.8
                },
                'search_request': {
                    'patterns': ['looking for', 'need', 'want', 'find', 'search', 'buy', 'get', 'shopping'],
                    'phrases': ['i want to buy', 'looking to purchase', 'need to find'],
                    'confidence': 0.7
                },
                'browse_request': {
                    'patterns': ['browse', 'categories', 'explore', 'show me', 'what do you have'],
                    'phrases': ['show me categories', 'what categories do you have'],
                    'confidence': 0.8
                },
                'more_info_request': {
                    'patterns': ['more info', 'tell me more', 'details', 'more about', 'first one', 'second one'],
                    'phrases': ['tell me more about', 'more details about', 'i want to know more'],
                    'confidence': 0.7
                },
                'comparison_request': {
                    'patterns': ['compare', 'difference', 'which is better', 'vs', 'versus'],
                    'phrases': ['compare these', 'what is the difference', 'which one is better'],
                    'confidence': 0.7
                },
                'external_request': {
                    'patterns': ['external', 'amazon', 'jumia', 'other stores', 'outside finda'],
                    'phrases': ['check other stores', 'search on amazon', 'what about jumia'],
                    'confidence': 0.9
                },
                'positive_response': {
                    'patterns': ['yes', 'yeah', 'sure', 'ok', 'okay', 'alright', 'go ahead'],
                    'phrases': ['yes please', 'sounds good', 'go for it'],
                    'confidence': 0.7
                },
                'negative_response': {
                    'patterns': ['no', 'nope', 'not', 'skip', 'pass', 'nah'],
                    'phrases': ['no thanks', 'not interested', 'maybe later'],
                    'confidence': 0.7
                }
            }
            
            # Calculate intent scores
            intent_scores = {}
            for intent, config in intent_patterns.items():
                score = 0
                
                # Check direct patterns
                for pattern in config.get('patterns', []):
                    if pattern in message_lower:
                        score += config['confidence'] * 0.8
                
                # Check phrases (higher weight)
                for phrase in config.get('phrases', []):
                    if phrase in message_lower:
                        score += config['confidence'] * 1.2
                
                if score > 0:
                    intent_scores[intent] = min(score, 1.0)  # Cap at 1.0
            
            # Get highest scoring intent
            if intent_scores:
                best_intent = max(intent_scores, key=intent_scores.get)
                if intent_scores[best_intent] > 0.5:
                    return {
                        'intent': best_intent,
                        'confidence': intent_scores[best_intent],
                        'context_aware': True,
                        'all_scores': intent_scores
                    }
            
            # Check if it looks like a search query
            if len(message_lower) > 2 and not any(word in message_lower for word in ['what', 'how', 'when', 'where', 'why']):
                return {
                    'intent': 'search_request',
                    'confidence': 0.6,
                    'context_aware': False
                }
            
            # Default to unclear
            return {
                'intent': 'unclear_response',
                'confidence': 0.3,
                'context_aware': False
            }
            
        except Exception as e:
            logger.error(f"Intent analysis error: {str(e)}")
            return {
                'intent': 'unclear_response',
                'confidence': 0.1,
                'context_aware': False,
                'error': str(e)
            }
    
    @staticmethod
    def _handle_contextual_response(message, expecting, context):
        """Handle responses based on conversation context"""
        try:
            if expecting == 'search_results':
                # User is responding to search results
                if any(word in message for word in ['yes', 'yeah', 'sure', 'ok', 'external', 'other']):
                    return {'intent': 'request_external_search', 'confidence': 0.9, 'context_aware': True}
                elif any(word in message for word in ['no', 'nope', 'not now', 'stay', 'finda']):
                    return {'intent': 'decline_external_search', 'confidence': 0.9, 'context_aware': True}
                elif any(word in message for word in ['first', '1st', 'top', 'number 1', '1']):
                    return {'intent': 'item_selection', 'confidence': 0.9, 'context_aware': True, 'selection': 0}
                elif any(word in message for word in ['second', '2nd', 'number 2', '2']):
                    return {'intent': 'item_selection', 'confidence': 0.9, 'context_aware': True, 'selection': 1}
                elif any(word in message for word in ['third', '3rd', 'number 3', '3']):
                    return {'intent': 'item_selection', 'confidence': 0.9, 'context_aware': True, 'selection': 2}
                elif any(word in message for word in ['more info', 'details', 'tell me more']):
                    return {'intent': 'more_details_request', 'confidence': 0.9, 'context_aware': True}
            
            elif expecting == 'category_selection':
                # User is responding to category browsing
                categories = context.get('last_categories_shown', [])
                for category in categories:
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
            
            return None
            
        except Exception as e:
            logger.error(f"Contextual response error: {str(e)}")
            return None
    
    @staticmethod
    def extract_search_terms(message, context=None):
        """Extract meaningful search terms from user message"""
        try:
            if not message:
                return ""
            
            # Remove common stop words and intent words
            stop_words = {
                'i', 'need', 'want', 'looking', 'for', 'a', 'an', 'the', 'some', 'any',
                'find', 'search', 'buy', 'get', 'show', 'me', 'can', 'you', 'help',
                'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 
                'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                'please', 'thanks', 'thank', 'hello', 'hi', 'hey'
            }
            
            # Clean message
            cleaned = re.sub(r'[^\w\s]', ' ', message.lower())
            words = [word for word in cleaned.split() if word not in stop_words and len(word) > 2]
            
            # If we have context, check for reference to previous search
            if context and len(words) < 2:
                last_query = context.get('last_search_query', '')
                if last_query:
                    return last_query
            
            return ' '.join(words) if words else message
            
        except Exception as e:
            logger.error(f"Search term extraction error: {str(e)}")
            return str(message)[:100]  # Fallback to original message


class ConversationFlowManager:
    """
    ENHANCED: Main manager for handling conversation flow with robust error handling
    """
    
    def __init__(self, user_id):
        try:
            self.user_id = str(user_id)
            self.context = ConversationContext(user_id)
            self.nlp = NaturalLanguageProcessor()
        except Exception as e:
            logger.error(f"ConversationFlowManager init error: {str(e)}")
            self.user_id = str(user_id)
            self.context = None
            self.nlp = NaturalLanguageProcessor()
    
    def process_message(self, user_message):
        """Process user message and determine appropriate response strategy"""
        try:
            if not user_message or len(user_message.strip()) < 1:
                return {
                    'intent': 'unclear_response',
                    'confidence': 0.1,
                    'context_aware': False,
                    'action_required': 'ask_clarification',
                    'context_data': {},
                    'search_terms': None,
                    'selected_item': None
                }
            
            # Ensure context is available
            if not self.context:
                self.context = ConversationContext(self.user_id)
            
            # Analyze user intent with context
            intent_analysis = self.nlp.analyze_user_intent(user_message, self.context)
            
            response_strategy = {
                'intent': intent_analysis['intent'],
                'confidence': intent_analysis['confidence'],
                'context_aware': intent_analysis.get('context_aware', False),
                'action_required': self._determine_action(intent_analysis),
                'context_data': self.context.context if self.context else {},
                'search_terms': None,
                'selected_item': None
            }
            
            # Extract additional data based on intent
            if intent_analysis['intent'] in ['search_request']:
                response_strategy['search_terms'] = self.nlp.extract_search_terms(
                    user_message, self.context.context if self.context else None
                )
            
            elif intent_analysis['intent'] == 'item_selection':
                selection_index = intent_analysis.get('selection', 0)
                results = self.context.context.get('last_search_results', []) if self.context else []
                if selection_index < len(results):
                    response_strategy['selected_item'] = results[selection_index]
            
            elif intent_analysis['intent'] == 'category_selected':
                response_strategy['selected_category'] = intent_analysis.get('selected_category')
            
            return response_strategy
            
        except Exception as e:
            logger.error(f"Message processing error: {str(e)}")
            return {
                'intent': 'unclear_response',
                'confidence': 0.1,
                'context_aware': False,
                'action_required': 'ask_clarification',
                'context_data': {},
                'search_terms': None,
                'selected_item': None,
                'error': str(e)
            }
    
    def _determine_action(self, intent_analysis):
        """Determine what action should be taken based on intent"""
        try:
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
                'positive_response': 'handle_positive_response',
                'negative_response': 'handle_negative_response',
                'unclear_response': 'ask_clarification'
            }
            
            return action_map.get(intent_analysis['intent'], 'ask_clarification')
            
        except Exception as e:
            logger.error(f"Action determination error: {str(e)}")
            return 'ask_clarification'
    
    def update_after_search(self, query, results):
        """Update context after search operation"""
        try:
            if self.context:
                self.context.update_search_context(query, results)
        except Exception as e:
            logger.error(f"Search context update error: {str(e)}")
    
    def update_after_categories(self, categories):
        """Update context after showing categories"""
        try:
            if self.context:
                self.context.update_after_categories(categories)
        except Exception as e:
            logger.error(f"Categories context update error: {str(e)}")
    
    def set_external_pending(self, query):
        """Set external search as pending"""
        try:
            if self.context:
                self.context.set_external_search_pending(query)
        except Exception as e:
            logger.error(f"External pending error: {str(e)}")
    
    def clear_context(self):
        """Clear conversation expectations"""
        try:
            if self.context:
                self.context.clear_expectations()
        except Exception as e:
            logger.error(f"Clear context error: {str(e)}")
    
    def add_exchange(self, user_input, bot_response):
        """Add conversation exchange to history"""
        try:
            if self.context:
                self.context.add_to_history(user_input, bot_response)
        except Exception as e:
            logger.error(f"Add exchange error: {str(e)}")


# Response generators for different conversation states
class ContextualResponseGenerator:
    """
    ENHANCED: Generate contextually appropriate responses with error handling
    """
    
    @staticmethod
    def generate_item_details_response(selected_item, context):
        """Generate detailed response about a selected item"""
        try:
            if not selected_item:
                return "I'm not sure which item you're referring to. Could you be more specific?"
            
            name = selected_item.get('name', 'Unknown Item')
            price = selected_item.get('price', 'Contact for price')
            location = selected_item.get('location', 'Location available')
            item_type = selected_item.get('type', 'item').title()
            item_id = selected_item.get('id', '')
            
            response = f"""
🔍 **{name}** - Detailed Info:

💰 **Price:** {price}
📍 **Location:** {location}
📦 **Type:** {item_type}

This is one of our top-rated items on Finda! Would you like:
• Contact details for the seller
• Similar items in this category  
• More photos and specifications
• Add to your favorites

Just let me know what interests you most!
"""
            
            if item_id:
                response += f"\n🔗 [View Full Details](https://finda-six.vercel.app/{item_type.lower()}s/{item_id})"
            
            return response
            
        except Exception as e:
            logger.error(f"Item details response error: {str(e)}")
            return "Let me help you find detailed information about this item. What specific details do you need?"
    
    @staticmethod
    def generate_clarification_response(context):
        """Generate response when user intent is unclear"""
        try:
            last_action = context.get('last_action') if context else None
            
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
            
        except Exception as e:
            logger.error(f"Clarification response error: {str(e)}")
            return "How can I help you today? Try searching for something specific or say 'categories' to browse!"
    
    @staticmethod
    def generate_encouragement_response(context):
        """Generate encouraging response to stay on Finda"""
        try:
            return """
Perfect choice! Staying with Finda is always smart! 🛍️

✅ **Why Finda wins:**
• 🚚 Lightning-fast local delivery  
• 💬 Chat directly with sellers
• 🏠 Support Nigerian businesses  
• 💯 No international shipping hassles
• 🔒 Secure local transactions

What else can I help you discover on our marketplace?
"""
            
        except Exception as e:
            logger.error(f"Encouragement response error: {str(e)}")
            return "Great choice staying with Finda! What else can I help you find today?"


class ConversationAnalytics:
    """
    ENHANCED: Track conversation metrics and patterns with error handling
    """
    
    @staticmethod
    def log_conversation_event(user_id, event_type, data=None):
        """Log conversation events for analytics"""
        try:
            cache_key = f"conversation_events_{user_id}"
            
            events = cache.get(cache_key, [])
            
            event = {
                'type': str(event_type),
                'data': data or {},
                'timestamp': timezone.now().isoformat()
            }
            
            events.append(event)
            
            # Keep only last 50 events
            if len(events) > 50:
                events = events[-50:]
            
            cache.set(cache_key, events, timeout=86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Analytics logging error: {str(e)}")
    
    @staticmethod
    def get_conversation_insights(user_id):
        """Get insights about user's conversation patterns"""
        try:
            cache_key = f"conversation_events_{user_id}"
            events = cache.get(cache_key, [])
            
            if not events:
                return {}
            
            # Analyze patterns
            event_types = {}
            for event in events:
                event_type = event.get('type', 'unknown')
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
            
        except Exception as e:
            logger.error(f"Insights generation error: {str(e)}")
            return {}


# Utility functions for conversation flow
def extract_item_reference(message, search_results):
    """Extract which item user is referring to with error handling"""
    try:
        if not message or not search_results:
            return None
        
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
            try:
                item_name = result.get('name', '').lower()
                # Check if any significant word from item name is in the message
                name_words = [word for word in item_name.split() if len(word) > 3]
                for word in name_words:
                    if word in message_lower:
                        return i
            except:
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"Item reference extraction error: {str(e)}")
        return None


def generate_contextual_followup(last_action, results_count=0):
    """Generate appropriate follow-up questions based on context"""
    try:
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
        
    except Exception as e:
        logger.error(f"Followup generation error: {str(e)}")
        return "What would you like to do next?"


def detect_conversation_ending(message):
    """Detect if user is ending the conversation"""
    try:
        if not message:
            return False
        
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
        
    except Exception as e:
        logger.error(f"Conversation ending detection error: {str(e)}")
        return False


def generate_goodbye_response(user_context=None):
    """Generate appropriate goodbye response"""
    try:
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
        
    except Exception as e:
        logger.error(f"Goodbye response error: {str(e)}")
        return "Thanks for using Finda! See you soon! 😊"


# Export main classes and functions
__all__ = [
    'ConversationContext',
    'NaturalLanguageProcessor',
    'ConversationFlowManager', 
    'ContextualResponseGenerator',
    'ConversationAnalytics',
    'extract_item_reference',
    'generate_contextual_followup',
    'detect_conversation_ending',
    'generate_goodbye_response'
]