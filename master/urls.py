"""
URL configuration for master project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

# Custom error handler import
from django.conf.urls import handler404
from django.shortcuts import render

# API root endpoint
def api_root(request):
    return JsonResponse(
        {
    "message": "Welcome to Finda API",
    "status": "active",
    "endpoints": {
        "admin": "/admin/",
        "chatbot": "/chatbot/api/",
        "auth_register": "/api/auth/register/",
        "auth_login": "/api/auth/login/",
        "auth_logout": "/api/auth/logout/",
        "auth_me": "/api/auth/me/",
        "auth_dashboard": "/api/auth/dashboard/",
        "auth_password_reset": "/api/auth/password-reset/",
        "auth_password_reset_confirm": "/api/auth/password-reset-confirm/",
        "auth_change_password": "/api/auth/change-password/",
        "main_api": "/api/main/",
        "main_categories": "/api/main/categories/",
        "main_products": "/api/main/products/",
        "main_services": "/api/main/services/",
        "main_home": "/api/main/home/",
        "main_stats": "/api/main/stats/",
        "main_search": "/api/main/search/",
        "main_filter_options": "/api/main/filter-options/",
        "main_payments_initiate": "/api/main/payments/initiate/",
        "main_payments_verify": "/api/main/payments/verify/"
            }
        })

urlpatterns = [
    path('', api_root, name='api_root'),  # Add this line for the root endpoint
    path('admin/', admin.site.urls),
    # path('', include('main.urls')),
    path('chatbot/', include('chatbot.urls')),
    # path('auth/', include('users.urls')),
    path('api/auth/', include('users.api.urls')),
    path("api/main/", include("main.api.urls")),
    # For Google authentication
    path('accounts/', include('allauth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG is False:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom 404 error handler
def custom_404_view(request, exception):
    return JsonResponse({
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist',
        'status_code': 404
    }, status=404)

handler404 = custom_404_view