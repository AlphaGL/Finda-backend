# urls.py - Enhanced with new endpoints
from django.urls import path
from .views import chat_api, voice_chat_api, image_search_api, voice_settings_api, CustomAuthToken

urlpatterns = [
    # Existing endpoints
    path('api/', chat_api, name='chatbot-api'),
    path('api-token-auth/', CustomAuthToken.as_view()),
    
    # New multimedia endpoints
    path('api/voice/', voice_chat_api, name='voice-chat-api'),
    path('api/image/', image_search_api, name='image-search-api'),
    path('api/voice-settings/', voice_settings_api, name='voice-settings-api'),
]
