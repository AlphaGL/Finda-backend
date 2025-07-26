# chatbot/urls.py - Perfect AI URL Configuration (Updated)
from django.urls import path, include
from .views import (
    PerfectAIChatAPI, PerfectExternalSearchAPI, PerfectFeedbackAPI,
    PerfectAnalyticsAPI, UserPreferencesAPI, perfect_ai_health_check,
    reset_perfect_memory, chat_api
)

app_name = 'chatbot'

urlpatterns = [
    # =======================
    # PERFECT AI CORE ENDPOINTS
    # =======================
    
    # Main perfect AI chat endpoint - handles ALL conversation scenarios
    path('perfect-chat/', PerfectAIChatAPI.as_view(), name='perfect_chat'),
    
    # Perfect external search with complete memory
    path('perfect-external-search/', PerfectExternalSearchAPI.as_view(), name='perfect_external_search'),
    
    # Perfect feedback system with learning integration
    path('perfect-feedback/', PerfectFeedbackAPI.as_view(), name='perfect_feedback'),
    path('perfect-feedback/<int:message_id>/', PerfectFeedbackAPI.as_view(), name='perfect_message_feedback'),
    
    # Perfect analytics with memory intelligence
    path('perfect-analytics/', PerfectAnalyticsAPI.as_view(), name='perfect_analytics'),
    
    # Enhanced preferences with AI learning
    path('perfect-preferences/', UserPreferencesAPI.as_view(), name='perfect_preferences'),
    
    # =======================
    # PERFECT MEMORY MANAGEMENT
    # =======================
    
    # Perfect AI health check
    path('perfect-health/', perfect_ai_health_check, name='perfect_health'),
    
    # Reset perfect memory (with user consent)
    path('sessions/<uuid:session_id>/reset-perfect-memory/', reset_perfect_memory, name='reset_perfect_memory'),
    
    # =======================
    # STANDARD ENDPOINTS (Primary)
    # =======================
    
    # Main chat endpoint (uses Perfect AI)
    path('chat/', PerfectAIChatAPI.as_view(), name='chat'),
    
    # External search endpoint
    path('external-search/', PerfectExternalSearchAPI.as_view(), name='external_search'),
    
    # Feedback endpoint
    path('feedback/', PerfectFeedbackAPI.as_view(), name='feedback'),
    path('feedback/<int:message_id>/', PerfectFeedbackAPI.as_view(), name='message_feedback'),
    
    # Analytics endpoint
    path('analytics/', PerfectAnalyticsAPI.as_view(), name='analytics'),
    
    # User preferences endpoint
    path('preferences/', UserPreferencesAPI.as_view(), name='preferences'),
    
    # System health check
    path('health/', perfect_ai_health_check, name='health'),
    
    # Memory management
    path('sessions/<uuid:session_id>/reset-memory/', reset_perfect_memory, name='reset_memory'),
    
    # =======================
    # BACKWARD COMPATIBILITY
    # =======================
    
    # Legacy endpoints redirect to perfect AI
    path('api/chat/', chat_api, name='legacy_api_chat_redirect'),
    path('legacy-chat/', chat_api, name='legacy_chat_redirect'),
    
    # =======================
    # API VERSIONING
    # =======================
    
    # Version 2.0 - Perfect AI (Current)
    path('v2/', include([
        path('chat/', PerfectAIChatAPI.as_view(), name='v2_chat'),
        path('external-search/', PerfectExternalSearchAPI.as_view(), name='v2_external_search'),
        path('feedback/', PerfectFeedbackAPI.as_view(), name='v2_feedback'),
        path('feedback/<int:message_id>/', PerfectFeedbackAPI.as_view(), name='v2_message_feedback'),
        path('analytics/', PerfectAnalyticsAPI.as_view(), name='v2_analytics'),
        path('preferences/', UserPreferencesAPI.as_view(), name='v2_preferences'),
        path('health/', perfect_ai_health_check, name='v2_health'),
        path('sessions/<uuid:session_id>/reset-memory/', reset_perfect_memory, name='v2_reset_memory'),
    ])),
    
    # Version 1.0 - Legacy support (redirects to perfect AI)
    path('v1/', include([
        path('chat/', chat_api, name='v1_chat'),
        path('feedback/', PerfectFeedbackAPI.as_view(), name='v1_feedback'),
        path('preferences/', UserPreferencesAPI.as_view(), name='v1_preferences'),
        path('health/', perfect_ai_health_check, name='v1_health'),
    ])),
    
    # =======================
    # SPECIALIZED ACCESS PATTERNS
    # =======================
    
    # API prefix patterns
    path('api/', include([
        path('chat/', PerfectAIChatAPI.as_view(), name='api_chat'),
        path('external-search/', PerfectExternalSearchAPI.as_view(), name='api_external_search'),
        path('feedback/', PerfectFeedbackAPI.as_view(), name='api_feedback'),
        path('feedback/<int:message_id>/', PerfectFeedbackAPI.as_view(), name='api_message_feedback'),
        path('analytics/', PerfectAnalyticsAPI.as_view(), name='api_analytics'),
        path('preferences/', UserPreferencesAPI.as_view(), name='api_preferences'),
        path('health/', perfect_ai_health_check, name='api_health'),
        path('sessions/<uuid:session_id>/reset-memory/', reset_perfect_memory, name='api_reset_memory'),
    ])),
    
    # Mobile app specific endpoints
    path('mobile/', include([
        path('v2/', include([
            path('chat/', PerfectAIChatAPI.as_view(), name='mobile_v2_chat'),
            path('quick-search/', PerfectExternalSearchAPI.as_view(), name='mobile_quick_search'),
            path('rate/', PerfectFeedbackAPI.as_view(), name='mobile_rate'),
            path('profile/', UserPreferencesAPI.as_view(), name='mobile_profile'),
            path('status/', perfect_ai_health_check, name='mobile_status'),
        ])),
        # Mobile v1 (legacy)
        path('chat/', PerfectAIChatAPI.as_view(), name='mobile_chat'),
        path('search/', PerfectExternalSearchAPI.as_view(), name='mobile_search'),
        path('feedback/', PerfectFeedbackAPI.as_view(), name='mobile_feedback'),
    ])),
    
    # Web app specific endpoints  
    path('web/', include([
        path('v2/', include([
            path('chat/', PerfectAIChatAPI.as_view(), name='web_v2_chat'),
            path('analytics/', PerfectAnalyticsAPI.as_view(), name='web_analytics'),
            path('settings/', UserPreferencesAPI.as_view(), name='web_settings'),
            path('external-sources/', PerfectExternalSearchAPI.as_view(), name='web_external_sources'),
            path('system-status/', perfect_ai_health_check, name='web_system_status'),
        ])),
        # Web v1 (legacy)
        path('chat/', PerfectAIChatAPI.as_view(), name='web_chat'),
        path('dashboard/', PerfectAnalyticsAPI.as_view(), name='web_dashboard'),
        path('preferences/', UserPreferencesAPI.as_view(), name='web_preferences'),
    ])),
    
    # =======================
    # ADMIN & DEBUGGING ENDPOINTS
    # =======================
    
    # Admin-specific endpoints (if needed)
    path('admin-api/', include([
        path('health-detailed/', perfect_ai_health_check, name='admin_health_detailed'),
        path('analytics-full/', PerfectAnalyticsAPI.as_view(), name='admin_analytics_full'),
        path('user/<int:user_id>/reset-memory/', reset_perfect_memory, name='admin_user_reset_memory'),
    ])),
    
    # =======================
    # ALTERNATIVE NAMING PATTERNS
    # =======================
    
    # Alternative names for the same endpoints
    path('conversation/', PerfectAIChatAPI.as_view(), name='conversation'),
    path('search-external/', PerfectExternalSearchAPI.as_view(), name='search_external'),
    path('rate-response/', PerfectFeedbackAPI.as_view(), name='rate_response'),
    path('user-analytics/', PerfectAnalyticsAPI.as_view(), name='user_analytics'),
    path('user-settings/', UserPreferencesAPI.as_view(), name='user_settings'),
    path('system-health/', perfect_ai_health_check, name='system_health'),
    
    # =======================
    # WEBHOOK & INTEGRATION ENDPOINTS
    # =======================
    
    # Webhook endpoints (if you plan to add webhook functionality)
    path('webhooks/', include([
        path('feedback-received/', PerfectFeedbackAPI.as_view(), name='webhook_feedback'),
        path('user-preferences-updated/', UserPreferencesAPI.as_view(), name='webhook_preferences'),
    ])),
    
    # Third-party integration endpoints
    path('integrations/', include([
        path('chat-widget/', PerfectAIChatAPI.as_view(), name='integration_chat_widget'),
        path('search-api/', PerfectExternalSearchAPI.as_view(), name='integration_search_api'),
        path('health-check/', perfect_ai_health_check, name='integration_health_check'),
    ])),
]

