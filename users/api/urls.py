# users/api/urls.py
from django.urls import path
from .views import (
    RegisterAPI, 
    LoginAPI, 
    logout_api,
    UserDetailAPI,
    user_dashboard_api,
    password_reset_api,
    password_reset_confirm_api,
    change_password_api
)

urlpatterns = [
    # Authentication
    path('register/', RegisterAPI.as_view(), name='api-register'),
    path('login/', LoginAPI.as_view(), name='api-login'),
    path('logout/', logout_api, name='api-logout'),
    
    # User profile
    path('me/', UserDetailAPI.as_view(), name='api-user-detail'),
    path('dashboard/', user_dashboard_api, name='api-user-dashboard'),
    
    # Password management
    path('password-reset/', password_reset_api, name='api-password-reset'),
    path('password-reset-confirm/', password_reset_confirm_api, name='api-password-reset-confirm'),
    path('change-password/', change_password_api, name='api-change-password'),
]