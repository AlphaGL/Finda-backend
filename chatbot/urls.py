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
        # Main chat API
        path('chat/', views.ChatAPIView.as_view(), name='chat_api'),
        
        # Quick search for instant results
        path('quick-search/', views.quick_search_view, name='quick_search'),
        
        # Conversation management
        path('conversation/<uuid:session_id>/', views.conversation_history_api_view, name='conversation_history'),
        
        # Feedback
        path('feedback/', views.feedback_api_view, name='feedback'),
        
        # System status
        path('status/', views.chatbot_status_view, name='status'),
        
        # File upload endpoints
        path('upload/image/', views.ImageUploadView.as_view(), name='upload_image'),
        path('upload/voice/', views.VoiceUploadView.as_view(), name='upload_voice'),
        
        # Search suggestions
        path('suggestions/', views.SearchSuggestionsView.as_view(), name='search_suggestions'),
        
        # Analytics (admin only)
        path('analytics/', views.AnalyticsAPIView.as_view(), name='analytics_api'),
    ])),
    
    # Admin views
    path('admin/', include([
        path('analytics/', views.admin_analytics_view, name='admin_analytics'),
        path('configuration/', views.AdminConfigurationView.as_view(), name='admin_configuration'),
        path('sessions/', views.AdminSessionsView.as_view(), name='admin_sessions'),
    ])),
    
    # Widget embed
    path('widget/', views.ChatWidgetView.as_view(), name='chat_widget'),
    
    # Health check
    path('health/', views.health_check_view, name='health_check'),
]