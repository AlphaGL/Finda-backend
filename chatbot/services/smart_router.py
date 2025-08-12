# ai_chatbot/services/smart_router.py
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
import json
import re

from .local_search import LocalSearchService
from .gemini_client import GeminiAIClient
from .web_search import WebSearchService
from .multimodal import MultimodalProcessor

logger = logging.getLogger(__name__)


class SmartChatbotRouter:
    """
    Intelligent router that manages the flow between local database search,
    external web search, and AI processing based on user queries and context
    """
    
    def __init__(self):
        # Initialize all services
        self.local_search = LocalSearchService()
        self.gemini_client = GeminiAIClient()
        self.web_search = WebSearchService()
        self.multimodal = MultimodalProcessor()
        
        # Router configuration
        self.config = {
            'local_search_threshold': 3,  # Minimum local results before going external
            'confidence_threshold': 0.7,  # Minimum confidence for local results
            'max_response_time': 30,      # Maximum response time in seconds
            'hybrid_search_enabled': True,
            'external_search_enabled': True,
            'cache_enabled': True,
            'cache_timeout': 1800,        # 30 minutes
        }
        
        # Load configuration from Django settings
        chatbot_settings = getattr(settings, 'CHATBOT_SETTINGS', {})
        self.config.update(chatbot_settings)
        
        # Intent classification keywords
        self.intent_keywords = {
            'product_search': [
                'buy', 'purchase', 'price', 'cost', 'sell', 'selling', 'product',
                'item', 'shop', 'store', 'market', 'find', 'looking for', 'need'
            ],
            'service_search': [
                'service', 'hire', 'book', 'appointment', 'professional', 'expert',
                'help', 'assistance', 'contractor', 'freelancer', 'work', 'job'
            ],
            'comparison': [
                'compare', 'vs', 'versus', 'difference', 'better', 'best', 'which',
                'recommend', 'suggestion', 'choose', 'decide'
            ],
            'location_query': [
                'where', 'location', 'near', 'around', 'close', 'nearby',
                'distance', 'map', 'address', 'directions'
            ],
            'price_inquiry': [
                'how much', 'price', 'cost', 'expensive', 'cheap', 'affordable',
                'budget', 'payment', 'pay', 'money', 'discount', 'deal'
            ],
            'general_info': [
                'what', 'how', 'why', 'when', 'tell me', 'explain', 'describe',
                'information', 'details', 'about', 'help', 'question'
            ]
        }
    
    async def process_message(
        self, 
        user_message: str,
        message_type: str = 'text',
        file_data: Any = None,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main method to process user messages and route to appropriate services
        
        Args:
            user_message: User's text message
            message_type: Type of message (text, image, voice)
            file_data: File data for image/voice messages
            context: Conversation context and user preferences
            
        Returns:
            Dict containing the complete response
        """
        try:
            start_time = datetime.now()
            
            # Initialize response structure
            response = {
                'success': True,
                'user_message': user_message,
                'message_type': message_type,
                'search_strategy': 'hybrid',
                'local_results': {},
                'external_results': {},
                'ai_response': {},
                'final_response': '',
                'metadata': {
                    'processing_time': 0,
                    'services_used': [],
                    'confidence_score': 0.0,
                    'search_mode': 'unknown'
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # Process different message types
            processed_input = await self._process_input_by_type(
                user_message, message_type, file_data
            )
            
            if not processed_input['success']:
                response['success'] = False
                response['final_response'] = processed_input.get('error', 'Failed to process input')
                return response
            
            # Update message with processed content
            enhanced_message = processed_input.get('enhanced_message', user_message)
            response['processed_input'] = processed_input
            
            # Analyze intent and determine search strategy
            intent_analysis = await self._analyze_intent(enhanced_message, context)
            response['intent'] = intent_analysis
            
            # Determine search strategy based on intent
            search_strategy = self._determine_search_strategy(intent_analysis, context)
            response['search_strategy'] = search_strategy['strategy']
            response['metadata']['search_mode'] = search_strategy['mode']
            
            # Execute search strategy
            search_results = await self._execute_search_strategy(
                enhanced_message, search_strategy, context
            )
            
            # Store search results
            response['local_results'] = search_results.get('local', {})
            response['external_results'] = search_results.get('external', {})
            response['metadata']['services_used'] = search_results.get('services_used', [])
            
            # Generate AI response using Gemini
            ai_response = await self._generate_ai_response(
                enhanced_message, search_results, context, intent_analysis
            )
            
            response['ai_response'] = ai_response
            response['final_response'] = ai_response.get('response', 'I apologize, but I could not generate a proper response.')
            response['metadata']['confidence_score'] = ai_response.get('confidence_score', 0.0)
            
            # Calculate total processing time
            end_time = datetime.now()
            response['metadata']['processing_time'] = (end_time - start_time).total_seconds()
            
            # Cache the response if appropriate
            if self.config['cache_enabled'] and response['success']:
                await self._cache_response(user_message, context, response)
            
            logger.info(
                f"Message processed successfully in {response['metadata']['processing_time']:.2f}s "
                f"using {response['search_strategy']} strategy"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'final_response': "I'm sorry, but I encountered an error processing your request. Please try again.",
                'timestamp': datetime.now().isoformat()
            }
    
    async def _process_input_by_type(
        self, 
        message: str, 
        message_type: str, 
        file_data: Any
    ) -> Dict[str, Any]:
        """Process different types of input (text, image, voice)"""
        try:
            result = {
                'success': True,
                'message_type': message_type,
                'enhanced_message': message,
                'extracted_info': {}
            }
            
            if message_type == 'image' and file_data:
                # Process image
                image_result = await self.multimodal.process_image(
                    file_data, message, 'product_search'
                )
                
                if image_result['success']:
                    result['extracted_info']['image'] = image_result
                    
                    # Enhance message with image analysis
                    ocr_text = image_result.get('ocr_text', '')
                    if ocr_text:
                        result['enhanced_message'] = f"{message} [Image contains text: {ocr_text}]"
                    else:
                        result['enhanced_message'] = f"{message} [User uploaded an image for analysis]"
                else:
                    result['success'] = False
                    result['error'] = image_result.get('error', 'Failed to process image')
            
            elif message_type == 'voice' and file_data:
                # Process voice note
                voice_result = await self.multimodal.process_voice_note(file_data)
                
                if voice_result['success'] and voice_result.get('transcription', {}).get('text'):
                    result['extracted_info']['voice'] = voice_result
                    transcribed_text = voice_result['transcription']['text']
                    
                    # Use transcribed text as the main message
                    result['enhanced_message'] = transcribed_text
                else:
                    result['success'] = False
                    result['error'] = voice_result.get('error', 'Failed to transcribe voice note')
            
            elif message_type == 'text':
                # For text messages, just return as is
                pass
            
            else:
                result['success'] = False
                result['error'] = f"Unsupported message type: {message_type}"
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _analyze_intent(self, message: str, context: Dict = None) -> Dict[str, Any]:
        """Analyze user intent from message"""
        try:
            intent_analysis = {
                'primary_intent': 'general_info',
                'confidence': 0.5,
                'detected_intents': {},
                'entities': {
                    'products': [],
                    'services': [],
                    'locations': [],
                    'prices': [],
                    'brands': []
                },
                'search_type': 'both',  # product, service, both
                'urgency': 'normal',    # low, normal, high
                'specificity': 'medium' # low, medium, high
            }
            
            message_lower = message.lower()
            
            # Score each intent based on keyword matches
            for intent_type, keywords in self.intent_keywords.items():
                score = sum(1 for keyword in keywords if keyword in message_lower)
                if score > 0:
                    intent_analysis['detected_intents'][intent_type] = score / len(keywords)
            
            # Determine primary intent
            if intent_analysis['detected_intents']:
                primary_intent = max(
                    intent_analysis['detected_intents'].items(),
                    key=lambda x: x[1]
                )[0]
                intent_analysis['primary_intent'] = primary_intent
                intent_analysis['confidence'] = intent_analysis['detected_intents'][primary_intent]
            
            # Extract entities
            intent_analysis['entities'] = await self._extract_entities(message)
            
            # Determine search type
            product_score = intent_analysis['detected_intents'].get('product_search', 0)
            service_score = intent_analysis['detected_intents'].get('service_search', 0)
            
            if product_score > service_score * 1.5:
                intent_analysis['search_type'] = 'product'
            elif service_score > product_score * 1.5:
                intent_analysis['search_type'] = 'service'
            
            # Determine urgency
            urgency_words = ['urgent', 'asap', 'immediately', 'now', 'quick', 'fast']
            if any(word in message_lower for word in urgency_words):
                intent_analysis['urgency'] = 'high'
            
            # Determine specificity
            if len(intent_analysis['entities']['products']) > 0 or len(intent_analysis['entities']['brands']) > 0:
                intent_analysis['specificity'] = 'high'
            elif intent_analysis['confidence'] > 0.7:
                intent_analysis['specificity'] = 'medium'
            else:
                intent_analysis['specificity'] = 'low'
            
            return intent_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing intent: {str(e)}")
            return {
                'primary_intent': 'general_info',
                'confidence': 0.3,
                'error': str(e)
            }
    
    async def _extract_entities(self, message: str) -> Dict[str, List[str]]:
        """Extract entities from message"""
        entities = {
            'products': [],
            'services': [],
            'locations': [],
            'prices': [],
            'brands': []
        }
        
        try:
            # Extract prices
            price_patterns = [
                r'[\$₦£€]\s*[\d,]+(?:\.\d{2})?',
                r'[\d,]+(?:\.\d{2})?\s*(?:dollars?|naira|pounds?|euros?)',
                r'under\s+[\$₦£€]?\s*[\d,]+',
                r'above\s+[\$₦£€]?\s*[\d,]+',
                r'between\s+[\$₦£€]?\s*[\d,]+\s+and\s+[\$₦£€]?\s*[\d,]+'
            ]
            
            for pattern in price_patterns:
                matches = re.findall(pattern, message, re.IGNORECASE)
                entities['prices'].extend(matches)
            
            # Extract potential product/brand names (capitalized words)
            capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', message)
            
            # Common brand names (you can expand this list)
            known_brands = [
                'Apple', 'Samsung', 'Sony', 'LG', 'HP', 'Dell', 'Lenovo', 'Asus',
                'Nike', 'Adidas', 'Toyota', 'Honda', 'Ford', 'Mercedes', 'BMW'
            ]
            
            for word in capitalized_words:
                if word in known_brands or len(word) > 3:  # Potential brand/product
                    if any(brand.lower() in word.lower() for brand in known_brands):
                        entities['brands'].append(word)
                    else:
                        entities['products'].append(word)
            
            # Extract locations (cities, states, countries)
            location_indicators = ['in', 'at', 'near', 'from', 'to']
            words = message.split()
            
            for i, word in enumerate(words):
                if word.lower() in location_indicators and i + 1 < len(words):
                    next_word = words[i + 1]
                    if next_word[0].isupper():  # Likely a proper noun (location)
                        entities['locations'].append(next_word)
            
            # Extract service types
            service_keywords = [
                'cleaning', 'repair', 'maintenance', 'installation', 'design',
                'development', 'consulting', 'tutoring', 'photography', 'catering'
            ]
            
            for keyword in service_keywords:
                if keyword in message.lower():
                    entities['services'].append(keyword)
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}")
            return entities
    
    def _determine_search_strategy(self, intent: Dict, context: Dict = None) -> Dict[str, Any]:
        """Determine the best search strategy based on intent and context"""
        strategy = {
            'strategy': 'hybrid',  # local_only, external_only, hybrid
            'mode': 'comprehensive',  # quick, comprehensive, detailed
            'priority': 'local_first',  # local_first, external_first, simultaneous
            'confidence_required': 0.7,
            'max_local_results': 10,
            'max_external_results': 10,
            'enable_ai_enhancement': True
        }
        
        try:
            primary_intent = intent.get('primary_intent', 'general_info')
            confidence = intent.get('confidence', 0.5)
            specificity = intent.get('specificity', 'medium')
            
            # High confidence and specific queries should try local first
            if confidence > 0.8 and specificity == 'high':
                strategy['priority'] = 'local_first'
                strategy['confidence_required'] = 0.6
            
            # Product/service searches should be comprehensive
            if primary_intent in ['product_search', 'service_search']:
                strategy['mode'] = 'comprehensive'
                strategy['max_local_results'] = 15
                
            # Comparison queries need both local and external
            elif primary_intent == 'comparison':
                strategy['strategy'] = 'hybrid'
                strategy['priority'] = 'simultaneous'
                strategy['mode'] = 'detailed'
                
            # General info can be handled mostly by AI
            elif primary_intent == 'general_info':
                strategy['strategy'] = 'hybrid'
                strategy['enable_ai_enhancement'] = True
                strategy['mode'] = 'quick'
                
            # Location queries should prioritize local
            elif primary_intent == 'location_query':
                strategy['priority'] = 'local_first'
                strategy['confidence_required'] = 0.5
            
            # Price inquiries might need external comparison
            elif primary_intent == 'price_inquiry':
                strategy['strategy'] = 'hybrid'
                strategy['priority'] = 'simultaneous'
            
            # Adjust based on context
            if context:
                # If user has location preferences, prioritize local
                if context.get('location_context'):
                    strategy['priority'] = 'local_first'
                
                # If previous searches were unsuccessful locally, try external
                recent_searches = context.get('recent_searches', [])
                if recent_searches:
                    recent_local_success = sum(
                        1 for search in recent_searches[-3:] 
                        if search.get('local_results_count', 0) > 0
                    )
                    if recent_local_success == 0:
                        strategy['priority'] = 'external_first'
            
            return strategy
            
        except Exception as e:
            logger.error(f"Error determining search strategy: {str(e)}")
            return strategy
    
    async def _execute_search_strategy(
        self, 
        message: str, 
        strategy: Dict, 
        context: Dict = None
    ) -> Dict[str, Any]:
        """Execute the determined search strategy"""
        results = {
            'local': {},
            'external': {},
            'services_used': [],
            'total_results': 0,
            'success': True
        }
        
        try:
            # Extract search filters from context
            filters = self._build_search_filters(context)
            
            if strategy['strategy'] in ['local_only', 'hybrid']:
                # Execute local search
                if strategy['priority'] == 'local_first' or strategy['priority'] == 'simultaneous':
                    local_results = await self._execute_local_search(message, filters, strategy)
                    results['local'] = local_results
                    results['services_used'].append('local_search')
                    results['total_results'] += local_results.get('total_results', 0)
            
            # Determine if external search is needed
            need_external = self._should_search_external(results, strategy)
            
            if need_external and strategy['strategy'] in ['external_only', 'hybrid']:
                # Get search keywords from Gemini
                gemini_strategy = await self.gemini_client.search_web_for_products(message, context)
                
                if gemini_strategy['success']:
                    search_keywords = gemini_strategy.get('recommended_keywords', [message])
                    
                    # Execute external search
                    external_results = await self._execute_external_search(
                        message, search_keywords, context, strategy
                    )
                    results['external'] = external_results
                    results['services_used'].append('web_search')
                    results['total_results'] += external_results.get('total_found', 0)
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing search strategy: {str(e)}")
            results['success'] = False
            results['error'] = str(e)
            return results
    
    def _should_search_external(self, current_results: Dict, strategy: Dict) -> bool:
        """Determine if external search is needed based on current results"""
        local_count = current_results.get('local', {}).get('total_results', 0)
        threshold = strategy.get('confidence_required', 0.7)
        min_results = self.config.get('local_search_threshold', 3)
        
        # Always search external if strategy requires it
        if strategy.get('priority') == 'external_first':
            return True
        
        if strategy.get('priority') == 'simultaneous':
            return True
        
        # Search external if local results are insufficient
        if local_count < min_results:
            return True
        
        # Search external if local results have low confidence
        local_confidence = current_results.get('local', {}).get('search_metadata', {}).get('confidence_score', 0)
        if local_confidence < threshold:
            return True
        
        return False
    
    async def _execute_local_search(self, message: str, filters: Dict, strategy: Dict) -> Dict:
        """Execute local database search"""
        try:
            return await asyncio.to_thread(
                self.local_search.search,
                message,
                **filters
            )
        except Exception as e:
            logger.error(f"Error in local search: {str(e)}")
            return {'total_results': 0, 'error': str(e), 'success': False}
    
    async def _execute_external_search(
        self, 
        message: str, 
        search_keywords: List[str], 
        context: Dict, 
        strategy: Dict
    ) -> Dict:
        """Execute external web search"""
        try:
            location_context = context.get('location_context') if context else None
            max_results = strategy.get('max_external_results', 10)
            
            return await self.web_search.search_products(
                message,
                search_keywords,
                location_context,
                max_results
            )
        except Exception as e:
            logger.error(f"Error in external search: {str(e)}")
            return {'total_found': 0, 'error': str(e), 'success': False}
    
    def _build_search_filters(self, context: Dict = None) -> Dict:
        """Build search filters from context"""
        filters = {}
        
        if not context:
            return filters
        
        # Location filters
        location_context = context.get('location_context', {})
        if location_context.get('country_id'):
            filters['country_id'] = location_context['country_id']
        if location_context.get('state_id'):
            filters['state_id'] = location_context['state_id']
        if location_context.get('city_id'):
            filters['city_id'] = location_context['city_id']
        
        # User preferences
        user_preferences = context.get('user_preferences', {})
        if user_preferences.get('max_price'):
            filters['max_price'] = user_preferences['max_price']
        if user_preferences.get('min_price'):
            filters['min_price'] = user_preferences['min_price']
        if user_preferences.get('preferred_brands'):
            filters['brands'] = user_preferences['preferred_brands']
        
        return filters
    
    async def _generate_ai_response(
        self, 
        message: str, 
        search_results: Dict, 
        context: Dict, 
        intent: Dict
    ) -> Dict[str, Any]:
        """Generate AI response using Gemini"""
        try:
            # Prepare context for Gemini
            ai_context = {
                'conversation_history': context.get('conversation_history', [])[-5:],  # Last 5 messages
                'user_preferences': context.get('user_preferences', {}),
                'location_context': context.get('location_context', {}),
                'search_results': {
                    'products': search_results.get('local', {}).get('products', [])[:5],
                    'services': search_results.get('local', {}).get('services', [])[:5],
                    'external_products': search_results.get('external', {}).get('products', [])[:5],
                    'total_results': search_results.get('total_results', 0)
                }
            }
            
            # Determine appropriate prompt type
            prompt_type = self._determine_prompt_type(intent)
            
            # Generate response
            response = await self.gemini_client.generate_response(
                message,
                ai_context,
                prompt_type,
                include_search_results=True
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return {
                'response': "I found some results for your query, but I'm having trouble generating a detailed response. Please let me know if you'd like me to try again.",
                'success': False,
                'error': str(e)
            }
    
    def _determine_prompt_type(self, intent: Dict) -> str:
        """Determine the appropriate prompt type for Gemini"""
        primary_intent = intent.get('primary_intent', 'general_info')
        
        prompt_mapping = {
            'product_search': 'product_recommender',
            'service_search': 'service_matcher',
            'comparison': 'product_recommender',
            'price_inquiry': 'price_analyst',
            'general_info': 'marketplace_assistant'
        }
        
        return prompt_mapping.get(primary_intent, 'marketplace_assistant')
    
    async def _cache_response(self, message: str, context: Dict, response: Dict):
        """Cache response for future use"""
        try:
            cache_key = self._generate_cache_key(message, context)
            
            # Only cache successful responses
            if response.get('success') and response.get('final_response'):
                cache_data = {
                    'final_response': response['final_response'],
                    'metadata': response['metadata'],
                    'cached_at': datetime.now().isoformat()
                }
                
                cache.set(cache_key, cache_data, self.config['cache_timeout'])
                logger.info(f"Response cached with key: {cache_key}")
                
        except Exception as e:
            logger.error(f"Error caching response: {str(e)}")
    
    def _generate_cache_key(self, message: str, context: Dict = None) -> str:
        """Generate cache key for message and context"""
        import hashlib
        
        cache_data = {
            'message': message.lower().strip(),
            'location': context.get('location_context', {}) if context else {},
            'preferences': context.get('user_preferences', {}) if context else {}
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        return f"chatbot_response_{hashlib.md5(cache_string.encode()).hexdigest()}"
    
    async def get_cached_response(self, message: str, context: Dict = None) -> Optional[Dict]:
        """Get cached response if available"""
        try:
            if not self.config['cache_enabled']:
                return None
            
            cache_key = self._generate_cache_key(message, context)
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.info("Returning cached response")
                return {
                    'final_response': cached_data['final_response'],
                    'metadata': cached_data['metadata'],
                    'from_cache': True,
                    'cached_at': cached_data['cached_at']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving cached response: {str(e)}")
            return None
    
    def update_config(self, new_config: Dict):
        """Update router configuration"""
        self.config.update(new_config)
        logger.info(f"Router configuration updated: {new_config}")
    
    def get_config(self) -> Dict:
        """Get current router configuration"""
        return self.config.copy()
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all services"""
        return {
            'local_search': 'active',
            'web_search': 'active',
            'gemini_client': 'active' if self.gemini_client.api_key else 'inactive',
            'multimodal': 'active',
            'cache_enabled': self.config['cache_enabled'],
            'configuration': self.config
        }


# Helper functions
def calculate_response_quality_score(response: Dict) -> float:
    """Calculate quality score for a response"""
    score = 0.0
    
    # Base score for successful response
    if response.get('success'):
        score += 0.3
    
    # Score for having results
    total_results = response.get('metadata', {}).get('total_results', 0)
    if total_results > 0:
        score += min(0.3, total_results * 0.05)  # Up to 0.3 for results
    
    # Score for confidence
    confidence = response.get('metadata', {}).get('confidence_score', 0)
    score += confidence * 0.2
    
    # Score for response completeness
    final_response = response.get('final_response', '')
    if len(final_response) > 50:
        score += 0.2
    
    return min(1.0, score)


def merge_search_results(local_results: Dict, external_results: Dict) -> Dict:
    """Merge local and external search results"""
    merged = {
        'products': [],
        'services': [],
        'total_count': 0,
        'sources': []
    }
    
    # Add local results
    if local_results.get('products'):
        for product in local_results['products']:
            product['source_type'] = 'local'
            merged['products'].append(product)
        merged['sources'].append('local_database')
    
    if local_results.get('services'):
        merged['services'] = local_results['services']
        merged['sources'].append('local_database')
    
    # Add external results
    if external_results.get('products'):
        for product in external_results['products']:
            product['source_type'] = 'external'
            merged['products'].append(product)
        merged['sources'].append('web_search')
    
    # Remove duplicates and rank
    merged['products'] = remove_duplicate_products(merged['products'])
    merged['total_count'] = len(merged['products']) + len(merged['services'])
    
    return merged


def remove_duplicate_products(products: List[Dict]) -> List[Dict]:
    """Remove duplicate products from list"""
    seen_titles = []
    unique_products = []
    
    for product in products:
        title = product.get('title', '').lower()
        
        # Check similarity with existing titles
        is_duplicate = False
        for seen_title in seen_titles:
            if calculate_similarity(title, seen_title) > 0.8:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_products.append(product)
            seen_titles.append(title)
    
    return unique_products


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two text strings"""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0