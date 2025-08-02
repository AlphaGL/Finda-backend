# views.py - FIXED: Database-first chatbot with proper priority system
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
from main.models import Products, Services, Category

User = get_user_model()

# ENHANCED SYSTEM PROMPT - Database-first priority
SYSTEM_PROMPT = (
    "You are Finda's intelligent shopping assistant. Your PRIMARY mission is to help users "
    "discover and buy products and services from Finda's marketplace.\n\n"
    "CORE PRINCIPLES:\n"
    "1. ALWAYS search Finda's database FIRST before any external suggestions\n"
    "2. Promote Finda products and services as the main solution\n"
    "3. Present external suggestions only as 'bonus options' when asked\n"  
    "4. Remember: Users came to Finda to buy from LOCAL sellers, not competitors\n"
    "5. Make Finda feel like the best choice, not just another option\n\n"
    "CONVERSATION FLOW:\n"
    "- Search Finda database for any product/service requests\n"
    "- Present Finda results with enthusiasm and detail\n"
    "- Only mention external stores as secondary options\n"
    "- Focus on benefits of buying local (faster delivery, better support)\n\n"
    "Always be enthusiastic about Finda's marketplace!"
)

# Intent recognition patterns
GREETINGS = {
    "hi", "hello", "hey", "hiya", "yo", "howdy", "sup", "what's up", "hey there", 
    "good morning", "good afternoon", "good evening", "morning", "evening",
    "habari", "sannu", "bawo", "ẹ n lẹ", "ndewo"
}

THANKS = {
    "thanks", "thank you", "thanks a lot", "thank you so much", "much appreciated",
    "thx", "ty", "tysm", "appreciate it", "ẹ se", "na gode", "asante"
}

POSITIVE_CONFIRMATIONS = {
    "yes", "yeah", "yep", "yup", "sure", "absolutely", "definitely", "okay", "ok",
    "alright", "go ahead", "let's do it", "why not", "sounds good", "yes please",
    "do it", "i want that", "show me", "y"
}

NEGATIVE_CONFIRMATIONS = {
    "no", "nope", "nah", "not really", "not now", "maybe later", "not interested",
    "no thanks", "i'm good", "i'll pass", "not today", "skip", "cancel", "n"
}

BROWSE_PATTERNS = {
    "categories", "browse", "explore", "what do you have", "show me", "catalog",
    "what's available", "list products", "list services", "shop", "marketplace"
}

EXTERNAL_REQUEST_PATTERNS = {
    "external", "amazon", "jumia", "konga", "other stores", "outside", "international"
}

