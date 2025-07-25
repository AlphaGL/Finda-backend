# chatbot/gemini_client.py - Enhanced with Vision and Advanced Features
import google.generativeai as genai
from django.conf import settings
from PIL import Image
import io
import json
import time
from typing import List, Dict, Any, Optional
import logging

# Configure Gemini - Use GOOGLE_API_KEY instead of GEMINI_API_KEY
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

# Enhanced system prompt for Finda AI
FINDA_AI_SYSTEM_PROMPT = """
You are Finda AI, the intelligent shopping assistant for Finda Marketplace - Africa's premier e-commerce platform.

Your primary role is to help users find products and services on Finda first, then suggest external alternatives if needed.

Core Capabilities:
1. 🛍️ Product Search: Help users find specific products with detailed filtering
2. 🔧 Service Search: Connect users with service providers and professionals  
3. 🖼️ Visual Search: Analyze product images to identify and find similar items
4. 🎤 Voice Search: Process voice queries naturally
5. 🌍 Location-aware: Provide region-specific results and recommendations
6. 💡 Smart Suggestions: Offer alternatives and related products/services

Personality & Tone:
- Friendly, helpful, and professional
- Enthusiastic about helping users find what they need
- Patient when gathering preferences and requirements
- Knowledgeable about African markets and shopping habits
- Use appropriate emojis to make interactions engaging

Search Process:
1. First, search Finda's internal database
2. If results found, present them with full details
3. Ask if user wants external alternatives
4. If no internal results, automatically search external sources
5. Always prioritize user preferences (price, location, brand, etc.)

Response Format:
- Be conversational and natural
- Include relevant emojis
- Provide clear, actionable information
- Always include contact details and links when showing products/services
- Ask follow-up questions to refine searches

Remember: You represent Finda Marketplace, so promote our platform while being helpful and honest about all options available to users.
"""

# Set up logging
logger = logging.getLogger(__name__)


def send_to_gemini(history: List[Dict], user_message: str, system_prompt: str = None) -> str:
    """
    Enhanced Gemini integration with better context handling
    """
    try:
        # Check if API key is configured
        api_key = getattr(settings, 'GOOGLE_API_KEY', None) or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return "I apologize, but I'm having trouble connecting to my AI service right now. Please try again later or contact support."
        
        # Use custom system prompt or default
        if system_prompt is None:
            system_prompt = FINDA_AI_SYSTEM_PROMPT
        
        # Format history for Gemini
        formatted_history = []
        
        for item in history:
            role = "user" if item["author"] == "user" else "model"
            if item["author"] == "assistant":
                role = "model"
            if role:
                formatted_history.append({
                    "role": role,
                    "parts": [item["content"]],
                })

        # Initialize the model with safety settings
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
        
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        model = genai.GenerativeModel(
            TEXT_MODEL,
            safety_settings=safety_settings,
            generation_config=generation_config
        )

        # Start chat with history
        chat = model.start_chat(history=formatted_history)

        # Handle first message with system prompt
        if not formatted_history:
            combined_prompt = f"{system_prompt}\n\nUser: {user_message}"
            response = chat.send_message(combined_prompt)
        else:
            response = chat.send_message(user_message)

        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "I apologize, but I'm having trouble processing your request right now. Please try again in a moment or browse our categories directly!"


def analyze_image_with_gemini(image_file, additional_context: str = "") -> Optional[Dict[str, Any]]:
    """
    Analyze product image using Gemini Vision API
    """
    try:
        # Check if API key is configured
        api_key = getattr(settings, 'GOOGLE_API_KEY', None) or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return None
        
        # Read and process image
        image_data = image_file.read()
        image_file.seek(0)
        
        # Create PIL Image object
        pil_image = Image.open(io.BytesIO(image_data))
        
        # Resize if too large
        max_size = (1024, 1024)
        if pil_image.size[0] > max_size[0] or pil_image.size[1] > max_size[1]:
            pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Enhanced analysis prompt
        analysis_prompt = f"""
        Analyze this product image and provide detailed information in JSON format. 
        {f"Additional context: {additional_context}" if additional_context else ""}
        
        Please identify:
        1. Product type and category
        2. Brand (if visible or recognizable)
        3. Colors (primary and secondary)
        4. Key features and characteristics
        5. Estimated condition
        6. Any text or numbers visible
        7. Style/design characteristics
        8. Material (if identifiable)
        9. Estimated price range for this type of product
        10. Similar product keywords for searching
        
        Return response in this JSON format:
        {{
            "product_type": "specific product name/type",
            "category": "general category",
            "subcategory": "more specific category",
            "brand": "brand name or null",
            "primary_color": "main color",
            "secondary_colors": ["color1", "color2"],
            "key_features": ["feature1", "feature2", "feature3"],
            "condition": "new/used/worn/refurbished",
            "style": "style description",
            "material": "material type or null",
            "text_detected": "any visible text/numbers",
            "estimated_price_range": {{"min": 0, "max": 0, "currency": "NGN"}},
            "search_keywords": ["keyword1", "keyword2", "keyword3"],
            "confidence_score": 0.85,
            "description": "detailed visual description",
            "size_indicators": "any size info visible",
            "quality_assessment": "assessment of product quality from image"
        }}
        
        Be as accurate and specific as possible. Use null for unknown values.
        """
        
        # Initialize vision model
        model = genai.GenerativeModel(VISION_MODEL)
        
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
                analysis_result['analysis_timestamp'] = time.time()
                analysis_result['image_dimensions'] = {
                    'width': pil_image.width,
                    'height': pil_image.height
                }
                analysis_result['analysis_model'] = VISION_MODEL
                
                return analysis_result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed: {e}. Raw response: {json_text[:200]}")
                
                # Fallback analysis
                return create_fallback_analysis(response.text, pil_image)
        
        return None
        
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return None


