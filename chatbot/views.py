# chatbot/views.py - Enhanced with Advanced Features
import json
import base64
import speech_recognition as sr
from PIL import Image
import io
import re
import time
from datetime import datetime, timedelta
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q, Avg, Count, Max
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import google.generativeai as genai
from django.conf import settings

from .gemini_client import send_to_gemini, analyze_image_with_gemini
from .models import (
    ChatMessage, ChatSession, UserPreference, SearchQuery, 
    ProductSuggestion, VoiceMessage, ImageAnalysis,
    ConversationContext, FeedbackRating, ExternalSourceTracking
)
from .serializers import (
    ChatMessageSerializer, ChatSessionSerializer, VoiceMessageSerializer,
    UserPreferenceSerializer, SearchQuerySerializer, ProductSuggestionSerializer,
    FeedbackRatingSerializer, ConversationContextSerializer,
    TextMessageInputSerializer, VoiceMessageInputSerializer, 
    ImageMessageInputSerializer, ChatResponseSerializer,
    PreferenceUpdateSerializer, AnalyticsSerializer
)
from main.models import Products, Services, Category, Country, State, City
from .utils import (
    extract_product_preferences, 
    filter_products_by_preferences,
    format_product_results,
    format_service_results,
    get_external_suggestions,
    process_voice_to_text,
    analyze_product_image
)

User = get_user_model()

# Enhanced system prompt
ENHANCED_SYSTEM_PROMPT = """
You are Finda AI, an intelligent shopping assistant for the Finda marketplace. Your role is to:

1. Help users find products and services on Finda's platform first
2. Ask detailed questions to understand user preferences (color, size, price range, location, brand, etc.)
3. Provide comprehensive product/service information with images, prices, and seller contact details
4. If no matches found internally, suggest external alternatives from popular stores
5. Handle image-based searches and voice queries naturally
6. Be conversational, helpful, and maintain context throughout the conversation

Always prioritize Finda's internal inventory before suggesting external sources.
When showing results, include: product name, price, seller location, contact info, and direct links.
"""

