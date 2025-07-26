# chatbot/views.py - Perfect AI Integration with Complete Memory System (FIXED)
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
from .enhanced_gemini_client import enhanced_gemini_client  # Import our fixed perfect AI
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

class PerfectAIChatAPI(APIView):
    """
    Perfect AI Chat API that handles everything with complete intelligence and memory - FIXED VERSION
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        """Perfect AI endpoint that handles ALL conversation scenarios - FIXED"""
        user = request.user
        start_time = time.time()
        session = None  # Initialize session variable
        
        try:
            # Get or create session with perfect memory
            session = self._get_or_create_session_with_memory(user, request.data.get('session_id'))
            
            # Build complete conversation history
            conversation_history = self._build_complete_conversation_history(session)
            
            # Build comprehensive user profile
            user_profile = self._build_comprehensive_user_profile(user, session)
            
            # Determine message type and content
            message_content, message_type, image_data = self._extract_message_content(request)
            
            if not message_content and not image_data:
                return Response({
                    "error": "Please send a message, image, or voice note!",
                    "session_id": str(session.id),
                    "suggestion": "I'm here to help you find amazing products and services on Finda! 🛍️"
                }, status=400)
            
            # Get current context data
            context_data = self._get_current_context_data(session)
            
            # Process with Perfect AI - FIXED: Now handles errors properly
            try:
                ai_result = enhanced_gemini_client.process_perfect_conversation(
                    user_message=message_content,
                    user_id=user.id,
                    session_id=str(session.id),
                    conversation_history=conversation_history,
                    user_profile=user_profile,
                    image_data=image_data,
                    context_data=context_data
                )
            except Exception as ai_error:
                logger.error(f"AI processing error: {ai_error}")
                # Create fallback response
                ai_result = {
                    'response': self._create_fallback_ai_response(user, conversation_history),
                    'message_analysis': {'error': str(ai_error), 'fallback_used': True},
                    'search_results': {'products': [], 'services': [], 'categories': []},
                    'updated_context': {},
                    'memory_updates': {},
                    'conversation_intelligence': {'status': 'fallback_mode'},
                    'next_conversation_guidance': ['ask_for_clarification'],
                    'user_satisfaction_prediction': 0.5,
                    'personality_insights': {}
                }
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Save message with perfect memory updates
            chat_message = self._save_message_with_memory(
                session=session,
                user_input=message_content,
                message_type=message_type,
                ai_result=ai_result,
                response_time_ms=response_time_ms,
                image_data=image_data,
                request=request
            )
            
            # Update perfect memory system
            try:
                self._update_perfect_memory_system(session, user, ai_result)
            except Exception as memory_error:
                logger.error(f"Memory update error: {memory_error}")
                # Continue without failing the response
            
            # Generate response with perfect intelligence
            return Response({
                "reply": ai_result['response'],
                "session_id": str(session.id),
                "message_id": chat_message.id,
                "timestamp": chat_message.timestamp,
                "message_analysis": ai_result.get('message_analysis', {}),
                "conversation_intelligence": ai_result.get('conversation_intelligence', {}),
                "user_satisfaction_prediction": ai_result.get('user_satisfaction_prediction', 0.8),
                "next_conversation_guidance": ai_result.get('next_conversation_guidance', []),
                "personality_insights": ai_result.get('personality_insights', {}),
                "search_results_found": len(ai_result.get('search_results', {}).get('products', [])),
                "response_time_ms": response_time_ms,
                "ai_confidence": ai_result.get('message_analysis', {}).get('intent_analysis', {}).get('intent_confidence', 0.85),
                "memory_updated": bool(ai_result.get('memory_updates')),
                "transcribed_text": ai_result.get('transcribed_text') if message_type == 'voice' else None,
                "system_status": "healthy" if not ai_result.get('message_analysis', {}).get('fallback_used') else "fallback_mode"
            })
            
        except Exception as e:
            logger.error(f"Error getting context data: {e}")
            return {
                'current_intent': 'greeting',
                'questions_asked': [],
                'preferences_collected': {},
                'missing_preferences': [],
                'last_search_results_internal': [],
                'external_sources_shown': False,
                'bounce_count': 0,
                'refinement_count': 0
            }

    def _save_message_with_memory(self, session, user_input, message_type, ai_result, 
                                 response_time_ms, image_data, request):
        """Save message with perfect memory integration - FIXED"""
        
        # Prepare image file if present
        image_file = None
        audio_file = None
        
        try:
            if message_type == 'image' and 'image' in request.FILES:
                image_file = request.FILES['image']
            elif message_type == 'voice' and 'audio' in request.FILES:
                audio_file = request.FILES['audio']
            
            # Create message with safe defaults
            chat_message = ChatMessage.objects.create(
                session=session,
                user_input=user_input or '',
                bot_response=ai_result.get('response', 'I apologize, but I encountered an issue. Please try again.'),
                message_type=message_type,
                image_file=image_file,
                audio_file=audio_file,
                image_analysis_data=ai_result.get('message_analysis', {}).get('image_analysis', {}),
                preference_data=ai_result.get('memory_updates', {}),
                search_results_data=ai_result.get('search_results', {}),
                external_sources_offered=False,  # Will be updated based on AI response
                response_time_ms=response_time_ms,
                transcription_confidence=ai_result.get('voice_confidence', 0.8) if message_type == 'voice' else None
            )
            
            # Save additional details based on message type
            if message_type == 'voice' and audio_file:
                try:
                    VoiceMessage.objects.create(
                        chat_message=chat_message,
                        transcription_engine='google',
                        transcription_confidence=ai_result.get('voice_confidence', 0.8),
                        processing_time_ms=response_time_ms
                    )
                except Exception as voice_save_error:
                    logger.error(f"Error saving voice message details: {voice_save_error}")
            
            if message_type == 'image' and ai_result.get('message_analysis', {}).get('image_analysis'):
                try:
                    image_analysis = ai_result['message_analysis']['image_analysis']
                    ImageAnalysis.objects.create(
                        chat_message=chat_message,
                        detected_objects=image_analysis.get('visual_characteristics', {}),
                        product_category_detected=image_analysis.get('product_identification', {}).get('category'),
                        brand_detected=image_analysis.get('product_identification', {}).get('brand'),
                        product_attributes=image_analysis.get('search_optimization', {}),
                        overall_confidence=image_analysis.get('confidence_score', 0.5),
                        analysis_engine='gemini',
                        processing_time_ms=response_time_ms
                    )
                except Exception as image_save_error:
                    logger.error(f"Error saving image analysis: {image_save_error}")
            
            return chat_message
            
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            # Create minimal message if all else fails
            return ChatMessage.objects.create(
                session=session,
                user_input=user_input or 'Message received',
                bot_response=ai_result.get('response', 'I apologize, but I encountered an issue. Please try again.'),
                message_type=message_type,
                response_time_ms=response_time_ms
            )

    def _update_perfect_memory_system(self, session, user, ai_result):
        """Update the perfect memory system with new insights - FIXED"""
        try:
            # Update session preferences safely
            memory_updates = ai_result.get('memory_updates', {})
            if memory_updates and isinstance(memory_updates, dict):
                try:
                    current_data = session.preference_data or {}
                    if isinstance(current_data, dict):
                        current_data.update(memory_updates)
                        session.preference_data = current_data
                        session.save()
                except Exception as session_update_error:
                    logger.error(f"Error updating session preferences: {session_update_error}")
            
            # Update conversation context safely
            try:
                context, created = ConversationContext.objects.get_or_create(
                    session=session,
                    defaults={
                        'current_intent': 'general_inquiry',
                        'preferences_collected': {},
                        'questions_asked': [],
                        'missing_preferences': []
                    }
                )
                
                # Update based on AI analysis
                message_analysis = ai_result.get('message_analysis', {})
                
                if message_analysis.get('intent_analysis', {}).get('primary_intent'):
                    context.current_intent = message_analysis['intent_analysis']['primary_intent']
                
                # Track conversation patterns safely
                if message_analysis.get('contextual_analysis', {}).get('topic_change_detected'):
                    context.bounce_count = (context.bounce_count or 0) + 1
                
                if 'refinement' in ai_result.get('next_conversation_guidance', []):
                    context.refinement_count = (context.refinement_count or 0) + 1
                
                # Update preferences collected safely
                new_preferences = ai_result.get('updated_context', {}).get('user_profile_updates', {}).get('preference_updates', {})
                if new_preferences and isinstance(new_preferences, dict):
                    current_prefs = context.preferences_collected or {}
                    if isinstance(current_prefs, dict):
                        current_prefs.update(new_preferences)
                        context.preferences_collected = current_prefs
                
                # Update search results safely
                search_results = ai_result.get('search_results', {})
                if search_results and (search_results.get('products') or search_results.get('services')):
                    context.last_search_results_internal = search_results
                
                context.save()
                
            except Exception as context_error:
                logger.error(f"Error updating conversation context: {context_error}")
            
            # Update user preferences if significant insights were gained
            try:
                personality_insights = ai_result.get('personality_insights', {})
                if personality_insights and not personality_insights.get('error') and isinstance(personality_insights, dict):
                    self._update_user_preferences_from_insights(user, personality_insights, memory_updates)
            except Exception as prefs_error:
                logger.error(f"Error updating user preferences: {prefs_error}")
            
            # Log search query if applicable
            try:
                if ai_result.get('search_results', {}).get('search_metadata'):
                    search_metadata = ai_result['search_results']['search_metadata']
                    SearchQuery.objects.create(
                        user=user,
                        session=session,
                        original_query=search_metadata.get('original_query', '')[:200],  # Limit length
                        processed_query=search_metadata.get('original_query', '')[:200],
                        search_type='mixed',
                        internal_results_count=search_metadata.get('total_results', 0),
                        preferences_used=memory_updates if isinstance(memory_updates, dict) else {},
                        response_time_ms=search_metadata.get('processing_time_ms', 0)
                    )
            except Exception as query_log_error:
                logger.error(f"Error logging search query: {query_log_error}")
                
        except Exception as e:
            logger.error(f"Error updating perfect memory system: {e}")
            # Don't fail the request if memory update fails

    def _create_perfect_error_response(self, session, error_message, user):
        """Create perfect error response that maintains AI personality - FIXED"""
        session_id = str(session.id) if session else None
        
        try:
            # Personalized error responses based on user history
            user_messages_count = 0
            if session:
                try:
                    user_messages_count = ChatMessage.objects.filter(session=session).count()
                except Exception as count_error:
                    logger.error(f"Error counting messages: {count_error}")
                    user_messages_count = 0
            
            if user_messages_count > 0:
                # Returning user - acknowledge relationship
                error_response = "I remember our conversation! I'm having a small technical hiccup right now, but I'm still here to help you find amazing products on Finda. Could you try asking me again? 🛍️"
            else:
                # New user - welcoming approach
                error_response = "Welcome to Finda AI! I'm excited to help you, but I'm experiencing a small technical issue. Don't worry - I'm here to help you find exactly what you need! Could you try your request again? 🌟"
            
            return Response({
                "error": error_response,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "suggestion": "I'm your intelligent shopping assistant - try telling me what product or service you're looking for!",
                "retry_guidance": "You can send text, voice messages, or even images of products you want to find!",
                "technical_error": error_message if user.is_staff else None,
                "system_status": "error_recovery_mode"
            }, status=500)
            
        except Exception as e:
            logger.error(f"Error creating error response: {e}")
            # Minimal fallback response
            return Response({
                "error": "I'm experiencing a technical issue. Please try again.",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }, status=500)

    # Helper methods for perfect memory system - FIXED VERSIONS

    def _initialize_session_preferences(self, user):
        """Initialize session with user's known preferences - FIXED"""
        try:
            user_prefs = UserPreference.objects.get(user=user)
            return {
                'categories': user_prefs.preferred_categories or [],
                'price_range': user_prefs.preferred_price_range or {},
                'locations': user_prefs.preferred_locations or [],
                'brands': user_prefs.preferred_brands or [],
                'language': user_prefs.preferred_language or 'en',
                'response_style': user_prefs.response_style or 'balanced'
            }
        except UserPreference.DoesNotExist:
            return {}
        except Exception as e:
            logger.error(f"Error initializing session preferences: {e}")
            return {}

    def _get_user_known_preferences(self, user):
        """Get preferences we already know about the user - FIXED"""
        preferences = {}
        
        try:
            # From explicit preferences
            try:
                user_prefs = UserPreference.objects.get(user=user)
                preferences.update({
                    'explicit_categories': user_prefs.preferred_categories or [],
                    'explicit_price_range': user_prefs.preferred_price_range or {},
                    'explicit_locations': user_prefs.preferred_locations or [],
                    'explicit_brands': user_prefs.preferred_brands or []
                })
            except UserPreference.DoesNotExist:
                pass
            
            # From conversation history
            try:
                recent_messages = ChatMessage.objects.filter(session__user=user).order_by('-timestamp')[:20]
                
                inferred_preferences = {}
                for msg in recent_messages:
                    if msg.preference_data and isinstance(msg.preference_data, dict):
                        for key, value in msg.preference_data.items():
                            if key not in inferred_preferences:
                                inferred_preferences[key] = []
                            if isinstance(value, list):
                                inferred_preferences[key].extend(value)
                            elif value:  # Any truthy value
                                inferred_preferences[key].append(str(value))
                
                # Clean up inferred preferences
                for key, values in inferred_preferences.items():
                    if isinstance(values, list):
                        inferred_preferences[key] = list(set(values))  # Remove duplicates
                
                preferences['inferred'] = inferred_preferences
            except Exception as e:
                logger.error(f"Error getting inferred preferences: {e}")
                preferences['inferred'] = {}
                
        except Exception as e:
            logger.error(f"Error getting user known preferences: {e}")
            preferences = {'explicit': {}, 'inferred': {}}
        
        return preferences

    def _identify_missing_preferences(self, user):
        """Identify what preferences we still need to learn - FIXED"""
        try:
            known_preferences = self._get_user_known_preferences(user)
            
            essential_preferences = [
                'categories', 'price_range', 'locations', 'brands', 
                'shopping_style', 'urgency_preference', 'quality_vs_price'
            ]
            
            missing = []
            for pref in essential_preferences:
                has_pref = False
                
                # Check in explicit preferences
                explicit_prefs = known_preferences.get('explicit', {})
                if isinstance(explicit_prefs, dict):
                    for key, value in explicit_prefs.items():
                        if pref in key and value:  # Has some value
                            has_pref = True
                            break
                
                # Check in inferred preferences
                if not has_pref:
                    inferred_prefs = known_preferences.get('inferred', {})
                    if isinstance(inferred_prefs, dict) and pref in inferred_prefs:
                        if inferred_prefs[pref]:  # Has some values
                            has_pref = True
                
                if not has_pref:
                    missing.append(pref)
            
            return missing
            
        except Exception as e:
            logger.error(f"Error identifying missing preferences: {e}")
            return ['categories', 'price_range', 'locations']  # Default missing preferences

    def _get_preferred_message_type(self, messages):
        """Analyze user's preferred message type - FIXED"""
        try:
            type_counts = {}
            for msg in messages:
                msg_type = getattr(msg, 'message_type', 'text')
                type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
            
            if not type_counts:
                return 'text'
            
            return max(type_counts, key=type_counts.get)
        except Exception as e:
            logger.error(f"Error getting preferred message type: {e}")
            return 'text'

    def _calculate_average_session_length(self, user):
        """Calculate average session length for user - FIXED"""
        try:
            sessions = ChatSession.objects.filter(user=user)
            if not sessions.exists():
                return 0
            
            total_messages = 0
            session_count = sessions.count()
            
            for session in sessions:
                total_messages += ChatMessage.objects.filter(session=session).count()
            
            return total_messages / session_count if session_count > 0 else 0
        except Exception as e:
            logger.error(f"Error calculating average session length: {e}")
            return 0

    def _calculate_response_engagement(self, messages):
        """Calculate how engaged user is with responses - FIXED"""
        try:
            if not messages:
                return 0.5
            
            positive_indicators = 0
            total_responses = 0
            
            for msg in messages:
                feedback = getattr(msg, 'user_feedback', None)
                if feedback:
                    total_responses += 1
                    if feedback in ['helpful', 'partial']:
                        positive_indicators += 1
            
            return positive_indicators / total_responses if total_responses > 0 else 0.5
        except Exception as e:
            logger.error(f"Error calculating response engagement: {e}")
            return 0.5

    def _analyze_topic_consistency(self, messages):
        """Analyze how consistent user is with topics - FIXED"""
        try:
            if len(messages) < 3:
                return 'insufficient_data'
            
            # Simple topic consistency analysis
            topic_changes = 0
            current_topics = set()
            
            for msg in messages:
                # Extract simple topics from message
                content = getattr(msg, 'user_input', '') or ''
                content = content.lower()
                new_topics = set()
                
                topic_keywords = ['phone', 'laptop', 'clothes', 'food', 'service', 'car', 'house']
                for keyword in topic_keywords:
                    if keyword in content:
                        new_topics.add(keyword)
                
                if current_topics and new_topics and not current_topics.intersection(new_topics):
                    topic_changes += 1
                
                if new_topics:  # Only update if we found topics
                    current_topics = new_topics
            
            consistency_ratio = 1 - (topic_changes / len(messages)) if len(messages) > 0 else 0
            
            if consistency_ratio > 0.8:
                return 'very_consistent'
            elif consistency_ratio > 0.6:
                return 'moderately_consistent'
            else:
                return 'topic_explorer'
        except Exception as e:
            logger.error(f"Error analyzing topic consistency: {e}")
            return 'unknown'

    def _calculate_satisfaction_trend(self, feedback_ratings):
        """Calculate if user satisfaction is improving over time - FIXED"""
        try:
            if feedback_ratings.count() < 3:
                return 'insufficient_data'
            
            ratings = list(feedback_ratings.order_by('created_at').values_list('helpfulness_rating', flat=True))
            
            # Simple trend analysis
            if len(ratings) >= 3:
                recent_avg = sum(ratings[-3:]) / 3
                if len(ratings) > 3:
                    older_avg = sum(ratings[:-3]) / len(ratings[:-3])
                else:
                    older_avg = recent_avg
                
                if recent_avg > older_avg + 0.5:
                    return 'improving'
                elif recent_avg < older_avg - 0.5:
                    return 'declining'
                else:
                    return 'stable'
            else:
                return 'insufficient_data'
        except Exception as e:
            logger.error(f"Error calculating satisfaction trend: {e}")
            return 'unknown'

    def _update_user_preferences_from_insights(self, user, personality_insights, memory_updates):
        """Update user preferences based on AI insights - FIXED"""
        try:
            user_prefs, created = UserPreference.objects.get_or_create(user=user)
            
            # Update preferences based on insights and memory updates safely
            if isinstance(memory_updates, dict):
                categories = memory_updates.get('categories')
                if isinstance(categories, list):
                    current_cats = user_prefs.preferred_categories or []
                    user_prefs.preferred_categories = list(set(current_cats + categories))
                
                brands = memory_updates.get('brands')
                if isinstance(brands, list):
                    current_brands = user_prefs.preferred_brands or []
                    user_prefs.preferred_brands = list(set(current_brands + brands))
                
                price_range = memory_updates.get('price_range')
                if isinstance(price_range, dict):
                    user_prefs.preferred_price_range = price_range
                
                locations = memory_updates.get('locations')
                if isinstance(locations, list):
                    current_locs = user_prefs.preferred_locations or []
                    user_prefs.preferred_locations = list(set(current_locs + locations))
            
            user_prefs.save()
            
        except Exception as e:
            logger.error(f"Error updating user preferences from insights: {e}")


