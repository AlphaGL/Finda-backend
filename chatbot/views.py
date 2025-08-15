# ai_chatbot/views.py
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.core.cache import cache
from django.conf import settings
from django.db import transaction

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    ChatSession, ChatMessage, SearchQuery, SearchResult, 
    UserFeedback, ChatAnalytics, BotConfiguration
)
from .serializers import (
    ChatSessionSerializer, ChatMessageSerializer, UserFeedbackSerializer,
    ChatMessageRequestSerializer, ChatMessageResponseSerializer,
    QuickSearchRequestSerializer, QuickSearchResponseSerializer,
    FeedbackRequestSerializer, ChatAnalyticsSerializer,
    BotConfigurationSerializer
)
from .services.smart_router import SmartChatbotRouter
from .utils import ChatSessionManager, ChatAnalyticsManager
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class ChatInterfaceView(TemplateView):
    """Main chat interface view"""
    template_name = 'ai_chatbot/chat_interface.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'AI Shopping Assistant',
            'websocket_url': self._get_websocket_url(),
            'supported_languages': self._get_supported_languages(),
            'max_file_size_mb': getattr(settings, 'CHATBOT_SETTINGS', {}).get('MAX_FILE_SIZE_MB', 10)
        })
        return context
    
    def _get_websocket_url(self):
        """Get WebSocket URL for real-time chat"""
        scheme = 'wss' if self.request.is_secure() else 'ws'
        host = self.request.get_host()
        return f"{scheme}://{host}/ws/chat/"
    
    def _get_supported_languages(self):
        """Get supported languages for the chat"""
        return {
            'en': 'English',
            'fr': 'French', 
            'es': 'Spanish',
            'de': 'German',
            'pt': 'Portuguese'
        }


