# ai_chatbot/tasks.py
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Avg, Q
from django.utils import timezone

from .models import (
    ChatSession, ChatMessage, SearchQuery, UserFeedback, 
    ChatAnalytics, BotConfiguration
)
from .services.smart_router import SmartChatbotRouter
from .utils.analytics import ChatAnalyticsManager

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_async_chat_message(self, message_data: Dict):
    """
    Process chat message asynchronously for heavy operations
    
    Args:
        message_data: Dictionary containing message info and processing requirements
    """
    try:
        logger.info(f"Processing async chat message: {message_data.get('message_id')}")
        
        # Initialize router
        router = SmartChatbotRouter()
        
        # Extract data
        message_text = message_data.get('message')
        message_type = message_data.get('message_type', 'text')
        context = message_data.get('context', {})
        session_id = message_data.get('session_id')
        
        # Process the message
        import asyncio
        result = asyncio.run(router.process_message(
            message_text, message_type, None, context
        ))
        
        # Update the database with results
        if message_data.get('message_id'):
            update_message_with_results.delay(message_data['message_id'], result)
        
        logger.info(f"Async chat message processed successfully: {message_data.get('message_id')}")
        return {
            'success': True,
            'message_id': message_data.get('message_id'),
            'processing_time': result.get('metadata', {}).get('processing_time', 0)
        }
        
    except Exception as e:
        logger.error(f"Error processing async chat message: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': str(e),
            'message_id': message_data.get('message_id')
        }


@shared_task
def update_message_with_results(message_id: str, processing_result: Dict):
    """
    Update chat message with processing results
    
    Args:
        message_id: ID of the chat message to update
        processing_result: Results from message processing
    """
    try:
        message = ChatMessage.objects.get(id=message_id)
        
        # Update message with results
        message.search_mode = processing_result.get('search_strategy', 'unknown')
        message.response_time = processing_result.get('metadata', {}).get('processing_time', 0)
        message.confidence_score = processing_result.get('metadata', {}).get('confidence_score', 0)
        message.search_results_count = (
            processing_result.get('local_results', {}).get('total_results', 0) +
            processing_result.get('external_results', {}).get('total_found', 0)
        )
        message.context_data.update({
            'async_processing': True,
            'processing_result': processing_result.get('metadata', {})
        })
        
        message.save()
        
        logger.info(f"Message {message_id} updated with processing results")
        
    except ChatMessage.DoesNotExist:
        logger.error(f"Chat message {message_id} not found")
    except Exception as e:
        logger.error(f"Error updating message {message_id}: {str(e)}")


