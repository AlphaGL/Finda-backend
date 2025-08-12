# ai_chatbot/services/gemini_client.py
import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from django.conf import settings
from django.core.cache import cache
import requests
from PIL import Image
import io
import base64

logger = logging.getLogger(__name__)


class GeminiAIClient:
    """
    Advanced Gemini AI client for marketplace chatbot
    Handles text generation, image analysis, and web search integration
    """
    
    def __init__(self):
        # Initialize Gemini
        self.api_key = getattr(settings, 'GOOGLE_API_KEY', os.getenv('GOOGLE_API_KEY'))
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is required")
        
        genai.configure(api_key=self.api_key)
        
        # Model configuration
        self.model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash')
        self.model = genai.GenerativeModel(self.model_name)
        
        # Safety settings - adjusted for marketplace use
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }
        
        # Generation configuration
        self.generation_config = {
            'temperature': 0.7,
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 2048,
        }
        
        # Marketplace-specific prompts
        self.system_prompts = {
            'marketplace_assistant': self._load_marketplace_prompt(),
            'product_recommender': self._load_product_recommender_prompt(),
            'service_matcher': self._load_service_matcher_prompt(),
            'price_analyst': self._load_price_analyst_prompt(),
            'image_analyzer': self._load_image_analyzer_prompt()
        }
        
        # Cache settings
        self.cache_timeout = 1800  # 30 minutes
        
        # Rate limiting
        self.last_request_time = None
        self.min_request_interval = 1.0  # 1 second between requests
    
    def _load_marketplace_prompt(self) -> str:
        """Load the main marketplace assistant prompt"""
        return """
        You are an AI shopping assistant for a comprehensive marketplace platform similar to Amazon, Jumia, or eBay. 
        Your role is to help users find products and services, compare prices, get recommendations, and make informed purchasing decisions.

        CAPABILITIES:
        - Search for products and services
        - Provide detailed product/service information
        - Compare prices and features
        - Recommend alternatives
        - Help with location-based searches
        - Assist with category browsing
        - Answer questions about sellers/service providers
        - Provide purchase guidance

        PERSONALITY:
        - Friendly, helpful, and professional
        - Knowledgeable about marketplace trends
        - Patient with user questions
        - Proactive in offering assistance
        - Honest about limitations

        GUIDELINES:
        1. Always prioritize user needs and preferences
        2. Provide accurate, up-to-date information
        3. Be transparent about product availability and pricing
        4. Respect user privacy and data
        5. Encourage safe and secure transactions
        6. Support local businesses when appropriate
        7. Provide multiple options when possible

        When you cannot find specific information in the local database, clearly state this and offer to search external sources or suggest alternatives.
        """
    
    def _load_product_recommender_prompt(self) -> str:
        """Load product recommendation prompt"""
        return """
        You are a product recommendation specialist. Analyze user preferences, budget, location, and requirements to suggest the best products.
        
        Consider:
        - Price range and value for money
        - User location and shipping
        - Product ratings and reviews
        - Brand reputation and reliability
        - Feature matching to user needs
        - Availability and stock status
        
        Provide 3-5 recommendations with clear reasons for each suggestion.
        """
    
    def _load_service_matcher_prompt(self) -> str:
        """Load service matching prompt"""
        return """
        You are a service matching expert. Help users find the right service providers based on their needs.
        
        Consider:
        - Service provider experience and ratings
        - Location and service area
        - Pricing and value
        - Availability and response time
        - Specializations and certifications
        - Previous customer feedback
        
        Match users with the most suitable service providers.
        """
    
    def _load_price_analyst_prompt(self) -> str:
        """Load price analysis prompt"""
        return """
        You are a price analysis expert. Help users understand pricing, find deals, and make cost-effective decisions.
        
        Analyze:
        - Market price comparisons
        - Value for money assessment
        - Seasonal pricing trends
        - Negotiation opportunities
        - Hidden costs or fees
        - Best time to buy
        
        Provide actionable pricing insights and recommendations.
        """
    
    def _load_image_analyzer_prompt(self) -> str:
        """Load image analysis prompt"""
        return """
        You are an image analysis expert for marketplace products. Analyze uploaded images to:
        
        1. Identify products and their features
        2. Assess product condition and quality
        3. Extract text or brand information
        4. Suggest search terms
        5. Recommend similar products
        6. Flag potential issues or concerns
        
        Provide detailed, accurate descriptions and actionable suggestions.
        """
    
    async def generate_response(
        self, 
        user_message: str, 
        context: Dict[str, Any] = None,
        prompt_type: str = 'marketplace_assistant',
        include_search_results: bool = True
    ) -> Dict[str, Any]:
        """
        Generate AI response for user message
        
        Args:
            user_message: User's input message
            context: Conversation and search context
            prompt_type: Type of prompt to use
            include_search_results: Whether to include search results in context
            
        Returns:
            Dict containing AI response and metadata
        """
        try:
            # Rate limiting
            await self._rate_limit()
            
            # Build the full prompt
            full_prompt = self._build_prompt(
                user_message, 
                context, 
                prompt_type, 
                include_search_results
            )
            
            # Check cache
            cache_key = self._generate_cache_key(full_prompt)
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info("Returning cached Gemini response")
                return cached_response
            
            # Generate response
            start_time = datetime.now()
            
            response = await self._generate_with_retry(full_prompt)
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            # Process response
            result = {
                'response': response.text if hasattr(response, 'text') else str(response),
                'model': self.model_name,
                'response_time': response_time,
                'timestamp': datetime.now().isoformat(),
                'prompt_type': prompt_type,
                'context_included': bool(context),
                'success': True
            }
            
            # Extract structured information if possible
            structured_info = self._extract_structured_info(result['response'])
            if structured_info:
                result['structured_info'] = structured_info
            
            # Cache the response
            cache.set(cache_key, result, self.cache_timeout)
            
            logger.info(f"Generated Gemini response in {response_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error generating Gemini response: {str(e)}")
            return {
                'response': "I apologize, but I'm having trouble processing your request right now. Please try again in a moment.",
                'error': str(e),
                'success': False,
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    async def analyze_image(self, image_data: Union[str, bytes], user_message: str = "") -> Dict[str, Any]:
        """
        Analyze uploaded image using Gemini Vision
        
        Args:
            image_data: Base64 encoded image or raw bytes
            user_message: Optional user message about the image
            
        Returns:
            Dict containing image analysis results
        """
        try:
            # Rate limiting
            await self._rate_limit()
            
            # Process image
            image = self._process_image(image_data)
            if not image:
                return {'error': 'Invalid image format', 'success': False}
            
            # Build prompt for image analysis
            prompt = self._build_image_analysis_prompt(user_message)
            
            # Generate response with image
            start_time = datetime.now()
            
            response = await self._generate_with_image(prompt, image)
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            # Process response
            result = {
                'analysis': response.text if hasattr(response, 'text') else str(response),
                'model': self.model_name,
                'response_time': response_time,
                'timestamp': datetime.now().isoformat(),
                'image_processed': True,
                'success': True
            }
            
            # Extract product information if detected
            product_info = self._extract_product_info_from_image_analysis(result['analysis'])
            if product_info:
                result['detected_products'] = product_info
            
            logger.info(f"Analyzed image in {response_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            return {
                'analysis': "I couldn't analyze this image. Please try uploading a clearer image.",
                'error': str(e),
                'success': False,
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    async def search_web_for_products(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """
        Use Gemini to search web for external products with purchase links
        
        Args:
            query: Search query
            context: Additional context for the search
            
        Returns:
            Dict containing web search results and product information
        """
        try:
            # Rate limiting
            await self._rate_limit()
            
            # Build web search prompt
            web_search_prompt = self._build_web_search_prompt(query, context)
            
            start_time = datetime.now()
            
            # First, ask Gemini to suggest search strategies and keywords
            strategy_response = await self._generate_with_retry(web_search_prompt)
            
            # Extract search keywords from Gemini's response
            search_keywords = self._extract_search_keywords(strategy_response.text)
            
            # Perform actual web searches (this will be handled by web_search.py)
            # For now, we'll structure the response for the web search service
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            result = {
                'search_strategy': strategy_response.text,
                'recommended_keywords': search_keywords,
                'original_query': query,
                'response_time': response_time,
                'timestamp': datetime.now().isoformat(),
                'requires_web_search': True,
                'success': True
            }
            
            logger.info(f"Generated web search strategy in {response_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in web search strategy: {str(e)}")
            return {
                'search_strategy': "I'll search for similar products online.",
                'recommended_keywords': [query],
                'error': str(e),
                'success': False,
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    async def generate_product_comparison(self, products: List[Dict]) -> Dict[str, Any]:
        """
        Generate product comparison using Gemini
        
        Args:
            products: List of product dictionaries to compare
            
        Returns:
            Dict containing comparison analysis
        """
        try:
            if len(products) < 2:
                return {
                    'comparison': "I need at least 2 products to make a comparison.",
                    'success': False
                }
            
            # Rate limiting
            await self._rate_limit()
            
            # Build comparison prompt
            comparison_prompt = self._build_comparison_prompt(products)
            
            start_time = datetime.now()
            response = await self._generate_with_retry(comparison_prompt)
            end_time = datetime.now()
            
            result = {
                'comparison': response.text,
                'products_compared': len(products),
                'response_time': (end_time - start_time).total_seconds(),
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating product comparison: {str(e)}")
            return {
                'comparison': "I couldn't generate a comparison at the moment. Please try again.",
                'error': str(e),
                'success': False
            }
    
    async def _generate_with_retry(self, prompt: str, max_retries: int = 3) -> Any:
        """Generate response with retry logic"""
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    prompt,
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings
                )
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def _generate_with_image(self, prompt: str, image: Any) -> Any:
        """Generate response with image input"""
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, image],
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            return response
        except Exception as e:
            logger.error(f"Error generating response with image: {str(e)}")
            raise e
    
    def _build_prompt(
        self, 
        user_message: str, 
        context: Dict[str, Any], 
        prompt_type: str,
        include_search_results: bool
    ) -> str:
        """Build the complete prompt for Gemini"""
        
        # Start with system prompt
        system_prompt = self.system_prompts.get(prompt_type, self.system_prompts['marketplace_assistant'])
        
        # Add current context
        context_info = ""
        if context:
            context_info += f"\nCONTEXT INFORMATION:\n"
            
            # Add user preferences
            if context.get('user_preferences'):
                context_info += f"User Preferences: {json.dumps(context['user_preferences'], indent=2)}\n"
            
            # Add location context
            if context.get('location_context'):
                context_info += f"Location Context: {json.dumps(context['location_context'], indent=2)}\n"
            
            # Add conversation history (last 5 messages)
            if context.get('conversation_history'):
                history = context['conversation_history'][-5:]
                context_info += "\nRECENT CONVERSATION:\n"
                for msg in history:
                    sender = "User" if msg.get('sender_type') == 'user' else "Assistant"
                    context_info += f"{sender}: {msg.get('content', '')}\n"
            
            # Add search results if available and requested
            if include_search_results and context.get('search_results'):
                search_results = context['search_results']
                context_info += f"\nSEARCH RESULTS FOUND:\n"
                
                # Add products
                if search_results.get('products'):
                    context_info += f"PRODUCTS ({len(search_results['products'])} found):\n"
                    for i, product in enumerate(search_results['products'][:5], 1):
                        context_info += f"{i}. {product.get('name', 'Unknown')} - {product.get('formatted_price', 'Price not available')}\n"
                        context_info += f"   Location: {product.get('location', {}).get('full_location', 'Unknown')}\n"
                        context_info += f"   Description: {product.get('description', '')[:100]}...\n\n"
                
                # Add services
                if search_results.get('services'):
                    context_info += f"SERVICES ({len(search_results['services'])} found):\n"
                    for i, service in enumerate(search_results['services'][:5], 1):
                        context_info += f"{i}. {service.get('name', 'Unknown')} - {service.get('price_range', 'Price on request')}\n"
                        context_info += f"   Provider: {service.get('provider', {}).get('name', 'Unknown')}\n"
                        context_info += f"   Location: {service.get('location', {}).get('full_location', 'Unknown')}\n\n"
                
                context_info += f"Total Results: {search_results.get('total_results', 0)}\n"
        
        # Build the complete prompt
        complete_prompt = f"""
{system_prompt}

{context_info}

USER MESSAGE: {user_message}

Please provide a helpful, accurate, and personalized response based on the context and search results provided. If you're recommending products or services, explain why they match the user's needs and provide relevant details like pricing, location, and features.
"""
        
        return complete_prompt
    
    def _build_image_analysis_prompt(self, user_message: str = "") -> str:
        """Build prompt for image analysis"""
        base_prompt = self.system_prompts['image_analyzer']
        
        if user_message:
            return f"{base_prompt}\n\nUser's question about this image: {user_message}\n\nPlease analyze the image and answer the user's question."
        else:
            return f"{base_prompt}\n\nPlease analyze this image and provide detailed information about any products you can identify."
    
    def _build_web_search_prompt(self, query: str, context: Dict = None) -> str:
        """Build prompt for web search strategy"""
        prompt = f"""
You are an expert at finding products online. The user is looking for: "{query}"

Based on this search query, please:

1. Suggest 3-5 specific search keywords or phrases that would be most effective for finding this product online
2. Identify the best types of websites to search (e.g., e-commerce sites, manufacturer sites, comparison sites)
3. Suggest any specific brands, models, or variations to look for
4. Mention any important specifications or features to consider

Context information:
"""
        
        if context:
            if context.get('location_context'):
                prompt += f"- User location: {context['location_context']}\n"
            if context.get('user_preferences'):
                prompt += f"- User preferences: {context['user_preferences']}\n"
        
        prompt += """
Please provide your response in this format:

RECOMMENDED SEARCH KEYWORDS:
- [keyword 1]
- [keyword 2]
- [keyword 3]

WEBSITE TYPES TO FOCUS ON:
- [website type 1]
- [website type 2]

SPECIFIC BRANDS/MODELS TO CONSIDER:
- [brand/model 1]
- [brand/model 2]

KEY SPECIFICATIONS TO LOOK FOR:
- [spec 1]
- [spec 2]
"""
        
        return prompt
    
    def _build_comparison_prompt(self, products: List[Dict]) -> str:
        """Build prompt for product comparison"""
        prompt = f"""
Please compare the following {len(products)} products and provide a detailed analysis:

"""
        
        for i, product in enumerate(products, 1):
            prompt += f"""
PRODUCT {i}:
Name: {product.get('name', 'Unknown')}
Price: {product.get('formatted_price', 'Price not available')}
Description: {product.get('description', 'No description')}
Location: {product.get('location', {}).get('full_location', 'Unknown')}
Rating: {product.get('rating', {}).get('average', 'Not rated')}/5 ({product.get('rating', {}).get('count', 0)} reviews)
Seller: {product.get('seller', {}).get('name', 'Unknown')}
Condition: {product.get('condition', 'Unknown')}

"""
        
        prompt += """
Please provide:

1. **PRICE COMPARISON**: Which offers the best value for money?

2. **FEATURE COMPARISON**: Compare key features and specifications

3. **LOCATION & DELIVERY**: Compare locations and potential shipping

4. **SELLER REPUTATION**: Compare seller ratings and trustworthiness

5. **OVERALL RECOMMENDATION**: Which product would you recommend and why?

6. **PROS & CONS**: List pros and cons for each product

Please be specific and help the user make an informed decision.
"""
        
        return prompt
    
    def _extract_search_keywords(self, response_text: str) -> List[str]:
        """Extract search keywords from Gemini's response"""
        keywords = []
        
        # Look for the keywords section
        lines = response_text.split('\n')
        in_keywords_section = False
        
        for line in lines:
            line = line.strip()
            if 'RECOMMENDED SEARCH KEYWORDS' in line.upper() or 'SEARCH KEYWORDS' in line.upper():
                in_keywords_section = True
                continue
            
            if in_keywords_section:
                if line.startswith('-') or line.startswith('•'):
                    keyword = line.lstrip('-• ').strip()
                    if keyword:
                        keywords.append(keyword)
                elif line.startswith(('WEBSITE', 'BRANDS', 'SPECIFICATIONS')) or not line:
                    if line.startswith(('WEBSITE', 'BRANDS', 'SPECIFICATIONS')):
                        break
        
        # Fallback: if no structured keywords found, extract from the response
        if not keywords:
            # Simple fallback extraction
            import re
            potential_keywords = re.findall(r'"([^"]+)"', response_text)
            keywords = potential_keywords[:5] if potential_keywords else [response_text.split()[0]]
        
        return keywords[:5]  # Limit to 5 keywords
    
    def _extract_structured_info(self, response_text: str) -> Optional[Dict]:
        """Extract structured information from response"""
        try:
            # Look for structured data in the response
            structured_info = {}
            
            # Extract price mentions
            import re
            price_pattern = r'[\$₦]\s*[\d,]+(?:\.\d{2})?'
            prices = re.findall(price_pattern, response_text)
            if prices:
                structured_info['mentioned_prices'] = prices
            
            # Extract product/service names (words in quotes or caps)
            products_mentioned = re.findall(r'"([^"]+)"', response_text)
            if products_mentioned:
                structured_info['products_mentioned'] = products_mentioned[:5]
            
            # Extract locations mentioned
            location_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:State|City|Country))\b'
            locations = re.findall(location_pattern, response_text)
            if locations:
                structured_info['locations_mentioned'] = locations[:3]
            
            return structured_info if structured_info else None
            
        except Exception as e:
            logger.error(f"Error extracting structured info: {str(e)}")
            return None
    
    def _extract_product_info_from_image_analysis(self, analysis_text: str) -> Optional[List[Dict]]:
        """Extract product information from image analysis"""
        try:
            # This is a simplified version - you can make it more sophisticated
            products = []
            
            # Look for product names, brands, or models mentioned
            import re
            
            # Common product indicators
            product_indicators = ['product', 'item', 'brand', 'model', 'device', 'gadget', 'tool']
            
            lines = analysis_text.split('\n')
            for line in lines:
                line = line.strip().lower()
                if any(indicator in line for indicator in product_indicators):
                    # Extract potential product name
                    words = line.split()
                    for i, word in enumerate(words):
                        if word in product_indicators and i + 1 < len(words):
                            product_name = ' '.join(words[i+1:i+4])  # Get next 3 words
                            if product_name:
                                products.append({
                                    'name': product_name.title(),
                                    'confidence': 0.7,
                                    'source': 'image_analysis'
                                })
                            break
            
            return products[:3] if products else None
            
        except Exception as e:
            logger.error(f"Error extracting product info from image analysis: {str(e)}")
            return None
    
    def _process_image(self, image_data: Union[str, bytes]) -> Optional[Image.Image]:
        """Process image data for Gemini Vision"""
        try:
            if isinstance(image_data, str):
                # Assume base64 encoded
                if image_data.startswith('data:image'):
                    # Remove data URL prefix
                    image_data = image_data.split(',')[1]
                
                # Decode base64
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            # Open with PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            # Resize if too large (Gemini has size limits)
            max_size = (1024, 1024)
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return None
    
    async def _rate_limit(self):
        """Simple rate limiting"""
        if self.last_request_time:
            time_since_last = (datetime.now() - self.last_request_time).total_seconds()
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = datetime.now()
    
    def _generate_cache_key(self, prompt: str) -> str:
        """Generate cache key for the prompt"""
        import hashlib
        return f"gemini_response_{hashlib.md5(prompt.encode()).hexdigest()}"
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            'model_name': self.model_name,
            'api_key_configured': bool(self.api_key),
            'safety_settings': str(self.safety_settings),
            'generation_config': self.generation_config,
            'available_prompts': list(self.system_prompts.keys())
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the Gemini API connection"""
        try:
            test_prompt = "Say 'Hello! I'm working correctly.' in exactly those words."
            response = await self._generate_with_retry(test_prompt)
            
            success = "Hello! I'm working correctly." in response.text
            
            return {
                'success': success,
                'response': response.text,
                'model': self.model_name,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'model': self.model_name,
                'timestamp': datetime.now().isoformat()
            }


# Helper functions for the service
def sanitize_prompt(prompt: str) -> str:
    """Sanitize prompt to prevent injection attacks"""
    # Remove potentially harmful characters
    import re
    # Allow alphanumeric, spaces, common punctuation
    sanitized = re.sub(r'[^\w\s\.\,\!\?\-\"\'\(\)\[\]\{\}]', '', prompt)
    return sanitized[:10000]  # Limit length


def extract_intent_from_response(response_text: str) -> Dict[str, Any]:
    """Extract intent and entities from AI response"""
    intent_data = {
        'intent': 'general_query',
        'entities': [],
        'confidence': 0.5
    }
    
    # Simple intent detection based on keywords
    response_lower = response_text.lower()
    
    if any(word in response_lower for word in ['buy', 'purchase', 'price', 'cost', 'how much']):
        intent_data['intent'] = 'purchase_inquiry'
        intent_data['confidence'] = 0.8
    elif any(word in response_lower for word in ['compare', 'vs', 'versus', 'difference']):
        intent_data['intent'] = 'product_comparison'
        intent_data['confidence'] = 0.8
    elif any(word in response_lower for word in ['recommend', 'suggest', 'best', 'which']):
        intent_data['intent'] = 'recommendation_request'
        intent_data['confidence'] = 0.8
    elif any(word in response_lower for word in ['where', 'location', 'near', 'find']):
        intent_data['intent'] = 'location_query'
        intent_data['confidence'] = 0.8
    
    return intent_data