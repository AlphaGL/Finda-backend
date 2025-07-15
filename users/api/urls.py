from django.urls import path
from .views import RegisterAPI, LoginAPI, UserDetailAPI
from rest_framework.authtoken import views as drf_views

urlpatterns = [
    path('register/', RegisterAPI.as_view(), name='api-register'),
    path('login/',    LoginAPI.as_view(),    name='api-login'),
    path('me/',       UserDetailAPI.as_view(), name='api-user-detail'),
    # optional: an endpoint to just swap username/password for token:
    path('token-auth/', drf_views.obtain_auth_token, name='api-token-auth'),
]
