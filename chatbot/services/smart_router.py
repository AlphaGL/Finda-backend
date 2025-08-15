# chatbot/services/smart_router.py - FIXED VERSION WITH PROPER SERPAPI FALLBACK
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .gemini_client import GeminiAIClient
from .local_search import LocalSearchService
from .serpapi_service import SerpAPIService

logger = logging.getLogger(__name__)

class SmartChatbotRouter:
    """
    Smart router that handles intent detection, local search first, then external search via SerpAPI
    """
    
    def __init__(self):
        self.gemini_client = GeminiAIClient()
        self.local_search = LocalSearchService()
        self.serpapi_service = SerpAPIService()
        
        # Configuration
        self.external_search_enabled = True
        self.max_results_per_source = 5
        self.min_results_threshold = 1  # If local results < this, trigger external search
        
    async def process_message(self, message: str, context: Dict = None) -> Dict[str, Any]:
        """
        Main entry point for processing user messages
        """
        try:
            start_time = datetime.now()
            logger.info(f"Processing message: '{message}'")
            
            if context is None:
                context = {}
                
            # Step 1: Intent Detection
            intent_result = self._detect_intent(message)
            logger.info(f"Detected intent: {intent_result}")
            
            # If not product/service related, return polite message
            if not intent_result['is_product_service']:
                return {
                    'success': True,
                    'final_response': intent_result['response'],
                    'intent': intent_result,
                    'search_results': None,
                    'processing_time': (datetime.now() - start_time).total_seconds()
                }
            
            # Step 2: Generate intro message using Gemini
            intro_message = await self._generate_intro_message(message, intent_result)
            
            # Step 3: Search internal database first
            local_results = await self._search_local_database(message, intent_result, context)
            local_total = local_results.get('total_results', 0)
            
            logger.info(f"Local search found {local_total} results")
            
            # Step 4: FIXED - If no local results OR insufficient results, search externally
            external_results = {}
            should_search_external = (
                self.external_search_enabled and 
                local_total < self.min_results_threshold
            )
            
            if should_search_external:
                logger.info(f"Local results ({local_total}) below threshold ({self.min_results_threshold}), searching externally...")
                external_results = await self._search_external(message, intent_result, context)
                logger.info(f"External search found {external_results.get('total_found', 0)} results")
            else:
                logger.info(f"Sufficient local results ({local_total}), skipping external search")
            
            # Step 5: Format final response in YOUR EXACT FORMAT
            formatted_response = self._format_response_exact_format(
                intro_message, 
                local_results, 
                external_results, 
                intent_result
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'success': True,
                'message_id': f"msg_{int(datetime.now().timestamp())}",
                'session_id': context.get('session_id', 'default_session'),
                'response': formatted_response,
                'message_type': 'text',
                'metadata': {
                    'processing_time': processing_time,
                    'search_strategy': 'local_first_then_external',
                    'confidence_score': intent_result.get('confidence', 0.8),
                    'services_used': ['local_db', 'serpapi'] if should_search_external else ['local_db'],
                    'has_external_results': bool(external_results.get('total_found', 0) > 0)
                },
                'search_results': {
                    'local': {
                        'products': local_results.get('products', []),
                        'services': local_results.get('services', []),
                        'total': local_total
                    },
                    'external': {
                        'products': external_results.get('products', []),
                        'services': external_results.get('services', []),
                        'total': external_results.get('total_found', 0)
                    }
                },
                'suggested_actions': [
                    {
                        'action': 'compare_products',
                        'label': 'Compare these products',
                        'description': 'Get a detailed comparison'
                    },
                    {
                        'action': 'filter_results',
                        'label': 'Filter results',
                        'description': 'Narrow down by criteria'
                    },
                    {
                        'action': 'similar_products',
                        'label': 'Find similar products',
                        'description': 'Search alternatives'
                    },
                    {
                        'action': 'new_search',
                        'label': 'Search for something else',
                        'description': 'Start a new search'
                    },
                    {
                        'action': 'get_recommendations',
                        'label': 'Get recommendations',
                        'description': 'Get personalized recommendations'
                    }
                ],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'response': "I apologize, but I'm having trouble processing your request right now. Please try again in a moment.",
                'processing_time': (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
            }
    
    def _detect_intent(self, message: str) -> Dict[str, Any]:
        """
        IMPROVED: Better intent detection for products vs services
        """
        message_lower = message.lower()
        
        # More comprehensive product keywords
        product_keywords = [
            # General shopping terms
            'buy', 'sell', 'purchase', 'price', 'cost', 'product', 'item', 'shopping',
            # Electronics
            'phone', 'laptop', 'computer', 'tablet', 'tv', 'camera', 'watch', 'headphones', 
            'speaker', 'gadget', 'device', 'electronics', 'smartphone', 'iphone', 'android',
            # Brands
            'samsung', 'apple', 'hp', 'dell', 'sony', 'lg', 'nike', 'adidas', 'canon', 'huawei',
            # Other products
            'clothing', 'shoes', 'furniture', 'car', 'vehicle', 'book', 'jewelry', 'bag', 'accessory',
            # Search terms
            'find', 'looking for', 'need', 'want', 'search for', 'show me', 'i want', 'get me'
        ]
        
        # More comprehensive service keywords  
        service_keywords = [
            # General service terms
            'service', 'hire', 'book', 'appointment', 'professional', 'expert', 'help', 'assist',
            # Specific services
            'repair', 'fix', 'cleaning', 'plumbing', 'electrician', 'mechanic', 'doctor',
            'lawyer', 'teacher', 'tutor', 'consultant', 'designer', 'developer', 'writer',
            'photographer', 'catering', 'delivery', 'transport', 'uber', 'taxi', 'driver',
            'massage', 'barber', 'salon', 'fitness', 'trainer', 'coach', 'therapist'
        ]
        
        # Count exact matches and partial matches
        product_score = 0
        service_score = 0
        
        for keyword in product_keywords:
            if keyword in message_lower:
                product_score += 2 if keyword == message_lower.strip() else 1
        
        for keyword in service_keywords:
            if keyword in message_lower:
                service_score += 2 if keyword == message_lower.strip() else 1
        
        logger.info(f"Intent scoring - Product: {product_score}, Service: {service_score}")
        
        # Determine intent with higher threshold
        if product_score > 0 or service_score > 0:
            intent_type = 'product' if product_score >= service_score else 'service'
            confidence = min(0.9, 0.6 + (max(product_score, service_score) * 0.1))
            
            return {
                'is_product_service': True,
                'type': intent_type,
                'confidence': confidence,
                'product_score': product_score,
                'service_score': service_score
            }
        else:
            return {
                'is_product_service': False,
                'response': "I'm here to help you find products and services! Please ask me about items you'd like to buy or services you need. For example: 'I need a Samsung Galaxy A16' or 'Looking for a cleaning service in Lagos'."
            }
    
    async def _generate_intro_message(self, message: str, intent_result: Dict) -> str:
        """
        Generate human-like intro message using Gemini
        """
        try:
            intent_type = intent_result.get('type', 'product')
            
            prompt = f"""
Generate a friendly, conversational intro message for a marketplace assistant. 
The user is looking for: "{message}"
This appears to be a {intent_type} search.

Generate a brief, enthusiastic intro (1-2 sentences) like:
- "Great! Let me help you find the perfect Samsung Galaxy A16..."
- "Sure! I'll search for cleaning services in your area..."
- "Perfect! Let me look for laptops that match your needs..."

Keep it natural and conversational. Don't mention search process details.
"""
            
            response = await self.gemini_client.generate_response(
                prompt, 
                context={}, 
                prompt_type='marketplace_assistant',
                include_search_results=False
            )
            
            if response.get('success', False):
                return response.get('response', '').strip()
            else:
                return f"Let me help you find what you're looking for!"
                
        except Exception as e:
            logger.error(f"Error generating intro: {str(e)}")
            return f"Let me search for that for you!"
    
    async def _search_local_database(self, message: str, intent_result: Dict, context: Dict) -> Dict[str, Any]:
        """
        Search internal database for products/services
        """
        try:
            logger.info(f"Searching local database for: {message}")
            
            # Determine search type based on intent
            search_type = 'both'  # Default to both
            if intent_result.get('type') == 'product':
                search_type = 'products'
            elif intent_result.get('type') == 'service':
                search_type = 'services'
            
            # Build filters from context
            filters = {}
            if context.get('location'):
                filters['location'] = context['location']
            
            # Perform search
            results = await self.local_search.search(
                query=message,
                search_type=search_type,
                filters=filters,
                location_context=context.get('location_context')
            )
            
            logger.info(f"Local search found {results.get('total_results', 0)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in local search: {str(e)}")
            return {
                'success': False,
                'total_results': 0,
                'products': [],
                'services': [],
                'error': str(e)
            }
    

    # async def _search_external(self, message: str, intent_result: Dict, context: Dict) -> Dict[str, Any]:
    #     """
    #     Search external sources using SerpAPI
    #     """
    #     try:
    #         if not self.external_search_enabled:
    #             logger.info("External search is disabled")
    #             return {'total_found': 0, 'products': [], 'services': []}
                
    #         logger.info(f"Searching external sources for: {message}")
            
    #         # Get user location for search
    #         location = "Nigeria"  # Default
    #         if context.get('location_context', {}).get('country'):
    #             location = context['location_context']['country']
    #         elif context.get('location_context', {}).get('city'):
    #             location = f"{context['location_context']['city']}, Nigeria"
            
    #         # Search based on intent type
    #         if intent_result.get('type') == 'service':
    #             results = await self.serpapi_service.search_local_services(
    #                 query=message,
    #                 location=location,
    #                 limit=self.max_results_per_source
    #             )
    #         else:
    #             # Default to product search
    #             results = await self.serpapi_service.search_products(
    #                 query=message,
    #                 location=location,
    #                 limit=self.max_results_per_source
    #             )
            
    #         logger.info(f"External search found {results.get('total_found', 0)} results")
    #         return results
            
    #     except Exception as e:
    #         logger.error(f"Error in external search: {str(e)}")
    #         return {
    #             'success': False,
    #             'total_found': 0,
    #             'products': [],
    #             'services': [],
    #             'error': str(e)
    #         }


    async def _search_external(self, message: str, intent_result: Dict, context: Dict) -> Dict[str, Any]:
        """
        FIXED: Search external sources using SerpAPI - now returns proper format
        """
        try:
            if not self.external_search_enabled:
                logger.info("External search is disabled")
                return {
                    'success': True,
                    'total_found': 0, 
                    'products': [], 
                    'services': []
                }
                
            logger.info(f"Searching external sources for: {message}")
            
            # Get user location for search
            location = "Nigeria"  # Default
            if context.get('location_context', {}).get('country'):
                location = context['location_context']['country']
            elif context.get('location_context', {}).get('city'):
                location = f"{context['location_context']['city']}, Nigeria"
            
            # FIXED: Always search both products and services, then combine results
            products_result = {'products': [], 'success': False}
            services_result = {'services': [], 'success': False}
            
            try:
                # Search for products
                logger.info(f"Searching products with SerpAPI: '{message}' in {location}")
                products_result = await self.serpapi_service.search_products(
                    query=message,
                    location=location,
                    limit=self.max_results_per_source
                )
                logger.info(f"Products search result: success={products_result.get('success')}, found={len(products_result.get('products', []))}")
            except Exception as e:
                logger.error(f"Error searching external products: {str(e)}")
            
            try:
                # Search for services
                logger.info(f"Searching services with SerpAPI: '{message}' in {location}")
                services_result = await self.serpapi_service.search_local_services(
                    query=message,
                    location=location,
                    limit=self.max_results_per_source
                )
                logger.info(f"Services search result: success={services_result.get('success')}, found={len(services_result.get('services', []))}")
            except Exception as e:
                logger.error(f"Error searching external services: {str(e)}")
            
            # FIXED: Combine results in the expected format
            combined_products = products_result.get('products', []) if products_result.get('success') else []
            combined_services = services_result.get('services', []) if services_result.get('success') else []
            
            total_found = len(combined_products) + len(combined_services)
            
            logger.info(f"External search completed: {len(combined_products)} products, {len(combined_services)} services, total: {total_found}")
            
            # FIXED: Return in the exact format your response builder expects
            return {
                'success': total_found > 0,
                'total_found': total_found,
                'products': combined_products,
                'services': combined_services,
                'source': 'serpapi',
                'products_success': products_result.get('success', False),
                'services_success': services_result.get('success', False),
                'errors': []
            }
            
        except Exception as e:
            logger.error(f"Error in external search: {str(e)}", exc_info=True)
            return {
                'success': False,
                'total_found': 0,
                'products': [],
                'services': [],
                'error': str(e)
            }


    def _format_response_exact_format(self, intro_message: str, local_results: Dict, external_results: Dict, intent_result: Dict) -> str:
        """
        Format response exactly as you specified in your requirements
        """
        response_parts = [intro_message]
        
        # Handle local results first
        local_total = local_results.get('total_results', 0)
        if local_total > 0:
            response_parts.append("\n🏪 **Found in Our Database:**\n")
            
            # Format local products according to your specifications
            products = local_results.get('products', [])
            for i, product in enumerate(products[:self.max_results_per_source], 1):
                try:
                    # Use your EXACT format for products
                    response_parts.append(f"**{i}. Product Details:**")
                    response_parts.append(f"**Product Name:** {product.get('product_name', 'N/A')}")
                    response_parts.append(f"**Product Description:** {product.get('product_description', 'No description available')}")
                    
                    if product.get('featured_image'):
                        response_parts.append(f"**Featured Image:** {product['featured_image']}")
                    else:
                        response_parts.append("**Featured Image:** No image available")
                    
                    response_parts.append(f"**Product Price:** {product.get('product_price', 'Price not available')}")
                    
                    if product.get('original_price'):
                        response_parts.append(f"**Original Price:** {product['original_price']}")
                    
                    response_parts.append(f"**Currency:** {product.get('currency', 'NGN')}")
                    response_parts.append(f"**Is Negotiable:** {'Yes' if product.get('is_negotiable', False) else 'No'}")
                    response_parts.append(f"**Country:** {product.get('country', 'Nigeria')}")
                    response_parts.append(f"**State:** {product.get('state', 'Not specified')}")
                    response_parts.append(f"**City:** {product.get('city', 'Not specified')}")
                    response_parts.append(f"**Address Details:** {product.get('address_details', 'Contact seller for details')}")
                    response_parts.append(f"**Provider Email:** {product.get('provider_email', 'Not available')}")
                    response_parts.append(f"**Provider WhatsApp:** {product.get('provider_whatsapp', 'Not available')}")
                    response_parts.append("")  # Empty line separator
                    
                except Exception as e:
                    logger.error(f"Error formatting product {i}: {e}")
                    response_parts.append(f"**{i}. Product information temporarily unavailable**")
                    response_parts.append("")
            
            # Format local services according to your specifications
            services = local_results.get('services', [])
            for i, service in enumerate(services[:self.max_results_per_source], len(products) + 1):
                try:
                    # Use your EXACT format for services
                    response_parts.append(f"**{i}. Service Details:**")
                    response_parts.append(f"**Service Name:** {service.get('service_name', 'N/A')}")
                    response_parts.append(f"**Service Description:** {service.get('service_description', 'No description available')}")
                    
                    if service.get('featured_image'):
                        response_parts.append(f"**Featured Image:** {service['featured_image']}")
                    else:
                        response_parts.append("**Featured Image:** No image available")
                    
                    response_parts.append(f"**Country:** {service.get('country', 'Nigeria')}")
                    response_parts.append(f"**State:** {service.get('state', 'Not specified')}")
                    response_parts.append(f"**City:** {service.get('city', 'Not specified')}")
                    response_parts.append(f"**Serves Remote:** {'Yes' if service.get('serves_remote', False) else 'No'}")
                    response_parts.append(f"**Provider Name:** {service.get('provider_name', 'Not available')}")
                    response_parts.append(f"**Provider Expertise:** {service.get('provider_expertise', 'Not specified')}")
                    response_parts.append(f"**Provider Experience:** {service.get('provider_experience', 'Not specified')}")
                    response_parts.append(f"**Provider Languages:** {service.get('provider_languages', 'Not specified')}")
                    response_parts.append(f"**Provider Email:** {service.get('provider_email', 'Not available')}")
                    response_parts.append("")  # Empty line separator
                    
                except Exception as e:
                    logger.error(f"Error formatting service {i}: {e}")
                    response_parts.append(f"**{i}. Service information temporarily unavailable**")
                    response_parts.append("")
        
        # Handle external results using SerpAPI format (your JSON structure)
        external_total = external_results.get('total_found', 0)
        if external_total > 0:
            response_parts.append("\n🌍 **External Search Results:**\n")
            
            # Add a message explaining these are external results
            response_parts.append("*The following results are from external sources and may require verification:*\n")
            
            # Format external results more cleanly than raw JSON
            external_products = external_results.get('products', [])
            external_services = external_results.get('services', [])
            
            # Format external products
            start_index = local_results.get('total_results', 0) + 1
            for i, product in enumerate(external_products[:3], start_index):
                response_parts.append(f"**{i}. External Product:**")
                response_parts.append(f"**Product Name:** {product.get('title', product.get('name', 'Unknown'))}")
                response_parts.append(f"**Price:** {product.get('formatted_price', product.get('price', 'Price not available'))}")
                response_parts.append(f"**Source:** {product.get('source', 'External marketplace')}")
                if product.get('rating', {}).get('average'):
                    response_parts.append(f"**Rating:** {product['rating']['average']}/5.0")
                if product.get('link'):
                    response_parts.append(f"**Link:** {product['link']}")
                response_parts.append("")
            
            # Format external services
            for i, service in enumerate(external_services[:3], start_index + len(external_products)):
                response_parts.append(f"**{i}. External Service:**")
                response_parts.append(f"**Service Name:** {service.get('title', service.get('name', 'Unknown'))}")
                response_parts.append(f"**Address:** {service.get('address', service.get('location', 'Location not specified'))}")
                if service.get('phone'):
                    response_parts.append(f"**Phone:** {service['phone']}")
                if service.get('rating', {}).get('average'):
                    response_parts.append(f"**Rating:** {service['rating']['average']}/5.0 ({service.get('rating', {}).get('count', 0)} reviews)")
                if service.get('website') or service.get('link'):
                    response_parts.append(f"**Website:** {service.get('website', service.get('link', ''))}")
                response_parts.append("")
        
        # Add helpful message if no results found anywhere
        if local_total == 0 and external_total == 0:
            response_parts.append("\n❌ **No Results Found**")
            response_parts.append("I couldn't find any matching products or services. Try:")
            response_parts.append("• Using different keywords")
            response_parts.append("• Being more specific (e.g., 'Samsung Galaxy A16' instead of 'phone')")
            response_parts.append("• Checking your spelling")
            response_parts.append("• Searching in a different location")
        
        return "\n".join(response_parts)


# Export the main router
__all__ = ['SmartChatbotRouter']