# =======================
# EXPORT PATTERNS FOR INCLUSION IN MAIN URLs
# =======================

# These patterns can be included in your main urls.py
api_patterns = [
    # Direct API access with chatbot prefix
    path('chatbot/', include(urlpatterns)),
    
    # API versioning at root level
    path('api/v2/chatbot/', include([
        path('chat/', PerfectAIChatAPI.as_view(), name='root_api_v2_chat'),
        path('external-search/', PerfectExternalSearchAPI.as_view(), name='root_api_v2_external_search'),
        path('feedback/', PerfectFeedbackAPI.as_view(), name='root_api_v2_feedback'),
        path('analytics/', PerfectAnalyticsAPI.as_view(), name='root_api_v2_analytics'),
        path('preferences/', UserPreferencesAPI.as_view(), name='root_api_v2_preferences'),
        path('health/', perfect_ai_health_check, name='root_api_v2_health'),
    ])),
    
    path('api/v1/chatbot/', include([
        path('chat/', chat_api, name='root_api_v1_chat'),
        path('feedback/', PerfectFeedbackAPI.as_view(), name='root_api_v1_feedback'),
        path('preferences/', UserPreferencesAPI.as_view(), name='root_api_v1_preferences'),
    ])),
]

# =======================
# COMPLETE URL CONFIGURATION
# =======================

