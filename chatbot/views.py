# views.py - ENHANCED VERSION with Natural Conversation Flow
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model

from .gemini_client import (
    send_to_gemini, analyze_image_with_gemini, 
    transcribe_audio, generate_voice_response
)
from .models import ChatMessage, UserVoiceSettings
from .serializers import ChatMessageSerializer, VoiceSettingsSerializer
from .utils import (
    search_finda_database, format_finda_results, generate_no_results_response,
    search_by_category, get_trending_items, format_categories_response,
    search_products_by_analysis
)
from .enhanced_conversation_manager import (
    ConversationFlowManager, ContextualResponseGenerator
)
from main.models import Products, Services, Category

User = get_user_model()

# ENHANCED SYSTEM PROMPT - Context-aware
SYSTEM_PROMPT = (
    "You are Finda's intelligent shopping assistant with advanced conversation abilities. "
    "You understand context, remember what you just discussed, and maintain natural conversation flow.\n\n"
    "CORE PRINCIPLES:\n"
    "1. ALWAYS maintain conversation context and remember what was just discussed\n"
    "2. Respond naturally to follow-up questions and references like 'the first one', 'tell me more'\n"
    "3. Search Finda's database FIRST, then offer external options only as bonus alternatives\n"
    "4. Keep conversations flowing naturally - no robotic responses\n"
    "5. Ask clarifying questions when user intent is unclear\n\n"
    "CONVERSATION SKILLS:\n"
    "- Remember the last search results and can discuss specific items\n"
    "- Understand contextual references and follow-up questions\n"
    "- Maintain conversation state across multiple exchanges\n"
    "- Ask natural follow-up questions to keep users engaged\n\n"
    "Always prioritize Finda's marketplace while maintaining natural, helpful conversation!"
)

class CustomAuthToken(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        if email is None or password is None:
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
            }
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """
    ENHANCED: Context-aware chatbot with natural conversation flow
    """
    user = request.user
    raw_message = request.data.get('message', '').strip()
    
    if not raw_message:
        return Response({"detail": "Please send a non-empty message."}, status=400)
    
    # Initialize conversation flow manager
    flow_manager = ConversationFlowManager(user.id)
    
    try:
        # Process message with context awareness
        response_strategy = flow_manager.process_message(raw_message)
        
        print(f"🧠 Intent: {response_strategy['intent']} (confidence: {response_strategy['confidence']})")
        print(f"🎯 Action: {response_strategy['action_required']}")
        print(f"🔄 Context-aware: {response_strategy['context_aware']}")
        
        # Execute appropriate action based on strategy
        bot_text = execute_conversation_action(
            response_strategy, raw_message, user, flow_manager
        )
        
        # Update conversation history
        flow_manager.add_exchange(raw_message, bot_text)
        
    except Exception as e:
        print(f"❌ Enhanced Chat API Error: {str(e)}")
        bot_text = (
            "I'm having a small technical hiccup right now. 🔧\n\n"
            "Could you please try again? I'm here to help you find amazing "
            "products and services on Finda!"
        )
        flow_manager.clear_context()
    
    # Save conversation to database
    ChatMessage.objects.create(
        user=user,
        user_input=raw_message,
        bot_response=bot_text
    )
    
    return Response({"reply": bot_text})