class EnhancedChatAPI(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        user = request.user
        message_type = request.data.get('type', 'text')  # text, voice, image
        
        try:
            if message_type == 'voice':
                return self.handle_voice_message(request, user)
            elif message_type == 'image':
                return self.handle_image_message(request, user)
            else:
                return self.handle_text_message(request, user)
        except Exception as e:
            return Response({
                "error": "Something went wrong. Please try again.",
                "detail": str(e)
            }, status=500)

    def handle_text_message(self, request, user):
        raw_message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        
        if not raw_message:
            return Response({"detail": "Please send a non-empty message."}, status=400)
        
        # Get or create chat session
        session = self.get_or_create_session(user, session_id)
        
        # Get conversation context
        context = self.get_conversation_context(session)
        
        # Process the message
        bot_response = self.process_user_message(raw_message, context, user, session)
        
        # Save message to database
        chat_message = ChatMessage.objects.create(
            session=session,
            user_input=raw_message,
            bot_response=bot_response,
            message_type='text'
        )
        
        return Response({
            "reply": bot_response,
            "session_id": session.id,
            "message_id": chat_message.id,
            "timestamp": chat_message.timestamp
        })

    def handle_voice_message(self, request, user):
        audio_file = request.FILES.get('audio')
        session_id = request.data.get('session_id')
        
        if not audio_file:
            return Response({"error": "No audio file provided"}, status=400)
        
        try:
            # Convert voice to text
            text_message = process_voice_to_text(audio_file)
            
            if not text_message:
                return Response({"error": "Could not process voice message"}, status=400)
            
            # Get or create session
            session = self.get_or_create_session(user, session_id)
            
            # Process as text message
            context = self.get_conversation_context(session)
            bot_response = self.process_user_message(text_message, context, user, session)
            
            # Save message
            chat_message = ChatMessage.objects.create(
                session=session,
                user_input=text_message,
                bot_response=bot_response,
                message_type='voice',
                audio_file=audio_file
            )
            
            return Response({
                "transcribed_text": text_message,
                "reply": bot_response,
                "session_id": session.id,
                "message_id": chat_message.id,
                "timestamp": chat_message.timestamp
            })
            
        except Exception as e:
            return Response({"error": f"Voice processing failed: {str(e)}"}, status=500)

    def handle_image_message(self, request, user):
        image_file = request.FILES.get('image')
        additional_message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')
        
        if not image_file:
            return Response({"error": "No image file provided"}, status=400)
        
        try:
            # Get or create session
            session = self.get_or_create_session(user, session_id)
            
            # Analyze image
            image_analysis = analyze_product_image(image_file)
            
            if not image_analysis:
                return Response({"error": "Could not analyze the image"}, status=400)
            
            # Create search query from image analysis
            search_query = f"{image_analysis.get('product_type', '')} {image_analysis.get('description', '')}".strip()
            
            if additional_message:
                combined_message = f"I'm looking for this product in the image: {additional_message}. Image shows: {search_query}"
            else:
                combined_message = f"I'm looking for this product: {search_query}"
            
            # Process the message
            context = self.get_conversation_context(session)
            bot_response = self.process_user_message(combined_message, context, user, session, image_analysis)
            
            # Save message
            chat_message = ChatMessage.objects.create(
                session=session,
                user_input=additional_message or "Image search",
                bot_response=bot_response,
                message_type='image',
                image_file=image_file,
                image_analysis_data=image_analysis
            )
            
            return Response({
                "image_analysis": image_analysis,
                "search_query": search_query,
                "reply": bot_response,
                "session_id": session.id,
                "message_id": chat_message.id,
                "timestamp": chat_message.timestamp
            })
            
        except Exception as e:
            return Response({"error": f"Image processing failed: {str(e)}"}, status=500)

    def get_or_create_session(self, user, session_id=None):
        if session_id:
            try:
                return ChatSession.objects.get(id=session_id, user=user)
            except ChatSession.DoesNotExist:
                pass
        
        return ChatSession.objects.create(user=user)

    def get_conversation_context(self, session):
        recent_messages = ChatMessage.objects.filter(
            session=session
        ).order_by('-timestamp')[:10]
        
        context = {
            'history': [],
            'preferences': {},
            'last_search_type': None,
            'awaiting_confirmation': False
        }
        
        for msg in reversed(recent_messages):
            context['history'].append({
                'author': 'user',
                'content': msg.user_input,
                'type': msg.message_type
            })
            context['history'].append({
                'author': 'assistant', 
                'content': msg.bot_response,
                'type': 'text'
            })
            
            # Extract preferences from conversation
            if msg.preference_data:
                context['preferences'].update(msg.preference_data)
        
        return context

    def process_user_message(self, message, context, user, session, image_data=None):
        lower_message = message.lower()
        
        # Check for greeting
        if self.is_greeting(lower_message):
            return "Hello! Welcome to Finda AI! 🛍️ I'm here to help you find amazing products and services. You can:\n\n• Tell me what you're looking for\n• Send me a photo of a product\n• Send a voice message\n• Browse our categories\n\nWhat would you like to find today?"
        
        # Check for browse request
        if self.is_browse_request(lower_message):
            return self.handle_browse_request()
        
        # Check for confirmation responses
        if context.get('awaiting_confirmation'):
            return self.handle_confirmation(message, context, user)
        
        # Extract product/service preferences
        preferences = extract_product_preferences(message, context.get('preferences', {}))
        
        # Update session preferences
        if preferences:
            session.preference_data = {**session.preference_data, **preferences}
            session.save()
        
        # Determine if looking for product or service
        is_service_query = self.detect_service_query(message)
        
        if is_service_query:
            return self.search_services(message, preferences, user, session, image_data)
        else:
            return self.search_products(message, preferences, user, session, image_data)

    def search_products(self, query, preferences, user, session, image_data=None):
        # Build search query
        search_terms = []
        if image_data:
            search_terms.extend([
                image_data.get('product_type', ''),
                image_data.get('brand', ''),
                image_data.get('color', ''),
                image_data.get('description', '')
            ])
        
        search_terms.append(query)
        combined_query = ' '.join(filter(None, search_terms))
        
        # Search internal database
        products = Products.objects.filter(
            Q(product_name__icontains=combined_query) |
            Q(product_description__icontains=combined_query) |
            Q(product_brand__icontains=combined_query) |
            Q(tags__icontains=combined_query),
            product_status='published'
        )
        
        # Apply preference filters
        if preferences:
            products = filter_products_by_preferences(products, preferences)
        
        # Sort by rating and promotion status
        products = products.annotate(
            avg_rating=Avg('product_ratings__rating')
        ).order_by('-is_promoted', '-is_featured', '-avg_rating', '-created_at')
        
        internal_results = list(products[:5])
        
        if internal_results:
            return self.format_internal_results(internal_results, 'product', preferences, session)
        else:
            # No internal results, check external sources
            return self.get_external_results(combined_query, 'product', preferences)

    def search_services(self, query, preferences, user, session, image_data=None):
        # Search internal services
        services = Services.objects.filter(
            Q(service_name__icontains=query) |
            Q(service_description__icontains=query) |
            Q(provider_expertise__icontains=query) |
            Q(tags__icontains=query),
            service_status='published'
        )
        
        # Apply location filters if specified
        if preferences.get('location'):
            location = preferences['location']
            services = services.filter(
                Q(city__name__icontains=location) |
                Q(state__name__icontains=location) |
                Q(country__name__icontains=location)
            )
        
        services = services.annotate(
            avg_rating=Avg('service_ratings__rating')
        ).order_by('-is_promoted', '-is_featured', '-avg_rating', '-created_at')
        
        internal_results = list(services[:5])
        
        if internal_results:
            return self.format_internal_results(internal_results, 'service', preferences, session)
        else:
            return self.get_external_results(query, 'service', preferences)

    def format_internal_results(self, results, result_type, preferences, session):
        if result_type == 'product':
            formatted_results = format_product_results(results)
        else:
            formatted_results = format_service_results(results)
        
        # Mark session as awaiting confirmation for external sources
        session.awaiting_external_confirmation = True
        session.last_search_query = formatted_results['query']
        session.save()
        
        response = f"Great! I found {len(results)} {result_type}(s) on Finda:\n\n"
        response += formatted_results['formatted_text']
        response += f"\n\n💡 Would you like me to also check external sources for more {result_type} options?"
        
        return response

    def get_external_results(self, query, search_type, preferences):
        try:
            # Use Gemini to get external suggestions
            external_prompt = f"""
            Find {search_type}s matching: {query}
            
            Preferences: {json.dumps(preferences, indent=2)}
            
            Please provide results from popular online stores like Amazon, Jumia, Konga, AliExpress, etc.
            Format the response as if you're accessing their APIs, showing:
            - Product/Service name
            - Price (in appropriate currency)
            - Store/Platform
            - Brief description
            - Availability/Rating if possible
            
            Present maximum 5 results in a user-friendly format.
            """
            
            external_results = send_to_gemini([], external_prompt)
            
            response = f"I couldn't find any {search_type}s matching your criteria in our Finda marketplace. However, I found these options from external sources:\n\n"
            response += external_results
            response += f"\n\n🔍 Want to try a different search or browse our Finda categories?"
            
            return response
            
        except Exception as e:
            return f"Sorry, I couldn't find any {search_type}s matching your criteria at the moment. Please try refining your search or browse our categories."

    def handle_confirmation(self, message, context, user):
        lower_message = message.lower()
        
        # Check for positive confirmation
        if any(word in lower_message for word in ['yes', 'yeah', 'sure', 'okay', 'ok', 'y']):
            # Get external results
            last_query = context.get('last_search_query', 'products')
            return self.get_external_results(last_query, 'product', context.get('preferences', {}))
        
        # Check for negative confirmation
        elif any(word in lower_message for word in ['no', 'nope', 'nah', 'n']):
            return "No problem! Is there anything else you'd like to search for? I'm here to help you find what you need on Finda! 😊"
        
        else:
            # Treat as new query
            return self.process_user_message(message, {}, user, None)

    def handle_browse_request(self):
        try:
            categories = Category.objects.filter(is_active=True, parent=None).order_by('sort_order', 'name')
            
            response = "Here are our main categories on Finda:\n\n"
            
            for category in categories[:10]:
                icon = getattr(category, 'icon', '📁') or "📁"
                subcategories = category.get_children() if hasattr(category, 'get_children') else Category.objects.filter(parent=category)
                subcat_text = f" ({subcategories.count()} subcategories)" if subcategories.exists() else ""
                response += f"{icon} **{category.name}**{subcat_text}\n"
            
            response += "\n💬 Just tell me what you're looking for, or click on any category to explore!"
            return response
        except Exception as e:
            return "Here are some popular categories on Finda:\n\n📱 Electronics\n👕 Fashion\n🏠 Home & Garden\n🚗 Automotive\n📚 Books & Education\n\n💬 Just tell me what you're looking for!"

    def is_greeting(self, message):
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']
        return any(greeting in message for greeting in greetings)

    def is_browse_request(self, message):
        browse_patterns = ['browse', 'categories', 'what do you have', 'show me', 'explore']
        return any(pattern in message for pattern in browse_patterns)

    def detect_service_query(self, message):
        service_keywords = [
            'service', 'services', 'provider', 'professional', 'expert',
            'hire', 'book', 'appointment', 'consultation', 'repair',
            'installation', 'cleaning', 'teaching', 'tutoring',
            'plumber', 'electrician', 'mechanic', 'doctor', 'lawyer'
        ]
        return any(keyword in message.lower() for keyword in service_keywords)


# User Preferences API
class UserPreferencesAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            preferences = UserPreference.objects.get(user=request.user)
            serializer = UserPreferenceSerializer(preferences)
            return Response(serializer.data)
        except UserPreference.DoesNotExist:
            # Return default preferences
            return Response({
                'preferred_categories': [],
                'preferred_price_range': {},
                'preferred_locations': [],
                'preferred_brands': [],
                'preferred_language': 'en',
                'voice_enabled': True,
                'image_search_enabled': True,
                'external_sources_preference': 'ask',
                'response_style': 'casual'
            })
    
    def post(self, request):
        preferences, created = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(preferences, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request):
        preferences, created = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(preferences, data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Chat Feedback API
class ChatFeedbackAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id=None):
        if message_id:
            try:
                chat_message = ChatMessage.objects.get(
                    id=message_id, 
                    session__user=request.user
                )
            except ChatMessage.DoesNotExist:
                return Response({"error": "Message not found"}, status=404)
        else:
            # Get latest message
            chat_message = ChatMessage.objects.filter(
                session__user=request.user
            ).order_by('-timestamp').first()
            
            if not chat_message:
                return Response({"error": "No messages found"}, status=404)
        
        # Create or update feedback
        feedback_data = request.data.copy()
        feedback_data['chat_message'] = chat_message.id
        feedback_data['user'] = request.user.id
        
        try:
            feedback = FeedbackRating.objects.get(
                chat_message=chat_message, 
                user=request.user
            )
            serializer = FeedbackRatingSerializer(feedback, data=feedback_data, partial=True)
        except FeedbackRating.DoesNotExist:
            serializer = FeedbackRatingSerializer(data=feedback_data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Voice Message Processing API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def process_voice_message(request):
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return Response({"error": "No audio file provided"}, status=400)
    
    try:
        # Convert voice to text
        text_result = process_voice_to_text(audio_file)
        
        if text_result:
            return Response({
                "transcribed_text": text_result,
                "success": True
            })
        else:
            return Response({
                "error": "Could not transcribe audio",
                "success": False
            }, status=400)
            
    except Exception as e:
        return Response({
            "error": f"Voice processing failed: {str(e)}",
            "success": False
        }, status=500)


# Image Analysis API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def analyze_product_image_api(request):
    image_file = request.FILES.get('image')
    if not image_file:
        return Response({"error": "No image file provided"}, status=400)
    
    try:
        # Analyze image
        analysis_result = analyze_product_image(image_file)
        
        if analysis_result:
            return Response({
                "analysis": analysis_result,
                "success": True
            })
        else:
            return Response({
                "error": "Could not analyze image",
                "success": False
            }, status=400)
            
    except Exception as e:
        return Response({
            "error": f"Image analysis failed: {str(e)}",
            "success": False
        }, status=500)


# Chat History API
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request, session_id=None):
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id, user=request.user)
            messages = ChatMessage.objects.filter(session=session).order_by('timestamp')
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)
    else:
        # Get all user messages
        messages = ChatMessage.objects.filter(
            session__user=request.user
        ).order_by('timestamp')[:50]
    
    serializer = ChatMessageSerializer(messages, many=True)
    return Response(serializer.data)


