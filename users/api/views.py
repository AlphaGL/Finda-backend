# users/api/views.py
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings

from .serializers import RegisterSerializer, UserSerializer, PasswordResetSerializer, PasswordResetConfirmSerializer
from main.models import Products, Services
from main.api.serializers import ProductsSerializer, ServicesSerializer

User = get_user_model()

from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse

@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({'detail': 'CSRF cookie set'})

class RegisterAPI(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Register a new user
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'Registration successful',
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class LoginAPI(ObtainAuthToken):
    """
    POST /api/auth/login/
    Login user and get token
    Body: {"email": "user@example.com", "password": "password"}
    """
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'Login successful',
            'token': token.key,
            'user': UserSerializer(user).data
        })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_api(request):
    """
    POST /api/auth/logout/
    Logout user (delete token)
    """
    try:
        # Delete the user's token to logout
        request.user.auth_token.delete()
        return Response({
            'message': 'Successfully logged out'
        }, status=status.HTTP_200_OK)
    except:
        return Response({
            'error': 'Error logging out'
        }, status=status.HTTP_400_BAD_REQUEST)

class UserDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /api/auth/me/ - Get current user profile
    PUT/PATCH /api/auth/me/ - Update current user profile
    DELETE /api/auth/me/ - Delete current user account
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.delete()
        return Response({
            'message': 'Account deleted successfully'
        }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_dashboard_api(request):
    """
    GET /api/auth/dashboard/
    Get user's dashboard data (products and services)
    """
    user = request.user
    
    # Get user's products
    products = Products.objects.filter(user=user)
    promoted_products = products.filter(is_promoted=True)
    
    # Get user's services
    services = Services.objects.filter(user=user)
    promoted_services = services.filter(is_promoted=True)
    
    return Response({
        'user': UserSerializer(user).data,
        'products': {
            'all': ProductsSerializer(products, many=True).data,
            'promoted': ProductsSerializer(promoted_products, many=True).data,
            'count': products.count()
        },
        'services': {
            'all': ServicesSerializer(services, many=True).data,
            'promoted': ServicesSerializer(promoted_services, many=True).data,
            'count': services.count()
        }
    })

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_api(request):
    """
    POST /api/auth/password-reset/
    Request password reset
    Body: {"email": "user@example.com"}
    """
    serializer = PasswordResetSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Create reset URL (you'll need to handle this in your frontend)
            reset_url = f"{settings.FRONTEND_URL}/password-reset/{uid}/{token}/"
            
            # Send email (you might want to use a proper email template)
            subject = "Password Reset Request"
            message = f"Click the link below to reset your password:\n{reset_url}"
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return Response({
                'message': 'Password reset email sent'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return Response({
                'message': 'If an account with this email exists, a password reset link has been sent.'
            }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_confirm_api(request):
    """
    POST /api/auth/password-reset-confirm/
    Confirm password reset
    Body: {"uid": "...", "token": "...", "password": "newpassword"}
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        password = serializer.validated_data['password']
        
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
            
            if default_token_generator.check_token(user, token):
                user.set_password(password)
                user.save()
                
                return Response({
                    'message': 'Password reset successful'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid reset token'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({
                'error': 'Invalid reset link'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password_api(request):
    """
    POST /api/auth/change-password/
    Change user password
    Body: {"old_password": "current", "new_password": "new"}
    """
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response({
            'error': 'Both old_password and new_password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not user.check_password(old_password):
        return Response({
            'error': 'Current password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user.set_password(new_password)
    user.save()
    
    # Delete old token and create new one
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    
    return Response({
        'message': 'Password changed successfully',
        'token': token.key  # Return new token
    }, status=status.HTTP_200_OK)