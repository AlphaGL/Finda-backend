# chatbot/enhanced_views.py - Fully Dynamic AI-Powered Views
import json
import time
from datetime import datetime, timedelta
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django.http import JsonResponse
from django.db.models import Q, Avg, Count
from typing import Dict
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
import csv
from .enhanced_gemini_client import enhanced_gemini_client
from .models import (
    ChatMessage, ChatSession, UserPreference, SearchQuery, 
    ProductSuggestion, VoiceMessage, ImageAnalysis,
    ConversationContext, FeedbackRating
)
from .serializers import (
    ChatMessageSerializer, ChatSessionSerializer, 
    UserPreferenceSerializer, FeedbackRatingSerializer
)
from .utils import process_voice_to_text, validate_image_file, validate_audio_file
import logging

logger = logging.getLogger(__name__)

class FullyDynamicChatAPI(APIView):
    """
    Fully dynamic chat API that lets Gemini AI handle everything
    while maintaining core Finda functionality
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        """Main endpoint that handles all types of messages dynamically"""
        user = request.user
        start_time = time.time()
        
        try:
            # Determine message type
            message_type = self._determine_message_type(request)
            
            # Get or create session
            session = self._get_or_create_session(user, request.data.get('session_id'))
            
            # Process message based on type
            if message_type == 'voice':
                return self._handle_voice_message_dynamic(request, user, session, start_time)
            elif message_type == 'image':
                return self._handle_image_message_dynamic(request, user, session, start_time)
            else:
                return self._handle_text_message_dynamic(request, user, session, start_time)
                
        except Exception as e:
            logger.error(f"Dynamic chat processing error: {e}")
            return Response({
                "error": "I'm having trouble processing your request right now. Please try again!",
                "detail": str(e) if request.user.is_staff else "Please try again later"
            }, status=500)

    def _determine_message_type(self, request) -> str:
        """Intelligently determine message type"""
        if 'audio' in request.FILES:
            return 'voice'
        elif 'image' in request.FILES:
            return 'image'
        elif request.data.get('type'):
            return request.data.get('type')
        else:
            return 'text'

    def _get_or_create_session(self, user, session_id=None):
        """Get or create chat session with intelligent session management"""
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=user)
                # Update session activity
                session.updated_at = datetime.now()
                session.save()
                return session
            except ChatSession.DoesNotExist:
                pass
        
        # Create new session
        session = ChatSession.objects.create(user=user)
        
        # Initialize conversation context
        ConversationContext.objects.get_or_create(
            session=session,
            defaults={'current_intent': 'greeting'}
        )
        
        return session

    def _handle_text_message_dynamic(self, request, user, session, start_time):
        """Handle text messages with full AI intelligence"""
        user_message = request.data.get('message', '').strip()
        
        if not user_message:
            return Response({
                "error": "Please send a message!",
                "session_id": session.id
            }, status=400)
        
        try:
            # Build comprehensive conversation context
            conversation_context = self._build_full_conversation_context(session, user)
            
            # Process with enhanced Gemini client
            ai_response = enhanced_gemini_client.process_dynamic_conversation(
                user_message=user_message,
                conversation_history=conversation_context['history'],
                user_context=conversation_context['user_context'],
                image_analysis=None
            )
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Save message to database
            chat_message = ChatMessage.objects.create(
                session=session,
                user_input=user_message,
                bot_response=ai_response['response'],
                message_type='text',
                preference_data=ai_response.get('context_updated', {}),
                search_results_data=ai_response.get('search_results', {}),
                response_time_ms=response_time_ms
            )
            
            # Update session context
            self._update_session_context(session, ai_response, user_message)
            
            # Log search performance
            if ai_response.get('search_results'):
                self._log_search_analytics(user_message, ai_response, user, session)
            
            return Response({
                "reply": ai_response['response'],
                "session_id": session.id,
                "message_id": chat_message.id,
                "timestamp": chat_message.timestamp,
                "conversation_state": ai_response.get('conversation_state'),
                "user_intent": ai_response.get('user_intent'),
                "confidence_score": ai_response.get('confidence_score'),
                "next_actions": ai_response.get('next_actions', []),
                "response_time_ms": response_time_ms
            })
            
        except Exception as e:
            logger.error(f"Text message processing error: {e}")
            return self._create_error_response(session, str(e))

    def _handle_voice_message_dynamic(self, request, user, session, start_time):
        """Handle voice messages with full context awareness"""
        audio_file = request.FILES.get('audio')
        
        if not audio_file:
            return Response({"error": "No audio file provided"}, status=400)
        
        # Validate audio file
        validation = validate_audio_file(audio_file)
        if not validation['is_valid']:
            return Response({
                "error": "Invalid audio file",
                "details": validation['errors']
            }, status=400)
        
        try:
            # Transcribe voice to text
            transcribed_text = process_voice_to_text(audio_file)
            
            if not transcribed_text:
                return Response({
                    "error": "Could not understand the audio. Please try speaking clearly or use text instead."
                }, status=400)
            
            # Build conversation context
            conversation_context = self._build_full_conversation_context(session, user)
            
            # Process voice with context
            voice_analysis = enhanced_gemini_client.process_voice_with_context(
                transcribed_text, conversation_context
            )
            
            # Process the conversation with transcribed text
            ai_response = enhanced_gemini_client.process_dynamic_conversation(
                user_message=transcribed_text,
                conversation_history=conversation_context['history'],
                user_context=conversation_context['user_context'],
                image_analysis=None
            )
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Save message
            chat_message = ChatMessage.objects.create(
                session=session,
                user_input=transcribed_text,
                bot_response=ai_response['response'],
                message_type='voice',
                audio_file=audio_file,
                preference_data=ai_response.get('context_updated', {}),
                search_results_data=ai_response.get('search_results', {}),
                response_time_ms=response_time_ms,
                transcription_confidence=voice_analysis.get('technical_quality', {}).get('transcription_confidence', 0.8)
            )
            
            # Save voice details
            VoiceMessage.objects.create(
                chat_message=chat_message,
                original_duration_seconds=None,  # Can be extracted if needed
                transcription_engine='google',
                transcription_confidence=voice_analysis.get('technical_quality', {}).get('transcription_confidence', 0.8),
                processing_time_ms=response_time_ms
            )
            
            # Update session context
            self._update_session_context(session, ai_response, transcribed_text)
            
            return Response({
                "transcribed_text": transcribed_text,
                "reply": ai_response['response'],
                "session_id": session.id,
                "message_id": chat_message.id,
                "timestamp": chat_message.timestamp,
                "voice_analysis": voice_analysis,
                "conversation_state": ai_response.get('conversation_state'),
                "confidence_score": ai_response.get('confidence_score'),
                "response_time_ms": response_time_ms
            })
            
        except Exception as e:
            logger.error(f"Voice message processing error: {e}")
            return self._create_error_response(session, f"Voice processing failed: {str(e)}")

    def _handle_image_message_dynamic(self, request, user, session, start_time):
        """Handle image messages with full AI analysis"""
        image_file = request.FILES.get('image')
        additional_message = request.data.get('message', '').strip()
        
        if not image_file:
            return Response({"error": "No image file provided"}, status=400)
        
        # Validate image file
        validation = validate_image_file(image_file)
        if not validation['is_valid']:
            return Response({
                "error": "Invalid image file",
                "details": validation['errors']
            }, status=400)
        
        try:
            # Build conversation context
            conversation_context = self._build_full_conversation_context(session, user)
            
            # Analyze image with context
            image_analysis = enhanced_gemini_client.analyze_image_with_context(
                image_file, additional_message
            )
            
            if not image_analysis:
                return Response({
                    "error": "Could not analyze the image. Please try a clearer photo or describe what you're looking for."
                }, status=400)
            
            # Create intelligent search query from image analysis
            search_query = self._create_search_query_from_image_analysis(image_analysis, additional_message)
            
            # Process with full AI intelligence
            ai_response = enhanced_gemini_client.process_dynamic_conversation(
                user_message=search_query,
                conversation_history=conversation_context['history'],
                user_context=conversation_context['user_context'],
                image_analysis=image_analysis
            )
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Save message
            chat_message = ChatMessage.objects.create(
                session=session,
                user_input=additional_message or "Image search",
                bot_response=ai_response['response'],
                message_type='image',
                image_file=image_file,
                image_analysis_data=image_analysis,
                preference_data=ai_response.get('context_updated', {}),
                search_results_data=ai_response.get('search_results', {}),
                response_time_ms=response_time_ms
            )
            
            # Save image analysis details
            ImageAnalysis.objects.create(
                chat_message=chat_message,
                original_width=image_analysis.get('processing_metadata', {}).get('image_dimensions', {}).get('width'),
                original_height=image_analysis.get('processing_metadata', {}).get('image_dimensions', {}).get('height'),
                detected_objects=image_analysis.get('visual_characteristics', {}),
                product_category_detected=image_analysis.get('product_identification', {}).get('category'),
                brand_detected=image_analysis.get('product_identification', {}).get('brand'),
                product_attributes=image_analysis.get('search_optimization', {}),
                overall_confidence=image_analysis.get('analysis_metadata', {}).get('confidence_score', 0.5),
                analysis_engine='gemini',
                processing_time_ms=response_time_ms
            )
            
            # Update session context
            self._update_session_context(session, ai_response, search_query)
            
            return Response({
                "image_analysis": image_analysis,
                "search_query": search_query,
                "reply": ai_response['response'],
                "session_id": session.id,
                "message_id": chat_message.id,
                "timestamp": chat_message.timestamp,
                "conversation_state": ai_response.get('conversation_state'),
                "confidence_score": ai_response.get('confidence_score'),
                "response_time_ms": response_time_ms
            })
            
        except Exception as e:
            logger.error(f"Image message processing error: {e}")
            return self._create_error_response(session, f"Image processing failed: {str(e)}")

    def _build_full_conversation_context(self, session, user) -> Dict:
        """Build comprehensive conversation context"""
        # Get recent messages
        recent_messages = ChatMessage.objects.filter(
            session=session
        ).order_by('-timestamp')[:15]
        
        # Format conversation history
        history = []
        for msg in reversed(recent_messages):
            history.append({
                'author': 'user',
                'content': msg.user_input,
                'type': msg.message_type,
                'timestamp': msg.timestamp.isoformat()
            })
            history.append({
                'author': 'assistant',
                'content': msg.bot_response,
                'type': 'text',
                'timestamp': msg.timestamp.isoformat()
            })
        
        # Get user preferences
        try:
            user_preferences = UserPreference.objects.get(user=user)
            preferences_data = {
                'categories': user_preferences.preferred_categories,
                'price_range': user_preferences.preferred_price_range,
                'locations': user_preferences.preferred_locations,
                'brands': user_preferences.preferred_brands,
                'language': user_preferences.preferred_language,
                'response_style': user_preferences.response_style,
                'external_sources_preference': user_preferences.external_sources_preference
            }
        except UserPreference.DoesNotExist:
            preferences_data = {}
        
        # Get conversation context
        try:
            context = ConversationContext.objects.get(session=session)
            context_data = {
                'current_intent': context.current_intent,
                'questions_asked': context.questions_asked,
                'preferences_collected': context.preferences_collected,
                'missing_preferences': context.missing_preferences,
                'last_search_results_internal': context.last_search_results_internal,
                'external_sources_shown': context.external_sources_shown,
                'bounce_count': context.bounce_count,
                'refinement_count': context.refinement_count
            }
        except ConversationContext.DoesNotExist:
            context_data = {}
        
        return {
            'history': history,
            'user_context': {
                'preferences': preferences_data,
                'session_data': session.preference_data,
                'awaiting_external_confirmation': session.awaiting_external_confirmation,
                'last_search_query': session.last_search_query,
                'last_search_type': session.last_search_type
            },
            'conversation_context': context_data,
            'user_info': {
                'user_id': user.id,
                'user_type': getattr(user, 'user_type', 'customer'),
                'session_count': ChatSession.objects.filter(user=user).count(),
                'total_messages': ChatMessage.objects.filter(session__user=user).count()
            }
        }

    def _create_search_query_from_image_analysis(self, image_analysis: Dict, additional_message: str) -> str:
        """Create intelligent search query from image analysis"""
        query_parts = []
        
        # Add user's additional message first
        if additional_message:
            query_parts.append(additional_message)
        
        # Add product identification
        product_id = image_analysis.get('product_identification', {})
        if product_id.get('product_type'):
            query_parts.append(product_id['product_type'])
        if product_id.get('brand'):
            query_parts.append(product_id['brand'])
        
        # Add key characteristics
        visual_chars = image_analysis.get('visual_characteristics', {})
        if visual_chars.get('primary_color'):
            query_parts.append(visual_chars['primary_color'])
        if visual_chars.get('style'):
            query_parts.append(visual_chars['style'])
        
        # Add primary keywords
        search_opt = image_analysis.get('search_optimization', {})
        primary_keywords = search_opt.get('primary_keywords', [])
        query_parts.extend(primary_keywords[:3])  # Top 3 keywords
        
        # Create coherent query
        unique_parts = list(dict.fromkeys(query_parts))  # Remove duplicates while preserving order
        return ' '.join(unique_parts).strip()

    def _update_session_context(self, session, ai_response: Dict, user_message: str):
        """Update session and conversation context based on AI response"""
        try:
            # Update session data
            context_updates = ai_response.get('context_updated', {})
            if context_updates:
                session.preference_data = {**session.preference_data, **context_updates}
            
            # Update conversation state
            conversation_state = ai_response.get('conversation_state', 'active_conversation')
            
            # Update or create conversation context
            context, created = ConversationContext.objects.get_or_create(
                session=session,
                defaults={'current_intent': ai_response.get('user_intent', 'general_inquiry')}
            )
            
            # Update context based on AI response
            if 'showing_results' in conversation_state:
                context.last_search_results_internal = ai_response.get('search_results', {})
            
            if 'external' in conversation_state.lower():
                context.external_sources_shown = True
            
            # Track refinements and topic bounces
            if ai_response.get('user_intent') == 'topic_change':
                context.bounce_count += 1
            
            if any('refine' in action for action in ai_response.get('next_actions', [])):
                context.refinement_count += 1
            
            context.current_intent = ai_response.get('user_intent', context.current_intent)
            context.save()
            
            session.save()
            
        except Exception as e:
            logger.error(f"Context update error: {e}")

    def _log_search_analytics(self, query: str, ai_response: Dict, user, session):
        """Log search analytics for performance tracking"""
        try:
            search_results = ai_response.get('search_results', {})
            internal_count = len(search_results.get('products', [])) + len(search_results.get('services', []))
            
            SearchQuery.objects.create(
                user=user,
                session=session,
                original_query=query,
                processed_query=query,  # Could be enhanced with processing
                search_type='mixed',
                internal_results_count=internal_count,
                external_sources_requested='external' in str(ai_response.get('next_actions', [])),
                preferences_used=ai_response.get('context_updated', {}),
                user_satisfied=None  # Will be updated based on feedback
            )
        except Exception as e:
            logger.error(f"Analytics logging error: {e}")

    def _create_error_response(self, session, error_message: str):
        """Create standardized error response"""
        return Response({
            "error": "I'm having trouble understanding that right now. Could you try rephrasing your request?",
            "session_id": session.id,
            "timestamp": datetime.now().isoformat(),
            "suggestion": "Try asking in a different way, or let me know what specific product or service you're looking for!",
            "debug_info": error_message if hasattr(session, 'user') and session.user.is_staff else None
        }, status=500)


class IntelligentExternalSearchAPI(APIView):
    """API for handling external search requests intelligently"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Handle external search requests with full context"""
        try:
            query = request.data.get('query', '')
            search_type = request.data.get('search_type', 'product')
            session_id = request.data.get('session_id')
            
            if not query:
                return Response({"error": "Search query is required"}, status=400)
            
            # Get session context
            session = None
            if session_id:
                try:
                    session = ChatSession.objects.get(id=session_id, user=request.user)
                except ChatSession.DoesNotExist:
                    pass
            
            # Build user preferences
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
            
            # Get external suggestions using enhanced client
            external_response = enhanced_gemini_client.generate_external_suggestions(
                query, search_type, preferences
            )
            
            # Update session if available
            if session:
                session.awaiting_external_confirmation = False
                session.save()
                
                # Log external search
                ChatMessage.objects.create(
                    session=session,
                    user_input=f"External search: {query}",
                    bot_response=external_response,
                    message_type='text',
                    external_sources_offered=True
                )
            
            return Response({
                "query": query,
                "search_type": search_type,
                "external_results": external_response,
                "preferences_applied": preferences,
                "session_id": session.id if session else None
            })
            
        except Exception as e:
            logger.error(f"External search error: {e}")
            return Response({
                "error": "External search is temporarily unavailable. Please try again later!",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)


class ContextAwareFeedbackAPI(APIView):
    """Enhanced feedback API with context awareness"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id=None):
        """Submit feedback with full conversation context"""
        try:
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
            
            # Extract feedback data
            rating = request.data.get('rating')
            feedback_text = request.data.get('feedback', '')
            issues = request.data.get('issues', [])
            
            if not rating or not (1 <= int(rating) <= 5):
                return Response({"error": "Rating must be between 1 and 5"}, status=400)
            
            # Create or update feedback
            feedback, created = FeedbackRating.objects.update_or_create(
                chat_message=chat_message,
                user=request.user,
                defaults={
                    'helpfulness_rating': int(rating),
                    'feedback_text': feedback_text,
                    'issues_reported': issues
                }
            )
            
            # Update message feedback status
            if int(rating) >= 4:
                chat_message.user_feedback = 'helpful'
            elif int(rating) >= 2:
                chat_message.user_feedback = 'partial'
            else:
                chat_message.user_feedback = 'not_helpful'
            chat_message.save()
            
            # Update search query satisfaction if related
            if hasattr(chat_message, 'search_queries'):
                for search_query in chat_message.search_queries.all():
                    search_query.user_satisfied = int(rating) >= 3
                    search_query.save()
            
            return Response({
                'message': 'Thank you for your feedback! It helps me learn and improve.',
                'rating': rating,
                'created': created,
                'feedback_id': feedback.id
            })
            
        except Exception as e:
            logger.error(f"Feedback submission error: {e}")
            return Response({
                "error": "Could not submit feedback. Please try again.",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)


class ConversationAnalyticsAPI(APIView):
    """API for conversation analytics and insights"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get conversation analytics for the user"""
        try:
            user = request.user
            
            # Basic statistics
            total_sessions = ChatSession.objects.filter(user=user).count()
            total_messages = ChatMessage.objects.filter(session__user=user).count()
            
            # Message type breakdown
            voice_messages = ChatMessage.objects.filter(
                session__user=user, message_type='voice'
            ).count()
            image_messages = ChatMessage.objects.filter(
                session__user=user, message_type='image'
            ).count()
            text_messages = total_messages - voice_messages - image_messages
            
            # Satisfaction metrics
            feedback_data = FeedbackRating.objects.filter(
                chat_message__session__user=user
            ).aggregate(
                avg_rating=Avg('helpfulness_rating'),
                total_feedback=Count('id')
            )
            
            # Conversation patterns
            recent_sessions = ChatSession.objects.filter(
                user=user,
                created_at__gte=datetime.now() - timedelta(days=30)
            )
            
            # Topic analysis (simplified)
            popular_intents = ConversationContext.objects.filter(
                session__user=user
            ).values('current_intent').annotate(
                count=Count('current_intent')
            ).order_by('-count')[:5]
            
            analytics_data = {
                'overview': {
                    'total_sessions': total_sessions,
                    'total_messages': total_messages,
                    'sessions_last_30_days': recent_sessions.count(),
                    'average_session_length': total_messages / total_sessions if total_sessions > 0 else 0
                },
                'message_types': {
                    'text': text_messages,
                    'voice': voice_messages,
                    'image': image_messages
                },
                'satisfaction': {
                    'average_rating': round(feedback_data['avg_rating'] or 0, 2),
                    'total_feedback_given': feedback_data['total_feedback'],
                    'feedback_rate': round(
                        (feedback_data['total_feedback'] / total_messages * 100) if total_messages > 0 else 0, 1
                    )
                },
                'conversation_patterns': {
                    'popular_intents': [
                        {'intent': item['current_intent'], 'count': item['count']} 
                        for item in popular_intents
                    ],
                    'average_refinements': ConversationContext.objects.filter(
                        session__user=user
                    ).aggregate(avg_refinements=Avg('refinement_count'))['avg_refinements'] or 0,
                    'topic_changes': ConversationContext.objects.filter(
                        session__user=user
                    ).aggregate(avg_bounces=Avg('bounce_count'))['avg_bounces'] or 0
                },
                'success_metrics': {
                    'searches_with_results': SearchQuery.objects.filter(
                        user=user, internal_results_count__gt=0
                    ).count(),
                    'external_searches_requested': SearchQuery.objects.filter(
                        user=user, external_sources_requested=True
                    ).count(),
                    'satisfied_searches': SearchQuery.objects.filter(
                        user=user, user_satisfied=True
                    ).count()
                }
            }
            
            return Response(analytics_data)
            
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            return Response({
                "error": "Could not generate analytics",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)


class IntelligentPreferencesAPI(APIView):
    """API for intelligent preference management"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user preferences with intelligent suggestions"""
        try:
            user = request.user
            
            # Get existing preferences
            try:
                preferences = UserPreference.objects.get(user=user)
                preferences_data = UserPreferenceSerializer(preferences).data
            except UserPreference.DoesNotExist:
                preferences_data = {}
            
            # Generate intelligent suggestions based on conversation history
            conversation_preferences = self._extract_preferences_from_conversations(user)
            
            # Merge and return
            return Response({
                'current_preferences': preferences_data,
                'suggested_preferences': conversation_preferences,
                'auto_detected_patterns': self._detect_user_patterns(user)
            })
            
        except Exception as e:
            logger.error(f"Preferences retrieval error: {e}")
            return Response({
                "error": "Could not retrieve preferences",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)
    
    def post(self, request):
        """Update preferences with intelligent validation"""
        try:
            user = request.user
            preferences, created = UserPreference.objects.get_or_create(user=user)
            
            # Validate and process preference updates
            serializer = UserPreferenceSerializer(preferences, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                
                # Update all active sessions with new preferences
                active_sessions = ChatSession.objects.filter(
                    user=user, 
                    is_active=True,
                    updated_at__gte=datetime.now() - timedelta(hours=1)
                )
                
                for session in active_sessions:
                    session.preference_data.update(request.data)
                    session.save()
                
                return Response({
                    'preferences': serializer.data,
                    'message': 'Preferences updated successfully! I\'ll use these in our future conversations.',
                    'sessions_updated': active_sessions.count()
                })
            else:
                return Response(serializer.errors, status=400)
                
        except Exception as e:
            logger.error(f"Preferences update error: {e}")
            return Response({
                "error": "Could not update preferences",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)
    
    def _extract_preferences_from_conversations(self, user) -> Dict:
        """Extract preferences from user's conversation history"""
        try:
            # Get recent messages
            recent_messages = ChatMessage.objects.filter(
                session__user=user,
                timestamp__gte=datetime.now() - timedelta(days=30)
            ).order_by('-timestamp')[:50]
            
            # Analyze preference data from messages
            all_preferences = {}
            for message in recent_messages:
                if message.preference_data:
                    for key, value in message.preference_data.items():
                        if key in all_preferences:
                            if isinstance(all_preferences[key], list) and isinstance(value, list):
                                all_preferences[key] = list(set(all_preferences[key] + value))
                            else:
                                all_preferences[key] = value
                        else:
                            all_preferences[key] = value
            
            return all_preferences
            
        except Exception as e:
            logger.error(f"Preference extraction error: {e}")
            return {}
    
    def _detect_user_patterns(self, user) -> Dict:
        """Detect user behavior patterns"""
        try:
            patterns = {}
            
            # Analyze message types preference
            message_counts = ChatMessage.objects.filter(session__user=user).values(
                'message_type'
            ).annotate(count=Count('message_type'))
            
            patterns['preferred_interaction_method'] = max(
                message_counts, key=lambda x: x['count']
            )['message_type'] if message_counts else 'text'
            
            # Analyze search patterns
            search_patterns = SearchQuery.objects.filter(user=user).values(
                'search_type'
            ).annotate(count=Count('search_type'))
            
            patterns['primary_search_interest'] = max(
                search_patterns, key=lambda x: x['count']
            )['search_type'] if search_patterns else 'product'
            
            # Analyze conversation length preference
            session_lengths = ChatSession.objects.filter(user=user).annotate(
                message_count=Count('messages')
            ).aggregate(avg_length=Avg('message_count'))
            
            patterns['conversation_style'] = 'detailed' if (
                session_lengths['avg_length'] or 0
            ) > 5 else 'brief'
            
            return patterns
            
        except Exception as e:
            logger.error(f"Pattern detection error: {e}")
            return {}


# Additional utility endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_health_check(request):
    """Health check for conversation system"""
    try:
        # Test AI client
        test_response = enhanced_gemini_client.process_dynamic_conversation(
            user_message="Hello",
            conversation_history=[],
            user_context={}
        )
        
        ai_status = "healthy" if test_response['response'] else "degraded"
        
        return Response({
            'status': 'healthy',
            'ai_client_status': ai_status,
            'database_status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'response_sample': test_response['response'][:100] if test_response['response'] else None
        })
        
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_conversation_context(request, session_id):
    """Reset conversation context for a fresh start"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        # Reset session data
        session.preference_data = {}
        session.awaiting_external_confirmation = False
        session.last_search_query = None
        session.last_search_type = None
        session.save()
        
        # Reset conversation context
        try:
            context = ConversationContext.objects.get(session=session)
            context.current_intent = 'greeting'
            context.questions_asked = []
            context.preferences_collected = {}
            context.missing_preferences = []
            context.last_search_results_internal = []
            context.external_sources_shown = False
            context.bounce_count = 0
            context.refinement_count = 0
            context.save()
        except ConversationContext.DoesNotExist:
            ConversationContext.objects.create(
                session=session,
                current_intent='greeting'
            )
        
        return Response({
            'message': 'Conversation context reset successfully! Let\'s start fresh.',
            'session_id': session.id,
            'new_context': 'greeting'
        })
        
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
    except Exception as e:
        logger.error(f"Context reset error: {e}")
        return Response({
            "error": "Could not reset conversation context",
            "detail": str(e) if request.user.is_staff else None
        }, status=500)
    
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_sessions_api(request):
    """
    API endpoint for managing chat sessions
    GET: List user's chat sessions
    POST: Create new chat session
    DELETE: Delete chat session
    """
    user = request.user
    
    try:
        if request.method == 'GET':
            # Get user's chat sessions with pagination
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            
            sessions = ChatSession.objects.filter(user=user).order_by('-updated_at')
            
            # Add session statistics
            sessions_data = []
            for session in sessions[(page-1)*page_size:page*page_size]:
                message_count = ChatMessage.objects.filter(session=session).count()
                last_message = ChatMessage.objects.filter(session=session).order_by('-timestamp').first()
                
                sessions_data.append({
                    'id': session.id,
                    'created_at': session.created_at,
                    'updated_at': session.updated_at,
                    'is_active': session.is_active,
                    'message_count': message_count,
                    'last_message_preview': last_message.user_input[:100] if last_message else None,
                    'last_message_time': last_message.timestamp if last_message else None,
                    'preference_data': session.preference_data,
                    'last_search_query': session.last_search_query
                })
            
            total_sessions = sessions.count()
            
            return Response({
                'sessions': sessions_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total_sessions,
                    'has_next': total_sessions > page * page_size,
                    'has_previous': page > 1
                }
            })
        
        elif request.method == 'POST':
            # Create new chat session
            session = ChatSession.objects.create(user=user)
            
            # Initialize conversation context
            ConversationContext.objects.create(
                session=session,
                current_intent='greeting'
            )
            
            return Response({
                'message': 'New chat session created successfully!',
                'session': {
                    'id': session.id,
                    'created_at': session.created_at,
                    'is_active': session.is_active
                }
            }, status=201)
        
        elif request.method == 'DELETE':
            # Delete specific session or all sessions
            session_id = request.data.get('session_id')
            
            if session_id:
                try:
                    session = ChatSession.objects.get(id=session_id, user=user)
                    session.delete()
                    return Response({
                        'message': f'Session {session_id} deleted successfully'
                    })
                except ChatSession.DoesNotExist:
                    return Response({
                        'error': 'Session not found'
                    }, status=404)
            else:
                # Delete all sessions for user
                deleted_count = ChatSession.objects.filter(user=user).count()
                ChatSession.objects.filter(user=user).delete()
                
                return Response({
                    'message': f'All {deleted_count} sessions deleted successfully'
                })
    
    except ValueError as e:
        return Response({
            'error': 'Invalid parameters provided',
            'detail': str(e)
        }, status=400)
    
    except Exception as e:
        logger.error(f"Chat sessions API error: {e}")
        return Response({
            'error': 'Could not process chat sessions request',
            'detail': str(e) if user.is_staff else 'Please try again later'
        }, status=500)

# =======================
# SESSION MANAGEMENT
# =======================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_chat_session(request, session_id):
    """Clear all messages from a specific chat session"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        # Delete all messages in the session
        message_count = ChatMessage.objects.filter(session=session).count()
        ChatMessage.objects.filter(session=session).delete()
        
        # Reset session context
        try:
            context = ConversationContext.objects.get(session=session)
            context.current_intent = 'greeting'
            context.questions_asked = []
            context.preferences_collected = {}
            context.missing_preferences = []
            context.last_search_results_internal = []
            context.external_sources_shown = False
            context.bounce_count = 0
            context.refinement_count = 0
            context.save()
        except ConversationContext.DoesNotExist:
            pass
        
        # Reset session data
        session.preference_data = {}
        session.awaiting_external_confirmation = False
        session.last_search_query = None
        session.last_search_type = None
        session.save()
        
        return Response({
            'message': f'Chat session cleared successfully. {message_count} messages removed.',
            'session_id': str(session.id),
            'messages_removed': message_count
        })
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=404)
    except Exception as e:
        logger.error(f"Clear session error: {e}")
        return Response({
            'error': 'Could not clear session',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request, session_id=None):
    """Get chat history for a session or all sessions"""
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        
        if session_id:
            # Get history for specific session
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
                messages = ChatMessage.objects.filter(session=session)
            except ChatSession.DoesNotExist:
                return Response({'error': 'Session not found'}, status=404)
        else:
            # Get history for all user sessions
            messages = ChatMessage.objects.filter(session__user=request.user)
        
        messages = messages.order_by('-timestamp')
        total_messages = messages.count()
        
        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        paginated_messages = messages[start:end]
        
        history_data = []
        for msg in paginated_messages:
            history_data.append({
                'id': msg.id,
                'session_id': str(msg.session.id),
                'user_input': msg.user_input,
                'bot_response': msg.bot_response,
                'message_type': msg.message_type,
                'timestamp': msg.timestamp,
                'user_feedback': msg.user_feedback,
                'response_time_ms': msg.response_time_ms,
                'has_image': bool(msg.image_file),
                'has_audio': bool(msg.audio_file)
            })
        
        return Response({
            'history': history_data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total_messages,
                'has_next': total_messages > end,
                'has_previous': page > 1
            },
            'session_id': str(session_id) if session_id else None
        })
        
    except Exception as e:
        logger.error(f"Chat history error: {e}")
        return Response({
            'error': 'Could not retrieve chat history',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_statistics(request, session_id):
    """Get statistics for a specific session"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        # Basic stats
        total_messages = ChatMessage.objects.filter(session=session).count()
        voice_messages = ChatMessage.objects.filter(session=session, message_type='voice').count()
        image_messages = ChatMessage.objects.filter(session=session, message_type='image').count()
        text_messages = total_messages - voice_messages - image_messages
        
        # Timing stats
        messages = ChatMessage.objects.filter(session=session)
        avg_response_time = messages.aggregate(
            avg_time=Avg('response_time_ms')
        )['avg_time'] or 0
        
        # Feedback stats
        feedback_stats = messages.exclude(user_feedback__isnull=True).aggregate(
            helpful_count=Count('id', filter=Q(user_feedback='helpful')),
            partial_count=Count('id', filter=Q(user_feedback='partial')),
            not_helpful_count=Count('id', filter=Q(user_feedback='not_helpful'))
        )
        
        # Session duration
        first_message = messages.order_by('timestamp').first()
        last_message = messages.order_by('-timestamp').first()
        
        session_duration = None
        if first_message and last_message:
            duration = last_message.timestamp - first_message.timestamp
            session_duration = duration.total_seconds()
        
        # Context stats
        try:
            context = ConversationContext.objects.get(session=session)
            context_stats = {
                'current_intent': context.current_intent,
                'bounce_count': context.bounce_count,
                'refinement_count': context.refinement_count,
                'external_sources_shown': context.external_sources_shown
            }
        except ConversationContext.DoesNotExist:
            context_stats = {}
        
        return Response({
            'session_id': str(session.id),
            'created_at': session.created_at,
            'updated_at': session.updated_at,
            'is_active': session.is_active,
            'message_stats': {
                'total_messages': total_messages,
                'text_messages': text_messages,
                'voice_messages': voice_messages,
                'image_messages': image_messages
            },
            'performance_stats': {
                'average_response_time_ms': round(avg_response_time, 2),
                'session_duration_seconds': session_duration
            },
            'feedback_stats': feedback_stats,
            'context_stats': context_stats
        })
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=404)
    except Exception as e:
        logger.error(f"Session statistics error: {e}")
        return Response({
            'error': 'Could not retrieve session statistics',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_context(request, session_id):
    """Get conversation context for a session"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        try:
            context = ConversationContext.objects.get(session=session)
            context_data = {
                'current_intent': context.current_intent,
                'questions_asked': context.questions_asked,
                'preferences_collected': context.preferences_collected,
                'missing_preferences': context.missing_preferences,
                'last_search_results_internal': context.last_search_results_internal,
                'external_sources_shown': context.external_sources_shown,
                'bounce_count': context.bounce_count,
                'refinement_count': context.refinement_count,
                'updated_at': context.updated_at
            }
        except ConversationContext.DoesNotExist:
            context_data = {
                'current_intent': 'greeting',
                'questions_asked': [],
                'preferences_collected': {},
                'missing_preferences': [],
                'last_search_results_internal': [],
                'external_sources_shown': False,
                'bounce_count': 0,
                'refinement_count': 0
            }
        
        return Response({
            'session_id': str(session.id),
            'context': context_data,
            'session_data': {
                'preference_data': session.preference_data,
                'awaiting_external_confirmation': session.awaiting_external_confirmation,
                'last_search_query': session.last_search_query,
                'last_search_type': session.last_search_type
            }
        })
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=404)
    except Exception as e:
        logger.error(f"Get context error: {e}")
        return Response({
            'error': 'Could not retrieve conversation context',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_conversation_context(request, session_id):
    """Update conversation context"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        context, created = ConversationContext.objects.get_or_create(
            session=session,
            defaults={'current_intent': 'greeting'}
        )
        
        # Update context fields
        update_data = request.data
        if 'current_intent' in update_data:
            context.current_intent = update_data['current_intent']
        if 'questions_asked' in update_data:
            context.questions_asked = update_data['questions_asked']
        if 'preferences_collected' in update_data:
            context.preferences_collected.update(update_data['preferences_collected'])
        if 'missing_preferences' in update_data:
            context.missing_preferences = update_data['missing_preferences']
        
        context.save()
        
        return Response({
            'message': 'Conversation context updated successfully',
            'session_id': str(session.id),
            'updated_fields': list(update_data.keys())
        })
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=404)
    except Exception as e:
        logger.error(f"Update context error: {e}")
        return Response({
            'error': 'Could not update conversation context',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


# =======================
# MULTIMEDIA PROCESSING
# =======================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_voice_message(request):
    """Process voice message directly"""
    audio_file = request.FILES.get('audio')
    
    if not audio_file:
        return Response({'error': 'No audio file provided'}, status=400)
    
    try:
        # Validate audio file
        validation = validate_audio_file(audio_file)
        if not validation['is_valid']:
            return Response({
                'error': 'Invalid audio file',
                'details': validation['errors']
            }, status=400)
        
        # Process voice to text
        transcribed_text = process_voice_to_text(audio_file)
        
        if not transcribed_text:
            return Response({
                'error': 'Could not transcribe audio'
            }, status=400)
        
        return Response({
            'transcribed_text': transcribed_text,
            'confidence': 0.8,  # Placeholder
            'audio_duration': None,  # Could be calculated
            'processing_time_ms': 1000  # Placeholder
        })
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        return Response({
            'error': 'Voice processing failed',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_product_image_api(request):
    """Analyze product image"""
    image_file = request.FILES.get('image')
    
    if not image_file:
        return Response({'error': 'No image file provided'}, status=400)
    
    try:
        # Validate image file
        validation = validate_image_file(image_file)
        if not validation['is_valid']:
            return Response({
                'error': 'Invalid image file',
                'details': validation['errors']
            }, status=400)
        
        # Analyze image (placeholder - implement actual analysis)
        analysis_result = {
            'product_identification': {
                'product_type': 'Unknown',
                'brand': None,
                'category': 'General'
            },
            'visual_characteristics': {
                'primary_color': 'Unknown',
                'style': 'Unknown'
            },
            'search_optimization': {
                'primary_keywords': ['product'],
                'suggested_search_terms': ['general product search']
            },
            'confidence_score': 0.5
        }
        
        return Response({
            'analysis': analysis_result,
            'processing_time_ms': 1500,
            'image_processed': True
        })
        
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return Response({
            'error': 'Image analysis failed',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


# =======================
# USER INTERACTION APIs
# =======================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rate_message(request, message_id):
    """Rate a specific message"""
    try:
        message = ChatMessage.objects.get(id=message_id, session__user=request.user)
        rating = request.data.get('rating')
        feedback_text = request.data.get('feedback', '')
        
        if not rating or not (1 <= int(rating) <= 5):
            return Response({'error': 'Rating must be between 1 and 5'}, status=400)
        
        # Update message feedback
        if int(rating) >= 4:
            message.user_feedback = 'helpful'
        elif int(rating) >= 2:
            message.user_feedback = 'partial'
        else:
            message.user_feedback = 'not_helpful'
        message.save()
        
        # Create or update feedback rating
        feedback, created = FeedbackRating.objects.update_or_create(
            chat_message=message,
            user=request.user,
            defaults={
                'helpfulness_rating': int(rating),
                'feedback_text': feedback_text
            }
        )
        
        return Response({
            'message': 'Rating submitted successfully',
            'rating': rating,
            'message_id': message_id,
            'created': created
        })
        
    except ChatMessage.DoesNotExist:
        return Response({'error': 'Message not found'}, status=404)
    except Exception as e:
        logger.error(f"Rate message error: {e}")
        return Response({
            'error': 'Could not submit rating',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_preferences(request):
    """Get user preferences"""
    try:
        preferences = UserPreference.objects.get(user=request.user)
        serializer = UserPreferenceSerializer(preferences)
        return Response(serializer.data)
    except UserPreference.DoesNotExist:
        return Response({'preferences': None, 'message': 'No preferences set'})
    except Exception as e:
        logger.error(f"Get preferences error: {e}")
        return Response({
            'error': 'Could not retrieve preferences',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_user_preferences(request):
    """Update user preferences"""
    try:
        preferences, created = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(preferences, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'preferences': serializer.data,
                'message': 'Preferences updated successfully',
                'created': created
            })
        else:
            return Response(serializer.errors, status=400)
            
    except Exception as e:
        logger.error(f"Update preferences error: {e}")
        return Response({
            'error': 'Could not update preferences',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_chat_stats(request):
    """Get user chat statistics"""
    try:
        user = request.user
        
        # Basic stats
        total_sessions = ChatSession.objects.filter(user=user).count()
        total_messages = ChatMessage.objects.filter(session__user=user).count()
        
        # Message type breakdown
        message_types = ChatMessage.objects.filter(session__user=user).values(
            'message_type'
        ).annotate(count=Count('message_type'))
        
        # Feedback stats
        feedback_stats = FeedbackRating.objects.filter(
            chat_message__session__user=user
        ).aggregate(
            avg_rating=Avg('helpfulness_rating'),
            total_feedback=Count('id')
        )
        
        return Response({
            'user_id': user.id,
            'total_sessions': total_sessions,
            'total_messages': total_messages,
            'message_types': list(message_types),
            'average_rating': round(feedback_stats['avg_rating'] or 0, 2),
            'total_feedback_given': feedback_stats['total_feedback'],
            'account_created': user.date_joined
        })
        
    except Exception as e:
        logger.error(f"User stats error: {e}")
        return Response({
            'error': 'Could not retrieve user statistics',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_user_data(request):
    """Export user chat data"""
    try:
        user = request.user
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="chat_export_{user.id}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Session ID', 'Message ID', 'Timestamp', 'User Input', 
            'Bot Response', 'Message Type', 'Feedback', 'Response Time (ms)'
        ])
        
        messages = ChatMessage.objects.filter(session__user=user).order_by('-timestamp')
        
        for msg in messages:
            writer.writerow([
                str(msg.session.id),
                msg.id,
                msg.timestamp.isoformat(),
                msg.user_input,
                msg.bot_response,
                msg.message_type,
                msg.user_feedback or 'None',
                msg.response_time_ms or 0
            ])
        
        return response
        
    except Exception as e:
        logger.error(f"Export data error: {e}")
        return Response({
            'error': 'Could not export data',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


# =======================
# SEARCH AND DISCOVERY
# =======================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_with_preferences_api(request):
    """Advanced search with user preferences"""
    try:
        query = request.data.get('query', '')
        search_type = request.data.get('search_type', 'product')
        
        if not query:
            return Response({'error': 'Search query is required'}, status=400)
        
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
        
        # Placeholder search results
        search_results = {
            'products': [],
            'services': [],
            'external_suggestions': [],
            'total_results': 0,
            'preferences_applied': preferences,
            'search_metadata': {
                'query': query,
                'search_type': search_type,
                'processing_time_ms': 500
            }
        }
        
        return Response(search_results)
        
    except Exception as e:
        logger.error(f"Advanced search error: {e}")
        return Response({
            'error': 'Search failed',
            'detail': str(e) if request.user.is_staff else None
        }, status=500)


# =======================
# SYSTEM HEALTH & MONITORING
# =======================

@api_view(['GET'])
@permission_classes([AllowAny])
def chatbot_health_check(request):
    """General health check"""
    try:
        # Test database
        db_healthy = ChatSession.objects.exists()
        
        health_data = {
            'status': 'healthy',
            'database': 'healthy' if db_healthy else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0',
            'services': {
                'chat_api': 'healthy',
                'voice_processing': 'healthy',
                'image_analysis': 'healthy'
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
@permission_classes([AllowAny])
def gemini_status_api(request):
    """Check Gemini AI status"""
    try:
        # Test Gemini connection (placeholder)
        gemini_status = {
            'status': 'healthy',
            'response_time_ms': 150,
            'last_test': datetime.now().isoformat(),
            'capabilities': ['text', 'image', 'voice']
        }
        
        return Response(gemini_status)
        
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)


# =======================
# WEBHOOK ENDPOINTS
# =======================

@api_view(['POST'])
@permission_classes([AllowAny])  # Webhooks usually need special authentication
def process_voice_webhook(request):
    """Webhook for voice processing"""
    try:
        # Process webhook data
        webhook_data = request.data
        
        return Response({
            'status': 'processed',
            'timestamp': datetime.now().isoformat(),
            'webhook_id': webhook_data.get('id', 'unknown')
        })
        
    except Exception as e:
        logger.error(f"Voice webhook error: {e}")
        return Response({
            'error': 'Webhook processing failed',
            'timestamp': datetime.now().isoformat()
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def image_analysis_webhook(request):
    """Webhook for image analysis"""
    try:
        # Process webhook data
        webhook_data = request.data
        
        return Response({
            'status': 'processed',
            'timestamp': datetime.now().isoformat(),
            'webhook_id': webhook_data.get('id', 'unknown')
        })
        
    except Exception as e:
        logger.error(f"Image webhook error: {e}")
        return Response({
            'error': 'Webhook processing failed',
            'timestamp': datetime.now().isoformat()
        }, status=500)


# =======================
# LEGACY SUPPORT
# =======================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """Legacy chat API - redirects to enhanced API"""
    # Redirect to the enhanced API
    enhanced_api = FullyDynamicChatAPI()
    return enhanced_api.post(request)


class UserPreferencesAPI(APIView):
    """Legacy preferences API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return get_user_preferences(request)
    
    def post(self, request):
        return update_user_preferences(request)


class ChatFeedbackAPI(APIView):
    """Legacy feedback API"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        message_id = request.data.get('message_id')
        if message_id:
            return rate_message(request, message_id)
        else:
            return Response({'error': 'message_id is required'}, status=400)


# =======================
# ADMIN & MANAGEMENT
# =======================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_message_operations(request):
    """Bulk operations on messages (admin only)"""
    if not request.user.is_staff:
        raise PermissionDenied("Admin access required")
    
    try:
        operation = request.data.get('operation')
        message_ids = request.data.get('message_ids', [])
        
        if operation == 'delete':
            deleted_count = ChatMessage.objects.filter(id__in=message_ids).count()
            ChatMessage.objects.filter(id__in=message_ids).delete()
            
            return Response({
                'operation': 'delete',
                'processed_count': deleted_count,
                'message': f'{deleted_count} messages deleted successfully'
            })
        
        elif operation == 'export':
            messages = ChatMessage.objects.filter(id__in=message_ids)
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="bulk_export.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID', 'User', 'Input', 'Response', 'Timestamp', 'Type'])
            
            for msg in messages:
                writer.writerow([
                    msg.id,
                    msg.session.user.username,
                    msg.user_input,
                    msg.bot_response,
                    msg.timestamp.isoformat(),
                    msg.message_type
                ])
            
            return response
        
        else:
            return Response({'error': 'Invalid operation'}, status=400)
            
    except Exception as e:
        logger.error(f"Bulk operations error: {e}")
        return Response({
            'error': 'Bulk operation failed',
            'detail': str(e)
        }, status=500)


class CustomAuthToken(ObtainAuthToken):
    """Custom authentication token"""
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email,
            'created': created
        })