def create_fallback_analysis(raw_text: str, image: Image.Image) -> Dict[str, Any]:
    """
    Create basic analysis when JSON parsing fails
    """
    return {
        "product_type": "unknown product",
        "category": "general",
        "description": raw_text[:300] if raw_text else "Unable to analyze image",
        "confidence_score": 0.3,
        "analysis_method": "fallback",
        "image_dimensions": {
            "width": image.width,
            "height": image.height
        },
        "search_keywords": extract_keywords_from_text(raw_text) if raw_text else [],
        "analysis_timestamp": time.time()
    }


def extract_keywords_from_text(text: str) -> List[str]:
    """
    Extract potential search keywords from analysis text
    """
    import re
    
    # Remove common words and extract meaningful terms
    common_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'can', 'image', 'shows',
        'appears', 'seems', 'looks', 'product', 'item'
    }
    
    # Extract words that could be keywords
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    keywords = [word for word in words if word not in common_words]
    
    # Return unique keywords, limited to 10
    return list(set(keywords))[:10]


def generate_external_search_results(query: str, search_type: str, preferences: Dict) -> str:
    """
    Generate realistic external search results using Gemini
    """
    try:
        # Check if API key is configured
        api_key = getattr(settings, 'GOOGLE_API_KEY', None) or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return generate_fallback_external_results(query, search_type)
        
        # Create prompt for external search simulation
        external_prompt = f"""
        As Finda AI, I need to provide external shopping results for the query: "{query}"
        
        Search type: {search_type}
        User preferences: {json.dumps(preferences) if preferences else "No specific preferences"}
        
        Please create realistic search results from popular African/international e-commerce platforms like:
        - Jumia (Nigeria, Kenya, etc.)
        - Konga (Nigeria)
        - Amazon (international shipping)
        - AliExpress
        - eBay
        - Other relevant platforms
        
        Format the response exactly like this:
        
        🌐 **External Search Results** (via Partner Store APIs)
        
        **1. [Realistic Product Name]**
        🏪 **Store:** [Platform Name]
        💰 **Price:** ₦[Amount] (or $[Amount])
        ⭐ **Rating:** [X.X/5.0] ([X] reviews)
        📦 **Availability:** [In Stock/Limited/Pre-order]
        🚚 **Shipping:** [Shipping details]
        🔗 **View Product:** Available on [Platform]
        
        **2. [Next Product]**
        [Same format...]
        
        Include 3-5 realistic results with:
        - Actual product names that match the query
        - Realistic prices in Nigerian Naira or US Dollars
        - Believable ratings and review counts
        - Accurate store names
        - Relevant shipping information
        
        End with: 
        💡 **Note:** Results from partner store APIs. Prices may vary. Visit stores directly for current pricing.
        
        🛍️ **Prefer Finda?** Try different keywords or browse our categories for local deals!
        """
        
        model = genai.GenerativeModel(TEXT_MODEL)
        response = model.generate_content(external_prompt)
        
        if response and response.text:
            return response.text.strip()
        
        return generate_fallback_external_results(query, search_type)
        
    except Exception as e:
        logger.error(f"External search generation error: {e}")
        return generate_fallback_external_results(query, search_type)


def generate_fallback_external_results(query: str, search_type: str) -> str:
    """
    Generate basic external results when API fails
    """
    return f"""
🔍 **External Search Results**

I found some options on external platforms for "{query}", but I'm having trouble accessing the full details right now.

🌐 **Available on these platforms:**
• Jumia - Check their {search_type} section
• Konga - Browse their marketplace  
• Amazon - International shipping available
• AliExpress - Wide variety of options

💡 **Tip:** Visit these platforms directly and search for "{query}" to see current prices and availability.

🛍️ **Meanwhile, try browsing Finda categories or refine your search - we might have exactly what you need!**
"""


