# chatbot/urls.py - Enhanced URL Configuration
from django.urls import path, include
from . import views
from .views import *
app_name = 'chatbot'

urlpatterns = [
    # =======================
    # ENHANCED DYNAMIC APIs 
    # =======================
    
    # Main chat endpoint - handles all message types dynamically
    path('chat/', FullyDynamicChatAPI.as_view(), name='dynamic_chat'),
    
    # External search with full context awareness
    path('external-search/', IntelligentExternalSearchAPI.as_view(), name='intelligent_external_search'),
    
    # Context-aware feedback system
    path('feedback/', ContextAwareFeedbackAPI.as_view(), name='context_feedback'),
    path('feedback/<int:message_id>/', ContextAwareFeedbackAPI.as_view(), name='message_feedback'),
    
    # Conversation analytics and insights
    path('analytics/', ConversationAnalyticsAPI.as_view(), name='conversation_analytics'),
    
    # Intelligent preferences management
    path('preferences/', IntelligentPreferencesAPI.as_view(), name='intelligent_preferences'),
    
    # =======================
    # CONVERSATION MANAGEMENT
    # =======================
    
    # Session management
    path('sessions/', views.chat_sessions_api, name='chat_sessions'),
    path('sessions/<uuid:session_id>/clear/', views.clear_chat_session, name='clear_session'),
    path('sessions/<uuid:session_id>/reset-context/', reset_conversation_context, name='reset_context'),
    path('sessions/<uuid:session_id>/history/', views.get_chat_history, name='session_history'),
    path('sessions/<uuid:session_id>/statistics/', views.session_statistics, name='session_stats'),
    path('sessions/<uuid:session_id>/context/', views.get_conversation_context, name='get_context'),
    path('sessions/<uuid:session_id>/context/update/', views.update_conversation_context, name='update_context'),
    
    # =======================
    # MULTIMEDIA PROCESSING
    # =======================
    
    # Voice message processing
    path('voice/process/', views.process_voice_message, name='process_voice'),
    
    # Image analysis
    path('image/analyze/', views.analyze_product_image_api, name='analyze_image'),
    
    # =======================
    # USER INTERACTION APIs
    # =======================
    
    # Message rating and feedback
    path('messages/<int:message_id>/rate/', views.rate_message, name='rate_message'),
    path('messages/history/', views.get_chat_history, name='chat_history'),
    
    # User preferences (legacy support)
    path('user/preferences/', views.get_user_preferences, name='get_preferences'),
    path('user/preferences/update/', views.update_user_preferences, name='update_preferences'),
    
    # User statistics
    path('user/stats/', views.user_chat_stats, name='user_stats'),
    path('user/export/', views.export_user_data, name='export_data'),
    
    # =======================
    # SEARCH AND DISCOVERY
    # =======================
    
    # Advanced search with preferences
    path('search/advanced/', views.search_with_preferences_api, name='advanced_search'),
    
    # =======================
    # SYSTEM HEALTH & MONITORING
    # =======================
    
    # Health checks
    path('health/', views.chatbot_health_check, name='health_check'),
    path('health/conversation/', conversation_health_check, name='conversation_health'),
    path('health/gemini/', views.gemini_status_api, name='gemini_status'),
    
    # =======================
    # WEBHOOK ENDPOINTS
    # =======================
    
    # External service webhooks
    path('webhooks/voice/', views.process_voice_webhook, name='voice_webhook'),
    path('webhooks/image/', views.image_analysis_webhook, name='image_webhook'),
    
    # =======================
    # LEGACY SUPPORT
    # =======================
    
    # Maintain backward compatibility
    path('api/chat/', views.chat_api, name='legacy_chat'),  # Redirects to enhanced API
    path('api/preferences/', views.UserPreferencesAPI.as_view(), name='legacy_preferences'),
    path('api/feedback/', views.ChatFeedbackAPI.as_view(), name='legacy_feedback'),
    
    # =======================
    # ADMIN & MANAGEMENT
    # =======================
    
    # Bulk operations (admin only)
    path('admin/bulk-operations/', views.bulk_message_operations, name='bulk_operations'),
    
    # Authentication
    path('auth/token/', views.CustomAuthToken.as_view(), name='custom_auth_token'),
]

# API versioning support
v1_patterns = [
    path('v1/', include(urlpatterns)),
]

# Complete URL patterns with versioning
urlpatterns = urlpatterns + v1_patterns