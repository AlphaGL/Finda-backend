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
from django.views import View

from .models import (
    ChatSession, ChatMessage, SearchQuery, SearchResult, 
    UserFeedback, ChatAnalytics, BotConfiguration
)
from .serializers import (
    ChatSessionSerializer, ChatMessageSerializer, UserFeedbackSerializer
)
from .services.smart_router import SmartChatbotRouter
from .utils import ChatSessionManager
from .utils import ChatAnalyticsManager
from channels.db import database_sync_to_async
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
    """Chat API endpoint with proper async support"""
    
    def __init__(self):
        super().__init__()
        self.router = SmartChatbotRouter()
        self.session_manager = ChatSessionManager()
        self.analytics = ChatAnalyticsManager()
    
    def get(self, request):
        """Handle GET requests - return API info"""
        return JsonResponse({
            'success': True,
            'message': 'Finda Chat API is running',
            'endpoints': {
                'chat': 'POST /chatbot/api/chat/ - Send chat messages',
                'methods': ['POST'],
                'supported_types': ['text', 'image', 'voice']
            },
            'version': '1.0.0'
        })
    
    def post(self, request):
        """Handle POST requests synchronously but run async operations with asyncio.run()"""
        try:
            # Parse request data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
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
                    'error': 'Message text or file is required'
                }, status=400)
            
            # Run the async processing
            result = asyncio.run(self._process_chat_async(
                request, message_text, message_type, session_id, file_data, data
            ))
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred while processing your message',
                'message': 'I apologize, but I encountered an error. Please try again.',
                'timestamp': datetime.now().isoformat()
            }, status=500)
    
    async def _process_chat_async(self, request, message_text, message_type, session_id, file_data, data):
        """Process chat message asynchronously"""
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
            message_text, message_type, file_data, context
        )
        
        # Save bot response
        bot_message = await self._save_bot_response(
            chat_session, processing_result, user_message
        )
        
        # Update analytics
        await self._update_analytics(processing_result, chat_session)
        
        # Prepare response data
        response_data = {
            'success': processing_result.get('success', True),
            'message_id': str(bot_message.id),
            'session_id': str(chat_session.id),
            'response': processing_result.get('final_response', ''),
            'message_type': 'text',
            'metadata': {
                'processing_time': processing_result.get('metadata', {}).get('processing_time', 0),
                'search_strategy': processing_result.get('search_strategy', 'unknown'),
                'confidence_score': processing_result.get('metadata', {}).get('confidence_score', 0),
                'services_used': processing_result.get('metadata', {}).get('services_used', [])
            },
            'search_results': {
                'local': {
                    'products': processing_result.get('local_results', {}).get('products', [])[:5],
                    'services': processing_result.get('local_results', {}).get('services', [])[:5],
                    'total': processing_result.get('local_results', {}).get('total_results', 0)
                },
                'external': {
                    'products': processing_result.get('external_results', {}).get('products', [])[:5],
                    'total': processing_result.get('external_results', {}).get('total_found', 0)
                }
            },
            'suggested_actions': await self._generate_suggested_actions(processing_result),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add TTS if requested
        if data.get('enable_tts', False):
            response_data['tts_audio'] = await self._generate_tts_response(
                processing_result.get('final_response', '')
            )
        
        return response_data

    @sync_to_async
    def _get_or_create_session(self, request, session_id):
        """Get existing session or create new one"""
        if session_id:
            try:
                session = ChatSession.objects.select_related('user').get(
                    id=session_id,
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
        # Handle search data saving synchronously within this transaction
        if processing_result.get('local_results') or processing_result.get('external_results'):
            self._save_search_data_sync(processing_result, user_message)
        
        bot_message_data = {
            'chat_session': session,
            'sender_type': 'bot',
            'message_type': 'text',
            'content': processing_result.get('final_response', ''),
            'search_mode': processing_result.get('search_strategy', 'unknown'),
            'response_time': processing_result.get('metadata', {}).get('processing_time', 0),
            'confidence_score': processing_result.get('metadata', {}).get('confidence_score', 0),
            'search_results_count': (
                processing_result.get('local_results', {}).get('total_results', 0) +
                processing_result.get('external_results', {}).get('total_found', 0)
            ),
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
            'session_id': str(session.id),
            'user_preferences': session.user_preferences,
            'location_context': session.location_context or self._extract_location_context(request),
            'conversation_history': [],
            'recent_searches': []
        }
        
        # Get recent data concurrently
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
            
            search_query_data = {
                'chat_message': user_message,
                'query_text': user_message.content,
                'search_type': intent.get('search_type', 'general'),
                'source_used': search_strategy,
                'filters': intent.get('filters', {}),
                'location_context': processing_result.get('location_context', {}),
                'local_results_count': processing_result.get('local_results', {}).get('total_results', 0),
                'external_results_count': processing_result.get('external_results', {}).get('total_found', 0),
                'total_results_shown': (
                    processing_result.get('local_results', {}).get('total_results', 0) +
                    processing_result.get('external_results', {}).get('total_found', 0)
                ),
                'search_duration': processing_result.get('metadata', {}).get('processing_time', 0)
            }
            
            search_query = SearchQuery.objects.create(**search_query_data)
            self._save_search_results_sync(search_query, processing_result)
            
        except Exception as e:
            logger.error(f"Error saving search data: {str(e)}")

    def _save_search_results_sync(self, search_query, processing_result):
        """Save search results synchronously"""
        try:
            results_to_create = []
            
            # Process local results
            local_results = processing_result.get('local_results', {})
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
            external_results = processing_result.get('external_results', {})
            for i, result in enumerate(external_results.get('products', [])[:10]):
                results_to_create.append(SearchResult(
                    search_query=search_query,
                    result_type='external_product',
                    title=result.get('title', 'Unknown'),
                    description=result.get('description', ''),
                    url=result.get('url', ''),
                    image_url=result.get('image_url', ''),
                    external_data=result,
                    price_info={
                        'price_text': result.get('price', ''),
                        'source': result.get('source', '')
                    },
                    relevance_score=result.get('confidence', 0.5),
                    position=i + 1 + len(local_results.get('products', []))
                ))
            
            if results_to_create:
                SearchResult.objects.bulk_create(results_to_create, ignore_conflicts=True)
                
        except Exception as e:
            logger.error(f"Error saving search results: {str(e)}")

    async def _update_analytics(self, processing_result, chat_session):
        """Update analytics"""
        try:
            analytics_data = {
                'session_id': str(chat_session.id),
                'response_time': processing_result.get('metadata', {}).get('processing_time', 0),
                'search_strategy': processing_result.get('search_strategy', 'unknown'),
                'results_count': (
                    processing_result.get('local_results', {}).get('total_results', 0) +
                    processing_result.get('external_results', {}).get('total_found', 0)
                ),
                'success': processing_result.get('success', True)
            }
            
            await self.analytics.record_interaction(analytics_data)
            
        except Exception as e:
            logger.error(f"Error updating analytics: {str(e)}")

    async def _generate_suggested_actions(self, processing_result):
        """Generate suggested actions"""
        suggestions = []
        local_results = processing_result.get('local_results', {})
        external_results = processing_result.get('external_results', {})
        
        if local_results.get('products') or external_results.get('products'):
            suggestions.extend([
                {'action': 'compare_products', 'label': 'Compare these products', 'description': 'Get a detailed comparison'},
                {'action': 'filter_results', 'label': 'Filter results', 'description': 'Narrow down by criteria'},
                {'action': 'similar_products', 'label': 'Find similar products', 'description': 'Search alternatives'}
            ])
        
        if local_results.get('services'):
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
      
# @method_decorator(csrf_exempt, name='dispatch')
# class ChatAPIView(APIView):
#     """Main API endpoint for chat interactions"""
#     permission_classes = [AllowAny]
    
#     def __init__(self):
#         super().__init__()
#         self.router = SmartChatbotRouter()
#         self.session_manager = ChatSessionManager()
#         self.analytics = ChatAnalyticsManager()
    
#     async def post(self, request):
#         """Handle chat messages"""
#         try:
#             # Parse request data
#             data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            
#             message_text = data.get('message', '').strip()
#             message_type = data.get('message_type', 'text')
#             session_id = data.get('session_id')
#             file_data = request.FILES.get('file') if message_type in ['image', 'voice'] else None
            
#             # Validate input
#             if not message_text and not file_data:
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Message text or file is required'
#                 }, status=400)
            
#             # Get or create chat session
#             chat_session = await self._get_or_create_session(request, session_id)
            
#             # Save user message to database
#             user_message = await self._save_user_message(
#                 chat_session, message_text, message_type, file_data
#             )
            
#             # Get conversation context
#             context = await self._build_conversation_context(chat_session, request)
            
#             # Process message with the router
#             processing_result = await self.router.process_message(
#                 message_text, message_type, file_data, context
#             )
            
#             # Save bot response to database
#             bot_message = await self._save_bot_response(
#                 chat_session, processing_result, user_message
#             )
            
#             # Update analytics
#             await self._update_analytics(processing_result, chat_session)
            
#             # Prepare response
#             response_data = {
#                 'success': processing_result.get('success', True),
#                 'message_id': str(bot_message.id),
#                 'session_id': str(chat_session.id),
#                 'response': processing_result.get('final_response', ''),
#                 'message_type': 'text',
#                 'metadata': {
#                     'processing_time': processing_result.get('metadata', {}).get('processing_time', 0),
#                     'search_strategy': processing_result.get('search_strategy', 'unknown'),
#                     'confidence_score': processing_result.get('metadata', {}).get('confidence_score', 0),
#                     'services_used': processing_result.get('metadata', {}).get('services_used', [])
#                 },
#                 'search_results': {
#                     'local': {
#                         'products': processing_result.get('local_results', {}).get('products', [])[:5],
#                         'services': processing_result.get('local_results', {}).get('services', [])[:5],
#                         'total': processing_result.get('local_results', {}).get('total_results', 0)
#                     },
#                     'external': {
#                         'products': processing_result.get('external_results', {}).get('products', [])[:5],
#                         'total': processing_result.get('external_results', {}).get('total_found', 0)
#                     }
#                 },
#                 'suggested_actions': await self._generate_suggested_actions(processing_result),
#                 'timestamp': datetime.now().isoformat()
#             }
            
#             # Add TTS audio if requested
#             if data.get('enable_tts', False):
#                 response_data['tts_audio'] = await self._generate_tts_response(
#                     processing_result.get('final_response', '')
#                 )
            
#             return JsonResponse(response_data)
            
#         except json.JSONDecodeError:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Invalid JSON data'
#             }, status=400)
        
#         except Exception as e:
#             logger.error(f"Error processing chat message: {str(e)}")
#             return JsonResponse({
#                 'success': False,
#                 'error': 'An error occurred while processing your message',
#                 'message': 'I apologize, but I encountered an error. Please try again.',
#                 'timestamp': datetime.now().isoformat()
#             }, status=500)
    
#     async def _get_or_create_session(self, request, session_id: Optional[str]) -> ChatSession:
#         """Get existing session or create new one"""
#         if session_id:
#             try:
#                 session = await ChatSession.objects.select_related('user').aget(
#                     id=session_id,
#                     status='active'
#                 )
#                 # Update last activity
#                 session.last_activity = datetime.now()
#                 await session.asave()
#                 return session
#             except ChatSession.DoesNotExist:
#                 pass
        
#         # Create new session
#         session_data = {
#             'session_id': self.session_manager.generate_session_id(),
#             'ip_address': self._get_client_ip(request),
#             'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
#             'device_info': self._extract_device_info(request)
#         }
        
#         if request.user.is_authenticated:
#             session_data['user'] = request.user
        
#         return await ChatSession.objects.acreate(**session_data)
    
#     async def _save_user_message(
#         self, 
#         session: ChatSession, 
#         message: str, 
#         message_type: str,
#         file_data: Any = None
#     ) -> ChatMessage:
#         """Save user message to database"""
#         message_data = {
#             'chat_session': session,
#             'sender_type': 'user',
#             'message_type': message_type,
#             'content': message,
#             'context_data': {}
#         }
        
#         # Handle file uploads
#         if file_data and message_type == 'image':
#             # Upload image to Cloudinary (this will be handled by multimodal service)
#             message_data['image'] = file_data
#         elif file_data and message_type == 'voice':
#             message_data['voice_file'] = file_data
        
#         return await ChatMessage.objects.acreate(**message_data)
    
#     async def _save_bot_response(
#         self,
#         session: ChatSession,
#         processing_result: Dict,
#         user_message: ChatMessage
#     ) -> ChatMessage:
#         """Save bot response to database"""
        
#         # Create search queries and results if applicable
#         if processing_result.get('local_results') or processing_result.get('external_results'):
#             await self._save_search_data(processing_result, user_message)
        
#         # Save bot message
#         bot_message_data = {
#             'chat_session': session,
#             'sender_type': 'bot',
#             'message_type': 'text',
#             'content': processing_result.get('final_response', ''),
#             'search_mode': processing_result.get('search_strategy', 'unknown'),
#             'response_time': processing_result.get('metadata', {}).get('processing_time', 0),
#             'confidence_score': processing_result.get('metadata', {}).get('confidence_score', 0),
#             'search_results_count': (
#                 processing_result.get('local_results', {}).get('total_results', 0) +
#                 processing_result.get('external_results', {}).get('total_found', 0)
#             ),
#             'context_data': {
#                 'intent': processing_result.get('intent', {}),
#                 'search_strategy': processing_result.get('search_strategy'),
#                 'services_used': processing_result.get('metadata', {}).get('services_used', [])
#             }
#         }
        
#         return await ChatMessage.objects.acreate(**bot_message_data)
    
#     async def _build_conversation_context(self, session: ChatSession, request) -> Dict:
#         """Build conversation context for the AI"""
#         context = {
#             'session_id': str(session.id),
#             'user_preferences': session.user_preferences,
#             'location_context': session.location_context or self._extract_location_context(request),
#             'conversation_history': [],
#             'recent_searches': []
#         }
        
#         # Get recent conversation history
#         recent_messages = await self._get_recent_messages(session, limit=10)
#         context['conversation_history'] = [
#             {
#                 'sender_type': msg.sender_type,
#                 'content': msg.content,
#                 'timestamp': msg.created_at.isoformat(),
#                 'message_type': msg.message_type
#             }
#             for msg in recent_messages
#         ]
        
#         # Get recent search queries
#         recent_searches = await self._get_recent_searches(session, limit=5)
#         context['recent_searches'] = [
#             {
#                 'query': search.query_text,
#                 'search_type': search.search_type,
#                 'results_count': search.total_results_shown,
#                 'timestamp': search.created_at.isoformat()
#             }
#             for search in recent_searches
#         ]
        
#         return context
    
#     @database_sync_to_async
#     def _get_recent_messages(self, session: ChatSession, limit: int = 10):
#         """Get recent messages from session"""
#         return list(session.messages.filter(
#             is_active=True
#         ).order_by('-created_at')[:limit])
    
#     @database_sync_to_async
#     def _get_recent_searches(self, session: ChatSession, limit: int = 5):
#         """Get recent search queries from session"""
#         return list(SearchQuery.objects.filter(
#             chat_message__chat_session=session
#         ).order_by('-created_at')[:limit])
    
#     async def _save_search_data(self, processing_result: Dict, user_message: ChatMessage):
#         """Save search data to database"""
#         try:
#             # Extract search information
#             search_strategy = processing_result.get('search_strategy', 'unknown')
#             intent = processing_result.get('intent', {})
            
#             # Create search query record
#             search_query_data = {
#                 'chat_message': user_message,
#                 'query_text': user_message.content,
#                 'search_type': intent.get('search_type', 'general'),
#                 'source_used': search_strategy,
#                 'filters': intent.get('filters', {}),
#                 'location_context': processing_result.get('location_context', {}),
#                 'local_results_count': processing_result.get('local_results', {}).get('total_results', 0),
#                 'external_results_count': processing_result.get('external_results', {}).get('total_found', 0),
#                 'total_results_shown': (
#                     processing_result.get('local_results', {}).get('total_results', 0) +
#                     processing_result.get('external_results', {}).get('total_found', 0)
#                 ),
#                 'search_duration': processing_result.get('metadata', {}).get('processing_time', 0)
#             }
            
#             search_query = await self._create_search_query(search_query_data)
            
#             # Save search results
#             await self._save_search_results(search_query, processing_result)
            
#         except Exception as e:
#             logger.error(f"Error saving search data: {str(e)}")
    
#     @database_sync_to_async
#     def _create_search_query(self, search_data: Dict) -> SearchQuery:
#         """Create search query record"""
#         return SearchQuery.objects.create(**search_data)
    
#     async def _save_search_results(self, search_query: SearchQuery, processing_result: Dict):
#         """Save individual search results"""
#         try:
#             results_to_create = []
            
#             # Process local results
#             local_results = processing_result.get('local_results', {})
#             for result_type in ['products', 'services']:
#                 results = local_results.get(result_type, [])
#                 for i, result in enumerate(results[:10]):  # Limit to top 10
#                     results_to_create.append({
#                         'search_query': search_query,
#                         'result_type': result_type[:-1],  # 'product' or 'service'
#                         'title': result.get('name', 'Unknown'),
#                         'description': result.get('description', ''),
#                         'url': result.get('url', ''),
#                         'image_url': result.get('image', ''),
#                         'object_id': result.get('id'),
#                         'external_data': result,
#                         'price_info': {
#                             'price': result.get('price', 0),
#                             'currency': result.get('currency', 'NGN'),
#                             'formatted': result.get('formatted_price', '')
#                         },
#                         'location_info': result.get('location', {}),
#                         'relevance_score': result.get('relevance_score', 0.5),
#                         'position': i + 1
#                     })
            
#             # Process external results
#             external_results = processing_result.get('external_results', {})
#             external_products = external_results.get('products', [])
#             for i, result in enumerate(external_products[:10]):
#                 results_to_create.append({
#                     'search_query': search_query,
#                     'result_type': 'external_product',
#                     'title': result.get('title', 'Unknown'),
#                     'description': result.get('description', ''),
#                     'url': result.get('url', ''),
#                     'image_url': result.get('image_url', ''),
#                     'external_data': result,
#                     'price_info': {
#                         'price_text': result.get('price', ''),
#                         'source': result.get('source', '')
#                     },
#                     'relevance_score': result.get('confidence', 0.5),
#                     'position': i + 1 + len(local_results.get('products', []))
#                 })
            
#             # Bulk create results
#             if results_to_create:
#                 await self._bulk_create_search_results(results_to_create)
            
#         except Exception as e:
#             logger.error(f"Error saving search results: {str(e)}")
    
#     @database_sync_to_async
#     def _bulk_create_search_results(self, results_data: List[Dict]):
#         """Bulk create search results"""
#         results = [SearchResult(**data) for data in results_data]
#         SearchResult.objects.bulk_create(results, ignore_conflicts=True)
    
#     async def _update_analytics(self, processing_result: Dict, chat_session: ChatSession):
#         """Update analytics with the interaction"""
#         try:
#             from .utils import ChatAnalyticsManager
#             analytics = ChatAnalyticsManager()
            
#             analytics_data = {
#                 'session_id': str(chat_session.id),
#                 'response_time': processing_result.get('metadata', {}).get('processing_time', 0),
#                 'search_strategy': processing_result.get('search_strategy', 'unknown'),
#                 'results_count': (
#                     processing_result.get('local_results', {}).get('total_results', 0) +
#                     processing_result.get('external_results', {}).get('total_found', 0)
#                 ),
#                 'success': processing_result.get('success', True)
#             }
            
#             await analytics.record_interaction(analytics_data)
            
#         except Exception as e:
#             logger.error(f"Error updating analytics: {str(e)}")
    
#     async def _generate_suggested_actions(self, processing_result: Dict) -> List[Dict]:
#         """Generate suggested actions based on processing result"""
#         suggestions = []
        
#         # Get search results
#         local_results = processing_result.get('local_results', {})
#         external_results = processing_result.get('external_results', {})
        
#         # If products found, suggest related actions
#         if local_results.get('products') or external_results.get('products'):
#             suggestions.extend([
#                 {
#                     'action': 'compare_products',
#                     'label': 'Compare these products',
#                     'description': 'Get a detailed comparison of the products found'
#                 },
#                 {
#                     'action': 'filter_results',
#                     'label': 'Filter results',
#                     'description': 'Narrow down results by price, location, or other criteria'
#                 },
#                 {
#                     'action': 'similar_products',
#                     'label': 'Find similar products',
#                     'description': 'Search for alternative or related products'
#                 }
#             ])
        
#         # If services found
#         if local_results.get('services'):
#             suggestions.extend([
#                 {
#                     'action': 'contact_provider',
#                     'label': 'Contact service provider',
#                     'description': 'Get in touch with the service provider directly'
#                 },
#                 {
#                     'action': 'check_availability',
#                     'label': 'Check availability',
#                     'description': 'Verify service availability in your area'
#                 }
#             ])
        
#         # General suggestions
#         suggestions.extend([
#             {
#                 'action': 'new_search',
#                 'label': 'Search for something else',
#                 'description': 'Start a new search query'
#             },
#             {
#                 'action': 'get_recommendations',
#                 'label': 'Get recommendations',
#                 'description': 'Get personalized product recommendations'
#             }
#         ])
        
#         return suggestions[:5]  # Limit to 5 suggestions
    
#     async def _generate_tts_response(self, text: str) -> Dict[str, Any]:
#         """Generate text-to-speech audio (placeholder)"""
#         # This is a placeholder - implement with your preferred TTS service
#         return {
#             'audio_url': None,
#             'duration': 0,
#             'format': 'mp3',
#             'message': 'TTS not implemented yet'
#         }
    
#     def _get_client_ip(self, request):
#         """Get client IP address from request"""
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             return x_forwarded_for.split(',')[0].strip()
#         return request.META.get('REMOTE_ADDR', 'Unknown')
    
#     def _extract_device_info(self, request) -> Dict[str, Any]:
#         """Extract device information from request"""
#         user_agent = request.META.get('HTTP_USER_AGENT', '')
        
#         device_info = {
#             'user_agent': user_agent[:500],
#             'is_mobile': 'Mobile' in user_agent or 'Android' in user_agent or 'iPhone' in user_agent,
#             'browser': 'Unknown',
#             'os': 'Unknown'
#         }
        
#         # Simple browser detection
#         if 'Chrome' in user_agent:
#             device_info['browser'] = 'Chrome'
#         elif 'Firefox' in user_agent:
#             device_info['browser'] = 'Firefox'
#         elif 'Safari' in user_agent:
#             device_info['browser'] = 'Safari'
#         elif 'Edge' in user_agent:
#             device_info['browser'] = 'Edge'
        
#         # Simple OS detection
#         if 'Windows' in user_agent:
#             device_info['os'] = 'Windows'
#         elif 'Mac' in user_agent:
#             device_info['os'] = 'macOS'
#         elif 'Linux' in user_agent:
#             device_info['os'] = 'Linux'
#         elif 'Android' in user_agent:
#             device_info['os'] = 'Android'
#         elif 'iOS' in user_agent:
#             device_info['os'] = 'iOS'
        
#         return device_info
    
#     def _extract_location_context(self, request) -> Dict[str, Any]:
#         """Extract location context from request"""
#         # This is a basic implementation - you might want to use a geolocation service
#         return {
#             'ip_address': self._get_client_ip(request),
#             'country': 'Nigeria',  # Default - implement proper geolocation
#             'timezone': 'Africa/Lagos',
#             'currency': 'NGN'
#         }


# Additional API view functions that were incomplete:

@api_view(['POST'])
@permission_classes([AllowAny])
async def quick_search_view(request):
    """Quick search API endpoint"""
    try:
        data = request.data
        query = data.get('query', '').strip()
        
        if not query:
            return Response({
                'success': False,
                'error': 'Search query is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate request
        serializer = QuickSearchRequestSerializer(data=data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Invalid request data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Perform quick search
        from .services.local_search import LocalSearchService
        local_search = LocalSearchService()
        
        search_result = await local_search.quick_search(
            query=query,
            category=data.get('category'),
            location=data.get('location'),
            price_range=data.get('price_range'),
            search_type=data.get('search_type', 'both')
        )
        
        response_serializer = QuickSearchResponseSerializer({
            'success': search_result['success'],
            'query': query,
            'results': search_result.get('results', {}),
            'search_time': search_result.get('search_time', 0),
            'error': search_result.get('error')
        })
        
        return Response(response_serializer.data)
        
    except Exception as e:
        logger.error(f"Error in quick search: {str(e)}")
        return Response({
            'success': False,
            'error': 'Search failed',
            'query': data.get('query', ''),
            'search_time': 0
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def conversation_history_api_view(request, session_id):
    """Get conversation history for a session"""
    try:
        # Get session
        session = get_object_or_404(ChatSession, id=session_id)
        
        # Check permissions (user can only access their own sessions)
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
        public_config = BotConfiguration.objects.filter(
            key__in=['max_file_size_mb', 'supported_languages', 'features_enabled'],
            is_active=True
        ).values('key', 'value')
        
        status_info['configuration'] = {
            config['key']: config['value'] for config in public_config
        }
        
        return Response(status_info)
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return Response({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@login_required
def admin_analytics_view(request):
    """Admin analytics dashboard view"""
    if not request.user.is_staff:
        return render(request, 'ai_chatbot/access_denied.html')
    
    try:
        # Get analytics data for the last 30 days
        analytics = ChatAnalytics.objects.all()[:30]
        
        # Get summary statistics
        total_sessions = sum(a.total_sessions for a in analytics)
        total_messages = sum(a.total_messages for a in analytics)
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
                












# Add these additional views to views.py

# Additional API Views that need to be added to views.py:

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
            except serializers.ValidationError as e:
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
            except serializers.ValidationError as e:
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
                popular_searches = local_search.get_popular_searches(limit)
                
                # Filter suggestions that match the query
                for search in popular_searches:
                    if query.lower() in search['term'].lower():
                        suggestions.append({
                            'text': search['term'],
                            'type': 'popular',
                            'count': search['count']
                        })
                
                # Get category suggestions
                from main.models import Category  # Adjust import path
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


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check_view(request):
    """Health check endpoint"""
    try:
        # Check database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Check cache
        cache.set('health_check', 'ok', 60)
        cache_status = cache.get('health_check') == 'ok'
        
        # Check Gemini API (optional)
        gemini_status = 'unknown'
        try:
            from .services.gemini_client import GeminiAIClient
            if hasattr(settings, 'GOOGLE_API_KEY') and settings.GOOGLE_API_KEY:
                gemini_status = 'configured'
            else:
                gemini_status = 'not_configured'
        except Exception:
            gemini_status = 'error'
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': 'ok',
                'cache': 'ok' if cache_status else 'error',
                'gemini_api': gemini_status,
                'local_search': 'ok',
                'web_search': 'ok'
            },
            'version': '1.0.0'
        }
        
        return Response(health_data)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)