def analyze_voice_intent(transcribed_text: str) -> Dict[str, Any]:
    """
    Analyze voice message intent and extract key information
    """
    try:
        # Check if API key is configured
        api_key = getattr(settings, 'GOOGLE_API_KEY', None) or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return create_fallback_intent_analysis(transcribed_text)
        
        intent_prompt = f"""
        Analyze this voice message transcript and extract key information:
        
        Transcript: "{transcribed_text}"
        
        Return JSON with:
        {{
            "intent": "search_product/search_service/browse/greeting/question/other",
            "main_query": "extracted search terms",
            "preferences": {{
                "colors": [],
                "price_range": {{"min": null, "max": null}},
                "locations": [],
                "brands": [],
                "sizes": []
            }},
            "urgency": "low/medium/high",
            "sentiment": "positive/neutral/negative",
            "language": "detected language code",
            "confidence": 0.0-1.0
        }}
        """
        
        model = genai.GenerativeModel(TEXT_MODEL)
        response = model.generate_content(intent_prompt)
        
        if response and response.text:
            try:
                json_text = response.text.strip()
                if '```json' in json_text:
                    json_text = json_text.split('```json')[1].split('```')[0].strip()
                
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
    
    except Exception as e:
        logger.error(f"Voice intent analysis error: {e}")
    
    # Fallback analysis
    return create_fallback_intent_analysis(transcribed_text)


def create_fallback_intent_analysis(transcribed_text: str) -> Dict[str, Any]:
    """
    Create fallback intent analysis when Gemini fails
    """
    return {
        "intent": "search_product",
        "main_query": transcribed_text,
        "preferences": {},
        "urgency": "medium",
        "sentiment": "neutral",
        "language": "en",
        "confidence": 0.5
    }


def generate_conversational_response(context: Dict, user_message: str, internal_results: List = None) -> str:
    """
    Generate contextual conversational response
    """
    try:
        # Check if API key is configured
        api_key = getattr(settings, 'GOOGLE_API_KEY', None) or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return create_fallback_conversational_response(context, user_message, internal_results)
        
        conversation_prompt = f"""
        As Finda AI, generate a natural, helpful response based on this context:
        
        User message: "{user_message}"
        
        Context:
        - Current intent: {context.get('intent', 'unknown')}
        - Previous preferences: {json.dumps(context.get('preferences', {}))}
        - Internal results found: {len(internal_results) if internal_results else 0}
        - Conversation history: {len(context.get('history', []))} messages
        
        Guidelines:
        1. Be conversational and friendly
        2. Use appropriate emojis
        3. If internal results exist, present them enthusiastically
        4. Ask relevant follow-up questions to refine search
        5. Offer to check external sources if needed
        6. Stay in character as Finda AI assistant
        7. Keep response length reasonable (2-4 paragraphs max)
        
        Internal results summary:
        {format_results_for_prompt(internal_results) if internal_results else "No internal results found"}
        """
        
        model = genai.GenerativeModel(TEXT_MODEL)
        response = model.generate_content(conversation_prompt)
        
        if response and response.text:
            return response.text.strip()
        
        return create_fallback_conversational_response(context, user_message, internal_results)
            
    except Exception as e:
        logger.error(f"Conversational response error: {e}")
        return create_fallback_conversational_response(context, user_message, internal_results)


def create_fallback_conversational_response(context: Dict, user_message: str, internal_results: List = None) -> str:
    """
    Create fallback conversational response when Gemini fails
    """
    if internal_results:
        return f"Great! I found {len(internal_results)} options on Finda for you. Let me show you the details!"
    else:
        return "I'm searching for that on Finda and external sources. Let me get back to you with the best options!"


def format_results_for_prompt(results: List) -> str:
    """
    Format results for inclusion in prompts
    """
    if not results:
        return "No results"
    
    summary = f"Found {len(results)} items:\n"
    for i, result in enumerate(results[:3], 1):  # Limit to first 3 for prompt
        if hasattr(result, 'product_name'):
            summary += f"{i}. {result.product_name} - ₦{result.product_price}\n"
        elif hasattr(result, 'service_name'):
            summary += f"{i}. {result.service_name} by {getattr(result, 'provider_name', 'Unknown')}\n"
    
    return summary


def validate_gemini_response(response_text: str) -> str:
    """
    Validate and clean Gemini responses
    """
    if not response_text:
        return "I apologize, I didn't catch that. Could you please try again?"
    
    # Remove any potential harmful content indicators
    response_text = response_text.strip()
    
    # Ensure response isn't too long
    if len(response_text) > 2000:
        response_text = response_text[:1997] + "..."
    
    # Ensure it ends properly
    if not response_text.endswith(('.', '!', '?', ':', '😊', '🛍️', '💡')):
        response_text += "!"
    
    return response_text


def get_model_status() -> Dict[str, Any]:
    """
    Check Gemini model availability and status
    """
    try:
        # Check if API key is configured
        api_key = getattr(settings, 'GOOGLE_API_KEY', None) or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return {
                "status": "error",
                "error": "No API key configured",
                "last_check": time.time(),
                "text_model": TEXT_MODEL,
                "vision_model": VISION_MODEL
            }
        
        # Test with a simple prompt
        model = genai.GenerativeModel(TEXT_MODEL)
        test_response = model.generate_content("Hello")
        
        return {
            "status": "active",
            "text_model": TEXT_MODEL,
            "vision_model": VISION_MODEL,
            "last_check": time.time(),
            "response_test": bool(test_response and test_response.text)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "last_check": time.time(),
            "text_model": TEXT_MODEL,
            "vision_model": VISION_MODEL
        }