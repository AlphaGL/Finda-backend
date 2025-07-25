# chatbot/enhanced_gemini_client.py - Fully Dynamic AI-Powered Chatbot
import google.generativeai as genai
from django.conf import settings
from PIL import Image
import io
import json
import time
from typing import List, Dict, Any, Optional
import logging
from main.models import Products, Services, Category
from django.db.models import Q, Avg
import re

# Configure Gemini
try:
    api_key = getattr(settings, 'GOOGLE_API_KEY', None) or getattr(settings, 'GEMINI_API_KEY', None)
    if api_key:
        genai.configure(api_key=api_key)
    else:
        print("Warning: No Google API key found. Set GOOGLE_API_KEY in settings.")
except Exception as e:
    print(f"Error configuring Gemini: {e}")

# Model configurations
TEXT_MODEL = "gemini-2.0-flash-exp"
VISION_MODEL = "gemini-2.0-flash-exp"

# Set up logging
logger = logging.getLogger(__name__)

# Enhanced Dynamic System Prompt
DYNAMIC_FINDA_AI_SYSTEM_PROMPT = """
You are Finda AI, the most intelligent and adaptive shopping assistant for Finda Marketplace - Africa's premier e-commerce platform. You have full autonomy to understand, adapt, and respond to ANY user query while maintaining your core mission.

🧠 CORE INTELLIGENCE CAPABILITIES:
- Understand context changes and topic shifts naturally
- Detect when users are confused, frustrated, or need clarification
- Adapt your communication style based on user behavior
- Handle interruptions, tangents, and complex multi-part requests
- Provide personalized experiences based on conversation history
- Learn from user preferences throughout the conversation

🛍️ PRIMARY MISSION:
1. Help users find products and services on Finda FIRST
2. Provide comprehensive product/service information with complete details
3. If no internal matches found, suggest external alternatives
4. Handle voice queries, image searches, and text naturally
5. Maintain conversation context across topic changes
6. Build user trust through helpful, accurate responses

🎭 PERSONALITY & ADAPTABILITY:
- Friendly, professional, and genuinely helpful
- Enthusiastic about helping users find what they need
- Patient with confused or indecisive users
- Adaptable communication style (formal/casual based on user)
- Proactive in asking clarifying questions
- Empathetic to user frustrations or concerns
- Use appropriate emojis to enhance engagement

🔄 CONTEXT AWARENESS RULES:
1. ALWAYS maintain conversation history awareness
2. Detect topic changes and acknowledge them naturally
3. When users seem confused, ask clarifying questions
4. If users interrupt or change topics, smoothly transition
5. Remember user preferences mentioned earlier in conversation
6. Adapt search strategy based on previous queries
7. Recognize returning conversation patterns

🔍 SEARCH & RECOMMENDATION INTELLIGENCE:
- Analyze user intent from ANY type of message
- Extract preferences from casual conversation
- Suggest related products/services proactively
- Handle vague queries by asking smart follow-up questions
- Cross-reference user behavior to improve suggestions
- Understand product relationships and complementary items

📞 RESPONSE STRATEGIES:
1. **Topic Changes**: "I see you're now interested in [new topic]. Let me help you with that!"
2. **Confusion**: "I notice you might be unsure. Let me clarify..."
3. **Frustration**: "I understand this can be overwhelming. Let's simplify..."
4. **Vague Queries**: "To find exactly what you need, could you tell me..."
5. **Multiple Requests**: "I'll help you with both [item A] and [item B]. Let's start with..."

🎯 INTELLIGENT ACTIONS YOU CAN TAKE:
- Search products/services with flexible matching
- Extract and remember user preferences
- Provide detailed product comparisons
- Suggest alternatives and related items
- Handle price negotiations and budget constraints
- Provide shopping advice and recommendations
- Manage external source suggestions
- Track user satisfaction and adapt accordingly

🌍 FINDA MARKETPLACE KNOWLEDGE:
- Prioritize internal Finda inventory first
- Present results with full details: price, location, contact info, links
- Understand African market preferences and shopping patterns
- Know about product categories, brands, and local suppliers
- Aware of shipping, payment, and delivery options
- Familiar with service provider categories and expertise levels

🎨 CONVERSATION FLOW MANAGEMENT:
- Start conversations warmly and assess user needs
- Build rapport through natural conversation
- Guide users through decision-making processes
- Handle objections and concerns professionally
- Celebrate successful matches and purchases
- End conversations with satisfaction confirmation

CRITICAL INSTRUCTION: You have FULL AUTONOMY to interpret, understand, and respond to ANY user message in the most helpful way possible. Never say you can't understand or can't help - instead, ask clarifying questions or provide the best assistance you can based on available information.

AVAILABLE TOOLS CONTEXT:
- You can search Finda's product database
- You can search Finda's service provider database  
- You can access user preference history
- You can analyze uploaded images for product identification
- You can process voice messages that have been transcribed
- You can generate external source suggestions when needed

Remember: Your goal is to be the most helpful, intelligent, and adaptive shopping assistant possible while driving success for both users and the Finda marketplace.
"""

