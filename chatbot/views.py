# views.py - WORLD-CLASS AI SHOPPING ASSISTANT
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from io import BytesIO
import logging
import json
import time
from datetime import timedelta

# Import enhanced modules - these should be imported here, not in __init__.py
from .models import ChatMessage, UserVoiceSettings
from .serializers import ChatMessageSerializer, VoiceSettingsSerializer
from .enhanced_conversation_manager import ConversationFlowManager, ConversationAnalytics
from .gemini_client import (
    send_to_gemini, analyze_image_with_gemini, transcribe_audio, 
    generate_voice_response, get_fallback_response
)
from .utils import (
    search_finda_database, format_finda_results, generate_no_results_response,
    search_by_category, format_categories_response, get_trending_items,
    search_products_by_analysis, validate_search_input, log_search_analytics
)
from .external_search_enhanced import (
    search_external_stores, format_external_results, get_price_comparison
)
from .chatbot_prompts import (
    get_system_prompt, get_greeting, detect_user_intent, 
    format_response_template, get_error_message
)

logger = logging.getLogger(__name__)

class CustomAuthToken(ObtainAuthToken):
    """Enhanced authentication with user preferences"""
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data,
                                             context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            
            # Initialize user settings if needed
            voice_settings, _ = UserVoiceSettings.objects.get_or_create(
                user=user,
                defaults={
                    'preferred_language': 'en',
                    'voice_speed': 1.0,
                    'voice_enabled': True
                }
            )
            
            return Response({
                'token': token.key,
                'user_id': user.pk,
                'username': user.username,
                'voice_settings': {
                    'language': voice_settings.preferred_language,
                    'speed': voice_settings.voice_speed,
                    'enabled': voice_settings.voice_enabled
                }
            })
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return Response({
                'error': 'Authentication failed',
                'detail': 'Please check your credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """
    WORLD-CLASS Chat API with comprehensive enhancements
    Handles all text-based conversations with global search integration
    """
    start_time = time.time()
    
    try:
        user = request.user
        user_id = str(user.id)
        
        # Rate limiting
        rate_limit_key = f"chat_rate_limit_{user_id}"
        request_count = cache.get(rate_limit_key, 0)
        
        if request_count >= 60:  # 60 requests per hour
            return Response({
                'error': 'Rate limit exceeded',
                'message': 'Please wait a moment before sending another message.',
                'retry_after': 3600
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        cache.set(rate_limit_key, request_count + 1, timeout=3600)
        
        if request.method == 'GET':
            return get_chat_history(request, user)
        
        # Process POST request
        user_message = request.data.get('message', '').strip()
        
        if not user_message:
            return Response({
                'error': 'Message required',
                'message': 'Please provide a message to continue our conversation.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate input
        is_valid, validated_message = validate_search_input(user_message)
        if not is_valid:
            return Response({
                'error': 'Invalid input',
                'message': 'Please provide a valid search query.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Initialize conversation manager
        conversation_manager = ConversationFlowManager(user_id)
        
        # Log conversation event
        ConversationAnalytics.log_conversation_event(
            user_id, 'message_received', {'message_length': len(user_message)}
        )
        
        # Process message and determine strategy
        strategy = conversation_manager.process_message(user_message)
        
        logger.info(f"🤖 User {user_id} | Intent: {strategy['intent']} | Confidence: {strategy['confidence']}")
        
        # Execute strategy
        response_data = execute_conversation_strategy(
            strategy, user_message, user, conversation_manager
        )
        
        # Generate AI response with context
        ai_response = generate_contextual_ai_response(
            user_message, strategy, response_data, user, conversation_manager
        )
        
        # Store conversation in database
        try:
            with transaction.atomic():
                message_obj = ChatMessage.objects.create(
                    user=user,
                    user_input=user_message[:500],  # Limit input length
                    bot_response=ai_response[:2000],  # Limit response length
                    timestamp=timezone.now()
                )
                
                # Update conversation context
                conversation_manager.add_exchange(user_message, ai_response)
                
        except Exception as db_error:
            logger.error(f"Database storage error: {str(db_error)}")
            # Continue without storing if DB fails
        
        # Log analytics
        ConversationAnalytics.log_conversation_event(
            user_id, 'response_generated', {
                'intent': strategy['intent'],
                'response_length': len(ai_response),
                'processing_time': time.time() - start_time
            }
        )
        
        # Log search analytics if applicable
        if strategy.get('search_terms'):
            results_count = len(response_data.get('finda_results', []))
            log_search_analytics(strategy['search_terms'], results_count, user_id)
        
        return Response({
            'response': ai_response,
            'intent': strategy['intent'],
            'confidence': strategy['confidence'],
            'context_aware': strategy['context_aware'],
            'finda_results': response_data.get('finda_results', []),
            'external_results': response_data.get('external_results', []),
            'categories': response_data.get('categories', []),
            'suggestions': response_data.get('suggestions', []),
            'processing_time': round(time.time() - start_time, 2),
            'message_id': getattr(message_obj, 'id', None)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Chat API error: {str(e)}")
        
        # Fallback response
        fallback_response = get_fallback_response('default')
        
        return Response({
            'response': fallback_response,
            'intent': 'error_recovery',
            'confidence': 0.1,
            'error': 'Technical issue occurred',
            'processing_time': round(time.time() - start_time, 2)
        }, status=status.HTTP_200_OK)


def execute_conversation_strategy(strategy, user_message, user, conversation_manager):
    """
    Execute the determined conversation strategy with comprehensive error handling
    """
    response_data = {
        'finda_results': [],
        'external_results': [],
        'categories': [],
        'suggestions': [],
        'selected_item': None
    }
    
    try:
        intent = strategy['intent']
        
        # CORE STRATEGY: Database-first approach
        if intent == 'perform_finda_search':
            search_terms = strategy.get('search_terms', user_message)
            logger.info(f"🔍 Performing Finda search: '{search_terms}'")
            
            # Search Finda database first (PRIORITY)
            finda_results = search_finda_database(search_terms, limit=8)
            response_data['finda_results'] = finda_results
            
            # Update conversation context
            conversation_manager.update_after_search(search_terms, finda_results)
            
            if not finda_results:
                # Try category-based search as fallback
                category_results = search_by_category(search_terms, limit=5)
                response_data['finda_results'] = category_results
        
        elif intent == 'show_categories':
            from main.models import Category
            try:
                categories = Category.objects.filter(
                    is_active=True, parent=None
                ).order_by('sort_order', 'name')[:15]
                response_data['categories'] = list(categories)
                conversation_manager.update_after_categories(categories)
            except Exception as cat_error:
                logger.error(f"Categories error: {str(cat_error)}")
        
        elif intent == 'search_category':
            selected_category = strategy.get('selected_category', user_message)
            category_results = search_by_category(selected_category, limit=8)
            response_data['finda_results'] = category_results
            conversation_manager.update_after_search(selected_category, category_results)
        
        elif intent == 'perform_external_search':
            # Only perform external search when explicitly requested
            search_terms = strategy.get('search_terms') or strategy['context_data'].get('last_search_query', user_message)
            logger.info(f"🌐 Performing EXTERNAL search: '{search_terms}'")
            
            try:
                external_results = search_external_stores(search_terms, limit=5)
                response_data['external_results'] = external_results
                
                # Also get price comparison if Finda results exist
                finda_results = strategy['context_data'].get('last_search_results', [])
                if finda_results:
                    price_comparison = get_price_comparison(finda_results, external_results)
                    response_data['price_comparison'] = price_comparison
                    
            except Exception as ext_error:
                logger.error(f"External search error: {str(ext_error)}")
                response_data['external_results'] = []
        
        elif intent == 'show_item_details':
            selected_item = strategy.get('selected_item')
            if selected_item:
                response_data['selected_item'] = selected_item
        
        elif intent == 'get_trending':
            trending_items = get_trending_items(limit=6)
            response_data['finda_results'] = trending_items
        
        # Set external search as pending if user declined
        elif intent == 'decline_external_search':
            conversation_manager.clear_context()
        
        # Set up external search if user wants it
        elif intent in ['request_external_search', 'confirm_external_search']:
            search_query = strategy['context_data'].get('last_search_query', user_message)
            conversation_manager.set_external_pending(search_query)
            
            # Actually perform the search
            try:
                external_results = search_external_stores(search_query, limit=6)
                response_data['external_results'] = external_results
            except Exception as ext_error:
                logger.error(f"External search execution error: {str(ext_error)}")
        
        return response_data
        
    except Exception as e:
        logger.error(f"Strategy execution error: {str(e)}")
        return response_data


def generate_contextual_ai_response(user_message, strategy, response_data, user, conversation_manager):
    """
    Generate AI response using Gemini with context and enhanced prompts
    """
    try:
        intent = strategy['intent']
        
        # Prepare context for AI
        context_info = ""
        
        # Include Finda results in context
        if response_data.get('finda_results'):
            results_summary = []
            for i, item in enumerate(response_data['finda_results'][:5], 1):
                try:
                    is_product = hasattr(item, 'product_name')
                    name = getattr(item, 'product_name' if is_product else 'service_name', 'Item')
                    price = getattr(item, 'product_price' if is_product else 'starting_price', 0)
                    location = item.get_full_location() if hasattr(item, 'get_full_location') else 'Available'
                    results_summary.append(f"{i}. {name} - ₦{price:,.2f} - {location}")
                except Exception as item_error:
                    logger.error(f"Item formatting error: {str(item_error)}")
                    continue
            
            if results_summary:
                context_info += f"\nFINDA SEARCH RESULTS for '{strategy.get('search_terms', user_message)}':\n"
                context_info += "\n".join(results_summary)
                context_info += f"\n\nTotal: {len(response_data['finda_results'])} items found on Finda marketplace."
        
        # Include external results in context if available
        if response_data.get('external_results'):
            context_info += f"\n\nEXTERNAL SEARCH RESULTS (as bonus options):\n"
            ext_summary = []
            for i, item in enumerate(response_data['external_results'][:3], 1):
                try:
                    name = item.get('name', 'Item')
                    price = item.get('price', 'Price available')
                    source = item.get('source', 'External store')
                    ext_summary.append(f"{i}. {name} - {price} - {source}")
                except:
                    continue
            context_info += "\n".join(ext_summary)
        
        # Include categories in context
        if response_data.get('categories'):
            cat_names = []
            for cat in response_data['categories'][:10]:
                try:
                    cat_names.append(getattr(cat, 'name', str(cat)))
                except:
                    continue
            if cat_names:
                context_info += f"\n\nAVAILABLE CATEGORIES: {', '.join(cat_names)}"
        
        # Get appropriate system prompt based on intent
        if intent in ['perform_external_search', 'request_external_search', 'confirm_external_search']:
            system_prompt = get_system_prompt('external')
        else:
            system_prompt = get_system_prompt('main')
        
        # Build conversation history for context
        conversation_history = []
        
        # Add system prompt as first message
        conversation_history.append({
            "author": "assistant",
            "content": system_prompt
        })
        
        # Add context information if available
        if context_info:
            conversation_history.append({
                "author": "assistant", 
                "content": f"CONTEXT: {context_info.strip()}"
            })
        
        # Add recent conversation history from context
        recent_history = strategy.get('context_data', {}).get('conversation_history', [])
        for exchange in recent_history[-3:]:  # Last 3 exchanges
            try:
                conversation_history.append({
                    "author": "user",
                    "content": exchange.get('user', '')
                })
                conversation_history.append({
                    "author": "assistant", 
                    "content": exchange.get('bot', '')
                })
            except:
                continue
        
        # Generate enhanced user message with intent context
        enhanced_message = user_message
        
        if intent == 'perform_finda_search' and response_data.get('finda_results'):
            enhanced_message = f"User searched for: '{strategy.get('search_terms', user_message)}'. Show the Finda results enthusiastically and offer external search as bonus option."
        elif intent == 'perform_external_search':
            enhanced_message = f"User wants external search results for: '{strategy.get('search_terms', user_message)}'. Show external results but remind them Finda is better for local shopping."
        elif intent == 'show_categories':
            enhanced_message = "User wants to browse categories. Show them available categories enthusiastically."
        elif intent == 'decline_external_search':
            enhanced_message = "User declined external search and wants to stick with Finda. Praise their choice and ask what else they need."
        
        # Send to Gemini AI
        try:
            ai_response = send_to_gemini(conversation_history, enhanced_message, max_retries=3)
            
            if ai_response and len(ai_response.strip()) > 10:
                return ai_response
            else:
                raise Exception("AI response too short or empty")
                
        except Exception as ai_error:
            logger.error(f"Gemini API error: {str(ai_error)}")
            
            # Generate fallback response based on intent and data
            return generate_intelligent_fallback(intent, response_data, user_message, strategy)
        
    except Exception as e:
        logger.error(f"AI response generation error: {str(e)}")
        return generate_intelligent_fallback(intent, response_data, user_message, strategy)


def generate_intelligent_fallback(intent, response_data, user_message, strategy):
    """
    Generate intelligent fallback responses when AI is unavailable
    """
    try:
        if intent == 'perform_finda_search':
            if response_data.get('finda_results'):
                formatted_results = format_finda_results(
                    response_data['finda_results'], 
                    strategy.get('search_terms', user_message)
                )
                if formatted_results:
                    return formatted_results
            else:
                return generate_no_results_response(strategy.get('search_terms', user_message))
        
        elif intent == 'show_categories':
            return format_categories_response()
        
        elif intent == 'perform_external_search':
            if response_data.get('external_results'):
                return format_external_results(
                    response_data['external_results'],
                    strategy.get('search_terms', user_message)
                )
            else:
                return "I'm checking external stores but having connectivity issues. Let's focus on our amazing Finda marketplace instead! What can I find for you?"
        
        elif intent == 'decline_external_search':
            return "Perfect choice! Staying with Finda means faster delivery, direct seller contact, and supporting local businesses. What else can I help you find? 🛍️"
        
        elif intent == 'greeting':
            return get_greeting('first_time_user')
        
        elif intent == 'thanks':
            return "You're very welcome! I'm always here to help you find the best deals on Finda. What else can I assist you with? 😊"
        
        else:
            return "I'm here to help you find amazing products and services on Finda! Try searching for specific items, browsing categories, or asking me anything about our marketplace. What are you looking for today? 🛍️"
            
    except Exception as e:
        logger.error(f"Fallback generation error: {str(e)}")
        return "I'm your Finda shopping assistant! Search for products, browse categories, or ask me anything. What can I help you find today?"


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def voice_chat_api(request):
    """
    ENHANCED Voice Chat API with comprehensive audio processing
    """
    start_time = time.time()
    
    try:
        user = request.user
        audio_file = request.FILES.get('audio')
        
        if not audio_file:
            return Response({
                'error': 'Audio file required',
                'message': 'Please provide an audio file for voice chat.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"🎤 Processing voice message from user {user.id}")
        
        # Rate limiting for voice
        rate_limit_key = f"voice_rate_limit_{user.id}"
        request_count = cache.get(rate_limit_key, 0)
        
        if request_count >= 20:  # 20 voice messages per hour
            return Response({
                'error': 'Voice rate limit exceeded',
                'message': 'Please wait before sending another voice message.',
                'retry_after': 3600
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        cache.set(rate_limit_key, request_count + 1, timeout=3600)
        
        # Transcribe audio
        try:
            transcript = transcribe_audio(audio_file)
            
            if not transcript:
                return Response({
                    'error': 'Transcription failed',
                    'message': 'Could not understand the audio. Please try speaking clearly or use text instead.',
                    'voice_response_url': None
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as transcribe_error:
            logger.error(f"Transcription error: {str(transcribe_error)}")
            return Response({
                'error': 'Audio processing failed',
                'message': 'Technical issue processing your voice message. Please try again or use text.',
                'voice_response_url': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.info(f"🎤 Transcribed: '{transcript}'")
        
        # Process the transcribed message using regular chat logic
        conversation_manager = ConversationFlowManager(str(user.id))
        strategy = conversation_manager.process_message(transcript)
        
        # Execute strategy
        response_data = execute_conversation_strategy(
            strategy, transcript, user, conversation_manager
        )
        
        # Generate AI response
        ai_response = generate_contextual_ai_response(
            transcript, strategy, response_data, user, conversation_manager
        )
        
        # Generate voice response
        voice_response_url = None
        try:
            user_settings = UserVoiceSettings.objects.get(user=user)
            if user_settings.voice_enabled:
                voice_response_url = generate_voice_response(
                    ai_response, 
                    language=user_settings.preferred_language,
                    slow=(user_settings.voice_speed < 1.0)
                )
        except UserVoiceSettings.DoesNotExist:
            # Create default settings
            UserVoiceSettings.objects.create(user=user)
            voice_response_url = generate_voice_response(ai_response)
        except Exception as voice_error:
            logger.error(f"Voice generation error: {str(voice_error)}")
        
        # Store in database
        try:
            with transaction.atomic():
                message_obj = ChatMessage.objects.create(
                    user=user,
                    user_input=transcript[:500],
                    bot_response=ai_response[:2000],
                    is_voice_message=True,
                    audio_file=audio_file,
                    transcript=transcript,
                    voice_response_url=voice_response_url or '',
                    timestamp=timezone.now()
                )
                
                conversation_manager.add_exchange(transcript, ai_response)
                
        except Exception as db_error:
            logger.error(f"Voice message DB storage error: {str(db_error)}")
        
        return Response({
            'transcript': transcript,
            'response': ai_response,
            'voice_response_url': voice_response_url,
            'intent': strategy['intent'],
            'confidence': strategy['confidence'],
            'finda_results': response_data.get('finda_results', []),
            'processing_time': round(time.time() - start_time, 2),
            'message_id': getattr(message_obj, 'id', None)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Voice chat API error: {str(e)}")
        return Response({
            'error': 'Voice processing failed',
            'message': 'Technical issue with voice processing. Please try text chat.',
            'processing_time': round(time.time() - start_time, 2)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def image_search_api(request):
    """
    ENHANCED Image Search API with comprehensive image analysis
    """
    start_time = time.time()
    
    try:
        user = request.user
        image_file = request.FILES.get('image')
        user_query = request.data.get('query', 'What products are in this image?')
        
        if not image_file:
            return Response({
                'error': 'Image file required',
                'message': 'Please provide an image file for visual search.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"📸 Processing image search from user {user.id}")
        
        # Rate limiting for images
        rate_limit_key = f"image_rate_limit_{user.id}"
        request_count = cache.get(rate_limit_key, 0)
        
        if request_count >= 10:  # 10 image searches per hour
            return Response({
                'error': 'Image rate limit exceeded',
                'message': 'Please wait before uploading another image.',
                'retry_after': 3600
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        cache.set(rate_limit_key, request_count + 1, timeout=3600)
        
        # Analyze image with Gemini Vision
        try:
            analysis_result = analyze_image_with_gemini(image_file, user_query)
            
            if not analysis_result or len(analysis_result.strip()) < 10:
                return Response({
                    'error': 'Image analysis failed',
                    'message': 'Could not analyze the image. Please try a clearer image or describe what you\'re looking for.',
                    'analysis': None,
                    'finda_results': []
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as analysis_error:
            logger.error(f"Image analysis error: {str(analysis_error)}")
            return Response({
                'error': 'Image processing failed',
                'message': 'Technical issue analyzing your image. Please try again or use text search.',
                'analysis': None,
                'finda_results': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.info(f"📸 Image analysis completed: {analysis_result[:100]}...")
        
        # Search Finda database based on analysis
        finda_results = search_products_by_analysis(analysis_result, limit=6)
        
        # Initialize conversation manager and update context
        conversation_manager = ConversationFlowManager(str(user.id))
        
        if finda_results:
            conversation_manager.update_after_search("image search", finda_results)
        
        # Generate contextual response
        enhanced_query = f"User uploaded an image. Analysis: {analysis_result}. Found {len(finda_results)} matching items on Finda."
        
        strategy = {
            'intent': 'image_search_response',
            'confidence': 0.9,
            'context_aware': True,
            'search_terms': None
        }
        
        response_data = {'finda_results': finda_results}
        
        ai_response = generate_contextual_ai_response(
            enhanced_query, strategy, response_data, user, conversation_manager
        )
        
        # Store in database
        try:
            with transaction.atomic():
                message_obj = ChatMessage.objects.create(
                    user=user,
                    user_input=f"Image search: {user_query}",
                    bot_response=ai_response[:2000],
                    is_image_message=True,
                    image_file=image_file,
                    image_analysis=analysis_result[:1000],
                    timestamp=timezone.now()
                )
                
                conversation_manager.add_exchange("image search", ai_response)
                
        except Exception as db_error:
            logger.error(f"Image message DB storage error: {str(db_error)}")
        
        return Response({
            'analysis': analysis_result,
            'response': ai_response,
            'finda_results': finda_results,
            'search_suggestions': [],  # Could add image-based suggestions
            'processing_time': round(time.time() - start_time, 2),
            'message_id': getattr(message_obj, 'id', None)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Image search API error: {str(e)}")
        return Response({
            'error': 'Image search failed',
            'message': 'Technical issue with image search. Please try text search instead.',
            'processing_time': round(time.time() - start_time, 2),
            'analysis': None,
            'finda_results': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def voice_settings_api(request):
    """
    Enhanced Voice Settings API
    """
    try:
        user = request.user
        
        if request.method == 'GET':
            try:
                settings = UserVoiceSettings.objects.get(user=user)
                serializer = VoiceSettingsSerializer(settings)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except UserVoiceSettings.DoesNotExist:
                # Create default settings
                settings = UserVoiceSettings.objects.create(user=user)
                serializer = VoiceSettingsSerializer(settings)
                return Response(serializer.data, status=status.HTTP_200_OK)
        
        elif request.method == 'PUT':
            try:
                settings, created = UserVoiceSettings.objects.get_or_create(user=user)
                serializer = VoiceSettingsSerializer(settings, data=request.data, partial=True)
                
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as save_error:
                logger.error(f"Voice settings save error: {str(save_error)}")
                return Response({
                    'error': 'Settings update failed',
                    'message': 'Could not update voice settings.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Voice settings API error: {str(e)}")
        return Response({
            'error': 'Voice settings error',
            'message': 'Technical issue with voice settings.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_chat_history(request, user):
    """
    Enhanced chat history with pagination and filtering
    """
    try:
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 20)), 50)  # Max 50 per page
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get messages with filters
        messages = ChatMessage.objects.filter(user=user).order_by('-timestamp')
        
        # Apply date filter if provided
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from:
            try:
                from django.utils.dateparse import parse_date
                date_from_parsed = parse_date(date_from)
                if date_from_parsed:
                    messages = messages.filter(timestamp__gte=date_from_parsed)
            except:
                pass
        
        if date_to:
            try:
                from django.utils.dateparse import parse_date
                date_to_parsed = parse_date(date_to)
                if date_to_parsed:
                    messages = messages.filter(timestamp__lte=date_to_parsed)
            except:
                pass
        
        # Get total count
        total_count = messages.count()
        
        # Get paginated results
        paginated_messages = messages[offset:offset + page_size]
        
        # Serialize messages
        serializer = ChatMessageSerializer(paginated_messages, many=True)
        
        return Response({
            'messages': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Chat history error: {str(e)}")
        return Response({
            'error': 'History retrieval failed',
            'messages': [],
            'pagination': {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_chat_history(request):
    """
    Clear chat history and conversation context
    """
    try:
        user = request.user
        user_id = str(user.id)
        
        # Clear database messages
        deleted_count, _ = ChatMessage.objects.filter(user=user).delete()
        
        # Clear conversation context
        conversation_manager = ConversationFlowManager(user_id)
        conversation_manager.clear_context()
        
        # Clear cache
        cache_keys = [
            f"conversation_context_{user_id}",
            f"conversation_events_{user_id}",
            f"search_results_{user_id}"
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        logger.info(f"Cleared {deleted_count} messages for user {user_id}")
        
        return Response({
            'message': f'Successfully cleared {deleted_count} messages and conversation context.',
            'deleted_count': deleted_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Clear history error: {str(e)}")
        return Response({
            'error': 'Failed to clear history',
            'message': 'Technical issue clearing chat history.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_feedback(request):
    """
    Submit user feedback on bot responses
    """
    try:
        user = request.user
        message_id = request.data.get('message_id')
        rating = request.data.get('rating')  # 1-5 stars
        feedback_text = request.data.get('feedback', '').strip()
        
        if not message_id:
            return Response({
                'error': 'Message ID required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate rating
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({
                'error': 'Rating must be between 1 and 5'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if message exists and belongs to user
        try:
            message = ChatMessage.objects.get(id=message_id, user=user)
        except ChatMessage.DoesNotExist:
            return Response({
                'error': 'Message not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Store feedback (you might want to create a Feedback model)
        feedback_data = {
            'user_id': str(user.id),
            'message_id': message_id,
            'rating': rating,
            'feedback': feedback_text[:500],  # Limit feedback length
            'timestamp': timezone.now().isoformat()
        }
        
        # Store in cache for now (implement proper model later)
        feedback_key = f"feedback_{message_id}"
        cache.set(feedback_key, feedback_data, timeout=86400 * 30)  # 30 days
        
        # Log analytics
        ConversationAnalytics.log_conversation_event(
            str(user.id), 'feedback_submitted', {
                'rating': rating,
                'has_text_feedback': bool(feedback_text),
                'message_id': message_id
            }
        )
        
        logger.info(f"Feedback submitted: User {user.id}, Message {message_id}, Rating {rating}")
        
        return Response({
            'message': 'Thank you for your feedback!',
            'feedback_id': feedback_key
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Feedback submission error: {str(e)}")
        return Response({
            'error': 'Feedback submission failed',
            'message': 'Technical issue submitting feedback.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def health_check(request):
    """
    System health check endpoint
    """
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'services': {}
        }
        
        # Check database
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status['services']['database'] = 'healthy'
        except Exception as db_error:
            health_status['services']['database'] = f'unhealthy: {str(db_error)}'
            health_status['status'] = 'degraded'
        
        # Check cache
        try:
            cache.set('health_check', 'test', timeout=60)
            cache.get('health_check')
            health_status['services']['cache'] = 'healthy'
        except Exception as cache_error:
            health_status['services']['cache'] = f'unhealthy: {str(cache_error)}'
            health_status['status'] = 'degraded'
        
        # Check AI service
        try:
            from .gemini_client import test_gemini_connection
            ai_healthy, ai_message = test_gemini_connection()
            if ai_healthy:
                health_status['services']['ai'] = 'healthy'
            else:
                health_status['services']['ai'] = f'unhealthy: {ai_message}'
                health_status['status'] = 'degraded'
        except Exception as ai_error:
            health_status['services']['ai'] = f'unhealthy: {str(ai_error)}'
            health_status['status'] = 'degraded'
        
        # Check file storage
        try:
            from django.core.files.storage import default_storage
            test_file_name = 'health_check_test.txt'
            default_storage.save(test_file_name, BytesIO(b'test'))
            default_storage.delete(test_file_name)
            health_status['services']['storage'] = 'healthy'
        except Exception as storage_error:
            health_status['services']['storage'] = f'unhealthy: {str(storage_error)}'
            health_status['status'] = 'degraded'
        
        status_code = status.HTTP_200_OK if health_status['status'] in ['healthy', 'degraded'] else status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(health_status, status=status_code)
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_search_suggestions(request):
    """
    Get search suggestions based on partial query
    """
    try:
        query = request.GET.get('q', '').strip()
        limit = min(int(request.GET.get('limit', 10)), 20)
        
        if len(query) < 2:
            return Response({
                'suggestions': [],
                'message': 'Query too short for suggestions'
            }, status=status.HTTP_200_OK)
        
        from .utils import get_search_suggestions
        suggestions = get_search_suggestions(query)[:limit]
        
        return Response({
            'suggestions': suggestions,
            'query': query,
            'count': len(suggestions)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Search suggestions error: {str(e)}")
        return Response({
            'suggestions': [],
            'error': 'Failed to get suggestions'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated]) 
def conversation_analytics(request):
    """
    Get conversation analytics for the user
    """
    try:
        user = request.user
        user_id = str(user.id)
        
        # Get conversation insights
        insights = ConversationAnalytics.get_conversation_insights(user_id)
        
        # Get conversation summary from context
        conversation_manager = ConversationFlowManager(user_id)
        summary = conversation_manager.context.get_conversation_summary() if conversation_manager.context else {}
        
        # Get message statistics
        try:
            total_messages = ChatMessage.objects.filter(user=user).count()
            voice_messages = ChatMessage.objects.filter(user=user, is_voice_message=True).count()
            image_messages = ChatMessage.objects.filter(user=user, is_image_message=True).count()
            
            # Recent activity (last 7 days)
            from datetime import timedelta
            week_ago = timezone.now() - timedelta(days=7)
            recent_messages = ChatMessage.objects.filter(
                user=user, 
                timestamp__gte=week_ago
            ).count()
            
        except Exception as stats_error:
            logger.error(f"Message stats error: {str(stats_error)}")
            total_messages = voice_messages = image_messages = recent_messages = 0
        
        analytics_data = {
            'user_stats': {
                'total_messages': total_messages,
                'voice_messages': voice_messages,
                'image_messages': image_messages,
                'recent_activity': recent_messages
            },
            'conversation_insights': insights,
            'session_summary': summary,
            'preferences': {
                'preferred_interaction': 'text',  # Could be enhanced
                'active_sessions': 1
            }
        }
        
        return Response(analytics_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return Response({
            'error': 'Analytics unavailable',
            'user_stats': {},
            'conversation_insights': {},
            'session_summary': {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quick_search(request):
    """
    Quick search endpoint for instant results
    """
    try:
        query = request.data.get('query', '').strip()
        category = request.data.get('category', '').strip()
        limit = min(int(request.data.get('limit', 5)), 10)
        
        if not query and not category:
            return Response({
                'error': 'Query or category required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate input
        is_valid, validated_query = validate_search_input(query)
        if query and not is_valid:
            return Response({
                'error': 'Invalid search query'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        results = []
        
        if category:
            from .utils import search_by_category
            results = search_by_category(category, limit)
        elif query:
            results = search_finda_database(validated_query, limit)
        
        # Format results for API response
        formatted_results = []
        for item in results:
            try:
                is_product = hasattr(item, 'product_name')
                formatted_item = {
                    'id': item.id,
                    'name': getattr(item, 'product_name' if is_product else 'service_name'),
                    'type': 'product' if is_product else 'service',
                    'price': str(getattr(item, 'product_price' if is_product else 'starting_price', 0)),
                    'location': item.get_full_location() if hasattr(item, 'get_full_location') else '',
                    'rating': item.average_rating() if hasattr(item, 'average_rating') else 0,
                    'url': item.get_absolute_url() if hasattr(item, 'get_absolute_url') else '',
                    'image': getattr(item, 'product_image', getattr(item, 'service_image', None))
                }
                formatted_results.append(formatted_item)
            except Exception as format_error:
                logger.error(f"Result formatting error: {str(format_error)}")
                continue
        
        return Response({
            'results': formatted_results,
            'query': query,
            'category': category,
            'count': len(formatted_results),
            'total_available': len(results)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Quick search error: {str(e)}")
        return Response({
            'error': 'Search failed',
            'results': [],
            'count': 0
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)