@method_decorator(csrf_exempt, name='dispatch')
class ChatAPIView(View):
    """Main chatbot API endpoint with async support"""
    
    def __init__(self):
        super().__init__()
        self.router = SmartChatbotRouter()
        self.session_manager = ChatSessionManager()
        self.analytics = ChatAnalyticsManager()
    
    def get(self, request):
        """Handle GET requests - return API info"""
        return JsonResponse({
            'success': True,
            'message': 'AI Chatbot API is running',
            'endpoints': {
                'chat': 'POST /chatbot/api/chat/ - Send chat messages',
                'methods': ['POST'],
                'supported_types': ['text', 'image', 'voice']
            },
            'version': '1.0.0'
        })
    
    def post(self, request):
        """Handle POST requests synchronously but run async operations"""
        try:
            # Parse request data
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST.dict()
            
            message_text = data.get('message', '').strip()
            message_type = data.get('message_type', 'text')
            session_id = data.get('session_id')
            file_data = request.FILES.get('file') if message_type in ['image', 'voice'] else None
            
            # Validate input
            if not message_text and not file_data:
                return JsonResponse({
                    'success': False,
                    'error': 'Message text or file is required',
                    'response': 'Please provide a message.'
                }, status=400)
            
            # Log the incoming request
            logger.info(f"Processing chat request: '{message_text}' (type: {message_type})")
            
            # Run the async processing
            result = asyncio.run(self._process_chat_async(
                request, message_text, message_type, session_id, file_data, data
            ))
            
            # Log the result
            logger.info(f"Chat processing complete. Response length: {len(result.get('response', ''))}")
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data',
                'response': 'Invalid request format.'
            }, status=400)
        
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred while processing your message',
                'response': 'I apologize, but I encountered an error. Please try again.',
                'timestamp': datetime.now().isoformat()
            }, status=500)
    
    async def _process_chat_async(self, request, message_text, message_type, session_id, file_data, data):
        """Process chat message asynchronously"""
        try:
            # Get or create chat session
            chat_session = await self._get_or_create_session(request, session_id)
            
            # Save user message
            user_message = await self._save_user_message(
                chat_session, message_text, message_type, file_data
            )
            
            # Build context
            context = await self._build_conversation_context(chat_session, request)
            
            # Process with router
            processing_result = await self.router.process_message(
                message_text, context
            )
            
            # DEBUG: Log the processing result structure
            logger.info(f"DEBUG: Processing result keys: {list(processing_result.keys())}")
            logger.info(f"DEBUG: Search results structure: {processing_result.get('search_results', 'NOT FOUND')}")
            
            # Save bot response
            bot_message = await self._save_bot_response(
                chat_session, processing_result, user_message
            )
            
            # Update analytics
            await self._update_analytics(processing_result, chat_session)
            
            # Get the final response
            final_response_text = processing_result.get('response', processing_result.get('final_response', ''))
            
            # FIXED: Extract search results correctly based on SmartChatbotRouter structure
            search_results = processing_result.get('search_results', {})
            
            # Handle both possible structures
            if 'local' in search_results and 'external' in search_results:
                # New structure from SmartChatbotRouter
                local_results = search_results.get('local', {})
                external_results = search_results.get('external', {})
            else:
                # Fallback to old structure
                local_results = processing_result.get('local_results', {})
                external_results = processing_result.get('external_results', {})
            
            # DEBUG: Log what we extracted
            logger.info(f"DEBUG: Extracted local results: products={len(local_results.get('products', []))}, services={len(local_results.get('services', []))}")
            logger.info(f"DEBUG: Extracted external results: products={len(external_results.get('products', []))}, services={len(external_results.get('services', []))}")
            
            # Prepare response data
            response_data = {
                'success': processing_result.get('success', True),
                'message_id': str(bot_message.id),
                'session_id': str(chat_session.session_id),
                'response': final_response_text,
                'message_type': 'text',
                'metadata': {
                    'processing_time': processing_result.get('processing_time', 0),
                    'search_strategy': processing_result.get('search_strategy', 'unknown'),
                    'confidence_score': processing_result.get('intent', {}).get('confidence', 0),
                    'services_used': processing_result.get('metadata', {}).get('services_used', []),
                    'has_external_results': len(external_results.get('services', [])) + len(external_results.get('products', [])) > 0
                },
                'search_results': {
                    'local': {
                        'products': local_results.get('products', [])[:5],
                        'services': local_results.get('services', [])[:5],
                        'total': local_results.get('total', local_results.get('total_results', 0))
                    },
                    'external': {
                        'products': external_results.get('products', [])[:5],
                        'services': external_results.get('services', [])[:5],
                        'total': external_results.get('total', external_results.get('total_found', 0))
                    }
                },
                'suggested_actions': await self._generate_suggested_actions(processing_result),
                'timestamp': datetime.now().isoformat()
            }
            
            # DEBUG: Log final response structure
            logger.info(f"DEBUG: Final response - external total: {response_data['search_results']['external']['total']}")
            logger.info(f"DEBUG: Final response - external services count: {len(response_data['search_results']['external']['services'])}")
            
            # Add TTS if requested
            if data.get('enable_tts', False):
                response_data['tts_audio'] = await self._generate_tts_response(final_response_text)
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error in async processing: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': 'I apologize, but I encountered an error while processing your request.',
                'timestamp': datetime.now().isoformat()
            }

    @sync_to_async
    def _get_or_create_session(self, request, session_id):
        """Get existing session or create new one"""
        if session_id:
            try:
                session = ChatSession.objects.select_related('user').get(
                    session_id=session_id,
                    status='active'
                )
                session.last_activity = datetime.now()
                session.save()
                return session
            except ChatSession.DoesNotExist:
                pass
        
        # Create new session
        session_data = {
            'session_id': self.session_manager.generate_session_id(),
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'device_info': self._extract_device_info(request)
        }
        
        if request.user.is_authenticated:
            session_data['user'] = request.user
        
        return ChatSession.objects.create(**session_data)

    @sync_to_async
    def _save_user_message(self, session, message, message_type, file_data=None):
        """Save user message to database"""
        message_data = {
            'chat_session': session,
            'sender_type': 'user',
            'message_type': message_type,
            'content': message,
            'context_data': {}
        }
        
        if file_data and message_type == 'image':
            message_data['image'] = file_data
        elif file_data and message_type == 'voice':
            message_data['voice_file'] = file_data
        
        return ChatMessage.objects.create(**message_data)

    @sync_to_async
    def _save_bot_response(self, session, processing_result, user_message):
        """Save bot response to database"""
        # Handle search data saving
        if processing_result.get('search_results') or processing_result.get('local_results') or processing_result.get('external_results'):
            self._save_search_data_sync(processing_result, user_message)
        
        # Extract search results for counting
        search_results = processing_result.get('search_results', {})
        local_results = search_results.get('local', processing_result.get('local_results', {}))
        external_results = search_results.get('external', processing_result.get('external_results', {}))
        
        total_results = (
            local_results.get('total', local_results.get('total_results', 0)) +
            external_results.get('total', external_results.get('total_found', 0))
        )
        
        bot_message_data = {
            'chat_session': session,
            'sender_type': 'bot',
            'message_type': 'text',
            'content': processing_result.get('response', processing_result.get('final_response', '')),
            'search_mode': processing_result.get('search_strategy', 'unknown'),
            'response_time': processing_result.get('processing_time', 0),
            'confidence_score': processing_result.get('intent', {}).get('confidence', 0),
            'search_results_count': total_results,
            'context_data': {
                'intent': processing_result.get('intent', {}),
                'search_strategy': processing_result.get('search_strategy'),
                'services_used': processing_result.get('metadata', {}).get('services_used', [])
            }
        }
        
        return ChatMessage.objects.create(**bot_message_data)

    async def _build_conversation_context(self, session, request):
        """Build conversation context"""
        context = {
            'session_id': str(session.session_id),
            'user_preferences': session.user_preferences,
            'location_context': session.location_context or self._extract_location_context(request),
            'conversation_history': [],
            'recent_searches': []
        }
        
        # Get recent data
        recent_messages, recent_searches = await asyncio.gather(
            self._get_recent_messages(session, 10),
            self._get_recent_searches(session, 5)
        )
        
        context['conversation_history'] = [
            {
                'sender_type': msg.sender_type,
                'content': msg.content,
                'timestamp': msg.created_at.isoformat(),
                'message_type': msg.message_type
            }
            for msg in recent_messages
        ]
        
        context['recent_searches'] = [
            {
                'query': search.query_text,
                'search_type': search.search_type,
                'results_count': search.total_results_shown,
                'timestamp': search.created_at.isoformat()
            }
            for search in recent_searches
        ]
        
        return context

    @sync_to_async
    def _get_recent_messages(self, session, limit=10):
        """Get recent messages"""
        return list(session.messages.filter(
            is_active=True
        ).order_by('-created_at')[:limit])

    @sync_to_async
    def _get_recent_searches(self, session, limit=5):
        """Get recent searches"""
        return list(SearchQuery.objects.filter(
            chat_message__chat_session=session
        ).order_by('-created_at')[:limit])

    def _save_search_data_sync(self, processing_result, user_message):
        """Save search data synchronously"""
        try:
            search_strategy = processing_result.get('search_strategy', 'unknown')
            intent = processing_result.get('intent', {})
            
            # Extract search results
            search_results = processing_result.get('search_results', {})
            local_results = search_results.get('local', processing_result.get('local_results', {}))
            external_results = search_results.get('external', processing_result.get('external_results', {}))
            
            search_query_data = {
                'chat_message': user_message,
                'query_text': user_message.content,
                'search_type': intent.get('search_type', 'general'),
                'source_used': search_strategy,
                'filters': intent.get('filters', {}),
                'location_context': processing_result.get('location_context', {}),
                'local_results_count': local_results.get('total', local_results.get('total_results', 0)),
                'external_results_count': external_results.get('total', external_results.get('total_found', 0)),
                'total_results_shown': (
                    local_results.get('total', local_results.get('total_results', 0)) +
                    external_results.get('total', external_results.get('total_found', 0))
                ),
                'search_duration': processing_result.get('processing_time', 0)
            }
            
            search_query = SearchQuery.objects.create(**search_query_data)
            self._save_search_results_sync(search_query, processing_result)
            
        except Exception as e:
            logger.error(f"Error saving search data: {str(e)}")

    def _save_search_results_sync(self, search_query, processing_result):
        """Save search results synchronously"""
        try:
            results_to_create = []
            
            # Extract search results
            search_results = processing_result.get('search_results', {})
            local_results = search_results.get('local', processing_result.get('local_results', {}))
            external_results = search_results.get('external', processing_result.get('external_results', {}))
            
            # Process local results
            for result_type in ['products', 'services']:
                results = local_results.get(result_type, [])
                for i, result in enumerate(results[:10]):
                    results_to_create.append(SearchResult(
                        search_query=search_query,
                        result_type=result_type[:-1],
                        title=result.get('name', 'Unknown'),
                        description=result.get('description', ''),
                        url=result.get('url', ''),
                        image_url=result.get('image', ''),
                        object_id=result.get('id'),
                        external_data=result,
                        price_info={
                            'price': result.get('price', 0),
                            'currency': result.get('currency', 'NGN'),
                            'formatted': result.get('formatted_price', '')
                        },
                        location_info=result.get('location', {}),
                        relevance_score=result.get('relevance_score', 0.5),
                        position=i + 1
                    ))
            
            # Process external results
            for result_type in ['products', 'services']:
                results = external_results.get(result_type, [])
                for i, result in enumerate(results[:10]):
                    results_to_create.append(SearchResult(
                        search_query=search_query,
                        result_type=f'external_{result_type[:-1]}',
                        title=result.get('title', result.get('name', 'Unknown')),
                        description=result.get('description', ''),
                        url=result.get('url', ''),
                        image_url=result.get('image_url', result.get('image', '')),
                        external_data=result,
                        price_info={
                            'price_text': result.get('price', ''),
                            'source': result.get('source', '')
                        },
                        relevance_score=result.get('confidence', result.get('relevance_score', 0.5)),
                        position=i + 1 + len(local_results.get(result_type, []))
                    ))
            
            if results_to_create:
                SearchResult.objects.bulk_create(results_to_create, ignore_conflicts=True)
                
        except Exception as e:
            logger.error(f"Error saving search results: {str(e)}")

    async def _update_analytics(self, processing_result, chat_session):
        """Update analytics"""
        try:
            search_results = processing_result.get('search_results', {})
            local_results = search_results.get('local', processing_result.get('local_results', {}))
            external_results = search_results.get('external', processing_result.get('external_results', {}))
            
            analytics_data = {
                'session_id': str(chat_session.session_id),
                'response_time': processing_result.get('processing_time', 0),
                'search_strategy': processing_result.get('search_strategy', 'unknown'),
                'results_count': (
                    local_results.get('total', local_results.get('total_results', 0)) +
                    external_results.get('total', external_results.get('total_found', 0))
                ),
                'success': processing_result.get('success', True)
            }
            
            await self.analytics.record_interaction(analytics_data)
            
        except Exception as e:
            logger.error(f"Error updating analytics: {str(e)}")

    async def _generate_suggested_actions(self, processing_result):
        """Generate suggested actions"""
        suggestions = []
        
        search_results = processing_result.get('search_results', {})
        local_results = search_results.get('local', processing_result.get('local_results', {}))
        external_results = search_results.get('external', processing_result.get('external_results', {}))
        
        if local_results.get('products') or external_results.get('products'):
            suggestions.extend([
                {'action': 'compare_products', 'label': 'Compare these products', 'description': 'Get a detailed comparison'},
                {'action': 'filter_results', 'label': 'Filter results', 'description': 'Narrow down by criteria'},
                {'action': 'similar_products', 'label': 'Find similar products', 'description': 'Search alternatives'}
            ])
        
        if local_results.get('services') or external_results.get('services'):
            suggestions.extend([
                {'action': 'contact_provider', 'label': 'Contact service provider', 'description': 'Get in touch directly'},
                {'action': 'check_availability', 'label': 'Check availability', 'description': 'Verify service availability'}
            ])
        
        suggestions.extend([
            {'action': 'new_search', 'label': 'Search for something else', 'description': 'Start a new search'},
            {'action': 'get_recommendations', 'label': 'Get recommendations', 'description': 'Get personalized recommendations'}
        ])
        
        return suggestions[:5]

    async def _generate_tts_response(self, text):
        """Generate TTS response"""
        return {
            'audio_url': None,
            'duration': 0,
            'format': 'mp3',
            'message': 'TTS not implemented yet'
        }

    def _get_client_ip(self, request):
        """Get client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'Unknown')

    def _extract_device_info(self, request):
        """Extract device info"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return {
            'user_agent': user_agent[:500],
            'is_mobile': any(x in user_agent for x in ['Mobile', 'Android', 'iPhone']),
            'browser': 'Chrome' if 'Chrome' in user_agent else 'Unknown',
            'os': 'Windows' if 'Windows' in user_agent else 'Unknown'
        }

    def _extract_location_context(self, request):
        """Extract location context"""
        return {
            'ip_address': self._get_client_ip(request),
            'country': 'Nigeria',
            'timezone': 'Africa/Lagos',
            'currency': 'NGN'
        }