# Add API patterns to main urlpatterns
complete_urlpatterns = urlpatterns + [
    # Include API patterns
    path('', include(api_patterns)),
]

# Export complete configuration
urlpatterns = complete_urlpatterns

# =======================
# URL PATTERN SUMMARY
# =======================
"""
MAIN ENDPOINTS:
- /chatbot/chat/ - Main chat interface (Perfect AI)
- /chatbot/external-search/ - External search
- /chatbot/feedback/ - Feedback system
- /chatbot/analytics/ - User analytics
- /chatbot/preferences/ - User preferences
- /chatbot/health/ - System health check

PERFECT AI SPECIFIC:
- /chatbot/perfect-chat/ - Explicit Perfect AI chat
- /chatbot/perfect-analytics/ - Perfect AI analytics
- /chatbot/perfect-health/ - Perfect AI health check

VERSIONED APIs:
- /chatbot/v2/* - Perfect AI endpoints (current)
- /chatbot/v1/* - Legacy endpoints

PLATFORM SPECIFIC:
- /chatbot/mobile/v2/* - Mobile app endpoints
- /chatbot/web/v2/* - Web app endpoints

ALTERNATIVE ACCESS:
- /chatbot/api/* - API prefix patterns
- /api/v2/chatbot/* - Root-level API access
- /api/v1/chatbot/* - Legacy root-level API access

MEMORY MANAGEMENT:
- /chatbot/sessions/<uuid:session_id>/reset-memory/ - Reset session memory
- /chatbot/sessions/<uuid:session_id>/reset-perfect-memory/ - Reset perfect memory

ADMIN & DEBUGGING:
- /chatbot/admin-api/* - Admin-specific endpoints
- /chatbot/system-health/ - System health alternative

INTEGRATIONS:
- /chatbot/integrations/* - Third-party integration endpoints
- /chatbot/webhooks/* - Webhook endpoints
"""