class CustomAuthToken(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, kwargs):
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
    FIXED: Database-first chatbot with proper conversation flow
    """
    user = request.user
    raw_message = request.data.get('message', '').strip()
    
    if not raw_message:
        return Response({"detail": "Please send a non-empty message."}, status=400)
    
    lower_message = raw_message.lower()
    
    # Build conversation history for context
    recent_messages = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:10]
    history = []
    for msg in reversed(recent_messages):
        history.append({'author': 'user', 'content': msg.user_input})
        history.append({'author': 'assistant', 'content': msg.bot_response})
    
    # Add system prompt for new users
    if not recent_messages.exists():
        history.insert(0, {'author': 'system', 'content': SYSTEM_PROMPT})
    
    try:
        # ===========================================
        # CONVERSATION FLOW - DATABASE FIRST ALWAYS
        # ===========================================
        
        # 1. GREETINGS - Welcome to Finda
        if any(greeting in lower_message for greeting in GREETINGS):
            if recent_messages.exists():
                bot_text = (
                    "Welcome back to Finda! 😊\n\n"
                    "Ready to discover more amazing deals from our local marketplace?\n"
                    "What are you looking for today?"
                )
            else:
                bot_text = (
                    "🛍️ Welcome to Finda! I'm your personal shopping assistant.\n\n"
                    "I'm here to help you discover amazing products and services from trusted local sellers. "
                    "What can I help you find today?\n\n"
                    "💡 You can:\n"
                    "• Search for specific items (e.g., 'iPhone 13', 'plumbing services')\n"
                    "• Browse categories (just say 'categories')\n"
                    "• Send me photos of items you want\n"
                    "• Use voice messages to search\n\n"
                    "Let's start shopping! What do you need?"
                )
        
        # 2. THANK YOU responses
        elif any(thanks in lower_message for thanks in THANKS):
            bot_text = (
                "You're very welcome! 😊\n\n"
                "I'm always here to help you find amazing deals on Finda. "
                "Feel free to search for anything else from our local marketplace!"
            )
        
        # 3. BROWSE CATEGORIES request
        elif any(pattern in lower_message for pattern in BROWSE_PATTERNS):
            bot_text = format_categories_response()
        
        # 4. Check if user is responding to EXTERNAL STORE suggestion
        elif recent_messages.exists():
            last_bot_response = recent_messages.first().bot_response.lower()
            asked_about_external = ("external stores" in last_bot_response or 
                                  "amazon" in last_bot_response or 
                                  "jumia" in last_bot_response or
                                  "bonus alternatives" in last_bot_response)
            
            # User wants external suggestions
            if asked_about_external and any(conf in lower_message for conf in POSITIVE_CONFIRMATIONS):
                external_prompt = (
                    f"The user searched for products on Finda and now wants external store suggestions "
                    f"as bonus options. Their original query was related to: '{raw_message}'. "
                    f"Provide helpful suggestions from reputable online stores that deliver to Nigeria "
                    f"like Amazon, Jumia, Konga, etc. Include approximate prices in Naira (₦) and "
                    f"mention shipping considerations. Keep it brief and remind them that Finda "  
                    f"offers local support and faster delivery."
                )
                bot_text = send_to_gemini(history, external_prompt)
            
            # User doesn't want external suggestions
            elif asked_about_external and any(conf in lower_message for conf in NEGATIVE_CONFIRMATIONS):
                bot_text = (
                    "Perfect choice! Stick with Finda for the best local shopping experience! 🛍️\n\n"
                    "✅ Smart decision because:\n"
                    "• 🚚 Faster local delivery\n"
                    "• 💬 Direct chat with sellers\n" 
                    "• 🏠 Support Nigerian businesses\n"
                    "• 💯 No international shipping hassles\n\n"
                    "What else can I help you find on Finda today?"
                )
            
            # Regular search - DATABASE FIRST!
            else:
                bot_text = handle_search_request(raw_message, lower_message)
        
        # 5. MAIN SEARCH LOGIC - Always search DATABASE FIRST
        else:
            bot_text = handle_search_request(raw_message, lower_message)
    
    except Exception as e:
        print(f"❌ Chat API Error: {str(e)}")
        bot_text = (
            "I'm having a small technical hiccup right now. 🔧\n\n"
            "Could you please try your search again? I'm here to help you "
            "find amazing products and services on Finda!"
        )
    
    # Save conversation to database
    ChatMessage.objects.create(
        user=user,
        user_input=raw_message,
        bot_response=bot_text
    )
    
    return Response({"reply": bot_text})

def handle_search_request(raw_message, lower_message):
    """
    CORE SEARCH LOGIC - Always prioritize Finda database
    """
    print(f"🔍 Processing search request: '{raw_message}'")
    
    # Check if user specifically asked for external stores
    explicit_external_request = any(pattern in lower_message for pattern in EXTERNAL_REQUEST_PATTERNS)
    
    if explicit_external_request:
        # User specifically asked for external stores
        return (
            f"I understand you want to check external stores for '{raw_message}'.\n\n"
            f"But first, let me show you what we have on Finda! 🛍️\n\n"
            f"{search_and_format_finda_results(raw_message)}\n\n"
            f"Would you still like me to check external stores like Amazon and Jumia as well?"
        )
    
    # NORMAL FLOW: Search Finda database FIRST
    return search_and_format_finda_results(raw_message)

def search_and_format_finda_results(query):
    """
    Search Finda database and format results properly
    """
    print(f"🎯 Searching Finda database for: '{query}'")
    
    # 1. SEARCH FINDA DATABASE FIRST
    finda_results = search_finda_database(query, limit=5)
    
    if finda_results:
        # SUCCESS! Found results in YOUR database
        print(f"✅ Found {len(finda_results)} results in Finda database")
        return format_finda_results(finda_results, query)
    
    else:
        # No results in YOUR database - offer helpful alternatives
        print("❌ No results found in Finda database")
        return generate_no_results_response(query)

@api_view(['POST']) 
@permission_classes([IsAuthenticated])
def voice_chat_api(request):
    """
    Enhanced voice chat with database-first priority
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
        
        # Get user's voice settings
        voice_settings = getattr(user, 'voice_settings', None)
        voice_enabled = voice_settings.voice_enabled if voice_settings else True
        
        # Process transcript using DATABASE-FIRST logic
        lower_transcript = transcript.lower()
        
        # Handle voice-specific responses
        if any(greeting in lower_transcript for greeting in GREETINGS):
            bot_text = (
                "🎤 Hello! I heard you loud and clear! Welcome to Finda!\n\n"
                "What can I help you find from our amazing local marketplace today?"
            )
        elif any(thanks in lower_transcript for thanks in THANKS):
            bot_text = "🎤 You're very welcome! Let me know if you'd like to find anything else on Finda."
        elif any(pattern in lower_transcript for pattern in BROWSE_PATTERNS):
            bot_text = format_categories_response()
        else:
            # MAIN VOICE SEARCH - Database first!
            bot_text = f"🎤 Perfect! I heard you asking for '{transcript}'.\n\nLet me search Finda's marketplace for you...\n\n"
            bot_text += search_and_format_finda_results(transcript)
        
        # Generate voice response if enabled
        voice_response_url = None
        if voice_enabled and bot_text:
            try:
                language = voice_settings.preferred_language if voice_settings else 'en'
                slow_speech = voice_settings.voice_speed < 1.0 if voice_settings else False
                
                # Clean bot_text for voice (remove markdown and emojis for better TTS)
                clean_text_for_voice = clean_text_for_tts(bot_text)
                voice_response_url = generate_voice_response(clean_text_for_voice, language, slow_speech)
            except Exception as e:
                print(f"⚠️ Voice generation failed: {e}")
        
        # Save conversation with voice metadata
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
    Enhanced image search with database-first priority
    """
    if 'image' not in request.FILES:
        return Response({"error": "No image provided"}, status=400)
    
    image_file = request.FILES['image']
    user_query = request.data.get('query', 'What products are in this image?')
    user = request.user
    
    try:
        print(f"📸 Processing image search with query: '{user_query}'")
        
        # Analyze image with Gemini Vision
        image_analysis = analyze_image_with_gemini(image_file, user_query)
        print(f"🤖 AI Analysis: {image_analysis[:100]}...")
        
        # SEARCH FINDA DATABASE using analysis results
        finda_results = search_products_by_analysis(image_analysis, limit=4)
        
        if finda_results:
            # SUCCESS! Found matching products in YOUR database
            print(f"✅ Found {len(finda_results)} image matches in Finda database")
            
            response_lines = [
                "📸 Excellent! Based on your image, I found these on Finda:\n"
            ]
            
            for i, obj in enumerate(finda_results, 1):
                is_product = hasattr(obj, 'product_name')
                name = obj.product_name if is_product else obj.service_name
                price = obj.get_formatted_price() if is_product else obj.get_formatted_price_range()
                location = obj.get_full_location()
                rating = obj.average_rating()
                rating_count = obj.rating_count()
                url = obj.get_absolute_url()
                
                # Format rating
                if rating > 0 and rating_count > 0:
                    stars = "⭐" * min(int(rating), 5)
                    rating_text = f"{stars} {rating}/5 ({rating_count} reviews)"
                else:
                    rating_text = "⭐ New listing"
                
                response_lines.append(
                    f"{i}. {name}\n"
                    f"   💰 {price}\n"
                    f"   📍 {location}\n"
                    f"   {rating_text}\n"
                    f"   🔗 [View Details](https://finda.ng{url})\n"
                )
            
            response_lines.extend([
                "\n✨ These are from verified Finda sellers with great ratings!\n",
                "💡 Need more options? I can also search external stores like Amazon, Jumia, etc. "
                "Just say 'yes' if you'd like me to check those too!"
            ])
            
            bot_text = "\n".join(response_lines)
        
        else:
            # No matches in YOUR database - use AI analysis but focus on Finda
            print("❌ No image matches found in Finda database")
            
            bot_text = (
                f"📸 I can see your image! {image_analysis}\n\n"
                f"I didn't find exact matches on Finda right now, but here's what I can do:\n\n"
                f"1️⃣ Browse similar categories on Finda\n"
                f"2️⃣ Set up alerts for when similar items arrive\n"
                f"3️⃣ Search external stores for similar products\n"
                f"4️⃣ Try different search terms based on what I see\n\n"
                f"What would you prefer? Say 'categories' to browse, or 'external' to check other stores!"
            )
        
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

# Helper functions
def clean_text_for_tts(text):
    """
    Clean text for better text-to-speech output
    """
    import re
    
    if not text:
        return ""
    
    # Remove markdown formatting
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)    # Italic
    cleaned = re.sub(r'#{1,6}\s', '', cleaned)          # Headers
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)  # Links
    
    # Remove excessive emojis for better speech
    cleaned = re.sub(r'[🛍️📸🎤✅❌💡🔍⭐💰📍🔗🚚💬🏠💯]', '', cleaned)
    
    # Clean up extra whitespace
    cleaned = ' '.join(cleaned.split())
    
    # Limit length for TTS (most TTS services have limits)
    if len(cleaned) > 500:
        cleaned = cleaned[:497] + "..."
    
    return cleaned