@shared_task
def generate_daily_analytics():
    """
    Generate daily analytics summary
    """
    try:
        logger.info("Starting daily analytics generation")
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Check if analytics already exist for yesterday
        if ChatAnalytics.objects.filter(date=yesterday).exists():
            logger.info(f"Analytics for {yesterday} already exist")
            return
        
        # Calculate analytics for yesterday
        start_datetime = datetime.combine(yesterday, datetime.min.time())
        end_datetime = datetime.combine(today, datetime.min.time())
        
        # Get sessions from yesterday
        sessions = ChatSession.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        )
        
        # Get messages from yesterday
        messages = ChatMessage.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        )
        
        # Get searches from yesterday
        searches = SearchQuery.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        )
        
        # Get feedback from yesterday
        feedbacks = UserFeedback.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        )
        
        # Calculate metrics
        total_sessions = sessions.count()
        total_messages = messages.count()
        unique_users = sessions.filter(user__isnull=False).values('user').distinct().count()
        anonymous_users = sessions.filter(user__isnull=True).count()
        
        total_searches = searches.count()
        local_searches = searches.filter(source_used__in=['local_db', 'both']).count()
        external_searches = searches.filter(source_used__in=['gemini_web', 'both']).count()
        successful_searches = searches.filter(total_results_shown__gt=0).count()
        
        # Calculate average response time
        bot_messages = messages.filter(sender_type='bot', response_time__isnull=False)
        avg_response_time = bot_messages.aggregate(avg=Avg('response_time'))['avg'] or 0
        
        # Calculate session duration
        session_durations = []
        for session in sessions:
            if session.created_at and session.last_activity:
                duration = (session.last_activity - session.created_at).total_seconds()
                session_durations.append(duration)
        
        avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0
        
        # Calculate feedback metrics
        positive_feedback = feedbacks.filter(feedback_type='thumbs_up').count()
        negative_feedback = feedbacks.filter(feedback_type='thumbs_down').count()
        
        rating_feedbacks = feedbacks.filter(rating__isnull=False)
        avg_rating = rating_feedbacks.aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Get top search terms
        top_search_terms = list(searches.values('query_text').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
        
        # Get top search categories
        top_categories = list(searches.exclude(
            filters__category_id__isnull=True
        ).values('filters__category_id').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
        
        # Create analytics record
        analytics = ChatAnalytics.objects.create(
            date=yesterday,
            total_sessions=total_sessions,
            total_messages=total_messages,
            unique_users=unique_users,
            anonymous_users=anonymous_users,
            total_searches=total_searches,
            local_searches=local_searches,
            external_searches=external_searches,
            successful_searches=successful_searches,
            average_response_time=avg_response_time,
            average_session_duration=avg_session_duration,
            positive_feedback=positive_feedback,
            negative_feedback=negative_feedback,
            average_rating=avg_rating,
            top_search_terms=top_search_terms,
            top_search_categories=top_categories
        )
        
        logger.info(f"Daily analytics generated for {yesterday}: {total_sessions} sessions, {total_messages} messages")
        
        # Send summary email to admins if configured
        if getattr(settings, 'SEND_ANALYTICS_EMAIL', False):
            send_analytics_email.delay(analytics.id)
        
        return {
            'success': True,
            'date': yesterday.isoformat(),
            'total_sessions': total_sessions,
            'total_messages': total_messages
        }
        
    except Exception as e:
        logger.error(f"Error generating daily analytics: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_sessions():
    """
    Clean up old and inactive chat sessions
    """
    try:
        logger.info("Starting session cleanup")
        
        # Mark sessions inactive after 1 hour of inactivity
        one_hour_ago = timezone.now() - timedelta(hours=1)
        inactive_count = ChatSession.objects.filter(
            last_activity__lt=one_hour_ago,
            status='active'
        ).update(status='inactive')
        
        # Delete very old sessions (older than 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        very_old_sessions = ChatSession.objects.filter(
            last_activity__lt=thirty_days_ago,
            status='inactive'
        )
        
        deleted_count = very_old_sessions.count()
        very_old_sessions.delete()
        
        logger.info(f"Session cleanup completed: {inactive_count} marked inactive, {deleted_count} deleted")
        
        return {
            'success': True,
            'marked_inactive': inactive_count,
            'deleted': deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_messages():
    """
    Clean up old chat messages to manage database size
    """
    try:
        logger.info("Starting message cleanup")
        
        # Delete messages older than 90 days
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        old_messages = ChatMessage.objects.filter(
            created_at__lt=ninety_days_ago
        )
        
        deleted_count = old_messages.count()
        old_messages.delete()
        
        # Clean up orphaned search queries
        orphaned_searches = SearchQuery.objects.filter(
            chat_message__isnull=True
        )
        orphaned_count = orphaned_searches.count()
        orphaned_searches.delete()
        
        logger.info(f"Message cleanup completed: {deleted_count} messages deleted, {orphaned_count} orphaned searches cleaned")
        
        return {
            'success': True,
            'messages_deleted': deleted_count,
            'orphaned_searches_deleted': orphaned_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up messages: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def send_analytics_email(analytics_id: int):
    """
    Send daily analytics summary email to admins
    
    Args:
        analytics_id: ID of the ChatAnalytics record
    """
    try:
        analytics = ChatAnalytics.objects.get(id=analytics_id)
        
        # Prepare email content
        subject = f"Chatbot Analytics Summary - {analytics.date}"
        
        message = f"""
Daily Chatbot Analytics Report
Date: {analytics.date}

📊 USAGE METRICS:
• Total Sessions: {analytics.total_sessions}
• Total Messages: {analytics.total_messages}
• Unique Users: {analytics.unique_users}
• Anonymous Users: {analytics.anonymous_users}

🔍 SEARCH METRICS:
• Total Searches: {analytics.total_searches}
• Local DB Searches: {analytics.local_searches}
• External Searches: {analytics.external_searches}
• Successful Searches: {analytics.successful_searches}
• Success Rate: {(analytics.successful_searches / analytics.total_searches * 100) if analytics.total_searches > 0 else 0:.1f}%

⚡ PERFORMANCE METRICS:
• Average Response Time: {analytics.average_response_time:.2f}s
• Average Session Duration: {analytics.average_session_duration:.2f}s

👍 FEEDBACK METRICS:
• Positive Feedback: {analytics.positive_feedback}
• Negative Feedback: {analytics.negative_feedback}
• Average Rating: {analytics.average_rating:.1f}/5.0

🔥 TOP SEARCH TERMS:
{chr(10).join([f"• {term['query_text']} ({term['count']} times)" for term in analytics.top_search_terms[:5]])}

This report was generated automatically by the AI Chatbot system.
        """
        
        # Get admin emails
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        admin_emails = list(User.objects.filter(
            is_staff=True,
            is_active=True,
            email__isnull=False
        ).values_list('email', flat=True))
        
        if admin_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False
            )
            
            logger.info(f"Analytics email sent to {len(admin_emails)} admins")
        else:
            logger.warning("No admin emails found for analytics report")
        
        return {
            'success': True,
            'emails_sent': len(admin_emails),
            'date': analytics.date.isoformat()
        }
        
    except ChatAnalytics.DoesNotExist:
        logger.error(f"Analytics record {analytics_id} not found")
        return {
            'success': False,
            'error': 'Analytics record not found'
        }
    except Exception as e:
        logger.error(f"Error sending analytics email: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def train_chatbot_model():
    """
    Train/update chatbot model based on conversation data
    This is a placeholder for ML model training
    """
    try:
        logger.info("Starting chatbot model training")
        
        # Get recent conversation data for training
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get successful conversations (with positive feedback)
        positive_conversations = ChatMessage.objects.filter(
            created_at__gte=thirty_days_ago,
            sender_type='bot',
            feedbacks__feedback_type='thumbs_up'
        ).select_related('chat_session').prefetch_related('feedbacks')
        
        training_data = []
        for message in positive_conversations:
            # Get the user message that prompted this response
            user_message = ChatMessage.objects.filter(
                chat_session=message.chat_session,
                created_at__lt=message.created_at,
                sender_type='user'
            ).order_by('-created_at').first()
            
            if user_message:
                training_data.append({
                    'user_input': user_message.content,
                    'bot_response': message.content,
                    'context': message.context_data,
                    'feedback_score': message.feedbacks.filter(
                        feedback_type='thumbs_up'
                    ).count()
                })
        
        # Here you would implement actual ML training
        # For now, we'll just log the training data size
        logger.info(f"Collected {len(training_data)} training examples")
        
        # Update bot configuration with training results
        BotConfiguration.set_config(
            'last_training_date',
            timezone.now().isoformat(),
            'Last time the chatbot model was trained'
        )
        
        BotConfiguration.set_config(
            'training_data_size',
            len(training_data),
            'Number of examples used in last training'
        )
        
        return {
            'success': True,
            'training_examples': len(training_data),
            'training_date': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error training chatbot model: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def update_search_suggestions():
    """
    Update search suggestions based on popular queries
    """
    try:
        logger.info("Updating search suggestions")
        
        # Get popular search terms from last 7 days
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        popular_terms = SearchQuery.objects.filter(
            created_at__gte=seven_days_ago,
            total_results_shown__gt=0  # Only successful searches
        ).values('query_text').annotate(
            search_count=Count('id'),
            avg_results=Avg('total_results_shown')
        ).order_by('-search_count')[:50]
        
        # Get trending categories
        trending_categories = SearchQuery.objects.filter(
            created_at__gte=seven_days_ago,
            filters__category_id__isnull=False
        ).values('filters__category_id').annotate(
            count=Count('id')
        ).order_by('-count')[:20]
        
        # Update bot configuration
        BotConfiguration.set_config(
            'popular_search_terms',
            list(popular_terms),
            'Popular search terms from last 7 days'
        )
        
        BotConfiguration.set_config(
            'trending_categories',
            list(trending_categories),
            'Trending categories from last 7 days'
        )
        
        BotConfiguration.set_config(
            'suggestions_last_updated',
            timezone.now().isoformat(),
            'Last time search suggestions were updated'
        )
        
        logger.info(f"Search suggestions updated: {len(popular_terms)} terms, {len(trending_categories)} categories")
        
        return {
            'success': True,
            'popular_terms_count': len(popular_terms),
            'trending_categories_count': len(trending_categories)
        }
        
    except Exception as e:
        logger.error(f"Error updating search suggestions: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def process_feedback_analysis():
    """
    Analyze user feedback to improve chatbot responses
    """
    try:
        logger.info("Processing feedback analysis")
        
        # Get recent feedback
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_feedback = UserFeedback.objects.filter(
            created_at__gte=seven_days_ago
        ).select_related('chat_message')
        
        # Analyze negative feedback
        negative_feedback = recent_feedback.filter(
            Q(feedback_type='thumbs_down') | Q(rating__lt=3)
        )
        
        negative_patterns = []
        for feedback in negative_feedback:
            if feedback.chat_message and feedback.chat_message.intent_detected:
                negative_patterns.append({
                    'intent': feedback.chat_message.intent_detected,
                    'query': feedback.chat_message.content[:100],
                    'response_time': feedback.chat_message.response_time,
                    'results_count': feedback.chat_message.search_results_count,
                    'comment': feedback.comment
                })
        
        # Analyze positive feedback
        positive_feedback = recent_feedback.filter(
            Q(feedback_type='thumbs_up') | Q(rating__gte=4)
        )
        
        positive_patterns = []
        for feedback in positive_feedback:
            if feedback.chat_message and feedback.chat_message.intent_detected:
                positive_patterns.append({
                    'intent': feedback.chat_message.intent_detected,
                    'search_mode': feedback.chat_message.search_mode,
                    'response_time': feedback.chat_message.response_time
                })
        
        # Update configuration with insights
        BotConfiguration.set_config(
            'feedback_analysis',
            {
                'analysis_date': timezone.now().isoformat(),
                'negative_patterns': negative_patterns[:10],
                'positive_patterns': positive_patterns[:10],
                'total_feedback': recent_feedback.count(),
                'satisfaction_rate': (
                    positive_feedback.count() / recent_feedback.count() * 100
                    if recent_feedback.count() > 0 else 0
                )
            },
            'Analysis of user feedback patterns'
        )
        
        logger.info(f"Feedback analysis completed: {recent_feedback.count()} feedback items analyzed")
        
        return {
            'success': True,
            'total_feedback': recent_feedback.count(),
            'negative_count': negative_feedback.count(),
            'positive_count': positive_feedback.count()
        }
        
    except Exception as e:
        logger.error(f"Error processing feedback analysis: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def monitor_system_health():
    """
    Monitor chatbot system health and send alerts if needed
    """
    try:
        logger.info("Monitoring system health")
        
        health_status = {
            'timestamp': timezone.now().isoformat(),
            'services': {},
            'alerts': [],
            'overall_status': 'healthy'
        }
        
        # Check database performance
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status['services']['database'] = 'ok'
        except Exception as e:
            health_status['services']['database'] = 'error'
            health_status['alerts'].append(f"Database error: {str(e)}")
        
        # Check cache
        try:
            from django.core.cache import cache
            cache.set('health_check', 'ok', 60)
            if cache.get('health_check') == 'ok':
                health_status['services']['cache'] = 'ok'
            else:
                health_status['services']['cache'] = 'error'
                health_status['alerts'].append("Cache not responding")
        except Exception as e:
            health_status['services']['cache'] = 'error'
            health_status['alerts'].append(f"Cache error: {str(e)}")
        
        # Check Gemini API
        try:
            router = SmartChatbotRouter()
            test_result = await router.gemini_client.test_connection()
            health_status['services']['gemini_api'] = 'ok' if test_result['success'] else 'error'
            if not test_result['success']:
                health_status['alerts'].append("Gemini API not responding")
        except Exception as e:
            health_status['services']['gemini_api'] = 'error'
            health_status['alerts'].append(f"Gemini API error: {str(e)}")
        
        # Check local search service
        try:
            from .services.local_search import LocalSearchService
            local_search = LocalSearchService()
            test_search = await local_search.search_products("test", limit=1)
            health_status['services']['local_search'] = 'ok' if test_search['success'] else 'error'
        except Exception as e:
            health_status['services']['local_search'] = 'error'
            health_status['alerts'].append(f"Local search error: {str(e)}")
        
        # Check web search service
        try:
            from .services.web_search import WebSearchService
            web_search = WebSearchService()
            # Simple test - don't actually search to avoid API costs
            health_status['services']['web_search'] = 'ok'
        except Exception as e:
            health_status['services']['web_search'] = 'error'
            health_status['alerts'].append(f"Web search error: {str(e)}")
        
        # Determine overall status
        if health_status['alerts']:
            health_status['overall_status'] = 'degraded' if len(health_status['alerts']) < 3 else 'unhealthy'
        
        # Update bot configuration with health status
        BotConfiguration.set_config(
            'system_health',
            health_status,
            'Current system health status'
        )
        
        # Send alerts if system is unhealthy
        if health_status['overall_status'] == 'unhealthy':
            send_health_alert.delay(health_status)
        
        logger.info(f"System health check completed: {health_status['overall_status']}")
        
        return {
            'success': True,
            'health_status': health_status['overall_status'],
            'alerts_count': len(health_status['alerts'])
        }
        
    except Exception as e:
        logger.error(f"Error monitoring system health: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def send_health_alert(health_status: Dict):
    """Send health alert email to admins"""
    try:
        from django.core.mail import send_mail
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        admin_emails = list(User.objects.filter(
            is_staff=True,
            is_active=True,
            email__isnull=False
        ).values_list('email', flat=True))
        
        if admin_emails:
            subject = "⚠️ AI Chatbot System Health Alert"
            message = f"""
SYSTEM HEALTH ALERT

Status: {health_status['overall_status'].upper()}
Time: {health_status['timestamp']}

ALERTS:
{chr(10).join([f"• {alert}" for alert in health_status['alerts']])}

SERVICE STATUS:
{chr(10).join([f"• {service}: {status}" for service, status in health_status['services'].items()])}

Please check the system immediately.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False
            )
            
            logger.info(f"Health alert sent to {len(admin_emails)} admins")
        
    except Exception as e:
        logger.error(f"Error sending health alert: {str(e)}")
