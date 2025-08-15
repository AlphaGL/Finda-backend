# ai_chatbot/urls.py
from django.urls import path, include
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Main chat interface
    path('', views.ChatInterfaceView.as_view(), name='chat_interface'),
    path('chat/', views.ChatInterfaceView.as_view(), name='chat_interface_alt'),
    
    # API endpoints
    path('api/', include([
        # Main chat API - supports both class-based and function-based views
        path('chat/', views.ChatAPIView.as_view(), name='chat_api'),
        path('chat/func/', views.chat_api, name='chat_api_func'),  # Function wrapper
        
        # Quick search for instant results
        path('search/', views.quick_search, name='quick_search'),
        path('quick-search/', views.quick_search, name='quick_search_alt'),  # Alternative URL
        
        # Conversation management
        path('conversation/<uuid:session_id>/', views.conversation_history_api_view, name='conversation_history'),
        path('sessions/<str:session_id>/', views.conversation_history_api_view, name='conversation_history_alt'),
        
        # Feedback system
        path('feedback/', views.feedback_api_view, name='feedback'),
        
        # System status and health
        path('status/', views.chatbot_status_view, name='status'),
        path('health/', views.health_check, name='health_check'),
        
        # File upload endpoints
        path('upload/', include([
            path('image/', views.ImageUploadView.as_view(), name='upload_image'),
            path('voice/', views.VoiceUploadView.as_view(), name='upload_voice'),
        ])),
        
        # Search and suggestions
        path('suggestions/', views.SearchSuggestionsView.as_view(), name='search_suggestions'),
        path('autocomplete/', views.SearchSuggestionsView.as_view(), name='autocomplete'),  # Alternative
        
        # Analytics (admin only)
        path('analytics/', views.AnalyticsAPIView.as_view(), name='analytics_api'),
    ])),
    
    # Admin views and management
    path('admin/', include([
        # Admin dashboard
        path('', views.admin_analytics_view, name='admin_dashboard'),
        path('analytics/', views.admin_analytics_view, name='admin_analytics'),
        
        # Configuration management
        path('configuration/', views.AdminConfigurationView.as_view(), name='admin_configuration'),
        path('config/', views.AdminConfigurationView.as_view(), name='admin_config_alt'),
        
        # Session management
        path('sessions/', views.AdminSessionsView.as_view(), name='admin_sessions'),
        
        # Additional admin endpoints can be added here
        # path('users/', views.AdminUsersView.as_view(), name='admin_users'),
        # path('reports/', views.AdminReportsView.as_view(), name='admin_reports'),
    ])),
    
    # Widget embed for external sites
    path('widget/', views.ChatWidgetView.as_view(), name='chat_widget'),
    path('embed/', views.ChatWidgetView.as_view(), name='chat_embed'),  # Alternative
    
    # Additional utility endpoints
    path('ping/', views.health_check, name='ping'),  # Simple ping endpoint
]

# Additional URL patterns for different use cases
# You can uncomment and modify these as needed:

# # WebSocket URLs (if using Django Channels)
# websocket_urlpatterns = [
#     path('ws/chat/', consumers.ChatConsumer.as_asgi()),
#     path('ws/chat/<str:session_id>/', consumers.ChatConsumer.as_asgi()),
# ]

# # API versioning (if needed in the future)
# v1_patterns = [
#     path('v1/', include([
#         path('chat/', views.ChatAPIView.as_view(), name='chat_api_v1'),
#         path('search/', views.quick_search, name='quick_search_v1'),
#     ]))
# ]

# # Mobile-specific endpoints (if needed)
# mobile_patterns = [
#     path('mobile/', include([
#         path('chat/', views.MobileChatAPIView.as_view(), name='mobile_chat_api'),
#         path('upload/voice/', views.MobileVoiceUploadView.as_view(), name='mobile_voice_upload'),
#     ]))
# ]

# You can extend urlpatterns like this if needed:
# urlpatterns += v1_patterns
# urlpatterns += mobile_patterns