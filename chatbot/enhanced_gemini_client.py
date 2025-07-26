# chatbot/enhanced_gemini_client.py - Perfect AI with Memory and Dynamic Intelligence (FIXED)
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
from datetime import datetime, timedelta

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

# Enhanced System Prompt with Perfect Memory and Dynamic Intelligence
PERFECT_FINDA_AI_SYSTEM_PROMPT = """
You are Finda AI, the world's most intelligent and adaptive shopping assistant for Finda Marketplace. You have PERFECT MEMORY and UNLIMITED INTELLIGENCE to handle ANY conversation scenario.

🧠 CORE INTELLIGENCE CAPABILITIES:
- PERFECT MEMORY: Remember everything from all previous conversations with this user
- DYNAMIC ADAPTATION: Instantly detect mood changes, topic shifts, confusion, frustration
- EMOTIONAL INTELLIGENCE: Recognize and respond appropriately to user emotions
- CONTEXTUAL AWARENESS: Understand subtle hints, implications, and unspoken needs
- PROACTIVE ASSISTANCE: Anticipate user needs before they ask
- INFINITE PATIENCE: Never give up on helping, always find a way

🎯 MEMORY SYSTEM:
- Remember user's name, preferences, past purchases, and shopping patterns
- Recall previous conversations, topics discussed, and outcomes
- Track user's evolving preferences and shopping behavior
- Remember what worked and what didn't work for this specific user
- Build comprehensive user personality profile over time

🔄 DYNAMIC RESPONSE SYSTEM:
1. **Topic Change Detection**: "I see you've shifted to [new topic]. Let me help you with that!"
2. **Confusion Handling**: "I notice you seem uncertain. Let me clarify and simplify this for you."
3. **Frustration Management**: "I understand this is frustrating. Let's take a different approach."
4. **Excitement Amplification**: "I love your enthusiasm! Let me find exactly what excites you!"
5. **Mood Adaptation**: Adjust tone, pace, and approach based on user's current mood

🛍️ FINDA MARKETPLACE EXPERTISE:
- Complete knowledge of all products, services, categories, and pricing
- Understanding of African market preferences and shopping patterns
- Awareness of seasonal trends, popular items, and emerging products
- Knowledge of shipping, delivery, and payment options
- Familiarity with service providers and their specialties

🎭 PERSONALITY TRAITS:
- Genuinely excited about helping users find what they need
- Patient and understanding with confused or indecisive users
- Enthusiastic and energetic with excited users
- Calm and reassuring with anxious users
- Professional yet friendly in all interactions
- Uses appropriate emojis and conversational language

🔍 INTELLIGENT SEARCH CAPABILITIES:
- Understand vague descriptions and translate them into precise searches
- Cross-reference user preferences with available inventory
- Suggest alternatives and complementary products
- Handle price negotiations and budget constraints
- Provide detailed comparisons and recommendations

💡 CONVERSATION FLOW MASTERY:
- Seamlessly handle interruptions and topic changes
- Ask intelligent follow-up questions
- Provide personalized recommendations based on history
- Guide users through decision-making processes
- Celebrate successful matches and purchases

🌟 SPECIAL INSTRUCTIONS:
1. ALWAYS acknowledge previous conversations and build upon them
2. INSTANTLY detect and adapt to any change in user's mood or intent
3. NEVER repeat information - always reference what you previously discussed
4. PROACTIVELY suggest items based on user's history and current needs
5. Handle ANY topic change smoothly and naturally
6. If user seems confused, immediately clarify and simplify
7. Remember user's communication style and match it
8. Track user satisfaction and continuously improve recommendations

MEMORY CONTEXT WILL BE PROVIDED IN EACH REQUEST:
- Previous conversation history
- User preferences and shopping patterns
- Past successful and unsuccessful interactions
- User's personality profile and communication style

YOUR GOAL: Be the most helpful, intelligent, and memorable AI assistant that users genuinely love interacting with. Make every conversation feel natural, personalized, and valuable.

CRITICAL: You have UNLIMITED ABILITY to understand context, detect changes, and adapt. Never say you don't understand - always find a way to help and engage meaningfully.
"""