# Function-based wrapper for backwards compatibility
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def chat_api(request):
    """
    Function-based view wrapper for the chatbot API
    """
    view = ChatAPIView()
    return view.post(request)
    return view.post(request)


@api_view(['POST'])
@permission_classes([AllowAny])
def quick_search(request):
    """Quick search API endpoint"""
    try:
        # Validate request
        serializer = ChatMessageRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        query = data.get('message', '').strip()
        
        if not query:
            return Response({
                'success': False,
                'error': 'Search query is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use the smart router for quick search
        router = SmartChatbotRouter()
        
        # Build minimal context
        context = {
            'user_id': request.user.id if request.user.is_authenticated else None,
            'session_id': data.get('session_id'),
            'language': data.get('language', 'en'),
            'location_context': data.get('user_location', {}),
            'request_ip': request.META.get('REMOTE_ADDR', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }
        
        # Run async operation
        result = asyncio.run(router.process_message(query, context))
        
        # Extract search results correctly
        search_results = result.get('search_results', {})
        local_results = search_results.get('local', result.get('local_results', {}))
        external_results = search_results.get('external', result.get('external_results', {}))
        
        return Response({
            'success': result.get('success', True),
            'query': query,
            'response': result.get('response', result.get('final_response', '')),
            'results_count': {
                'local': local_results.get('total', local_results.get('total_results', 0)),
                'external': external_results.get('total', external_results.get('total_found', 0))
            },
            'processing_time': result.get('processing_time', 0)
        })
        
    except Exception as e:
        logger.error(f"Error in quick search: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'query': request.data.get('message', ''),
            'processing_time': 0
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    try:
        # Check database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Check cache
        cache.set('health_check', 'ok', 60)
        cache_status = cache.get('health_check') == 'ok'
        
        health_data = {
            'status': 'healthy',
            'service': 'AI Chatbot',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'services': {
                'database': 'ok',
                'cache': 'ok' if cache_status else 'error',
                'local_search': 'ok',
                'web_search': 'ok'
            }
        }
        
        return Response(health_data)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def conversation_history_api_view(request, session_id):
    """Get conversation history for a session"""
    try:
        # Get session
        session = get_object_or_404(ChatSession, session_id=session_id)
        
        # Check permissions
        if session.user and session.user != request.user:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get messages with pagination
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 50)), 100)
        offset = (page - 1) * page_size
        
        # Get messages
        messages = session.messages.filter(
            is_active=True
        ).order_by('created_at')[offset:offset + page_size]
        
        total_count = session.messages.filter(is_active=True).count()
        
        # Serialize
        serializer = ChatMessageSerializer(messages, many=True)
        
        return Response({
            'success': True,
            'session': ChatSessionSerializer(session).data,
            'messages': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': offset + page_size < total_count,
                'has_previous': page > 1
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve conversation history'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def feedback_api_view(request):
    """Submit feedback for a chat message"""
    try:
        # Validate request
        serializer = FeedbackRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Invalid feedback data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        
        # Get the message
        message = get_object_or_404(ChatMessage, id=validated_data['message_id'])
        
        # Create or update feedback
        feedback_data = {
            'chat_message': message,
            'feedback_type': validated_data['feedback_type'],
            'rating': validated_data.get('rating'),
            'comment': validated_data.get('comment', ''),
            'accuracy_rating': validated_data.get('accuracy_rating'),
            'helpfulness_rating': validated_data.get('helpfulness_rating'),
            'speed_rating': validated_data.get('speed_rating'),
            'ip_address': request.META.get('REMOTE_ADDR')
        }
        
        if request.user.is_authenticated:
            feedback_data['user'] = request.user
        
        # Create or update feedback
        feedback, created = UserFeedback.objects.update_or_create(
            chat_message=message,
            user=request.user if request.user.is_authenticated else None,
            defaults=feedback_data
        )
        
        return Response({
            'success': True,
            'message': 'Feedback submitted successfully',
            'feedback_id': str(feedback.id),
            'created': created
        })
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to submit feedback'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def chatbot_status_view(request):
    """Get chatbot system status"""
    try:
        # Get basic system info
        status_info = {
            'status': 'operational',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        }
        
        # Get today's basic stats
        today = datetime.now().date()
        today_sessions = ChatSession.objects.filter(created_at__date=today).count()
        today_messages = ChatMessage.objects.filter(created_at__date=today).count()
        
        status_info.update({
            'daily_stats': {
                'sessions_today': today_sessions,
                'messages_today': today_messages,
                'active_sessions': ChatSession.objects.filter(status='active').count()
            }
        })
        
        # Get configuration info (non-sensitive)
        try:
            public_config = BotConfiguration.objects.filter(
                key__in=['max_file_size_mb', 'supported_languages', 'features_enabled'],
                is_active=True
            ).values('key', 'value')
            
            status_info['configuration'] = {
                config['key']: config['value'] for config in public_config
            }
        except:
            status_info['configuration'] = {}
        
        return Response(status_info)
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return Response({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Additional API Views

class ImageUploadView(APIView):
    """Handle image upload for analysis"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Handle image upload"""
        try:
            if 'image' not in request.FILES:
                return Response({
                    'success': False,
                    'error': 'No image file provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            image_file = request.FILES['image']
            message = request.data.get('message', '')
            
            # Validate image
            from .serializers import validate_image_file
            try:
                validate_image_file(image_file)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process image with multimodal service
            from .services.multimodal import MultimodalProcessor
            multimodal = MultimodalProcessor()
            
            result = asyncio.run(multimodal.process_image(
                image_file, message, 'product_search'
            ))
            
            return Response({
                'success': result['success'],
                'image_analysis': result,
                'message': 'Image processed successfully' if result['success'] else 'Failed to process image'
            })
            
        except Exception as e:
            logger.error(f"Error in image upload: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to process image'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VoiceUploadView(APIView):
    """Handle voice note upload for transcription"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Handle voice upload"""
        try:
            if 'voice' not in request.FILES:
                return Response({
                    'success': False,
                    'error': 'No voice file provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            voice_file = request.FILES['voice']
            language = request.data.get('language', 'en')
            
            # Validate audio
            from .serializers import validate_audio_file
            try:
                validate_audio_file(voice_file)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process voice with multimodal service
            from .services.multimodal import MultimodalProcessor
            multimodal = MultimodalProcessor()
            
            result = asyncio.run(multimodal.process_voice_note(voice_file, language))
            
            return Response({
                'success': result['success'],
                'transcription': result.get('transcription', {}),
                'audio_info': result.get('audio_info', {}),
                'message': 'Voice processed successfully' if result['success'] else 'Failed to process voice'
            })
            
        except Exception as e:
            logger.error(f"Error in voice upload: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to process voice'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchSuggestionsView(APIView):
    """Provide search suggestions and autocomplete"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get search suggestions"""
        try:
            query = request.GET.get('q', '').strip()
            limit = min(int(request.GET.get('limit', 10)), 20)
            
            suggestions = []
            
            if len(query) >= 2:
                # Get suggestions from local search service
                from .services.local_search import LocalSearchService
                local_search = LocalSearchService()
                
                # Get popular searches
                try:
                    popular_searches = local_search.get_popular_searches(limit)
                    
                    # Filter suggestions that match the query
                    for search in popular_searches:
                        if query.lower() in search['term'].lower():
                            suggestions.append({
                                'text': search['term'],
                                'type': 'popular',
                                'count': search['count']
                            })
                except Exception as e:
                    logger.warning(f"Could not get popular searches: {str(e)}")
                
                # Get category suggestions (if available)
                try:
                    from main.models import Category  # Adjust import path as needed
                    categories = Category.objects.filter(
                        name__icontains=query,
                        is_active=True
                    )[:5]
                    
                    for category in categories:
                        suggestions.append({
                            'text': category.name,
                            'type': 'category',
                            'description': f"Browse {category.name} category"
                        })
                except ImportError:
                    # Category model not available
                    pass
                except Exception as e:
                    logger.warning(f"Could not get categories: {str(e)}")
            
            return Response({
                'success': True,
                'query': query,
                'suggestions': suggestions[:limit]
            })
            
        except Exception as e:
            logger.error(f"Error getting suggestions: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to get suggestions'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AnalyticsAPIView(APIView):
    """API for chatbot analytics (admin only)"""
    
    def get(self, request):
        """Get analytics data"""
        if not request.user.is_staff:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # Get date range
            days = int(request.GET.get('days', 30))
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Get analytics
            analytics = ChatAnalytics.objects.filter(
                date__range=[start_date, end_date]
            ).order_by('-date')
            
            serializer = ChatAnalyticsSerializer(analytics, many=True)
            
            # Calculate summary statistics
            total_sessions = sum(a.total_sessions for a in analytics)
            total_messages = sum(a.total_messages for a in analytics)
            avg_response_time = sum(a.average_response_time for a in analytics) / len(analytics) if analytics else 0
            
            return Response({
                'success': True,
                'analytics': serializer.data,
                'summary': {
                    'date_range': f"{start_date} to {end_date}",
                    'total_sessions': total_sessions,
                    'total_messages': total_messages,
                    'avg_response_time': round(avg_response_time, 2),
                    'days_analyzed': len(analytics)
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve analytics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatWidgetView(TemplateView):
    """Embeddable chat widget"""
    template_name = 'ai_chatbot/chat_widget.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Widget configuration
        widget_config = {
            'theme': self.request.GET.get('theme', 'light'),
            'position': self.request.GET.get('position', 'bottom-right'),
            'auto_open': self.request.GET.get('auto_open', 'false').lower() == 'true',
            'show_branding': self.request.GET.get('branding', 'true').lower() == 'true',
            'primary_color': self.request.GET.get('color', '#007bff'),
            'greeting_message': self.request.GET.get('greeting', 'Hi! How can I help you find products or services today?')
        }
        
        context['widget_config'] = widget_config
        return context


class AdminConfigurationView(APIView):
    """Admin view for bot configuration"""
    
    def get(self, request):
        """Get current bot configuration"""
        if not request.user.is_staff:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            configurations = BotConfiguration.objects.filter(is_active=True)
            serializer = BotConfigurationSerializer(configurations, many=True)
            
            return Response({
                'success': True,
                'configurations': serializer.data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def post(self, request):
        """Update bot configuration"""
        if not request.user.is_staff:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            key = request.data.get('key')
            value = request.data.get('value')
            description = request.data.get('description', '')
            
            if not key or value is None:
                return Response({
                    'success': False,
                    'error': 'Key and value are required'
                }, status=400)
            
            # Update or create configuration
            config = BotConfiguration.set_config(key, value, description)
            
            return Response({
                'success': True,
                'message': 'Configuration updated successfully',
                'configuration': BotConfigurationSerializer(config).data
            })
            
        except Exception as e:
            logger.error(f"Error updating configuration: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to update configuration'
            }, status=500)


class AdminSessionsView(APIView):
    """Admin view for chat sessions"""
    
    def get(self, request):
        """Get chat sessions with pagination"""
        if not request.user.is_staff:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            # Pagination parameters
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', 20)), 100)
            offset = (page - 1) * page_size
            
            # Filters
            status_filter = request.GET.get('status')
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            
            # Build queryset
            queryset = ChatSession.objects.all()
            
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            sessions = queryset.order_by('-last_activity')[offset:offset + page_size]
            
            serializer = ChatSessionSerializer(sessions, many=True)
            
            return Response({
                'success': True,
                'sessions': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting sessions: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve sessions'
            }, status=500)


@login_required
def admin_analytics_view(request):
    """Admin analytics dashboard view"""
    if not request.user.is_staff:
        return render(request, 'ai_chatbot/access_denied.html')
    
    try:
        # Get analytics data for the last 30 days
        analytics = ChatAnalytics.objects.all().order_by('-date')[:30]
        
        # Get summary statistics
        total_sessions = sum(a.total_sessions for a in analytics) if analytics else 0
        total_messages = sum(a.total_messages for a in analytics) if analytics else 0
        avg_rating = sum(a.average_rating for a in analytics) / len(analytics) if analytics else 0
        
        context = {
            'analytics': analytics,
            'summary': {
                'total_sessions': total_sessions,
                'total_messages': total_messages,
                'average_rating': round(avg_rating, 1),
                'days_analyzed': len(analytics)
            },
            'chart_data': {
                'dates': [a.date.strftime('%Y-%m-%d') for a in reversed(analytics)],
                'sessions': [a.total_sessions for a in reversed(analytics)],
                'messages': [a.total_messages for a in reversed(analytics)],
                'ratings': [a.average_rating for a in reversed(analytics)]
            }
        }
        
        return render(request, 'ai_chatbot/admin_analytics.html', context)
        
    except Exception as e:
        logger.error(f"Error in admin analytics view: {str(e)}")
        return render(request, 'ai_chatbot/error.html', {'error': str(e)})