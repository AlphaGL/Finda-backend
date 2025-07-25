# chatbot/urls.py - Enhanced URL Configuration
from django.urls import path, include
from .views import (
    # Enhanced Chat APIs
    EnhancedChatAPI,
    chat_api,  # Legacy support
    
    # Multimedia Processing
    process_voice_message,
    analyze_product_image_api,
    
    # Chat Management
    get_chat_history,
    chat_sessions_api,
    clear_chat_session,
    
    # User Preferences
    # UserPreferencesAPI,
    update_user_preferences,
    get_user_preferences,
    
    # Feedback and Analytics
    ChatFeedbackAPI,
    chat_analytics_api,
    user_chat_stats,
    
    # Advanced Features
    search_with_preferences_api,
    get_conversation_context,
    update_conversation_context,
    
    # System and Health
    chatbot_health_check,
    gemini_status_api,
    
    # Authentication
    CustomAuthToken,
    
    # Additional endpoints
    bulk_message_operations,
    rate_message,
    session_statistics,
    export_user_data,
    process_voice_webhook,
    image_analysis_webhook,
)

app_name = 'chatbot'

urlpatterns = [
    # ===========================
    #  CORE CHAT ENDPOINTS
    # ===========================
    
    # Main chat API (enhanced)
    path('chat/', EnhancedChatAPI.as_view(), name='enhanced-chat'),
    
    # Legacy chat API (backward compatibility)
    path('api/', chat_api, name='legacy-chat-api'),
    
    # ===========================
    #  MULTIMEDIA PROCESSING
    # ===========================
    
    # Voice message processing
    path('voice/', process_voice_message, name='process-voice'),
    
    # Image analysis
    path('image-analysis/', analyze_product_image_api, name='analyze-image'),
    
    # ===========================
    #  CHAT SESSION MANAGEMENT
    # ===========================
    
    # Chat sessions CRUD
    path('sessions/', chat_sessions_api, name='chat-sessions'),
    
    # Get chat history
    path('history/', get_chat_history, name='chat-history'),
    path('history/<uuid:session_id>/', get_chat_history, name='chat-history-session'),
    
    # Clear/delete chat session
    path('sessions/<uuid:session_id>/clear/', clear_chat_session, name='clear-session'),
    
    # Session statistics
    path('sessions/<uuid:session_id>/stats/', session_statistics, name='session-stats'),
    
    # ===========================
    #  USER PREFERENCES
    # ===========================
    
    # User preferences management
    # path('preferences/', UserPreferencesAPI.as_view(), name='user-preferences'),
    
    # Specific preference operations
    path('preferences/update/', update_user_preferences, name='update-preferences'),
    path('preferences/get/', get_user_preferences, name='get-preferences'),
    
    # ===========================
    #  FEEDBACK AND ANALYTICS
    # ===========================
    
    # Chat feedback
    path('feedback/', ChatFeedbackAPI.as_view(), name='chat-feedback'),
    path('messages/<int:message_id>/feedback/', ChatFeedbackAPI.as_view(), name='message-feedback'),
    
    # Message rating
    path('messages/<int:message_id>/rate/', rate_message, name='rate-message'),
    
    # Analytics endpoints
    path('analytics/', chat_analytics_api, name='chat-analytics'),
    path('analytics/user/', user_chat_stats, name='user-chat-stats'),
    
    # ===========================
    #  ADVANCED SEARCH FEATURES
    # ===========================
    
    # Search with preferences
    path('search/', search_with_preferences_api, name='search-with-preferences'),
    
    # Conversation context management
    path('context/<uuid:session_id>/', get_conversation_context, name='get-context'),
    path('context/<uuid:session_id>/update/', update_conversation_context, name='update-context'),
    
    # ===========================
    #  SYSTEM HEALTH & STATUS
    # ===========================
    
    # Health check
    path('health/', chatbot_health_check, name='health-check'),
    
    # Gemini API status
    path('gemini-status/', gemini_status_api, name='gemini-status'),
    
    # ===========================
    #  AUTHENTICATION
    # ===========================
    
    # Token authentication
    path('auth/token/', CustomAuthToken.as_view(), name='api-token-auth'),
    
    # ===========================
    #  WEBHOOK ENDPOINTS
    # ===========================
    
    # External service webhooks (if needed)
    path('webhooks/voice-processing/', process_voice_webhook, name='voice-webhook'),
    path('webhooks/image-analysis/', image_analysis_webhook, name='image-webhook'),
    
    # ===========================
    #  ADMIN & UTILITY ENDPOINTS
    # ===========================
    
    # Bulk operations (admin)
    path('admin/bulk-operations/', bulk_message_operations, name='bulk-operations'),
    
    # Data export (GDPR compliance)
    path('export/', export_user_data, name='export-user-data'),
]

# Additional URL patterns for API versioning
v1_patterns = [
    path('v1/chat/', EnhancedChatAPI.as_view(), name='v1-chat'),
    path('v1/voice/', process_voice_message, name='v1-voice'),
    path('v1/image/', analyze_product_image_api, name='v1-image'),
    path('v1/sessions/', chat_sessions_api, name='v1-sessions'),
    # path('v1/preferences/', UserPreferencesAPI.as_view(), name='v1-preferences'),
    path('v1/feedback/', ChatFeedbackAPI.as_view(), name='v1-feedback'),
    path('v1/analytics/', chat_analytics_api, name='v1-analytics'),
    path('v1/search/', search_with_preferences_api, name='v1-search'),
]

# Add versioned URLs
urlpatterns += v1_patterns