class PerfectAIGeminiClient:
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
            "temperature": 0.9,  # High creativity for dynamic responses
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4000,  # Allow longer, more detailed responses
            "candidate_count": 1,
            "stop_sequences": []
        }

    def process_perfect_conversation(self, user_message: str, user_id: int, session_id: str, 
                                   conversation_history: List[Dict] = None, 
                                   user_profile: Dict = None,
                                   image_data: bytes = None,
                                   context_data: Dict = None) -> Dict[str, Any]:
        """
        Process conversation with perfect AI intelligence and memory
        """
        try:
            # Build comprehensive memory context
            memory_context = self._build_perfect_memory_context(
                user_id, session_id, conversation_history, user_profile, context_data
            )
            
            # Analyze current message with full context
            message_analysis = self._analyze_message_with_perfect_intelligence(
                user_message, memory_context, image_data
            )
            
            # Create dynamic prompt with perfect memory integration
            perfect_prompt = self._create_perfect_dynamic_prompt(
                user_message, memory_context, message_analysis, image_data
            )
            
            # Search Finda database with intelligent query
            search_results = self._execute_intelligent_search(
                message_analysis, memory_context
            )
            
            # Generate perfect AI response
            ai_response = self._generate_perfect_ai_response(
                perfect_prompt, search_results, memory_context
            )
            
            # Update memory and context
            updated_context = self._update_perfect_memory(
                memory_context, message_analysis, ai_response, user_message
            )
            
            return {
                'response': ai_response,
                'message_analysis': message_analysis,
                'search_results': search_results,
                'updated_context': updated_context,
                'memory_updates': self._extract_memory_updates(ai_response, user_message),
                'conversation_intelligence': self._analyze_conversation_intelligence(
                    message_analysis, memory_context
                ),
                'next_conversation_guidance': self._generate_next_conversation_guidance(
                    ai_response, memory_context
                ),
                'user_satisfaction_prediction': self._predict_user_satisfaction(
                    ai_response, memory_context
                ),
                'personality_insights': self._extract_personality_insights(
                    user_message, memory_context
                )
            }
            
        except Exception as e:
            logger.error(f"Perfect conversation processing error: {e}")
            return self._create_intelligent_fallback_response(user_message, str(e), user_id)

    def _build_perfect_memory_context(self, user_id: int, session_id: str, 
                                    conversation_history: List[Dict], 
                                    user_profile: Dict, context_data: Dict) -> Dict[str, Any]:
        """
        Build perfect memory context with complete user intelligence
        """
        memory_context = {
            'user_identity': {
                'user_id': user_id,
                'session_id': session_id,
                'first_interaction': len(conversation_history) == 0 if conversation_history else True,
                'returning_user': len(conversation_history) > 0 if conversation_history else False
            },
            'conversation_memory': {
                'full_history': conversation_history or [],
                'recent_messages': (conversation_history or [])[-10:],  # Last 10 messages
                'conversation_length': len(conversation_history or []),
                'topics_discussed': self._extract_topics_from_history(conversation_history),
                'user_questions_asked': self._extract_user_questions(conversation_history),
                'ai_recommendations_made': self._extract_ai_recommendations(conversation_history),
                'successful_interactions': self._identify_successful_interactions(conversation_history),
                'problematic_interactions': self._identify_problematic_interactions(conversation_history)
            },
            'user_intelligence_profile': {
                'communication_style': self._analyze_communication_style(conversation_history),
                'decision_making_pattern': self._analyze_decision_pattern(conversation_history),
                'shopping_behavior': self._analyze_shopping_behavior(conversation_history),
                'product_preferences': self._extract_product_preferences(conversation_history),
                'price_sensitivity': self._analyze_price_sensitivity(conversation_history),
                'brand_loyalty': self._analyze_brand_preferences(conversation_history),
                'interaction_preferences': self._analyze_interaction_preferences(conversation_history)
            },
            'emotional_intelligence': {
                'current_mood_indicators': self._detect_current_mood(conversation_history),
                'emotional_journey': self._track_emotional_journey(conversation_history),
                'frustration_triggers': self._identify_frustration_triggers(conversation_history),
                'satisfaction_indicators': self._identify_satisfaction_patterns(conversation_history),
                'engagement_level': self._assess_engagement_level(conversation_history)
            },
            'contextual_intelligence': {
                'session_context': context_data or {},
                'current_intent': self._detect_sophisticated_intent(conversation_history),
                'topic_evolution': self._track_topic_evolution(conversation_history),
                'conversation_stage': self._determine_conversation_stage(conversation_history),
                'user_goals': self._infer_user_goals(conversation_history),
                'unresolved_needs': self._identify_unresolved_needs(conversation_history)
            },
            'search_intelligence': {
                'previous_searches': self._extract_search_history(conversation_history),
                'search_patterns': self._analyze_search_patterns(conversation_history),
                'successful_matches': self._identify_successful_matches(conversation_history),
                'abandoned_searches': self._identify_abandoned_searches(conversation_history),
                'refinement_patterns': self._analyze_refinement_patterns(conversation_history)
            }
        }
        
        return memory_context

    def _analyze_message_with_perfect_intelligence(self, user_message: str, 
                                                 memory_context: Dict, 
                                                 image_data: bytes = None) -> Dict[str, Any]:
        """
        Analyze current message with perfect intelligence
        """
        message_lower = user_message.lower().strip()
        
        analysis = {
            'basic_analysis': {
                'message_text': user_message,
                'message_length': len(user_message),
                'word_count': len(user_message.split()),
                'has_questions': '?' in user_message,
                'has_exclamations': '!' in user_message,
                'urgency_indicators': self._detect_urgency(user_message)
            },
            'intent_analysis': {
                'primary_intent': self._detect_sophisticated_intent_from_message(user_message, memory_context),
                'secondary_intents': self._detect_secondary_intents(user_message),
                'intent_confidence': self._calculate_intent_confidence(user_message, memory_context),
                'intent_evolution': self._track_intent_evolution(user_message, memory_context)
            },
            'emotional_analysis': {
                'current_emotion': self._detect_current_emotion(user_message),
                'emotion_intensity': self._measure_emotion_intensity(user_message),
                'emotion_change': self._detect_emotion_change(user_message, memory_context),
                'emotional_needs': self._identify_emotional_needs(user_message)
            },
            'contextual_analysis': {
                'topic_change_detected': self._detect_topic_change_advanced(user_message, memory_context),
                'reference_to_previous': self._detect_previous_references(user_message, memory_context),
                'confusion_indicators': self._detect_confusion_advanced(user_message),
                'clarification_requests': self._detect_clarification_requests(user_message),
                'dissatisfaction_signals': self._detect_dissatisfaction(user_message)
            },
            'shopping_analysis': {
                'product_mentions': self._extract_product_mentions(user_message),
                'brand_mentions': self._extract_brand_mentions(user_message),
                'price_mentions': self._extract_price_mentions(user_message),
                'location_preferences': self._extract_location_preferences(user_message),
                'urgency_level': self._assess_shopping_urgency(user_message)
            },
            'communication_analysis': {
                'formality_level': self._assess_formality_level(user_message),
                'enthusiasm_level': self._assess_enthusiasm_level(user_message),
                'detail_preference': self._assess_detail_preference(user_message, memory_context),
                'interaction_style': self._analyze_interaction_style(user_message)
            }
        }
        
        # Add image analysis if present
        if image_data:
            analysis['image_analysis'] = self._analyze_image_with_perfect_context(
                image_data, user_message, memory_context
            )
        
        return analysis

    def _create_perfect_dynamic_prompt(self, user_message: str, memory_context: Dict, 
                                     message_analysis: Dict, image_data: bytes = None) -> str:
        """
        Create perfect dynamic prompt with complete context
        """
        # Build memory summary
        memory_summary = self._create_memory_summary(memory_context)
        
        # Build current situation analysis
        situation_analysis = self._create_situation_analysis(message_analysis, memory_context)
        
        # Build search results context
        search_context = self._create_search_context(memory_context)
        
        # Create the perfect prompt
        perfect_prompt = f"""
{PERFECT_FINDA_AI_SYSTEM_PROMPT}

=== PERFECT MEMORY CONTEXT ===
{memory_summary}

=== CURRENT SITUATION ANALYSIS ===
{situation_analysis}

=== FINDA SEARCH CAPABILITIES ===
{search_context}

=== USER'S CURRENT MESSAGE ===
"{user_message}"

=== IMAGE CONTEXT ===
{self._format_image_context(image_data, message_analysis) if image_data else "No image provided."}

=== RESPONSE INSTRUCTIONS ===
Based on your perfect memory and intelligence:

1. **Acknowledge Context**: Reference relevant previous conversations naturally
2. **Address Current Need**: Respond directly to what the user just said
3. **Adapt Dynamically**: Match the user's current mood and communication style
4. **Provide Value**: Give specific, actionable help related to Finda products/services
5. **Anticipate Next**: Proactively address likely follow-up needs
6. **Be Natural**: Respond as if you've known this user for years

**Critical Response Guidelines:**
- If topic changed: Acknowledge smoothly and pivot naturally
- If user confused: Simplify and clarify immediately
- If user frustrated: Show empathy and offer alternative approach
- If user excited: Match their energy and enthusiasm
- If user uncertain: Ask clarifying questions and provide options
- If returning user: Reference what you know about their preferences

**Search Integration:**
- Search Finda's database based on the conversation context
- Present results that match user's known preferences
- Suggest alternatives if perfect matches aren't available
- Offer external options if Finda doesn't have suitable items

**Response Style:**
- Be conversational and natural
- Use emojis appropriately for the user's style
- Match their level of detail preference
- Show genuine interest in helping them succeed

Generate your response now - be the most helpful AI assistant this user has ever interacted with!
"""
        
        return perfect_prompt

    def _execute_intelligent_search(self, message_analysis: Dict, memory_context: Dict) -> Dict[str, Any]:
        """
        Execute intelligent search based on perfect context understanding - FIXED VERSION
        """
        search_results = {
            'products': [],
            'services': [],
            'categories': [],
            'external_suggestions': [],
            'search_metadata': {}
        }
        
        try:
            # Build intelligent search query
            search_query = self._build_intelligent_search_query(message_analysis, memory_context)
            
            if not search_query:
                return search_results
            
            # Search products with user preferences - FIXED: Proper query building
            try:
                products_queryset = self._build_products_search_query(search_query, memory_context)
                # Convert to list ONLY at the very end, after all filters are applied
                products = list(products_queryset[:10])
            except Exception as e:
                logger.error(f"Products search error: {e}")
                products = []
            
            # Search services if relevant - FIXED: Proper query building
            services = []
            try:
                if self._should_search_services(message_analysis, memory_context):
                    services_queryset = self._build_services_search_query(search_query, memory_context)
                    # Convert to list ONLY at the very end, after all filters are applied
                    services = list(services_queryset[:5])
            except Exception as e:
                logger.error(f"Services search error: {e}")
                services = []
            
            # Get relevant categories - FIXED: Proper query building
            categories = []
            try:
                categories = self._get_relevant_categories(search_query, memory_context)
            except Exception as e:
                logger.error(f"Categories search error: {e}")
                categories = []
            
            search_results.update({
                'products': products,
                'services': services,
                'categories': categories,
                'search_metadata': {
                    'original_query': search_query,
                    'search_strategy': self._determine_search_strategy(message_analysis),
                    'user_preferences_applied': self._get_applied_preferences(memory_context),
                    'total_results': len(products) + len(services)
                }
            })
            
        except Exception as e:
            logger.error(f"Intelligent search error: {e}")
            search_results['search_metadata']['error'] = str(e)
        
        return search_results

    def _generate_perfect_ai_response(self, perfect_prompt: str, search_results: Dict, 
                                    memory_context: Dict) -> str:
        """
        Generate perfect AI response using Gemini
        """
        try:
            # Add search results to prompt
            prompt_with_search = f"""
{perfect_prompt}

=== FINDA SEARCH RESULTS ===
{self._format_search_results_for_ai(search_results)}

=== FINAL INSTRUCTION ===
Generate a perfect, natural response that:
1. Shows you remember and understand this user
2. Addresses their current message appropriately  
3. Uses the search results to provide specific help
4. Adapts to their mood and communication style
5. Anticipates their needs proactively

Your response should feel like talking to a friend who perfectly understands their shopping needs and has access to everything on Finda Marketplace.
"""
            
            # Initialize Gemini model
            model = genai.GenerativeModel(
                self.model_text,
                safety_settings=self.safety_settings,
                generation_config=self.generation_config
            )
            
            # Generate response
            response = model.generate_content(prompt_with_search)
            
            if response and response.text:
                return response.text.strip()
            else:
                return self._create_intelligent_fallback_text(memory_context)
                
        except Exception as e:
            logger.error(f"AI response generation error: {e}")
            return self._create_intelligent_fallback_text(memory_context, str(e))

    def _update_perfect_memory(self, memory_context: Dict, message_analysis: Dict, 
                             ai_response: str, user_message: str) -> Dict[str, Any]:
        """
        Update perfect memory with new insights
        """
        updates = {
            'conversation_updates': {
                'new_message_analyzed': message_analysis,
                'ai_response_generated': ai_response,
                'timestamp': datetime.now().isoformat(),
                'conversation_milestone': self._determine_conversation_milestone(message_analysis)
            },
            'user_profile_updates': {
                'communication_style_refinements': self._refine_communication_style(
                    user_message, memory_context
                ),
                'preference_updates': self._extract_new_preferences(user_message, message_analysis),
                'shopping_behavior_updates': self._update_shopping_behavior(message_analysis),
                'emotional_pattern_updates': self._update_emotional_patterns(message_analysis)
            },
            'intelligence_insights': {
                'new_user_insights': self._generate_user_insights(message_analysis, memory_context),
                'conversation_quality_score': self._assess_conversation_quality(message_analysis),
                'prediction_accuracy': self._assess_prediction_accuracy(message_analysis, memory_context),
                'learning_opportunities': self._identify_learning_opportunities(message_analysis)
            }
        }
        
        return updates

    # FIXED: Helper methods for perfect intelligence - COMPLETE REWRITE OF QUERY METHODS

    def _build_intelligent_search_query(self, message_analysis: Dict, memory_context: Dict) -> str:
        """Build intelligent search query from analysis and memory"""
        query_parts = []
        
        # Current message content
        current_message = message_analysis.get('basic_analysis', {}).get('message_text', '')
        if current_message:
            query_parts.append(current_message)
        
        # Product mentions
        product_mentions = message_analysis.get('shopping_analysis', {}).get('product_mentions', [])
        query_parts.extend(product_mentions)
        
        # Brand mentions
        brand_mentions = message_analysis.get('shopping_analysis', {}).get('brand_mentions', [])
        query_parts.extend(brand_mentions)
        
        # User preferences from memory
        preferences = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
        if preferences and not message_analysis.get('contextual_analysis', {}).get('topic_change_detected'):
            # Add relevant preferences if not changing topic
            for pref_type, pref_values in preferences.items():
                if pref_type in ['colors', 'brands', 'categories'] and pref_values:
                    if isinstance(pref_values, list):
                        query_parts.extend(pref_values[:2])  # Add top 2 preferences
                    elif isinstance(pref_values, str):
                        query_parts.append(pref_values)
        
        # Clean and combine
        query_parts = [part.strip() for part in query_parts if part and isinstance(part, str) and part.strip()]
        return ' '.join(set(query_parts))  # Remove duplicates
    
    def _build_products_search_query(self, search_query: str, memory_context: Dict):
        """
        Build Django ORM query for products - COMPLETELY FIXED TO PREVENT SLICING ERROR
        """
        if not search_query:
            return Products.objects.none()
        
        try:
            # Start with base queryset - NO SLICING AT ALL until the very end
            base_query = Products.objects.all()
            
            # Apply status filter first
            query = base_query.filter(product_status='published')
            
            # Apply search filters - build Q objects first
            search_filters = Q()
            
            # Add main search terms
            if search_query.strip():
                search_terms = search_query.split()
                for term in search_terms:
                    if term.strip():
                        term_filter = (
                            Q(product_name__icontains=term) |
                            Q(product_description__icontains=term) |
                            Q(product_brand__icontains=term) |
                            Q(tags__icontains=term)
                        )
                        search_filters |= term_filter
            
            # Apply the search filters if we have any
            if search_filters:
                query = query.filter(search_filters)
            
            # Apply user preferences if available
            preferences = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
            
            if isinstance(preferences, dict):
                # Price range filter
                price_range = preferences.get('price_range', {})
                if isinstance(price_range, dict):
                    if price_range.get('min'):
                        try:
                            min_price = float(price_range['min'])
                            query = query.filter(product_price__gte=min_price)
                        except (ValueError, TypeError):
                            pass
                    if price_range.get('max'):
                        try:
                            max_price = float(price_range['max'])
                            query = query.filter(product_price__lte=max_price)
                        except (ValueError, TypeError):
                            pass
                
                # Brand filter
                preferred_brands = preferences.get('brands', [])
                if preferred_brands and isinstance(preferred_brands, list):
                    brand_filters = Q()
                    for brand in preferred_brands[:3]:  # Limit to prevent too many OR conditions
                        if brand and isinstance(brand, str):
                            brand_filters |= Q(product_brand__icontains=brand.strip())
                    if brand_filters:
                        query = query.filter(brand_filters)
                
                # Location preference
                preferred_locations = preferences.get('locations', [])
                if preferred_locations and isinstance(preferred_locations, list):
                    location_filters = Q()
                    for location in preferred_locations[:3]:  # Limit to prevent too many OR conditions
                        if location and isinstance(location, str):
                            location_filters |= (
                                Q(city__name__icontains=location.strip()) | 
                                Q(state__name__icontains=location.strip())
                            )
                    if location_filters:
                        query = query.filter(location_filters)
            
            # Apply ordering and make distinct - STILL NO SLICING
            final_query = query.distinct().order_by('-created_at')
            
            # Return the complete QuerySet - slicing will happen in the calling method
            return final_query
            
        except Exception as e:
            logger.error(f"Error building products query: {e}")
            # Return empty queryset on error
            return Products.objects.none()

    def _should_search_services(self, message_analysis: Dict, memory_context: Dict) -> bool:
        """Determine if we should search services"""
        intent = message_analysis.get('intent_analysis', {}).get('primary_intent', '')
        message = message_analysis.get('basic_analysis', {}).get('message_text', '').lower()
        
        service_indicators = [
            'service', 'repair', 'fix', 'help with', 'consultation',
            'installation', 'delivery', 'cleaning', 'maintenance'
        ]
        
        return intent == 'service_request' or any(indicator in message for indicator in service_indicators)
    
    def _build_services_search_query(self, search_query: str, memory_context: Dict):
        """
        Build Django ORM query for services - COMPLETELY FIXED TO PREVENT SLICING ERROR
        """
        if not search_query:
            return Services.objects.none()
        
        try:
            # Start with base queryset - NO SLICING AT ALL until the very end
            base_query = Services.objects.all()
            
            # Apply status filter first
            query = base_query.filter(service_status='published')
            
            # Apply search filters - build Q objects first
            search_filters = Q()
            
            # Add main search terms
            if search_query.strip():
                search_terms = search_query.split()
                for term in search_terms:
                    if term.strip():
                        term_filter = (
                            Q(service_name__icontains=term) |
                            Q(service_description__icontains=term) |
                            Q(provider_expertise__icontains=term)
                        )
                        search_filters |= term_filter
            
            # Apply the search filters if we have any
            if search_filters:
                query = query.filter(search_filters)
            
            # Apply location preferences if available
            preferences = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
            if isinstance(preferences, dict):
                preferred_locations = preferences.get('locations', [])
                if preferred_locations and isinstance(preferred_locations, list):
                    location_filters = Q()
                    for location in preferred_locations[:3]:  # Limit to prevent too many OR conditions
                        if location and isinstance(location, str):
                            location_filters |= (
                                Q(city__name__icontains=location.strip()) |
                                Q(state__name__icontains=location.strip())
                            )
                    if location_filters:
                        query = query.filter(location_filters)
            
            # Apply ordering and make distinct - STILL NO SLICING
            final_query = query.distinct().order_by('-created_at')
            
            # Return the complete QuerySet - slicing will happen in the calling method
            return final_query
            
        except Exception as e:
            logger.error(f"Error building services query: {e}")
            # Return empty queryset on error
            return Services.objects.none()
    
    def _get_relevant_categories(self, search_query: str, memory_context: Dict) -> List:
        """Get relevant categories - FIXED TO PREVENT SLICING ISSUES"""
        if not search_query:
            return []
        
        try:
            # Build the complete query without any slicing
            categories_query = Category.objects.filter(is_active=True)
            
            # Apply search filters
            if search_query.strip():
                search_terms = search_query.split()
                search_filters = Q()
                
                for term in search_terms:
                    if term.strip():
                        term_filter = (
                            Q(name__icontains=term) |
                            Q(description__icontains=term)
                        )
                        search_filters |= term_filter
                
                if search_filters:
                    categories_query = categories_query.filter(search_filters)
            
            # Apply ordering and convert to list at the very end
            final_categories = categories_query.order_by('name')
            
            # Convert to list with slicing ONLY at the very end
            return list(final_categories[:3])
            
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
        
    def _format_search_results_for_ai(self, search_results: Dict) -> str:
        """Format search results for AI consumption"""
        if not search_results or not any(search_results.values()):
            return "No specific matches found in Finda database for this query."
        
        formatted_parts = []
        
        # Format products
        products = search_results.get('products', [])
        if products:
            formatted_parts.append("🛍️ PRODUCTS FOUND:")
            for i, product in enumerate(products[:5], 1):
                formatted_parts.append(f"""
{i}. **{product.product_name}**
   💰 Price: ₦{product.product_price:,.2f}
   🏢 Brand: {getattr(product, 'product_brand', 'N/A')}
   📍 Location: {product.city.name if product.city else 'N/A'}, {product.state.name if product.state else 'N/A'}
   📝 Description: {product.product_description[:150]}...
   📞 Contact: {getattr(product, 'provider_phone', 'Contact via platform')}
   ✅ Status: {getattr(product, 'product_condition', 'Available')}
""")
        
        # Format services
        services = search_results.get('services', [])
        if services:
            formatted_parts.append("\n🔧 SERVICES FOUND:")
            for i, service in enumerate(services[:3], 1):
                formatted_parts.append(f"""
{i}. **{service.service_name}**
   👤 Provider: {getattr(service, 'provider_name', 'Service Provider')}
   📍 Location: {service.city.name if service.city else 'N/A'}, {service.state.name if service.state else 'N/A'}
   💰 Price: {getattr(service, 'starting_price', 'Contact for pricing')}
   📝 Description: {service.service_description[:150]}...
   📞 Contact: {getattr(service, 'provider_phone', 'Contact via platform')}
""")
        
        # Format categories
        categories = search_results.get('categories', [])
        if categories:
            formatted_parts.append("\n📂 RELEVANT CATEGORIES:")
            for category in categories:
                formatted_parts.append(f"• **{category.name}**: {getattr(category, 'description', 'Browse this category')}")
        
        return "\n".join(formatted_parts) if formatted_parts else "No specific matches found."

    def _create_memory_summary(self, memory_context: Dict) -> str:
        """Create comprehensive memory summary for AI"""
        user_id = memory_context.get('user_identity', {}).get('user_id', 'Unknown')
        is_returning = memory_context.get('user_identity', {}).get('returning_user', False)
        
        if not is_returning:
            return "**NEW USER**: This is a first-time interaction. Build rapport and learn about their preferences."
        
        # Build memory summary for returning user
        conversation_memory = memory_context.get('conversation_memory', {})
        user_profile = memory_context.get('user_intelligence_profile', {})
        emotional_intel = memory_context.get('emotional_intelligence', {})
        
        summary_parts = [
            f"**RETURNING USER (ID: {user_id})**",
            f"**Previous Conversations**: {conversation_memory.get('conversation_length', 0)} messages exchanged",
            f"**Topics Discussed**: {', '.join(conversation_memory.get('topics_discussed', [])[:5])}",
            f"**Communication Style**: {user_profile.get('communication_style', 'Unknown')}",
            f"**Shopping Behavior**: {user_profile.get('shopping_behavior', 'Unknown')}",
            f"**Current Mood Indicators**: {', '.join(emotional_intel.get('current_mood_indicators', []))}",
            f"**Product Preferences**: {user_profile.get('product_preferences', {})}",
            f"**Successful Interactions**: {len(conversation_memory.get('successful_interactions', []))}",
            f"**Areas of Confusion**: {', '.join(conversation_memory.get('problematic_interactions', [])[:3])}"
        ]
        
        return "\n".join(summary_parts)

    def _create_situation_analysis(self, message_analysis: Dict, memory_context: Dict) -> str:
        """Create current situation analysis"""
        intent = message_analysis.get('intent_analysis', {}).get('primary_intent', 'unknown')
        emotion = message_analysis.get('emotional_analysis', {}).get('current_emotion', 'neutral')
        topic_change = message_analysis.get('contextual_analysis', {}).get('topic_change_detected', False)
        confusion = message_analysis.get('contextual_analysis', {}).get('confusion_indicators', [])
        
        analysis_parts = [
            f"**Primary Intent**: {intent}",
            f"**Current Emotion**: {emotion}",
            f"**Topic Change Detected**: {'Yes' if topic_change else 'No'}",
            f"**Confusion Indicators**: {', '.join(confusion) if confusion else 'None'}",
            f"**Message Urgency**: {message_analysis.get('shopping_analysis', {}).get('urgency_level', 'Normal')}",
            f"**Communication Style**: {message_analysis.get('communication_analysis', {}).get('interaction_style', 'Standard')}"
        ]
        
        return "\n".join(analysis_parts)

    def _create_search_context(self, memory_context: Dict) -> str:
        """Create search context for AI"""
        search_intel = memory_context.get('search_intelligence', {})
        
        context_parts = [
            "**Available Search Capabilities**:",
            "• Product database with prices, brands, locations, and descriptions",
            "• Service provider database with expertise and contact information",
            "• Category browsing for product discovery",
            "• External marketplace suggestions when internal results are limited",
            "",
            f"**User's Search History**: {len(search_intel.get('previous_searches', []))} previous searches",
            f"**Successful Matches**: {len(search_intel.get('successful_matches', []))} items previously found",
            f"**Search Patterns**: {search_intel.get('search_patterns', 'Learning user preferences')}"
        ]
        
        return "\n".join(context_parts)

    def _format_image_context(self, image_data: bytes, message_analysis: Dict) -> str:
        """Format image context if present"""
        if not image_data:
            return "No image provided."
        
        image_analysis = message_analysis.get('image_analysis', {})
        if not image_analysis:
            return "Image provided but analysis pending."
        
        return f"""
**Image Analysis Results**:
• Product Type: {image_analysis.get('product_type', 'Unknown')}
• Brand Detected: {image_analysis.get('brand', 'Not detected')}
• Primary Colors: {', '.join(image_analysis.get('colors', []))}
• Estimated Category: {image_analysis.get('category', 'General')}
• Confidence Score: {image_analysis.get('confidence', 0.5):.1%}
"""

    def _analyze_image_with_perfect_context(self, image_data: bytes, user_message: str, 
                                          memory_context: Dict) -> Dict[str, Any]:
        """Analyze image with perfect context awareness"""
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Resize if needed
            max_size = (1024, 1024)
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Enhanced analysis prompt with user context
            user_preferences = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
            previous_searches = memory_context.get('search_intelligence', {}).get('previous_searches', [])
            
            analysis_prompt = f"""
Analyze this product image with complete context awareness:

USER CONTEXT:
- User Message: "{user_message}"
- Previous Searches: {', '.join(previous_searches[-3:]) if previous_searches else 'None'}
- User Preferences: {user_preferences}

Provide comprehensive JSON analysis:
{{
    "product_identification": {{
        "product_type": "specific product name/type",
        "category": "general category",
        "subcategory": "specific subcategory",
        "brand": "brand name if visible",
        "model": "model/version if identifiable"
    }},
    "visual_characteristics": {{
        "primary_color": "main color",
        "secondary_colors": ["color1", "color2"],
        "style": "style description",
        "material": "material type if visible",
        "condition": "new/used assessment",
        "size_indicators": "any size information visible"
    }},
    "search_optimization": {{
        "primary_keywords": ["keyword1", "keyword2", "keyword3"],
        "alternative_keywords": ["alt1", "alt2", "alt3"],
        "search_query": "optimized search query for Finda"
    }},
    "user_context_matching": {{
        "matches_user_preferences": true/false,
        "preference_alignment_score": 0.85,
        "similar_to_previous_searches": true/false
    }},
    "confidence_score": 0.90
}}
"""
            
            # Initialize vision model
            model = genai.GenerativeModel(self.model_vision)
            
            # Generate analysis
            response = model.generate_content([analysis_prompt, image])
            
            if response and response.text:
                json_text = response.text.strip()
                
                # Clean JSON response
                if '```json' in json_text:
                    json_text = json_text.split('```json')[1].split('```')[0].strip()
                elif '```' in json_text:
                    json_text = json_text.split('```')[1].strip()
                
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    # Fallback analysis
                    return {
                        "product_identification": {"product_type": "product", "category": "general"},
                        "confidence_score": 0.5
                    }
            
            return {"error": "No analysis generated"}
            
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return {"error": f"Analysis failed: {str(e)}"}

    # Additional helper methods for perfect memory and intelligence

    def _extract_topics_from_history(self, history: List[Dict]) -> List[str]:
        """Extract all topics discussed in conversation history"""
        if not history:
            return []
        
        topics = []
        topic_keywords = []
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                # Extract potential topics using simple keyword extraction
                words = re.findall(r'\b[a-zA-Z]{4,}\b', content)
                topic_keywords.extend(words)
        
        # Simple topic clustering (can be enhanced with NLP)
        common_topics = ['phone', 'laptop', 'clothes', 'shoes', 'food', 'service', 'repair', 'buy', 'sell']
        for topic in common_topics:
            if any(topic in keyword for keyword in topic_keywords):
                topics.append(topic)
        
        return list(set(topics))

    def _detect_sophisticated_intent_from_message(self, message: str, memory_context: Dict) -> str:
        """Detect sophisticated intent using context and memory"""
        message_lower = message.lower()
        
        # Context-aware intent detection
        previous_intents = []
        if memory_context.get('conversation_memory', {}).get('full_history'):
            for msg in memory_context['conversation_memory']['full_history'][-3:]:
                if msg.get('author') == 'user':
                    # Simple intent extraction from previous messages
                    prev_content = msg.get('content', '').lower()
                    if any(word in prev_content for word in ['buy', 'purchase', 'get', 'find']):
                        previous_intents.append('purchase_intent')
                    elif any(word in prev_content for word in ['compare', 'difference', 'better']):
                        previous_intents.append('comparison_intent')
        
        # Current message intent
        intent_patterns = {
            'greeting': ['hi', 'hello', 'hey', 'good morning', 'good afternoon'],
            'purchase_intent': ['buy', 'purchase', 'get', 'need to buy', 'looking for', 'want to get'],
            'comparison_request': ['compare', 'difference', 'better', 'vs', 'versus', 'which is'],
            'price_inquiry': ['how much', 'price', 'cost', 'expensive', 'cheap', 'budget'],
            'confusion': ['confused', 'dont understand', 'not sure', 'unclear', 'help me understand'],
            'topic_change': ['actually', 'wait', 'instead', 'never mind', 'change my mind'],
            'dissatisfaction': ['not what i want', 'different', 'not good', 'not right'],
            'information_seeking': ['tell me about', 'what is', 'how does', 'explain', 'details'],
            'location_specific': ['near me', 'in lagos', 'in abuja', 'local', 'around here'],
            'urgency': ['urgent', 'quickly', 'asap', 'immediately', 'right now', 'today']
        }
        
        detected_intents = []
        for intent, keywords in intent_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_intents.append(intent)
        
        # Use context to refine intent
        if 'topic_change' in detected_intents:
            return 'topic_change'
        elif 'confusion' in detected_intents:
            return 'confusion'
        elif 'dissatisfaction' in detected_intents:
            return 'dissatisfaction'
        elif detected_intents:
            return detected_intents[0]
        elif previous_intents and len(message.split()) < 5:  # Short message, likely continuation
            return 'continuation'
        else:
            return 'general_inquiry'

    def _detect_current_emotion(self, message: str) -> str:
        """Detect current emotional state from message"""
        message_lower = message.lower()
        
        emotion_indicators = {
            'excited': ['awesome', 'amazing', 'great', 'perfect', 'love it', 'fantastic', '!'],
            'frustrated': ['frustrated', 'annoying', 'terrible', 'awful', 'hate', 'stupid'],
            'confused': ['confused', 'lost', 'dont understand', 'unclear', 'not sure'],
            'impatient': ['hurry', 'quickly', 'fast', 'urgent', 'asap', 'waiting'],
            'satisfied': ['good', 'nice', 'helpful', 'thanks', 'perfect', 'exactly'],
            'disappointed': ['disappointed', 'not good', 'expected better', 'not satisfied'],
            'curious': ['interesting', 'tell me more', 'what about', 'how about', '?'],
            'determined': ['need', 'must have', 'definitely', 'absolutely', 'certainly']
        }
        
        for emotion, indicators in emotion_indicators.items():
            if any(indicator in message_lower for indicator in indicators):
                return emotion
        
        return 'neutral'

    def _detect_topic_change_advanced(self, message: str, memory_context: Dict) -> bool:
        """Advanced topic change detection"""
        message_lower = message.lower()
        
        # Direct topic change indicators
        change_indicators = [
            'actually', 'wait', 'instead', 'never mind', 'forget that',
            'change of mind', 'different topic', 'something else',
            'on second thought', 'let me ask about', 'what about'
        ]
        
        if any(indicator in message_lower for indicator in change_indicators):
            return True
        
        # Check if current message topic differs significantly from recent conversation
        recent_topics = memory_context.get('conversation_memory', {}).get('topics_discussed', [])
        current_topics = self._extract_topics_from_message(message)
        
        if recent_topics and current_topics:
            # Simple topic similarity check
            topic_overlap = len(set(recent_topics) & set(current_topics))
            if topic_overlap == 0 and len(current_topics) > 0:
                return True
        
        return False

    def _extract_topics_from_message(self, message: str) -> List[str]:
        """Extract topics from a single message"""
        message_lower = message.lower()
        
        # Common product/service categories
        topics = []
        category_keywords = {
            'electronics': ['phone', 'laptop', 'computer', 'tablet', 'tv', 'camera'],
            'fashion': ['clothes', 'shoes', 'dress', 'shirt', 'pants', 'bag'],
            'food': ['food', 'restaurant', 'meal', 'cooking', 'recipe'],
            'services': ['repair', 'cleaning', 'delivery', 'installation', 'consultation'],
            'automotive': ['car', 'vehicle', 'motorcycle', 'parts', 'maintenance'],
            'home': ['furniture', 'decoration', 'appliance', 'home', 'house']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                topics.append(category)
        
        return topics

    # Helper methods for determining search strategy and preferences
    def _determine_search_strategy(self, message_analysis: Dict) -> str:
        """Determine the search strategy used"""
        try:
            intent = message_analysis.get('intent_analysis', {}).get('primary_intent', 'general')
            
            strategy_mapping = {
                'purchase_intent': 'product_focused',
                'product_search': 'product_focused',
                'service_request': 'service_focused',
                'comparison_request': 'comparison_focused',
                'price_inquiry': 'price_focused',
                'location_specific': 'location_focused'
            }
            
            return strategy_mapping.get(intent, 'general_search')
            
        except Exception as e:
            logger.error(f"Error determining search strategy: {e}")
            return 'general_search'
    
    def _get_applied_preferences(self, memory_context: Dict) -> Dict:
        """Get which preferences were applied in the search"""
        try:
            preferences = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
            applied = {}
            
            # Only include preferences that have actual values
            for key, value in preferences.items():
                if value:  # Check if value exists and is not empty
                    if isinstance(value, list) and len(value) > 0:
                        applied[key] = value
                    elif isinstance(value, dict) and value:
                        applied[key] = value
                    elif isinstance(value, str) and value.strip():
                        applied[key] = value
                    elif isinstance(value, (int, float)) and value != 0:
                        applied[key] = value
            
            return applied
            
        except Exception as e:
            logger.error(f"Error getting applied preferences: {e}")
            return {}

    # Additional missing helper methods for the complete system
    def _extract_user_questions(self, history: List[Dict]) -> List[str]:
        """Extract questions user has asked"""
        questions = []
        if not history:
            return questions
        
        for msg in history:
            if msg.get('author') == 'user' and '?' in msg.get('content', ''):
                questions.append(msg.get('content', ''))
        
        return questions[-5:]  # Last 5 questions

    def _extract_ai_recommendations(self, history: List[Dict]) -> List[str]:
        """Extract AI recommendations from history"""
        recommendations = []
        if not history:
            return recommendations
        
        for msg in history:
            if msg.get('author') == 'assistant':
                content = msg.get('content', '').lower()
                if any(phrase in content for phrase in ['recommend', 'suggest', 'try', 'consider']):
                    recommendations.append(msg.get('content', '')[:100])
        
        return recommendations[-3:]  # Last 3 recommendations

    def _identify_successful_interactions(self, history: List[Dict]) -> List[Dict]:
        """Identify successful interactions from history"""
        successful = []
        if not history:
            return successful
        
        success_indicators = ['perfect', 'exactly', 'great', 'thanks', 'helpful', 'found it']
        
        for i, msg in enumerate(history):
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(indicator in content for indicator in success_indicators):
                    successful.append({
                        'message_index': i,
                        'content': msg.get('content', ''),
                        'timestamp': msg.get('timestamp')
                    })
        
        return successful

    def _identify_problematic_interactions(self, history: List[Dict]) -> List[str]:
        """Identify problematic interactions that caused confusion"""
        problems = []
        if not history:
            return problems
        
        problem_indicators = [
            'confused', 'dont understand', 'not what i want', 'wrong',
            'not helpful', 'different', 'not right'
        ]
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(indicator in content for indicator in problem_indicators):
                    problems.append(content[:50])
        
        return problems[-3:]  # Last 3 problems

    def _analyze_communication_style(self, history: List[Dict]) -> str:
        """Analyze user's communication style"""
        if not history:
            return 'unknown'
        
        user_messages = [msg.get('content', '') for msg in history if msg.get('author') == 'user']
        if not user_messages:
            return 'unknown'
        
        # Analyze patterns
        total_chars = sum(len(msg) for msg in user_messages)
        avg_length = total_chars / len(user_messages)
        
        exclamation_count = sum(msg.count('!') for msg in user_messages)
        question_count = sum(msg.count('?') for msg in user_messages)
        
        if avg_length > 100:
            style = 'detailed'
        elif avg_length < 30:
            style = 'brief'
        else:
            style = 'moderate'
        
        if exclamation_count > len(user_messages) * 0.5:
            style += '_enthusiastic'
        elif question_count > len(user_messages) * 0.7:
            style += '_inquisitive'
        
        return style

    def _analyze_decision_pattern(self, history: List[Dict]) -> str:
        """Analyze how user makes decisions"""
        if not history:
            return 'unknown'
        
        user_messages = [msg.get('content', '').lower() for msg in history if msg.get('author') == 'user']
        
        # Look for decision-making patterns
        quick_decision_indicators = ['yes', 'ok', 'sure', 'lets go', 'perfect', 'ill take it']
        deliberate_indicators = ['let me think', 'compare', 'options', 'tell me more', 'what about']
        
        quick_count = sum(any(indicator in msg for indicator in quick_decision_indicators) for msg in user_messages)
        deliberate_count = sum(any(indicator in msg for indicator in deliberate_indicators) for msg in user_messages)
        
        if quick_count > deliberate_count:
            return 'quick_decision_maker'
        elif deliberate_count > quick_count:
            return 'deliberate_decision_maker'
        else:
            return 'balanced_decision_maker'

    def _analyze_shopping_behavior(self, history: List[Dict]) -> str:
        """Analyze shopping behavior patterns"""
        if not history:
            return 'unknown'
        
        user_messages = [msg.get('content', '').lower() for msg in history if msg.get('author') == 'user']
        
        # Behavior indicators
        price_focused = sum('price' in msg or 'cost' in msg or 'cheap' in msg for msg in user_messages)
        quality_focused = sum('quality' in msg or 'best' in msg or 'durable' in msg for msg in user_messages)
        brand_focused = sum(any(brand in msg for brand in ['nike', 'apple', 'samsung', 'brand']) for msg in user_messages)
        convenience_focused = sum('delivery' in msg or 'near me' in msg or 'fast' in msg for msg in user_messages)
        
        behaviors = [
            ('price_conscious', price_focused),
            ('quality_focused', quality_focused),
            ('brand_conscious', brand_focused),
            ('convenience_focused', convenience_focused)
        ]
        
        primary_behavior = max(behaviors, key=lambda x: x[1])
        return primary_behavior[0] if primary_behavior[1] > 0 else 'general_shopper'

    def _create_intelligent_fallback_response(self, user_message: str, error: str, user_id: int) -> Dict[str, Any]:
        """Create intelligent fallback when processing fails"""
        fallback_responses = [
            "I understand you're asking about something important. Let me help you find what you need on Finda! Could you tell me a bit more about what you're looking for?",
            "I'm here to help you discover amazing products and services on Finda! What can I assist you with today?",
            "Thanks for reaching out! I'd love to help you find exactly what you need. Could you give me a few more details about what you're searching for?",
            "I'm your Finda AI assistant, ready to help you find the best products and services! What are you interested in today?"
        ]
        
        import random
        response = random.choice(fallback_responses)
        
        return {
            'response': response,
            'message_analysis': {'error': 'Processing failed', 'fallback_used': True},
            'search_results': {'products': [], 'services': [], 'categories': []},
            'updated_context': {},
            'memory_updates': {},
            'conversation_intelligence': {'status': 'fallback_mode'},
            'next_conversation_guidance': ['ask_for_clarification'],
            'user_satisfaction_prediction': 0.3,
            'personality_insights': {'error': error if user_id else None}
        }

    def _create_intelligent_fallback_text(self, memory_context: Dict, error: str = None) -> str:
        """Create intelligent fallback text when AI generation fails"""
        user_id = memory_context.get('user_identity', {}).get('user_id')
        is_returning = memory_context.get('user_identity', {}).get('returning_user', False)
        
        if is_returning:
            return "I remember our previous conversations! I'm here to help you find exactly what you need on Finda. What can I assist you with today? 🛍️"
        else:
            return "Welcome to Finda AI! I'm excited to help you discover amazing products and services. What are you looking for today? 🌟"

    # Continue with all the remaining helper methods that were causing the errors...
    
    def _extract_product_preferences(self, history: List[Dict]) -> Dict:
        """Extract product preferences from conversation history"""
        preferences = {
            'categories': [],
            'brands': [],
            'colors': [],
            'price_ranges': [],
            'locations': []
        }
        
        if not history:
            return preferences
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                
                # Extract categories
                category_keywords = ['phone', 'laptop', 'clothes', 'shoes', 'food', 'car']
                for keyword in category_keywords:
                    if keyword in content and keyword not in preferences['categories']:
                        preferences['categories'].append(keyword)
                
                # Extract brands
                brand_keywords = ['apple', 'samsung', 'nike', 'adidas', 'toyota', 'lg']
                for brand in brand_keywords:
                    if brand in content and brand not in preferences['brands']:
                        preferences['brands'].append(brand)
        
        return preferences

    def _analyze_price_sensitivity(self, history: List[Dict]) -> str:
        """Analyze user's price sensitivity"""
        if not history:
            return 'unknown'
        
        user_messages = [msg.get('content', '').lower() for msg in history if msg.get('author') == 'user']
        
        # Count price-related terms
        budget_terms = sum('cheap' in msg or 'budget' in msg or 'affordable' in msg for msg in user_messages)
        quality_terms = sum('quality' in msg or 'premium' in msg or 'expensive' in msg for msg in user_messages)
        
        if budget_terms > quality_terms:
            return 'price_sensitive'
        elif quality_terms > budget_terms:
            return 'quality_focused'
        else:
            return 'balanced'

    def _analyze_brand_preferences(self, history: List[Dict]) -> str:
        """Analyze brand preference patterns"""
        if not history:
            return 'unknown'
        
        user_messages = [msg.get('content', '').lower() for msg in history if msg.get('author') == 'user']
        
        brand_mentions = sum('brand' in msg or any(brand in msg for brand in ['apple', 'samsung', 'nike']) for msg in user_messages)
        
        if brand_mentions > len(user_messages) * 0.3:
            return 'brand_conscious'
        else:
            return 'brand_flexible'

    def _analyze_interaction_preferences(self, history: List[Dict]) -> str:
        """Analyze how user prefers to interact"""
        if not history:
            return 'unknown'
        
        # Count different interaction types
        image_messages = sum(1 for msg in history if msg.get('has_image'))
        voice_messages = sum(1 for msg in history if msg.get('has_audio'))
        text_messages = sum(1 for msg in history if msg.get('type') == 'text')
        
        total = len(history)
        if total == 0:
            return 'unknown'
        
        if image_messages > total * 0.3:
            return 'visual_preferred'
        elif voice_messages > total * 0.3:
            return 'voice_preferred'
        else:
            return 'text_preferred'

    def _detect_current_mood(self, history: List[Dict]) -> List[str]:
        """Detect current mood indicators from recent conversation"""
        mood_indicators = []
        if not history:
            return mood_indicators
        
        # Look at last few messages
        recent_messages = history[-3:] if len(history) >= 3 else history
        
        for msg in recent_messages:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                
                if any(word in content for word in ['excited', 'great', 'awesome', '!']):
                    mood_indicators.append('enthusiastic')
                elif any(word in content for word in ['confused', 'lost', 'unclear']):
                    mood_indicators.append('confused')
                elif any(word in content for word in ['frustrated', 'annoyed', 'difficult']):
                    mood_indicators.append('frustrated')
                elif any(word in content for word in ['thanks', 'helpful', 'good']):
                    mood_indicators.append('satisfied')
        
        return list(set(mood_indicators))

    def _track_emotional_journey(self, history: List[Dict]) -> List[str]:
        """Track emotional journey through conversation"""
        journey = []
        if not history:
            return journey
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(word in content for word in ['excited', 'great', 'awesome']):
                    journey.append('positive')
                elif any(word in content for word in ['confused', 'frustrated', 'difficult']):
                    journey.append('negative')
                else:
                    journey.append('neutral')
        
        return journey

    def _identify_frustration_triggers(self, history: List[Dict]) -> List[str]:
        """Identify what causes user frustration"""
        triggers = []
        if not history:
            return triggers
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if 'frustrated' in content or 'annoying' in content:
                    # Look for what was mentioned as frustrating
                    if 'slow' in content:
                        triggers.append('slow_responses')
                    elif 'wrong' in content or 'not what' in content:
                        triggers.append('incorrect_results')
                    elif 'dont understand' in content:
                        triggers.append('communication_issues')
        
        return list(set(triggers))

    def _identify_satisfaction_patterns(self, history: List[Dict]) -> List[str]:
        """Identify what makes user satisfied"""
        patterns = []
        if not history:
            return patterns
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(word in content for word in ['perfect', 'exactly', 'great', 'helpful']):
                    patterns.append('accurate_results')
                elif 'fast' in content or 'quick' in content:
                    patterns.append('quick_responses')
                elif 'understand' in content and 'thanks' in content:
                    patterns.append('clear_communication')
        
        return list(set(patterns))

    def _assess_engagement_level(self, history: List[Dict]) -> str:
        """Assess user's engagement level"""
        if not history:
            return 'unknown'
        
        user_messages = [msg for msg in history if msg.get('author') == 'user']
        
        if not user_messages:
            return 'low'
        
        # Calculate engagement score
        avg_message_length = sum(len(msg.get('content', '')) for msg in user_messages) / len(user_messages)
        question_ratio = sum(1 for msg in user_messages if '?' in msg.get('content', '')) / len(user_messages)
        
        if avg_message_length > 50 and question_ratio > 0.3:
            return 'high'
        elif avg_message_length > 20:
            return 'medium'
        else:
            return 'low'

    def _detect_sophisticated_intent(self, history: List[Dict]) -> str:
        """Detect sophisticated intent from conversation history"""
        if not history:
            return 'greeting'
        
        recent_user_messages = [msg for msg in history[-3:] if msg.get('author') == 'user']
        
        if not recent_user_messages:
            return 'general_inquiry'
        
        latest_content = recent_user_messages[-1].get('content', '').lower()
        
        # Intent detection based on latest message
        if any(word in latest_content for word in ['buy', 'purchase', 'get', 'need']):
            return 'purchase_intent'
        elif any(word in latest_content for word in ['compare', 'difference', 'better']):
            return 'comparison_request'
        elif any(word in latest_content for word in ['price', 'cost', 'how much']):
            return 'price_inquiry'
        elif any(word in latest_content for word in ['confused', 'dont understand']):
            return 'clarification_needed'
        else:
            return 'general_inquiry'

    def _track_topic_evolution(self, history: List[Dict]) -> List[str]:
        """Track how topics have evolved"""
        evolution = []
        if not history:
            return evolution
        
        current_topic = None
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                topics = self._extract_topics_from_message(content)
                
                if topics and topics != current_topic:
                    evolution.append(topics[0])  # Take first topic
                    current_topic = topics
        
        return evolution

    def _determine_conversation_stage(self, history: List[Dict]) -> str:
        """Determine what stage the conversation is in"""
        if not history:
            return 'greeting'
        
        message_count = len(history)
        
        if message_count < 4:
            return 'introduction'
        elif message_count < 10:
            return 'exploration'
        elif message_count < 20:
            return 'engagement'
        else:
            return 'relationship'

    def _infer_user_goals(self, history: List[Dict]) -> List[str]:
        """Infer user's goals from conversation"""
        goals = []
        if not history:
            return goals
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                
                if any(word in content for word in ['buy', 'purchase', 'need to get']):
                    goals.append('make_purchase')
                elif any(word in content for word in ['compare', 'options', 'alternatives']):
                    goals.append('research_products')
                elif any(word in content for word in ['price', 'cost', 'budget']):
                    goals.append('find_best_price')
                elif any(word in content for word in ['near me', 'local', 'delivery']):
                    goals.append('find_local_options')
        
        return list(set(goals))

    def _identify_unresolved_needs(self, history: List[Dict]) -> List[str]:
        """Identify unresolved needs from conversation"""
        needs = []
        if not history:
            return needs
        
        # Look for questions that weren't fully answered
        for i, msg in enumerate(history):
            if msg.get('author') == 'user' and '?' in msg.get('content', ''):
                # Check if next AI response was satisfactory
                if i + 1 < len(history):
                    next_msg = history[i + 1]
                    if next_msg.get('author') == 'assistant':
                        # Simple check - if user asked another question right after, 
                        # previous need might be unresolved
                        if i + 2 < len(history) and '?' in history[i + 2].get('content', ''):
                            needs.append('clarification_needed')
        
        return list(set(needs))

    def _extract_search_history(self, history: List[Dict]) -> List[str]:
        """Extract search history from conversation"""
        searches = []
        if not history:
            return searches
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '')
                # If message contains product/service terms, consider it a search
                if any(word in content.lower() for word in ['find', 'looking for', 'need', 'want', 'search']):
                    searches.append(content[:50])  # First 50 chars
        
        return searches[-5:]  # Last 5 searches

    def _analyze_search_patterns(self, history: List[Dict]) -> str:
        """Analyze search patterns"""
        if not history:
            return 'no_pattern'
        
        search_messages = []
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(word in content for word in ['find', 'looking', 'need', 'want']):
                    search_messages.append(content)
        
        if len(search_messages) < 2:
            return 'insufficient_data'
        
        # Simple pattern analysis
        topics = []
        for search in search_messages:
            topics.extend(self._extract_topics_from_message(search))
        
        if len(set(topics)) == 1:
            return 'focused_search'  # Searching for same thing
        elif len(set(topics)) > len(topics) * 0.8:
            return 'exploratory_search'  # Searching for different things
        else:
            return 'mixed_search'

    def _identify_successful_matches(self, history: List[Dict]) -> List[str]:
        """Identify successful matches from conversation"""
        matches = []
        if not history:
            return matches
        
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(phrase in content for phrase in ['perfect', 'exactly what', 'found it', 'thats it']):
                    matches.append(content[:50])
        
        return matches

    def _identify_abandoned_searches(self, history: List[Dict]) -> List[str]:
        """Identify abandoned searches"""
        abandoned = []
        if not history:
            return abandoned
        
        # Look for topic changes without resolution
        current_search = None
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(word in content for word in ['find', 'looking', 'need']):
                    if current_search and not any(word in content for word in ['found', 'perfect', 'thanks']):
                        abandoned.append(current_search[:50])
                    current_search = content
        
        return abandoned

    def _analyze_refinement_patterns(self, history: List[Dict]) -> str:
        """Analyze how user refines searches"""
        if not history:
            return 'no_refinement'
        
        refinement_indicators = []
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                if any(phrase in content for phrase in ['actually', 'instead', 'different', 'not quite']):
                    refinement_indicators.append(content)
        
        if len(refinement_indicators) == 0:
            return 'no_refinement'
        elif len(refinement_indicators) <= 2:
            return 'minimal_refinement'
        else:
            return 'frequent_refinement'

    # Additional helper methods for complete functionality

    def _detect_urgency(self, message: str) -> List[str]:
        """Detect urgency indicators in message"""
        urgency_indicators = []
        message_lower = message.lower()
        
        urgency_patterns = {
            'high': ['urgent', 'asap', 'immediately', 'right now', 'emergency'],
            'medium': ['soon', 'quickly', 'fast', 'today'],
            'time_specific': ['tomorrow', 'this week', 'by friday']
        }
        
        for level, patterns in urgency_patterns.items():
            for pattern in patterns:
                if pattern in message_lower:
                    urgency_indicators.append(f"{level}_{pattern.replace(' ', '_')}")
        
        return urgency_indicators

    def _detect_secondary_intents(self, message: str) -> List[str]:
        """Detect secondary intents in user message"""
        secondary_intents = []
        message_lower = message.lower()
        
        # Secondary intent patterns
        if 'also' in message_lower or 'and' in message_lower:
            secondary_intents.append('multiple_requests')
        
        if 'but' in message_lower or 'however' in message_lower:
            secondary_intents.append('clarification_needed')
        
        if 'or' in message_lower:
            secondary_intents.append('alternative_options')
        
        return secondary_intents

    def _calculate_intent_confidence(self, message: str, memory_context: Dict) -> float:
        """Calculate confidence in intent detection"""
        base_confidence = 0.5
        
        # Increase confidence if message is clear and specific
        if len(message.split()) > 5:
            base_confidence += 0.2
        
        # Increase confidence if we have conversation history
        history = memory_context.get('conversation_memory', {}).get('full_history', [])
        if len(history) > 0:
            base_confidence += 0.2
        
        # Increase confidence if message contains clear action words
        action_words = ['buy', 'find', 'search', 'need', 'want', 'looking for']
        if any(word in message.lower() for word in action_words):
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)

    def _track_intent_evolution(self, message: str, memory_context: Dict) -> str:
        """Track how user intent has evolved"""
        current_intent = self._detect_sophisticated_intent_from_message(message, memory_context)
        
        history = memory_context.get('conversation_memory', {}).get('full_history', [])
        if not history:
            return 'initial_intent'
        
        # Look at recent intents
        recent_messages = [msg for msg in history[-3:] if msg.get('author') == 'user']
        if recent_messages:
            last_message = recent_messages[-1].get('content', '')
            last_intent = self._detect_sophisticated_intent_from_message(last_message, memory_context)
            
            if current_intent == last_intent:
                return 'consistent_intent'
            else:
                return 'intent_change'
        
        return 'evolving_intent'

    def _measure_emotion_intensity(self, message: str) -> float:
        """Measure intensity of emotion in message"""
        intensity = 0.0
        
        # Count exclamation marks
        intensity += message.count('!') * 0.2
        
        # Count capital letters (shouting)
        capitals = sum(1 for c in message if c.isupper())
        if len(message) > 0:
            capital_ratio = capitals / len(message)
            intensity += capital_ratio * 0.3
        
        # Look for intensity words
        intensity_words = ['very', 'extremely', 'really', 'absolutely', 'definitely']
        for word in intensity_words:
            if word in message.lower():
                intensity += 0.1
        
        return min(intensity, 1.0)

    def _detect_emotion_change(self, message: str, memory_context: Dict) -> bool:
        """Detect if emotion has changed from previous messages"""
        current_emotion = self._detect_current_emotion(message)
        
        history = memory_context.get('conversation_memory', {}).get('full_history', [])
        recent_user_messages = [msg for msg in history[-3:] if msg.get('author') == 'user']
        
        if recent_user_messages:
            last_message = recent_user_messages[-1].get('content', '')
            last_emotion = self._detect_current_emotion(last_message)
            return current_emotion != last_emotion
        
        return False

    def _identify_emotional_needs(self, message: str) -> List[str]:
        """Identify emotional needs from user message"""
        needs = []
        message_lower = message.lower()
        
        # Emotional need patterns
        if any(word in message_lower for word in ['confused', 'lost', 'help']):
            needs.append('guidance')
        
        if any(word in message_lower for word in ['frustrated', 'annoyed', 'difficult']):
            needs.append('patience')
        
        if any(word in message_lower for word in ['excited', 'love', 'amazing']):
            needs.append('enthusiasm_matching')
        
        if any(word in message_lower for word in ['worried', 'concerned', 'anxious']):
            needs.append('reassurance')
        
        return needs

    def _detect_previous_references(self, message: str, memory_context: Dict) -> bool:
        """Detect if user is referencing previous conversation"""
        reference_indicators = [
            'you said', 'earlier', 'before', 'previously', 'last time',
            'remember', 'as you mentioned', 'like we discussed'
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in reference_indicators)

    def _detect_confusion_advanced(self, message: str) -> List[str]:
        """Advanced confusion detection"""
        confusion_indicators = []
        message_lower = message.lower()
        
        confusion_patterns = {
            'understanding': ['dont understand', 'not clear', 'confused', 'unclear'],
            'expectations': ['not what i expected', 'different', 'not right'],
            'process': ['how do i', 'what should i', 'not sure how'],
            'results': ['wrong results', 'not finding', 'cant find']
        }
        
        for category, patterns in confusion_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                confusion_indicators.append(category)
        
        return confusion_indicators

    def _detect_clarification_requests(self, message: str) -> List[str]:
        """Detect clarification requests"""
        clarification_requests = []
        message_lower = message.lower()
        
        if any(phrase in message_lower for phrase in ['what do you mean', 'can you explain', 'tell me more']):
            clarification_requests.append('explanation_needed')
        
        if any(phrase in message_lower for phrase in ['how does', 'how do i', 'what is']):
            clarification_requests.append('instruction_needed')
        
        if '?' in message and any(word in message_lower for word in ['why', 'how', 'what', 'when', 'where']):
            clarification_requests.append('information_needed')
        
        return clarification_requests

    def _detect_dissatisfaction(self, message: str) -> List[str]:
        """Detect dissatisfaction signals"""
        dissatisfaction_signals = []
        message_lower = message.lower()
        
        dissatisfaction_patterns = {
            'quality': ['not good enough', 'poor quality', 'disappointing'],
            'relevance': ['not what i want', 'not relevant', 'not helpful'],
            'speed': ['too slow', 'taking too long', 'not fast enough'],
            'understanding': ['you dont understand', 'not getting it', 'missing the point']
        }
        
        for category, patterns in dissatisfaction_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                dissatisfaction_signals.append(category)
        
        return dissatisfaction_signals

    def _extract_location_preferences(self, message: str) -> List[str]:
        """Extract location preferences from message"""
        locations = []
        message_lower = message.lower()
        
        # Nigerian cities and states
        nigerian_locations = [
            'lagos', 'abuja', 'kano', 'ibadan', 'port harcourt', 'benin',
            'kaduna', 'jos', 'ilorin', 'onitsha', 'aba', 'enugu',
            'warri', 'calabar', 'maiduguri', 'zaria', 'owerri'
        ]
        
        for location in nigerian_locations:
            if location in message_lower:
                locations.append(location)
        
        # General location indicators
        if 'near me' in message_lower:
            locations.append('near_user')
        elif 'local' in message_lower:
            locations.append('local_area')
        
        return locations

    def _assess_shopping_urgency(self, message: str) -> str:
        """Assess shopping urgency level"""
        message_lower = message.lower()
        
        high_urgency = ['urgent', 'asap', 'immediately', 'right now', 'emergency', 'today']
        medium_urgency = ['soon', 'quickly', 'this week', 'fast']
        
        if any(word in message_lower for word in high_urgency):
            return 'high'
        elif any(word in message_lower for word in medium_urgency):
            return 'medium'
        else:
            return 'normal'

    def _assess_formality_level(self, message: str) -> str:
        """Assess formality level of message"""
        message_lower = message.lower()
        
        formal_indicators = ['please', 'kindly', 'would you', 'could you', 'thank you']
        informal_indicators = ['hey', 'hi', 'thanks', 'ok', 'yeah', 'cool']
        
        formal_count = sum(1 for indicator in formal_indicators if indicator in message_lower)
        informal_count = sum(1 for indicator in informal_indicators if indicator in message_lower)
        
        if formal_count > informal_count:
            return 'formal'
        elif informal_count > formal_count:
            return 'informal'
        else:
            return 'neutral'

    def _assess_enthusiasm_level(self, message: str) -> str:
        """Assess enthusiasm level"""
        message_lower = message.lower()
        
        enthusiasm_indicators = ['awesome', 'amazing', 'great', 'fantastic', 'love', 'excited']
        exclamation_count = message.count('!')
        
        enthusiasm_score = sum(1 for indicator in enthusiasm_indicators if indicator in message_lower)
        enthusiasm_score += exclamation_count * 0.5
        
        if enthusiasm_score >= 2:
            return 'high'
        elif enthusiasm_score >= 1:
            return 'medium'
        else:
            return 'low'

    def _assess_detail_preference(self, message: str, memory_context: Dict) -> str:
        """Assess user's preference for detail level"""
        message_length = len(message)
        
        # Check conversation history for pattern
        history = memory_context.get('conversation_memory', {}).get('full_history', [])
        user_messages = [msg.get('content', '') for msg in history if msg.get('author') == 'user']
        
        if user_messages:
            avg_length = sum(len(msg) for msg in user_messages) / len(user_messages)
            if avg_length > 100:
                return 'detailed'
            elif avg_length < 30:
                return 'brief'
            else:
                return 'moderate'
        
        # Fallback to current message
        if message_length > 100:
            return 'detailed'
        elif message_length < 30:
            return 'brief'
        else:
            return 'moderate'

    def _analyze_interaction_style(self, message: str) -> str:
        """Analyze interaction style from current message"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['please help', 'can you', 'would you']):
            return 'polite_requester'
        elif any(word in message_lower for word in ['find me', 'get me', 'i need', 'i want']):
            return 'direct_requester'
        elif '?' in message:
            return 'inquisitive'
        elif any(word in message_lower for word in ['thanks', 'great', 'perfect']):
            return 'appreciative'
        else:
            return 'neutral'

    # Final helper methods for memory extraction and analysis

    def _extract_memory_updates(self, ai_response: str, user_message: str) -> Dict:
        """Extract memory updates from AI response and user message"""
        updates = {}
        
        # Extract potential categories from user message
        user_lower = user_message.lower()
        categories = []
        category_keywords = {
            'electronics': ['phone', 'laptop', 'computer', 'tablet'],
            'fashion': ['clothes', 'shoes', 'dress', 'shirt'],
            'automotive': ['car', 'motorcycle', 'vehicle'],
            'home': ['furniture', 'house', 'home']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in user_lower for keyword in keywords):
                categories.append(category)
        
        if categories:
            updates['categories_mentioned'] = categories
        
        # Extract price mentions
        import re
        price_matches = re.findall(r'(\d+)', user_message)
        if price_matches:
            updates['price_mentioned'] = [int(p) for p in price_matches if int(p) > 100]
        
        return updates

    def _analyze_conversation_intelligence(self, message_analysis: Dict, memory_context: Dict) -> Dict:
        """Analyze conversation intelligence metrics"""
        return {
            'intent_confidence': message_analysis.get('intent_analysis', {}).get('intent_confidence', 0.5),
            'context_continuity': len(memory_context.get('conversation_memory', {}).get('full_history', [])) > 0,
            'personalization_level': len(memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})),
            'conversation_stage': self._determine_conversation_stage(memory_context.get('conversation_memory', {}).get('full_history', []))
        }

    def _generate_next_conversation_guidance(self, ai_response: str, memory_context: Dict) -> List[str]:
        """Generate guidance for next conversation steps"""
        guidance = []
        
        # Basic guidance based on conversation stage
        history = memory_context.get('conversation_memory', {}).get('full_history', [])
        stage = self._determine_conversation_stage(history)
        
        if stage == 'greeting':
            guidance.append('learn_user_preferences')
        elif stage == 'introduction':
            guidance.append('clarify_needs')
        elif stage == 'exploration':
            guidance.append('provide_recommendations')
        else:
            guidance.append('maintain_relationship')
        
        # Add specific guidance based on AI response content
        response_lower = ai_response.lower()
        if 'search' in response_lower:
            guidance.append('show_search_results')
        if '?' in ai_response:
            guidance.append('await_clarification')
        
        return guidance

    def _predict_user_satisfaction(self, ai_response: str, memory_context: Dict) -> float:
        """Predict user satisfaction with current response"""
        base_score = 0.7  # Default satisfaction
        
        # Increase score if we have search results
        if 'search_results' in memory_context:
            base_score += 0.1
        
        # Increase score if we know user preferences
        prefs = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
        if prefs:
            base_score += 0.1
        
        # Increase score if response is personalized
        if any(word in ai_response.lower() for word in ['remember', 'know', 'preference']):
            base_score += 0.1
        
        return min(base_score, 1.0)

    def _extract_personality_insights(self, user_message: str, memory_context: Dict) -> Dict:
        """Extract personality insights from user interaction"""
        insights = {}
        
        message_lower = user_message.lower()
        
        # Communication style
        if len(user_message) > 50:
            insights['communication_style'] = 'detailed'
        elif len(user_message) < 20:
            insights['communication_style'] = 'brief'
        else:
            insights['communication_style'] = 'moderate'
        
        # Urgency level
        urgency_words = ['urgent', 'quick', 'asap', 'immediately', 'now']
        if any(word in message_lower for word in urgency_words):
            insights['urgency_preference'] = 'high'
        else:
            insights['urgency_preference'] = 'normal'
        
        # Politeness level
        polite_words = ['please', 'thank', 'appreciate', 'kindly']
        if any(word in message_lower for word in polite_words):
            insights['politeness_level'] = 'high'
        else:
            insights['politeness_level'] = 'normal'
        
        return insights

    # Additional utility methods for external suggestions

    def generate_external_suggestions_with_memory(self, query: str, search_type: str, 
                                                memory_context: Dict) -> str:
        """Generate external suggestions with perfect memory context"""
        try:
            # Extract user preferences and history for better external suggestions
            user_preferences = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
            shopping_behavior = memory_context.get('user_intelligence_profile', {}).get('shopping_behavior', '')
            previous_searches = memory_context.get('search_intelligence', {}).get('previous_searches', [])
            
            external_prompt = f"""