class PerfectExternalSearchAPI(APIView):
    """Enhanced external search with perfect memory - FIXED"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Handle external search with perfect memory context - FIXED"""
        try:
            query = request.data.get('query', '')
            search_type = request.data.get('search_type', 'product')
            session_id = request.data.get('session_id')
            
            if not query:
                return Response({"error": "Search query is required"}, status=400)
            
            # Get session and build memory context safely
            session = None
            memory_context = {}
            
            if session_id:
                try:
                    session = ChatSession.objects.get(id=session_id, user=request.user)
                    
                    # Build memory context for external search
                    perfect_chat_api = PerfectAIChatAPI()
                    conversation_history = perfect_chat_api._build_complete_conversation_history(session)
                    user_profile = perfect_chat_api._build_comprehensive_user_profile(request.user, session)
                    context_data = perfect_chat_api._get_current_context_data(session)
                    
                    memory_context = {
                        'user_identity': {
                            'user_id': request.user.id,
                            'session_id': str(session.id),
                            'returning_user': len(conversation_history) > 0
                        },
                        'conversation_memory': {
                            'full_history': conversation_history,
                            'topics_discussed': self._extract_topics_from_history(conversation_history)
                        },
                        'user_intelligence_profile': {
                            'product_preferences': user_profile.get('preferences', {}),
                            'shopping_behavior': user_profile.get('shopping_history', {}),
                            'communication_style': user_profile.get('interaction_patterns', {}).get('preferred_message_type', 'standard')
                        },
                        'search_intelligence': {
                            'previous_searches': [msg['content'] for msg in conversation_history if msg['author'] == 'user'][-5:],
                            'search_patterns': user_profile.get('shopping_history', {})
                        }
                    }
                    
                except ChatSession.DoesNotExist:
                    pass
                except Exception as context_error:
                    logger.error(f"Error building memory context: {context_error}")
            
            # Generate external suggestions with perfect memory
            try:
                external_response = enhanced_gemini_client.generate_external_suggestions_with_memory(
                    query, search_type, memory_context
                )
            except Exception as suggestions_error:
                logger.error(f"Error generating external suggestions: {suggestions_error}")
                external_response = self._create_fallback_external_response(query, search_type)
            
            # Update session if available
            if session:
                try:
                    session.awaiting_external_confirmation = False
                    session.save()
                    
                    # Log external search with memory context
                    ChatMessage.objects.create(
                        session=session,
                        user_input=f"External search: {query}",
                        bot_response=external_response,
                        message_type='text',
                        external_sources_offered=True,
                        preference_data=memory_context.get('user_intelligence_profile', {}).get('product_preferences', {})
                    )
                except Exception as session_update_error:
                    logger.error(f"Error updating session for external search: {session_update_error}")
            
            return Response({
                "query": query,
                "search_type": search_type,
                "external_results": external_response,
                "memory_context_used": bool(memory_context),
                "personalized": len(conversation_history) > 0 if 'conversation_history' in locals() else False,
                "session_id": str(session.id) if session else None
            })
            
        except Exception as e:
            logger.error(f"Perfect external search error: {e}")
            return Response({
                "error": "I'm having trouble searching external sources right now, but I'm still here to help you find what you need on Finda! 🛍️",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)

    def _create_fallback_external_response(self, query, search_type):
        """Create fallback external response"""
        return f"""
I searched for "{query}" and here are some external options you might find helpful:

🌐 **Try these popular platforms:**
• **Jumia** - Nigeria's leading marketplace
• **Konga** - Wide variety of {search_type}s
• **Amazon** - International shipping available
• **AliExpress** - Affordable options

💡 **Tip**: Try different keywords, or check back on Finda as we add new {search_type}s daily!

🛍️ **Let's keep searching together!**
"""

    def _extract_topics_from_history(self, history):
        """Extract topics from history"""
        topics = []
        for msg in history:
            if msg.get('author') == 'user':
                content = msg.get('content', '').lower()
                # Simple topic extraction
                topic_keywords = ['phone', 'laptop', 'clothes', 'shoes', 'food', 'service', 'car', 'house']
                for keyword in topic_keywords:
                    if keyword in content and keyword not in topics:
                        topics.append(keyword)
        return topics


class PerfectFeedbackAPI(APIView):
    """Perfect feedback system with memory integration - FIXED"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id=None):
        """Submit feedback with perfect memory integration - FIXED"""
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
            
            # Create or update feedback with memory context
            feedback, created = FeedbackRating.objects.update_or_create(
                chat_message=chat_message,
                user=request.user,
                defaults={
                    'helpfulness_rating': int(rating),
                    'feedback_text': feedback_text,
                    'issues_reported': issues if isinstance(issues, list) else []
                }
            )
            
            # Update message feedback status with perfect memory learning
            if int(rating) >= 4:
                chat_message.user_feedback = 'helpful'
                feedback_category = 'positive'
            elif int(rating) >= 2:
                chat_message.user_feedback = 'partial'
                feedback_category = 'neutral'
            else:
                chat_message.user_feedback = 'not_helpful'
                feedback_category = 'negative'
            
            chat_message.save()
            
            # Learn from feedback for perfect memory system
            try:
                self._learn_from_feedback(chat_message, feedback, feedback_category)
            except Exception as learning_error:
                logger.error(f"Error learning from feedback: {learning_error}")
            
            # Generate personalized thank you response
            thank_you_response = self._generate_personalized_thank_you(
                request.user, int(rating), feedback_text, feedback_category
            )
            
            return Response({
                'message': thank_you_response,
                'rating': rating,
                'created': created,
                'feedback_id': feedback.id,
                'memory_updated': True,
                'learning_applied': True
            })
            
        except Exception as e:
            logger.error(f"Perfect feedback submission error: {e}")
            return Response({
                "error": "Thank you for trying to give feedback! I couldn't process it right now, but I appreciate your input and I'm always learning to serve you better! 🌟",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)

    def _learn_from_feedback(self, chat_message, feedback, feedback_category):
        """Learn from feedback to improve future responses - FIXED"""
        try:
            # Update conversation context based on feedback
            session = chat_message.session
            context, created = ConversationContext.objects.get_or_create(
                session=session,
                defaults={'current_intent': 'feedback_learning'}
            )
            
            # Track feedback patterns safely
            feedback_data = context.preferences_collected or {}
            if not isinstance(feedback_data, dict):
                feedback_data = {}
            
            if 'feedback_history' not in feedback_data:
                feedback_data['feedback_history'] = []
            
            feedback_entry = {
                'rating': feedback.helpfulness_rating,
                'category': feedback_category,
                'issues': feedback.issues_reported if isinstance(feedback.issues_reported, list) else [],
                'message_type': chat_message.message_type,
                'had_search_results': bool(chat_message.search_results_data),
                'timestamp': datetime.now().isoformat()
            }
            
            feedback_data['feedback_history'].append(feedback_entry)
            
            # Keep only last 10 feedback entries
            feedback_data['feedback_history'] = feedback_data['feedback_history'][-10:]
            
            # Extract learning insights
            if feedback_category == 'negative':
                # Learn what went wrong
                if 'learning_insights' not in feedback_data:
                    feedback_data['learning_insights'] = {}
                
                feedback_data['learning_insights']['last_negative_feedback'] = {
                    'user_input': chat_message.user_input or '',
                    'bot_response_length': len(chat_message.bot_response or ''),
                    'issues_reported': feedback.issues_reported if isinstance(feedback.issues_reported, list) else [],
                    'search_results_provided': len(chat_message.search_results_data.get('products', [])) if chat_message.search_results_data else 0
                }
            
            elif feedback_category == 'positive':
                # Learn what worked well
                if 'success_patterns' not in feedback_data:
                    feedback_data['success_patterns'] = {}
                
                feedback_data['success_patterns']['last_positive_feedback'] = {
                    'user_input': chat_message.user_input or '',
                    'response_approach': 'successful',
                    'message_type': chat_message.message_type,
                    'search_results_count': len(chat_message.search_results_data.get('products', [])) if chat_message.search_results_data else 0
                }
            
            context.preferences_collected = feedback_data
            context.save()
            
            # Update user preferences based on feedback
            try:
                self._update_user_preferences_from_feedback(chat_message.session.user, feedback, feedback_category)
            except Exception as prefs_error:
                logger.error(f"Error updating user preferences from feedback: {prefs_error}")
            
        except Exception as e:
            logger.error(f"Learning from feedback error: {e}")

    def _generate_personalized_thank_you(self, user, rating, feedback_text, feedback_category):
        """Generate personalized thank you response - FIXED"""
        try:
            # Get user's conversation history for personalization
            total_messages = ChatMessage.objects.filter(session__user=user).count()
            
            if feedback_category == 'positive':
                if total_messages > 10:
                    return f"Thank you so much! 🌟 I love helping you find what you need - that's what makes our {total_messages} conversations so rewarding! I'll keep learning your preferences to serve you even better!"
                else:
                    return "Thank you! 🌟 I'm so glad I could help you! I'm always learning and improving to make your Finda shopping experience amazing!"
            
            elif feedback_category == 'neutral':
                return f"Thanks for the feedback! 💭 I hear you - I'm always working to improve. With {total_messages} conversations under our belt, I'm getting better at understanding exactly what you need!"
            
            else:  # negative
                if feedback_text:
                    return "Thank you for the honest feedback! 🙏 I really appreciate you taking the time to help me improve. I'm learning from this to serve you better in our future conversations!"
                else:
                    return "I appreciate your feedback! 🙏 I'm always learning and this helps me understand how to better assist you. Let's keep working together to find exactly what you need!"
        except Exception as e:
            logger.error(f"Error generating thank you response: {e}")
            return "Thank you for your feedback! I'm always learning to serve you better! 🌟"

    def _update_user_preferences_from_feedback(self, user, feedback, feedback_category):
        """Update user preferences based on feedback patterns - FIXED"""
        try:
            user_prefs, created = UserPreference.objects.get_or_create(user=user)
            
            feedback_text = feedback.feedback_text or ''
            
            # Adjust response style based on feedback
            if feedback_category == 'negative' and 'too detailed' in feedback_text.lower():
                user_prefs.response_style = 'brief'
            elif feedback_category == 'negative' and 'more detail' in feedback_text.lower():
                user_prefs.response_style = 'detailed'
            elif feedback_category == 'positive':
                # Keep current style if it's working
                pass
            
            # Adjust external sources preference based on feedback
            if 'external' in feedback_text.lower():
                if feedback_category == 'positive':
                    user_prefs.external_sources_preference = True
                elif feedback_category == 'negative':
                    user_prefs.external_sources_preference = False
            
            user_prefs.save()
            
        except Exception as e:
            logger.error(f"Error updating preferences from feedback: {e}")


# Additional APIs for perfect memory system - FIXED

class PerfectAnalyticsAPI(APIView):
    """Perfect analytics with memory intelligence - FIXED"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get perfect analytics with memory insights - FIXED"""
        try:
            user = request.user
            
            # Build comprehensive analytics safely
            analytics_data = {
                'user_journey': self._analyze_user_journey(user),
                'conversation_intelligence': self._analyze_conversation_intelligence_analytics(user),
                'memory_effectiveness': self._analyze_memory_effectiveness(user),
                'satisfaction_evolution': self._analyze_satisfaction_evolution(user),
                'personalization_score': self._calculate_personalization_score(user),
                'ai_learning_progress': self._analyze_ai_learning_progress(user)
            }
            
            return Response(analytics_data)
            
        except Exception as e:
            logger.error(f"Perfect analytics error: {e}")
            return Response({
                "error": "I'm analyzing your conversation patterns to serve you better! Please try again in a moment.",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)

    def _analyze_user_journey(self, user):
        """Analyze complete user journey - FIXED"""
        try:
            sessions = ChatSession.objects.filter(user=user).order_by('created_at')
            messages = ChatMessage.objects.filter(session__user=user).order_by('timestamp')
            
            return {
                'total_sessions': sessions.count(),
                'total_messages': messages.count(),
                'journey_start': sessions.first().created_at.isoformat() if sessions.exists() else None,
                'last_interaction': messages.last().timestamp.isoformat() if messages.exists() else None,
                'engagement_trend': self._calculate_engagement_trend(sessions),
                'topic_evolution': self._analyze_topic_evolution(messages),
                'milestone_achievements': self._identify_milestones(user)
            }
        except Exception as e:
            logger.error(f"Error analyzing user journey: {e}")
            return {'error': 'Analysis unavailable'}

    def _analyze_conversation_intelligence_analytics(self, user):
        """Analyze AI's conversation intelligence with this user - FIXED"""
        try:
            messages = ChatMessage.objects.filter(session__user=user).order_by('timestamp')
            
            return {
                'response_time_trend': self._analyze_response_time_trend(messages),
                'topic_change_handling': self._analyze_topic_change_handling(messages),
                'confusion_resolution': self._analyze_confusion_resolution(messages),
                'personalization_accuracy': self._analyze_personalization_accuracy(messages),
                'search_success_rate': self._calculate_search_success_rate(messages)
            }
        except Exception as e:
            logger.error(f"Error analyzing conversation intelligence: {e}")
            return {'error': 'Analysis unavailable'}

    def _analyze_memory_effectiveness(self, user):
        """Analyze how effective the memory system is - FIXED"""
        try:
            contexts = ConversationContext.objects.filter(session__user=user)
            
            memory_score = 0
            total_factors = 0
            
            for context in contexts:
                # Score based on preferences collected
                if context.preferences_collected and isinstance(context.preferences_collected, dict):
                    memory_score += len(context.preferences_collected)
                    total_factors += 1
                
                # Score based on successful interactions
                bounce_count = getattr(context, 'bounce_count', 0) or 0
                if bounce_count < 2:  # Low topic changes indicate good memory
                    memory_score += 2
                    total_factors += 1
            
            return {
                'memory_effectiveness_score': memory_score / total_factors if total_factors > 0 else 0,
                'preferences_learned': self._count_total_preferences_learned(user),
                'conversation_continuity': self._assess_conversation_continuity(user),
                'context_retention': self._assess_context_retention(user)
            }
        except Exception as e:
            logger.error(f"Error analyzing memory effectiveness: {e}")
            return {'error': 'Analysis unavailable'}

    def _analyze_satisfaction_evolution(self, user):
        """Analyze how user satisfaction has evolved - FIXED"""
        try:
            feedback_ratings = FeedbackRating.objects.filter(user=user).order_by('created_at')
            
            if not feedback_ratings.exists():
                return {'status': 'insufficient_data'}
            
            ratings = list(feedback_ratings.values_list('helpfulness_rating', flat=True))
            
            return {
                'current_satisfaction': ratings[-1] if ratings else 0,
                'satisfaction_trend': self._calculate_satisfaction_trend_detailed(ratings),
                'improvement_areas': self._identify_improvement_areas(feedback_ratings),
                'success_factors': self._identify_success_factors(feedback_ratings)
            }
        except Exception as e:
            logger.error(f"Error analyzing satisfaction evolution: {e}")
            return {'error': 'Analysis unavailable'}

    def _calculate_personalization_score(self, user):
        """Calculate how well personalized the experience is - FIXED"""
        try:
            base_score = 0.0
            
            # Check if user has preferences
            try:
                user_prefs = UserPreference.objects.get(user=user)
                base_score = 0.3  # Has preferences
            except UserPreference.DoesNotExist:
                base_score = 0.0
            
            # Add score based on conversation history
            messages = ChatMessage.objects.filter(session__user=user)
            if messages.count() > 10:
                base_score += 0.3  # Long relationship
            
            # Add score based on memory utilization
            contexts = ConversationContext.objects.filter(session__user=user)
            if contexts.exists():
                total_prefs = 0
                for context in contexts:
                    if context.preferences_collected and isinstance(context.preferences_collected, dict):
                        total_prefs += len(context.preferences_collected)
                
                avg_preferences = total_prefs / contexts.count()
                if avg_preferences > 3:
                    base_score += 0.4  # Good memory utilization
            
            return min(base_score, 1.0)
        except Exception as e:
            logger.error(f"Error calculating personalization score: {e}")
            return 0.5

    def _analyze_ai_learning_progress(self, user):
        """Analyze how much the AI has learned about this user - FIXED"""
        try:
            learning_metrics = {
                'communication_style_learned': False,
                'shopping_preferences_learned': False,
                'decision_making_pattern_learned': False,
                'response_style_preference_learned': False
            }
            
            # Check if communication style is learned
            messages = ChatMessage.objects.filter(session__user=user)
            if messages.count() > 5:
                learning_metrics['communication_style_learned'] = True
            
            # Check if shopping preferences are learned
            try:
                user_prefs = UserPreference.objects.get(user=user)
                if (user_prefs.preferred_categories and len(user_prefs.preferred_categories) > 0) or \
                   (user_prefs.preferred_brands and len(user_prefs.preferred_brands) > 0):
                    learning_metrics['shopping_preferences_learned'] = True
            except UserPreference.DoesNotExist:
                pass
            
            # Check decision making pattern
            contexts = ConversationContext.objects.filter(session__user=user)
            if contexts.exists():
                for context in contexts:
                    if context.preferences_collected and isinstance(context.preferences_collected, dict):
                        if len(context.preferences_collected) > 0:
                            learning_metrics['decision_making_pattern_learned'] = True
                            break
            
            # Check response style preference
            feedback_ratings = FeedbackRating.objects.filter(user=user)
            if feedback_ratings.exists():
                learning_metrics['response_style_preference_learned'] = True
            
            return {
                'learning_metrics': learning_metrics,
                'overall_learning_score': sum(learning_metrics.values()) / len(learning_metrics),
                'next_learning_opportunities': self._identify_learning_opportunities_analytics(user)
            }
        except Exception as e:
            logger.error(f"Error analyzing AI learning progress: {e}")
            return {'error': 'Analysis unavailable'}

    # Additional helper methods for analytics - SIMPLIFIED VERSIONS

    def _calculate_engagement_trend(self, sessions):
        """Calculate user engagement trend - FIXED"""
        try:
            if sessions.count() < 2:
                return 'insufficient_data'
            
            # Simple engagement analysis
            total_sessions = sessions.count()
            if total_sessions > 5:
                return 'high_engagement'
            elif total_sessions > 2:
                return 'moderate_engagement'
            else:
                return 'new_user'
        except Exception:
            return 'unknown'

    def _analyze_topic_evolution(self, messages):
        """Analyze topic evolution - SIMPLIFIED"""
        try:
            topics = []
            for msg in messages[:10]:  # Analyze first 10 messages
                if hasattr(msg, 'user_input') and msg.user_input:
                    content = msg.user_input.lower()
                    if 'phone' in content:
                        topics.append('electronics')
                    elif 'clothes' in content:
                        topics.append('fashion')
                    elif 'food' in content:
                        topics.append('food')
            
            return list(set(topics))
        except Exception:
            return []

    def _identify_milestones(self, user):
        """Identify user milestones - SIMPLIFIED"""
        try:
            milestones = []
            
            # Message count milestones
            message_count = ChatMessage.objects.filter(session__user=user).count()
            if message_count >= 50:
                milestones.append('frequent_user')
            elif message_count >= 10:
                milestones.append('engaged_user')
            elif message_count >= 1:
                milestones.append('first_interaction')
            
            # Feedback milestones
            feedback_count = FeedbackRating.objects.filter(user=user).count()
            if feedback_count >= 5:
                milestones.append('feedback_contributor')
            
            return milestones
        except Exception:
            return []

    def _count_total_preferences_learned(self, user):
        """Count total preferences learned - SIMPLIFIED"""
        try:
            count = 0
            
            # Count explicit preferences
            try:
                user_prefs = UserPreference.objects.get(user=user)
                if user_prefs.preferred_categories:
                    count += len(user_prefs.preferred_categories)
                if user_prefs.preferred_brands:
                    count += len(user_prefs.preferred_brands)
            except UserPreference.DoesNotExist:
                pass
            
            return count
        except Exception:
            return 0

    def _assess_conversation_continuity(self, user):
        """Assess conversation continuity - SIMPLIFIED"""
        try:
            sessions = ChatSession.objects.filter(user=user)
            if sessions.count() > 1:
                return 'good_continuity'
            else:
                return 'single_session'
        except Exception:
            return 'unknown'

    def _assess_context_retention(self, user):
        """Assess context retention - SIMPLIFIED"""
        try:
            contexts = ConversationContext.objects.filter(session__user=user)
            if contexts.exists():
                return 'active_retention'
            else:
                return 'no_retention'
        except Exception:
            return 'unknown'

    def _identify_learning_opportunities_analytics(self, user):
        """Identify learning opportunities - SIMPLIFIED"""
        try:
            opportunities = []
            
            try:
                user_prefs = UserPreference.objects.get(user=user)
                if not user_prefs.preferred_categories:
                    opportunities.append('product_categories')
                if not user_prefs.preferred_price_range:
                    opportunities.append('price_preferences')
                if not user_prefs.preferred_locations:
                    opportunities.append('location_preferences')
            except UserPreference.DoesNotExist:
                opportunities.extend(['basic_preferences', 'shopping_style', 'communication_preferences'])
            
            # Check conversation patterns
            messages = ChatMessage.objects.filter(session__user=user)
            if messages.count() < 10:
                opportunities.append('conversation_history')
            
            feedback_count = FeedbackRating.objects.filter(user=user).count()
            if feedback_count < 3:
                opportunities.append('feedback_patterns')
            
            return opportunities
        except Exception:
            return ['general_learning']

    # Simplified helper methods for analytics
    def _analyze_response_time_trend(self, messages):
        """Simplified response time analysis"""
        try:
            total_time = sum(msg.response_time_ms or 0 for msg in messages if msg.response_time_ms)
            count = sum(1 for msg in messages if msg.response_time_ms)
            avg_time = total_time / count if count > 0 else 1000
            
            if avg_time < 2000:
                return 'fast'
            elif avg_time < 5000:
                return 'moderate'
            else:
                return 'slow'
        except Exception:
            return 'unknown'

    def _analyze_topic_change_handling(self, messages):
        """Simplified topic change handling analysis"""
        return 'good' if messages.count() > 5 else 'learning'

    def _analyze_confusion_resolution(self, messages):
        """Simplified confusion resolution analysis"""
        return 'effective' if messages.count() > 3 else 'developing'

    def _analyze_personalization_accuracy(self, messages):
        """Simplified personalization accuracy analysis"""
        return 'high' if messages.count() > 10 else 'moderate'

    def _calculate_search_success_rate(self, messages):
        """Simplified search success rate calculation"""
        try:
            messages_with_results = sum(1 for msg in messages if msg.search_results_data)
            total_messages = messages.count()
            return messages_with_results / total_messages if total_messages > 0 else 0
        except Exception:
            return 0

    def _calculate_satisfaction_trend_detailed(self, ratings):
        """Simplified satisfaction trend calculation"""
        if len(ratings) < 2:
            return 'insufficient_data'
        
        recent = sum(ratings[-3:]) / len(ratings[-3:])
        overall = sum(ratings) / len(ratings)
        
        if recent > overall:
            return 'improving'
        elif recent < overall:
            return 'declining'
        else:
            return 'stable'

    def _identify_improvement_areas(self, feedback_ratings):
        """Simplified improvement areas identification"""
        return ['response_speed', 'search_accuracy'] if feedback_ratings.count() < 5 else []

    def _identify_success_factors(self, feedback_ratings):
        """Simplified success factors identification"""
        return ['personalization', 'helpfulness'] if feedback_ratings.count() > 3 else []


# Health check and system endpoints with perfect AI integration - FIXED

@api_view(['GET'])
@permission_classes([AllowAny])
def perfect_ai_health_check(request):
    """Health check for perfect AI system - FIXED"""
    try:
        # Test perfect AI client safely
        try:
            test_result = enhanced_gemini_client.process_perfect_conversation(
                user_message="Hello",
                user_id=0,
                session_id="test",
                conversation_history=[],
                user_profile={},
                image_data=None,
                context_data={}
            )
            
            ai_status = "healthy" if test_result.get('response') else "degraded"
            ai_response_sample = test_result.get('response', '')[:100] if test_result.get('response') else None
        except Exception as ai_test_error:
            logger.error(f"AI health check error: {ai_test_error}")
            ai_status = "degraded"
            ai_response_sample = None
        
        return Response({
            'status': 'healthy',
            'perfect_ai_status': ai_status,
            'memory_system_status': 'active',
            'conversation_intelligence_status': 'active',
            'database_status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'ai_response_sample': ai_response_sample,
            'memory_features': [
                'perfect_conversation_memory',
                'user_profile_intelligence', 
                'dynamic_adaptation',
                'context_awareness',
                'personalized_responses'
            ]
        })
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'fallback_mode': 'active'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_perfect_memory(request, session_id):
    """Reset perfect memory for a session (with user consent) - FIXED"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        # Confirm user wants to reset (this is permanent)
        confirm = request.data.get('confirm_reset', False)
        if not confirm:
            return Response({
                'message': 'Are you sure you want to reset our conversation memory? This will make me forget our previous conversations and start fresh.',
                'action_required': 'Send confirm_reset: true to proceed',
                'warning': 'This action cannot be undone'
            })
        
        # Reset session memory safely
        try:
            session.preference_data = {}
            session.awaiting_external_confirmation = False
            session.last_search_query = None
            session.last_search_type = None
            session.save()
        except Exception as session_reset_error:
            logger.error(f"Error resetting session: {session_reset_error}")
        
        # Reset conversation context safely
        try:
            context, created = ConversationContext.objects.get_or_create(
                session=session,
                defaults={
                    'current_intent': 'greeting',
                    'questions_asked': [],
                    'preferences_collected': {},
                    'missing_preferences': [],
                    'last_search_results_internal': [],
                    'external_sources_shown': False,
                    'bounce_count': 0,
                    'refinement_count': 0
                }
            )
            
            if not created:
                context.current_intent = 'greeting'
                context.questions_asked = []
                context.preferences_collected = {}
                context.missing_preferences = []
                context.last_search_results_internal = []
                context.external_sources_shown = False
                context.bounce_count = 0
                context.refinement_count = 0
                context.save()
        except Exception as context_reset_error:
            logger.error(f"Error resetting context: {context_reset_error}")
        
        return Response({
            'message': 'Perfect! Our conversation memory has been reset. Hi there! I\'m Finda AI, and I\'m excited to get to know you and help you find amazing products and services! 🌟',
            'session_id': str(session.id),
            'memory_status': 'reset_complete',
            'new_conversation_started': True
        })
        
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
    except Exception as e:
        logger.error(f"Perfect memory reset error: {e}")
        return Response({
            "error": "I couldn't reset our memory right now, but I'm still here to help you! 💫",
            "detail": str(e) if request.user.is_staff else None
        }, status=500)


# Legacy endpoint redirects for backward compatibility
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_api(request):
    """Legacy chat API - redirects to Perfect AI - FIXED"""
    perfect_chat = PerfectAIChatAPI()
    return perfect_chat.post(request)


# Main URL endpoints - FIXED
class UserPreferencesAPI(APIView):
    """Enhanced preferences API with perfect memory integration - FIXED"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user preferences with AI insights - FIXED"""
        try:
            user = request.user
            
            # Get explicit preferences safely
            try:
                preferences = UserPreference.objects.get(user=user)
                preferences_data = UserPreferenceSerializer(preferences).data
            except UserPreference.DoesNotExist:
                preferences_data = {}
            except Exception as prefs_error:
                logger.error(f"Error getting preferences: {prefs_error}")
                preferences_data = {}
            
            # Get AI-learned preferences from conversations safely
            try:
                ai_learned_preferences = self._extract_ai_learned_preferences(user)
            except Exception as ai_prefs_error:
                logger.error(f"Error extracting AI preferences: {ai_prefs_error}")
                ai_learned_preferences = {}
            
            # Get recommendation for missing preferences safely
            try:
                perfect_chat_api = PerfectAIChatAPI()
                missing_preferences = perfect_chat_api._identify_missing_preferences(user)
            except Exception as missing_error:
                logger.error(f"Error identifying missing preferences: {missing_error}")
                missing_preferences = []
            
            # Calculate personalization score safely
            try:
                analytics_api = PerfectAnalyticsAPI()
                personalization_score = analytics_api._calculate_personalization_score(user)
            except Exception as score_error:
                logger.error(f"Error calculating personalization score: {score_error}")
                personalization_score = 0.5
            
            return Response({
                'explicit_preferences': preferences_data,
                'ai_learned_preferences': ai_learned_preferences,
                'missing_preferences': missing_preferences,
                'personalization_score': personalization_score,
                'recommendation': 'Your AI assistant is learning your preferences through our conversations to serve you better! 🧠✨'
            })
            
        except Exception as e:
            logger.error(f"Enhanced preferences retrieval error: {e}")
            return Response({
                "error": "I'm analyzing your preferences to serve you better! Please try again.",
                "detail": str(e) if request.user.is_staff else None
            }, status=500)
    # Fix for the PerfectAIChatAPI.post() method - Replace the existing method with this corrected version

    def post(self, request):
        """Perfect AI endpoint that handles ALL conversation scenarios - FIXED"""
        user = request.user
        start_time = time.time()
        session = None  # Initialize session variable
        
        try:
            # Get or create session with perfect memory
            session = self._get_or_create_session_with_memory(user, request.data.get('session_id'))
            
            # Build complete conversation history
            conversation_history = self._build_complete_conversation_history(session)
            
            # Build comprehensive user profile
            user_profile = self._build_comprehensive_user_profile(user, session)
            
            # Determine message type and content
            message_content, message_type, image_data = self._extract_message_content(request)
            
            if not message_content and not image_data:
                return Response({
                    "error": "Please send a message, image, or voice note!",
                    "session_id": str(session.id),
                    "suggestion": "I'm here to help you find amazing products and services on Finda! 🛍️"
                }, status=400)
            
            # Get current context data
            context_data = self._get_current_context_data(session)
            
            # Process with Perfect AI - FIXED: Now handles errors properly
            try:
                ai_result = enhanced_gemini_client.process_perfect_conversation(
                    user_message=message_content,
                    user_id=user.id,
                    session_id=str(session.id),
                    conversation_history=conversation_history,
                    user_profile=user_profile,
                    image_data=image_data,
                    context_data=context_data
                )
            except Exception as ai_error:
                logger.error(f"AI processing error: {ai_error}")
                # Create fallback response
                ai_result = {
                    'response': self._create_fallback_ai_response(user, conversation_history),
                    'message_analysis': {'error': str(ai_error), 'fallback_used': True},
                    'search_results': {'products': [], 'services': [], 'categories': []},
                    'updated_context': {},
                    'memory_updates': {},
                    'conversation_intelligence': {'status': 'fallback_mode'},
                    'next_conversation_guidance': ['ask_for_clarification'],
                    'user_satisfaction_prediction': 0.5,
                    'personality_insights': {}
                }
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Save message with perfect memory updates
            chat_message = self._save_message_with_memory(
                session=session,
                user_input=message_content,
                message_type=message_type,
                ai_result=ai_result,
                response_time_ms=response_time_ms,
                image_data=image_data,
                request=request
            )
            
            # Update perfect memory system
            try:
                self._update_perfect_memory_system(session, user, ai_result)
            except Exception as memory_error:
                logger.error(f"Memory update error: {memory_error}")
                # Continue without failing the response
            
            # Generate response with perfect intelligence
            return Response({
                "reply": ai_result['response'],
                "session_id": str(session.id),
                "message_id": chat_message.id,
                "timestamp": chat_message.timestamp,
                "message_analysis": ai_result.get('message_analysis', {}),
                "conversation_intelligence": ai_result.get('conversation_intelligence', {}),
                "user_satisfaction_prediction": ai_result.get('user_satisfaction_prediction', 0.8),
                "next_conversation_guidance": ai_result.get('next_conversation_guidance', []),
                "personality_insights": ai_result.get('personality_insights', {}),
                "search_results_found": len(ai_result.get('search_results', {}).get('products', [])),
                "response_time_ms": response_time_ms,
                "ai_confidence": ai_result.get('message_analysis', {}).get('intent_analysis', {}).get('intent_confidence', 0.85),
                "memory_updated": bool(ai_result.get('memory_updates')),
                "transcribed_text": ai_result.get('transcribed_text') if message_type == 'voice' else None,
                "system_status": "healthy" if not ai_result.get('message_analysis', {}).get('fallback_used') else "fallback_mode"
            })
            
        except Exception as e:
            logger.error(f"Perfect AI chat processing error: {e}")
            # FIXED: Return proper Response object instead of dictionary
            return self._create_perfect_error_response(session, str(e), user)
    
    
    def _extract_ai_learned_preferences(self, user):
        """Extract preferences AI has learned from conversations - FIXED"""
        try:
            learned_prefs = {}
            
            # Get preferences from conversation contexts safely
            contexts = ConversationContext.objects.filter(session__user=user)
            for context in contexts:
                try:
                    if context.preferences_collected and isinstance(context.preferences_collected, dict):
                        for key, value in context.preferences_collected.items():
                            if key not in learned_prefs:
                                learned_prefs[key] = []
                            if isinstance(value, list):
                                learned_prefs[key].extend(value)
                            elif value:  # Any truthy value
                                learned_prefs[key].append(str(value))
                except Exception as context_error:
                    logger.error(f"Error processing context preferences: {context_error}")
                    continue
            
            # Clean up duplicates
            for key, values in learned_prefs.items():
                if isinstance(values, list):
                    learned_prefs[key] = list(set(values))
            
            return learned_prefs
        except Exception as e:
            logger.error(f"Error extracting AI learned preferences: {e}")
            return {}

    def _generate_preferences_confirmation(self, user, updated_data, created):
        """Generate personalized confirmation message - FIXED"""
        try:
            total_conversations = ChatMessage.objects.filter(session__user=user).count()
            
            if created:
                return f"Perfect! I've saved your preferences and I'll remember them in all our future conversations! 🎯 With {total_conversations} messages already exchanged, I'm excited to serve you even better!"
            else:
                return f"Got it! I've updated your preferences in my perfect memory system. 🧠✨ I'll use these insights along with everything I've learned from our {total_conversations} conversations to help you better!"
        except Exception as e:
            logger.error(f"Error generating confirmation message: {e}")
            return "Perfect! I've updated your preferences and I'll remember them in our future conversations! 🎯"


    # Export the main chat API class for URL configuration
    __all__ = [
        'PerfectAIChatAPI', 
        'PerfectExternalSearchAPI', 
        'PerfectFeedbackAPI',
        'PerfectAnalyticsAPI',
        'UserPreferencesAPI',
        'perfect_ai_health_check',
        'reset_perfect_memory',
        'chat_api'
    ]

    # ... (rest of code continues here)

    def process_chat_error(self, session, e, user):
        """Process chat error and return appropriate response"""
        logger.error(f"Perfect AI chat processing error: {e}")
        return self._create_perfect_error_response(session, str(e), user)

    def _create_fallback_ai_response(self, user, conversation_history):
        """Create a fallback AI response when main processing fails"""
        total_conversations = len(conversation_history) if conversation_history else 0
        
        if total_conversations > 0:
            return "I remember our previous conversations! I'm having a small technical moment, but I'm still here to help you find amazing products on Finda. What are you looking for today? 🛍️"
        else:
            return "Welcome to Finda AI! I'm excited to help you discover amazing products and services. I'm having a small technical hiccup, but I'm ready to assist you. What are you looking for? 🌟"

    def _get_or_create_session_with_memory(self, user, session_id=None):
        """Get or create session with perfect memory initialization - FIXED"""
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=user)
                # Update session activity
                session.updated_at = datetime.now()
                session.save()
                return session
            except ChatSession.DoesNotExist:
                logger.warning(f"Session {session_id} not found, creating new session")
        
        # Create new session with memory initialization
        try:
            session = ChatSession.objects.create(
                user=user,
                preference_data=self._initialize_session_preferences(user)
            )
            
            # Initialize conversation context with memory
            ConversationContext.objects.get_or_create(
                session=session,
                defaults={
                    'current_intent': 'greeting',
                    'preferences_collected': self._get_user_known_preferences(user),
                    'questions_asked': [],
                    'missing_preferences': self._identify_missing_preferences(user)
                }
            )
            
            return session
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            # If all else fails, create a minimal session
            return ChatSession.objects.create(user=user, preference_data={})

    def _build_complete_conversation_history(self, session):
        """Build complete conversation history for perfect memory - FIXED"""
        try:
            messages = ChatMessage.objects.filter(session=session).order_by('timestamp')
            
            history = []
            for msg in messages:
                # Add user message
                history.append({
                    'author': 'user',
                    'content': msg.user_input or '',
                    'type': msg.message_type or 'text',
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else datetime.now().isoformat(),
                    'feedback': msg.user_feedback,
                    'has_image': bool(msg.image_file),
                    'has_audio': bool(msg.audio_file)
                })
                
                # Add AI response
                history.append({
                    'author': 'assistant',
                    'content': msg.bot_response or '',
                    'type': 'text',
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else datetime.now().isoformat(),
                    'search_results_provided': bool(msg.search_results_data),
                    'external_sources_offered': msg.external_sources_offered,
                    'response_time_ms': msg.response_time_ms or 0
                })
            
            return history
        except Exception as e:
            logger.error(f"Error building conversation history: {e}")
            return []

    def _build_comprehensive_user_profile(self, user, session):
        """Build comprehensive user profile for perfect AI - FIXED"""
        profile = {
            'user_basic_info': {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'date_joined': user.date_joined.isoformat() if user.date_joined else datetime.now().isoformat(),
                'total_sessions': 0,
                'total_messages': 0
            },
            'preferences': {},
            'shopping_history': {},
            'interaction_patterns': {},
            'satisfaction_metrics': {}
        }
        
        try:
            # Get session and message counts safely
            profile['user_basic_info']['total_sessions'] = ChatSession.objects.filter(user=user).count()
            profile['user_basic_info']['total_messages'] = ChatMessage.objects.filter(session__user=user).count()
            
            # Get user preferences safely
            try:
                user_prefs = UserPreference.objects.get(user=user)
                profile['preferences'] = {
                    'categories': user_prefs.preferred_categories or [],
                    'price_range': user_prefs.preferred_price_range or {},
                    'locations': user_prefs.preferred_locations or [],
                    'brands': user_prefs.preferred_brands or [],
                    'language': user_prefs.preferred_language or 'en',
                    'response_style': user_prefs.response_style or 'balanced',
                    'voice_enabled': user_prefs.voice_enabled or False,
                    'image_search_enabled': user_prefs.image_search_enabled or False,
                    'external_sources_preference': user_prefs.external_sources_preference or True
                }
            except UserPreference.DoesNotExist:
                profile['preferences'] = {}
            
            # Analyze shopping history safely
            try:
                search_queries = SearchQuery.objects.filter(user=user).order_by('-created_at')[:20]
                if search_queries.exists():
                    satisfied_count = search_queries.filter(user_satisfied=True).count()
                    total_count = search_queries.count()
                    
                    profile['shopping_history'] = {
                        'recent_searches': [sq.original_query for sq in search_queries[:5] if sq.original_query],
                        'search_categories': list(set([sq.search_type for sq in search_queries if sq.search_type])),
                        'satisfaction_rate': satisfied_count / total_count if total_count > 0 else 0.5,
                        'external_requests': search_queries.filter(external_sources_requested=True).count()
                    }
            except Exception as e:
                logger.error(f"Error analyzing shopping history: {e}")
                profile['shopping_history'] = {}
            
            # Analyze interaction patterns safely
            try:
                recent_messages = ChatMessage.objects.filter(session__user=user).order_by('-timestamp')[:50]
                if recent_messages.exists():
                    profile['interaction_patterns'] = {
                        'preferred_message_type': self._get_preferred_message_type(recent_messages),
                        'average_session_length': self._calculate_average_session_length(user),
                        'response_engagement': self._calculate_response_engagement(recent_messages),
                        'topic_consistency': self._analyze_topic_consistency(recent_messages)
                    }
            except Exception as e:
                logger.error(f"Error analyzing interaction patterns: {e}")
                profile['interaction_patterns'] = {}
            
            # Get satisfaction metrics safely
            try:
                feedback_ratings = FeedbackRating.objects.filter(user=user)
                if feedback_ratings.exists():
                    avg_rating = feedback_ratings.aggregate(avg=Avg('helpfulness_rating'))['avg']
                    profile['satisfaction_metrics'] = {
                        'average_rating': avg_rating or 3.5,
                        'total_feedback_given': feedback_ratings.count(),
                        'common_issues': [],  # Simplified for now
                        'improvement_trend': self._calculate_satisfaction_trend(feedback_ratings)
                    }
            except Exception as e:
                logger.error(f"Error analyzing satisfaction metrics: {e}")
                profile['satisfaction_metrics'] = {}
        
        except Exception as e:
            logger.error(f"Error building user profile: {e}")
            # Return minimal profile on error
            profile = {
                'user_basic_info': {'user_id': user.id, 'username': user.username},
                'preferences': {},
                'shopping_history': {},
                'interaction_patterns': {},
                'satisfaction_metrics': {}
            }
        
        return profile

    def _extract_message_content(self, request):
        """Extract message content and determine type - FIXED"""
        message_content = ""
        message_type = "text"
        image_data = None
        
        try:
            # Handle voice message
            if 'audio' in request.FILES:
                audio_file = request.FILES['audio']
                validation = validate_audio_file(audio_file)
                if validation['is_valid']:
                    try:
                        message_content = process_voice_to_text(audio_file)
                        message_type = "voice"
                    except Exception as voice_error:
                        logger.error(f"Voice processing error: {voice_error}")
                        message_content = "Voice message received"
                        message_type = "voice"
                else:
                    raise ValueError(f"Invalid audio file: {validation['errors']}")
            
            # Handle image message
            elif 'image' in request.FILES:
                image_file = request.FILES['image']
                validation = validate_image_file(image_file)
                if validation['is_valid']:
                    try:
                        image_data = image_file.read()
                        image_file.seek(0)  # Reset file pointer
                        message_content = request.data.get('message', 'Image search')
                        message_type = "image"
                    except Exception as image_error:
                        logger.error(f"Image processing error: {image_error}")
                        message_content = "Image received"
                        message_type = "image"
                else:
                    raise ValueError(f"Invalid image file: {validation['errors']}")
            
            # Handle text message
            else:
                message_content = request.data.get('message', '').strip()
                message_type = "text"
            
            return message_content, message_type, image_data
            
        except Exception as e:
            logger.error(f"Error extracting message content: {e}")
            # Return safe defaults
            return request.data.get('message', 'Hello'), 'text', None

    def _get_current_context_data(self, session):
        """Get current context data for the session - FIXED"""
        try:
            context = ConversationContext.objects.get(session=session)
            return {
                'current_intent': context.current_intent or 'greeting',
                'questions_asked': context.questions_asked or [],
                'preferences_collected': context.preferences_collected or {},
                'missing_preferences': context.missing_preferences or [],
                'last_search_results_internal': context.last_search_results_internal or [],
                'external_sources_shown': context.external_sources_shown or False,
                'bounce_count': context.bounce_count or 0,
                'refinement_count': context.refinement_count or 0
            }
        except ConversationContext.DoesNotExist:
            # Create default context
            try:
                ConversationContext.objects.create(
                    session=session,
                    current_intent='greeting',
                    questions_asked=[],
                    preferences_collected={},
                    missing_preferences=[]
                )
            except Exception as e:
                logger.error(f"Error creating conversation context: {e}")
            
            return {
                'current_intent': 'greeting',
                'questions_asked': [],
                'preferences_collected': {},
                'missing_preferences': [],
                'last_search_results_internal': [],
                'external_sources_shown': False,
                'bounce_count': 0,
                'refinement_count': 0
            }
        except Exception as e:
            logger.error(f"Error getting context data: {e}")
            return {
                'current_intent': 'greeting',
                'questions_asked': [],
                'preferences_collected': {},
                'missing_preferences': [],
                'last_search_results_internal': [],
                'external_sources_shown': False,
                'bounce_count': 0,
                'refinement_count': 0
            }