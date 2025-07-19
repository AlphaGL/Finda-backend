# chatbot/urls.py
from django.urls import path
from .views import chat_api, CustomAuthToken, LogoutView, verify_token, chat_history, health_check

# Remove the api/ prefix from here since it's already in your main URLs
urlpatterns = [
    # Keep your existing structure but fix the paths
    path('api/', chat_api, name='chatbot-api'),  # This will be /api/ when included
    path('token-auth/', CustomAuthToken.as_view(), name='api-token-auth'),  # This will be /api/token-auth/
    
    # Additional endpoints (optional)
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/verify/', verify_token, name='verify_token'),
    path('chat/history/', chat_history, name='chat_history'),
    path('health/', health_check, name='health_check'),
]