class EnhancedDynamicGeminiClient:
    def __init__(self):
        self.model_text = TEXT_MODEL
        self.model_vision = VISION_MODEL
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
        ]
        self.generation_config = {
            "temperature": 0.8,  # Higher for more creative responses
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 3000,  # Longer responses for complex queries
        }

    def process_dynamic_conversation(self, user_message: str, conversation_history: List[Dict], 
                                   user_context: Dict = None, image_analysis: Dict = None) -> Dict[str, Any]:
        """
        Main method to process any user message with full context awareness
        """
        try:
            # Build comprehensive context
            context = self._build_comprehensive_context(
                user_message, conversation_history, user_context, image_analysis
            )
            
            # Create dynamic prompt
            dynamic_prompt = self._create_dynamic_prompt(context)
            
            # Search internal databases
            search_results = self._intelligent_search(context)
            
            # Generate contextual response
            response = self._generate_contextual_response(dynamic_prompt, search_results, context)
            
            # Analyze response for next actions
            next_actions = self._analyze_response_for_actions(response, context)
            
            return {
                'response': response,
                'context_updated': self._extract_context_updates(response, context),
                'search_results': search_results,
                'next_actions': next_actions,
                'conversation_state': self._determine_conversation_state(context, response),
                'user_intent': context.get('detected_intent'),
                'confidence_score': context.get('confidence_score', 0.8)
            }
            
        except Exception as e:
            logger.error(f"Dynamic conversation processing error: {e}")
            return self._create_fallback_response(user_message, str(e))

    def _build_comprehensive_context(self, user_message: str, history: List[Dict], 
                                   user_context: Dict, image_analysis: Dict) -> Dict[str, Any]:
        """
        Build comprehensive context from all available information
        """
        context = {
            'current_message': user_message,
            'message_intent': self._detect_intent(user_message),
            'topic_change': self._detect_topic_change(user_message, history),
            'user_emotion': self._detect_user_emotion(user_message),
            'confusion_indicators': self._detect_confusion(user_message),
            'conversation_history': history[-10:] if history else [],  # Last 10 messages
            'user_preferences': self._extract_cumulative_preferences(history, user_context),
            'session_context': user_context or {},
            'image_context': image_analysis,
            'conversation_stage': self._determine_conversation_stage(history),
            'previous_searches': self._extract_previous_searches(history),
            'user_satisfaction_indicators': self._detect_satisfaction_indicators(history),
            'detected_intent': self._analyze_comprehensive_intent(user_message, history),
            'confidence_score': self._calculate_confidence(user_message, history)
        }
        
        return context

    def _detect_intent(self, message: str) -> str:
        """Enhanced intent detection with context awareness"""
        message_lower = message.lower()
        
        # Multiple intent patterns
        intents = {
            'greeting': ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening'],
            'search_product': ['looking for', 'need to buy', 'want to purchase', 'find me', 'search for'],
            'search_service': ['need help with', 'looking for service', 'hire someone', 'book appointment'],
            'compare': ['compare', 'difference between', 'which is better', 'vs', 'versus'],
            'price_inquiry': ['how much', 'price', 'cost', 'expensive', 'cheap', 'budget'],
            'location_specific': ['near me', 'in lagos', 'in abuja', 'local', 'nearby'],
            'confusion': ['confused', 'not sure', 'dont understand', 'help me understand', 'what do you mean'],
            'topic_change': ['actually', 'wait', 'instead', 'never mind', 'change of mind'],
            'dissatisfaction': ['not what i want', 'something else', 'not satisfied', 'different'],
            'confirmation': ['yes', 'no', 'okay', 'sure', 'exactly', 'that works'],
            'browse': ['show me categories', 'what do you have', 'browse', 'explore'],
            'external_request': ['check other sites', 'amazon', 'jumia', 'online stores']
        }
        
        detected_intents = []
        for intent, keywords in intents.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_intents.append(intent)
        
        # Return primary intent or 'general' if multiple/none
        if len(detected_intents) == 1:
            return detected_intents[0]
        elif 'topic_change' in detected_intents:
            return 'topic_change'
        elif 'confusion' in detected_intents:
            return 'confusion'
        elif detected_intents:
            return detected_intents[0]  # Return first detected
        else:
            return 'general_inquiry'

    def _detect_topic_change(self, message: str, history: List[Dict]) -> bool:
        """Detect if user is changing topics"""
        if not history:
            return False
            
        change_indicators = [
            'actually', 'wait', 'instead', 'never mind', 'forget that',
            'change of mind', 'different topic', 'something else',
            'on second thought', 'let me ask about', 'what about'
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in change_indicators)

    def _detect_user_emotion(self, message: str) -> str:
        """Detect user's emotional state"""
        message_lower = message.lower()
        
        emotions = {
            'frustrated': ['frustrated', 'annoying', 'not working', 'terrible', 'awful', 'hate'],
            'confused': ['confused', 'dont understand', 'not sure', 'unclear', 'lost', 'help'],
            'excited': ['excited', 'amazing', 'perfect', 'love it', 'awesome', 'great'],
            'impatient': ['quickly', 'fast', 'hurry', 'urgent', 'asap', 'immediately'],
            'satisfied': ['good', 'nice', 'helpful', 'thanks', 'perfect', 'exactly'],
            'dissatisfied': ['not good', 'not right', 'wrong', 'not what i wanted', 'different']
        }
        
        for emotion, keywords in emotions.items():
            if any(keyword in message_lower for keyword in keywords):
                return emotion
                
        return 'neutral'

    def _detect_confusion(self, message: str) -> List[str]:
        """Detect specific confusion indicators"""
        confusion_patterns = [
            'i dont understand',
            'what do you mean',
            'confused about',
            'not sure what',
            'dont know how',
            'can you explain',
            'not clear',
            'help me understand'
        ]
        
        message_lower = message.lower()
        found_indicators = [pattern for pattern in confusion_patterns if pattern in message_lower]
        return found_indicators

    def _extract_cumulative_preferences(self, history: List[Dict], user_context: Dict) -> Dict:
        """Extract and combine preferences from entire conversation"""
        preferences = user_context.get('preferences', {}) if user_context else {}
        
        # Analyze conversation history for additional preferences
        for message in history:
            if message.get('author') == 'user':
                content = message.get('content', '')
                # Extract preferences from each user message
                extracted = self._extract_preferences_from_text(content)
                for key, value in extracted.items():
                    if key in preferences:
                        if isinstance(preferences[key], list):
                            preferences[key] = list(set(preferences[key] + value))
                        else:
                            preferences[key] = value
                    else:
                        preferences[key] = value
        
        return preferences

    def _extract_preferences_from_text(self, text: str) -> Dict:
        """Extract preferences from text using pattern matching"""
        text_lower = text.lower()
        preferences = {}
        
        # Color preferences
        colors = ['red', 'blue', 'green', 'yellow', 'black', 'white', 'brown', 'gray', 'pink', 'purple', 'orange']
        found_colors = [color for color in colors if color in text_lower]
        if found_colors:
            preferences['colors'] = found_colors
        
        # Size preferences
        sizes = ['small', 'medium', 'large', 'xl', 'xxl', 'xs']
        found_sizes = [size for size in sizes if size in text_lower]
        if found_sizes:
            preferences['sizes'] = found_sizes
        
        # Price range extraction
        price_patterns = [
            r'under (\d+)', r'below (\d+)', r'less than (\d+)',
            r'between (\d+) and (\d+)', r'(\d+) to (\d+)',
            r'around (\d+)', r'about (\d+)'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                if len(matches[0]) == 2:  # Range
                    preferences['price_range'] = {'min': int(matches[0][0]), 'max': int(matches[0][1])}
                else:  # Single value
                    preferences['price_range'] = {'max': int(matches[0])}
                break
        
        # Brand preferences
        brands = ['nike', 'adidas', 'apple', 'samsung', 'sony', 'lg', 'hp', 'dell']
        found_brands = [brand for brand in brands if brand in text_lower]
        if found_brands:
            preferences['brands'] = found_brands
        
        return preferences

    def _determine_conversation_stage(self, history: List[Dict]) -> str:
        """Determine what stage of conversation we're in"""
        if not history:
            return 'initial'
        
        message_count = len([msg for msg in history if msg.get('author') == 'user'])
        
        if message_count <= 2:
            return 'greeting_exploration'
        elif message_count <= 5:
            return 'need_identification'
        elif message_count <= 10:
            return 'product_search_refinement'
        else:
            return 'decision_support'

    def _intelligent_search(self, context: Dict) -> Dict[str, Any]:
        """Perform intelligent search based on comprehensive context"""
        search_results = {
            'products': [],
            'services': [],
            'categories': [],
            'suggestions': []
        }
        
        try:
            # Build search query from context
            search_query = self._build_intelligent_search_query(context)
            
            if not search_query:
                return search_results
            
            # Search products
            products = Products.objects.filter(
                Q(product_name__icontains=search_query) |
                Q(product_description__icontains=search_query) |
                Q(product_brand__icontains=search_query) |
                Q(tags__icontains=search_query),
                product_status='published'
            )
            
            # Apply preference filters
            preferences = context.get('user_preferences', {})
            if preferences:
                products = self._apply_preference_filters(products, preferences)
            
            search_results['products'] = list(products[:8])
            
            # Search services if intent suggests it
            if context.get('detected_intent') in ['search_service', 'general_inquiry']:
                services = Services.objects.filter(
                    Q(service_name__icontains=search_query) |
                    Q(service_description__icontains=search_query) |
                    Q(provider_expertise__icontains=search_query),
                    service_status='published'
                )
                search_results['services'] = list(services[:5])
            
            # Get relevant categories
            categories = Category.objects.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query),
                is_active=True
            )
            search_results['categories'] = list(categories[:3])
            
        except Exception as e:
            logger.error(f"Intelligent search error: {e}")
        
        return search_results

    def _build_intelligent_search_query(self, context: Dict) -> str:
        """Build intelligent search query from context"""
        query_parts = []
        
        # Current message
        current_message = context.get('current_message', '')
        if current_message:
            query_parts.append(current_message)
        
        # Image analysis context
        image_context = context.get('image_context')
        if image_context:
            query_parts.extend([
                image_context.get('product_type', ''),
                image_context.get('brand', ''),
                image_context.get('description', '')
            ])
        
        # Previous search context if continuing conversation
        previous_searches = context.get('previous_searches', [])
        if previous_searches and not context.get('topic_change'):
            # Include recent search terms for context continuity
            query_parts.extend(previous_searches[-2:])
        
        # Filter out empty strings and combine
        query_parts = [part.strip() for part in query_parts if part and part.strip()]
        return ' '.join(query_parts)

    def _apply_preference_filters(self, queryset, preferences: Dict):
        """Apply user preferences to filter queryset"""
        # This is a simplified version - you can expand based on your model fields
        
        if preferences.get('colors'):
            color_q = Q()
            for color in preferences['colors']:
                color_q |= Q(product_description__icontains=color)
            queryset = queryset.filter(color_q)
        
        if preferences.get('price_range'):
            price_range = preferences['price_range']
            if price_range.get('min'):
                queryset = queryset.filter(product_price__gte=price_range['min'])
            if price_range.get('max'):
                queryset = queryset.filter(product_price__lte=price_range['max'])
        
        if preferences.get('brands'):
            brand_q = Q()
            for brand in preferences['brands']:
                brand_q |= Q(product_brand__icontains=brand)
            queryset = queryset.filter(brand_q)
        
        return queryset

    def _create_dynamic_prompt(self, context: Dict) -> str:
        """Create a dynamic prompt based on comprehensive context"""
        
        base_prompt = DYNAMIC_FINDA_AI_SYSTEM_PROMPT
        
        # Add context-specific instructions
        context_additions = []
        
        # Handle topic changes
        if context.get('topic_change'):
            context_additions.append("""
CONTEXT ALERT: User has changed topics. Acknowledge this change naturally and pivot to help with their new request.
""")
        
        # Handle confusion
        if context.get('confusion_indicators'):
            context_additions.append(f"""
CONTEXT ALERT: User seems confused about: {', '.join(context['confusion_indicators'])}. 
Provide clear, simple explanations and ask clarifying questions.
""")
        
        # Handle user emotion
        user_emotion = context.get('user_emotion', 'neutral')
        if user_emotion != 'neutral':
            context_additions.append(f"""
CONTEXT ALERT: User seems {user_emotion}. Adjust your response tone accordingly.
""")
        
        # Add conversation history context
        if context.get('conversation_history'):
            context_additions.append(f"""
CONVERSATION CONTEXT: You have been chatting with this user. Here's the recent conversation:
{self._format_conversation_history(context['conversation_history'])}
""")
        
        # Add search results context
        search_results = context.get('search_results', {})
        if search_results and any(search_results.values()):
            context_additions.append(f"""
SEARCH RESULTS AVAILABLE:
- Products found: {len(search_results.get('products', []))}
- Services found: {len(search_results.get('services', []))}
- Categories found: {len(search_results.get('categories', []))}

Use these results to provide comprehensive assistance.
""")
        
        # Add user preferences context
        preferences = context.get('user_preferences', {})
        if preferences:
            context_additions.append(f"""
USER PREFERENCES KNOWN:
{json.dumps(preferences, indent=2)}

Consider these preferences in your recommendations.
""")
        
        # Combine all context
        full_prompt = base_prompt + "\n".join(context_additions)
        
        return full_prompt

    def _format_conversation_history(self, history: List[Dict]) -> str:
        """Format conversation history for context"""
        formatted = []
        for msg in history[-6:]:  # Last 6 messages
            role = "User" if msg.get('author') == 'user' else "You"
            content = msg.get('content', '')[:100]  # Truncate long messages
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

    def _generate_contextual_response(self, prompt: str, search_results: Dict, context: Dict) -> str:
        """Generate response using Gemini with full context"""
        try:
            # Format search results for the prompt
            results_text = self._format_search_results_for_prompt(search_results)
            
            # Create the final prompt with search results
            final_prompt = f"""
{prompt}

CURRENT USER MESSAGE: "{context.get('current_message', '')}"

SEARCH RESULTS FROM FINDA DATABASE:
{results_text}

INSTRUCTIONS FOR THIS RESPONSE:
1. Address the user's current message directly
2. Use the search results to provide specific product/service recommendations
3. If no perfect matches, suggest alternatives or ask clarifying questions
4. Maintain conversation flow and acknowledge any context changes
5. Be helpful, natural, and engaging
6. Include specific product details, prices, and contact information when showing results
7. If no internal results, mention you'll check external sources

Respond naturally and helpfully:
"""

            # Initialize model
            model = genai.GenerativeModel(
                self.model_text, 
                safety_settings=self.safety_settings,
                generation_config=self.generation_config
            )
            
            # Generate response
            response = model.generate_content(final_prompt)
            
            if response and response.text:
                return response.text.strip()
            else:
                return self._create_default_response(context)
                
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return self._create_fallback_response_text(context, str(e))

    def _format_search_results_for_prompt(self, search_results: Dict) -> str:
        """Format search results for inclusion in prompt"""
        if not search_results or not any(search_results.values()):
            return "No specific matches found in Finda database."
        
        formatted_parts = []
        
        # Format products
        products = search_results.get('products', [])
        if products:
            formatted_parts.append("PRODUCTS FOUND:")
            for i, product in enumerate(products[:5], 1):
                formatted_parts.append(f"""
{i}. {product.product_name}
   Price: ₦{product.product_price:,.2f}
   Brand: {getattr(product, 'product_brand', 'N/A')}
   Location: {product.city.name if product.city else 'N/A'}, {product.state.name if product.state else 'N/A'}
   Description: {product.product_description[:150]}...
   Contact: {getattr(product, 'provider_phone', 'Contact via platform')}
   Status: {product.product_condition if hasattr(product, 'product_condition') else 'Available'}
""")
        
        # Format services
        services = search_results.get('services', [])
        if services:
            formatted_parts.append("\nSERVICES FOUND:")
            for i, service in enumerate(services[:3], 1):
                formatted_parts.append(f"""
{i}. {service.service_name}
   Provider: {getattr(service, 'provider_name', 'Service Provider')}
   Location: {service.city.name if service.city else 'N/A'}, {service.state.name if service.state else 'N/A'}
   Price: {getattr(service, 'starting_price', 'Contact for pricing')}
   Description: {service.service_description[:150]}...
   Contact: {getattr(service, 'provider_phone', 'Contact via platform')}
""")
        
        # Format categories
        categories = search_results.get('categories', [])
        if categories:
            formatted_parts.append("\nRELEVANT CATEGORIES:")
            for category in categories:
                formatted_parts.append(f"- {category.name}: {getattr(category, 'description', 'Browse this category')}")
        
        return "\n".join(formatted_parts) if formatted_parts else "No specific matches found."

    def _analyze_response_for_actions(self, response: str, context: Dict) -> List[str]:
        """Analyze the generated response to determine next actions"""
        actions = []
        
        response_lower = response.lower()
        
        # Check if external search needed
        if 'no matches' in response_lower or 'not found' in response_lower:
            actions.append('suggest_external_search')
        
        # Check if more clarification needed
        if '?' in response and ('could you' in response_lower or 'can you tell me' in response_lower):
            actions.append('awaiting_clarification')
        
        # Check if showing results
        if 'found' in response_lower and ('product' in response_lower or 'service' in response_lower):
            actions.append('results_presented')
        
        # Check if conversation ending
        if any(phrase in response_lower for phrase in ['hope this helps', 'let me know if', 'anything else']):
            actions.append('conversation_completion_offered')
        
        return actions

    def _extract_context_updates(self, response: str, context: Dict) -> Dict:
        """Extract context updates from the generated response"""
        updates = {}
        
        # Extract any new preferences mentioned in response
        response_lower = response.lower()
        
        # Update conversation stage based on response
        if 'let me search' in response_lower:
            updates['conversation_stage'] = 'searching'
        elif 'found' in response_lower:
            updates['conversation_stage'] = 'results_presented'
        elif '?' in response and 'tell me' in response_lower:
            updates['conversation_stage'] = 'gathering_requirements'
        
        return updates

    def _determine_conversation_state(self, context: Dict, response: str) -> str:
        """Determine the current state of conversation"""
        response_lower = response.lower()
        
        if 'hello' in response_lower or 'welcome' in response_lower:
            return 'greeting'
        elif '?' in response and ('tell me' in response_lower or 'could you' in response_lower):
            return 'gathering_info'
        elif 'found' in response_lower and 'product' in response_lower:
            return 'showing_results'
        elif 'external' in response_lower or 'other sites' in response_lower:
            return 'suggesting_external'
        elif 'hope this helps' in response_lower:
            return 'completion'
        else:
            return 'active_conversation'

    def _calculate_confidence(self, message: str, history: List[Dict]) -> float:
        """Calculate confidence score for the interaction"""
        confidence = 0.5  # Base confidence
        
        # Increase confidence for clear intent
        clear_intents = ['buy', 'search', 'find', 'looking for', 'need', 'want']
        if any(intent in message.lower() for intent in clear_intents):
            confidence += 0.2
        
        # Increase confidence for specific product mentions
        if len(message.split()) > 3:  # Detailed messages
            confidence += 0.1
        
        # Increase confidence for continuing conversation
        if history:
            confidence += 0.2
        
        return min(confidence, 1.0)

    def _extract_previous_searches(self, history: List[Dict]) -> List[str]:
        """Extract previous search queries from conversation history"""
        searches = []
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '')
                # Look for search-like patterns
                search_indicators = ['looking for', 'find', 'search', 'need', 'want to buy']
                if any(indicator in content.lower() for indicator in search_indicators):
                    searches.append(content)
        return searches[-3:]  # Last 3 searches

    def _detect_satisfaction_indicators(self, history: List[Dict]) -> str:
        """Detect user satisfaction from conversation history"""
        satisfaction_keywords = {
            'satisfied': ['perfect', 'exactly', 'great', 'thanks', 'helpful', 'good'],
            'unsatisfied': ['not what i want', 'different', 'not right', 'not good', 'something else'],
            'neutral': ['ok', 'okay', 'continue', 'next']
        }
        
        recent_messages = history[-3:] if len(history) >= 3 else history
        
        for msg in reversed(recent_messages):
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                for satisfaction_level, keywords in satisfaction_keywords.items():
                    if any(keyword in content for keyword in keywords):
                        return satisfaction_level
        
        return 'unknown'

    def _analyze_comprehensive_intent(self, message: str, history: List[Dict]) -> str:
        """Comprehensive intent analysis considering conversation history"""
        # Get basic intent
        basic_intent = self._detect_intent(message)
        
        # Modify based on conversation context
        if history:
            last_bot_message = None
            for msg in reversed(history):
                if msg.get('author') == 'assistant':
                    last_bot_message = msg.get('content', '').lower()
                    break
            
            if last_bot_message:
                # If bot asked a question, user is likely responding
                if '?' in last_bot_message:
                    if basic_intent == 'general_inquiry':
                        return 'responding_to_question'
                
                # If bot showed results, user might be evaluating
                if 'found' in last_bot_message and 'product' in last_bot_message:
                    if basic_intent == 'general_inquiry':
                        return 'evaluating_results'
        
        return basic_intent

    def _create_fallback_response(self, user_message: str, error: str) -> Dict[str, Any]:
        """Create fallback response when processing fails"""
        return {
            'response': f"I understand you're asking about '{user_message}'. Let me help you find what you're looking for on Finda! Could you tell me a bit more about what specific product or service you need?",
            'context_updated': {},
            'search_results': {'products': [], 'services': [], 'categories': []},
            'next_actions': ['awaiting_clarification'],
            'conversation_state': 'error_recovery',
            'user_intent': 'general_inquiry',
            'confidence_score': 0.3,
            'error': error
        }

    def _create_default_response(self, context: Dict) -> str:
        """Create default response when Gemini doesn't respond"""
        user_message = context.get('current_message', '')
        
        if context.get('detected_intent') == 'greeting':
            return "Hello! Welcome to Finda AI! 🛍️ I'm here to help you find amazing products and services. What are you looking for today?"
        
        return f"I'd be happy to help you with '{user_message}'. Let me search our Finda marketplace for you! Could you tell me a bit more about what you're looking for?"

    def _create_fallback_response_text(self, context: Dict, error: str) -> str:
        """Create fallback response text when generation fails"""
        return f"I'm here to help you find what you need on Finda! I understand you're asking about '{context.get('current_message', 'your request')}'. Let me know more details and I'll search our marketplace for you! 🛍️"

    def generate_external_suggestions(self, query: str, search_type: str, preferences: Dict = None) -> str:
        """Generate external suggestions using Gemini when no internal results found"""
        try:
            external_prompt = f"""
You are Finda AI helping a user find {search_type}s for: "{query}"

User preferences: {json.dumps(preferences) if preferences else "No specific preferences"}

Since we couldn't find matches in Finda's database, please generate realistic external shopping suggestions from popular platforms like:
- Jumia (Nigeria/Africa)
- Konga (Nigeria) 
- Amazon (with international shipping)
- AliExpress
- Other relevant e-commerce sites

Format your response as a helpful shopping assistant:

1. Acknowledge we searched Finda first but found limited matches
2. Present 3-4 realistic external options with:
   - Product/service name
   - Estimated price in Nigerian Naira (₦) or USD ($)
   - Platform/store name
   - Brief description
   - Any relevant details (shipping, ratings, etc.)
3. End with encouragement to check back on Finda or try different search terms

Be conversational, helpful, and maintain the Finda AI personality while being honest about external options.
"""

            model = genai.GenerativeModel(
                self.model_text,
                safety_settings=self.safety_settings,
                generation_config=self.generation_config
            )
            
            response = model.generate_content(external_prompt)
            
            if response and response.text:
                return response.text.strip()
            else:
                return self._create_fallback_external_response(query, search_type)
                
        except Exception as e:
            logger.error(f"External suggestions error: {e}")
            return self._create_fallback_external_response(query, search_type)

    def _create_fallback_external_response(self, query: str, search_type: str) -> str:
        """Fallback external response when AI generation fails"""
        return f"""
I searched our Finda marketplace for "{query}" but didn't find perfect matches right now. 

🌐 **You might find options on these external platforms:**
• **Jumia** - Nigeria's leading marketplace
• **Konga** - Wide variety of products
• **Amazon** - International shipping available
• **AliExpress** - Affordable options

💡 **Tip:** Try searching with different keywords, or check back on Finda as we add new {search_type}s daily!

🛍️ **Want to try a different search on Finda?** I'm here to help!
"""

    def analyze_image_with_context(self, image_file, additional_context: str = "") -> Optional[Dict[str, Any]]:
        """Enhanced image analysis with conversation context"""
        try:
            # Read and process image
            image_data = image_file.read()
            image_file.seek(0)
            
            # Create PIL Image object
            pil_image = Image.open(io.BytesIO(image_data))
            
            # Resize if too large
            max_size = (1024, 1024)
            if pil_image.size[0] > max_size[0] or pil_image.size[1] > max_size[1]:
                pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Enhanced analysis prompt with context awareness
            analysis_prompt = f"""
As Finda AI, analyze this product image with full intelligence and context awareness.

{f"Additional context from user: {additional_context}" if additional_context else ""}

Provide a comprehensive JSON analysis that I can use to:
1. Search our Finda product database effectively
2. Help the user find exactly what they're looking for
3. Suggest related or alternative products

Required JSON format:
{{
    "product_identification": {{
        "product_type": "specific product category/name",
        "category": "general category",
        "subcategory": "specific subcategory",
        "brand": "brand name if identifiable or null",
        "model": "model/version if visible or null"
    }},
    "visual_characteristics": {{
        "primary_color": "main color",
        "secondary_colors": ["color1", "color2"],
        "style": "style description",
        "material": "material type if identifiable",
        "size_indicators": "any size info visible",
        "condition": "new/used/worn assessment"
    }},
    "search_optimization": {{
        "primary_keywords": ["keyword1", "keyword2", "keyword3"],
        "alternative_keywords": ["alt1", "alt2", "alt3"],
        "category_suggestions": ["cat1", "cat2"],
        "brand_suggestions": ["brand1", "brand2"]
    }},
    "market_intelligence": {{
        "estimated_price_range": {{"min": 0, "max": 0, "currency": "NGN"}},
        "target_audience": "who would buy this",
        "seasonal_relevance": "any seasonal aspects",
        "complementary_products": ["item1", "item2"]
    }},
    "user_assistance": {{
        "detailed_description": "comprehensive description for user",
        "key_features": ["feature1", "feature2", "feature3"],
        "search_suggestions": ["suggestion1", "suggestion2"],
        "questions_to_ask_user": ["question1", "question2"]
    }},
    "analysis_metadata": {{
        "confidence_score": 0.85,
        "analysis_quality": "high/medium/low",
        "recommendation": "what to do next"
    }}
}}

Be thorough, accurate, and focus on helping the user find what they need on Finda marketplace.
"""
            
            # Initialize vision model
            model = genai.GenerativeModel(self.model_vision)
            
            # Generate analysis
            response = model.generate_content([analysis_prompt, pil_image])
            
            if response and response.text:
                # Clean and parse JSON response
                json_text = response.text.strip()
                
                # Remove markdown formatting if present
                if '```json' in json_text:
                    json_text = json_text.split('```json')[1].split('```')[0].strip()
                elif '```' in json_text:
                    json_text = json_text.split('```')[1].strip()
                
                try:
                    analysis_result = json.loads(json_text)
                    
                    # Add metadata
                    analysis_result['processing_metadata'] = {
                        'analysis_timestamp': time.time(),
                        'image_dimensions': {'width': pil_image.width, 'height': pil_image.height},
                        'analysis_engine': self.model_vision,
                        'context_provided': bool(additional_context)
                    }
                    
                    return analysis_result
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed: {e}. Raw response: {json_text[:200]}")
                    return self._create_fallback_image_analysis(response.text, pil_image)
            
            return None
            
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return None

    def _create_fallback_image_analysis(self, raw_text: str, image: Image.Image) -> Dict[str, Any]:
        """Create fallback analysis when JSON parsing fails"""
        return {
            "product_identification": {
                "product_type": "unidentified product",
                "category": "general"
            },
            "visual_characteristics": {
                "primary_color": "unknown",
                "condition": "unknown"
            },
            "search_optimization": {
                "primary_keywords": self._extract_keywords_from_text(raw_text),
                "alternative_keywords": []
            },
            "user_assistance": {
                "detailed_description": raw_text[:300] if raw_text else "Image analysis failed",
                "questions_to_ask_user": [
                    "Could you describe what product this is?",
                    "What specific details are you looking for?"
                ]
            },
            "analysis_metadata": {
                "confidence_score": 0.2,
                "analysis_quality": "low",
                "recommendation": "ask_user_for_details"
            },
            "processing_metadata": {
                "analysis_method": "fallback_text_analysis",
                "image_dimensions": {"width": image.width, "height": image.height}
            }
        }

    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        if not text:
            return []
        
        import re
        
        # Remove common words
        common_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'can', 'image', 'shows',
            'appears', 'seems', 'looks', 'product', 'item'
        }
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [word for word in words if word not in common_words]
        
        # Return unique keywords, limited to 10
        return list(set(keywords))[:10]

    def process_voice_with_context(self, transcribed_text: str, conversation_context: Dict = None) -> Dict[str, Any]:
        """Process voice message with full context awareness"""
        try:
            # Enhanced voice processing prompt
            voice_prompt = f"""
As Finda AI, analyze this voice message transcription with full context awareness:

TRANSCRIBED TEXT: "{transcribed_text}"

CONVERSATION CONTEXT: {json.dumps(conversation_context, indent=2) if conversation_context else "No prior context"}

Provide a comprehensive analysis in JSON format:
{{
    "intent_analysis": {{
        "primary_intent": "main user intent",
        "confidence": 0.85,
        "intent_clarity": "clear/unclear/ambiguous"
    }},
    "content_extraction": {{
        "main_request": "what user wants",
        "preferences_mentioned": {{}},
        "specific_details": [],
        "urgency_level": "low/medium/high"
    }},
    "context_awareness": {{
        "relates_to_previous": true/false,
        "topic_continuation": true/false,
        "new_topic_started": true/false,
        "clarification_needed": true/false
    }},
    "response_guidance": {{
        "recommended_approach": "how to respond",
        "search_suggestions": [],
        "questions_to_ask": [],
        "tone_recommendation": "casual/formal/empathetic"
    }},
    "technical_quality": {{
        "transcription_confidence": 0.85,
        "audio_clarity_assessment": "good/fair/poor",
        "processing_notes": "any issues"
    }}
}}

Focus on understanding the user's true intent and providing guidance for the best response.
"""

            model = genai.GenerativeModel(
                self.model_text,
                safety_settings=self.safety_settings,
                generation_config=self.generation_config
            )
            
            response = model.generate_content(voice_prompt)
            
            if response and response.text:
                json_text = response.text.strip()
                if '```json' in json_text:
                    json_text = json_text.split('```json')[1].split('```')[0].strip()
                
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    pass
        
        except Exception as e:
            logger.error(f"Voice processing error: {e}")
        
        # Fallback analysis
        return {
            "intent_analysis": {
                "primary_intent": "general_inquiry",
                "confidence": 0.5,
                "intent_clarity": "unclear"
            },
            "content_extraction": {
                "main_request": transcribed_text,
                "preferences_mentioned": {},
                "specific_details": [],
                "urgency_level": "medium"
            },
            "context_awareness": {
                "relates_to_previous": False,
                "topic_continuation": False,
                "new_topic_started": True,
                "clarification_needed": True
            },
            "response_guidance": {
                "recommended_approach": "ask_for_clarification",
                "search_suggestions": [],
                "questions_to_ask": ["Could you tell me more about what you're looking for?"],
                "tone_recommendation": "casual"
            },
            "technical_quality": {
                "transcription_confidence": 0.7,
                "audio_clarity_assessment": "fair",
                "processing_notes": "Used fallback analysis"
            }
        }

# Create global instance
enhanced_gemini_client = EnhancedDynamicGeminiClient()