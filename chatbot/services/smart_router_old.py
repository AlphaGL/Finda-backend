# ai_chatbot/services/smart_router.py (FIXED VERSION)
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .gemini_client import GeminiAIClient
from .local_search import LocalSearchService
from .external_search import EnhancedExternalSearchService
from .multimodal import MultimodalProcessor
from ..utils import MessageProcessor, SearchHelper, PerformanceMonitor

logger = logging.getLogger(__name__)

class SmartChatbotRouter:
    """Enhanced smart router with SerpAPI external search integration"""
    
    def __init__(self):
        self.gemini_client = GeminiAIClient()
        self.local_search = LocalSearchService()
        self.external_search = EnhancedExternalSearchService()
        self.multimodal_processor = MultimodalProcessor()
        self.message_processor = MessageProcessor()
        self.search_helper = SearchHelper()
        self.performance_monitor = PerformanceMonitor()
        
        # Search strategy configuration - LOWERED THRESHOLD FOR BETTER EXTERNAL SEARCH TRIGGERING
        self.min_local_results_threshold = 1  # Lower threshold to trigger external search more often
        self.external_search_enabled = True
        self.max_external_results = 10
    
    async def process_message(
        self, 
        message: str, 
        message_type: str = 'text', 
        file_data: Any = None, 
        context: Dict = None
    ) -> Dict[str, Any]:
        """
        Main message processing method with enhanced external search
        """
        try:
            self.performance_monitor.start_timer('total_processing')
            logger.info(f"Processing message: '{message}' (type: {message_type})")
            
            # Initialize context if not provided
            if context is None:
                context = {}
            
            # Handle different message types
            if message_type == 'image' and file_data:
                return await self._process_image_message(file_data, message, context)
            elif message_type == 'voice' and file_data:
                return await self._process_voice_message(file_data, context)
            else:
                return await self._process_text_message(message, context)
                
        except Exception as e:
            logger.error(f"Error in message processing: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'final_response': "I apologize, but I encountered an error processing your message. Please try again.",
                'search_strategy': 'error',
                'metadata': {'processing_time': 0, 'error': str(e)}
            }
        finally:
            total_time = self.performance_monitor.end_timer('total_processing')
    
    async def _process_text_message(self, message: str, context: Dict) -> Dict[str, Any]:
        """Process text message with enhanced search strategy"""
        try:
            logger.info(f"Processing text message: {message}")
            
            # Step 1: Extract intent and entities
            intent_analysis = self.message_processor.extract_intent(message)
            logger.info(f"Intent analysis: {intent_analysis}")
            
            # Step 2: Determine search strategy
            search_strategy = self._determine_search_strategy(intent_analysis, context)
            logger.info(f"Selected search strategy: {search_strategy}")
            
            # Step 3: Execute search strategy
            if search_strategy == 'local_only':
                return await self._execute_local_only_strategy(message, intent_analysis, context)
            elif search_strategy == 'external_only':
                return await self._execute_external_only_strategy(message, intent_analysis, context)
            elif search_strategy == 'hybrid_local_first':
                return await self._execute_hybrid_local_first_strategy(message, intent_analysis, context)
            elif search_strategy == 'hybrid_concurrent':
                return await self._execute_hybrid_concurrent_strategy(message, intent_analysis, context)
            else:  # ai_response_only
                return await self._execute_ai_response_only_strategy(message, intent_analysis, context)
                
        except Exception as e:
            logger.error(f"Error processing text message: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'final_response': "I encountered an error processing your message. Please try again.",
                'search_strategy': 'error'
            }
    # def _determine_search_strategy(self, intent_analysis: Dict, context: Dict) -> str:
    #     """Determine the best search strategy based on intent and context"""
    #     primary_intent = intent_analysis.get('primary_intent', 'general_query')
    #     confidence = intent_analysis.get('confidence', 0.3)
        
    #     logger.info(f"Determining strategy for intent: {primary_intent} (confidence: {confidence})")
        
    #     # Check if this is a product/service search
    #     search_intents = ['product_search', 'service_request', 'price_inquiry', 'comparison']
        
    #     # ALWAYS try hybrid approach for product/service searches
    #     if primary_intent in search_intents:
    #         logger.info(f"Product/service search detected, using hybrid_local_first strategy")
    #         return 'hybrid_local_first'
    #     elif any(keyword in intent_analysis.get('entities', []) for keyword in ['buy', 'purchase', 'price', 'cost', 'find']):
    #         logger.info(f"Purchase-related keywords detected, using hybrid_local_first strategy")
    #         return 'hybrid_local_first'
    #     elif primary_intent in ['greeting', 'goodbye']:
    #         return 'ai_response_only'
    #     elif 'online' in intent_analysis.get('entities', []) or 'external' in context.get('preferences', {}):
    #         return 'external_only'
    #     else:
    #         # For any ambiguous query that might be a search, use hybrid approach
    #         logger.info(f"Ambiguous query, defaulting to hybrid_local_first strategy")
    #         return 'hybrid_local_first'
    def _determine_search_strategy(self, intent_analysis: Dict, context: Dict) -> str:
        """Determine the best search strategy based on intent and context"""
        primary_intent = intent_analysis.get('primary_intent', 'general_query')
        confidence = intent_analysis.get('confidence', 0.3)
        original_message = intent_analysis.get('original_message', '').lower()
        
        logger.info(f"Determining strategy for intent: {primary_intent} (confidence: {confidence})")
        logger.info(f"Original message: '{original_message}'")
        
        # AGGRESSIVE SEARCH DETECTION - trigger external search for most queries
        search_indicators = [
            # Shopping keywords
            'buy', 'purchase', 'shop', 'store', 'order', 'price', 'cost', 'cheap', 
            'expensive', 'discount', 'deal', 'sale', 'offer',
            
            # Product keywords  
            'samsung', 'iphone', 'laptop', 'phone', 'computer', 'tv', 'tablet',
            'watch', 'headphones', 'camera', 'speaker', 'mouse', 'keyboard',
            
            # Platform keywords
            'jumia', 'konga', 'amazon', 'ebay', 'aliexpress', 'online',
            
            # Search intent keywords
            'find', 'looking for', 'need', 'want', 'search', 'where to buy',
            'where can i', 'how much', 'give me', 'show me', 'results from',
            
            # Comparison keywords
            'compare', 'vs', 'versus', 'better', 'best', 'which', 'difference',
            
            # Price range keywords
            'under', 'below', 'above', 'between', 'around', 'budget', 'affordable'
        ]
        
        # Check if any search indicators are present
        has_search_indicators = any(indicator in original_message for indicator in search_indicators)
        
        # Check for specific external request
        external_request_phrases = [
            'results from', 'search on', 'find on', 'check on', 'look on',
            'jumia', 'konga', 'amazon', 'online'
        ]
        wants_external = any(phrase in original_message for phrase in external_request_phrases)
        
        # Decision logic - BE MORE AGGRESSIVE
        if primary_intent in ['product_search', 'service_request', 'price_inquiry', 'comparison']:
            logger.info(f"Direct product/service intent detected -> hybrid_local_first")
            return 'hybrid_local_first'
        elif has_search_indicators or wants_external:
            logger.info(f"Search indicators detected -> hybrid_local_first")
            return 'hybrid_local_first'
        elif primary_intent in ['greeting', 'goodbye']:
            logger.info(f"Greeting/goodbye -> ai_only")
            return 'ai_response_only'
        else:
            # For ANY ambiguous query, default to hybrid search
            logger.info(f"Ambiguous query -> defaulting to hybrid_local_first")
            return 'hybrid_local_first'
    
    # async def _execute_hybrid_local_first_strategy(self, message: str, intent_analysis: Dict, context: Dict) -> Dict[str, Any]:
    #     """Execute hybrid search strategy - local first, then external if needed"""
    #     try:
    #         logger.info(f"Executing hybrid local-first strategy for: {message}")
            
    #         # Step 1: Try local search first
    #         local_results = await self._perform_local_search(message, intent_analysis, context)
    #         local_total = local_results.get('total_results', 0)
            
    #         logger.info(f"Local search returned {local_total} results")
            
    #         # Step 2: Always try external search for product/service queries, regardless of local results
    #         # This ensures we show both local AND external options to users
    #         external_results = {}
            
    #         # Check if this looks like a product/service search
    #         is_product_service_search = (
    #             intent_analysis.get('primary_intent') in ['product_search', 'service_request', 'price_inquiry', 'comparison'] or
    #             any(keyword in message.lower() for keyword in ['buy', 'purchase', 'price', 'cost', 'find', 'need', 'want', 'looking for']) or
    #             local_total == 0  # If no local results, definitely try external
    #         )
            
    #         if is_product_service_search and self.external_search_enabled:
    #             logger.info(f"Triggering external search for product/service query")
    #             external_results = await self._perform_external_search(message, intent_analysis, context)
    #             logger.info(f"External search returned {external_results.get('total_found', 0)} results")
            
    #         # Step 3: Generate AI response with both local and external data
    #         response = await self._generate_ai_response(message, intent_analysis, context, local_results, external_results)
            
    #         # Determine the final strategy based on what we found
    #         final_strategy = 'local_sufficient' if local_total >= self.min_local_results_threshold and not external_results.get('total_found', 0) else 'hybrid_local_first'
            
    #         return {
    #             'success': True,
    #             'search_strategy': final_strategy,
    #             'local_results': local_results,
    #             'external_results': external_results,
    #             'final_response': response,
    #             'intent': intent_analysis,
    #             'metadata': {
    #                 'processing_time': self.performance_monitor.get_metrics().get('total_processing', {}).get('duration', 0),
    #                 'confidence_score': intent_analysis.get('confidence', 0),
    #                 'services_used': self._get_services_used(local_results, external_results)
    #             }
    #         }
                
    #     except Exception as e:
    #         logger.error(f"Error in hybrid local-first strategy: {str(e)}")
    #         # Fallback to AI response only
    #         return await self._execute_ai_response_only_strategy(message, intent_analysis, context)
    
    async def _execute_hybrid_local_first_strategy(self, message: str, intent_analysis: Dict, context: Dict) -> Dict[str, Any]:
        """Execute hybrid search strategy - ALWAYS try external for potential product searches"""
        try:
            logger.info(f"Executing hybrid local-first strategy for: {message}")
            
            # Step 1: Try local search first (optional - can skip if you want external-only)
            local_results = await self._perform_local_search(message, intent_analysis, context)
            local_total = local_results.get('total_results', 0)
            
            logger.info(f"Local search returned {local_total} results")
            
            # Step 2: ALWAYS try external search for any query that reached this strategy
            external_results = {}
            
            if self.external_search_enabled:
                logger.info(f"Triggering external search for: {message}")
                external_results = await self._perform_external_search(message, intent_analysis, context)
                external_total = external_results.get('total_found', 0)
                logger.info(f"External search returned {external_total} results")
            
            # Step 3: Generate AI response
            ai_response = await self._generate_ai_response(message, intent_analysis, context, local_results, external_results)
            
            # Step 4: CRITICAL - Combine AI response with formatted external results
            final_response = ai_response
            
            external_total = external_results.get('total_found', 0)
            if external_total > 0:
                logger.info(f"Formatting and appending {external_total} external results")
                
                # Get formatted external results
                external_formatted = self.external_search.format_results_for_response(external_results)
                
                if external_formatted and external_formatted.strip():
                    # Combine AI response with external results
                    final_response = f"{ai_response}\n\n{external_formatted}"
                    logger.info(f"Successfully combined AI response ({len(ai_response)} chars) with external results ({len(external_formatted)} chars)")
                    logger.info(f"Final response length: {len(final_response)} chars")
                else:
                    logger.warning("External results formatting returned empty string")
            else:
                logger.info("No external results to append")
            
            return {
                'success': True,
                'search_strategy': 'hybrid_local_first',
                'local_results': local_results,
                'external_results': external_results,
                'final_response': final_response,  # This includes both AI + external results
                'intent': intent_analysis,
                'metadata': {
                    'processing_time': self.performance_monitor.get_metrics().get('total_processing', {}).get('duration', 0),
                    'confidence_score': intent_analysis.get('confidence', 0),
                    'services_used': self._get_services_used(local_results, external_results),
                    'ai_response_length': len(ai_response),
                    'external_results_count': external_total,
                    'final_response_length': len(final_response)
                }
            }
                
        except Exception as e:
            logger.error(f"Error in hybrid local-first strategy: {str(e)}", exc_info=True)
            # Fallback to AI response only
            return await self._execute_ai_response_only_strategy(message, intent_analysis, context)
    

    def _get_services_used(self, local_results: Dict, external_results: Dict) -> List[str]:
        """Get list of services used in the search"""
        services = ['gemini_ai']
        
        if local_results.get('total_results', 0) > 0:
            services.append('local_search')
        
        if external_results.get('total_found', 0) > 0:
            services.append('external_search')
        
        return services
    
    async def _execute_hybrid_concurrent_strategy(self, message: str, intent_analysis: Dict, context: Dict) -> Dict[str, Any]:
        """Execute concurrent search strategy - local and external simultaneously"""
        try:
            logger.info(f"Executing hybrid concurrent strategy for: {message}")
            
            # Run both searches concurrently
            local_task = self._perform_local_search(message, intent_analysis, context)
            external_task = self._perform_external_search(message, intent_analysis, context)
            
            local_results, external_results = await asyncio.gather(
                local_task, external_task, return_exceptions=True
            )
            
            # Handle any exceptions
            if isinstance(local_results, Exception):
                logger.error(f"Local search failed: {str(local_results)}")
                local_results = {'total_results': 0, 'products': [], 'services': []}
            
            if isinstance(external_results, Exception):
                logger.error(f"External search failed: {str(external_results)}")
                external_results = {'total_found': 0, 'products': [], 'services': []}
            
            # Generate AI response with both results
            response = await self._generate_ai_response(message, intent_analysis, context, local_results, external_results)
            
            return {
                'success': True,
                'search_strategy': 'hybrid_concurrent',
                'local_results': local_results,
                'external_results': external_results,
                'final_response': response,
                'intent': intent_analysis,
                'metadata': {
                    'processing_time': self.performance_monitor.get_metrics().get('total_processing', {}).get('duration', 0),
                    'confidence_score': intent_analysis.get('confidence', 0),
                    'services_used': self._get_services_used(local_results, external_results)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in hybrid concurrent strategy: {str(e)}")
            return await self._execute_ai_response_only_strategy(message, intent_analysis, context)
    
    async def _execute_external_only_strategy(self, message: str, intent_analysis: Dict, context: Dict) -> Dict[str, Any]:
        """Execute external search only strategy"""
        try:
            logger.info(f"Executing external-only strategy for: {message}")
            
            external_results = await self._perform_external_search(message, intent_analysis, context)
            
            # Generate AI response with external data only
            response = await self._generate_ai_response(message, intent_analysis, context, {}, external_results)
            
            return {
                'success': True,
                'search_strategy': 'external_only',
                'local_results': {},
                'external_results': external_results,
                'final_response': response,
                'intent': intent_analysis,
                'metadata': {
                    'processing_time': self.performance_monitor.get_metrics().get('total_processing', {}).get('duration', 0),
                    'confidence_score': intent_analysis.get('confidence', 0),
                    'services_used': self._get_services_used({}, external_results)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in external-only strategy: {str(e)}")
            return await self._execute_ai_response_only_strategy(message, intent_analysis, context)
    
    async def _execute_local_only_strategy(self, message: str, intent_analysis: Dict, context: Dict) -> Dict[str, Any]:
        """Execute local search only strategy"""
        try:
            logger.info(f"Executing local-only strategy for: {message}")
            
            local_results = await self._perform_local_search(message, intent_analysis, context)
            
            # Generate AI response with local data only
            response = await self._generate_ai_response(message, intent_analysis, context, local_results, {})
            
            return {
                'success': True,
                'search_strategy': 'local_only',
                'local_results': local_results,
                'external_results': {},
                'final_response': response,
                'intent': intent_analysis,
                'metadata': {
                    'processing_time': self.performance_monitor.get_metrics().get('total_processing', {}).get('duration', 0),
                    'confidence_score': intent_analysis.get('confidence', 0),
                    'services_used': self._get_services_used(local_results, {})
                }
            }
            
        except Exception as e:
            logger.error(f"Error in local-only strategy: {str(e)}")
            return await self._execute_ai_response_only_strategy(message, intent_analysis, context)
    
    async def _execute_ai_response_only_strategy(self, message: str, intent_analysis: Dict, context: Dict) -> Dict[str, Any]:
        """Execute AI response only strategy (no search)"""
        try:
            logger.info(f"Executing AI-only strategy for: {message}")
            
            response = await self._generate_ai_response(message, intent_analysis, context, {}, {})
            
            return {
                'success': True,
                'search_strategy': 'ai_only',
                'local_results': {},
                'external_results': {},
                'final_response': response,
                'intent': intent_analysis,
                'metadata': {
                    'processing_time': self.performance_monitor.get_metrics().get('total_processing', {}).get('duration', 0),
                    'confidence_score': intent_analysis.get('confidence', 0),
                    'services_used': ['gemini_ai']
                }
            }
            
        except Exception as e:
            logger.error(f"Error in AI-only strategy: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'final_response': "I'm having trouble processing your request right now. Please try again.",
                'search_strategy': 'error'
            }
    
    async def _perform_local_search(self, message: str, intent_analysis: Dict, context: Dict) -> Dict[str, Any]:
        """Perform local database search"""
        try:
            logger.info(f"Performing local search for: {message}")
            
            # Build search filters
            filters = self.search_helper.build_search_filters(message, context) if hasattr(self.search_helper, 'build_search_filters') else {}
            
            # Determine search type based on intent
            search_type = 'both'  # Default
            if intent_analysis.get('primary_intent') == 'product_search':
                search_type = 'products'
            elif intent_analysis.get('primary_intent') == 'service_request':
                search_type = 'services'
            
            # Perform local search - this is now properly async
            result = await self.local_search.search(
                query=message,
                search_type=search_type,
                filters=filters,
                location_context=context.get('location_context')
            )
            
            logger.info(f"Local search completed: {result.get('success', False)}, found {result.get('total_results', 0)} results")
            return result
            
        except Exception as e:
            logger.error(f"Error performing local search: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'products': [],
                'services': [],
                'total_results': 0,
                'query': message,
                'search_type': 'both'
            }
        
    # async def _generate_ai_response(
    #     self, 
    #     message: str, 
    #     intent_analysis: Dict, 
    #     context: Dict, 
    #     local_results: Dict, 
    #     external_results: Dict
    # ) -> str:
    #     """Generate AI response using Gemini with search results"""
    #     try:
    #         logger.info(f"Generating AI response for message: {message}")
            
    #         # Build prompt with search results
    #         prompt = self._build_response_prompt(message, intent_analysis, context, local_results, external_results)
            
    #         # Generate response using Gemini
    #         response = await self.gemini_client.generate_response(prompt, context)
    #         logger.info(f"Generated base AI response, length: {len(response)}")
            
    #         # ALWAYS append external search results if available - this is the key fix
    #         external_total = external_results.get('total_found', 0)
    #         if external_total > 0:
    #             logger.info(f"Appending formatted external search results ({external_total} results)")
    #             external_formatted = self.external_search.format_results_for_response(external_results)
    #             if external_formatted and external_formatted.strip():
    #                 response += f"\n\n{external_formatted}"
    #                 logger.info(f"Successfully appended external results, total response length: {len(response)}")
    #             else:
    #                 logger.warning("External results formatting returned empty string")
            
    #         return response
            
    #     except Exception as e:
    #         logger.error(f"Error generating AI response: {str(e)}")
    #         return "I'm having trouble generating a response right now. Please try again."
    
    async def _generate_ai_response(
        self, 
        message: str, 
        intent_analysis: Dict, 
        context: Dict, 
        local_results: Dict, 
        external_results: Dict
    ) -> str:
        """Generate AI response using Gemini - DO NOT append external results here"""
        try:
            logger.info(f"Generating AI response for message: {message}")
            
            # Build prompt with search context
            prompt = self._build_response_prompt(message, intent_analysis, context, local_results, external_results)
            
            # Generate response using Gemini
            response = await self.gemini_client.generate_response(prompt, context)
            logger.info(f"Generated AI response, length: {len(response)}")
            
            # Return ONLY the AI response - external results are appended in the calling method
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return "I'm having trouble generating a response right now. Please try again."
    
    def _build_response_prompt(
        self, 
        message: str, 
        intent_analysis: Dict, 
        context: Dict, 
        local_results: Dict, 
        external_results: Dict
    ) -> str:
        """Build comprehensive prompt for AI response generation"""
        
        prompt_parts = [
            f"User query: {message}",
            f"Detected intent: {intent_analysis.get('primary_intent', 'general_query')}",
            f"User location: {context.get('location_context', {}).get('country', 'Nigeria')}"
        ]
        
        # Add local results if available
        local_total = local_results.get('total_results', 0)
        if local_total > 0:
            prompt_parts.append(f"\nLocal database results ({local_total} found):")
            
            if local_results.get('products'):
                prompt_parts.append("Products:")
                for i, product in enumerate(local_results['products'][:5], 1):
                    prompt_parts.append(f"{i}. {product.get('name', 'Unknown')} - {product.get('formatted_price', 'N/A')}")
            
            if local_results.get('services'):
                prompt_parts.append("Services:")
                for i, service in enumerate(local_results['services'][:5], 1):
                    prompt_parts.append(f"{i}. {service.get('name', 'Unknown')} - {service.get('price_range', 'Contact for pricing')}")
        
        # Add external results if available
        external_total = external_results.get('total_found', 0)
        if external_total > 0:
            prompt_parts.append(f"\nExternal search results ({external_total} found):")
            
            if external_results.get('products'):
                prompt_parts.append("External Products:")
                for i, product in enumerate(external_results['products'][:3], 1):
                    prompt_parts.append(f"{i}. {product.get('name', 'Unknown')} - {product.get('formatted_price', 'N/A')} from {product.get('source', 'External Store')}")
            
            if external_results.get('services'):
                prompt_parts.append("External Services:")
                for i, service in enumerate(external_results['services'][:3], 1):
                    prompt_parts.append(f"{i}. {service.get('name', 'Unknown')} - {service.get('location', 'Unknown location')}")
        
        # Add instructions
        prompt_parts.extend([
            "\nInstructions:",
            "1. Provide a helpful, conversational response about the search results",
            "2. If both local and external results are available, mention that you found options both locally and online",
            "3. Highlight key information like prices, locations, and contact details",
            "4. If no results were found, suggest alternative search terms or approaches",
            "5. Be friendly and helpful while providing the information",
            "6. Keep your response concise - detailed external results will be appended separately",
            "7. DO NOT format external results in your response - they will be formatted separately"
        ])
        
        return "\n".join(prompt_parts)
    
    async def _process_image_message(self, image_file, message: str, context: Dict) -> Dict[str, Any]:
        """Process image message (existing implementation)"""
        try:
            logger.info(f"Processing image message with text: {message}")
            return await self.multimodal_processor.process_image(image_file, message, 'product_search')
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'final_response': "I had trouble processing your image. Please try again."
            }
    
    async def _process_voice_message(self, voice_file, context: Dict) -> Dict[str, Any]:
        """Process voice message (existing implementation)"""
        try:
            logger.info(f"Processing voice message")
            return await self.multimodal_processor.process_voice_note(voice_file, 'en')
        except Exception as e:
            logger.error(f"Error processing voice: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'final_response': "I had trouble processing your voice message. Please try again."
            }