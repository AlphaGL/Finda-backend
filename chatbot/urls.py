from django.urls import path
from .views import chat_api
from .views import CustomAuthToken

urlpatterns = [
    path('api/', chat_api, name='chatbot-api'),
    path('api-token-auth/', CustomAuthToken.as_view()),
]