You are Finda AI helping a user find {search_type}s for: "{query}"

USER MEMORY CONTEXT:
- User Preferences: {json.dumps(user_preferences, indent=2) if user_preferences else "Learning preferences"}
- Shopping Behavior: {shopping_behavior}
- Previous Searches: {', '.join(previous_searches[-3:]) if previous_searches else "First search"}
- Communication Style: {memory_context.get('user_intelligence_profile', {}).get('communication_style', 'standard')}

Since we couldn't find perfect matches in Finda's database, provide personalized external shopping suggestions:

1. **Acknowledge our relationship**: Reference that you know their preferences from previous conversations
2. **Present 3-4 realistic external options** with:
   - Product/service name tailored to their known preferences
   - Estimated price in Nigerian Naira (₦) 
   - Platform name (Jumia, Konga, Amazon, etc.)
   - Why this matches their shopping behavior and preferences
   - Shipping/availability info for Nigeria

3. **Maintain Finda loyalty**: Encourage them to check back on Finda or try different search terms

4. **Match their communication style**: Be enthusiastic if they're enthusiastic, detailed if they prefer details

Be conversational, personal, and show you remember who they are and what they like!
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
                return self._create_fallback_external_response_with_memory(query, search_type, memory_context)
                
        except Exception as e:
            logger.error(f"External suggestions with memory error: {e}")
            return self._create_fallback_external_response_with_memory(query, search_type, memory_context)

    def _create_fallback_external_response_with_memory(self, query: str, search_type: str, 
                                                     memory_context: Dict) -> str:
        """Create fallback external response with memory context"""
        is_returning = memory_context.get('user_identity', {}).get('returning_user', False)
        user_preferences = memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
        
        if is_returning and user_preferences:
            return f"""
I remember you prefer {', '.join(list(user_preferences.keys())[:3])} - let me suggest some external options for "{query}":

🌐 **Based on your preferences, try these platforms:**
• **Jumia** - Great for {search_type}s matching your style
• **Konga** - Often has deals on items you like  
• **Amazon** - International shipping available for premium options

💡 **Tip**: I'll keep learning your preferences to find better matches on Finda next time!

🛍️ **Want to try a different search on Finda?** I remember what works for you!
"""
        else:
            return f"""
I searched our Finda marketplace for "{query}" but didn't find perfect matches right now.

🌐 **You might find options on these external platforms:**
• **Jumia** - Nigeria's leading marketplace
• **Konga** - Wide variety of products  
• **Amazon** - International shipping available
• **AliExpress** - Affordable options

💡 **Tip**: Try different keywords, or check back on Finda as we add new {search_type}s daily!

🛍️ **Let's keep searching together!** I'm learning what you like.
"""

    # Missing helper methods that were causing errors

    def _determine_conversation_milestone(self, message_analysis: Dict) -> str:
        """Determine if this is a conversation milestone"""
        intent = message_analysis.get('intent_analysis', {}).get('primary_intent', '')
        
        milestone_intents = {
            'purchase_intent': 'purchase_readiness',
            'comparison_request': 'decision_making',
            'price_inquiry': 'budget_consideration',
            'topic_change': 'topic_transition',
            'confusion': 'clarification_point'
        }
        
        return milestone_intents.get(intent, 'regular_interaction')

    def _refine_communication_style(self, user_message: str, memory_context: Dict) -> Dict:
        """Refine understanding of user's communication style"""
        current_style = self._analyze_interaction_style(user_message)
        
        # Get historical style
        historical_style = memory_context.get('user_intelligence_profile', {}).get('communication_style', 'unknown')
        
        refinements = {
            'current_message_style': current_style,
            'historical_style': historical_style,
            'style_consistency': current_style == historical_style,
            'refinement_confidence': 0.8 if current_style == historical_style else 0.5
        }
        
        return refinements

    def _extract_new_preferences(self, user_message: str, message_analysis: Dict) -> Dict:
        """Extract new preferences from current message"""
        new_preferences = {}
        
        # Extract product mentions as category preferences
        product_mentions = message_analysis.get('shopping_analysis', {}).get('product_mentions', [])
        if product_mentions:
            new_preferences['categories'] = product_mentions
        
        # Extract brand mentions
        brand_mentions = message_analysis.get('shopping_analysis', {}).get('brand_mentions', [])
        if brand_mentions:
            new_preferences['brands'] = brand_mentions
        
        # Extract location preferences
        location_mentions = message_analysis.get('shopping_analysis', {}).get('location_preferences', [])
        if location_mentions:
            new_preferences['locations'] = location_mentions
        
        # Extract price preferences
        price_mentions = message_analysis.get('shopping_analysis', {}).get('price_mentions', {})
        if price_mentions:
            new_preferences['price_range'] = price_mentions
        
        return new_preferences

    def _update_shopping_behavior(self, message_analysis: Dict) -> Dict:
        """Update shopping behavior understanding"""
        updates = {}
        
        # Update urgency patterns
        urgency_level = message_analysis.get('shopping_analysis', {}).get('urgency_level', 'normal')
        if urgency_level != 'normal':
            updates['urgency_pattern'] = urgency_level
        
        # Update decision making style
        intent = message_analysis.get('intent_analysis', {}).get('primary_intent', '')
        if intent in ['comparison_request', 'price_inquiry']:
            updates['decision_style'] = 'deliberate'
        elif intent == 'purchase_intent':
            updates['decision_style'] = 'decisive'
        
        return updates

    def _update_emotional_patterns(self, message_analysis: Dict) -> Dict:
        """Update emotional pattern understanding"""
        updates = {}
        
        current_emotion = message_analysis.get('emotional_analysis', {}).get('current_emotion', 'neutral')
        emotion_intensity = message_analysis.get('emotional_analysis', {}).get('emotion_intensity', 0.5)
        
        updates['recent_emotion'] = current_emotion
        updates['emotion_intensity'] = emotion_intensity
        
        # Track emotional needs
        emotional_needs = message_analysis.get('emotional_analysis', {}).get('emotional_needs', [])
        if emotional_needs:
            updates['emotional_needs'] = emotional_needs
        
        return updates

    def _generate_user_insights(self, message_analysis: Dict, memory_context: Dict) -> Dict:
        """Generate new insights about the user"""
        insights = {}
        
        # Communication insights
        communication_style = message_analysis.get('communication_analysis', {}).get('interaction_style', 'neutral')
        insights['communication_preference'] = communication_style
        
        # Shopping insights
        intent = message_analysis.get('intent_analysis', {}).get('primary_intent', '')
        if intent in ['purchase_intent', 'price_inquiry']:
            insights['shopping_readiness'] = 'high'
        elif intent in ['information_seeking', 'comparison_request']:
            insights['shopping_readiness'] = 'research_phase'
        
        # Engagement insights
        message_length = message_analysis.get('basic_analysis', {}).get('message_length', 0)
        if message_length > 100:
            insights['engagement_level'] = 'high_detail'
        elif message_length < 20:
            insights['engagement_level'] = 'brief_interaction'
        
        return insights

    def _assess_conversation_quality(self, message_analysis: Dict) -> float:
        """Assess quality of current conversation"""
        quality_score = 0.5  # Base score
        
        # Increase score for clear intent
        intent_confidence = message_analysis.get('intent_analysis', {}).get('intent_confidence', 0.5)
        quality_score += intent_confidence * 0.3
        
        # Increase score for emotional positivity
        emotion = message_analysis.get('emotional_analysis', {}).get('current_emotion', 'neutral')
        if emotion in ['excited', 'satisfied', 'curious']:
            quality_score += 0.2
        elif emotion in ['frustrated', 'confused']:
            quality_score -= 0.1
        
        return min(max(quality_score, 0.0), 1.0)

    def _assess_prediction_accuracy(self, message_analysis: Dict, memory_context: Dict) -> float:
        """Assess how accurate our predictions were"""
        # This would compare predicted vs actual user behavior
        # For now, return a baseline score
        base_accuracy = 0.7
        
        # Check if topic change was predicted correctly
        topic_change_detected = message_analysis.get('contextual_analysis', {}).get('topic_change_detected', False)
        conversation_stage = memory_context.get('contextual_intelligence', {}).get('conversation_stage', 'unknown')
        
        if conversation_stage in ['exploration', 'engagement'] and not topic_change_detected:
            base_accuracy += 0.1  # Good prediction - no unexpected topic change
        
        return min(base_accuracy, 1.0)

    def _identify_learning_opportunities(self, message_analysis: Dict) -> List[str]:
        """Identify learning opportunities from current interaction"""
        opportunities = []
        
        # Check for confusion indicators
        confusion_indicators = message_analysis.get('contextual_analysis', {}).get('confusion_indicators', [])
        if confusion_indicators:
            opportunities.append('improve_clarity')
        
        # Check for dissatisfaction
        dissatisfaction_signals = message_analysis.get('contextual_analysis', {}).get('dissatisfaction_signals', [])
        if dissatisfaction_signals:
            opportunities.append('improve_relevance')
        
        # Check for topic changes
        topic_change = message_analysis.get('contextual_analysis', {}).get('topic_change_detected', False)
        if topic_change:
            opportunities.append('better_topic_prediction')
        
        # Check for low intent confidence
        intent_confidence = message_analysis.get('intent_analysis', {}).get('intent_confidence', 1.0)
        if intent_confidence < 0.6:
            opportunities.append('improve_intent_detection')
        
        return opportunities

    def _extract_product_mentions(self, message: str) -> List[str]:
        """Extract specific product mentions from message"""
        message_lower = message.lower()
        
        # Common product categories and items
        products = []
        product_patterns = {
            'electronics': ['phone', 'iphone', 'samsung', 'laptop', 'computer', 'tablet', 'tv', 'camera'],
            'fashion': ['shoes', 'dress', 'shirt', 'pants', 'bag', 'jacket', 'clothes'],
            'home': ['furniture', 'sofa', 'bed', 'table', 'chair', 'fridge', 'washing machine'],
            'automotive': ['car', 'motorcycle', 'bike', 'tire', 'battery'],
            'beauty': ['makeup', 'perfume', 'skincare', 'hair', 'cosmetics']
        }
        
        for category, items in product_patterns.items():
            for item in items:
                if item in message_lower:
                    products.append(item)
        
        return list(set(products))

    def _extract_brand_mentions(self, message: str) -> List[str]:
        """Extract brand mentions from message"""
        message_lower = message.lower()
        
        common_brands = [
            'apple', 'samsung', 'nike', 'adidas', 'lg', 'sony', 'hp', 'dell',
            'toyota', 'honda', 'ford', 'coca cola', 'pepsi', 'gucci', 'prada'
        ]
        
        mentioned_brands = [brand for brand in common_brands if brand in message_lower]
        return mentioned_brands

    def _extract_price_mentions(self, message: str) -> Dict[str, Any]:
        """Extract price-related information from message"""
        price_info = {}
        
        # Find price ranges
        import re
        price_patterns = [
            r'under (\d+)',
            r'below (\d+)', 
            r'less than (\d+)',
            r'between (\d+) and (\d+)',
            r'(\d+) to (\d+)',
            r'around (\d+)',
            r'about (\d+)'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, message.lower())
            if matches:
                if len(matches[0]) == 2:  # Range pattern
                    price_info['range'] = {'min': int(matches[0][0]), 'max': int(matches[0][1])}
                else:  # Single value pattern
                    if 'under' in pattern or 'below' in pattern or 'less than' in pattern:
                        price_info['max'] = int(matches[0])
                    else:
                        price_info['target'] = int(matches[0])
                break
        
        return price_info


# Create global instance
enhanced_gemini_client = PerfectAIGeminiClient()