def execute_conversation_action(response_strategy, raw_message, user, flow_manager):
    """
    Execute the appropriate action based on conversation analysis
    """
    action = response_strategy['action_required']
    intent = response_strategy['intent']
    context_data = response_strategy['context_data']
    
    # === GREETING RESPONSES ===
    if action == 'send_welcome':
        flow_manager.clear_context()
        
        # Check if returning user
        recent_messages = ChatMessage.objects.filter(user=user).exists()
        
        if recent_messages:
            return (
                "Welcome back to Finda! 😊\n\n"
                "Ready to discover more amazing deals from our local marketplace? "
                "What are you looking for today?"
            )
        else:
            return (
                "🛍️ Welcome to Finda! I'm your personal shopping assistant.\n\n"
                "I'm here to help you discover amazing products and services from "
                "trusted local Nigerian sellers. What can I help you find today?\n\n"
                "💡 **You can:**\n"
                "• Search for anything (e.g., 'iPhone 13', 'plumber')\n"
                "• Browse categories (just say 'categories')\n"
                "• Send photos of items you want\n"
                "• Use voice messages to search\n\n"
                "Let's start shopping! What do you need?"
            )
    
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
        return handle_finda_search(search_terms, flow_manager)
    
    # === BROWSE CATEGORIES ===
    elif action == 'show_categories':
        categories = Category.objects.filter(
            is_active=True, parent=None
        ).order_by('sort_order', 'name')
        
        flow_manager.update_after_categories(categories)
        return format_categories_response()
    
    # === EXTERNAL SEARCH REQUEST ===
    elif action == 'perform_external_search':
        query = context_data.get('last_search_query', raw_message)
        flow_manager.clear_context()
        
        return handle_external_search_request(query, user)
    
    # === DECLINE EXTERNAL SEARCH ===
    elif action == 'encourage_finda':
        flow_manager.clear_context()
        return ContextualResponseGenerator.generate_encouragement_response(context_data)
    
    # === ITEM SELECTION ===
    elif action == 'show_item_details':
        selected_item = response_strategy.get('selected_item')
        return ContextualResponseGenerator.generate_item_details_response(
            selected_item, context_data
        )
    
    # === CATEGORY SELECTION ===
    elif action == 'search_category':
        category_name = response_strategy.get('selected_category', raw_message)
        return handle_category_search(category_name, flow_manager)
    
    # === MORE DETAILS REQUEST ===
    elif action == 'show_detailed_info':
        return provide_detailed_info(context_data)
    
    # === COMPARISON REQUEST ===
    elif action == 'compare_items':
        return handle_comparison_request(context_data)
    
    # === UNCLEAR RESPONSE ===
    elif action == 'ask_clarification':
        return ContextualResponseGenerator.generate_clarification_response(context_data)
    
    # === FALLBACK ===
    else:
        # Default to search
        return handle_finda_search(raw_message, flow_manager)


def handle_finda_search(search_terms, flow_manager):
    """
    Handle Finda database search with context updates
    """
    print(f"🔍 Searching Finda for: '{search_terms}'")
    
    # Search Finda database
    finda_results = search_finda_database(search_terms, limit=5)
    
    if finda_results:
        # Update conversation context with results
        flow_manager.update_after_search(search_terms, finda_results)
        
        # Format results with context-aware messaging
        formatted_results = format_finda_results(finda_results, search_terms)
        
        # Add contextual follow-up
        contextual_followup = (
            "\n💬 **What would you like to do next?**\n"
            "• Say 'first one' or 'second one' for details\n"
            "• Ask 'tell me more' for additional info\n"
            "• Say 'yes' to check external stores too\n"
            "• Search for something else\n\n"
            "I'm here to help! 😊"
        )
        
        return formatted_results + contextual_followup
    
    else:
        # No results - offer alternatives with context
        flow_manager.set_external_pending(search_terms)
        return generate_no_results_response(search_terms)


def handle_category_search(category_name, flow_manager):
    """
    Handle category-based search
    """
    results = search_by_category(category_name, limit=6)
    
    if results:
        flow_manager.update_after_search(f"category:{category_name}", results)
        
        response_lines = [
            f"🛍️ **{category_name.title()} Category** - Great choices on Finda:\n"
        ]
        
        for i, obj in enumerate(results[:4], 1):
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
        return f"No items found in {category_name} category right now. Try browsing other categories or search for specific items!"


