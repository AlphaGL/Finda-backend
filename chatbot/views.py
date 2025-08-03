# views.py - FULLY ENHANCED & BUG-FIXED VERSION
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
import json
import logging

from .gemini_client import (
    send_to_gemini, analyze_image_with_gemini, 
    transcribe_audio, generate_voice_response
)
from .models import ChatMessage, UserVoiceSettings
from .serializers import ChatMessageSerializer, VoiceSettingsSerializer
from .utils import (
    search_finda_database, format_finda_results, generate_no_results_response,
    search_by_category, get_trending_items, format_categories_response,
    search_products_by_analysis, clean_search_query
)
from .enhanced_conversation_manager import (
    ConversationFlowManager, ContextualResponseGenerator
)
from .chatbot_prompts import (
    get_system_prompt, get_greeting, format_response_template,
    get_error_message, detect_user_intent, RESPONSE_TEMPLATES
)
from main.models import Products, Services, Category

User = get_user_model()
logger = logging.getLogger(__name__)

# ENHANCED SYSTEM PROMPT
SYSTEM_PROMPT = get_system_prompt('main')

class CustomAuthToken(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        try:
            email = request.data.get('email')
            password = request.data.get('password')

            if not email or not password:
                return Response({"error": "Email and password are required"}, status=400)

            user = authenticate(request, email=email, password=password)
            if not user:
                return Response({"error": "Invalid credentials"}, status=401)

            token, created = Token.objects.get_or_create(user=user)
            return Response({
                "token": token.key,
                "user": {
                    "id": user.id,
                    "email": user.email,  
                    "name": user.get_full_name(),
                    "username": user.username if hasattr(user, 'username') else user.email,
                }
            })
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return Response({"error": "Authentication failed"}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """
    ENHANCED: Fully bug-fixed context-aware chatbot with natural conversation flow
    """
    user = request.user
    raw_message = request.data.get('message', '').strip()
    
    if not raw_message:
        return Response({
            "error": "Please send a non-empty message.",
            "reply": "Hi! What can I help you find on Finda today? 😊"
        }, status=400)
    
    try:
        # Initialize conversation flow manager with error handling
        flow_manager = ConversationFlowManager(user.id)
        
        # Process message with enhanced context awareness
        response_strategy = flow_manager.process_message(raw_message)
        
        logger.info(f"User {user.id}: {raw_message[:50]}...")
        logger.info(f"Intent: {response_strategy['intent']} (confidence: {response_strategy['confidence']})")
        
        # Execute appropriate action based on strategy
        bot_text = execute_conversation_action(
            response_strategy, raw_message, user, flow_manager
        )
        
        # Ensure we have a valid response
        if not bot_text or len(bot_text.strip()) < 10:
            bot_text = get_fallback_response(raw_message, user)
        
        # Update conversation history
        flow_manager.add_exchange(raw_message, bot_text)
        
        # Save to database with error handling
        try:
            ChatMessage.objects.create(
                user=user,
                user_input=raw_message,
                bot_response=bot_text
            )
        except Exception as db_error:
            logger.error(f"Database save error: {str(db_error)}")
            # Continue anyway - don't fail the response
        
        return Response({"reply": bot_text})
        
    except Exception as e:
        logger.error(f"Chat API Error for user {user.id}: {str(e)}")
        
        # Clear any corrupted context
        try:
            flow_manager = ConversationFlowManager(user.id)
            flow_manager.clear_context()
        except:
            pass
        
        # Return helpful error response
        error_response = get_error_message('general_search_error')
        
        return Response({
            "reply": error_response,
            "error_handled": True
        })


def execute_conversation_action(response_strategy, raw_message, user, flow_manager):
    """
    ENHANCED: Execute the appropriate action with comprehensive error handling
    """
    action = response_strategy['action_required']
    intent = response_strategy['intent']
    context_data = response_strategy['context_data']
    
    try:
        # === GREETING RESPONSES ===
        if action == 'send_welcome':
            flow_manager.clear_context()
            
            # Determine user type
            recent_messages = ChatMessage.objects.filter(user=user).exists()
            user_type = 'returning_user' if recent_messages else 'first_time_user'
            
            return get_greeting(user_type)
        
        # === THANKS RESPONSES ===
        elif action == 'send_thanks_response':
            return (
                "You're very welcome! 😊\n\n"
                "I'm always here to help you find amazing deals on Finda. "
                "Is there anything else you'd like to search for?"
            )
        
        # === FINDA SEARCH ===
        elif action == 'perform_finda_search':
            search_terms = response_strategy.get('search_terms', raw_message)
            return handle_finda_search(search_terms, flow_manager, user)
        
        # === BROWSE CATEGORIES ===
        elif action == 'show_categories':
            return handle_categories_display(flow_manager)
        
        # === EXTERNAL SEARCH REQUEST ===
        elif action == 'perform_external_search':
            query = context_data.get('last_search_query', raw_message)
            flow_manager.clear_context()
            return handle_external_search_request(query, user)
        
        # === ENCOURAGE FINDA ===
        elif action == 'encourage_finda':
            flow_manager.clear_context()
            return ContextualResponseGenerator.generate_encouragement_response(context_data)
        
        # === ITEM SELECTION ===
        elif action == 'show_item_details':
            selected_item = response_strategy.get('selected_item')
            return handle_item_selection(selected_item, context_data, flow_manager)
        
        # === CATEGORY SELECTION ===
        elif action == 'search_category':
            category_name = response_strategy.get('selected_category', raw_message)
            return handle_category_search(category_name, flow_manager, user)
        
        # === MORE DETAILS REQUEST ===
        elif action == 'show_detailed_info':
            return provide_detailed_info(context_data, flow_manager)
        
        # === COMPARISON REQUEST ===
        elif action == 'compare_items':
            return handle_comparison_request(context_data)
        
        # === UNCLEAR RESPONSE ===
        elif action == 'ask_clarification':
            return ContextualResponseGenerator.generate_clarification_response(context_data)
        
        # === FALLBACK ===
        else:
            # Default to intelligent search
            return handle_intelligent_fallback(raw_message, flow_manager, user)
            
    except Exception as e:
        logger.error(f"Action execution error ({action}): {str(e)}")
        return get_fallback_response(raw_message, user)


def handle_finda_search(search_terms, flow_manager, user):
    """
    ENHANCED: Handle Finda database search with robust error handling
    """
    try:
        # Clean and validate search terms
        cleaned_query = clean_search_query(search_terms)
        if not cleaned_query or len(cleaned_query) < 2:
            return (
                "I'd love to help you search! Could you please tell me what specific "
                "product or service you're looking for?\n\n"
                "💡 **Examples:**\n"
                "• 'iPhone 13'\n"
                "• 'Laptop repair service'\n"
                "• 'Wedding photographer'\n"
                "• 'Used car Toyota'"
            )
        
        logger.info(f"Searching Finda for: '{cleaned_query}'")
        
        # Search Finda database with enhanced error handling
        finda_results = search_finda_database(cleaned_query, limit=5)
        
        if finda_results and len(finda_results) > 0:
            # Update conversation context with results
            flow_manager.update_after_search(cleaned_query, finda_results)
            
            # Format results with enhanced presentation
            formatted_results = format_finda_results(finda_results, cleaned_query, limit=3)
            
            if not formatted_results:
                # Fallback formatting
                formatted_results = format_basic_results(finda_results, cleaned_query)
            
            # Add contextual follow-up
            contextual_followup = (
                "\n💬 **What would you like to do next?**\n"
                "• Say 'first one' or 'number 1' for details\n"
                "• Ask 'tell me more' for additional info\n"
                "• Say 'yes' to check external stores too\n"
                "• Search for something else\n\n"
                "I'm here to help! 😊"
            )
            
            return formatted_results + contextual_followup
        
        else:
            # No results - offer smart alternatives
            flow_manager.set_external_pending(cleaned_query)
            return generate_enhanced_no_results_response(cleaned_query)
            
    except Exception as e:
        logger.error(f"Finda search error: {str(e)}")
        return (
            f"I'm searching for '{search_terms}' but having a small technical issue. "
            "Let me try a different approach - could you describe what you're looking for "
            "in a different way?"
        )


def handle_categories_display(flow_manager):
    """
    ENHANCED: Handle category display with error handling
    """
    try:
        categories = Category.objects.filter(
            is_active=True, 
            parent=None
        ).order_by('sort_order', 'name')
        
        if categories.exists():
            flow_manager.update_after_categories(categories)
            return format_categories_response()
        else:
            return (
                "Our categories are being updated right now. "
                "In the meantime, try searching for specific items like:\n\n"
                "📱 Electronics: 'iPhone', 'laptop', 'headphones'\n"
                "👗 Fashion: 'shoes', 'dress', 'bag'\n"
                "🏠 Home: 'furniture', 'kitchen', 'bedroom'\n"
                "🚗 Automotive: 'car', 'motorcycle', 'parts'\n"
                "💼 Services: 'plumber', 'electrician', 'photographer'\n\n"
                "What are you looking for?"
            )
    except Exception as e:
        logger.error(f"Categories display error: {str(e)}")
        return "Try searching for specific items instead! What are you looking for?"


def handle_item_selection(selected_item, context_data, flow_manager):
    """
    ENHANCED: Handle item selection with proper validation
    """
    try:
        if not selected_item:
            last_results = context_data.get('last_search_results', [])
            if last_results:
                return (
                    f"I have {len(last_results)} items from your last search. "
                    "Which one interests you? You can say:\n"
                    "• 'first one' or 'number 1'\n"
                    "• 'second one' or 'number 2'\n"
                    "• 'third one' or 'number 3'\n"
                )
            else:
                return "I'm not sure which item you're referring to. Could you search for something specific?"
        
        return ContextualResponseGenerator.generate_item_details_response(
            selected_item, context_data
        )
        
    except Exception as e:
        logger.error(f"Item selection error: {str(e)}")
        return "Let me help you find what you're looking for. What specific item interests you?"


def handle_category_search(category_name, flow_manager, user):
    """
    ENHANCED: Handle category-based search with validation
    """
    try:
        results = search_by_category(category_name, limit=6)
        
        if results and len(results) > 0:
            flow_manager.update_after_search(f"category:{category_name}", results)
            
            response_lines = [
                f"🛍️ **{category_name.title()} Category** - Great choices on Finda:\n"
            ]
            
            for i, obj in enumerate(results[:4], 1):
                try:
                    is_product = hasattr(obj, 'product_name')
                    name = obj.product_name if is_product else obj.service_name
                    price = obj.get_formatted_price() if is_product else obj.get_formatted_price_range()
                    location = obj.get_full_location()
                    rating = obj.average_rating()
                    
                    stars = "⭐" * min(int(rating), 5) if rating > 0 else "⭐ New"
                    
                    response_lines.append(
                        f"{i}. **{name}**\n"
                        f"   💰 {price} | 📍 {location}\n"
                        f"   {stars}\n"
                    )
                except Exception as item_error:
                    logger.error(f"Error formatting item {i}: {str(item_error)}")
                    continue
            
            total_count = len(results)
            if total_count > 4:
                response_lines.append(f"\n*Plus {total_count - 4} more in this category!*\n")
            
            response_lines.append(
                "💬 **What interests you?**\n"
                "• Pick a number for details (e.g., 'first one')\n"
                "• Ask for 'more options' in this category\n"
                "• Search for something specific\n"
            )
            
            return "\n".join(response_lines)
        
        else:
            return (
                f"No items found in {category_name} category right now. "
                "Try browsing other categories or search for specific items!\n\n"
                "Type 'categories' to see all available categories."
            )
            
    except Exception as e:
        logger.error(f"Category search error: {str(e)}")
        return f"Having trouble with {category_name} category. Try searching for specific items instead!"


def handle_external_search_request(query, user):
    """
    ENHANCED: Handle external search requests with proper fallbacks
    """
    try:
        external_prompt = f"""
The user searched for '{query}' on Finda and now wants external store suggestions.

Provide helpful suggestions from reputable online stores that deliver to Nigeria:
- Amazon (with shipping to Nigeria)
- Jumia Nigeria  
- Konga
- AliExpress
- Other reliable e-commerce platforms

Guidelines:
- Include approximate prices in Nigerian Naira (₦)
- Mention shipping considerations and delivery times  
- Keep suggestions brief and focused (3-4 options max)
- Remind them that Finda offers local support and faster delivery
- End by asking if they'd like to return to searching Finda

Present this as SECONDARY information - Finda should still feel like the better choice.
"""
        
        # Build context history
        recent_messages = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:4]
        history = []
        for msg in reversed(recent_messages):
            history.append({'author': 'user', 'content': msg.user_input})
            history.append({'author': 'assistant', 'content': msg.bot_response})
        
        external_response = send_to_gemini(history, external_prompt)
        
        return external_response + "\n\n🔄 Ready to return to Finda's marketplace? Just let me know what else you'd like to find!"
        
    except Exception as e:
        logger.error(f"External search error: {str(e)}")
        return (
            "I'm having trouble accessing external stores right now. 🔧\n\n"
            "But that's perfect! Finda has amazing local options with:\n"
            "• 🚚 Faster delivery\n"
            "• 💬 Direct seller contact\n" 
            "• 🏠 Support local businesses\n"
            "• 💯 No international shipping hassles\n\n"
            "What else can I help you find on Finda?"
        )


def provide_detailed_info(context_data, flow_manager):
    """
    ENHANCED: Provide detailed information with better formatting
    """
    try:
        last_results = context_data.get('last_search_results', [])
        last_query = context_data.get('last_search_query', '')
        
        if not last_results:
            return (
                "I'd love to give you more details! Could you let me know specifically "
                "what you'd like to learn more about? You can:\n\n"
                "• Search for a specific product or service\n"
                "• Browse our categories (type 'categories')\n"
                "• Ask about any item you're interested in"
            )
        
        response_lines = [
            f"📋 **Detailed Info** for your '{last_query}' search:\n"
        ]
        
        for i, item in enumerate(last_results[:3], 1):
            try:
                response_lines.append(
                    f"**{i}. {item['name']}**\n"
                    f"   💰 Price: {item['price']}\n"
                    f"   📍 Location: {item['location']}\n"
                    f"   📦 Type: {item['type'].title()}\n"
                    f"   🔗 [View Full Details](https://finda-six.vercel.app/{item['type']}s/{item['id']})\n"
                )
            except Exception as item_error:
                logger.error(f"Error formatting detailed item {i}: {str(item_error)}")
                continue
        
        response_lines.append(
            "\n💬 **Want to know more?**\n"
            "• Say 'contact seller' for any item\n"
            "• Ask 'compare these items'\n"
            "• Request 'similar items'\n"
            "• Get 'seller ratings and reviews'"
        )
        
        return "\n".join(response_lines)
        
    except Exception as e:
        logger.error(f"Detailed info error: {str(e)}")
        return "Let me help you find detailed information. What specific item are you interested in?"


def handle_comparison_request(context_data):
    """
    ENHANCED: Handle item comparison with better validation
    """
    try:
        last_results = context_data.get('last_search_results', [])
        
        if len(last_results) < 2:
            return (
                "I need at least 2 items to compare! Let me search for more options "
                "or you can search for specific items you'd like to compare.\n\n"
                "Try searching for something like 'iPhone' or 'laptop' to see multiple options."
            )
        
        item1, item2 = last_results[0], last_results[1]
        
        return f"""
⚖️ **Comparison: {item1['name']} vs {item2['name']}**

**Option 1:** {item1['name']}
• 💰 Price: {item1['price']}
• 📍 Location: {item1['location']}
• 📦 Type: {item1['type'].title()}

**Option 2:** {item2['name']}  
• 💰 Price: {item2['price']}
• 📍 Location: {item2['location']}
• 📦 Type: {item2['type'].title()}

💡 **My Recommendation:**
Both are great options from verified Finda sellers! Choose based on:
• 💰 Budget preference
• 📍 Location convenience  
• 🚚 Delivery speed

Would you like contact details for either seller, or should I find more options?
"""
        
    except Exception as e:
        logger.error(f"Comparison error: {str(e)}")
        return "Let me help you compare items. Search for something specific to see multiple options!"


def handle_intelligent_fallback(raw_message, flow_manager, user):
    """
    ENHANCED: Intelligent fallback that tries to understand user intent
    """
    try:
        # Detect if it might be a search query
        if len(raw_message) > 3:
            # Try as search first
            search_result = handle_finda_search(raw_message, flow_manager, user)
            if "didn't find exact matches" not in search_result:
                return search_result
        
        # Check if it's a greeting
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon']
        if any(greeting in raw_message.lower() for greeting in greetings):
            return get_greeting('returning_user')
        
        # Default helpful response
        return (
            "I want to help you find what you need on Finda! 😊\n\n"
            "💡 **Here's what I can do:**\n"
            "• 🔍 **Search** - Tell me what you're looking for\n"
            "• 📂 **Browse** - Say 'categories' to explore\n"
            "• 📸 **Image Search** - Send a photo of what you want\n"
            "• 🎤 **Voice Search** - Send a voice message\n\n"
            "What would you like to find today?"
        )
        
    except Exception as e:
        logger.error(f"Intelligent fallback error: {str(e)}")
        return get_fallback_response(raw_message, user)


def get_fallback_response(raw_message, user):
    """
    ENHANCED: Always-working fallback response
    """
    return (
        "I'm here to help you find amazing products and services on Finda! 🛍️\n\n"
        "Try telling me what you're looking for:\n"
        "• 'iPhone 13'\n"
        "• 'Laptop repair'\n"
        "• 'Wedding photographer'\n"
        "• Or just say 'categories' to browse\n\n"
        "What can I help you find?"
    )


def format_basic_results(results, query):
    """
    ENHANCED: Basic results formatting as fallback
    """
    try:
        if not results:
            return None
        
        response_lines = [f"🛍️ Found these options on Finda for '{query}':\n"]
        
        for i, obj in enumerate(results[:3], 1):
            try:
                is_product = hasattr(obj, 'product_name')
                name = obj.product_name if is_product else obj.service_name
                price = obj.get_formatted_price() if is_product else obj.get_formatted_price_range()
                location = obj.get_full_location() if hasattr(obj, 'get_full_location') else 'Location available'
                
                response_lines.append(f"{i}. {name}\n   💰 {price}\n   📍 {location}\n")
            except Exception as item_error:
                logger.error(f"Error formatting basic result {i}: {str(item_error)}")
                continue
        
        response_lines.append("✨ All from verified Finda sellers!")
        return "\n".join(response_lines)
        
    except Exception as e:
        logger.error(f"Basic formatting error: {str(e)}")
        return f"Found {len(results)} items on Finda for '{query}'. Contact sellers directly for details!"


def generate_enhanced_no_results_response(query):
    """
    ENHANCED: Better no-results response with smart suggestions
    """
    try:
        # Generate alternative search suggestions
        query_words = query.lower().split()
        suggestions = []
        
        # Common alternatives
        alternatives = {
            'phone': ['mobile', 'smartphone', 'cell phone'],
            'laptop': ['computer', 'notebook', 'PC'],
            'car': ['vehicle', 'automobile', 'auto'],
            'dress': ['clothing', 'outfit', 'apparel'],
            'repair': ['fix', 'service', 'maintenance'],
        }
        
        for word in query_words:
            if word in alternatives:
                suggestions.extend(alternatives[word])
        
        suggestion_text = ""
        if suggestions:
            suggestion_text = f"Try searching for: {', '.join(suggestions[:3])}"
        
        return f"""
🔍 I searched Finda thoroughly for '{query}' but didn't find exact matches right now.

Don't give up! Here's how I can help:

1️⃣ **Try different keywords**
   • {suggestion_text if suggestion_text else "Maybe 'phone' instead of 'smartphone'"}
   • Or use brand names like 'iPhone', 'Samsung'

2️⃣ **Browse our categories**
   • Type 'categories' to see what's popular
   • Discover similar items you might like

3️⃣ **Set up alerts** (Coming soon!)
   • Get notified when '{query}' arrives on Finda

4️⃣ **Search external stores**
   • Amazon, Jumia, Konga as backup options

What would you prefer? Say 'categories' to browse, or 'external' to check other stores!
"""
        
    except Exception as e:
        logger.error(f"Enhanced no-results error: {str(e)}")
        return generate_no_results_response(query)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_chat_api(request):
    """
    ENHANCED: Voice chat with comprehensive error handling
    """
    if 'audio' not in request.FILES:
        return Response({
            "error": "No audio file provided",
            "reply": "🎤 Please send a voice message and I'll help you find what you're looking for!"
        }, status=400)
    
    audio_file = request.FILES['audio']
    user = request.user
    
    try:
        logger.info(f"Processing voice message for user {user.id}")
        
        # Transcribe audio to text with timeout handling
        transcript = transcribe_audio(audio_file)
        
        if not transcript or len(transcript.strip()) < 2:
            return Response({
                "error": "🎤 I couldn't understand your voice message clearly.",
                "reply": "Please try speaking more clearly or use text instead. I'm here to help!",
                "transcript": ""
            }, status=400)
        
        logger.info(f"Voice transcribed: '{transcript}'")
        
        # Process using enhanced conversation flow
        flow_manager = ConversationFlowManager(user.id)
        response_strategy = flow_manager.process_message(transcript)
        
        # Add voice context indicator
        voice_prefix = f"🎤 I heard: \"{transcript}\"\n\n"
        
        # Execute action with voice-friendly formatting
        bot_text = execute_conversation_action(
            response_strategy, transcript, user, flow_manager
        )
        
        # Make response more voice-friendly
        bot_text = voice_prefix + make_voice_friendly(bot_text)
        
        # Update conversation history
        flow_manager.add_exchange(transcript, bot_text)
        
        # Generate voice response if enabled
        voice_response_url = None
        try:
            voice_settings = getattr(user, 'voice_settings', None)
            voice_enabled = voice_settings.voice_enabled if voice_settings else True
            
            if voice_enabled:
                language = voice_settings.preferred_language if voice_settings else 'en'
                slow_speech = voice_settings.voice_speed < 1.0 if voice_settings else False
                
                clean_text = clean_text_for_tts(bot_text)
                voice_response_url = generate_voice_response(clean_text, language, slow_speech)
        except Exception as voice_error:
            logger.error(f"Voice generation failed: {str(voice_error)}")
            # Continue without voice response
        
        # Save conversation
        try:
            chat_message = ChatMessage.objects.create(
                user=user,
                user_input=transcript,
                bot_response=bot_text,
                is_voice_message=True,
                audio_file=audio_file,
                transcript=transcript,
                voice_response_url=voice_response_url or ""
            )
        except Exception as save_error:
            logger.error(f"Voice message save error: {str(save_error)}")
            # Continue anyway
        
        return Response({
            "transcript": transcript,
            "reply": bot_text,
            "voice_response_url": voice_response_url,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Voice processing error: {str(e)}")
        return Response({
            "error": f"🎤 Voice processing failed. Please try again or use text.",
            "reply": "I'm having trouble with voice right now. Try typing your message instead!",
            "transcript": ""
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def image_search_api(request):
    """
    ENHANCED: Image search with comprehensive error handling
    """
    if 'image' not in request.FILES:
        return Response({
            "error": "No image provided",
            "reply": "📸 Please send an image and I'll help you find similar items on Finda!"
        }, status=400)
    
    image_file = request.FILES['image']
    user_query = request.data.get('query', 'What products are in this image?')
    user = request.user
    
    try:
        logger.info(f"Processing image search for user {user.id}")
        
        # Initialize conversation flow
        flow_manager = ConversationFlowManager(user.id)
        
        # Analyze image with Gemini Vision
        try:
            image_analysis = analyze_image_with_gemini(image_file, user_query)
            logger.info(f"Image analysis completed: {image_analysis[:100]}...")
        except Exception as analysis_error:
            logger.error(f"Image analysis failed: {str(analysis_error)}")
            image_analysis = f"I can see your image but having trouble analyzing it in detail. Please describe what you're looking for."
        
        # Search Finda database using analysis results
        finda_results = []
        try:
            finda_results = search_products_by_analysis(image_analysis, limit=4)
        except Exception as search_error:
            logger.error(f"Image-based search failed: {str(search_error)}")
        
        if finda_results and len(finda_results) > 0:
            # Update conversation context
            search_query = f"image:{user_query}"
            flow_manager.update_after_search(search_query, finda_results)
            
            response_lines = [
                "📸 **Excellent! Based on your image, I found these on Finda:**\n",
                f"🤖 *I can see: {image_analysis[:150]}...*\n"
            ]
            
            for i, obj in enumerate(finda_results, 1):
                try:
                    is_product = hasattr(obj, 'product_name')
                    name = obj.product_name if is_product else obj.service_name
                    price = obj.get_formatted_price() if is_product else obj.get_formatted_price_range()
                    location = obj.get_full_location()
                    rating = obj.average_rating()
                    
                    stars = "⭐" * min(int(rating), 5) if rating > 0 else "⭐ New"
                    
                    response_lines.append(
                        f"{i}. **{name}**\n"
                        f"   💰 {price}\n"
                        f"   📍 {location}\n"
                        f"   {stars}\n"
                    )
                except Exception as item_error:
                    logger.error(f"Error formatting image result {i}: {str(item_error)}")
                    continue
            
            response_lines.extend([
                "\n✨ These are from verified Finda sellers!",
                "\n💬 **What would you like to do?**",
                "• Say 'first one' for details about any item",
                "• Ask 'tell me more' for additional information", 
                "• Say 'yes' to also check external stores",
                "• Upload another image to search"
            ])
            
            bot_text = "\n".join(response_lines)
        
        else:
            # No matches found
            bot_text = f"""
📸 **I can see your image!** {image_analysis}

I didn't find exact matches on Finda right now, but here's what I can do:

1️⃣ **Browse similar categories** on Finda
2️⃣ **Set up alerts** for when similar items arrive  
3️⃣ **Search external stores** for similar products
4️⃣ **Try different search terms** based on what I see

💡 **My suggestions based on your image:**
• Try searching for specific brands I noticed
• Browse related categories on Finda
• Upload a clearer image if possible

What would you prefer? Say 'categories' to browse, or 'external' to check other stores!
"""
        
        # Save conversation with image metadata
        try:
            chat_message = ChatMessage.objects.create(
                user=user,
                user_input=user_query,
                bot_response=bot_text,
                is_image_message=True,
                image_file=image_file,
                image_analysis=image_analysis
            )
        except Exception as save_error:
            logger.error(f"Image message save error: {str(save_error)}")
            # Continue anyway
        
        return Response({
            "image_analysis": image_analysis,
            "reply": bot_text,
            "finda_matches_found": len(finda_results),
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Image processing error: {str(e)}")
        return Response({
            "error": f"📸 Image processing failed. Please try uploading a clearer image.",
            "reply": "Having trouble with your image. Try describing what you're looking for instead!",
            "image_analysis": ""
        }, status=500)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def voice_settings_api(request):
    """
    ENHANCED: Manage user voice settings with error handling
    """
    user = request.user
    
    try:
        if request.method == 'GET':
            settings, created = UserVoiceSettings.objects.get_or_create(
                user=user,
                defaults={
                    'preferred_language': 'en',
                    'voice_speed': 1.0,
                    'voice_enabled': True
                }
            )
            serializer = VoiceSettingsSerializer(settings)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            settings, created = UserVoiceSettings.objects.get_or_create(user=user)
            serializer = VoiceSettingsSerializer(settings, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "success": True,
                    "message": "Voice settings updated successfully",
                    "data": serializer.data
                })
            return Response({
                "success": False,
                "errors": serializer.errors
            }, status=400)
            
    except Exception as e:
        logger.error(f"Voice settings error: {str(e)}")
        return Response({
            "error": "Failed to manage voice settings",
            "success": False
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_history_api(request):
    """
    ENHANCED: Get user's chat history with pagination
    """
    try:
        user = request.user
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get messages with pagination
        messages = ChatMessage.objects.filter(user=user).order_by('-timestamp')[offset:offset + page_size]
        total_count = ChatMessage.objects.filter(user=user).count()
        
        # Serialize messages
        serializer = ChatMessageSerializer(messages, many=True)
        
        return Response({
            "messages": serializer.data,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "has_next": total_count > (page * page_size)
        })
        
    except Exception as e:
        logger.error(f"Chat history error: {str(e)}")
        return Response({
            "error": "Failed to retrieve chat history",
            "messages": []
        }, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_chat_history_api(request):
    """
    ENHANCED: Clear user's chat history and context
    """
    try:
        user = request.user
        
        # Delete chat messages
        deleted_count = ChatMessage.objects.filter(user=user).delete()[0]
        
        # Clear conversation context
        flow_manager = ConversationFlowManager(user.id)
        flow_manager.clear_context()
        
        return Response({
            "success": True,
            "message": f"Cleared {deleted_count} messages and reset conversation context",
            "deleted_count": deleted_count
        })
        
    except Exception as e:
        logger.error(f"Clear history error: {str(e)}")
        return Response({
            "error": "Failed to clear chat history",
            "success": False
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def feedback_api(request):
    """
    ENHANCED: Collect user feedback for conversation improvement
    """
    try:
        user = request.user
        message_id = request.data.get('message_id')
        feedback_type = request.data.get('type')  # 'helpful', 'not_helpful', 'incorrect'
        feedback_text = request.data.get('feedback', '')
        
        if not message_id or not feedback_type:
            return Response({
                "error": "Message ID and feedback type are required"
            }, status=400)
        
        # Log feedback for analytics
        logger.info(f"Feedback from user {user.id}: {feedback_type} for message {message_id}")
        
        # Store in cache for analytics (you can create a Feedback model later)
        feedback_key = f"feedback_{message_id}_{user.id}"
        feedback_data = {
            'user_id': user.id,
            'message_id': message_id,
            'type': feedback_type,
            'text': feedback_text,
            'timestamp': timezone.now().isoformat()
        }
        cache.set(feedback_key, feedback_data, timeout=86400 * 7)  # 7 days
        
        return Response({
            "success": True,
            "message": "Thank you for your feedback! This helps us improve."
        })
        
    except Exception as e:
        logger.error(f"Feedback error: {str(e)}")
        return Response({
            "error": "Failed to submit feedback",
            "success": False
        }, status=500)


# === HELPER FUNCTIONS ===

def make_voice_friendly(text):
    """
    ENHANCED: Make text more suitable for voice interaction
    """
    if not text:
        return ""
    
    try:
        # Simplify formatting for voice
        voice_text = text.replace('**', '').replace('*', '')
        voice_text = voice_text.replace('###', '').replace('##', '').replace('#', '')
        
        # Replace bullet points with spoken format
        voice_text = voice_text.replace('•', 'Option:')
        voice_text = voice_text.replace('1️⃣', 'First option:')
        voice_text = voice_text.replace('2️⃣', 'Second option:')
        voice_text = voice_text.replace('3️⃣', 'Third option:')
        voice_text = voice_text.replace('4️⃣', 'Fourth option:')
        
        # Simplify excessive emojis for better speech
        emoji_replacements = {
            '🛍️': '',
            '📸': '',
            '🎤': '',
            '💰': 'Price:',
            '📍': 'Location:',
            '⭐': 'rating',
            '🔍': '',
            '💡': '',
            '✅': '',
            '🚚': '',
            '💬': ''
        }
        
        for emoji, replacement in emoji_replacements.items():
            voice_text = voice_text.replace(emoji, replacement)
        
        # Clean up extra whitespace
        voice_text = ' '.join(voice_text.split())
        
        # Ensure reasonable length for voice
        if len(voice_text) > 500:
            sentences = voice_text.split('.')
            result = ""
            for sentence in sentences:
                if len(result + sentence) < 450:
                    result += sentence + ". "
                else:
                    break
            voice_text = result.strip()
        
        return voice_text
        
    except Exception as e:
        logger.error(f"Voice friendly conversion error: {str(e)}")
        return "I found some options for you. Let me know if you need more details!"


def clean_text_for_tts(text):
    """
    ENHANCED: Clean text for text-to-speech synthesis
    """
    import re
    
    if not text:
        return ""
    
    try:
        # Remove markdown formatting
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)    # Italic
        cleaned = re.sub(r'#{1,6}\s', '', cleaned)          # Headers
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)  # Links
        
        # Remove URLs
        cleaned = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned)
        
        # Remove excessive emojis for better speech
        cleaned = re.sub(r'[🛍️📸🎤✅❌💡🔍⭐💰📍🔗🚚💬🏠💯📦⚖️🔄]', '', cleaned)
        
        # Convert common symbols to words
        cleaned = cleaned.replace('&', 'and')
        cleaned = cleaned.replace('@', 'at')
        cleaned = cleaned.replace('#', 'number')
        cleaned = cleaned.replace('%', 'percent')
        cleaned = cleaned.replace('₦', 'naira')
        cleaned = cleaned.replace(',', 'dollars')
        
        # Clean up extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Limit length for TTS (most services have limits)
        if len(cleaned) > 500:
            sentences = cleaned.split('.')
            result = ""
            for sentence in sentences:
                if len(result + sentence) < 450:
                    result += sentence + ". "
                else:
                    break
            cleaned = result.strip()
        
        return cleaned
        
    except Exception as e:
        logger.error(f"TTS cleaning error: {str(e)}")
        return text[:200]  # Fallback to truncated original


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_check_api(request):
    """
    ENHANCED: Health check endpoint for monitoring
    """
    try:
        # Check database connectivity
        db_status = "OK"
        try:
            ChatMessage.objects.first()
        except Exception:
            db_status = "ERROR"
        
        # Check cache connectivity
        cache_status = "OK"
        try:
            cache.set('health_check', 'test', 10)
            cache.get('health_check')
        except Exception:
            cache_status = "ERROR"
        
        return Response({
            "status": "healthy" if db_status == "OK" and cache_status == "OK" else "unhealthy",
            "database": db_status,
            "cache": cache_status,
            "timestamp": timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": timezone.now().isoformat()
        }, status=500)
    