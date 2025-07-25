# chatbot/additional_views.py - Additional View Functions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
import json

from .models import (
    ChatSession, ChatMessage, UserPreference, SearchQuery,
    FeedbackRating, ConversationContext
)
from .serializers import (
    UserPreferenceSerializer, FeedbackRatingSerializer,
    ChatSessionSerializer, PreferenceUpdateSerializer,
    AnalyticsSerializer
)
from .gemini_client import get_model_status
from .utils import extract_product_preferences, filter_products_by_preferences
from main.models import Products, Services


# ===========================
#  USER PREFERENCES VIEWS
# ===========================

class UserPreferencesAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user preferences"""
        try:
            preferences = UserPreference.objects.get(user=request.user)
            serializer = UserPreferenceSerializer(preferences)
            return Response(serializer.data)
        except UserPreference.DoesNotExist:
            return Response({
                "message": "No preferences found",
                "preferences": {}
            })
    
    def post(self, request):
        """Create/Update user preferences"""
        try:
            preferences, created = UserPreference.objects.get_or_create(
                user=request.user
            )
            serializer = UserPreferenceSerializer(preferences, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Preferences updated successfully",
                    "preferences": serializer.data
                })
            
            return Response(serializer.errors, status=400)
            
        except Exception as e:
            return Response({
                "error": f"Failed to update preferences: {str(e)}"
            }, status=500)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_preferences(request):
    """Update specific user preferences"""
    try:
        preferences, created = UserPreference.objects.get_or_create(
            user=request.user
        )
        
        serializer = PreferenceUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Update preferences based on provided data
            for key, value in serializer.validated_data.items():
                if hasattr(preferences, key):
                    setattr(preferences, key, value)
            
            preferences.save()
            
            return Response({
                "message": "Preferences updated successfully",
                "updated_fields": list(serializer.validated_data.keys())
            })
        
        return Response(serializer.errors, status=400)
        
    except Exception as e:
        return Response({
            "error": f"Failed to update preferences: {str(e)}"
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_preferences(request):
    """Get user preferences with defaults"""
    try:
        preferences, created = UserPreference.objects.get_or_create(
            user=request.user
        )
        
        serializer = UserPreferenceSerializer(preferences)
        
        return Response({
            "preferences": serializer.data,
            "is_new_user": created
        })
        
    except Exception as e:
        return Response({
            "error": f"Failed to get preferences: {str(e)}"
        }, status=500)


# ===========================
#  FEEDBACK VIEWS
# ===========================

class ChatFeedbackAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id=None):
        """Submit feedback for a chat message"""
        try:
            if message_id:
                try:
                    message = ChatMessage.objects.get(
                        id=message_id,
                        session__user=request.user
                    )
                except ChatMessage.DoesNotExist:
                    return Response({"error": "Message not found"}, status=404)
            else:
                # Get the latest message if no ID provided
                message = ChatMessage.objects.filter(
                    session__user=request.user
                ).order_by('-timestamp').first()
                
                if not message:
                    return Response({"error": "No messages found"}, status=404)
            
            # Create or update feedback
            feedback, created = FeedbackRating.objects.get_or_create(
                chat_message=message,
                user=request.user,
                defaults=request.data
            )
            
            if not created:
                # Update existing feedback
                serializer = FeedbackRatingSerializer(feedback, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response({
                        "message": "Feedback updated successfully",
                        "feedback": serializer.data
                    })
                return Response(serializer.errors, status=400)
            
            serializer = FeedbackRatingSerializer(feedback)
            return Response({
                "message": "Feedback submitted successfully",
                "feedback": serializer.data
            }, status=201)
            
        except Exception as e:
            return Response({
                "error": f"Failed to submit feedback: {str(e)}"
            }, status=500)
    
    def get(self, request, message_id=None):
        """Get feedback for a message or all user feedback"""
        try:
            if message_id:
                try:
                    message = ChatMessage.objects.get(
                        id=message_id,
                        session__user=request.user
                    )
                    feedback = FeedbackRating.objects.filter(
                        chat_message=message,
                        user=request.user
                    ).first()
                    
                    if feedback:
                        serializer = FeedbackRatingSerializer(feedback)
                        return Response(serializer.data)
                    else:
                        return Response({"message": "No feedback found"})
                        
                except ChatMessage.DoesNotExist:
                    return Response({"error": "Message not found"}, status=404)
            else:
                # Get all user feedback
                feedback = FeedbackRating.objects.filter(
                    user=request.user
                ).order_by('-created_at')[:20]
                
                serializer = FeedbackRatingSerializer(feedback, many=True)
                return Response({
                    "feedback": serializer.data,
                    "count": feedback.count()
                })
                
        except Exception as e:
            return Response({
                "error": f"Failed to get feedback: {str(e)}"
            }, status=500)


# ===========================
#  ANALYTICS VIEWS
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_analytics_api(request):
    """Get chat analytics for the user"""
    try:
        user = request.user
        
        # Get date range (default last 30 days)
        days = int(request.GET.get('days', 30))
        since_date = timezone.now() - timedelta(days=days)
        
        # Basic statistics
        total_sessions = ChatSession.objects.filter(user=user).count()
        total_messages = ChatMessage.objects.filter(session__user=user).count()
        
        # Recent activity
        recent_sessions = ChatSession.objects.filter(
            user=user,
            created_at__gte=since_date
        ).count()
        
        recent_messages = ChatMessage.objects.filter(
            session__user=user,
            timestamp__gte=since_date
        ).count()
        
        # Message types breakdown
        message_types = ChatMessage.objects.filter(
            session__user=user,
            timestamp__gte=since_date
        ).values('message_type').annotate(count=Count('id'))
        
        # Search queries
        search_queries = SearchQuery.objects.filter(
            user=user,
            created_at__gte=since_date
        ).count()
        
        # User satisfaction (from feedback)
        avg_satisfaction = FeedbackRating.objects.filter(
            user=user,
            created_at__gte=since_date
        ).aggregate(avg_rating=Avg('helpfulness_rating'))['avg_rating'] or 0
        
        # Most searched categories
        most_searched = SearchQuery.objects.filter(
            user=user,
            created_at__gte=since_date
        ).values('search_type').annotate(count=Count('id')).order_by('-count')[:5]
        
        # Session duration statistics
        sessions_with_duration = ChatSession.objects.filter(
            user=user,
            created_at__gte=since_date
        ).annotate(
            message_count=Count('messages'),
            duration=Count('messages') * 2  # Approximate duration in minutes
        )
        
        avg_session_duration = sessions_with_duration.aggregate(
            avg_duration=Avg('duration')
        )['avg_duration'] or 0
        
        analytics_data = {
            'total_sessions': total_sessions,
            'total_messages': total_messages,
            'recent_sessions': recent_sessions,
            'recent_messages': recent_messages,
            'message_types': list(message_types),
            'search_queries': search_queries,
            'avg_satisfaction': round(avg_satisfaction, 2),
            'most_searched': list(most_searched),
            'avg_session_duration': round(avg_session_duration, 2),
            'period_days': days
        }
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response({
            "error": f"Failed to get analytics: {str(e)}"
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_chat_stats(request):
    """Get detailed user chat statistics"""
    try:
        user = request.user
        
        # Activity by day (last 7 days)
        daily_activity = []
        for i in range(7):
            date = timezone.now().date() - timedelta(days=i)
            messages_count = ChatMessage.objects.filter(
                session__user=user,
                timestamp__date=date
            ).count()
            
            daily_activity.append({
                'date': date.isoformat(),
                'messages': messages_count
            })
        
        # Popular search terms
        popular_searches = SearchQuery.objects.filter(
            user=user
        ).values('original_query').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Feedback summary
        feedback_summary = FeedbackRating.objects.filter(
            user=user
        ).aggregate(
            total_feedback=Count('id'),
            avg_helpfulness=Avg('helpfulness_rating'),
            avg_accuracy=Avg('accuracy_rating'),
            avg_speed=Avg('response_speed_rating')
        )
        
        # Multimedia usage
        multimedia_usage = ChatMessage.objects.filter(
            session__user=user
        ).exclude(message_type='text').values('message_type').annotate(
            count=Count('id')
        )
        
        return Response({
            'daily_activity': daily_activity,
            'popular_searches': list(popular_searches),
            'feedback_summary': feedback_summary,
            'multimedia_usage': list(multimedia_usage)
        })
        
    except Exception as e:
        return Response({
            "error": f"Failed to get user stats: {str(e)}"
        }, status=500)


# ===========================
#  ADVANCED SEARCH VIEWS
# ===========================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_with_preferences_api(request):
    """Advanced search with user preferences"""
    try:
        query = request.data.get('query', '').strip()
        search_type = request.data.get('type', 'both')  # product, service, both
        use_preferences = request.data.get('use_preferences', True)
        
        if not query:
            return Response({"error": "Query is required"}, status=400)
        
        user = request.user
        preferences = {}
        
        # Get user preferences if requested
        if use_preferences:
            try:
                user_prefs = UserPreference.objects.get(user=user)
                preferences = {
                    'colors': user_prefs.preferred_categories,
                    'price_range': user_prefs.preferred_price_range,
                    'locations': user_prefs.preferred_locations,
                    'brands': user_prefs.preferred_brands
                }
            except UserPreference.DoesNotExist:
                pass
        
        # Extract additional preferences from query
        extracted_prefs = extract_product_preferences(query, preferences)
        preferences.update(extracted_prefs)
        
        results = {'products': [], 'services': []}
        
        # Search products if requested
        if search_type in ['product', 'both']:
            products = Products.objects.filter(
                Q(product_name__icontains=query) |
                Q(product_description__icontains=query) |
                Q(product_brand__icontains=query) |
                Q(tags__icontains=query),
                product_status='published'
            )
            
            if preferences:
                products = filter_products_by_preferences(products, preferences)
            
            products = products.annotate(
                avg_rating=Avg('product_ratings__rating')
            ).order_by('-is_promoted', '-is_featured', '-avg_rating')[:10]
            
            results['products'] = [
                {
                    'id': p.id,
                    'name': p.product_name,
                    'price': float(p.product_price),
                    'currency': p.currency,
                    'location': f"{p.city.name}, {p.state.name}",
                    'rating': p.average_rating(),
                    'image': p.featured_image.url if p.featured_image else None,
                    'url': f"/products/{p.slug}/",
                    'is_promoted': p.is_promoted
                }
                for p in products
            ]
        
        # Search services if requested
        if search_type in ['service', 'both']:
            services = Services.objects.filter(
                Q(service_name__icontains=query) |
                Q(service_description__icontains=query) |
                Q(provider_expertise__icontains=query) |
                Q(tags__icontains=query),
                service_status='published'
            )
            
            services = services.annotate(
                avg_rating=Avg('service_ratings__rating')
            ).order_by('-is_promoted', '-is_featured', '-avg_rating')[:10]
            
            results['services'] = [
                {
                    'id': s.id,
                    'name': s.service_name,
                    'provider': s.provider_name,
                    'price_range': s.get_formatted_price_range(),
                    'location': f"{s.city.name}, {s.state.name}",
                    'rating': s.average_rating(),
                    'image': s.featured_image.url if s.featured_image else None,
                    'url': f"/services/{s.slug}/",
                    'is_promoted': s.is_promoted
                }
                for s in services
            ]
        
        # Log search query
        SearchQuery.objects.create(
            user=user,
            original_query=query,
            search_type=search_type,
            internal_results_count=len(results['products']) + len(results['services']),
            preferences_used=preferences
        )
        
        return Response({
            'query': query,
            'search_type': search_type,
            'preferences_used': preferences,
            'results': results,
            'total_results': len(results['products']) + len(results['services'])
        })
        
    except Exception as e:
        return Response({
            "error": f"Search failed: {str(e)}"
        }, status=500)


# ===========================
#  CONVERSATION CONTEXT VIEWS
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_context(request, session_id):
    """Get conversation context for a session"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        context, created = ConversationContext.objects.get_or_create(
            session=session
        )
        
        # Get recent messages for context
        recent_messages = ChatMessage.objects.filter(
            session=session
        ).order_by('-timestamp')[:10]
        
        return Response({
            'session_id': session_id,
            'context': {
                'current_intent': context.current_intent,
                'questions_asked': context.questions_asked,
                'preferences_collected': context.preferences_collected,
                'missing_preferences': context.missing_preferences,
                'external_sources_shown': context.external_sources_shown,
                'bounce_count': context.bounce_count,
                'refinement_count': context.refinement_count
            },
            'recent_messages_count': recent_messages.count(),
            'session_preferences': session.preference_data
        })
        
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
    except Exception as e:
        return Response({
            "error": f"Failed to get context: {str(e)}"
        }, status=500)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_conversation_context(request, session_id):
    """Update conversation context"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        context, created = ConversationContext.objects.get_or_create(
            session=session
        )
        
        # Update context fields
        update_data = request.data
        
        for field in ['current_intent', 'questions_asked', 'preferences_collected', 
                      'missing_preferences', 'external_sources_shown']:
            if field in update_data:
                setattr(context, field, update_data[field])
        
        context.save()
        
        return Response({
            'message': 'Context updated successfully',
            'session_id': session_id,
            'updated_fields': list(update_data.keys())
        })
        
    except ChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
    except Exception as e:
        return Response({
            "error": f"Failed to update context: {str(e)}"
        }, status=500)


# ===========================
#  SYSTEM HEALTH VIEWS
# ===========================

@api_view(['GET'])
@permission_classes([AllowAny])
def chatbot_health_check(request):
    """Health check endpoint for chatbot system"""
    try:
        # Check database connectivity
        db_status = "healthy"
        try:
            ChatSession.objects.count()
        except Exception:
            db_status = "error"
        
        # Check Gemini API status
        gemini_status = get_model_status()
        
        # Check recent activity
        recent_messages = ChatMessage.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        # Overall health
        overall_health = "healthy"
        if db_status == "error" or gemini_status.get("status") == "error":
            overall_health = "degraded"
        
        return Response({
            'status': overall_health,
            'timestamp': timezone.now().isoformat(),
            'components': {
                'database': db_status,
                'gemini_api': gemini_status.get("status", "unknown"),
                'recent_activity': recent_messages
            },
            'version': '2.0.0',
            'features': [
                'text_chat',
                'voice_messages', 
                'image_analysis',
                'preference_learning',
                'external_search'
            ]
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gemini_status_api(request):
    """Get detailed Gemini API status"""
    try:
        status_info = get_model_status()
        
        # Add usage statistics if available
        recent_usage = ChatMessage.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        return Response({
            'gemini_status': status_info,
            'recent_usage_24h': recent_usage,
            'models': {
                'text_model': 'gemini-2.0-flash-exp',
                'vision_model': 'gemini-2.0-flash-exp'
            }
        })
        
    except Exception as e:
        return Response({
            "error": f"Failed to get Gemini status: {str(e)}"
        }, status=500)


# ===========================
#  WEBHOOK HANDLERS
# ===========================

@api_view(['POST'])
@permission_classes([AllowAny])
def process_voice_webhook(request):
    """Webhook for external voice processing services"""
    try:
        # Validate webhook signature if needed
        data = request.data
        
        # Process webhook data
        message_id = data.get('message_id')
        transcription = data.get('transcription')
        confidence = data.get('confidence', 0.0)
        
        if message_id and transcription:
            try:
                message = ChatMessage.objects.get(id=message_id)
                # Update message with transcription results
                message.user_input = transcription
                message.transcription_confidence = confidence
                message.save()
                
                return Response({'status': 'success'})
            except ChatMessage.DoesNotExist:
                return Response({'error': 'Message not found'}, status=404)
        
        return Response({'error': 'Invalid webhook data'}, status=400)
        
    except Exception as e:
        return Response({
            "error": f"Webhook processing failed: {str(e)}"
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def image_analysis_webhook(request):
    """Webhook for external image analysis services"""
    try:
        data = request.data
        
        message_id = data.get('message_id')
        analysis_result = data.get('analysis')
        
        if message_id and analysis_result:
            try:
                message = ChatMessage.objects.get(id=message_id)
                message.image_analysis_data = analysis_result
                message.save()
                
                return Response({'status': 'success'})
            except ChatMessage.DoesNotExist:
                return Response({'error': 'Message not found'}, status=404)
        
        return Response({'error': 'Invalid webhook data'}, status=400)
        
    except Exception as e:
        return Response({
            "error": f"Webhook processing failed: {str(e)}"
        }, status=500)


# ===========================
#  UTILITY FUNCTIONS
# ===========================

def get_user_session_summary(user, days=30):
    """Get summary of user's chat sessions"""
    since_date = timezone.now() - timedelta(days=days)
    
    sessions = ChatSession.objects.filter(
        user=user,
        created_at__gte=since_date
    ).annotate(
        message_count=Count('messages')
    ).order_by('-updated_at')
    
    return {
        'total_sessions': sessions.count(),
        'active_sessions': sessions.filter(is_active=True).count(),
        'total_messages': sum(s.message_count for s in sessions),
        'avg_messages_per_session': sessions.aggregate(
            avg=Avg('message_count')
        )['avg'] or 0
    }


def cleanup_old_sessions(days=90):
    """Cleanup old inactive sessions"""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    old_sessions = ChatSession.objects.filter(
        updated_at__lt=cutoff_date,
        is_active=False
    )
    
    count = old_sessions.count()
    old_sessions.delete()
    
    return count