def provide_detailed_info(context_data):
    """
    Provide more detailed information based on context
    """
    last_results = context_data.get('last_search_results', [])
    last_query = context_data.get('last_search_query', '')
    
    if not last_results:
        return (
            "I'd love to give you more details! Could you let me know specifically "
            "what you'd like to learn more about? You can:\n\n"
            "• Search for a specific product or service\n"
            "• Browse our categories\n"
            "• Ask about any item you're interested in"
        )
    
    response_lines = [
        f"📋 **Detailed Info** for your '{last_query}' search:\n"
    ]
    
    for i, item in enumerate(last_results[:3], 1):
        response_lines.append(
            f"**{i}. {item['name']}**\n"
            f"   💰 Price: {item['price']}\n"
            f"   📍 Location: {item['location']}\n"
            f"   📦 Type: {item['type'].title()}\n"
            f"   🔗 [View Full Details](https://finda.ng/{item['type']}s/{item['id']})\n"
        )
    
    response_lines.append(
        "\n💬 **Want to know more?**\n"
        "• Say 'contact seller' for any item\n"
        "• Ask 'compare these items'\n"
        "• Request 'similar items'\n"
        "• Get 'seller ratings and reviews'"
    )
    
    return "\n".join(response_lines)


def handle_comparison_request(context_data):
    """
    Handle item comparison requests
    """
    last_results = context_data.get('last_search_results', [])
    
    if len(last_results) < 2:
        return (
            "I need at least 2 items to compare! Let me search for more options "
            "or you can search for specific items you'd like to compare."
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


def handle_external_search_request(query, user):
    """
    Handle external search requests using Gemini
    """
    external_prompt = f"""
The user searched for '{query}' on Finda and now wants external store suggestions as bonus options.

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

Remember: Present this as SECONDARY information - Finda should still feel like the better choice.
"""
    
    try:
        # Build minimal history for context
        recent_messages = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:6]
        history = []
        for msg in reversed(recent_messages):
            history.append({'author': 'user', 'content': msg.user_input})
            history.append({'author': 'assistant', 'content': msg.bot_response})
        
        external_response = send_to_gemini(history, external_prompt)
        
        return external_response + "\n\n🔄 Ready to return to Finda's marketplace? Just let me know what else you'd like to find!"
        
    except Exception as e:
        print(f"❌ External search error: {e}")
        return (
            "I'm having trouble accessing external stores right now. 🔧\n\n"
            "But that's okay! Finda has amazing local options with:\n"
            "• 🚚 Faster delivery\n"
            "• 💬 Direct seller contact\n" 
            "• 🏠 Support local businesses\n\n"
            "What else can I help you find on Finda?"
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def voice_chat_api(request):
    """
    Enhanced voice chat with natural conversation flow
    """
    if 'audio' not in request.FILES:
        return Response({"error": "No audio file provided"}, status=400)
    
    audio_file = request.FILES['audio']
    user = request.user
    
    try:
        # Transcribe audio to text
        transcript = transcribe_audio(audio_file)
        
        if not transcript:
            return Response({
                "error": "🎤 I couldn't understand your voice message clearly. Please try speaking more clearly or use text instead.",
                "transcript": ""
            }, status=400)
        
        print(f"🎤 Voice transcribed: '{transcript}'")
        
        # Process using enhanced conversation flow
        flow_manager = ConversationFlowManager(user.id)
        response_strategy = flow_manager.process_message(transcript)
        
        # Add voice context indicator
        voice_prefix = "🎤 I heard you say: \"" + transcript + "\"\n\n"
        
        # Execute action with voice-friendly formatting
        bot_text = execute_conversation_action(
            response_strategy, transcript, user, flow_manager
        )
        
        # Make response more voice-friendly
        bot_text = voice_prefix + make_voice_friendly(bot_text)
        
        # Update conversation history
        flow_manager.add_exchange(transcript, bot_text)
        
        # Generate voice response if enabled
        voice_settings = getattr(user, 'voice_settings', None)
        voice_enabled = voice_settings.voice_enabled if voice_settings else True
        voice_response_url = None
        
        if voice_enabled:
            try:
                language = voice_settings.preferred_language if voice_settings else 'en'
                slow_speech = voice_settings.voice_speed < 1.0 if voice_settings else False
                
                clean_text = clean_text_for_tts(bot_text)
                voice_response_url = generate_voice_response(clean_text, language, slow_speech)
            except Exception as e:
                print(f"⚠️ Voice generation failed: {e}")
        
        # Save conversation
        chat_message = ChatMessage.objects.create(
            user=user,
            user_input=transcript,
            bot_response=bot_text,
            is_voice_message=True,
            audio_file=audio_file,
            transcript=transcript,
            voice_response_url=voice_response_url or ""
        )
        
        return Response({
            "transcript": transcript,
            "reply": bot_text,
            "voice_response_url": voice_response_url,
            "message_id": chat_message.id
        })
        
    except Exception as e:
        print(f"❌ Voice processing error: {e}")
        return Response({
            "error": f"🎤 Voice processing failed: {str(e)}",
            "transcript": ""
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def image_search_api(request):
    """
    Enhanced image search with conversation context
    """
    if 'image' not in request.FILES:
        return Response({"error": "No image provided"}, status=400)
    
    image_file = request.FILES['image']
    user_query = request.data.get('query', 'What products are in this image?')
    user = request.user
    
    try:
        print(f"📸 Processing image search with query: '{user_query}'")
        
        # Initialize conversation flow
        flow_manager = ConversationFlowManager(user.id)
        
        # Analyze image with Gemini Vision
        image_analysis = analyze_image_with_gemini(image_file, user_query)
        print(f"🤖 AI Analysis: {image_analysis[:100]}...")
        
        # Search Finda database using analysis results
        finda_results = search_products_by_analysis(image_analysis, limit=4)
        
        if finda_results:
            # Update conversation context
            search_query = f"image:{user_query}"
            flow_manager.update_after_search(search_query, finda_results)
            
            response_lines = [
                "📸 **Excellent! Based on your image, I found these on Finda:**\n",
                f"🤖 *I can see: {image_analysis[:150]}...*\n"
            ]
            
            for i, obj in enumerate(finda_results, 1):
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
        chat_message = ChatMessage.objects.create(
            user=user,
            user_input=user_query,
            bot_response=bot_text,
            is_image_message=True,
            image_file=image_file,
            image_analysis=image_analysis
        )
        
        return Response({
            "image_analysis": image_analysis,
            "reply": bot_text,
            "finda_matches_found": len(finda_results),
            "message_id": chat_message.id
        })
        
    except Exception as e:
        print(f"❌ Image processing error: {e}")
        return Response({
            "error": f"📸 Image processing failed: {str(e)}. Please try uploading a clearer image or describe what you're looking for instead."
        }, status=500)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def voice_settings_api(request):
    """
    Manage user voice settings
    """
    user = request.user
    
    if request.method == 'GET':
        settings, created = UserVoiceSettings.objects.get_or_create(user=user)
        serializer = VoiceSettingsSerializer(settings)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        settings, created = UserVoiceSettings.objects.get_or_create(user=user)
        serializer = VoiceSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# === HELPER FUNCTIONS ===

def make_voice_friendly(text):
    """
    Make text more suitable for voice interaction
    """
    if not text:
        return ""
    
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
    emoji_map = {
        '🛍️': 'shopping',
        '📸': 'image',
        '🎤': 'voice',
        '💰': 'price',
        '📍': 'location',
        '⭐': 'rating',
        '🔍': 'search',
        '💡': 'tip',
        '✅': 'benefit',
        '🚚': 'delivery'
    }
    
    for emoji, word in emoji_map.items():
        voice_text = voice_text.replace(emoji, '')
    
    # Clean up extra whitespace
    voice_text = ' '.join(voice_text.split())
    
    return voice_text


def clean_text_for_tts(text):
    """
    Clean text for text-to-speech synthesis
    """
    import re
    
    if not text:
        return ""
    
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