# Chat Sessions API
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_sessions_api(request):
    if request.method == 'GET':
        sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')
        serializer = ChatSessionSerializer(sessions, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        session = ChatSession.objects.create(user=request.user)
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# Clear Chat Session API
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_chat_session(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        session.delete()
        return Response({"message": "Session cleared successfully"})
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)


# User Preferences Functions
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_user_preferences(request):
    preferences, created = UserPreference.objects.get_or_create(user=request.user)
    serializer = UserPreferenceSerializer(preferences, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_preferences(request):
    try:
        preferences = UserPreference.objects.get(user=request.user)
        serializer = UserPreferenceSerializer(preferences)
        return Response(serializer.data)
    except UserPreference.DoesNotExist:
        return Response({
            'preferred_categories': [],
            'preferred_price_range': {},
            'preferred_locations': [],
            'preferred_brands': [],
            'preferred_language': 'en',
            'voice_enabled': True,
            'image_search_enabled': True,
            'external_sources_preference': 'ask',
            'response_style': 'casual'
        })


# Analytics APIs
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_analytics_api(request):
    user = request.user
    
    # Calculate analytics
    total_messages = ChatMessage.objects.filter(session__user=user).count()
    total_sessions = ChatSession.objects.filter(user=user).count()
    total_voice_messages = ChatMessage.objects.filter(
        session__user=user, 
        message_type='voice'
    ).count()
    total_image_messages = ChatMessage.objects.filter(
        session__user=user, 
        message_type='image'
    ).count()
    
    # Average session length (messages per session)
    avg_session_length = 0
    if total_sessions > 0:
        avg_session_length = total_messages / total_sessions
    
    # Most searched categories (placeholder)
    most_searched_categories = ['Electronics', 'Fashion', 'Home & Garden']
    
    # User satisfaction score (from feedback)
    satisfaction_score = FeedbackRating.objects.filter(
        chat_message__session__user=user
    ).aggregate(avg_rating=Avg('helpfulness_rating'))['avg_rating'] or 0
    
    # Top external sources (placeholder)
    top_external_sources = ['Amazon', 'Jumia', 'Konga']
    
    analytics_data = {
        'total_messages': total_messages,
        'total_sessions': total_sessions,
        'total_voice_messages': total_voice_messages,
        'total_image_messages': total_image_messages,
        'average_session_length': round(avg_session_length, 2),
        'most_searched_categories': most_searched_categories,
        'user_satisfaction_score': round(satisfaction_score, 2),
        'top_external_sources': top_external_sources
    }
    
    return Response(analytics_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_chat_stats(request):
    user = request.user
    
    # Get last 30 days stats
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    recent_messages = ChatMessage.objects.filter(
        session__user=user,
        timestamp__gte=thirty_days_ago
    )
    
    stats = {
        'messages_last_30_days': recent_messages.count(),
        'sessions_last_30_days': ChatSession.objects.filter(
            user=user,
            created_at__gte=thirty_days_ago
        ).count(),
        'most_active_day': 'Monday',  # Placeholder
        'favorite_search_type': 'products',  # Placeholder
        'average_response_rating': FeedbackRating.objects.filter(
            chat_message__session__user=user
        ).aggregate(avg=Avg('helpfulness_rating'))['avg'] or 0
    }
    
    return Response(stats)


# Advanced Search API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_with_preferences_api(request):
    query = request.data.get('query', '')
    search_type = request.data.get('type', 'product')  # product or service
    
    if not query:
        return Response({"error": "Query is required"}, status=400)
    
    # Get user preferences
    try:
        user_prefs = UserPreference.objects.get(user=request.user)
        preferences = {
            'categories': user_prefs.preferred_categories,
            'price_range': user_prefs.preferred_price_range,
            'locations': user_prefs.preferred_locations,
            'brands': user_prefs.preferred_brands
        }
    except UserPreference.DoesNotExist:
        preferences = {}
    
    if search_type == 'product':
        # Search products
        products = Products.objects.filter(
            Q(product_name__icontains=query) |
            Q(product_description__icontains=query) |
            Q(product_brand__icontains=query),
            product_status='published'
        )
        
        if preferences:
            products = filter_products_by_preferences(products, preferences)
        
        results = products[:10]
        formatted_results = format_product_results(list(results))
        
    else:
        # Search services
        services = Services.objects.filter(
            Q(service_name__icontains=query) |
            Q(service_description__icontains=query),
            service_status='published'
        )
        
        results = services[:10]
        formatted_results = format_service_results(list(results))
    
    return Response({
        'query': query,
        'type': search_type,
        'results_count': len(results),
        'formatted_results': formatted_results.get('formatted_text', ''),
        'preferences_applied': preferences
    })


# Conversation Context APIs
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_context(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        context, created = ConversationContext.objects.get_or_create(session=session)
        serializer = ConversationContextSerializer(context)
        return Response(serializer.data)
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_conversation_context(request, session_id):
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        context, created = ConversationContext.objects.get_or_create(session=session)
        serializer = ConversationContextSerializer(context, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)


# Health Check and Status APIs
@api_view(['GET'])
@permission_classes([AllowAny])
def chatbot_health_check(request):
    """Health check endpoint for monitoring"""
    try:
        # Check database connectivity
        user_count = User.objects.count()
        message_count = ChatMessage.objects.count()
        
        # Check if Gemini is configured
        gemini_configured = bool(getattr(settings, 'GOOGLE_API_KEY', None))
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'connected': True,
                'users': user_count,
                'messages': message_count
            },
            'services': {
                'gemini_configured': gemini_configured,
                'voice_processing': True,  # Placeholder
                'image_analysis': True     # Placeholder
            }
        }
        
        return Response(health_data)
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gemini_status_api(request):
    """Check Gemini API status"""
    try:
        # Test Gemini connection
        test_response = send_to_gemini([], "Hello, are you working?")
        
        return Response({
            'status': 'connected',
            'response_received': bool(test_response),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)


# Webhook endpoints (placeholders for future integration)
@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def process_voice_webhook(request):
    """Webhook for external voice processing services"""
    try:
        data = json.loads(request.body)
        # Process webhook data here
        return JsonResponse({
            'status': 'received',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def image_analysis_webhook(request):
    """Webhook for external image analysis services"""
    try:
        data = json.loads(request.body)
        # Process webhook data here
        return JsonResponse({
            'status': 'received',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)


# Legacy API for backward compatibility
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """Legacy endpoint - redirects to enhanced API"""
    enhanced_api = EnhancedChatAPI()
    return enhanced_api.post(request)


# Custom Authentication Token API
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
                "user_type": getattr(user, 'user_type', 'customer'),
            }
        })


# Message Rating API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rate_message(request, message_id):
    """Rate a specific message"""
    try:
        message = ChatMessage.objects.get(
            id=message_id,
            session__user=request.user
        )
        
        rating = request.data.get('rating')
        feedback_text = request.data.get('feedback', '')
        
        if not rating or not (1 <= int(rating) <= 5):
            return Response({"error": "Rating must be between 1 and 5"}, status=400)
        
        # Update or create feedback
        feedback, created = FeedbackRating.objects.update_or_create(
            chat_message=message,
            user=request.user,
            defaults={
                'helpfulness_rating': int(rating),
                'feedback_text': feedback_text
            }
        )
        
        # Update message user_feedback field
        if int(rating) >= 4:
            message.user_feedback = 'helpful'
        elif int(rating) >= 2:
            message.user_feedback = 'partial'
        else:
            message.user_feedback = 'not_helpful'
        message.save()
        
        return Response({
            'message': 'Rating saved successfully',
            'rating': rating,
            'created': created
        })
        
    except ChatMessage.DoesNotExist:
        return Response({"error": "Message not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# Session Statistics API
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_statistics(request, session_id):
    """Get statistics for a specific session"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        messages = ChatMessage.objects.filter(session=session)
        
        stats = {
            'session_id': str(session.id),
            'total_messages': messages.count(),
            'voice_messages': messages.filter(message_type='voice').count(),
            'image_messages': messages.filter(message_type='image').count(),
            'text_messages': messages.filter(message_type='text').count(),
            'duration_minutes': 0,  # Calculate based on first and last message
            'average_response_time': messages.aggregate(
                avg_time=Avg('response_time_ms')
            )['avg_time'] or 0,
            'user_satisfaction': messages.exclude(
                user_feedback__isnull=True
            ).count(),
            'created_at': session.created_at,
            'last_activity': session.updated_at
        }
        
        # Calculate session duration
        first_message = messages.order_by('timestamp').first()
        last_message = messages.order_by('-timestamp').first()
        
        if first_message and last_message:
            duration = last_message.timestamp - first_message.timestamp
            stats['duration_minutes'] = duration.total_seconds() / 60
        
        return Response(stats)
        
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)


# Export User Data API (GDPR compliance)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_user_data(request):
    """Export all user's chatbot data"""
    user = request.user
    
    # Get all user sessions
    sessions = ChatSession.objects.filter(user=user)
    
    # Get all messages
    messages = ChatMessage.objects.filter(session__user=user)
    
    # Get preferences
    try:
        preferences = UserPreference.objects.get(user=user)
        preferences_data = UserPreferenceSerializer(preferences).data
    except UserPreference.DoesNotExist:
        preferences_data = {}
    
    # Get feedback
    feedback = FeedbackRating.objects.filter(user=user)
    
    export_data = {
        'user_info': {
            'id': user.id,
            'email': user.email,
            'export_date': datetime.now().isoformat()
        },
        'sessions': ChatSessionSerializer(sessions, many=True).data,
        'messages': ChatMessageSerializer(messages, many=True).data,
        'preferences': preferences_data,
        'feedback': FeedbackRatingSerializer(feedback, many=True).data,
        'statistics': {
            'total_sessions': sessions.count(),
            'total_messages': messages.count(),
            'total_feedback': feedback.count()
        }
    }
    
    return Response(export_data)


# Batch Operations API (for admin use)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_message_operations(request):
    """Bulk operations on messages (delete, export, etc.)"""
    if not request.user.is_staff:
        return Response({"error": "Staff access required"}, status=403)
    
    operation = request.data.get('operation')
    message_ids = request.data.get('message_ids', [])
    
    if operation == 'delete':
        deleted_count = ChatMessage.objects.filter(
            id__in=message_ids,
            session__user=request.user
        ).delete()[0]
        
        return Response({
            'operation': 'delete',
            'affected_count': deleted_count
        })
    
    elif operation == 'export':
        messages = ChatMessage.objects.filter(
            id__in=message_ids
        ).values(
            'user_input', 'bot_response', 'timestamp', 
            'message_type', 'user_feedback'
        )
        
        return Response({
            'operation': 'export',
            'data': list(messages)
        })
    
    else:
        return Response({"error": "Invalid operation"}, status=400)